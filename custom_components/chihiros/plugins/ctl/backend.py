"""Backend helpers for the bundled CTL dashboard plugin."""

from __future__ import annotations

import os
import shlex
import subprocess


def run_command(command: str) -> dict[str, object]:
    """Run one allowed chihirosctl command and return process output."""
    command_text = str(command or "").strip()
    if not command_text.startswith("chihirosctl "):
        raise ValueError("Only chihirosctl commands are allowed")
    if any(token in command_text for token in [";", "&", "|", "`", "$(", ">", "<"]):
        raise ValueError("Shell operators are not allowed")

    parts = shlex.split(command_text)
    result = subprocess.run(
        parts,
        cwd="/opt/chihiros-src",
        env={
            **os.environ,
            "PYTHONPATH": "/opt/chihiros-src/src:/opt/chihiros-src/custom_components/chihiros/vendor:/opt/chihiros-src",
        },
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    return {
        "returncode": result.returncode,
        "output": output or "(no output)",
    }


def run_ctl_command(command: str) -> dict[str, object]:
    """Run one CTL command for the dashboard backend."""
    return run_command(command)
