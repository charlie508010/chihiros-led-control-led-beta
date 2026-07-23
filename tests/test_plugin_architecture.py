"""Contracts for the isolated Chihiros device-plugin architecture."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "chihiros"
LED_PLUGIN = COMPONENT / "plugins" / "led"


def _load_manifest_module():
    path = COMPONENT / "core" / "plugin_loader" / "manifest.py"
    spec = importlib.util.spec_from_file_location("test_chihiros_plugin_manifest", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_led_plugin_has_complete_manifest_and_isolated_subsystems() -> None:
    """LED must be discoverable as a plugin with explicit subsystem boundaries."""
    data = json.loads((LED_PLUGIN / "plugin.json").read_text(encoding="utf-8"))

    assert data["id"] == "led"
    assert data["python_entrypoint"] == "plugin.py"
    assert data["frontend"] == "dashboard/chihiros-led-card.js"
    assert data["platforms"] == ["light", "sensor", "switch", "fan"]
    for directory in ("protocol", "services", "entities", "storage", "cli", "dashboard", "translations"):
        assert (LED_PLUGIN / directory).is_dir()
    assert (LED_PLUGIN / "const.py").is_file()
    assert (LED_PLUGIN / "validators.py").is_file()
    assert (LED_PLUGIN / "services" / "runtime.py").is_file()
    assert (LED_PLUGIN / "storage" / "runtime.py").is_file()
    for platform in ("light", "sensor", "switch", "fan"):
        assert (LED_PLUGIN / "entities" / f"{platform}.py").is_file()


def test_integration_uses_led_plugin_as_canonical_domain_implementation() -> None:
    """Core runtime imports must resolve LED constants and services through the plugin."""
    integration = (LED_PLUGIN / "integration.py").read_text(encoding="utf-8")
    domain_entrypoint = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    light = (COMPONENT / "light.py").read_text(encoding="utf-8")
    sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
    switch = (COMPONENT / "switch.py").read_text(encoding="utf-8")

    assert "from .const import (" in integration
    assert "from .services import async_update_led_services" in integration
    assert "from .plugins.led.integration import (" in domain_entrypoint
    assert "from .plugins.led.services import async_enable_led_auto_mode" in switch
    assert ".packages.led" not in integration
    assert ".packages.led" not in switch
    assert "async_setup_entry = async_setup_led_plugin_entry" in light
    assert "async_setup_entry = async_setup_led_plugin_entry" in sensor
    assert "async_setup_entry = async_setup_led_plugin_entry" in switch


def test_plugin_manifest_rejects_paths_outside_plugin_directory(tmp_path: Path) -> None:
    """A plugin must not escape its own directory through manifest paths."""
    module = _load_manifest_module()
    manifest_path = tmp_path / "plugin.json"
    manifest_path.write_text(
        json.dumps({"id": "unsafe", "python_entrypoint": "../outside.py"}),
        encoding="utf-8",
    )

    try:
        module.PluginManifest.from_path(manifest_path)
    except ValueError as err:
        assert "inside its plugin directory" in str(err)
    else:
        raise AssertionError("Unsafe plugin path was accepted")


def test_led_manifest_exposes_entity_platforms_to_core() -> None:
    """The validated manifest must expose platforms without plugin-specific imports."""
    module = _load_manifest_module()
    manifest = module.PluginManifest.from_path(LED_PLUGIN / "plugin.json")

    assert manifest.platforms == ("light", "sensor", "switch", "fan")
    assert manifest.public_data()["platforms"] == ["light", "sensor", "switch", "fan"]


def test_addon_server_reports_discovered_plugins_instead_of_fixed_empty_values() -> None:
    """The add-on API must expose the manifests discovered by the Core."""
    server = (ROOT / "chihiros_beta" / "ui" / "server.py").read_text(encoding="utf-8")

    assert "def plugin_manifest_rows()" in server
    assert 'CONFIG_ROOT / ".chihiros_led_core" / "plugins"' in server
    assert '"installed_plugins": installed_plugin_kinds()' in server
    assert '"plugin_assets": plugin_assets()' in server


def test_doser_devices_use_separate_entries_in_led_core_domain() -> None:
    """Doser devices must use their own entries without creating a second integration tile."""
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
    config_flow = (LED_PLUGIN / "config_flow.py").read_text(encoding="utf-8")
    integration = (LED_PLUGIN / "integration.py").read_text(encoding="utf-8")
    run_script = (ROOT / "chihiros_beta" / "run.sh").read_text(encoding="utf-8")

    assert manifest["domain"] == "chihiros_led_core"
    assert {"local_name": "DYDOSE*", "connectable": True} in manifest["bluetooth"]
    assert {"local_name": "DYMIX*", "connectable": True} in manifest["bluetooth"]
    assert "if is_doser_entry(entry):" in sensor
    assert "ENTRY_DEVICE_KIND: DEVICE_KIND_DOSER" in config_flow
    assert "if is_doser_name(discovery_info.name):" in config_flow
    assert "DOSER_PLATFORMS: list[Platform] = [Platform.SENSOR]" in integration
    assert "if is_doser_entry(entry):" in integration
    assert 'doser_integration_target="/config/custom_components/chihiros_doser"' not in run_script
    assert "custom_components/chihiros_doser/." not in run_script

    platform_loader = (ROOT / "custom_components" / "chihiros" / "core" / "plugin_loader" / "platforms.py").read_text(
        encoding="utf-8"
    )
    assert '_DOSER_PLUGIN_ID = "doser"' in platform_loader
    assert "doser_entry = is_doser_entry(entry)" in platform_loader
    assert "not doser_entry and loaded.manifest.plugin_id == _DOSER_PLUGIN_ID" in platform_loader
