"""Tests for shared protocol debug rendering."""

from __future__ import annotations

from chihiros_led_control.debug_output import render_raw_notifications


def test_render_raw_notifications_decodes_rx_frames() -> None:
    """Render received frames with decoded RX details."""
    frame = bytes.fromhex("5B150A00010A01FFFFFFFF002C39")

    output = render_raw_notifications(
        [frame],
        describe_rx_frame=lambda _payload: ["Laufzeitmeldung Firmware=21, Laufzeit=511 min"],
    )

    assert "RX: 5B 15 0A 00 01 0A 01 FF FF FF FF 00 2C 39" in output
    assert "[RX] Decode Message" in output
    assert "Command Print    : [91, 21, 10, 0, 1, 10, 1, 255, 255, 255, 255, 0, 44, 57]" in output
    assert "Mode             : 10" in output
    assert "Parameters       : [1, 255, 255, 255, 255, 0, 44]" in output
    assert "Bedeutung        : Laufzeitmeldung Firmware=21, Laufzeit=511 min" in output
