"""Data types for the optional Doser plugin."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DoserSchedule:
    """One local dosing-pump schedule row."""

    pump_idx: int
    active: bool
    time: str
    ml: float
    weekdays: tuple[str, ...] = ("everyday",)
    kind: str = "single_dose"
    interval_minutes: int | None = None
    timer_entries: tuple[tuple[str, float], ...] = ()
    window_entries: tuple[tuple[str, str, int], ...] = ()
    schedule_type_id: int | None = None
    valid_from_tomorrow: bool = False
