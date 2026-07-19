"""Backend helpers for the bundled Wireshark dashboard plugin."""

# ruff: noqa: D103,E501,I001

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import shutil
import struct
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SOURCE_ROOT = Path(os.environ.get("CHIHIROS_SOURCE_ROOT", "/opt/chihiros-src"))
CONFIG_ROOT = Path(os.environ.get("HASS_CONFIG", "/config"))
WIRESHARK_ROOT = CONFIG_ROOT / ".chihiros" / "chihiros_wireshark_control"
DEFAULT_HCI_LOG_DIR = WIRESHARK_ROOT / "hci_log"
DEFAULT_CAPTURE_DIR = WIRESHARK_ROOT / "captures"
ADB_KEY_DIR = CONFIG_ROOT / ".android"
BTSNOOP_EPOCH_DELTA_US = 62_168_256_000 * 1_000_000
LANGUAGE_TIMEZONES = {"de": "Europe/Berlin", "en": "UTC"}


def _timezone_for_language(language: object = "de") -> ZoneInfo:
    """Return the Wireshark timezone selected by the configured UI language."""
    language_key = str(language or "de").strip().lower()
    return ZoneInfo(LANGUAGE_TIMEZONES.get(language_key, LANGUAGE_TIMEZONES["de"]))


def _btsnoop_timestamp_to_local(timestamp_us: int, language: object = "de") -> str:
    """Convert a btsnoop epoch timestamp to the configured wall-clock timezone."""
    unix_us = timestamp_us - BTSNOOP_EPOCH_DELTA_US
    return datetime.fromtimestamp(unix_us / 1_000_000, tz=_timezone_for_language(language)).strftime(
        "%d.%m.%Y %H:%M:%S.%f"
    )[:-3]


