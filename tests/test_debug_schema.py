from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "chihiros" / "debug_schema.py"
SPEC = spec_from_file_location("debug_schema_test_module", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_debug_sections = MODULE.build_debug_sections


make_debug_data = MODULE.make_debug_data


make_service_result = MODULE.make_service_result


def test_make_debug_data_builds_shared_sections() -> None:
    payload = make_debug_data(
        service="reset_schedule",
        device="DYU1000",
        address="AA:BB:CC:DD:EE:FF",
        action="reset_settings()",
        summary="LED schedule reset",
        request={"address": "AA:BB:CC:DD:EE:FF", "debug": True},
        response={"ok": True},
        details={"rows": 0},
        raw_debug="TX 1\nRX 1",
    )

    sections = payload["sections"]
    assert sections[0]["title"] == "Debug"
    assert "Service: chihiros.reset_schedule" in sections[0]["value"]
    assert sections[1]["title"] == "Doku / Kopieren"
    assert "action: chihiros.reset_schedule" in sections[1]["value"]
    assert "debug: true" in sections[1]["value"]
    assert (
        'python -m chihiros_led_control.cli --debug led reset-settings "AA:BB:CC:DD:EE:FF"'
        in sections[1]["value"]
    )
    assert "reset-schedule" not in sections[1]["value"]
    assert sections[2]["title"] == "Raw Debug"
    assert sections[3]["title"] == "Details JSON"


def test_build_debug_sections_skips_empty_values() -> None:
    sections = build_debug_sections(service="set_schedule", summary="Rows: 1")

    assert len(sections) == 1
    assert sections[0]["title"] == "Debug"
    assert "Summary: Rows: 1" in sections[0]["value"]


def test_build_debug_sections_adds_copyable_led_schedule_examples() -> None:
    sections = build_debug_sections(
        service="add_schedule",
        summary="LED schedule period sent",
        request={
            "address": "AA:BB:CC:DD:EE:FF",
            "start": "17:00",
            "end": "22:00",
            "levels": {"red": 65, "green": 40, "blue": 65, "white": 50},
            "ramp_up_minutes": 0,
            "weekdays": ["everyday"],
        },
    )

    doc = sections[1]["value"]
    assert sections[1]["title"] == "Doku / Kopieren"
    assert "action: chihiros.add_schedule" in doc
    assert "address: \"AA:BB:CC:DD:EE:FF\"" in doc
    assert "debug: true" in doc
    assert "python -m chihiros_led_control.cli led add-schedule" in doc
    assert "--red 65 --green 40 --blue 65 --white 50" in doc
