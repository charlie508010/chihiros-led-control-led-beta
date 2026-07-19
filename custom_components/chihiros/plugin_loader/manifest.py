"""Manifest parsing for optional Chihiros device plugins."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Validated metadata for one Chihiros plugin directory."""

    plugin_id: str
    name: str
    version: str
    root: Path
    python_entrypoint: str
    frontend: str
    cli_entrypoint: str
    platforms: tuple[str, ...]
    tabs: tuple[dict[str, str], ...]

    @classmethod
    def from_path(cls, path: Path) -> PluginManifest:
        """Read and validate a ``plugin.json`` file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Plugin manifest must contain an object: {path}")
        plugin_id = str(data.get("id") or "").strip()
        if not _PLUGIN_ID.fullmatch(plugin_id):
            raise ValueError(f"Invalid plugin id {plugin_id!r}: {path}")
        tabs = _normalize_tabs(data.get("tabs"), plugin_id, str(data.get("name") or plugin_id))
        return cls(
            plugin_id=plugin_id,
            name=str(data.get("name") or plugin_id).strip(),
            version=str(data.get("version") or "0.0.0").strip(),
            root=path.parent.resolve(),
            python_entrypoint=_safe_relative_path(data.get("python_entrypoint"), "plugin.py"),
            frontend=_safe_relative_path(data.get("frontend"), ""),
            cli_entrypoint=str(data.get("cli_entrypoint") or "").strip(),
            platforms=_normalize_platforms(data.get("platforms")),
            tabs=tabs,
        )

    def public_data(self) -> dict[str, Any]:
        """Return metadata safe for the dashboard API."""
        return {
            "id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "frontend": self.frontend,
            "platforms": list(self.platforms),
            "tabs": [dict(tab) for tab in self.tabs],
        }


def _safe_relative_path(value: object, default: str) -> str:
    text = str(value or default).strip().replace("\\", "/")
    if not text:
        return ""
    candidate = Path(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Plugin path must stay inside its plugin directory: {text}")
    return text


def _normalize_tabs(value: object, plugin_id: str, plugin_name: str) -> tuple[dict[str, str], ...]:
    rows = value if isinstance(value, list) else []
    tabs: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        tab_id = str(row.get("id") or "").strip()
        if not _PLUGIN_ID.fullmatch(tab_id):
            raise ValueError(f"Invalid tab id {tab_id!r} in plugin {plugin_id}")
        tabs.append(
            {
                "id": tab_id,
                "title": str(row.get("title") or tab_id).strip(),
                "icon": str(row.get("icon") or "").strip(),
            }
        )
    if not tabs:
        tabs.append({"id": plugin_id, "title": plugin_name, "icon": ""})
    return tuple(tabs)


def _normalize_platforms(value: object) -> tuple[str, ...]:
    rows = value if isinstance(value, list) else []
    platforms: list[str] = []
    for row in rows:
        platform = str(row or "").strip()
        if not _PLUGIN_ID.fullmatch(platform):
            raise ValueError(f"Invalid plugin platform {platform!r}")
        if platform not in platforms:
            platforms.append(platform)
    return tuple(platforms)