def _protocol_helpers() -> tuple[object, object, object]:
    src = SOURCE_ROOT / "src"
    protocol_path = src / "chihiros_led_control" / "protocol.py"
    if not protocol_path.exists():
        protocol_path = (
            SOURCE_ROOT / "custom_components" / "chihiros" / "vendor" / "chihiros_led_control" / "protocol.py"
        )
    if not protocol_path.exists():
        protocol_path = Path.cwd() / "src" / "chihiros_led_control" / "protocol.py"
    spec = importlib.util.spec_from_file_location("chihiros_wireshark_protocol", protocol_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Chihiros protocol parser not found")
    protocol = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = protocol
    spec.loader.exec_module(protocol)
    wrgb_channels = {"red": 0, "green": 1, "blue": 2, "white": 3}
    return (
        protocol.calculate_checksum,
        protocol.parse_doser_totals_frame,
        lambda frame: protocol.parse_notification(frame, wrgb_channels),
    )


def _byte_values_from_decimal_list(line: str) -> list[int] | None:
    match = re.search(r"\[([0-9,\s]+)\]", line)
    if not match:
        return None
    values = [int(item) for item in re.findall(r"\d+", match.group(1))]
    if len(values) >= 6 and all(0 <= item <= 255 for item in values) and values[0] in {0x5A, 0x5B, 0xA5}:
        return values
    return None


def _byte_values_from_hex(line: str) -> list[int] | None:
    values = [int(item, 16) for item in re.findall(r"(?<![0-9A-Fa-f])(?:0x)?([0-9A-Fa-f]{2})(?![0-9A-Fa-f])", line)]
    if len(values) >= 6 and any(item in {0x5A, 0x5B, 0xA5} for item in values):
        start = next(index for index, item in enumerate(values) if item in {0x5A, 0x5B, 0xA5})
        return values[start:]
    return None


def _extract_wireshark_frames(text: str) -> list[dict[str, object]]:
    pull7_rows = _pull7_extract_rows_from_jsonl(text)
    if pull7_rows:
        return [
            {"line": index + 1, "direction": str(row.get("dir") or "?").upper(), "raw": b"", "json": row}
            for index, row in enumerate(pull7_rows[:300])
        ]
    frames = []
    for number, line in enumerate(text.splitlines(), start=1):
        json_frame = _json_line_frame(line, number)
        if json_frame is not None:
            frames.append(json_frame)
            if len(frames) >= 300:
                break
            continue
        direction = "RX" if re.search(r"\brx\b|receive|notify", line, re.IGNORECASE) else ""
        if re.search(r"\btx\b|write|send|command", line, re.IGNORECASE):
            direction = "TX"
        values = _byte_values_from_decimal_list(line) or _byte_values_from_hex(line)
        if not values:
            continue
        frames.append({"line": number, "direction": direction or "?", "raw": bytes(values[:96])})
        if len(frames) >= 300:
            break
    return frames


def _pull7_now_str() -> str:
    return datetime.now(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y %H:%M:%S")


def _capture_filename_timestamp(now: datetime | None = None, language: object = "de") -> str:
    """Return the capture filename timestamp in the same timezone as packet rows."""
    selected_timezone = _timezone_for_language(language)
    current = now or datetime.now(selected_timezone)
    if current.tzinfo is not None:
        current = current.astimezone(selected_timezone)
    return current.strftime("%Y-%m-%d-%H-%M-%S")


def _pull7_xor_checksum(buf: bytes) -> int:
    if len(buf) < 2:
        return 0
    checksum = buf[1]
    for value in buf[2:]:
        checksum ^= value
    return checksum & 0xFF


def _pull7_att_name(opcode: int) -> str:
    names = {
        0x02: "exchange-mtu-request",
        0x03: "exchange-mtu-response",
        0x04: "find-information-request",
        0x05: "find-information-response",
        0x08: "read-by-type-request",
        0x09: "read-by-type-response",
        0x10: "read-by-group-type-request",
        0x11: "read-by-group-type-response",
        0x12: "write-request",
        0x13: "write-response",
        0x1B: "notify",
        0x1D: "indicate",
        0x52: "write-command",
    }
    return names.get(opcode, f"att-0x{opcode:02X}")


def _pull7_direction_from_record(obj: dict[str, object], direction: str) -> str:
    if direction != "unknown":
        return direction
    raw_dir = obj.get("dir")
    if raw_dir == "out":
        return "tx"
    if raw_dir == "in":
        return "rx"
    flags = obj.get("flags")
    if isinstance(flags, int):
        return "tx" if flags & 0x01 else "rx"
    return "unknown"


def _pull7_find_frames(payload: bytes) -> list[tuple[bytes, int]]:
    out: list[tuple[bytes, int]] = []
    length = len(payload)
    for index in range(length):
        first = payload[index]
        if first not in (0x5A, 0xA5, 0x5B):
            continue
        if first == 0x5B and index + 6 <= length:
            expected = payload[index + 2] + 2
            if index + expected <= length:
                candidate = payload[index : index + expected]
                if len(candidate) >= 50 and candidate[1] == 0x08 and candidate[5] == 0xFE:
                    out.append((bytes(candidate), index))
                    continue
        if first == 0xA5 and index + 3 <= length:
            expected = payload[index + 2] + 2
            if expected < 8 or index + expected > length:
                continue
            candidate = payload[index : index + expected]
            if candidate[1] == 0x01 and _pull7_xor_checksum(candidate[:-1]) == candidate[-1]:
                out.append((bytes(candidate), index))
            continue
        for frame_len in range(8, min(128, length - index) + 1):
            candidate = payload[index : index + frame_len]
            if len(candidate) < 8 or candidate[1] != 0x01:
                continue
            checksum_ok = False
            if candidate[0] == 0x5B:
                if candidate[-1] in (0x28, 0x29):
                    if _pull7_xor_checksum(candidate[:-2]) == candidate[-2]:
                        checksum_ok = True
                        candidate = candidate[:-1]
                elif _pull7_xor_checksum(candidate[:-1]) == candidate[-1]:
                    checksum_ok = True
            elif candidate[0] in (0x5A, 0xA5) and _pull7_xor_checksum(candidate[:-1]) == candidate[-1]:
                checksum_ok = True
            if checksum_ok:
                out.append((bytes(candidate), index))
                break
    return out


def _pull7_att_meta(payload: bytes, frame_start: int) -> tuple[str, str]:
    opcode_names = {
        0x12: ("tx", "write-request"),
        0x52: ("tx", "write-command"),
        0x1B: ("rx", "notify"),
        0x1D: ("rx", "indicate"),
    }
    if len(payload) >= 10 and payload[0] == 0x02:
        l2cap_len = int.from_bytes(payload[5:7], "little")
        cid = int.from_bytes(payload[7:9], "little")
        att_start = 9
        att_end = min(len(payload), att_start + l2cap_len)
        if cid == 0x0004 and att_start < len(payload):
            opcode = payload[att_start]
            if att_start <= frame_start < att_end:
                return opcode_names.get(opcode, ("unknown", f"att-0x{opcode:02X}"))
    if frame_start > 0:
        opcode = payload[frame_start - 1]
        if opcode in opcode_names:
            return opcode_names[opcode]
    return ("unknown", "unknown")


def _pull7_frame_to_row(frame: bytes, obj: dict[str, object], direction: str, att_op: str) -> dict[str, object] | None:
    if len(frame) < 8:
        return None
    return {
        "time": obj.get("time") or obj.get("ts") or _pull7_now_str(),
        "dir": direction,
        "att": att_op,
        "host_name": obj.get("host_name"),
        "src_mac": obj.get("src_mac"),
        "src_name": obj.get("src_name"),
        "dest_mac": obj.get("dest_mac"),
        "dest_name": obj.get("dest_name"),
        "names": obj.get("names") if isinstance(obj.get("names"), dict) else {},
        "cmd": int(frame[0]),
        "mode": int(frame[5]),
        "parm": [int(value) for value in frame[6:-1]],
        "hex": frame.hex(" ").upper(),
    }


def _pull7_att_packets(payload: bytes, obj: dict[str, object]) -> list[dict[str, object]]:
    if len(payload) < 10 or payload[0] != 0x02:
        return []
    l2cap_len = int.from_bytes(payload[5:7], "little")
    cid = int.from_bytes(payload[7:9], "little")
    if cid != 0x0004:
        return []
    att_start = 9
    att_end = min(len(payload), att_start + l2cap_len)
    if att_start >= att_end:
        return []
    att = payload[att_start:att_end]
    opcode = att[0]
    if opcode in (0x02, 0x04, 0x08, 0x10, 0x12, 0x52):
        direction = "tx"
    elif opcode in (0x01, 0x03, 0x05, 0x09, 0x11, 0x13, 0x1B, 0x1D):
        direction = "rx"
    else:
        direction = _pull7_direction_from_record(obj, "unknown")
    handle = None
    if opcode in (0x12, 0x52, 0x1B, 0x1D) and len(att) >= 3:
        handle = int.from_bytes(att[1:3], "little")
        value = att[3:]
    elif opcode in (0x04, 0x08, 0x10) and len(att) >= 5:
        handle = int.from_bytes(att[1:3], "little")
        value = att[1:]
    else:
        value = att[1:]
    row: dict[str, object] = {
        "time": obj.get("time") or obj.get("ts") or _pull7_now_str(),
        "dir": direction,
        "att": _pull7_att_name(opcode),
        "att_opcode": f"0x{opcode:02X}",
        "handle": f"0x{handle:04X}" if handle is not None else None,
        "host_name": obj.get("host_name"),
        "src_mac": obj.get("src_mac"),
        "src_name": obj.get("src_name"),
        "dest_mac": obj.get("dest_mac"),
        "dest_name": obj.get("dest_name"),
        "names": obj.get("names") if isinstance(obj.get("names"), dict) else {},
        "value_hex": value.hex(" ").upper(),
        "att_hex": att.hex(" ").upper(),
    }
    for frame, _start in _pull7_find_frames(value):
        frame_row = _pull7_frame_to_row(frame, obj, direction, _pull7_att_name(opcode))
        if frame_row:
            row.update(
                {"cmd": frame_row["cmd"], "mode": frame_row["mode"], "parm": frame_row["parm"], "hex": frame_row["hex"]}
            )
            break
    return [row]


def _pull7_extract_rows_from_jsonl(text: str, *, all_att: bool = True) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    saw_hci_jsonl = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        hex_text = obj.get("bytes_hex") or obj.get("data_hex")
        if not isinstance(hex_text, str) or len(hex_text) < 4:
            continue
        saw_hci_jsonl = True
        try:
            raw = bytes.fromhex(hex_text.replace(" ", ""))
        except ValueError:
            continue
        if all_att:
            rows.extend(_pull7_att_packets(raw, obj))
            continue
        for frame, start in _pull7_find_frames(raw):
            direction, att_op = _pull7_att_meta(raw, start)
            direction = _pull7_direction_from_record(obj, direction)
            frame_row = _pull7_frame_to_row(frame, obj, direction, att_op)
            if frame_row:
                rows.append(frame_row)
    return rows if saw_hci_jsonl else []


def _json_line_frame(line: str, number: int) -> dict[str, object] | None:
    text = line.strip().rstrip(",")
    if not text.startswith("{") and "{" in text:
        text = text[text.find("{") :].strip().rstrip(",")
    if not text.startswith("{"):
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    raw_hex = str(obj.get("hex") or obj.get("frame_hex") or obj.get("bytes_hex") or obj.get("data_hex") or "").strip()
    raw = b""
    if raw_hex:
        try:
            raw = bytes.fromhex(re.sub(r"[^0-9A-Fa-f]", "", raw_hex))
        except ValueError:
            raw = b""
    if not raw and isinstance(obj.get("parm"), list) and obj.get("cmd") is not None and obj.get("mode") is not None:
        params = [int(item) & 0xFF for item in obj.get("parm", []) if isinstance(item, int)]
        raw = bytes([int(obj["cmd"]) & 0xFF, 0, len(params) + 7, 0, 0, int(obj["mode"]) & 0xFF, *params, 0])
    if not raw and not {"cmd", "mode", "parm", "att", "dir"}.intersection(obj):
        return None
    return {
        "line": number,
        "direction": str(obj.get("dir") or obj.get("direction") or "?").upper(),
        "raw": raw,
        "json": obj,
    }


def _compact_frame_from_hex_blob(hex_blob: str) -> dict[str, object] | None:
    text = str(hex_blob or "").strip()
    if not text:
        return None
    try:
        payload = bytes.fromhex("".join(text.split()))
    except ValueError:
        return None

    def checksum_ok(frame: bytes) -> bool:
        if len(frame) < 8:
            return False
        value = frame[1]
        for item in frame[2:-1]:
            value ^= item
        return (value & 0xFF) == frame[-1]

    for start, first in enumerate(payload):
        if first not in (0x5A, 0xA5, 0x5B):
            continue
        if start + 8 > len(payload):
            continue
        expected = payload[start + 2] + 2
        if expected < 8 or start + expected > len(payload):
            continue
        frame = payload[start : start + expected]
        if frame[1] != 0x01:
            continue
        if first in (0x5A, 0xA5) and not checksum_ok(frame):
            continue
        if first == 0x5B and not (checksum_ok(frame) or (len(frame) >= 2 and checksum_ok(frame[:-1]))):
            continue
        return {
            "cmd": int(frame[0]),
            "mode": int(frame[5]) if len(frame) >= 6 else None,
            "parm": [int(item) for item in frame[6:-1]],
            "hex": frame.hex(" ").upper(),
        }
    return None


def _row_with_compact_frame(row: dict[str, object]) -> dict[str, object]:
    if row.get("cmd") is not None and row.get("mode") is not None:
        return row
    for key in ("hex", "value_hex", "att_hex"):
        parsed = _compact_frame_from_hex_blob(str(row.get(key) or ""))
        if parsed:
            merged = dict(row)
            merged.update(parsed)
            return merged
    return row


def _name_with_mac(mac: object, name: object) -> str:
    mac_text = str(mac or "").strip()
    name_text = str(name or "").strip()
    if mac_text and name_text:
        return f"{mac_text} ({name_text})"
    return mac_text or name_text


def _int_value(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text, 16) if text.lower().startswith("0x") else int(text)
    except ValueError:
        return None


def _chihiros_protocol_name(command: object) -> str:
    cmd = _int_value(command)
    if cmd == 0x5A:
        return "Chihiros 5A"
    if cmd == 0xA5:
        return "Chihiros A5"
    if cmd == 0x5B:
        return "Chihiros 5B"
    return ""


def _row_protocol(obj: dict[str, object]) -> str:
    protocol = _chihiros_protocol_name(obj.get("cmd"))
    if protocol:
        return protocol
    protocol = _chihiros_protocol_name(obj.get("command"))
    if protocol:
        return protocol
    att = str(obj.get("att") or "").strip().lower()
    if att == "notify":
        return "Notify"
    if att == "indicate":
        return "Indicate"
    if obj.get("att") or obj.get("att_opcode"):
        return "ATT"
    pkt_type = str(obj.get("pkt_type") or "")
    return {
        "0x01": "HCI_CMD",
        "0x02": "HCI_ACL",
        "0x03": "HCI_SCO",
        "0x04": "HCI_EVT",
        "0x05": "HCI_ISO",
    }.get(pkt_type, pkt_type)


def _row_endpoints(obj: dict[str, object]) -> tuple[str, str]:
    direction = str(obj.get("dir") or obj.get("direction") or "").lower()
    source = _name_with_mac(obj.get("src_mac"), obj.get("src_name"))
    destination = _name_with_mac(obj.get("dest_mac"), obj.get("dest_name"))
    host = str(obj.get("host_name") or "").strip() or "App/Handy"
    device = destination or source or "Geraet"
    if direction == "tx":
        return source or host, destination or device
    if direction == "rx":
        return source or device, host
    return source, destination


def _json_display_fields(obj: dict[str, object], raw: bytes) -> dict[str, object]:
    obj = _row_with_compact_frame(obj)
    params = obj.get("parm")
    if not isinstance(params, list):
        params = list(raw[6:-1]) if len(raw) > 7 else []
    if obj.get("cmd") is not None and isinstance(params, list):
        param_text = "[" + ", ".join(str(int(item)) for item in params if isinstance(item, int)) + "]"
    else:
        param_text = str(obj.get("value_hex") or "").strip()
    if not param_text and isinstance(params, list):
        param_text = " ".join(f"{int(item) & 0xFF:02X}" for item in params if isinstance(item, int))
    encoded = str(obj.get("hex") or obj.get("frame_hex") or obj.get("att_hex") or "").strip()
    if not encoded and raw:
        encoded = raw.hex(" ").upper()
    source, destination = _row_endpoints(obj)
    return {
        "timestamp": str(obj.get("time") or obj.get("ts") or ""),
        "source": source,
        "destination": destination,
        "protocol": _row_protocol(obj),
        "command": str(obj.get("cmd") if obj.get("cmd") is not None else ""),
        "mode": str(obj.get("mode") if obj.get("mode") is not None else ""),
        "params": param_text,
        "parsed_summary": param_text,
        "parsed_type": str(obj.get("att") or obj.get("att_opcode") or ""),
        "hex": encoded,
    }


def _mode_name(mode: int) -> str:
    return {
        0x04: "auth/status",
        0x07: "brightness",
        0x0A: "runtime/status",
        0x1B: "manual dose",
        0x1E: "doser totals",
        0x22: "manual/daily totals",
        0x34: "fallback totals",
        0xFE: "schedule snapshot",
    }.get(mode, f"0x{mode:02X}")


def _decode_wireshark_frame(frame: dict[str, object]) -> dict[str, object]:
    raw = bytes(frame["raw"])
    source_json = frame.get("json")
    calculate_checksum, parse_doser_totals_frame, parse_notification = _protocol_helpers()
    mode = raw[5] if len(raw) > 5 else None
    params = list(raw[6:-1]) if len(raw) > 7 else []
    checksum = None
    if len(raw) >= 7:
        try:
            checksum = int(calculate_checksum(raw[:-1])) == raw[-1]
        except ValueError:
            checksum = None
    parsed_type = ""
    parsed_summary = ""
    totals = parse_doser_totals_frame(raw)
    if totals is not None:
        parsed_type = "doser_totals"
        parsed_summary = ", ".join(f"CH{idx + 1}={value:.1f} mL" for idx, value in enumerate(totals))
    notification = parse_notification(raw)
    if notification is not None:
        parsed_type = type(notification).__name__
        if hasattr(notification, "runtime_minutes"):
            parsed_summary = f"runtime={notification.runtime_minutes} min"
        elif hasattr(notification, "points"):
            parsed_summary = f"{len(notification.points)} schedule points"
    decoded = {
        "line": frame["line"],
        "direction": frame["direction"],
        "hex": raw.hex(" ").upper(),
        "command": f"0x{raw[0]:02X}" if raw else "",
        "protocol": _chihiros_protocol_name(raw[0] if raw else None),
        "version": raw[1] if len(raw) > 1 else None,
        "length": raw[2] if len(raw) > 2 else None,
        "message_id": f"{raw[3]:02X} {raw[4]:02X}" if len(raw) > 4 else "",
        "mode": f"0x{mode:02X}" if mode is not None else "",
        "mode_name": _mode_name(mode) if mode is not None else "",
        "params": " ".join(f"{item:02X}" for item in params),
        "checksum": "ok" if checksum is True else ("fail" if checksum is False else "unknown"),
        "parsed_type": parsed_type,
        "parsed_summary": parsed_summary,
    }
    if isinstance(source_json, dict):
        decoded.update(_json_display_fields(source_json, raw))
        decoded["raw_json"] = source_json
    protocol = _chihiros_protocol_name(decoded.get("command"))
    if protocol:
        decoded["protocol"] = protocol
    return decoded


def analyze_wireshark_text(text: str) -> dict[str, object]:
    frames = _extract_wireshark_frames(text)
    decoded = [_decode_wireshark_frame(frame) for frame in frames]
    return {
        "status": "ok",
        "frames": decoded,
        "count": len(decoded),
    }


def _safe_config_path(value: object, fallback: Path) -> Path:
    text = str(value or "").strip()
    path = Path(text) if text else fallback
    if not path.is_absolute():
        path = CONFIG_ROOT / path
    resolved = path.resolve()
    config_root = CONFIG_ROOT.resolve()
    if not str(resolved).startswith(str(config_root)):
        raise ValueError("Pfad muss unter /config liegen")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _pull7_type_to_hci_packet(snooz_type: int, payload: bytes) -> bytes:
    if snooz_type == 0x20:
        return b"\x01" + payload
    if snooz_type in (0x11, 0x21):
        return b"\x02" + payload
    if snooz_type in (0x12, 0x22):
        return b"\x03" + payload
    if snooz_type == 0x10:
        return b"\x04" + payload
    if snooz_type in (0x17, 0x2D):
        return b"\x05" + payload
    return payload


def _pull7_records_from_btsnoop(
    path: Path, *, strip_hci: bool = False, language: object = "de"
) -> list[dict[str, object]]:
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError("Ungueltige btsnoop-Datei.")
    records = data[16:]
    pos = 0
    parsed: list[dict[str, object]] = []
    mac_cache: dict[str, str | None] = {"src": None, "dst": None}
    name_cache: dict[str, str] = {}
    host_name: str | None = None

    def mac_from_le(buf: bytes) -> str:
        return ":".join(f"{value:02x}" for value in reversed(buf))

    def valid_mac(mac: str) -> bool:
        return len(mac.split(":")) == 6 and mac not in {"00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"}

    def parse_adv_name(payload: bytes) -> str | None:
        offset = 0
        while offset < len(payload):
            field_len = payload[offset]
            if field_len == 0:
                break
            end = offset + 1 + field_len
            if end > len(payload):
                break
            ad_type = payload[offset + 1]
            value = payload[offset + 2 : end]
            if ad_type in (0x08, 0x09) and value:
                text = value.decode("utf-8", errors="ignore").strip("\x00 ")
                if 3 <= len(text) <= 80 and all(32 <= ord(ch) < 127 for ch in text):
                    return text
            offset = end
        return None

    def parse_plain_name(payload: bytes) -> str | None:
        text = payload.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
        if 3 <= len(text) <= 80 and any(ch.isalpha() for ch in text) and all(32 <= ord(ch) < 127 for ch in text):
            return text
        return None

    def add_packet(packet: bytes, orig_len: int, flags: int, ts_human: str) -> None:
        nonlocal host_name
        pkt_type = packet[0] if packet else None
        if strip_hci and pkt_type in (0x01, 0x04):
            return
        src_mac = mac_cache.get("src")
        dest_mac = mac_cache.get("dst")
        packet_macs: set[str] = set()

        def record_mac(buf: bytes, cache_key: str | None = None) -> str | None:
            if len(buf) != 6:
                return None
            mac = mac_from_le(buf)
            if not valid_mac(mac):
                return None
            packet_macs.add(mac)
            if cache_key:
                mac_cache[cache_key] = mac
            return mac

        if pkt_type == 0x04 and len(packet) >= 3:
            event_code = packet[1]
            if event_code == 0x03 and len(packet) >= 14:
                dest_mac = record_mac(packet[7:13], "dst")
            elif event_code == 0x3E and len(packet) > 12:
                subevent = packet[3]
                if subevent in (0x01, 0x0A) and len(packet) >= 15:
                    dest_mac = record_mac(packet[9:15], "dst")
                elif subevent == 0x02 and len(packet) >= 13:
                    offset = 5
                    reports = packet[4]
                    for _ in range(reports):
                        if offset + 9 > len(packet):
                            break
                        bd_addr = record_mac(packet[offset + 2 : offset + 8], "dst")
                        dest_mac = bd_addr or dest_mac
                        data_len_index = offset + 8
                        data_len = packet[data_len_index]
                        data_start = data_len_index + 1
                        data_end = data_start + data_len
                        if data_end > len(packet):
                            break
                        adv_name = parse_adv_name(packet[data_start:data_end])
                        if bd_addr and adv_name:
                            name_cache[bd_addr] = adv_name
                        offset = data_end + 1
                elif subevent == 0x0D and len(packet) >= 29:
                    offset = 5
                    reports = packet[4]
                    for _ in range(reports):
                        if offset + 24 > len(packet):
                            break
                        bd_addr = record_mac(packet[offset + 3 : offset + 9], "dst")
                        dest_mac = bd_addr or dest_mac
                        data_len_index = offset + 23
                        data_len = packet[data_len_index]
                        data_start = data_len_index + 1
                        data_end = data_start + data_len
                        if data_end > len(packet):
                            break
                        adv_name = parse_adv_name(packet[data_start:data_end])
                        if bd_addr and adv_name:
                            name_cache[bd_addr] = adv_name
                        offset = data_end
        elif pkt_type == 0x01 and len(packet) >= 10:
            opcode = struct.unpack("<H", packet[1:3])[0]
            if opcode in (0x0405, 0x200D) and len(packet) >= 16:
                dest_mac = record_mac(packet[10:16], "dst") or dest_mac
            candidate = None
            if opcode == 0x0C13 and len(packet) > 4:
                candidate = parse_plain_name(packet[4:])
            elif opcode == 0x0C52 and len(packet) > 4:
                candidate = parse_adv_name(packet[4:])
            if candidate:
                host_name = candidate

        src_name = name_cache.get(src_mac) if src_mac else None
        dest_name = name_cache.get(dest_mac) if dest_mac else None
        parsed.append(
            {
                "time": ts_human,
                "pkt_type": f"0x{pkt_type:02X}" if pkt_type is not None else None,
                "orig_len": orig_len,
                "flags": flags,
                "host_name": host_name,
                "src_mac": src_mac,
                "src_name": src_name,
                "dest_mac": dest_mac,
                "dest_name": dest_name,
                "macs": sorted(packet_macs),
                "names": {mac: name_cache[mac] for mac in sorted(packet_macs) if mac in name_cache},
                "data_hex": " ".join(f"{value:02x}" for value in packet),
                "bytes_hex": packet.hex(),
            }
        )

    standard_btsnoop = False
    if len(records) >= 24:
        probe_orig, probe_inc, _probe_flags, _probe_drops, _probe_ts = struct.unpack(">IIIIq", records[:24])
        standard_btsnoop = 0 < probe_inc <= probe_orig <= len(records)
    if standard_btsnoop:
        while pos < len(records):
            if pos + 24 > len(records):
                break
            orig_len, inc_len, flags, _drops, ts = struct.unpack(">IIIIq", records[pos : pos + 24])
            start = pos + 24
            end = start + inc_len
            if end > len(records):
                break
            packet = records[start:end]
            try:
                ts_human = _btsnoop_timestamp_to_local(ts, language)
            except Exception:
                ts_human = f"invalid({ts})"
            add_packet(packet, orig_len, flags, ts_human)
            pos = end
    else:
        elapsed_ms = 0
        while pos + 9 <= len(records):
            length, packet_length, delta_time_ms, snooz_type = struct.unpack_from("<HHIb", records, pos)
            if length <= 0 or pos + 9 + length - 1 > len(records):
                break
            pos += 9
            payload = records[pos : pos + length - 1]
            pos += length - 1
            elapsed_ms += delta_time_ms
            packet = _pull7_type_to_hci_packet(snooz_type, payload)
            flags = 0 if snooz_type in (0x20, 0x21, 0x22, 0x2D) else 1
            add_packet(packet, packet_length, flags, f"+{elapsed_ms}ms")
    return parsed


def _write_pull7_frames(jsonl_path: Path, *, all_att: bool = True) -> Path:
    rows = _pull7_extract_rows_from_jsonl(jsonl_path.read_text(encoding="utf-8", errors="replace"), all_att=all_att)
    frames_path = jsonl_path.with_suffix(".frames.jsonl")
    frames_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8"
    )
    return frames_path


def _adb_base_target(data: dict[str, object]) -> list[str]:
    ip = str(data.get("adb_ip") or "").strip()
    port = str(data.get("adb_port") or "5555").strip() or "5555"
    if ip:
        return ["-s", f"{ip}:{port}"]
    return []


def _adb_env() -> dict[str, str]:
    ADB_KEY_DIR.mkdir(parents=True, exist_ok=True)
    return {**os.environ, "HOME": str(CONFIG_ROOT), "ADB_VENDOR_KEYS": str(ADB_KEY_DIR)}


def _run_process(args: list[str], *, timeout: int = 45, env: dict[str, str] | None = None) -> dict[str, object]:
    if shutil.which(args[0]) is None:
        return {"returncode": 127, "output": f"{args[0]} ist im Add-on nicht installiert."}
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False, env=env)
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "output": "Zeitueberschreitung"}
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    return {"returncode": result.returncode, "output": output or "(no output)"}


