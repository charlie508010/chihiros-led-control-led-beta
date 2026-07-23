"""Discovery and loading of packaged and externally installed plugins."""

from __future__ import annotations

import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

from .manifest import PluginManifest
from .registry import LoadedPlugin, PluginRegistry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
PLUGIN_REGISTRY_DATA_KEY = "plugin_registry"


def plugin_roots(hass: HomeAssistant) -> tuple[Path, ...]:
    """Return packaged and configuration-local plugin roots."""
    packaged = Path(__file__).resolve().parents[2] / "plugins"
    external = Path(hass.config.path(".chihiros_led_core", "plugins"))
    return packaged, external


def discover_plugin_manifests(roots: tuple[Path, ...]) -> tuple[PluginManifest, ...]:
    """Discover valid manifests without loading plugin code."""
    manifests: dict[str, PluginManifest] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for manifest_path in sorted(root.glob("*/plugin.json")):
            try:
                manifest = PluginManifest.from_path(manifest_path)
            except (OSError, ValueError, TypeError) as err:
                _LOGGER.error("Ignoring invalid Chihiros plugin manifest %s: %s", manifest_path, err)
                continue
            if manifest.plugin_id in manifests:
                _LOGGER.warning("Ignoring duplicate Chihiros plugin %s from %s", manifest.plugin_id, manifest.root)
                continue
            manifests[manifest.plugin_id] = manifest
    return tuple(manifests[key] for key in sorted(manifests))


async def async_load_plugins(hass: HomeAssistant, domain: str) -> PluginRegistry:
    """Load all discovered plugins and invoke their optional setup hook."""
    domain_data = hass.data.setdefault(domain, {})
    existing = domain_data.get(PLUGIN_REGISTRY_DATA_KEY)
    if isinstance(existing, PluginRegistry):
        return existing

    registry = PluginRegistry()
    manifests = await hass.async_add_executor_job(discover_plugin_manifests, plugin_roots(hass))
    for manifest in manifests:
        if "home_assistant" not in manifest.runtimes:
            continue
        try:
            module = await hass.async_add_executor_job(_load_module, manifest)
            setup = getattr(module, "async_setup_plugin", None)
            if callable(setup):
                result = setup(hass, manifest)
                if inspect.isawaitable(result):
                    result = await result
                if result is False:
                    raise RuntimeError("plugin setup returned false")
            registry.register(LoadedPlugin(manifest=manifest, module=module))
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Could not load Chihiros plugin %s from %s", manifest.plugin_id, manifest.root)
    domain_data[PLUGIN_REGISTRY_DATA_KEY] = registry
    return registry


def _load_module(manifest: PluginManifest) -> ModuleType:
    entrypoint = (manifest.root / manifest.python_entrypoint).resolve()
    if manifest.root not in entrypoint.parents or not entrypoint.is_file():
        raise FileNotFoundError(f"Plugin entrypoint not found: {entrypoint}")
    module_name = f"chihiros_device_plugin_{manifest.plugin_id}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        entrypoint,
        submodule_search_locations=[str(manifest.root)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create module spec for {entrypoint}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module
