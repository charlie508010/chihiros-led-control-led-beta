"""Chihiros LED control CLI entrypoint."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, time

import typer
from bleak import BleakScanner
from rich import print
from rich.table import Table
from typing_extensions import Annotated

from . import commands, store
from .client import ChihirosDevice, ChihirosDosingPump, ChihirosMagStirrer
from .factory import detect_model, get_device_from_address
from .protocol import parse_doser_totals_frame
from .weekday_encoding import WeekdaySelect, encode_selected_weekdays

app = typer.Typer()
config_app = typer.Typer(help="Lokale CTL-Konfiguration")
template_app = typer.Typer(help="LED-Templates")
led_app = typer.Typer(help="LED CTL-Befehle")
doser_app = typer.Typer(help="Doser CTL-Befehle")
ruehrer_app = typer.Typer(help="Ruehrer/MagStirrer CTL-Befehle")
app.add_typer(config_app, name="config")
app.add_typer(template_app, name="template")
app.add_typer(led_app, name="led")
app.add_typer(doser_app, name="doser")
app.add_typer(ruehrer_app, name="ruehrer")
app.add_typer(ruehrer_app, name="magstirrer")

DeviceCommand = Callable[[ChihirosDevice], Awaitable[None]]
DEBUG_ENABLED = False
DEFAULT_DOSER_MAX_SINGLE_ML = 50.0
DEFAULT_DOSER_MAX_DAILY_ML = 250.0
DEFAULT_MAGSTIRRER_LEAD_TIME = 59
DEFAULT_MAGSTIRRER_SPEED = 20
DEFAULT_MAGSTIRRER_RESERVED = 0
DOSER_MAGSTIRRER_LINK_PREFIX = "doser_magstirrer_link"


def _enable_compact_debug_logging() -> None:
    logging.basicConfig(level=logging.WARNING)
    for logger_name in (
        "asyncio",
        "bleak",
        "bleak.backends",
        "bleak.backends.winrt",
        "bleak_retry_connector",
    ):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


@app.callback()
def main(
    debug: Annotated[bool, typer.Option("--debug", help="Debug-Ausgabe aktivieren")] = False,
) -> None:
    """Chihiros LED control CLI."""
    global DEBUG_ENABLED
    DEBUG_ENABLED = debug
    if debug:
        _enable_compact_debug_logging()


@doser_app.callback()
def doser_main(
    debug: Annotated[
        bool, typer.Option("--debug/--no-debug", help="Ausfuehrliche Doser-Debug-Ausgabe aktivieren")
    ] = False,
) -> None:
    """Doser CTL-Befehle."""
    global DEBUG_ENABLED
    if debug:
        DEBUG_ENABLED = True
        _enable_compact_debug_logging()


def _is_ble_address(value: str) -> bool:
    """Return whether a value is a complete colon-separated BLE address."""
    parts = value.strip().split(":")
    return len(parts) == 6 and all(
        len(part) == 2 and all(char in "0123456789abcdefABCDEF" for char in part) for part in parts
    )


def _run_device_func(device_address: str, command: DeviceCommand) -> None:
    async def _async_func() -> None:
        requested_address = device_address.strip()
        resolved_address = (
            requested_address if _is_ble_address(requested_address) else store.resolve_device_address(requested_address)
        )
        dev = await get_device_from_address(resolved_address)
        await command(dev)

    asyncio.run(_async_func())


def _weekday_mask(weekdays: list[WeekdaySelect]) -> int:
    return encode_selected_weekdays(weekdays)


def _parse_timer_entry(value: str) -> tuple[time, int]:
    if "=" not in value:
        raise typer.BadParameter("Timer must be HH:MM=SECONDS")
    time_text, seconds_text = value.split("=", 1)
    try:
        entry_time = datetime.strptime(time_text.strip(), "%H:%M").time()
    except ValueError as exc:
        raise typer.BadParameter("Timer time must be HH:MM") from exc
    try:
        seconds = int(seconds_text.strip())
    except ValueError as exc:
        raise typer.BadParameter("Timer value must be seconds") from exc
    if not 1 <= seconds <= 10922:
        raise typer.BadParameter("Timer seconds must be 1..10922")
    return entry_time, seconds * 6


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        parsed = datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError as exc:
        raise typer.BadParameter("Zeit muss HH:MM sein") from exc
    return parsed.hour, parsed.minute


def _duration_raw_from_seconds(seconds: int) -> int:
    if not 1 <= int(seconds) <= 10922:
        raise typer.BadParameter("Dauer muss 1..10922 Sekunden sein")
    return int(seconds) * 6


def _duration_seconds_from_raw(raw: int) -> float:
    return int(raw) / 6.0


def _parse_magstirrer_timer_block(value: str) -> dict[str, int]:
    if "=" not in value:
        raise typer.BadParameter("Timer muss HH:MM=SEKUNDEN sein")
    time_text, seconds_text = value.split("=", 1)
    hour, minute = _parse_hhmm(time_text)
    try:
        seconds = int(seconds_text.strip())
    except ValueError as exc:
        raise typer.BadParameter("Timer-Dauer muss Sekunden sein") from exc
    return {"hour": hour, "minute": minute, "duration_s": seconds, "value": _duration_raw_from_seconds(seconds)}


def _parse_magstirrer_window_block(value: str) -> dict[str, int]:
    if "=" not in value or "-" not in value:
        raise typer.BadParameter("Zeitfenster muss START-END=WERT sein")
    range_text, count_text = value.split("=", 1)
    start_text, end_text = range_text.split("-", 1)
    start_hour, start_minute = _parse_hhmm(start_text)
    end_hour, end_minute = _parse_hhmm(end_text)
    try:
        count = int(count_text.strip())
    except ValueError as exc:
        raise typer.BadParameter("Zeitfenster-Wert muss eine Zahl sein") from exc
    if not 1 <= count <= 24:
        raise typer.BadParameter("Zeitfenster-Wert muss 1..24 sein")
    return {
        "start_hour": start_hour,
        "start_minute": start_minute,
        "end_hour": end_hour,
        "end_minute": end_minute,
        "value": count,
    }


def _weekday_mask_text(mask: int) -> str:
    if int(mask) == 0x7F:
        return "taeglich"
    names = [(64, "Mo"), (32, "Di"), (16, "Mi"), (8, "Do"), (4, "Fr"), (2, "Sa"), (1, "So")]
    selected = [name for bit, name in names if int(mask) & bit]
    return ", ".join(selected) if selected else "-"


def _magstirrer_device_key(device_address: str | None) -> str:
    return store.resolve_device_address(device_address or "ruehrer_1").upper()


def _magstirrer_channel_names(device_address: str | None = None) -> dict[int, str]:
    return store.list_channel_names("ruehrer", _magstirrer_device_key(device_address))


def _magstirrer_channel_name(ch_id: int, device_address: str | None = None) -> str:
    return _magstirrer_channel_names(device_address).get(int(ch_id), f"CH{int(ch_id) + 1}")


def _magstirrer_entries_for_client(entries: list[dict[str, int]]) -> list[tuple[time, int]]:
    return [(_time_from_parts(int(item["hour"]), int(item["minute"])), int(item["value"])) for item in entries]


def _time_from_parts(hour: int, minute: int) -> time:
    return time(hour=int(hour), minute=int(minute))


def _format_magstirrer_entry(row: dict[str, object]) -> str:
    entries = row.get("entries") or []
    kind = str(row.get("schedule_kind") or "")
    parts: list[str] = []
    if kind == "window":
        for item in entries if isinstance(entries, list) else []:
            parts.append(
                f"{int(item['start_hour']):02d}:{int(item['start_minute']):02d}-"
                f"{int(item['end_hour']):02d}:{int(item['end_minute']):02d}={int(item['value'])}"
            )
    else:
        for item in entries if isinstance(entries, list) else []:
            parts.append(
                f"{int(item['hour']):02d}:{int(item['minute']):02d}="
                f"{_duration_seconds_from_raw(int(item['value'])):.0f}s"
            )
    return (
        f"Lokal: CH{int(row['channel']) + 1}, Art={kind or '-'}, "
        f"timer_type={int(row.get('timer_type') or 0)}, "
        f"Wochentage={_weekday_mask_text(int(row.get('weekdays_mask') or 0))}, "
        f"Status={'aktiv' if int(row.get('enabled') or 0) else 'inaktiv'}, "
        f"Eintraege={', '.join(parts) if parts else '-'}, Quelle={row.get('source') or '-'}"
    )


def _format_brightness(values: list[int]) -> str:
    names = ["Rot", "Gruen", "Blau", "Weiss"]
    if len(values) == 1:
        return f"Gesamt={values[0]}%"
    return ", ".join(f"{name}={value}%" for name, value in zip(names, values))


def _print_template_rows(rows: list[tuple[str, list[int]]]) -> None:
    table = Table("Name", "Werte")
    for name, values in rows:
        table.add_row(name, _format_brightness(values))
    print(table)


def _print_raw_notifications(dev: ChihirosDevice, *, title: str = "Debug") -> None:
    print(title)
    print(f"Device: {dev.address}")
    print(f"Notifications: {len(dev.raw_notifications)}")
    for index, payload in enumerate(dev.raw_notifications, start=1):
        print(f"RX {index}: {payload.hex(' ')}")


def _print_raw_tx_frames(dev: ChihirosDevice) -> None:
    tx_frames = list(getattr(dev, "tx_debug_frames", []))
    if not tx_frames:
        return
    print("")
    print("GESENDET")
    for index, payload in enumerate(tx_frames, start=1):
        print(f"TX {index}: {payload.hex(' ').upper()}")
    print("-" * 72)


def _print_compare_log(dev: ChihirosDevice) -> None:
    output = dev.render_compare_log(tx_commands={0xA5})
    if output:
        print("")
        print(output)


def _decoded_doser_totals(dev: ChihirosDevice) -> tuple[int, list[float]] | None:
    for payload in reversed(dev.raw_notifications):
        totals = parse_doser_totals_frame(payload)
        if totals is not None:
            return payload[5] if len(payload) > 5 else 0, totals
    return None


def _print_doser_rx_return(dev: ChihirosDevice) -> tuple[int, list[float]] | None:
    if hasattr(dev, "render_raw_notifications"):
        output = dev.render_raw_notifications(dedupe=True)
        if output:
            print("")
            print(output)
        return _decoded_doser_totals(dev)
    if not dev.raw_notifications:
        return None
    print("")
    print("-" * 72)
    print("GERÄTEANTWORT")
    print("-" * 72)
    seen: set[bytes] = set()
    for payload in dev.raw_notifications:
        payload_bytes = bytes(payload)
        if payload_bytes in seen:
            continue
        seen.add(payload_bytes)
        print(f"RX: {payload.hex(' ').upper()}")
    print("-" * 72)
    return _decoded_doser_totals(dev)


def _print_doser_manual_summary(
    device_address: str,
    pump: int,
    ml: float,
    decoded: tuple[int, list[float]] | None,
) -> None:
    print("")
    print("-" * 72)
    print("ZUSAMMENFASSUNG")
    print("-" * 72)
    print(f"Aktion: manuelle Dosierung | Kanal: CH{pump} | Menge: {ml:.1f} ml")
    if decoded is not None:
        mode, totals = decoded
        print("Geräteantwort:")
        print(f"  0x{mode:02X}: {_format_channels_debug(totals)}")
    print(f"Lokal: {_format_channels_debug(store.get_manual_daily_totals(device_address))}")
    remaining = float(store.get_containers(device_address).get(str(pump - 1), 0.0))
    print(f"Lokal: Behaelter CH{pump} um {ml:.2f} ml reduziert; Rest={remaining:.2f} ml")


def _print_doser_totals_summary(totals: list[float] | None) -> None:
    print("")
    print("ZUSAMMENFASSUNG")
    print("Aktion: automatische Tageswerte lesen")
    if totals is not None:
        print("Geraeteantwort:")
        print(f"  {_format_channels(totals)}")


def _print_doser_command_debug(dev: ChihirosDevice, *, title: str) -> None:
    _print_raw_notifications(dev, title=title)
    _print_raw_tx_frames(dev)
    _print_compare_log(dev)
    _print_doser_rx_return(dev)


def _clear_debug_frames(dev: ChihirosDevice) -> None:
    if hasattr(dev, "clear_debug_buffers"):
        dev.clear_debug_buffers()
        return
    dev.raw_notifications.clear()
    if hasattr(dev, "tx_debug_frames"):
        dev.tx_debug_frames.clear()
    if hasattr(dev, "debug_frames"):
        dev.debug_frames.clear()


def _print_led_protocol_debug(dev: ChihirosDevice) -> None:
    if hasattr(dev, "render_protocol_debug"):
        output = dev.render_protocol_debug(dedupe_rx=True)
        if output:
            print(output)
        return
    _print_raw_notifications(dev, title="LED debug")
    _print_raw_tx_frames(dev)


def _format_channels(values: list[float] | dict[str, float]) -> str:
    if isinstance(values, dict):
        ordered = [float(values.get(str(index), 0.0)) for index in range(4)]
    else:
        ordered = [float(value) for value in values[:4]]
    return ", ".join(f"CH{index + 1} {value:.1f} ml" for index, value in enumerate(ordered))


def _format_channels_debug(values: list[float] | dict[str, float]) -> str:
    if isinstance(values, dict):
        ordered = [float(values.get(str(index), 0.0)) for index in range(4)]
    else:
        ordered = [float(value) for value in values[:4]]
    return ", ".join(f"CH{index + 1}={value:.2f} ml" for index, value in enumerate(ordered))


def _state_device(device_address: str) -> str:
    return store.resolve_device_address(device_address).upper()


def _doser_kind_text(kind: str) -> str:
    return {
        "single_dose": "Einzeldosis",
        "interval": "Intervall",
        "timer": "Timerliste",
        "window": "Zeitfenster",
    }.get(kind, kind)


def _channel_index(ch_id: int) -> int:
    return int(ch_id) - 1


def _legacy_kind(kind: str) -> str:
    normalized = kind.strip().lower()
    if normalized in {"magstirrer", "mag", "rührer", "stirrer"}:
        return "ruehrer"
    return store.normalize_kind(normalized)


def _magstirrer_runtime_setting_key(device_key: str, ch_id: int) -> str:
    return f"magstirrer_runtime.{str(device_key).upper()}.{int(ch_id)}"


def _doser_magstirrer_link_key(doser_device: str, doser_ch_id: int) -> str:
    device_key = store.resolve_device_address(doser_device).upper()
    return f"{DOSER_MAGSTIRRER_LINK_PREFIX}.{device_key}.{int(doser_ch_id)}"


def _setting_float(key: str, fallback: float) -> float:
    raw = store.get_setting(key)
    try:
        return float(raw) if raw is not None else fallback
    except ValueError:
        return fallback


def _setting_int(key: str, fallback: int) -> int:
    raw = store.get_setting(key)
    try:
        return int(raw) if raw is not None else fallback
    except ValueError:
        return fallback


@config_app.command("path")
def config_path() -> None:
    """Show the local CTL SQLite path."""
    print(str(store.state_db_path()))


@config_app.command("set-device")
def config_set_device(
    kind: Annotated[str, typer.Argument(help="led, doser, ruehrer oder heizer")],
    index: Annotated[int, typer.Argument(min=1)],
    address: Annotated[str, typer.Argument(help="MAC-Adresse oder ID")],
    alias: Annotated[str | None, typer.Option("--alias")] = None,
    label: Annotated[str, typer.Option("--label")] = "",
    model: Annotated[str, typer.Option("--model")] = "",
) -> None:
    """Store one local device alias."""
    row = store.set_device(kind, index, address, alias=alias, label=label, model=model)
    print(f"OK: {row['alias']} -> {row['address']}")


@config_app.command("delete-device")
def config_delete_device(
    kind: Annotated[str, typer.Argument(help="led, doser, ruehrer oder heizer")],
    alias_or_index: Annotated[str, typer.Argument(help="Alias oder Nummer")],
) -> None:
    """Delete one local device alias."""
    deleted = store.delete_device(kind, alias_or_index)
    print("OK: deleted" if deleted else "Not found")


@config_app.command("show-device")
def config_show_device(
    kind: Annotated[str, typer.Argument(help="led, doser, ruehrer oder heizer")],
    alias_or_index: Annotated[str, typer.Argument(help="Alias oder Nummer")],
) -> None:
    """Show one local device alias."""
    alias = alias_or_index if not alias_or_index.isdigit() else store.default_alias(kind, int(alias_or_index))
    for row in store.list_devices(kind):
        if row.get("alias") == alias:
            label = row.get("label") or "-"
            model = row.get("model") or "-"
            print(f"{row['kind']} {row['alias']} -> {row['address']} Label={label} Model={model}")
            return
    print("Not found")


@config_app.command("list-devices")
def config_list_devices(kind: Annotated[str | None, typer.Option("--kind")] = None) -> None:
    """List local device aliases."""
    table = Table("Kind", "Alias", "Address", "Label", "Model")
    for row in store.list_devices(kind):
        table.add_row(
            row.get("kind", ""),
            row.get("alias", ""),
            row.get("address", ""),
            row.get("label", ""),
            row.get("model", ""),
        )
    print(table)


@config_app.command("resolve")
def config_resolve(device: str) -> None:
    """Resolve a local alias to its address."""
    print(store.resolve_device_address(device))


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    """Set one local string setting."""
    store.set_setting(key, value)
    print("OK")


@config_app.command("get")
def config_get(key: str) -> None:
    """Get one local string setting."""
    value = store.get_setting(key)
    print("" if value is None else value)


@config_app.command("list")
def config_list(prefix: Annotated[str, typer.Option("--prefix")] = "") -> None:
    """List local settings."""
    table = Table("Key", "Value")
    for key, value in store.list_settings(prefix):
        table.add_row(key, value)
    print(table)


@config_app.command("delete")
def config_delete(key: str) -> None:
    """Delete one local setting."""
    print("OK: deleted" if store.delete_setting(key) else "Not found")


@config_app.command("set-language")
def config_set_language(language: Annotated[str, typer.Argument(help="de or en")]) -> None:
    """Store the preferred local CTL language."""
    language = language.strip().lower()
    if language not in {"de", "en"}:
        raise typer.BadParameter("language must be de or en")
    store.set_setting("language", language)
    print("OK")


@config_app.command("show-language")
def config_show_language() -> None:
    """Show the preferred local CTL language."""
    print(store.get_setting("language", "de"))


@config_app.command("delete-language")
def config_delete_language() -> None:
    """Delete the preferred local CTL language."""
    print("OK: deleted" if store.delete_setting("language") else "Not found")


def _config_set_indexed_device(kind: str, index: int, address: str) -> None:
    row = store.set_device(kind, index, address)
    print(f"OK: {row['alias']} -> {row['address']}")


def _config_show_indexed_device(kind: str, index: int) -> None:
    alias = store.default_alias(kind, index)
    print(store.resolve_device_address(alias))


def _config_delete_indexed_device(kind: str, index: int) -> None:
    print("OK: deleted" if store.delete_device(kind, str(index)) else "Not found")


@config_app.command("set-doser")
def config_set_doser(index: Annotated[int, typer.Argument(min=1, max=4)], address: str) -> None:
    """Compatibility alias for storing a Doser device."""
    _config_set_indexed_device("doser", index, address)


@config_app.command("show-doser")
def config_show_doser(index: Annotated[int, typer.Argument(min=1, max=4)] = 1) -> None:
    """Compatibility alias for showing a Doser device."""
    _config_show_indexed_device("doser", index)


@config_app.command("delete-doser")
def config_delete_doser(index: Annotated[int, typer.Argument(min=1, max=4)] = 1) -> None:
    """Compatibility alias for deleting a Doser device."""
    _config_delete_indexed_device("doser", index)


@config_app.command("set-led")
def config_set_led(index: Annotated[int, typer.Argument(min=1, max=4)], address: str) -> None:
    """Compatibility alias for storing an LED device."""
    _config_set_indexed_device("led", index, address)


@config_app.command("show-led")
def config_show_led(index: Annotated[int, typer.Argument(min=1, max=4)] = 1) -> None:
    """Compatibility alias for showing an LED device."""
    _config_show_indexed_device("led", index)


@config_app.command("delete-led")
def config_delete_led(index: Annotated[int, typer.Argument(min=1, max=4)] = 1) -> None:
    """Compatibility alias for deleting an LED device."""
    _config_delete_indexed_device("led", index)


@config_app.command("set-magstirrer")
def config_set_magstirrer(index: Annotated[int, typer.Argument(min=1, max=4)], address: str) -> None:
    """Compatibility alias for storing a MagStirrer device."""
    _config_set_indexed_device("ruehrer", index, address)


@config_app.command("show-magstirrer")
def config_show_magstirrer(index: Annotated[int, typer.Argument(min=1, max=4)] = 1) -> None:
    """Compatibility alias for showing a MagStirrer device."""
    _config_show_indexed_device("ruehrer", index)


@config_app.command("delete-magstirrer")
def config_delete_magstirrer(index: Annotated[int, typer.Argument(min=1, max=4)] = 1) -> None:
    """Compatibility alias for deleting a MagStirrer device."""
    _config_delete_indexed_device("ruehrer", index)


@config_app.command("set-doser-safety")
def config_set_doser_safety(
    max_single_ml: Annotated[float, typer.Option("--max-single-ml", min=0.2)] = DEFAULT_DOSER_MAX_SINGLE_ML,
    max_daily_ml: Annotated[float, typer.Option("--max-daily-ml", min=0.2)] = DEFAULT_DOSER_MAX_DAILY_ML,
) -> None:
    """Store local Doser safety limits."""
    if max_daily_ml < max_single_ml:
        raise typer.BadParameter("--max-daily-ml muss groesser/gleich --max-single-ml sein")
    store.set_setting("doser_safety.max_single_ml", f"{float(max_single_ml):.1f}")
    store.set_setting("doser_safety.max_daily_ml", f"{float(max_daily_ml):.1f}")
    print(f"Doser-Schutz gespeichert: Einzeldosis={max_single_ml:.1f} ml, Tagesmenge={max_daily_ml:.1f} ml")


@config_app.command("show-doser-safety")
def config_show_doser_safety() -> None:
    """Show local Doser safety limits."""
    print(
        "Doser-Schutz: "
        f"Einzeldosis={_setting_float('doser_safety.max_single_ml', DEFAULT_DOSER_MAX_SINGLE_ML):.1f} ml, "
        f"Tagesmenge={_setting_float('doser_safety.max_daily_ml', DEFAULT_DOSER_MAX_DAILY_ML):.1f} ml"
    )


@config_app.command("delete-doser-safety")
def config_delete_doser_safety() -> None:
    """Delete local Doser safety limits."""
    deleted = store.delete_setting("doser_safety.max_single_ml") or store.delete_setting("doser_safety.max_daily_ml")
    print("OK: deleted" if deleted else "Not found")


@config_app.command("set-doser-magstirrer-link")
def config_set_doser_magstirrer_link(
    doser_device: str,
    magstirrer_device: str,
    doser_ch_id: Annotated[int, typer.Option("--doser-ch-id", min=0, max=3)] = 0,
    enabled: Annotated[bool, typer.Option("--enabled/--disabled")] = True,
) -> None:
    """Store a local Doser/MagStirrer link."""
    doser_key = store.resolve_device_address(doser_device).upper()
    mag_key = store.resolve_device_address(magstirrer_device).upper()
    data = {
        "enabled": bool(enabled),
        "doser_device": doser_device,
        "doser_key": doser_key,
        "doser_ch_id": int(doser_ch_id),
        "magstirrer_device": magstirrer_device,
        "magstirrer_key": mag_key,
        "magstirrer_ch_id": int(doser_ch_id),
    }
    store.set_setting(_doser_magstirrer_link_key(doser_device, doser_ch_id), json.dumps(data, ensure_ascii=False))
    print(f"OK: {doser_key} CH{doser_ch_id + 1} -> {mag_key} CH{doser_ch_id + 1}")


@config_app.command("set-doser-magstirrer-link-active")
def config_set_doser_magstirrer_link_active(
    doser_device: str,
    doser_ch_id: Annotated[int, typer.Option("--doser-ch-id", min=0, max=3)] = 0,
    enabled: Annotated[bool, typer.Option("--enabled/--disabled")] = True,
) -> None:
    """Enable or disable a stored Doser/MagStirrer link."""
    key = _doser_magstirrer_link_key(doser_device, doser_ch_id)
    raw = store.get_setting(key)
    if not raw:
        raise typer.BadParameter("Keine Doser/Ruehrer-Verknuepfung fuer diesen Doser-Kanal gespeichert")
    data = json.loads(raw)
    data["enabled"] = bool(enabled)
    store.set_setting(key, json.dumps(data, ensure_ascii=False))
    print(f"OK: Doser/Ruehrer-Verknuepfung CH{doser_ch_id + 1} ist {'aktiv' if enabled else 'inaktiv'}")


@config_app.command("show-doser-magstirrer-links")
def config_show_doser_magstirrer_links() -> None:
    """Show stored Doser/MagStirrer links."""
    rows = store.list_settings(f"{DOSER_MAGSTIRRER_LINK_PREFIX}.")
    if not rows:
        print("Keine Doser/Ruehrer-Verknuepfungen gespeichert.")
        return
    for _key, value in rows:
        data = json.loads(value)
        print(
            f"{data.get('doser_key')} CH{int(data.get('doser_ch_id', 0)) + 1} -> "
            f"{data.get('magstirrer_key')} CH{int(data.get('magstirrer_ch_id', data.get('doser_ch_id', 0))) + 1}, "
            f"Status={'aktiv' if data.get('enabled') else 'inaktiv'}"
        )


@config_app.command("delete-doser-magstirrer-link")
def config_delete_doser_magstirrer_link(
    doser_device: str,
    doser_ch_id: Annotated[int, typer.Option("--doser-ch-id", min=0, max=3)] = 0,
) -> None:
    """Delete a stored Doser/MagStirrer link."""
    print("OK: deleted" if store.delete_setting(_doser_magstirrer_link_key(doser_device, doser_ch_id)) else "Not found")


@config_app.command("show-magstirrer-defaults")
def config_show_magstirrer_defaults() -> None:
    """Show local MagStirrer defaults."""
    print(
        "Ruehrer-Standardwerte: "
        f"lead-time={_setting_int('magstirrer.default.lead_time', DEFAULT_MAGSTIRRER_LEAD_TIME)}, "
        f"speed={_setting_int('magstirrer.default.speed', DEFAULT_MAGSTIRRER_SPEED)}"
    )


@config_app.command("set-magstirrer-defaults")
def config_set_magstirrer_defaults(
    lead_time: Annotated[int, typer.Option("--lead-time", min=0, max=59)] = DEFAULT_MAGSTIRRER_LEAD_TIME,
    speed: Annotated[int, typer.Option("--speed", min=0, max=20)] = DEFAULT_MAGSTIRRER_SPEED,
) -> None:
    """Store local MagStirrer defaults."""
    store.set_setting("magstirrer.default.lead_time", str(int(lead_time)))
    store.set_setting("magstirrer.default.speed", str(int(speed)))
    print(f"OK: Ruehrer-Standardwerte gespeichert: lead-time={lead_time}, speed={speed}")


@config_app.command("set-magstirrer-runtime")
def config_set_magstirrer_runtime(
    magstirrer_device: str,
    ch_id: Annotated[int | None, typer.Option("--ch-id", min=0, max=3)] = None,
    channel: Annotated[int | None, typer.Option("--channel", min=1, max=4)] = None,
    runtime_min: Annotated[int | None, typer.Option("--runtime-min", min=0, max=59)] = None,
    speed: Annotated[int | None, typer.Option("--speed", min=0, max=20)] = None,
    reserved: Annotated[int | None, typer.Option("--reserved", min=0, max=255)] = None,
) -> None:
    """Store local MagStirrer runtime defaults for one channel."""
    effective_ch_id = int(ch_id if ch_id is not None else ((channel - 1) if channel is not None else 0))
    mag_key = store.resolve_device_address(magstirrer_device).upper()
    data = {
        "magstirrer_key": mag_key,
        "ch_id": effective_ch_id,
        "runtime_min": _setting_int("magstirrer.default.lead_time", DEFAULT_MAGSTIRRER_LEAD_TIME)
        if runtime_min is None
        else int(runtime_min),
        "speed": _setting_int("magstirrer.default.speed", DEFAULT_MAGSTIRRER_SPEED) if speed is None else int(speed),
        "reserved": DEFAULT_MAGSTIRRER_RESERVED if reserved is None else int(reserved),
    }
    store.set_setting(_magstirrer_runtime_setting_key(mag_key, effective_ch_id), json.dumps(data, ensure_ascii=False))
    print(f"OK: Ruehrer-Runtime lokal gespeichert: {mag_key} CH{effective_ch_id + 1}")


@config_app.command("show-magstirrer-runtime")
def config_show_magstirrer_runtime() -> None:
    """Show local MagStirrer runtime defaults."""
    rows = store.list_settings("magstirrer_runtime.")
    if not rows:
        print("Keine Ruehrer-Runtime gespeichert.")
        return
    for key, value in rows:
        data = json.loads(value)
        print(
            f"{data.get('magstirrer_key') or key} CH{int(data.get('ch_id', 0)) + 1}: "
            f"runtime_min={int(data.get('runtime_min', 0))}, speed={int(data.get('speed', 0))}, "
            f"reserved={int(data.get('reserved', 0))}"
        )


@config_app.command("delete-magstirrer-runtime")
def config_delete_magstirrer_runtime(
    magstirrer_device: str,
    ch_id: Annotated[int | None, typer.Option("--ch-id", min=0, max=3)] = None,
    channel: Annotated[int | None, typer.Option("--channel", min=1, max=4)] = None,
) -> None:
    """Delete local MagStirrer runtime defaults for one channel."""
    effective_ch_id = int(ch_id if ch_id is not None else ((channel - 1) if channel is not None else 0))
    mag_key = store.resolve_device_address(magstirrer_device).upper()
    print(
        "OK: deleted"
        if store.delete_setting(_magstirrer_runtime_setting_key(mag_key, effective_ch_id))
        else "Not found"
    )


@config_app.command("db-info")
def config_db_info() -> None:
    """Show local CTL state database information."""
    info = store.state_db_info()
    print(f"path: {info['path']}")
    for table, count in info["tables"].items():
        print(f"{table}: {count}")


@config_app.command("db-migrate")
def config_db_migrate() -> None:
    """Create or migrate local CTL state tables."""
    store.init_state_db()
    print("SQLite migration complete.")


@config_app.command("list-profiles")
def config_list_profiles(kind: Annotated[str | None, typer.Option("--kind")] = None) -> None:
    """Compatibility alias for listing device profiles."""
    config_list_devices(kind)


@config_app.command("set-device-name")
def config_set_device_name(kind: str, device: str, name: str) -> None:
    """Store a local display name for a configured device."""
    if not store.update_device_fields(_legacy_kind(kind), device, label=name):
        row = store.set_device(_legacy_kind(kind), 1, store.resolve_device_address(device), alias=device, label=name)
        print(f"OK: {row['alias']} -> {row['address']}")
    else:
        print("OK")


@config_app.command("delete-device-name")
def config_delete_device_name(kind: str, device: str) -> None:
    """Delete a local display name for a configured device."""
    print("OK" if store.update_device_fields(_legacy_kind(kind), device, label="") else "Not found")


@config_app.command("set-device-model")
def config_set_device_model(kind: str, device: str, model: str) -> None:
    """Store a local model name for a configured device."""
    if not store.update_device_fields(_legacy_kind(kind), device, model=model):
        row = store.set_device(_legacy_kind(kind), 1, store.resolve_device_address(device), alias=device, model=model)
        print(f"OK: {row['alias']} -> {row['address']}")
    else:
        print("OK")


@config_app.command("delete-device-model")
def config_delete_device_model(kind: str, device: str) -> None:
    """Delete a local model name for a configured device."""
    print("OK" if store.update_device_fields(_legacy_kind(kind), device, model="") else "Not found")


@config_app.command("set-channel-name")
def config_set_channel_name(
    kind: str,
    device: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=0, max=3)],
    name: str,
) -> None:
    """Store a local channel display name."""
    store.set_channel_name(_legacy_kind(kind), store.resolve_device_address(device), ch_id, name)
    print("OK")


@config_app.command("delete-channel-name")
def config_delete_channel_name(
    kind: str,
    device: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=0, max=3)],
) -> None:
    """Delete a local channel display name."""
    key = f"channel_name.{_legacy_kind(kind)}.{store.resolve_device_address(device).upper()}.{int(ch_id)}"
    print("OK: deleted" if store.delete_setting(key) else "Not found")


@config_app.command("show-local-names")
def config_show_local_names(
    kind: Annotated[str | None, typer.Option("--kind")] = None,
    device: Annotated[str | None, typer.Option("--device")] = None,
) -> None:
    """Show local device and channel names."""
    for row in store.list_devices(_legacy_kind(kind) if kind else None):
        if (
            device
            and row.get("alias") != device
            and row.get("address", "").upper() != store.resolve_device_address(device).upper()
        ):
            continue
        print(f"Geraet: {row['kind']} {row['alias']}={row['address']} Name={row.get('label') or '-'}")
        names = store.list_channel_names(row["kind"], row["address"])
        for ch_id, name in sorted(names.items()):
            print(f"  CH{ch_id + 1}: {name}")


@template_app.command("set-template-standart")
def template_legacy_set_standard(
    template_name: Annotated[str, typer.Option("--template-name")],
    brightness: Annotated[list[int], typer.Argument(min=0, max=100)],
) -> None:
    """Compatibility alias for updating a standard LED template."""
    template_set_standard(template_name, brightness)


@template_app.command("create-standard-template")
def template_legacy_create_standard(
    template_name: Annotated[str, typer.Option("--template-name")],
    brightness: Annotated[list[int], typer.Argument(min=0, max=100)],
) -> None:
    """Compatibility alias for creating a standard LED template."""
    template_set_standard(template_name, brightness)


@template_app.command("set-standard")
def template_set_standard(
    template_name: Annotated[str, typer.Option("--template-name")],
    brightness: Annotated[list[int], typer.Argument(min=0, max=100)],
) -> None:
    """Create or update a standard LED template."""
    store.set_standard_template(template_name, brightness)
    print("OK")


@template_app.command("list-standard")
def template_list_standard() -> None:
    """List standard LED templates."""
    _print_template_rows(store.list_standard_templates())


@template_app.command("delete-standard")
def template_delete_standard(template_name: Annotated[str, typer.Option("--template-name")]) -> None:
    """Delete a standard LED template."""
    print("OK: deleted" if store.delete_standard_template(template_name) else "Not found")


@template_app.command("delete-standard-template")
def template_legacy_delete_standard(template_name: Annotated[str, typer.Option("--template-name")]) -> None:
    """Compatibility alias for deleting a standard LED template."""
    template_delete_standard(template_name)


@template_app.command("list-standard-templates")
def template_legacy_list_standard() -> None:
    """Compatibility alias for listing standard LED templates."""
    template_list_standard()


@template_app.command("set")
def template_set(
    device_address: str,
    template_name: Annotated[str, typer.Option("--template-name")],
    brightness: Annotated[list[int], typer.Argument(min=0, max=100)],
) -> None:
    """Create or update a device LED template."""
    store.set_device_template(device_address, template_name, brightness)
    print("OK")


@template_app.command("set-template")
def template_legacy_set(
    device_address: str,
    template_name: Annotated[str, typer.Option("--template-name")],
    brightness: Annotated[list[int], typer.Argument(min=0, max=100)],
) -> None:
    """Compatibility alias for updating a device LED template."""
    template_set(device_address, template_name, brightness)


@template_app.command("create-template")
def template_legacy_create(
    device_address: str,
    template_name: Annotated[str, typer.Option("--template-name")],
    brightness: Annotated[list[int], typer.Argument(min=0, max=100)],
) -> None:
    """Compatibility alias for creating a device LED template."""
    template_set(device_address, template_name, brightness)


@template_app.command("list")
def template_list(device_address: str) -> None:
    """List device LED templates."""
    _print_template_rows(store.list_device_templates(device_address))


@template_app.command("list-templates")
@template_app.command("show")
def template_legacy_list(device_address: str) -> None:
    """Compatibility alias for listing device LED templates."""
    template_list(device_address)


@template_app.command("delete")
def template_delete(device_address: str, template_name: Annotated[str, typer.Option("--template-name")]) -> None:
    """Delete a device LED template."""
    print("OK: deleted" if store.delete_device_template(device_address, template_name) else "Not found")


@template_app.command("delete-template")
def template_legacy_delete(device_address: str, template_name: Annotated[str, typer.Option("--template-name")]) -> None:
    """Compatibility alias for deleting a device LED template."""
    template_delete(device_address, template_name)


@template_app.command("load")
def template_load(
    device_address: str,
    template_name: Annotated[str, typer.Option("--template-name")],
    standard: Annotated[bool, typer.Option("--standard/--device-template")] = False,
) -> None:
    """Load a stored LED template and send it as brightness."""
    values = (
        store.get_standard_template(template_name)
        if standard
        else store.get_device_template(device_address, template_name)
    )
    if values is None:
        raise typer.BadParameter(f"Template not found: {template_name}")
    _run_device_func(device_address, lambda dev: dev.set_brightness(values))


@template_app.command("load-template")
def template_legacy_load(
    device_address: str,
    template_name: Annotated[str, typer.Option("--template-name")],
) -> None:
    """Compatibility alias for loading a device LED template."""
    template_load(device_address, template_name, standard=False)


@template_app.command("load-template-standart")
def template_legacy_load_standard(
    device_address: str,
    template_name: Annotated[str, typer.Option("--template-name")],
) -> None:
    """Compatibility alias for loading a standard LED template."""
    template_load(device_address, template_name, standard=True)


@template_app.command("set-on-preset")
def template_set_on_preset(
    device_address: str,
    brightness: Annotated[list[int], typer.Argument(min=0, max=100)],
) -> None:
    """Store brightness values used by local turn-on workflows."""
    store.set_led_on_preset(device_address, brightness)
    print(f"OK: {store.resolve_device_address(device_address).upper()} -> {_format_brightness(brightness)}")


@template_app.command("show-on-preset")
def template_show_on_preset(device_address: Annotated[str, typer.Argument()] = "") -> None:
    """Show stored local turn-on brightness values."""
    rows = store.list_led_on_presets(device_address or None)
    if not rows:
        print("Keine LED-On-Presets gespeichert.")
        return
    for row in rows:
        print(
            f"Lokal: {row['device_key']}: {_format_brightness(row['values'])}, Aktualisiert={row.get('updated_at') or ''}"
        )


@template_app.command("clear-on-preset")
def template_clear_on_preset(device_address: str) -> None:
    """Delete stored local turn-on brightness values."""
    print("OK: deleted" if store.delete_led_on_preset(device_address) else "Not found")


@led_app.command("list-devices")
@app.command()
def list_devices(timeout: Annotated[int, typer.Option()] = 5) -> None:
    """List all bluetooth devices."""
    table = Table("Name", "Address", "Model")
    discovered_devices = asyncio.run(BleakScanner.discover(timeout=timeout))
    for device in discovered_devices:
        model = detect_model(device.name)
        model_name = "???" if model.fallback else model.name
        table.add_row(device.name, device.address, model_name)
    print("Discovered the following devices:")
    print(table)


@led_app.command("turn-on")
@app.command()
def turn_on(device_address: str) -> None:
    """Turn on a light."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.turn_on()
        if DEBUG_ENABLED:
            _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


