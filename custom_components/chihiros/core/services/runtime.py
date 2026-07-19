"""Shared backend service runner helpers for device plugins."""

from __future__ import annotations

from typing import Any, Protocol

from homeassistant.core import ServiceCall


class ServiceOperation(Protocol):
    """Callable service operation used by internal packages."""

    async def __call__(self, data: dict[str, Any]) -> dict[str, Any]:
        """Run a service operation and return response details."""


def response_requested(call: ServiceCall) -> bool:
    """Return whether the Home Assistant service call requested a response."""
    return bool(getattr(call, "return_response", False))


__all__ = ["ServiceOperation", "response_requested"]
