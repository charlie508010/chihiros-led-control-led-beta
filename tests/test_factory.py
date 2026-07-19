"""Tests for Chihiros device model detection and factory helpers."""

from __future__ import annotations

import asyncio

from chihiros_led_control.client import ChihirosDosingPump
from chihiros_led_control.factory import (
    create_device,
    detect_model,
    needs_device_type,
    resolve_model,
)
from chihiros_led_control.models import FALLBACK, MODEL_POWER_WATTS, model_power_watts


class FakeBLEDevice:
    """Small BLEDevice stand-in for factory tests."""

    def __init__(self, name: str | None = None) -> None:
        """Create a fake BLE device."""
        self.name = name
        self.address = "AA:BB:CC:DD:EE:FF"


def test_detect_model_matches_name_prefix() -> None:
    """Model detection matches advertised name prefixes."""
    assert detect_model("DYNW601234567890").name == "WRGB II"


def test_detect_model_sets_dyu1000_max_brightness() -> None:
    """DYU1000 uses the standard 100-step WRGB brightness range."""
    model = detect_model("DYU1000ffd22ceb9ae2")

    assert model.max_brightness == 100
    assert model.max_power_watts == 59
    assert model.schedule_reset_parameter == 40
    assert model.schedule_reset_from_snapshot is True


def test_model_power_table_contains_manufacturer_values() -> None:
    """Every supplied LED product size retains its configured maximum power."""
    assert dict(MODEL_POWER_WATTS["Z Light TINY"]) == {"default": 6}
    assert dict(MODEL_POWER_WATTS["Tiny Terrarium Egg"]) == {"default": 10}
    assert dict(MODEL_POWER_WATTS["A II"]) == {
        "301": 15,
        "351": 18,
        "361": 18,
        "401": 18,
        "451": 21,
        "501": 25,
        "601": 28,
        "801": 40,
        "901": 40,
        "1201": 58,
    }
    assert dict(MODEL_POWER_WATTS["WRGB II"]) == {"30": 33, "45": 49, "60": 67, "90": 100, "120": 130}
    assert dict(MODEL_POWER_WATTS["WRGB II Pro"]) == {"30": 37, "45": 56, "60": 74, "80": 100, "90": 110, "120": 138}
    assert dict(MODEL_POWER_WATTS["WRGB II Slim"]) == {"30": 23, "45": 35, "60": 45, "90": 69, "120": 90}
    assert dict(MODEL_POWER_WATTS["C II"]) == {"default": 16}
    assert dict(MODEL_POWER_WATTS["C II RGB"]) == {"default": 20}
    assert dict(MODEL_POWER_WATTS["Universal WRGB"]) == {
        "550": 28,
        "600": 29,
        "700": 33,
        "800": 36,
        "920": 55,
        "1000": 59,
        "1200": 91,
        "1500": 100,
    }
    assert model_power_watts("A II", "1201") == 58


def test_detect_model_resolves_product_specific_power() -> None:
    """Known BLE product codes select their size-specific manufacturer power."""
    expected = {
        "DYZSD001122334455": 6,
        "DYDD001122334455": 10,
        "DYNW30001122334455": 33,
        "DYNW12P001122334455": 130,
        "DYWPRO60001122334455": 74,
        "DYSL90001122334455": 69,
        "DYNC2N001122334455": 16,
        "DYNCRGB001122334455": 20,
        "DYU550001122334455": 28,
        "DYU1500001122334455": 100,
    }
    assert {device_name: detect_model(device_name).max_power_watts for device_name in expected} == expected


def test_detect_model_matches_legacy_wrgb_prefix() -> None:
    """Model detection matches the legacy WRGB prefix from app templates."""
    assert detect_model("DYWRGB1234567890").name == "WRGB II"


def test_detect_model_matches_esphome_wrgb_prefix() -> None:
    """Model detection matches the WRGB prefix observed in the ESPHome bridge."""
    assert detect_model("DYNT901234567890").name == "WRGB II"


def test_detect_model_does_not_rely_on_fixed_slicing() -> None:
    """Model detection works without fixed suffix slicing."""
    assert detect_model("DYSL120-short").name == "WRGB II Slim"


def test_detect_model_matches_dosing_pump_prefix() -> None:
    """Model detection matches dosing pump advertisements."""
    assert detect_model("DYDOSE1234567890").name == "Dosing Pump"


def test_unknown_model_needs_device_type() -> None:
    """Unknown models use fallback metadata and need a type."""
    assert detect_model("UNKNOWN").fallback is True
    assert needs_device_type("UNKNOWN") is True


def test_commander_model_needs_device_type() -> None:
    """Commander devices need a user-selected generic type."""
    assert needs_device_type("DYCOM123456789") is True


def test_resolve_fallback_device_type() -> None:
    """Fallback models resolve to a generic device type."""
    model = resolve_model("UNKNOWN", FALLBACK, "rgb")

    assert model.name == "Generic RGB"
    assert dict(model.color_channels) == {"red": 0, "green": 1, "blue": 2}


def test_factory_created_device_uses_generic_wrgb_model() -> None:
    """Factory-created devices expose generic WRGB metadata."""

    async def create() -> tuple[str, dict[str, int]]:
        device = create_device(FakeBLEDevice("UNKNOWN"), device_type="wrgb")  # type: ignore[arg-type]
        return device.model_name, device.colors

    model_name, colors = asyncio.run(create())

    assert model_name == "Generic WRGB"
    assert colors == {"white": 3, "red": 0, "green": 1, "blue": 2}


def test_factory_created_dosing_pump_uses_dosing_client() -> None:
    """Factory-created dosing pump devices use the dosing client class."""

    async def create() -> ChihirosDosingPump:
        return create_device(FakeBLEDevice("DYDOSE1234567890"))  # type: ignore[arg-type, return-value]

    device = asyncio.run(create())

    assert isinstance(device, ChihirosDosingPump)
    assert device.model_name == "Dosing Pump"
    assert device.colors == {}
