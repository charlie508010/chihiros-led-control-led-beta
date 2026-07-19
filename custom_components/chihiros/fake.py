"""Compatibility exports for LED development devices."""

from .plugins.led.testing.fake import (
    FAKE_ADDRESS_PREFIX,
    FAKE_DEVICES,
    FAKE_DEVICES_BY_ADDRESS,
    FAKE_DEVICES_ENV,
    FakeChihirosDevice,
    FakeChihirosDeviceInfo,
    create_fake_device,
    fake_devices_enabled,
    is_fake_address,
    iter_enabled_fake_devices,
)

__all__ = [
    "FAKE_ADDRESS_PREFIX",
    "FAKE_DEVICES",
    "FAKE_DEVICES_BY_ADDRESS",
    "FAKE_DEVICES_ENV",
    "FakeChihirosDevice",
    "FakeChihirosDeviceInfo",
    "create_fake_device",
    "fake_devices_enabled",
    "is_fake_address",
    "iter_enabled_fake_devices",
]