@led_app.command("turn-off")
@app.command()
def turn_off(device_address: str) -> None:
    """Turn off a light."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.turn_off()
        if DEBUG_ENABLED:
            _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


@led_app.command("set-brightness")
@app.command()
def set_brightness(device_address: str, brightness: Annotated[list[int], typer.Argument()]) -> None:
    """Set brightness of a light."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.set_brightness(brightness)
        if DEBUG_ENABLED:
            _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


@led_app.command("add-setting")
@app.command()
def add_setting(
    device_address: str,
    sunrise: Annotated[datetime, typer.Argument(formats=["%H:%M"])],
    sunset: Annotated[datetime, typer.Argument(formats=["%H:%M"])],
    max_brightness: Annotated[list[int], typer.Argument()],
    ramp_up_in_minutes: Annotated[int, typer.Option(min=1, max=150)] = 1,
    weekdays: Annotated[list[WeekdaySelect], typer.Option()] = [WeekdaySelect.everyday],
) -> None:
    """Add setting to a light."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.add_setting(
            sunrise=sunrise,
            sunset=sunset,
            max_brightness=max_brightness,
            ramp_up_in_minutes=ramp_up_in_minutes,
            weekdays=weekdays,
        )
        if DEBUG_ENABLED:
            _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


@led_app.command("remove-setting")
@app.command()
def remove_setting(
    device_address: str,
    sunrise: Annotated[datetime, typer.Argument(formats=["%H:%M"])],
    sunset: Annotated[datetime, typer.Argument(formats=["%H:%M"])],
    ramp_up_in_minutes: Annotated[int, typer.Option(min=1, max=150)] = 1,
    weekdays: Annotated[list[WeekdaySelect], typer.Option()] = [WeekdaySelect.everyday],
) -> None:
    """Remove setting from a light."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.remove_setting(
            sunrise=sunrise,
            sunset=sunset,
            ramp_up_in_minutes=ramp_up_in_minutes,
            weekdays=weekdays,
        )
        if DEBUG_ENABLED:
            _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


