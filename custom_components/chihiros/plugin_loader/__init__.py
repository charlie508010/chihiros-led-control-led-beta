"""Public plugin loader API for Chihiros Core."""

from .loader import PLUGIN_REGISTRY_DATA_KEY, async_load_plugins, discover_plugin_manifests, plugin_roots
from .manifest import PluginManifest
from .registry import LoadedPlugin, PluginRegistry

__all__ = [
    "PLUGIN_REGISTRY_DATA_KEY",
    "LoadedPlugin",
    "PluginManifest",
    "PluginRegistry",
    "async_load_plugins",
    "discover_plugin_manifests",
    "plugin_roots",
]
