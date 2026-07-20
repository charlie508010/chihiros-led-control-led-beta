"""Shared protocol debug rendering for CLI and Home Assistant."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

RxFrameDescription = Callable[[bytes], str | Iterable[str]]


def frame_params(payload: bytes | bytearray) -> list[int]:
    """Return protocol parameters from a raw frame."""
    data = bytes(payload)
    if len(data) < 7:
        return []
    command_length = data[2]
    cmd = data[0]
    if cmd == 0x5B:
        param_len = max(0, int(command_length) - 2)
    else:
        param_len = max(0, int(command_length) - 5)
    available = max(0, len(data) - 7)
    if param_len != available:
        param_len = available
    return [int(value) for value in data[6 : min(len(data) - 1, 6 + param_len)]]


def compact_frame_info(payload: bytes | bytearray, direction: str, timestamp: str = "") -> dict[str, object]:
    """Build compact app-log style frame data."""
    data = bytes(payload)
    info: dict[str, object] = {
        "dir": direction,
        "cmd": data[0] if data else None,
        "mode": data[5] if len(data) >= 6 else None,
        "parm": frame_params(data),
    }
    if timestamp:
        info["time"] = timestamp
    return info


def debug_frame_rows(
    *,
    debug_frames: Iterable[dict[str, Any]],
    tx_debug_frames: Iterable[bytes | bytearray],
    raw_notifications: Iterable[bytes | bytearray],
    directions: set[str] | None = None,
    tx_commands: set[int] | None = None,
    rx_modes: set[int] | None = None,
) -> list[dict[str, object]]:
    """Return compact chronological debug rows filtered by direction and command."""
    allowed_directions = directions or {"tx", "rx"}
    rows: list[dict[str, object]] = []
    for frame in debug_frames:
        payload = frame.get("payload")
        direction = str(frame.get("dir") or "")
        if not isinstance(payload, (bytes, bytearray)) or direction not in allowed_directions:
            continue
        info = compact_frame_info(payload, direction, str(frame.get("time") or ""))
        if direction == "tx":
            if tx_commands and int(info.get("cmd") or -1) not in tx_commands:
                continue
        elif rx_modes and int(info.get("mode") or -1) not in rx_modes:
            continue
        rows.append(info)
    if rows:
        return rows
    if "tx" in allowed_directions:
        for payload in tx_debug_frames:
            info = compact_frame_info(payload, "tx")
            if tx_commands and int(info.get("cmd") or -1) not in tx_commands:
                continue
            rows.append(info)
    if "rx" in allowed_directions:
        for payload in raw_notifications:
            info = compact_frame_info(payload, "rx")
            if rx_modes and int(info.get("mode") or -1) not in rx_modes:
                continue
            rows.append(info)
    return rows


def render_compare_log(
    *,
    debug_frames: Iterable[dict[str, Any]],
    tx_debug_frames: Iterable[bytes | bytearray],
    raw_notifications: Iterable[bytes | bytearray],
    tx_commands: set[int] | None = None,
    include_missing_tx_frames: bool = False,
) -> str:
    """Render app-log comparison with sent frames only."""
    rows = debug_frame_rows(
        debug_frames=debug_frames,
        tx_debug_frames=tx_debug_frames,
        raw_notifications=raw_notifications,
        directions={"tx"},
        tx_commands=tx_commands,
    )
    if include_missing_tx_frames:
        seen = {
            (
                str(row.get("dir") or ""),
                int(row.get("cmd") or -1),
                int(row.get("mode") or -1),
                tuple(int(value) for value in (row.get("parm") or [])),
                str(row.get("time") or ""),
            )
            for row in rows
        }
        for payload in tx_debug_frames:
            info = compact_frame_info(payload, "tx")
            if tx_commands and int(info.get("cmd") or -1) not in tx_commands:
                continue
            exact_key = (
                "tx",
                int(info.get("cmd") or -1),
                int(info.get("mode") or -1),
                tuple(int(value) for value in (info.get("parm") or [])),
                "",
            )
            if any(item[:4] == exact_key[:4] for item in seen):
                continue
            rows.append(info)
            seen.add(exact_key)
    if not rows:
        return ""
    lines = ["-" * 72, "VERGLEICH APP-LOG", "-" * 72]
    for row in rows:
        lines.append(f"[INFO SYSTEM]  {json.dumps(row, ensure_ascii=False)}")
        lines.append("-" * 72)
    return "\n".join(lines)


def render_raw_notifications(
    raw_notifications: Iterable[bytes | bytearray],
    *,
    dedupe: bool = False,
    title: str = "GERÄTEANTWORT",
    describe_rx_frame: RxFrameDescription | None = None,
) -> str:
    """Render RX notifications below the app-log comparison."""
    notifications = [bytes(payload) for payload in raw_notifications]
    if not notifications:
        return ""
    lines = ["-" * 72, title, "-" * 72]
    seen: set[bytes] = set()
    for payload in notifications:
        if dedupe and payload in seen:
            continue
        seen.add(payload)
        lines.append(f"RX: {payload.hex(' ').upper()}")
        lines.extend(render_rx_protocol_debug(payload, describe_rx_frame=describe_rx_frame))
    lines.append("-" * 72)
    return "\n".join(lines)


def render_rx_protocol_debug(
    payload: bytes | bytearray,
    *,
    describe_rx_frame: RxFrameDescription | None = None,
) -> list[str]:
    """Render decoded details for one received RX frame."""
    data = bytes(payload)
    if not data:
        return []
    cmd_id = data[0] if len(data) >= 1 else None
    version = data[1] if len(data) >= 2 else None
    command_length = data[2] if len(data) >= 3 else None
    msg_hi = data[3] if len(data) >= 4 else None
    msg_lo = data[4] if len(data) >= 5 else None
    mode = data[5] if len(data) >= 6 else None
    checksum = data[-1]
    lines = [
        "[RX] Decode Message",
        f"  Command Print    : {[int(b) for b in data]}",
        f"  Command ID       : {cmd_id}",
        f"  Version          : {version}",
        f"  Command Length   : {command_length}",
        f"  Message ID High  : {msg_hi}",
        f"  Message ID Low   : {msg_lo}",
        f"  Mode             : {mode}",
        f"  Parameters       : {frame_params(data)}",
        f"  Checksum         : {checksum}",
    ]
    if describe_rx_frame is not None:
        description = describe_rx_frame(data)
        if isinstance(description, str):
            descriptions = [description] if description else []
        else:
            descriptions = [str(item) for item in description if str(item)]
        if descriptions:
            lines.append(f"  Bedeutung        : {descriptions[0]}")
            lines.extend(f"  Details          : {description_line}" for description_line in descriptions[1:])
    return lines


def render_tx_protocol_debug(
    tx_debug_frames: Iterable[bytes | bytearray],
    *,
    address: str,
    describe_tx_frame: Callable[[int | None, int | None, list[int]], str],
    start_index: int = 1,
) -> str:
    """Render detailed sent TX frames."""
    blocks: list[str] = []
    for index, payload in enumerate(tx_debug_frames, start=start_index):
        data = bytes(payload)
        cmd_id = data[0] if len(data) >= 1 else None
        version = data[1] if len(data) >= 2 else None
        command_length = data[2] if len(data) >= 3 else None
        msg_hi = data[3] if len(data) >= 4 else None
        msg_lo = data[4] if len(data) >= 5 else None
        mode = data[5] if len(data) >= 6 else None
        checksum = data[-1] if data else None
        params = frame_params(data)
        meaning = describe_tx_frame(cmd_id, mode, params)
        lines = [
            f"DEBUG    {address}: Sending commands ['{data.hex()}']",
            f"[TX #{index}] Encode Message",
            f"  Command Print    : {[int(b) for b in data]}",
            f"  Command ID       : {cmd_id}",
            f"  Version          : {version}",
            f"  Command Length   : {command_length}",
            f"  Message ID High  : {msg_hi}",
            f"  Message ID Low   : {msg_lo}",
            f"  Mode             : {mode}",
            f"  Parameters       : {params}",
            f"  Checksum         : {checksum}",
        ]
        if meaning:
            lines.append(f"  Bedeutung        : {meaning}")
        lines.append("-" * 72)
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def render_protocol_debug(
    *,
    debug_frames: Iterable[dict[str, Any]],
    tx_debug_frames: Iterable[bytes | bytearray],
    raw_notifications: Iterable[bytes | bytearray],
    address: str,
    describe_tx_frame: Callable[[int | None, int | None, list[int]], str],
    describe_rx_frame: RxFrameDescription | None = None,
    tx_commands: set[int] | None = None,
    dedupe_rx: bool = False,
    include_missing_tx_frames: bool = False,
) -> str:
    """Render the complete shared protocol debug text for every caller."""
    blocks = [
        render_tx_protocol_debug(tx_debug_frames, address=address, describe_tx_frame=describe_tx_frame),
        render_compare_log(
            debug_frames=debug_frames,
            tx_debug_frames=tx_debug_frames,
            raw_notifications=raw_notifications,
            tx_commands=tx_commands,
            include_missing_tx_frames=include_missing_tx_frames,
        ),
        render_raw_notifications(raw_notifications, dedupe=dedupe_rx, describe_rx_frame=describe_rx_frame),
    ]
    return "\n\n".join(block for block in blocks if block.strip())