@led_app.command("delete-setting-exact")
def delete_setting_exact(
    device_address: str,
    sunrise: Annotated[datetime, typer.Argument(formats=["%H:%M"])],
    sunset: Annotated[datetime, typer.Argument(formats=["%H:%M"])],
    ramp_up_in_minutes: Annotated[int, typer.Option(min=1, max=150)] = 1,
    weekdays: Annotated[list[WeekdaySelect], typer.Option()] = [WeekdaySelect.everyday],
    finalize: Annotated[
        bool,
        typer.Option("--finalize/--no-finalize", help="Direkt nach dem Loeschframe Parameter 40 senden."),
    ] = False,
) -> None:
    """Send one exact LED schedule delete frame, optionally followed by parameter 40."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        delete_command = commands.create_delete_auto_setting_command(
            dev.get_next_msg_id(),
            sunrise.time(),
            sunset.time(),
            ramp_up_in_minutes,
            encode_selected_weekdays(weekdays),
            brightness_channels=dev._channel_count(),
        )
        commands_to_send = [bytes(delete_command)]
        if finalize:
            commands_to_send.append(bytes(commands.create_auto_parameter_command(dev.get_next_msg_id(), 40)))
        await dev._send_command(commands_to_send, 3, immediate_after_prelude=True)
        print(
            f"Gesendet: LED-Zeitplan deaktivieren {sunrise:%H:%M}-{sunset:%H:%M}, "
            f"Ramp={ramp_up_in_minutes} min, Abschluss={'40' if finalize else 'nein'}"
        )
        if DEBUG_ENABLED:
            _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


@led_app.command("reset-settings")
@app.command()
def reset_settings(device_address: str) -> None:
    """Reset settings from a light."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.reset_settings()
        if DEBUG_ENABLED:
            _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