def _run_adb(data: dict[str, object], args: list[str], *, timeout: int = 45, target: bool = True) -> dict[str, object]:
    command = ["adb"]
    if target:
        command += _adb_base_target(data)
    command += args
    return _run_process(command, timeout=timeout, env=_adb_env())


def _adb_su(data: dict[str, object], command: str, *, timeout: int = 45) -> dict[str, object]:
    return _run_adb(data, ["shell", f"su -c {shlex.quote(command)}"], timeout=timeout)


def _adb_su_ok(result: dict[str, object]) -> bool:
    output = str(result.get("output") or "").lower()
    return int(result.get("returncode") or 0) == 0 and "uid=0" in output


def _append_adb_output(outputs: list[str], label: str, result: dict[str, object]) -> None:
    outputs.append(f"$ {label}\n{result.get('output') or ''}")


def _restart_adb_server() -> list[str]:
    outputs = []
    for args in (["adb", "kill-server"], ["adb", "start-server"]):
        result = _run_process(args, timeout=20, env=_adb_env())
        outputs.append(f"$ {' '.join(args)}\n{result['output']}")
    return outputs


def _connect_adb(data: dict[str, object]) -> dict[str, object]:
    ip = str(data.get("adb_ip") or "").strip()
    port = str(data.get("adb_port") or "5555").strip() or "5555"
    if not ip:
        raise ValueError("ADB IP fehlt")
    target = f"{ip}:{port}"
    outputs = _restart_adb_server()
    for args in (["adb", "disconnect", target], ["adb", "connect", target], ["adb", "devices", "-l"]):
        result = _run_process(args, timeout=30, env=_adb_env())
        outputs.append(f"$ {' '.join(args)}\n{result['output']}")
    text = "\n\n".join(outputs)
    failed = bool(
        re.search(r"\bunauthorized\b|\boffline\b|failed to authenticate|cannot connect|failed to connect", text, re.I)
    )
    return {"returncode": 1 if failed else 0, "output": text}


