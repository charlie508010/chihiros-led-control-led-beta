"""Documentation and optional Wireshark package contracts."""

from __future__ import annotations

import importlib.util
import json
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_uses_led_cli_group_and_obsolete_commands_are_absent() -> None:
    """Examples use the LED group and removed commands never return to Typer registrations."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
    cli = (ROOT / "src/chihiros_led_control/cli.py").read_text(encoding="utf-8")
    assert "chihirosctl led set-brightness" in readme
    for obsolete in ("delete-setting-exact", "reset-settings-7", "test-auto-parameter", "hard-reset"):
        assert obsolete not in cli


def test_wireshark_package_is_external_and_reproducible_artifact_exists() -> None:
    """Wireshark ships outside the auto-loaded LED plugin directory as an installable TGZ."""
    source = ROOT / "plugin_packages/wireshark"
    manifest = json.loads((source / "plugin.json").read_text())
    artifact = ROOT / f"dist/chihiros-wireshark-{manifest['version']}.tgz"
    assert manifest["runtimes"] == ["addon"]
    assert set(manifest["backend_actions"]) == {"analyze_wireshark_text", "run_wireshark_adb_action"}
    with tarfile.open(artifact, "r:gz") as bundle:
        assert set(bundle.getnames()) == {"README.md", "backend.py", "plugin.json", "www/wireshark-plugin.js"}


def test_wireshark_decoder_handles_saved_led_frame() -> None:
    """The packaged backend decodes a captured LED brightness frame without non-LED helpers."""
    path = ROOT / "plugin_packages/wireshark/backend.py"
    spec = importlib.util.spec_from_file_location("test_wireshark_backend", path)
    assert spec and spec.loader
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    result = backend.analyze_wireshark_text("5A 01 07 00 20 07 00 64 45")
    assert result["count"] == 1
    assert result["frames"][0]["mode_name"] == "brightness"


def test_dashboard_has_matching_translation_keys() -> None:
    """The dashboard's German and English dictionaries expose the same keys."""
    source = (ROOT / "custom_components/chihiros/plugins/led/dashboard/chihiros-led-core-card.js").read_text()
    de = source[source.index("de: {") : source.index("en: {")]
    en_start = source.index("en: {")
    en = source[en_start : source.index("\n    };", en_start)]

    def keys(block: str) -> set[str]:
        return set(re.findall(r"^\s{8}([a-z0-9_]+):", block, re.MULTILINE))

    assert keys(de) == keys(en)