@led_app.command("reset-settings-7")
def reset_settings_7(device_address: str) -> None:
    """Send the historically verified DYU1000 reset sequence 18 then 7."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        commands_to_send = [
            bytes(commands.create_switch_to_automatic_tab_command(dev.get_next_msg_id())),
            bytes(commands.create_auto_parameter_command(dev.get_next_msg_id(), 7)),
        ]
        await dev._send_command(commands_to_send, 3, connection_prelude="automatic_tab")
        print("Gesendet: historischer DYU1000-Zeitplanreset [18,255] -> [7,255,255]")
        if DEBUG_ENABLED:
            _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


@led_app.command("test-auto-parameter")
def test_auto_parameter(
    device_address: str,
    first_parameter: Annotated[int, typer.Argument(min=0, max=255)],
) -> None:
    """Send diagnostic mode 5 parameters [VALUE, 255, 255]."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.send_auto_parameter(first_parameter)
        if DEBUG_ENABLED:
            _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


@led_app.command("hard-reset")
@app.command("hard-reset")
def hard_reset(device_address: str) -> None:
    """Send LED hard-reset stages 5, 6, 7, and final stop/exit stage 4."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.hard_reset()
        if DEBUG_ENABLED:
            _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


@app.command()
def dose_ml(
    device_address: str,
    pump: Annotated[int, typer.Argument(min=1, max=4)],
    ml: Annotated[float, typer.Argument(min=0.2, max=999.9)],
) -> None:
    """Trigger an immediate manual dose on a dosing pump."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosDosingPump):
            raise typer.BadParameter(f"{dev.name} is not a dosing pump")
        await dev.dose_ml(pump - 1, ml)

    _run_device_func(device_address, command)


