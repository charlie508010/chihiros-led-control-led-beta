#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    source = Path("/opt/chihiros-led-core-src")
    src = source / "src"
    vendor = source / "custom_components" / "chihiros" / "vendor"
    for path in (str(src), str(vendor), str(source)):
        if path not in sys.path:
            sys.path.insert(0, path)

    sys.argv[0] = "chihirosctl"
    if (src / "chihiros_led_control" / "led_cli.py").is_file():
        runpy.run_module("chihiros_led_control.led_cli", run_name="__main__")
        return

    print("No LED-only chihirosctl entrypoint found in /opt/chihiros-led-core-src.")
    raise SystemExit(2)


if __name__ == "__main__":
    main()
