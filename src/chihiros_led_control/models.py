"""Device model registry for Chihiros LEDs."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class DeviceModel:
    """Static metadata for a Chihiros LED model."""

    name: str
    advertised_codes: tuple[str, ...]
    color_channels: Mapping[str, int]
    max_brightness: int = 100
    needs_device_type: bool = False
    fallback: bool = False
    schedule_reset_parameter: int = 5
    schedule_reset_from_snapshot: bool = False
    max_power_watts: float | None = None
    has_fan: bool = False


WHITE_CHANNELS = MappingProxyType({"white": 0})
RGB_CHANNELS = MappingProxyType({"red": 0, "green": 1, "blue": 2})
WRGB_CHANNELS = MappingProxyType({"white": 3, "red": 0, "green": 1, "blue": 2})
COMMANDER_CHANNELS = MappingProxyType({"white": 0, "red": 0, "green": 1, "blue": 2})
TINY_TERRARIUM_EGG_CHANNELS = MappingProxyType({"red": 0, "green": 1})
Z_LIGHT_TINY_CHANNELS = MappingProxyType({"white": 0, "warm": 1})

MODEL_POWER_WATTS: Mapping[str, Mapping[str, float]] = MappingProxyType(
    {
        "Z Light TINY": MappingProxyType({"default": 6}),
        "Tiny Terrarium Egg": MappingProxyType({"default": 10}),
        "A II": MappingProxyType(
            {
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
        ),
        "WRGB II": MappingProxyType({"30": 33, "45": 49, "60": 67, "90": 100, "120": 130}),
        "WRGB II Pro": MappingProxyType({"30": 37, "45": 56, "60": 74, "80": 100, "90": 110, "120": 138}),
        "WRGB II Slim": MappingProxyType({"30": 23, "45": 35, "60": 45, "90": 69, "120": 90}),
        "C II": MappingProxyType({"default": 16}),
        "C II RGB": MappingProxyType({"default": 20}),
        "Universal WRGB": MappingProxyType(
            {"550": 28, "600": 29, "700": 33, "800": 36, "920": 55, "1000": 59, "1200": 91, "1500": 100}
        ),
    }
)

# Source metadata is kept next to the values so UI and documentation changes cannot silently turn an estimate into a
# manufacturer specification. ``official_product_page`` means the model/size table was checked against Chihiros' own
# product material; ``empirical`` is deliberately limited to the locally measured Universal WRGB profile.
MODEL_POWER_SOURCES: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "Z Light TINY": MappingProxyType(
            {
                "status": "official_product_page",
                "url": "https://www.chihirosaquaticstudio.com/products/chihiros-z-light-tiny-led-light",
            }
        ),
        "Tiny Terrarium Egg": MappingProxyType(
            {
                "status": "official_product_page",
                "url": "https://www.chihirosaquaticstudio.com/products/chihiros-tiny-terrarium-egg",
            }
        ),
        "A II": MappingProxyType(
            {
                "status": "official_product_page",
                "url": "https://www.chihirosaquaticstudio.com/products/chihiros-a-ii-led-light",
            }
        ),
        "WRGB II": MappingProxyType(
            {
                "status": "official_product_page",
                "url": "https://www.chihirosaquaticstudio.com/products/chihiros-wrgb-ii-led-light",
            }
        ),
        "WRGB II Pro": MappingProxyType(
            {
                "status": "official_product_page",
                "url": "https://www.chihirosaquaticstudio.com/products/chihiros-wrgb-ii-pro-led-light",
            }
        ),
        "WRGB II Slim": MappingProxyType(
            {
                "status": "official_product_page",
                "url": "https://www.chihirosaquaticstudio.com/products/chihiros-wrgb-ii-slim-led-light",
            }
        ),
        "C II": MappingProxyType(
            {
                "status": "official_product_page",
                "url": "https://www.chihirosaquaticstudio.com/products/chihiros-c-ii-led-light",
            }
        ),
        "C II RGB": MappingProxyType(
            {
                "status": "official_product_page",
                "url": "https://www.chihirosaquaticstudio.com/products/chihiros-c-ii-rgb-led-light",
            }
        ),
        "Universal WRGB": MappingProxyType({"status": "empirical", "url": ""}),
    }
)

MODEL_CODE_POWER_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "DYSSD": "default",
        "DYZSD": "default",
        "DYDD": "default",
        "DYNT90": "90",
        "DYNW30": "30",
        "DYNW45": "45",
        "DYNW60": "60",
        "DYNW90": "90",
        "DYNW12P": "120",
        "DYWPRO30": "30",
        "DYWPRO45": "45",
        "DYWPRO60": "60",
        "DYWPRO80": "80",
        "DYWPRO90": "90",
        "DYWPR120": "120",
        "DYSL30": "30",
        "DYSL45": "45",
        "DYSL60": "60",
        "DYSL90": "90",
        "DYSL120": "120",
        "DYSL12": "120",
        "DYNC2N": "default",
        "DYNCRGP": "default",
        "DYNCRGB": "default",
        "DYU550": "550",
        "DYU600": "600",
        "DYU700": "700",
        "DYU800": "800",
        "DYU920": "920",
        "DYU1000": "1000",
        "DYU1200": "1200",
        "DYU1500": "1500",
    }
)


def model_power_watts(model_name: str, product_key: str = "default") -> float | None:
    """Return configured manufacturer power for one model/product size."""
    value = MODEL_POWER_WATTS.get(model_name, {}).get(str(product_key))
    return None if value is None else float(value)


def model_power_watts_for_code(model_name: str, advertised_code: str) -> float | None:
    """Resolve manufacturer power from a known BLE advertised product code."""
    product_key = MODEL_CODE_POWER_KEYS.get(advertised_code)
    return None if product_key is None else model_power_watts(model_name, product_key)


GENERIC_WHITE = DeviceModel("Generic White LED", (), WHITE_CHANNELS)
GENERIC_RGB = DeviceModel("Generic RGB", (), RGB_CHANNELS)
GENERIC_WRGB = DeviceModel("Generic WRGB", (), WRGB_CHANNELS)
FALLBACK = DeviceModel("fallback", (), COMMANDER_CHANNELS, needs_device_type=True, fallback=True)

SUPPORTED_MODELS: tuple[DeviceModel, ...] = (
    DeviceModel("Z Light TINY", ("DYSSD", "DYZSD"), Z_LIGHT_TINY_CHANNELS),
    DeviceModel("Tiny Terrarium Egg", ("DYDD",), TINY_TERRARIUM_EGG_CHANNELS),
    DeviceModel("A II", ("DYNA2", "DYNA2N"), WHITE_CHANNELS),
    DeviceModel(
        "WRGB II",
        ("DYNT90", "DYWRGB", "DYNWRGB", "DYNW30", "DYNW45", "DYNW60", "DYNW90", "DYNW12P"),
        RGB_CHANNELS,
    ),
    DeviceModel(
        "WRGB II Pro",
        ("DYWPRO30", "DYWPRO45", "DYWPRO60", "DYWPRO80", "DYWPRO90", "DYWPR120"),
        WRGB_CHANNELS,
    ),
    DeviceModel(
        "WRGB II Slim",
        ("DYSILN", "DYSL30", "DYSL45", "DYSL60", "DYSL90", "DYSL120", "DYSL12"),
        RGB_CHANNELS,
    ),
    DeviceModel("WRGB VIVID III", ("DYVVD3",), WRGB_CHANNELS, has_fan=True),
    DeviceModel("C II", ("DYNC2N",), WHITE_CHANNELS),
    DeviceModel("C II RGB", ("DYNCRGP", "DYNCRGB"), RGB_CHANNELS),
    DeviceModel(
        "Universal WRGB",
        ("DYU1000",),
        WRGB_CHANNELS,
        max_brightness=100,
        schedule_reset_parameter=40,
        schedule_reset_from_snapshot=True,
    ),
    DeviceModel(
        "Universal WRGB",
        (
            "DYU550",
            "DYU600",
            "DYU700",
            "DYU800",
            "DYU920",
            "DYU1200",
            "DYU1500",
        ),
        WRGB_CHANNELS,
    ),
    DeviceModel("Commander 1", ("DYCOM",), COMMANDER_CHANNELS, needs_device_type=True),
    DeviceModel("Commander 4", ("DYLED",), COMMANDER_CHANNELS, needs_device_type=True),
)

GENERIC_MODELS_BY_DEVICE_TYPE = MappingProxyType(
    {
        "white": GENERIC_WHITE,
        "rgb": GENERIC_RGB,
        "wrgb": GENERIC_WRGB,
    }
)

MODEL_BY_CODE = MappingProxyType({code: model for model in SUPPORTED_MODELS for code in model.advertised_codes})


def iter_model_codes_by_specificity() -> tuple[tuple[str, DeviceModel], ...]:
    """Return model codes sorted so longer prefixes win."""
    return tuple(
        sorted(
            MODEL_BY_CODE.items(),
            key=lambda code_model: len(code_model[0]),
            reverse=True,
        )
    )