@doser_app.command("dose-ml")
def doser_dose_ml(
    device_address: str,
    pump: Annotated[int, typer.Option("--pump", min=1, max=4)],
    ml: Annotated[float, typer.Option("--ml", min=0.2, max=999.9)],
    debug: Annotated[bool, typer.Option("--debug", help="Rohe BLE-Antworten anzeigen")] = False,
) -> None:
    """Trigger an immediate manual dose on a dosing pump."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosDosingPump):
            raise typer.BadParameter(f"{dev.name} is not a dosing pump")
        if debug or DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.dose_ml(pump - 1, ml)
        store.record_manual(device_address, pump - 1, ml)
        store.adjust_container(device_address, pump - 1, -ml)
        store.record_action(
            "manual_dose",
            device_address=_state_device(device_address),
            channel=pump - 1,
            params={"ml": float(ml)},
            status="ok",
        )
        if debug or DEBUG_ENABLED:
            print(f"OK: manuell dosiert CH{pump} {ml:.1f} ml")
            _print_compare_log(dev)
            decoded = _print_doser_rx_return(dev)
            _print_doser_manual_summary(device_address, pump, ml, decoded)

    _run_device_func(device_address, command)


@doser_app.command("add-setting-dosing-pump")
def doser_add_setting(
    device_address: str,
    performance_time: Annotated[datetime, typer.Argument(formats=["%H:%M"])],
    ch_id: Annotated[int, typer.Option("--ch-id", min=1, max=4)] = 1,
    ch_ml: Annotated[float, typer.Option("--ch-ml", min=0.2, max=999.9)] = 0.2,
    weekdays: Annotated[list[WeekdaySelect], typer.Option("--weekdays", "-w")] = [WeekdaySelect.everyday],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
    valid_from_tomorrow: Annotated[bool, typer.Option("--valid-from-tomorrow/--valid-from-today")] = False,
) -> None:
    """Send a single-dose Doser schedule to the device."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosDosingPump):
            raise typer.BadParameter(f"{dev.name} is not a dosing pump")
        channel = _channel_index(ch_id)
        _clear_debug_frames(dev)
        await dev.add_schedule(
            channel,
            performance_time.time(),
            ch_ml,
            weekdays_mask=_weekday_mask(weekdays),
            active=active,
            next_day_flag=valid_from_tomorrow,
        )
        store.upsert_doser_schedule(
            device_address,
            channel,
            performance_time.time().strftime("%H:%M"),
            _weekday_mask(weekdays),
            ch_ml,
            schedule_kind="single_dose",
            timer_type=0,
            enabled=active,
            source="ble",
            not_before_date="tomorrow" if valid_from_tomorrow else "",
        )
        store.record_action(
            "set_schedule",
            device_address=_state_device(device_address),
            channel=channel,
            params={"kind": "single_dose", "time": performance_time.time().strftime("%H:%M"), "ml": float(ch_ml)},
            status="ok",
        )
        if DEBUG_ENABLED:
            _print_doser_command_debug(dev, title="Schedule debug")

    _run_device_func(device_address, command)


