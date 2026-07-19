"""Runtime interfaces owned by the optional Doser plugin."""

from __future__ import annotations

from datetime import time
from typing import Protocol


class DosingChihirosClient(Protocol):
    """Doser-facing BLE client surface required by the plugin."""

    raw_notifications: list[bytes]
    last_doser_totals: list[float] | None

    async def dose_ml(self, pump_idx: int, volume_ml: float) -> None:
        """Dose a volume on one pump channel."""

    async def add_schedule(
        self,
        pump_idx: int,
        schedule_time: time,
        dose_ml: float,
        weekdays_mask: int = 0x7F,
        active: bool = True,
        next_day_flag: bool = False,
    ) -> None:
        """Program one single-dose schedule."""

    async def add_interval_schedule(
        self,
        pump_idx: int,
        interval_minutes: int,
        dose_ml: float,
        weekdays_mask: int = 0x7F,
        active: bool = True,
        next_day_flag: bool = False,
    ) -> None:
        """Program one interval schedule."""

    async def read_auto_totals(self, mode: int = 0x34, *, clear_notifications: bool = True) -> list[float] | None:
        """Read automatic daily totals directly."""

    async def read_auto_totals_via_dialog(
        self,
        mode: int = 0x22,
        *,
        clear_notifications: bool = True,
    ) -> list[float] | None:
        """Read automatic daily totals using the Doser dialog sequence."""

    async def read_doser_notifications(self, notification_wait: float = 5.0) -> None:
        """Collect the complete Doser notification burst."""
