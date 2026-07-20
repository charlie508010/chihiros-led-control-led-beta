"""Shared debug payload helpers for dashboard service responses."""

from __future__ import annotations

import json
import re
from typing import Any

SERVICE_DOMAIN = "chihiros_led_core"


def normalize_protocol_debug_text(value: str) -> str:
    """Normalize shared protocol debug text in one central place."""
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^\s*Raw Debug:?\s*\n?", "", text, flags=re.IGNORECASE)
    json_block_pattern = r"(?:^|\n){label}:\n\{{.*?\}}(?=\n[A-Z][A-Za-z ]*:|\n[A-Z]{{2,}}\b|\Z)"
    text = re.sub(
        json_block_pattern.format(label="Request JSON"),
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(
        json_block_pattern.format(label="Response JSON"),
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    raw_lines = text.splitlines()
    reordered_lines: list[str] = []
    index = 0
    while index < len(raw_lines):
        line = raw_lines[index]
        stripped = line.strip()
        if not stripped.startswith("[TX #"):
            reordered_lines.append(line)
            index += 1
            continue

        tx_block: list[str] = [line]
        index += 1
        while index < len(raw_lines):
            current = raw_lines[index]
            current_stripped = current.strip()
            is_separator = bool(current_stripped) and set(current_stripped) == {"-"}
            if is_separator:
                debug_after = raw_lines[index + 1] if index + 1 < len(raw_lines) else ""
                if debug_after.strip().startswith("DEBUG") and "Sending commands [" in debug_after:
                    tx_block.insert(0, debug_after)
                    reordered_lines.extend(tx_block)
                    reordered_lines.append(current)
                    index += 2
                    break
                debug_inside = [
                    entry for entry in tx_block if entry.strip().startswith("DEBUG") and "Sending commands [" in entry
                ]
                other_inside = [
                    entry
                    for entry in tx_block
                    if not (entry.strip().startswith("DEBUG") and "Sending commands [" in entry)
                ]
                reordered_lines.extend(debug_inside + other_inside)
                reordered_lines.append(current)
                index += 1
                break
            tx_block.append(current)
            index += 1
        else:
            debug_inside = [
                entry for entry in tx_block if entry.strip().startswith("DEBUG") and "Sending commands [" in entry
            ]
            other_inside = [
                entry for entry in tx_block if not (entry.strip().startswith("DEBUG") and "Sending commands [" in entry)
            ]
            reordered_lines.extend(debug_inside + other_inside)

    lines: list[str] = []
    in_compare_log = False
    skip_separator = False
    for line in reordered_lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered == "protocol debug":
            continue
        if stripped == "VERGLEICH APP-LOG":
            in_compare_log = True
            skip_separator = False
            lines.append(line)
            continue
        if in_compare_log and stripped == "GERÄTEANTWORT":
            in_compare_log = False
            skip_separator = False
            lines.append(line)
            continue
        if in_compare_log and stripped.startswith(("[INFO]", "[INFO APP]")) and '"dir": "rx"' in stripped:
            skip_separator = True
            continue
        if in_compare_log and skip_separator and set(stripped) == {"-"}:
            skip_separator = False
            continue
        skip_separator = False
        lines.append(line)

    collapsed: list[str] = []
    previous_was_separator = False
    for line in lines:
        is_separator = set(line.strip()) == {"-"} if line.strip() else False
        if is_separator and previous_was_separator:
            continue
        collapsed.append(line)
        previous_was_separator = is_separator
    return "\n".join(collapsed).strip()


def _text_section(title: str, value: str) -> dict[str, Any] | None:
    text = str(value or "").strip()
    if not text:
        return None
    return {"title": title, "type": "text", "value": text}


def _json_section(title: str, value: Any) -> dict[str, Any] | None:
    if value in ({}, None, ""):
        return None
    return {"title": title, "type": "json", "value": value}


def _protocol_debug_section(value: str) -> dict[str, Any] | None:
    text = normalize_protocol_debug_text(value)
    if not text or text.lower() == "protocol debug":
        return None
    return {"title": "Raw Debug", "type": "text", "value": text}


def _doc_command_section(
    *,
    service: str,
    request: dict[str, Any] | None = None,
    summary: str = "",
) -> dict[str, Any] | None:
    """Build an additional copy-friendly service example without replacing raw debug."""
    debug_service = str(service or "").strip()
    if not debug_service:
        return None
    if not debug_service.startswith(f"{SERVICE_DOMAIN}."):
        debug_service = f"{SERVICE_DOMAIN}.{debug_service}"

    data = dict(request or {})
    if not data:
        return None
    data.setdefault("debug", True)

    lines = [
        "Dashboard / Home Assistant action:",
        "",
        f"action: {debug_service}",
        "data:",
    ]
    lines.extend(_yaml_lines(data, indent=2))

    ctl_lines = _ctl_example_lines(debug_service, data)
    if ctl_lines:
        lines.extend(["", "CTL / Terminal example:", "", *ctl_lines])

    if summary:
        lines.extend(["", f"Summary: {summary}"])

    return {"title": "Doku / Kopieren", "type": "text", "value": "\n".join(lines)}


def _yaml_lines(value: Any, *, indent: int = 0) -> list[str]:
    """Render a small, dependency-free YAML subset for copyable HA actions."""
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, dict):
                lines.append(f"{prefix}{key}:")
                lines.extend(_yaml_lines(item, indent=indent + 2))
            elif isinstance(item, list):
                lines.append(f"{prefix}{key}:")
                lines.extend(_yaml_lines(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{prefix}-")
                lines.extend(_yaml_lines(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return lines
    return [f"{prefix}{_yaml_scalar(value)}"]


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, int | float):
        return str(value)
    text = str(value)
    if not text or any(char in text for char in ":#{}[]&,*?|-<>=!%@`"):
        return json.dumps(text, ensure_ascii=False)
    return text


def _ctl_example_lines(service: str, data: dict[str, Any]) -> list[str]:
    """Return a best-effort CLI example for known LED scheduler services."""
    address = str(data.get("address") or "").strip()
    if service.endswith(".add_schedule"):
        start = str(data.get("start") or "").strip()
        end = str(data.get("end") or "").strip()
        levels = data.get("levels") if isinstance(data.get("levels"), dict) else data.get("brightness")
        levels = levels if isinstance(levels, dict) else {}
        weekdays = data.get("weekdays")
        weekday_text = ",".join(str(item) for item in weekdays) if isinstance(weekdays, list) else str(weekdays or "")
        ramp = max(1, int(data.get("ramp_up_minutes", 1)))
        active = data.get("active")
        parts = ["python -m chihirosctl", "led", "add-schedule"]
        if address:
            parts.extend(["--address", address])
        if start:
            parts.extend(["--start", start])
        if end:
            parts.extend(["--end", end])
        for channel in ("red", "green", "blue", "white"):
            if channel in levels:
                parts.extend([f"--{channel}", str(levels[channel])])
        parts.extend(["--ramp-up-minutes", str(ramp)])
        if weekday_text:
            parts.extend(["--weekdays", weekday_text])
        if active is False:
            parts.append("--inactive")
        parts.append("--debug")
        return [" ".join(parts)]

    if service.endswith(".set_schedule"):
        return [
            "python -m chihirosctl led set-schedule "
            + (f"--address {address} " if address else "")
            + "--debug"
        ]

    if service.endswith(".reset_schedule"):
        command = "python -m chihirosctl --debug led reset-settings"
        if address:
            command += f' "{address}"'
        return [command]

    return []


def build_debug_sections(
    *,
    service: str,
    device: str = "",
    address: str = "",
    action: str = "",
    summary: str = "",
    request: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    raw_debug: str = "",
) -> list[dict[str, Any]]:
    """Build normalized debug sections shared by all dashboard services."""
    debug_service = str(service or "").strip()
    if debug_service and not debug_service.startswith(f"{SERVICE_DOMAIN}."):
        debug_service = f"{SERVICE_DOMAIN}.{debug_service}"
    meta_lines = [
        f"Service: {debug_service}" if debug_service else "",
        f"Summary: {summary}" if summary else "",
        f"Device: {device}" if device else "",
        f"Address: {address}" if address else "",
        f"Action: {action}" if action else "",
    ]
    sections = [
        _text_section("Debug", "\n".join(line for line in meta_lines if line)),
        _doc_command_section(service=debug_service, request=request, summary=summary),
        _protocol_debug_section(raw_debug),
        _json_section("Details JSON", details),
    ]
    return [section for section in sections if section]


def make_debug_data(
    *,
    service: str,
    device: str = "",
    address: str = "",
    action: str = "",
    summary: str = "",
    request: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    raw_debug: str = "",
    sections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a shared debug payload shape for all dashboard services."""
    normalized_sections = sections or build_debug_sections(
        service=service,
        device=device,
        address=address,
        action=action,
        summary=summary,
        request=request,
        response=response,
        details=details,
        raw_debug=raw_debug,
    )
    payload = {
        "service": service,
        "device": device,
        "address": address,
        "action": action,
        "summary": summary,
        "request": request or {},
        "response": response or {},
        "details": details or {},
        "raw_debug": raw_debug or "",
        "sections": normalized_sections,
    }
    return {key: value for key, value in payload.items() if value not in ("", {}, None)}


def render_debug_text(
    *,
    service: str,
    device: str = "",
    address: str = "",
    action: str = "",
    summary: str = "",
    request: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    raw_debug: str = "",
    sections: list[dict[str, Any]] | None = None,
) -> str:
    """Render a plain-text debug payload that is always JSON-safe for HA service responses."""
    normalized_sections = sections or build_debug_sections(
        service=service,
        device=device,
        address=address,
        action=action,
        summary=summary,
        request=request,
        response=response,
        details=details,
        raw_debug=raw_debug,
    )
    blocks: list[str] = []
    for section in normalized_sections:
        title = str(section.get("title") or "").strip()
        section_type = str(section.get("type") or "").strip().lower()
        if section_type == "json":
            value = section.get("value")
            if value in ({}, None, ""):
                continue
            body = json.dumps(value, indent=2, ensure_ascii=False)
            blocks.append(f"{title}:\n{body}" if title else body)
            continue
        value = str(section.get("value") or section.get("text") or "").strip()
        if not value:
            continue
        blocks.append(f"{title}\n{value}" if title else value)
    return "\n\n".join(block for block in blocks if block).strip()


def make_service_result(
    *,
    service: str,
    ok: bool,
    send_status: str = "",
    send_detail: str = "",
    debug: bool = False,
    device: str = "",
    address: str = "",
    action: str = "",
    summary: str = "",
    request: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    raw_debug: str = "",
    sections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a shared service response payload for the dashboard."""
    debug_data = (
        make_debug_data(
            service=service,
            device=device,
            address=address,
            action=action,
            summary=summary,
            request=request,
            response=response,
            details=details,
            raw_debug=raw_debug,
            sections=sections,
        )
        if debug
        else {}
    )
    rendered_debug = (
        render_debug_text(
            service=service,
            device=device,
            address=address,
            action=action,
            summary=summary,
            request=request,
            response=response,
            details=details,
            raw_debug=raw_debug,
            sections=sections,
        )
        if debug
        else ""
    )
    result = {
        "ok": bool(ok),
        "send_status": str(send_status or ""),
        "send_detail": str(send_detail or ""),
        "debug_data": debug_data,
        "debug_output": rendered_debug,
    }
    return {key: value for key, value in result.items() if value not in ("", {}, None)}