@doser_app.command("add-interval")
def doser_add_interval(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=1, max=4)] = 1,
    ch_ml: Annotated[float, typer.Option("--ch-ml", min=5.0, max=999.9)] = 5.0,
    interval: Annotated[int, typer.Option("--interval", min=0, max=59)] = 0,
    weekdays: Annotated[list[WeekdaySelect], typer.Option("--weekdays", "-w")] = [WeekdaySelect.everyday],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
    valid_from_tomorrow: Annotated[bool, typer.Option("--valid-from-tomorrow/--valid-from-today")] = False,
) -> None:
    """Send a Doser 24h interval schedule to the device."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosDosingPump):
            raise typer.BadParameter(f"{dev.name} is not a dosing pump")
        channel = _channel_index(ch_id)
        _clear_debug_frames(dev)
        await dev.add_interval_schedule(
            channel,
            interval,
            ch_ml,
            weekdays_mask=_weekday_mask(weekdays),
            active=active,
            next_day_flag=valid_from_tomorrow,
        )
        store.upsert_doser_schedule(
            device_address,
            channel,
            f"00:{interval:02d}",
            _weekday_mask(weekdays),
            ch_ml,
            schedule_kind="interval",
            timer_type=1,
            enabled=active,
            source="ble",
            not_before_date="tomorrow" if valid_from_tomorrow else "",
        )
        store.record_action(
            "set_schedule",
            device_address=_state_device(device_address),
            channel=channel,
            params={"kind": "interval", "interval": int(interval), "ml": float(ch_ml)},
            status="ok",
        )
        if DEBUG_ENABLED:
            _print_doser_command_debug(dev, title="Schedule debug")

    _run_device_func(device_address, command)


@doser_app.command("enable-schedule")
def doser_enable_schedule(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=1, max=4)] = 1,
) -> None:
    """Enable one Doser schedule."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosDosingPump):
            raise typer.BadParameter(f"{dev.name} is not a dosing pump")
        channel = _channel_index(ch_id)
        _clear_debug_frames(dev)
        await dev.set_schedule_active(channel, True)
        store.set_doser_schedule_enabled(device_address, channel, True)
        store.record_action(
            "enable_schedule", device_address=_state_device(device_address), channel=channel, status="ok"
        )
        if DEBUG_ENABLED:
            _print_doser_command_debug(dev, title="Enable schedule debug")

    _run_device_func(device_address, command)


@doser_app.command("disable-schedule")
def doser_disable_schedule(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=1, max=4)] = 1,
) -> None:
    """Disable one Doser schedule."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosDosingPump):
            raise typer.BadParameter(f"{dev.name} is not a dosing pump")
        channel = _channel_index(ch_id)
        _clear_debug_frames(dev)
        await dev.set_schedule_active(channel, False)
        store.set_doser_schedule_enabled(device_address, channel, False)
        store.record_action(
            "disable_schedule", device_address=_state_device(device_address), channel=channel, status="ok"
        )
        if DEBUG_ENABLED:
            _print_doser_command_debug(dev, title="Disable schedule debug")

    _run_device_func(device_address, command)


@doser_app.command("read-auto-totals")
def doser_read_auto_totals(
    device_address: str,
    mode: Annotated[int, typer.Option("--mode", min=0, max=255)] = 0x22,
    debug: Annotated[bool, typer.Option("--debug", help="Rohe BLE-Antworten anzeigen")] = False,
) -> None:
    """Read automatic daily totals from a Doser."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosDosingPump):
            raise typer.BadParameter(f"{dev.name} is not a dosing pump")
        if debug or DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        totals = await dev.read_auto_totals(mode)
        fallback_mode = None
        if totals is None and mode != 0x34:
            fallback_mode = 0x34
            totals = await dev.read_auto_totals(fallback_mode, clear_notifications=False)
        dialog_mode = None
        if totals is None:
            dialog_mode = mode
            totals = await dev.read_auto_totals_via_dialog(dialog_mode, clear_notifications=False)
        if debug or DEBUG_ENABLED:
            print(f"Mode: 0x{mode:02X}")
            if fallback_mode is not None:
                print(f"Fallback Mode: 0x{fallback_mode:02X}")
            if dialog_mode is not None:
                print(f"Dialog Mode: 0x{dialog_mode:02X}")
            _print_raw_notifications(dev, title="Auto totals debug")
            _print_raw_tx_frames(dev)
            _print_compare_log(dev)
            decoded = _print_doser_rx_return(dev)
            _print_doser_totals_summary(totals or decoded)
        if totals is not None:
            stored_mode = (
                dialog_mode if dialog_mode is not None else fallback_mode if fallback_mode is not None else mode
            )
            store.record_doser_auto_totals(device_address, stored_mode, totals)
            store.record_action(
                "read_auto_totals",
                device_address=_state_device(device_address),
                params={"mode": int(stored_mode), "totals": totals},
                status="ok",
            )
        print("No totals received" if totals is None else totals)

    _run_device_func(device_address, command)


@doser_app.command("read-notifications")
def doser_read_notifications(
    device_address: str,
    notification_wait: Annotated[float, typer.Option("--notification-wait", min=0.0, max=30.0)] = 5.0,
) -> None:
    """Request and print the current Doser notifications once."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosDosingPump):
            raise typer.BadParameter(f"{dev.name} is not a dosing pump")
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.read_doser_notifications(notification_wait=notification_wait)
        output = dev.render_protocol_debug(tx_commands={0x5A, 0xA5}, dedupe_rx=True)
        if output:
            print(output)

    _run_device_func(device_address, command)


@doser_app.command("show-containers")
def doser_show_containers(device_address: str) -> None:
    """Show local Doser container volumes."""
    print(f"Lokal: {_format_channels(store.get_containers(device_address))}")


@doser_app.command("set-container")
def doser_set_container(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=1, max=4)],
    ml: Annotated[float, typer.Option("--ml", min=0.0, max=9999.9)],
) -> None:
    """Set one local Doser container volume."""
    channel = _channel_index(ch_id)
    store.set_container(device_address, channel, ml)
    store.record_action(
        "set_container",
        device_address=_state_device(device_address),
        channel=channel,
        params={"ml": float(ml)},
        status="ok",
    )
    print(f"Lokal: CH{ch_id} Behaelter={ml:.1f} ml")


@doser_app.command("add-container")
def doser_add_container(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=1, max=4)],
    delta: Annotated[float, typer.Option("--delta")],
) -> None:
    """Adjust one local Doser container volume."""
    channel = _channel_index(ch_id)
    store.adjust_container(device_address, channel, delta)
    store.record_action(
        "add_container",
        device_address=_state_device(device_address),
        channel=channel,
        params={"delta": float(delta)},
        status="ok",
    )
    print(f"Lokal: {_format_channels(store.get_containers(device_address))}")


@doser_app.command("show-history")
def doser_show_history(
    device_address: str,
    limit: Annotated[int, typer.Option("--limit", min=1, max=500)] = 20,
) -> None:
    """Show local manual dosing history."""
    rows = store.get_history(device_address, limit)
    if not rows:
        print("Lokal: Keine manuelle Historie gespeichert.")
        return
    for row in rows:
        print(f"{row['ts']}: CH{int(row['ch']) + 1} {float(row['ml']):.1f} ml")


@doser_app.command("clear-history")
def doser_clear_history(device_address: str) -> None:
    """Clear local manual dosing history."""
    store.clear_history(device_address)
    store.record_action("clear_history", device_address=_state_device(device_address), status="ok")
    print("Lokal: Historie geloescht.")


@doser_app.command("show-schedules")
def doser_show_schedules(device_address: str) -> None:
    """Show local Doser schedules."""
    rows = store.list_doser_schedules(device_address)
    if not rows:
        print("Lokal: Keine Zeitplaene gespeichert.")
        return
    for row in rows:
        status = "an" if bool(row.get("enabled")) else "aus"
        print(
            f"Lokal: CH{int(row['channel']) + 1}: {_doser_kind_text(str(row['schedule_kind']))}, "
            f"Zeit={row['schedule_time']}, Menge={float(row['dose_ml']):.1f} ml, "
            f"Wochentage=0x{int(row['weekdays_mask']):02X}, Status={status}, "
            f"Typ-ID={int(row.get('schedule_type_id') or 1)}"
        )


@doser_app.command("clear-schedule")
def doser_clear_schedule(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=1, max=4)],
    kind: Annotated[str | None, typer.Option("--kind")] = None,
    local_only: Annotated[bool, typer.Option("--local-only/--send-device")] = True,
) -> None:
    """Clear local Doser schedule state."""
    channel = _channel_index(ch_id)
    deleted = store.delete_doser_schedule(device_address, channel, kind)
    store.record_action(
        "clear_schedule",
        device_address=_state_device(device_address),
        channel=channel,
        params={"kind": kind, "local_only": local_only},
        status="ok",
        output=f"deleted={deleted}",
    )
    print(f"Lokal: {deleted} Zeitplan-Zeile(n) fuer CH{ch_id} geloescht.")


@doser_app.command("show-auto-totals")
def doser_show_auto_totals(
    device_address: str,
    mode: Annotated[int | None, typer.Option("--mode-5b", min=0, max=255)] = None,
    day: Annotated[str | None, typer.Option("--day")] = None,
) -> None:
    """Show local Doser automatic daily totals."""
    rows = store.get_doser_auto_totals(device_address, mode, day)
    if not rows:
        print("Lokal: Keine Auto-Tageswerte gespeichert.")
        return
    current: dict[int, list[float]] = {}
    for row in rows:
        mode_key = int(row["mode"])
        current.setdefault(mode_key, [0.0, 0.0, 0.0, 0.0])
        channel = int(row["channel"])
        if 0 <= channel < 4:
            current[mode_key][channel] = float(row["ml"])
    for mode_key, values in sorted(current.items()):
        print(f"Lokal: 0x{mode_key:02X}: {_format_channels(values)}")


@doser_app.command("set-auto-total")
def doser_set_auto_total(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=1, max=4)],
    ml: Annotated[float, typer.Option("--ml", min=0.0, max=9999.9)],
    mode: Annotated[int, typer.Option("--mode-5b", min=0, max=255)] = 0x22,
    day: Annotated[str | None, typer.Option("--day")] = None,
) -> None:
    """Set one local Doser automatic daily total."""
    channel = _channel_index(ch_id)
    store.set_doser_auto_total(device_address, channel, mode, ml, day)
    store.record_action(
        "set_auto_total",
        device_address=_state_device(device_address),
        channel=channel,
        params={"mode": int(mode), "ml": float(ml), "day": day},
        status="ok",
    )
    print(f"Lokal: CH{ch_id} Auto-Tageswert={ml:.1f} ml, mode=0x{mode:02X}")


@doser_app.command("clear-auto-totals")
def doser_clear_auto_totals(
    device_address: str,
    mode: Annotated[int | None, typer.Option("--mode-5b", min=0, max=255)] = None,
    day: Annotated[str | None, typer.Option("--day")] = None,
) -> None:
    """Clear local Doser automatic daily totals."""
    deleted = store.clear_doser_auto_totals(device_address, mode, day)
    store.record_action(
        "clear_auto_totals",
        device_address=_state_device(device_address),
        params={"mode": mode, "day": day},
        status="ok",
        output=f"deleted={deleted}",
    )
    print(f"Lokal: {deleted} Auto-Tageswert-Zeile(n) geloescht.")


@doser_app.command("show-manual-totals")
def doser_show_manual_totals(device_address: str) -> None:
    """Show today's local manual Doser totals."""
    print(f"Lokal: {_format_channels(store.get_manual_daily_totals(device_address))}")


