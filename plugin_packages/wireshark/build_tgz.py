"""Build the standalone Wireshark dashboard plugin TGZ reproducibly."""

from __future__ import annotations

import gzip
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    """Build the installable archive into ``dist``."""
    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    version = str(manifest["version"])
    destination = ROOT / "dist" / f"chihiros-wireshark-{version}.tgz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and "dist" not in path.relative_to(ROOT).parts
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in files:
            data = path.read_bytes()
            info = tarfile.TarInfo(path.relative_to(ROOT).as_posix())
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(data))
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(tar_buffer.getvalue())
    print(destination)


if __name__ == "__main__":
    main()
