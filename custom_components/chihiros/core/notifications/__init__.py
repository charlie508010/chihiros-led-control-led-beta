"""Shared notification polling and dispatch contracts for plugins."""

from .runtime import (
    NOTIFICATION_POLL_GAP_SECONDS,
    NOTIFICATION_POLL_INTERVAL,
    NOTIFICATION_POLL_LAST_FINISHED,
    NOTIFICATION_POLL_LOCK,
    NotificationPollPayload,
    NotificationPollResult,
    async_poll_device_notifications,
    async_track_notification_poll,
)

__all__ = [
    "NOTIFICATION_POLL_GAP_SECONDS",
    "NOTIFICATION_POLL_INTERVAL",
    "NOTIFICATION_POLL_LAST_FINISHED",
    "NOTIFICATION_POLL_LOCK",
    "NotificationPollPayload",
    "NotificationPollResult",
    "async_poll_device_notifications",
    "async_track_notification_poll",
]