@doser_app.command("show-daily-totals")
def doser_show_daily_totals(
    device_address: str,
    mode: Annotated[int, typer.Option("--mode-5b", min=0, max=255)] = 0x22,
    day: Annotated[str | None, typer.Option("--day")] = None,
) -> None:
    """Show local automatic, manual and container totals."""
    auto_rows = store.get_doser_auto_totals(device_address, mode, day)
    auto_values = [0.0, 0.0, 0.0, 0.0]
    for row in auto_rows:
        channel = int(row["channel"])
        if 0 <= channel < 4:
            auto_values[channel] = float(row["ml"])
    manual_values = store.get_manual_daily_totals(device_address)
    containers = store.get_containers(device_address)
    for channel in range(4):
        print(
            f"Lokal: CH{channel + 1}: auto={auto_values[channel]:.1f} ml, "
            f"manuell={manual_values[channel]:.1f} ml, "
            f"gesamt={auto_values[channel] + manual_values[channel]:.1f} ml, "
            f"Behaelter={float(containers.get(str(channel), 0.0)):.1f} ml"
        )


@ruehrer_app.command("set-power")
def ruehrer_set_power(
    device_address: str,
    on: Annotated[bool, typer.Option("--on/--off")] = True,
) -> None:
    """Set MagStirrer run/power state."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosMagStirrer):
            raise typer.BadParameter(f"{dev.name} is not a MagStirrer")
        await dev.set_power(on)

    _run_device_func(device_address, command)


@ruehrer_app.command("show")
def ruehrer_show(
    device_address: Annotated[str | None, typer.Argument(help="Device alias or MAC address")] = None,
    device_option: Annotated[str | None, typer.Option("--device")] = None,
) -> None:
    """Show local MagStirrer device and channel names."""
    device_address = device_address or device_option
    device_key = _magstirrer_device_key(device_address)
    print(f"ruehrer_1: {device_key}")
    ruehrer_show_channel_names(device_address=device_address)


@ruehrer_app.command("set-channel-name")
def ruehrer_set_channel_name(
    name: Annotated[str, typer.Argument(help="Lokaler Kanalname")],
    ch_id: Annotated[int, typer.Option("--ch-id", min=0, max=3)] = 0,
    device_address: Annotated[str | None, typer.Option("--device")] = None,
) -> None:
    """Store a local MagStirrer channel name."""
    store.set_channel_name("ruehrer", _magstirrer_device_key(device_address), ch_id, name)
    print(f"OK: MagStirrer CH{ch_id + 1} local name set to {name.strip()}")


@ruehrer_app.command("show-channel-names")
def ruehrer_show_channel_names(device_address: Annotated[str | None, typer.Option("--device")] = None) -> None:
    """Show local MagStirrer channel names."""
    names = _magstirrer_channel_names(device_address)
    for ch_id in range(4):
        print(f"CH{ch_id + 1} (ch_id={ch_id}): {names.get(ch_id, '-')}")


@ruehrer_app.command("run-for")
def ruehrer_run_for(
    device_address: str,
    seconds: Annotated[int, typer.Option("--seconds", min=1, max=600)] = 10,
) -> None:
    """Run MagStirrer for a fixed number of seconds."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosMagStirrer):
            raise typer.BadParameter(f"{dev.name} is not a MagStirrer")
        await dev.run_for(seconds)

    _run_device_func(device_address, command)


@ruehrer_app.command("enable-auto-mode")
def ruehrer_enable_auto_mode(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=0, max=3)] = 0,
    on: Annotated[bool, typer.Option("--on/--off")] = True,
    catch_up: Annotated[int, typer.Option("--catch-up", min=0, max=255)] = 0,
) -> None:
    """Enable or disable MagStirrer auto mode for a channel."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosMagStirrer):
            raise typer.BadParameter(f"{dev.name} is not a MagStirrer")
        await dev.set_auto_mode(ch_id, on, catch_up)

    _run_device_func(device_address, command)


@ruehrer_app.command("set-runtime-speed")
def ruehrer_set_runtime_speed(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=0, max=3)] = 0,
    runtime_minutes: Annotated[int, typer.Option("--runtime-minutes", min=0, max=255)] = 90,
    speed: Annotated[int, typer.Option("--speed", min=0, max=100)] = 70,
    reserved: Annotated[int, typer.Option("--reserved", min=0, max=255)] = 0,
) -> None:
    """Set MagStirrer runtime and speed."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosMagStirrer):
            raise typer.BadParameter(f"{dev.name} is not a MagStirrer")
        await dev.set_runtime_speed(ch_id, runtime_minutes, speed)

    _run_device_func(device_address, command)
    store.set_setting(
        f"magstirrer_runtime.{_state_device(device_address)}.{int(ch_id)}",
        f'{{"magstirrer_key":"{_state_device(device_address)}","ch_id":{int(ch_id)},"runtime_min":{int(runtime_minutes)},"speed":{int(speed)},"reserved":{int(reserved)}}}',
    )


@ruehrer_app.command("set-timers")
def ruehrer_set_timers(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=0, max=3)] = 0,
    timer: Annotated[list[str], typer.Option("--timer", help="HH:MM=SECONDS")] = [],
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
    catch_up: Annotated[int, typer.Option("--catch-up", min=0, max=255)] = 0,
    weekdays: Annotated[list[WeekdaySelect], typer.Option("--weekdays", "-w", case_sensitive=False)] = [
        WeekdaySelect.everyday
    ],
) -> None:
    """Set MagStirrer timer entries."""
    parsed_timers = [_parse_timer_entry(item) for item in timer]

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosMagStirrer):
            raise typer.BadParameter(f"{dev.name} is not a MagStirrer")
        await dev.set_timers(ch_id, parsed_timers, active=active, catch_up=catch_up)

    _run_device_func(device_address, command)
    store.upsert_magstirrer_schedule(
        device_address,
        ch_id,
        "timer",
        _weekday_mask(weekdays),
        [
            {"hour": entry_time.hour, "minute": entry_time.minute, "value": raw_value}
            for entry_time, raw_value in parsed_timers
        ]
        if active
        else [],
        timer_type=3,
        catch_up=catch_up,
        enabled=active,
        source="ble-mode-0x15",
    )


