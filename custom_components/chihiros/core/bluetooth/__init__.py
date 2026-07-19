"""Shared Bluetooth primitives for Chihiros device plugins."""

from __future__ import annotations

import asyncio


class DeviceOperationLocks:
    """Provide one shared asynchronous operation lock per normalized MAC address."""

    def __init__(self) -> None:
        """Initialize an empty lock registry."""
        self._locks: dict[str, asyncio.Lock] = {}

    def for_address(self, address: str) -> asyncio.Lock:
        """Return the stable lock assigned to one Bluetooth address."""
        key = normalize_address(address)
        return self._locks.setdefault(key, asyncio.Lock())


def normalize_address(address: str) -> str:
    """Normalize a Bluetooth address for shared registries and storage."""
    return str(address or "").strip().upper().replace("-", ":")


__all__ = ["DeviceOperationLocks", "normalize_address"]