def _adb_usb_serials() -> list[str]:
    result = _run_process(["adb", "devices", "-l"], timeout=20, env=_adb_env())
    serials: list[str] = []
    for line in str(result.get("output") or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device" and ":" not in parts[0]:
            serials.append(parts[0])
    return serials


def _enable_adb_over_usb(data: dict[str, object]) -> dict[str, object]:
    port = str(data.get("adb_port") or "5555").strip() or "5555"
    ip = str(data.get("adb_ip") or "").strip()
    target = f"{ip}:{port}" if ip else ""
    outputs: list[str] = []
    serials = _adb_usb_serials()
    if not serials:
        devices = _run_process(["adb", "devices", "-l"], timeout=20, env=_adb_env())
        _append_adb_output(outputs, "adb devices -l", devices)
        return {
            "returncode": 1,
            "output": "\n\n".join(
                outputs
                + [
                    "Kein USB-ADB-Geraet gefunden. Handy per USB anschliessen, "
                    "USB-Debugging bestaetigen und nochmal druecken."
                ]
            ),
        }
    serial = serials[0]
    tcpip = _run_process(["adb", "-s", serial, "tcpip", port], timeout=30, env=_adb_env())
    _append_adb_output(outputs, f"adb -s {serial} tcpip {port}", tcpip)
    if tcpip["returncode"] != 0:
        return {"returncode": int(tcpip["returncode"]), "output": "\n\n".join(outputs)}
    time.sleep(2.0)
    if target:
        connect = _run_process(["adb", "connect", target], timeout=30, env=_adb_env())
        _append_adb_output(outputs, f"adb connect {target}", connect)
        return {"returncode": int(connect["returncode"]), "output": "\n\n".join(outputs)}
    return {"returncode": 0, "output": "\n\n".join(outputs)}


def _common_hci_paths(package_name: str) -> list[str]:
    paths = [
        "/sdcard/btsnoop_hci.log",
        "/sdcard/Download/btsnoop_hci.log",
        "/data/misc/bluetooth/logs/btsnoop_hci.log",
        "/data/misc/bluetooth/logs/btsnoop_hci.log.last",
        "/data/misc/bluedroid/btsnoop_hci.log",
    ]
    if package_name:
        paths += [
            f"/sdcard/Android/data/{package_name}/files/btsnoop_hci.log",
            f"/sdcard/Android/data/{package_name}/files/hci_log/btsnoop_hci.log",
        ]
    return paths


def _list_hci_logs(data: dict[str, object]) -> dict[str, object]:
    hci_dir = _safe_config_path(data.get("hci_log_dir"), DEFAULT_HCI_LOG_DIR)
    files = []
    for folder, patterns in ((hci_dir, ["*.log", "*.cfa", "*.pcap", "*.pcapng"]),):
        for pattern in patterns:
            for item in folder.glob(pattern):
                if item.is_file():
                    files.append(
                        {
                            "name": item.name,
                            "path": str(item),
                            "folder": str(folder),
                            "size": item.stat().st_size,
                            "mtime": int(item.stat().st_mtime),
                        }
                    )
    files.sort(key=lambda row: int(row["mtime"]), reverse=True)
    return {"returncode": 0, "output": f"{len(files)} Logdatei(en) gefunden", "files": files}


def _hci_log_files(data: dict[str, object]) -> list[dict[str, object]]:
    files = _list_hci_logs(data).get("files")
    return files if isinstance(files, list) else []


def _capture_paths_for_log(log_path: Path, capture_dir: Path) -> tuple[Path, Path]:
    jsonl_path = capture_dir / f"{log_path.stem}.jsonl"
    frames_path = capture_dir / f"{log_path.stem}.frames.jsonl"
    return jsonl_path, frames_path


def _resolve_frames_file(data: dict[str, object]) -> Path | None:
    capture_dir = _safe_config_path(data.get("capture_dir"), DEFAULT_CAPTURE_DIR)
    hci_dir = _safe_config_path(data.get("hci_log_dir"), DEFAULT_HCI_LOG_DIR)
    frames_value = str(data.get("frames_file") or "").strip()
    if frames_value:
        frames_path = Path(frames_value)
        if not frames_path.is_absolute():
            frames_path = capture_dir / frames_path
        if frames_path.is_file():
            return frames_path.resolve()

    source = str(data.get("capture_file") or "").strip()
    if source:
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = hci_dir / source_path
        if source_path.name.endswith(".frames.jsonl") and source_path.is_file():
            return source_path.resolve()
        if source_path.suffix.lower() in {".log", ".cfa", ".pcap", ".pcapng"}:
            _, frames_path = _capture_paths_for_log(source_path, capture_dir)
            if frames_path.is_file():
                return frames_path.resolve()

    candidates = sorted(capture_dir.glob("*.frames.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0].resolve() if candidates else None


def _format_gui_compare_app_log(frames_path: Path, direction: str | None = None) -> str:
    lines = [f"Aktueller Mitschnitt: {frames_path.name}"]
    count = 0
    with frames_path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            row_dir = str(row.get("dir") or "").lower()
            if direction and row_dir != direction.lower():
                continue
            if row.get("cmd") is not None and row.get("mode") is not None:
                payload = {
                    "time": row.get("time"),
                    "dir": row.get("dir"),
                    "cmd": row.get("cmd"),
                    "mode": row.get("mode"),
                    "parm": row.get("parm") or [],
                }
                prefix = "[INFO APP]  "
            else:
                att = str(row.get("att") or "").strip().lower()
                raw_hex = str(row.get("value_hex") or row.get("att_hex") or row.get("hex") or "").strip()
                if row_dir != "rx" or att not in {"notify", "indicate"} or not raw_hex:
                    continue
                payload = {
                    "time": row.get("time"),
                    "dir": row.get("dir"),
                    "att": att,
                    "handle": row.get("handle"),
                    "hex": raw_hex,
                }
                prefix = "[INFO NOTIFY]  "
            lines.append(prefix + json.dumps(payload, ensure_ascii=False))
            count += 1
    if count == 0:
        missing_kind = "Notify/RX" if direction == "rx" else "cmd/mode/parm"
        lines.append(f"[INFO APP]  Keine {missing_kind} Frames in {frames_path.name} gefunden.")
    lines.append("-" * 72)
    return "\n".join(lines)


def _load_capture_file(data: dict[str, object]) -> dict[str, object]:
    hci_dir = _safe_config_path(data.get("hci_log_dir"), DEFAULT_HCI_LOG_DIR)
    capture_dir = _safe_config_path(data.get("capture_dir"), DEFAULT_CAPTURE_DIR)
    source = str(data.get("capture_file") or "").strip()
    if not source:
        return {"returncode": 1, "output": "Keine Datei ausgewaehlt."}
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = (
            capture_dir / source_path
            if source_path.suffix.lower() in {".jsonl", ".txt", ".json", ".csv"}
            else hci_dir / source_path
        )
    source_path = source_path.resolve()
    allowed = [hci_dir.resolve(), capture_dir.resolve()]
    if not any(str(source_path).startswith(str(folder)) for folder in allowed):
        return {"returncode": 1, "output": "Datei liegt ausserhalb der erlaubten Wireshark-Ordner."}
    if not source_path.is_file():
        return {"returncode": 1, "output": f"Datei nicht gefunden: {source_path}"}
    if source_path.suffix.lower() in {".log", ".cfa", ".pcap", ".pcapng"}:
        converted = _btsnoop_to_jsonl({**data, "capture_file": str(source_path)})
        if converted["returncode"] != 0:
            return converted
        source_path = Path(str(converted.get("frames_file") or converted.get("file") or ""))
    elif source_path.suffix.lower() == ".jsonl" and not source_path.name.endswith(".frames.jsonl"):
        frames_path = _write_pull7_frames(source_path, all_att=True)
        if frames_path.is_file() and frames_path.stat().st_size > 0:
            source_path = frames_path
    if source_path.suffix.lower() not in {".txt", ".json", ".jsonl", ".csv"}:
        return {"returncode": 1, "output": f"{source_path.name} ist binaer. Erst btsnoop -> JSONL ausfuehren."}
    text = source_path.read_text(encoding="utf-8", errors="replace")
    return {
        "returncode": 0,
        "output": f"Datei geladen: {source_path}",
        "text": text,
        "file": str(source_path),
        "frames_file": str(source_path) if source_path.name.endswith(".frames.jsonl") else "",
        "files": _hci_log_files(data),
    }


def _pull_hci_logs(data: dict[str, object]) -> dict[str, object]:
    package_name = str(data.get("app_package") or "cn.chihiros.chihiros_magic_new").strip()
    target_dir = _safe_config_path(data.get("hci_log_dir"), DEFAULT_HCI_LOG_DIR)
    outputs = []
    pulled = []
    for remote in _common_hci_paths(package_name):
        destination = target_dir / Path(remote).name
        result = _run_adb(data, ["pull", remote, str(destination)], timeout=90)
        outputs.append(f"$ adb pull {remote} {destination}\n{result['output']}")
        if result["returncode"] == 0:
            pulled.append(str(destination))
    return {"returncode": 0 if pulled else 1, "output": "\n\n".join(outputs), "files": pulled}


def _btsnoop_to_jsonl(data: dict[str, object]) -> dict[str, object]:
    capture_dir = _safe_config_path(data.get("capture_dir"), DEFAULT_CAPTURE_DIR)
    hci_dir = _safe_config_path(data.get("hci_log_dir"), DEFAULT_HCI_LOG_DIR)
    source = str(data.get("capture_file") or "").strip()
    if source:
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = hci_dir / source_path
    else:
        candidates = sorted(hci_dir.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not candidates:
            return {"returncode": 1, "output": f"Keine .log Datei in {hci_dir} gefunden."}
        source_path = candidates[0]
    output_path, frames_target = _capture_paths_for_log(source_path, capture_dir)
    try:
        records = _pull7_records_from_btsnoop(
            source_path,
            strip_hci=bool(data.get("strip_hci")),
            language=data.get("language", "de"),
        )
    except Exception as err:
        return {"returncode": 1, "output": f"btsnoop parse fehlgeschlagen: {err}"}
    output_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) for record in records)
        + ("\n" if records else ""),
        encoding="utf-8",
    )
    frames_path = _write_pull7_frames(output_path, all_att=True)
    if frames_path != frames_target and frames_path.is_file():
        frames_target.write_text(frames_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        frames_path = frames_target
    text = frames_path.read_text(encoding="utf-8", errors="replace") if frames_path.is_file() else ""
    return {
        "returncode": 0,
        "output": f"JSONL geschrieben: {output_path}\nFrames geschrieben: {frames_path}",
        "file": str(output_path),
        "frames_file": str(frames_path),
        "log_file": str(source_path),
        "text": text,
        "files": _hci_log_files(data),
    }


def _compare_app_log(data: dict[str, object]) -> dict[str, object]:
    frames_path = _resolve_frames_file(data)
    if not frames_path:
        return {
            "returncode": 1,
            "output": "Keine .frames.jsonl fuer Vergleich gefunden. Erst Frames extrahieren oder Mitschnitt beenden.",
        }
    tx_output = _format_gui_compare_app_log(frames_path, direction="tx")
    rx_output = _format_gui_compare_app_log(frames_path, direction="rx")
    output = "\n\n".join(
        [
            "Aktueller Mitschnitt - Notify/RX",
            rx_output,
            "Aktueller Mitschnitt - TX/Schreibframes",
            tx_output,
        ]
    )
    return {
        "returncode": 0,
        "output": output,
        "text": output,
        "tx_output": tx_output,
        "rx_output": rx_output,
        "frames_file": str(frames_path),
        "title": frames_path.name,
    }


def _adb_debug_guide() -> dict[str, object]:
    return {
        "returncode": 0,
        "output": (
            "Kein Root erkannt. Normaler ADB/Bugreport-Mitschnitt.\n"
            "1. Am Handy Entwickleroptionen und USB-Debugging aktivieren.\n"
            "2. Wenn ADB per WLAN nicht geht: Handy per USB verbinden.\n"
            "3. 'ADB USB freischalten' druecken und die Abfrage am Handy bestaetigen.\n"
            "4. In der App die gewuenschte Aktion ausfuehren.\n"
            "5. Danach 'Mitschnitt Ende' druecken. Das holt den Bugreport und dauert laenger als Root-Direkt."
        ),
    }


def _start_capture(data: dict[str, object]) -> dict[str, object]:
    package_name = str(data.get("app_package") or "cn.chihiros.chihiros_magic_new").strip()
    outputs = []
    returncode = 0
    if data.get("root_direct"):
        root_id = _adb_su(data, "id", timeout=30)
        _append_adb_output(outputs, "adb shell su -c id", root_id)
        if not _adb_su_ok(root_id):
            return {"returncode": 1, "output": "\n\n".join(outputs + ["Root nicht verfuegbar. Erst Root pruefen."])}
        if package_name:
            result = _adb_su(data, f"am force-stop {shlex.quote(package_name)}", timeout=30)
            _append_adb_output(outputs, f"adb shell su -c am force-stop {package_name}", result)
            returncode = max(returncode, int(result["returncode"]))
        root_commands = [
            "settings put secure bluetooth_hci_log 1",
            "settings put global bluetooth_btsnoop_default_mode full",
            "setprop persist.bluetooth.btsnooplogmode full",
            "setprop persist.bluetooth.btsnoopdefaultmode full",
            "svc bluetooth disable",
            "svc bluetooth enable",
        ]
        for command in root_commands:
            result = _adb_su(data, command, timeout=30)
            _append_adb_output(outputs, f"adb shell su -c {command}", result)
            if result["returncode"] != 0:
                returncode = int(result["returncode"])
            if command == "svc bluetooth disable":
                time.sleep(2.0)
        time.sleep(2.0)
        if package_name:
            resolved = _adb_su(
                data,
                f"cmd package resolve-activity --brief {shlex.quote(package_name)} 2>/dev/null",
                timeout=30,
            )
            component = ""
            for line in reversed(str(resolved.get("output") or "").splitlines()):
                text = line.strip()
                if "/" in text and not text.startswith("priority="):
                    component = text
                    break
            if not component:
                component = f"{package_name}/.MainActivity"
            result = _adb_su(data, f"am start -n {shlex.quote(component)}", timeout=30)
            _append_adb_output(outputs, f"adb shell su -c am start -n {component}", result)
        outputs.append("Root-Modus aktiv. Mitschnitt laeuft mit direktem HCI-Pull.")
    else:
        commands = [
            ["shell", "logcat", "-c"],
            ["shell", "settings", "put", "secure", "bluetooth_hci_log", "1"],
            ["shell", "svc", "bluetooth", "disable"],
            ["shell", "svc", "bluetooth", "enable"],
        ]
        for command in commands:
            result = _run_adb(data, command, timeout=30)
            outputs.append(f"$ adb {' '.join(command)}\n{result['output']}")
            if result["returncode"] != 0:
                returncode = int(result["returncode"])
            if command == ["shell", "svc", "bluetooth", "disable"]:
                time.sleep(2.0)
        time.sleep(2.0)
        outputs.append("Root-Modus aus. Mitschnitt laeuft, Ende holt HCI per Standardpfad.")
    outputs.append("Jetzt Aktion in der Chihiros App ausfuehren, danach Mitschnitt Ende klicken.")
    return {"returncode": returncode, "output": "\n\n".join(outputs)}


def _pull_root_hci_direct(
    data: dict[str, object],
    *,
    stop_capture: bool = True,
) -> dict[str, object]:
    target_dir = _safe_config_path(data.get("hci_log_dir"), DEFAULT_HCI_LOG_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    root_id = _adb_su(data, "id", timeout=30)
    _append_adb_output(outputs, "adb shell su -c id", root_id)
    if not _adb_su_ok(root_id):
        return {"returncode": 1, "output": "\n\n".join(outputs + ["Root nicht verfuegbar."])}
    candidates = (
        "/data/log/bt/btsnoop_hci.log",
        "/data/log/bt/btsnoop_hci.log.last",
        "/data/misc/bluetooth/logs/btsnoop_hci.log",
        "/data/misc/bluetooth/logs/btsnoop_hci.log.last",
        "/data/media/0/btsnoop_hci.log",
        "/data/media/0/btsnoop_hci.log.last",
        "/data/media/0/btsnooz_hci.log",
        "/data/media/0/btsnooz_hci.log.last",
    )
    remote_path = ""
    for candidate in candidates:
        probe = _adb_su(
            data,
            f"if [ -f {candidate} ] && [ $(wc -c < {candidate}) -gt 16 ]; then echo {candidate}; fi",
            timeout=30,
        )
        _append_adb_output(outputs, f"adb shell su -c probe {candidate}", probe)
        if probe["returncode"] == 0 and str(probe.get("output") or "").strip():
            remote_path = str(probe["output"]).splitlines()[-1].strip()
            break
    if not remote_path:
        return {
            "returncode": 1,
            "output": "\n\n".join(
                outputs
                + [
                    "Keine direkte btsnoop_hci.log per Root gefunden. "
                    "Mitschnitt Start ausfuehren, App neu verbinden und eine BLE-Aktion ausfuehren."
                ]
            ),
        }
    stamp = _capture_filename_timestamp(language=data.get("language", "de"))
    local_path = target_dir / f"btsnoop_hci_{stamp}.log"
    tmp_remote = f"/sdcard/chihiros_btsnoop_{stamp}.log"
    copy_result = _adb_su(data, f"cp {remote_path} {tmp_remote} && chmod 666 {tmp_remote}", timeout=60)
    _append_adb_output(outputs, f"adb shell su -c cp {remote_path}", copy_result)
    if copy_result["returncode"] != 0:
        return {"returncode": int(copy_result["returncode"]), "output": "\n\n".join(outputs)}
    pull_result = _run_adb(data, ["pull", tmp_remote, str(local_path)], timeout=120)
    _append_adb_output(outputs, f"adb pull {tmp_remote} {local_path}", pull_result)
    _adb_su(data, f"rm -f {tmp_remote}", timeout=30)
    if stop_capture:
        _adb_su(data, "settings put secure bluetooth_hci_log 0", timeout=30)
        _adb_su(data, "settings put global bluetooth_btsnoop_default_mode empty", timeout=30)
        _adb_su(data, "setprop persist.bluetooth.btsnooplogmode disabled", timeout=30)
        _adb_su(data, "setprop persist.bluetooth.btsnoopdefaultmode empty", timeout=30)
    files = [str(local_path)] if pull_result["returncode"] == 0 and local_path.is_file() else []
    return {
        "returncode": 0 if files else int(pull_result["returncode"]),
        "output": "\n\n".join(outputs),
        "files": files,
    }


def _snapshot_capture(data: dict[str, object]) -> dict[str, object]:
    if not data.get("root_direct"):
        return {
            "returncode": 1,
            "output": "HCI-Zwischenstaende benoetigen den Root-Direktmodus.",
            "files": [],
        }
    result = _pull_root_hci_direct(data, stop_capture=False)
    files = result.get("files") if isinstance(result.get("files"), list) else []
    if result.get("returncode") == 0 and files:
        result["snapshot_file"] = str(files[-1])
    return result


def _end_capture(data: dict[str, object]) -> dict[str, object]:
    outputs = []
    pulled = {"returncode": 1, "output": "", "files": []}
    for attempt in range(1, 6):
        if data.get("root_direct"):
            pulled = _pull_root_hci_direct(data)
        else:
            pulled = _pull_hci_logs(data)
        outputs.append(f"Versuch {attempt}:\n{pulled['output']}")
        pulled_files = pulled.get("files") if isinstance(pulled.get("files"), list) else []
        if pulled["returncode"] == 0 and pulled_files:
            break
        if attempt < 5:
            time.sleep(2.0)
    outputs.append(pulled["output"])
    pulled_files = pulled.get("files") if isinstance(pulled.get("files"), list) else []
    convert_data = {**data}
    if pulled_files:
        convert_data["capture_file"] = str(pulled_files[-1])
    converted = _btsnoop_to_jsonl(convert_data)
    outputs.append(converted["output"])
    returncode = 0 if pulled["returncode"] == 0 or converted["returncode"] == 0 else 1
    response: dict[str, object] = {
        "returncode": returncode,
        "output": "\n\n".join(str(item) for item in outputs if item),
        "files": _hci_log_files(data),
    }
    converted_file = converted.get("frames_file") or converted.get("file")
    if converted_file and Path(str(converted_file)).is_file():
        response["text"] = Path(str(converted_file)).read_text(encoding="utf-8", errors="replace")
        response["file"] = str(converted_file)
        response["frames_file"] = str(converted_file)
    if pulled_files:
        response["log_file"] = str(pulled_files[-1])
    return response


def run_wireshark_adb_action(data: dict[str, object]) -> dict[str, object]:
    action = str(data.get("action") or "").strip()
    if action == "list-files":
        return _list_hci_logs(data)
    if action == "load-file":
        return _load_capture_file(data)
    if action == "devices":
        return _run_adb(data, ["devices", "-l"], target=False)
    if action == "connect":
        return _connect_adb(data)
    if action == "adb-usb":
        return _enable_adb_over_usb(data)
    if action == "root-check":
        normal = _run_adb(data, ["shell", "id"], timeout=20)
        root = _run_adb(data, ["shell", "su -c id"], timeout=20)
        return {
            "returncode": 0 if normal["returncode"] == 0 or root["returncode"] == 0 else 1,
            "output": f"$ adb shell id\n{normal['output']}\n\n$ adb shell su -c id\n{root['output']}",
        }
    if action == "pull-hci":
        return _pull_hci_logs(data)
    if action == "btsnoop-jsonl":
        return _btsnoop_to_jsonl(data)
    if action == "compare-app-log":
        return _compare_app_log(data)
    if action == "adb-debug-guide":
        return _adb_debug_guide()
    if action == "capture-start":
        return _start_capture(data)
    if action == "capture-snapshot":
        return _snapshot_capture(data)
    if action == "capture-end":
        return _end_capture(data)
    raise ValueError(f"Unbekannte Wireshark/ADB Aktion: {action}")
