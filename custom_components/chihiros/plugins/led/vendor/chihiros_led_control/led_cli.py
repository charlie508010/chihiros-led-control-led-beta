"""LED-only command-line entrypoint."""

from __future__ import annotations

import typer
from typing_extensions import Annotated

from . import cli as shared_cli

app = typer.Typer(help="Chihiros LED control")
app.add_typer(shared_cli.led_app, name="led")
app.add_typer(shared_cli.template_app, name="template")


@app.callback()
def main(
    debug: Annotated[bool, typer.Option("--debug", help="Debug-Ausgabe aktivieren")] = False,
) -> None:
    """Control Chihiros LED devices."""
    shared_cli.DEBUG_ENABLED = debug
    if debug:
        shared_cli._enable_compact_debug_logging()


if __name__ == "__main__":
    app()
