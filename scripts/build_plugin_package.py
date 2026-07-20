"""Build deterministic installable dashboard plugin archives."""

from __future__ import annotations

import argparse
import gzip
import io
import json
import tarfile
from pathlib import Path


def build(source: Path, output_dir: Path) -> Path:
    """Build one reproducible TGZ from a plugin source directory."""
    manifest = json.loads((source / "plugin.json").read_text(encoding="utf-8"))
    plugin_id = str(manifest["id"])
    version = str(manifest["version"])
    destination = output_dir / f"chihiros-{plugin_id}-{version}.tgz"
    output_dir.mkdir(parents=True, exist_ok=True)
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(
            item
            for item in source.rglob("*")
            if item.is_file()
            and "dist" not in item.relative_to(source).parts
            and "__pycache__" not in item.parts
            and item.suffix not in {".pyc", ".pyo"}
        ):
            relative = path.relative_to(source).as_posix()
            data = path.read_bytes()
            info = tarfile.TarInfo(relative)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(data))
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(tar_buffer.getvalue())
    return destination


def main() -> None:
    """Parse command-line arguments and build a plugin package."""
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()
    print(build(args.source, args.output_dir))


if __name__ == "__main__":
    main()
