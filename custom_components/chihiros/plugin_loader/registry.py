"""Runtime registry for loaded Chihiros plugins."""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType

from .manifest import PluginManifest


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    """One successfully imported plugin."""

    manifest: PluginManifest
    module: ModuleType


class PluginRegistry:
    """Keep loaded plugins isolated and addressable by their manifest id."""

    def __init__(self) -> None:
        """Initialize an empty plugin registry."""
        self._plugins: dict[str, LoadedPlugin] = {}

    def register(self, plugin: LoadedPlugin) -> None:
        """Register a plugin exactly once."""
        plugin_id = plugin.manifest.plugin_id
        if plugin_id in self._plugins:
            raise ValueError(f"Duplicate Chihiros plugin id: {plugin_id}")
        self._plugins[plugin_id] = plugin

    def get(self, plugin_id: str) -> LoadedPlugin | None:
        """Return one loaded plugin by id."""
        return self._plugins.get(plugin_id)

    def all(self) -> tuple[LoadedPlugin, ...]:
        """Return loaded plugins in stable id order."""
        return tuple(self._plugins[key] for key in sorted(self._plugins))
