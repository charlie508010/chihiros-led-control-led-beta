"""Home Assistant config-flow entrypoint for the LED plugin."""

from .plugins.led.config_flow import ChihirosConfigFlow

__all__ = ["ChihirosConfigFlow"]
