"""Chihiros LED control CLI entrypoint."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

import typer
from bleak import BleakScanner
from rich import print
from rich.table import Table
from typing_extensions import Annotated

from . import store
from .client import ChihirosDevice
from .factory import detect_model, get_device_from_address
from .weekday_encoding import WeekdaySelect, encode_selected_weekdays

app = typer.Typer()
config_app = typer.Typer(help="Lokale CTL-Konfiguration")
template_app = typer.Typer(help="LED-Templates")
led_app = typer.Typer(help="LED CTL-Befehle")
app.add_typer(config_app, name="config")
app.add_typer(template_app, name="template")
app.add_typer(led_app, name="led")

DeviceCommand = Callable[[ChihirosDevice], Awaitable[None]]
DEBUG_ENABLED = False


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












def _legacy_kind(kind: str) -> str:
    normalized = kind.strip().lower()
    if normalized != "led":
        raise typer.BadParameter("Dieser Export unterstützt ausschließlich LED-Geräte")
    return "led"










@config_app.command("path")
def config_path() -> None:
    """Show the local CTL SQLite path."""
    print(str(store.state_db_path()))


@config_app.command("set-device")
def config_set_device(
    kind: Annotated[str, typer.Argument(help="led")],
    index: Annotated[int, typer.Argument(min=1)],
    address: Annotated[str, typer.Argument(help="MAC-Adresse oder ID")],
    alias: Annotated[str | None, typer.Option("--alias")] = None,
    label: Annotated[str, typer.Option("--label")] = "",
    model: Annotated[str, typer.Option("--model")] = "",
) -> None:
    """Store one local device alias."""
    row = store.set_device(_legacy_kind(kind), index, address, alias=alias, label=label, model=model)
    print(f"OK: {row['alias']} -> {row['address']}")


@config_app.command("delete-device")
def config_delete_device(
    kind: Annotated[str, typer.Argument(help="led")],
    alias_or_index: Annotated[str, typer.Argument(help="Alias oder Nummer")],
) -> None:
    """Delete one local device alias."""
    deleted = store.delete_device(_legacy_kind(kind), alias_or_index)
    print("OK: deleted" if deleted else "Not found")


@config_app.command("show-device")
def config_show_device(
    kind: Annotated[str, typer.Argument(help="led")],
    alias_or_index: Annotated[str, typer.Argument(help="Alias oder Nummer")],
) -> None:
    """Show one local device alias."""
    led_kind = _legacy_kind(kind)
    alias = alias_or_index if not alias_or_index.isdigit() else store.default_alias(led_kind, int(alias_or_index))
    for row in store.list_devices(led_kind):
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
    for row in store.list_devices(_legacy_kind(kind) if kind else "led"):
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


@led_app.command("set-fan-speed")
@app.command()
def set_fan_speed(device_address: str, speed_percent: Annotated[int, typer.Argument(min=0, max=100)]) -> None:
    """Set fan speed percentage on fan-equipped lights."""
    _run_device_func(device_address, lambda dev: dev.set_fan_speed(speed_percent))


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
