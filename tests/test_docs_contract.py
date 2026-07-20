"""Documentation and dashboard translation contracts."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_uses_led_cli_group_and_obsolete_commands_are_absent() -> None:
    """Examples use the LED group and removed commands never return to Typer registrations."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
    cli = (ROOT / "src/chihiros_led_control/cli.py").read_text(encoding="utf-8")
    assert "chihirosctl led set-brightness" in readme
    for obsolete in ("delete-setting-exact", "reset-settings-7", "test-auto-parameter", "hard-reset"):
        assert obsolete not in cli


def test_dashboard_has_matching_translation_keys() -> None:
    """The dashboard's German and English dictionaries expose the same keys."""
    source = (ROOT / "custom_components/chihiros/plugins/led/dashboard/chihiros-led-core-card.js").read_text()
    de = source[source.index("de: {") : source.index("en: {")]
    en_start = source.index("en: {")
    en = source[en_start : source.index("\n    };", en_start)]

    def keys(block: str) -> set[str]:
        return set(re.findall(r"^\s{8}([a-z0-9_]+):", block, re.MULTILINE))

    assert keys(de) == keys(en)
