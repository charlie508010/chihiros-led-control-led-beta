"""Shared periodic notification polling for Chihiros device plugins."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

NOTIFICATION_POLL_INTERVAL = timedelta(minutes=15)
NOTIFICATION_POLL_GAP_SECONDS = 5.0
NOTIFICATION_POLL_LOCK = "chihiros_notification_poll_lock"
NOTIFICATION_POLL_LAST_FINISHED = "chihiros_notification_poll_last_finished"


@dataclass(slots=True)
class NotificationPollPayload:
    """Device-specific values returned by one notification request."""

    success: bool
    raw_frames: tuple[bytes, ...] = ()
    values: tuple[float, ...] = ()
    notification_count: int | None = None
    output: str = ""
    error: str = ""


@dataclass(slots=True)
class NotificationPollResult:
    """Normalized LED notification polling result."""

    address: str
    device_type: str
    mode: int
    expected_modes: tuple[int, ...]
    checked_at: datetime
    status: str
    output: str
    notifications: int
    raw_frames: tuple[bytes, ...]
    values: tuple[float, ...]
    error: str = ""


def _frame_mode(frame: bytes) -> int | None:
    return frame[5] if len(frame) > 5 and frame[0] == 0x5B else None


async def async_poll_device_notifications(
    hass: HomeAssistant,
    *,
    address: str,
    device_type: str,
    mode: int,
    expected_modes: Collection[int],
    query: Callable[[], Awaitable[NotificationPollPayload]],
) -> NotificationPollResult:
    """Run one serialized notification request and normalize its result."""
    expected = tuple(int(value) for value in expected_modes)
    lock = hass.data.setdefault(NOTIFICATION_POLL_LOCK, asyncio.Lock())
    async with lock:
        loop = asyncio.get_running_loop()
        last_finished = float(hass.data.get(NOTIFICATION_POLL_LAST_FINISHED, 0.0) or 0.0)
        remaining_gap = NOTIFICATION_POLL_GAP_SECONDS - (loop.time() - last_finished)
        if remaining_gap > 0:
            await asyncio.sleep(remaining_gap)
        checked_at = datetime.now().astimezone()
        try:
            payload = await query()
        except Exception as err:  # noqa: BLE001
            payload = NotificationPollPayload(success=False, error=str(err) or type(err).__name__)
        finally:
            hass.data[NOTIFICATION_POLL_LAST_FINISHED] = loop.time()

    matching_frames = tuple(
        frame for frame in payload.raw_frames if not expected or _frame_mode(frame) in expected
    )
    notifications = (
        max(0, int(payload.notification_count))
        if payload.notification_count is not None
        else len(matching_frames)
    )
    success = bool(payload.success)
    status = "ok" if success else "error"
    error = "" if success else (payload.error or "Keine passende Geraetemeldung empfangen")
    output = payload.output or (f"{notifications} notification(s) received" if success else error)
    return NotificationPollResult(
        address=str(address),
        device_type=str(device_type),
        mode=int(mode),
        expected_modes=expected,
        checked_at=checked_at,
        status=status,
        output=output,
        notifications=notifications,
        raw_frames=tuple(payload.raw_frames),
        values=tuple(payload.values),
        error=error,
    )


def async_track_notification_poll(
    hass: HomeAssistant,
    callback: Callable[[Any], Awaitable[None]],
) -> Callable[[], None]:
    """Register the shared 15-minute notification interval."""
    from homeassistant.helpers.event import async_track_time_interval

    return async_track_time_interval(hass, callback, NOTIFICATION_POLL_INTERVAL)
