"""Shared Home Assistant service contracts for device plugins."""

from .runtime import ServiceOperation, response_requested

__all__ = ["ServiceOperation", "response_requested"]
