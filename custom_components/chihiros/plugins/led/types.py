"""Typing helpers for the LED plugin."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

from .models import ChihirosData

ResolveDevice: TypeAlias = Callable[[dict[str, Any]], ChihirosData]

__all__ = ["ResolveDevice"]
