"""Namespaced persistent-storage paths shared by device plugins."""

from __future__ import annotations

import os
from pathlib import Path


def state_db_path() -> Path:
    """Return the LED Core add-on state database path."""
    configured = (os.environ.get("CHIHIROS_STATE_DB") or "").strip()
    if configured:
        return Path(configured)
    return Path("/config/.chihiros_led_core/chihiros_led_core.sqlite3")


__all__ = ["state_db_path"]