@ruehrer_app.command("clear-timers")
def ruehrer_clear_timers(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=0, max=3)] = 0,
    deactivate: Annotated[bool, typer.Option("--deactivate/--keep-active")] = False,
    weekdays: Annotated[list[WeekdaySelect], typer.Option("--weekdays", "-w", case_sensitive=False)] = [
        WeekdaySelect.everyday
    ],
) -> None:
    """Clear MagStirrer timers on one channel."""

    async def command(dev: ChihirosDevice) -> None:
        if not isinstance(dev, ChihirosMagStirrer):
            raise typer.BadParameter(f"{dev.name} is not a MagStirrer")
        await dev.set_timers(ch_id, [], active=not deactivate, catch_up=0)

    _run_device_func(device_address, command)
    store.upsert_magstirrer_schedule(
        device_address,
        ch_id,
        "timer",
        _weekday_mask(weekdays),
        [],
        timer_type=3,
        catch_up=0,
        enabled=not deactivate,
        source="ble-clear-timers",
    )


@ruehrer_app.command("add-setting")
def ruehrer_add_setting(
    device_address: str,
    performance_time: Annotated[str, typer.Argument(help="HH:MM")],
    ch_id: Annotated[int, typer.Option("--ch-id", min=0, max=3)] = 0,
    active: Annotated[bool, typer.Option("--active/--inactive")] = True,
    timer_type: Annotated[int, typer.Option("--timer-type", min=0, max=255)] = 3,
    value: Annotated[int, typer.Option("--value", min=0, max=65535)] = 360,
    timer_entries: Annotated[list[str], typer.Option("--timer")] = [],
    window_entries: Annotated[list[str], typer.Option("--window")] = [],
    interval: Annotated[str | None, typer.Option("--interval")] = None,
    schedule_value: Annotated[int, typer.Option("--schedule-value", min=0, max=65535)] = 0,
    weekdays: Annotated[list[WeekdaySelect], typer.Option("--weekdays", "-w", case_sensitive=False)] = [
        WeekdaySelect.everyday
    ],
    catch_up: Annotated[int, typer.Option("--catch-up", min=0, max=255)] = 0,
) -> None:
    """Set a MagStirrer schedule and store it locally."""
    if window_entries and (timer_entries or interval):
        raise typer.BadParameter("--window kann nicht mit --timer oder --interval kombiniert werden")
    if timer_entries and interval:
        raise typer.BadParameter("--timer kann nicht mit --interval kombiniert werden")

    schedule_kind = "single"
    entries: list[dict[str, int]]
    if window_entries:
        schedule_kind = "window"
        entries = [_parse_magstirrer_window_block(item) for item in window_entries]
        # Native client has no window sender yet; store locally for now.
    elif interval:
        schedule_kind = "interval"
        hour, minute = _parse_hhmm(interval)
        timer_type = 1
        entries = [{"hour": hour, "minute": minute, "value": 0}]
    elif timer_entries:
        schedule_kind = "timer"
        entries = [_parse_magstirrer_timer_block(item) for item in timer_entries]
    else:
        hour, minute = _parse_hhmm(performance_time)
        entries = [{"hour": hour, "minute": minute, "value": int(value)}]

    if schedule_kind == "window":
        print(
            "Gespeichert: Zeitfenster ist lokal erfasst; BLE-Senden fuer Fenster ist im neuen Client noch nicht freigeschaltet."
        )
    else:

        async def command(dev: ChihirosDevice) -> None:
            if not isinstance(dev, ChihirosMagStirrer):
                raise typer.BadParameter(f"{dev.name} is not a MagStirrer")
            await dev.set_timers(ch_id, _magstirrer_entries_for_client(entries), active=active, catch_up=catch_up)

        _run_device_func(device_address, command)

    store.upsert_magstirrer_schedule(
        device_address,
        ch_id,
        schedule_kind,
        _weekday_mask(weekdays),
        entries if active else [],
        timer_type=timer_type,
        schedule_value=schedule_value,
        catch_up=catch_up,
        enabled=active,
        source="ble-mode-0x15" if schedule_kind != "window" else "local-window",
    )
    store.record_action(
        "magstirrer_set_schedule",
        device_address=_state_device(device_address),
        channel=ch_id,
        params={"kind": schedule_kind, "timer_type": timer_type, "entries": entries},
        status="ok",
    )
    print(
        f"OK: MagStirrer {schedule_kind} CH{ch_id + 1} ({_magstirrer_channel_name(ch_id, device_address)}) gespeichert"
    )


@ruehrer_app.command("enable-schedule")
def ruehrer_enable_schedule(
    device_address: str,
    performance_time: Annotated[str, typer.Argument(help="HH:MM")],
    ch_id: Annotated[int, typer.Option("--ch-id", min=0, max=3)] = 0,
    timer_type: Annotated[int, typer.Option("--timer-type", min=0, max=255)] = 3,
    value: Annotated[int, typer.Option("--value", min=0, max=65535)] = 360,
    weekdays: Annotated[list[WeekdaySelect], typer.Option("--weekdays", "-w", case_sensitive=False)] = [
        WeekdaySelect.everyday
    ],
) -> None:
    """Enable a MagStirrer schedule."""
    ruehrer_add_setting(
        device_address=device_address,
        performance_time=performance_time,
        ch_id=ch_id,
        active=True,
        timer_type=timer_type,
        value=value,
        weekdays=weekdays,
    )


@ruehrer_app.command("disable-schedule")
def ruehrer_disable_schedule(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=0, max=3)] = 0,
    weekdays: Annotated[list[WeekdaySelect], typer.Option("--weekdays", "-w", case_sensitive=False)] = [
        WeekdaySelect.everyday
    ],
) -> None:
    """Disable a MagStirrer schedule."""
    ruehrer_add_setting(
        device_address=device_address,
        performance_time="00:00",
        ch_id=ch_id,
        active=False,
        timer_type=3,
        value=0,
        weekdays=weekdays,
    )


@ruehrer_app.command("show-schedules")
def ruehrer_show_schedules(device_address: str) -> None:
    """Show locally stored MagStirrer schedules."""
    rows = store.list_magstirrer_schedules(device_address)
    if not rows:
        print("Keine lokalen Ruehrer-Zeitplaene gespeichert.")
        return
    for row in rows:
        print(_format_magstirrer_entry(row))


@ruehrer_app.command("clear-schedules")
def ruehrer_clear_schedules(
    device_address: str,
    ch_id: Annotated[int, typer.Option("--ch-id", min=0, max=3)] = 0,
    kind: Annotated[str | None, typer.Option("--kind")] = None,
    weekdays: Annotated[list[WeekdaySelect], typer.Option("--weekdays", "-w", case_sensitive=False)] = [
        WeekdaySelect.everyday
    ],
) -> None:
    """Delete locally stored MagStirrer schedules. Does not write BLE."""
    deleted = store.delete_magstirrer_schedule(device_address, ch_id, kind, _weekday_mask(weekdays))
    print(f"{deleted} lokale Ruehrer-Zeitplanzeile(n) geloescht.")


@led_app.command("enable-auto-mode")
@app.command()
def enable_auto_mode(device_address: str) -> None:
    """Enable auto mode in a light."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.enable_auto_mode()
        if DEBUG_ENABLED:
            _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


@led_app.command("watch-runtime")
def watch_runtime(
    device_address: str,
    interval_minutes: Annotated[float, typer.Option("--interval-minutes", min=0.01)] = 15.0,
    samples: Annotated[int, typer.Option("--samples", min=1, max=96)] = 3,
    notification_wait: Annotated[float, typer.Option("--notification-wait", min=0.0, max=30.0)] = 3.0,
) -> None:
    """Request and print LED runtime notifications at a fixed interval."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        for sample in range(1, samples + 1):
            _clear_debug_frames(dev)
            previous_raw = dev.last_runtime_notification.raw if dev.last_runtime_notification else None
            await dev.query_status_active(notification_wait=notification_wait)
            notification = dev.last_runtime_notification
            received = notification is not None and notification.raw != previous_raw
            timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
            if notification is None:
                print(f"[{timestamp}] Messung {sample}/{samples}: keine Runtime-Notification empfangen")
            else:
                print(
                    f"[{timestamp}] Messung {sample}/{samples}: Firmware={notification.firmware_version}, "
                    f"Laufzeit={notification.runtime_minutes} min, neue Notification={'ja' if received else 'nicht bestaetigt'}"
                )
                print(f"RX: {notification.raw.hex(' ').upper()}")
            if DEBUG_ENABLED:
                _print_led_protocol_debug(dev)
            if sample < samples:
                delay = interval_minutes * 60
                print(f"Naechste Abfrage in {interval_minutes:g} Minuten ...")
                await asyncio.sleep(delay)

    _run_device_func(device_address, command)


@led_app.command("read-notifications")
@app.command("read-notifications")
def read_notifications(
    device_address: str,
    notification_wait: Annotated[float, typer.Option("--notification-wait", min=0.0, max=30.0)] = 3.0,
) -> None:
    """Request and print the current LED runtime and schedule notifications once."""

    async def command(dev: ChihirosDevice) -> None:
        if DEBUG_ENABLED:
            dev.set_log_level(logging.DEBUG)
        _clear_debug_frames(dev)
        await dev.query_status_active(notification_wait=notification_wait)
        _print_led_protocol_debug(dev)

    _run_device_func(device_address, command)


if __name__ == "__main__":
    try:
        app()
    except asyncio.CancelledError:
        pass
