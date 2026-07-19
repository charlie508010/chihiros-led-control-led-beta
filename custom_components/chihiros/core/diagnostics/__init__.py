"""Shared protocol diagnostics exposed to device plugins."""

from .schema import (
    build_debug_sections,
    make_debug_data,
    make_service_result,
    normalize_protocol_debug_text,
    render_debug_text,
)

__all__ = [
    "build_debug_sections",
    "make_debug_data",
    "make_service_result",
    "normalize_protocol_debug_text",
    "render_debug_text",
]
