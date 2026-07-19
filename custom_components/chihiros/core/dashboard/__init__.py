"""Dashboard metadata shared between Core and device plugins."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PluginTab:
    """One dashboard tab contributed by a device plugin."""

    tab_id: str
    title: str
    icon: str = ""


__all__ = ["PluginTab"]
