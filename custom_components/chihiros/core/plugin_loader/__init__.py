"""Stable plugin discovery and registration interface."""

from ...plugin_loader import (
    PLUGIN_REGISTRY_DATA_KEY,
    LoadedPlugin,
    PluginManifest,
    PluginRegistry,
    async_load_plugins,
    discover_plugin_manifests,
    plugin_roots,
)

__all__ = [
    "PLUGIN_REGISTRY_DATA_KEY",
    "LoadedPlugin",
    "PluginManifest",
    "PluginRegistry",
    "async_load_plugins",
    "discover_plugin_manifests",
    "plugin_roots",
]
