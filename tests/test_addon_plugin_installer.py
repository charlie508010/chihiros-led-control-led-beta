"""Security and lifecycle tests for add-on TGZ plugins."""

from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("test_addon_server", ROOT / "chihiros_beta/ui/server.py")
assert SPEC and SPEC.loader
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


def archive(files: dict[str, bytes], *, symlink: str = "") -> bytes:
    """Build a small in-memory gzip tar archive."""
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as bundle:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            bundle.addfile(info, io.BytesIO(content))
        if symlink:
            info = tarfile.TarInfo(symlink)
            info.type = tarfile.SYMTYPE
            info.linkname = "plugin.json"
            bundle.addfile(info)
    return output.getvalue()


def manifest(version: str = "1.0.0") -> bytes:
    """Return an allowlisted test plugin manifest."""
    return json.dumps(
        {
            "id": "sample",
            "name": "Sample",
            "version": version,
            "runtimes": ["addon"],
            "frontend": "www/plugin.js",
            "backend_entrypoint": "backend.py",
            "backend_actions": ["ping"],
            "tabs": [{"id": "sample", "title": "Sample"}],
        }
    ).encode()


@pytest.fixture
def plugin_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep installer writes inside a temporary directory."""
    external = tmp_path / "plugins"
    monkeypatch.setattr(server, "EXTERNAL_PLUGIN_ROOT", external)
    monkeypatch.setattr(server, "PLUGIN_BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.setattr(server, "PLUGIN_STAGING_ROOT", tmp_path / "staging")
    monkeypatch.setattr(server, "PLUGIN_QUARANTINE_ROOT", tmp_path / "quarantine")
    monkeypatch.setattr(server, "STARTUP_EXTERNAL_PLUGIN_IDS", frozenset())
    server._PLUGIN_BACKEND_CACHE.clear()
    return external


def test_install_and_update_retains_dated_backup(plugin_roots: Path) -> None:
    """An update publishes the new version and moves the previous version to backups."""
    files = {"plugin.json": manifest(), "www/plugin.js": b"export {};", "backend.py": b"def ping(): return 'v1'\n"}
    first = server.install_plugin_tgz(archive(files))
    assert first["restart_required"] is True
    assert first["backup"] == ""
    files["plugin.json"] = manifest("2.0.0")
    files["backend.py"] = b"def ping(): return 'v2'\n"
    second = server.install_plugin_tgz(archive(files))
    backup = Path(str(second["backup"]))
    assert backup.is_dir()
    assert (backup / "backend.py").read_text() == "def ping(): return 'v1'\n"
    assert (plugin_roots / "sample" / "backend.py").read_text() == "def ping(): return 'v2'\n"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "folder/../../escape"])
def test_install_rejects_path_traversal(plugin_roots: Path, name: str) -> None:
    """Absolute and parent paths never reach the plugin directory."""
    with pytest.raises(ValueError, match="Unsafe"):
        server.install_plugin_tgz(archive({"plugin.json": manifest(), name: b"bad"}))
    assert not plugin_roots.exists()


def test_install_rejects_links(plugin_roots: Path) -> None:
    """Symlinks and hardlink-like archive entries are rejected."""
    with pytest.raises(ValueError, match="Unsupported"):
        server.install_plugin_tgz(archive({"plugin.json": manifest()}, symlink="www/plugin.js"))
    assert not plugin_roots.exists()


def test_install_rejects_unpacked_size_limit(plugin_roots: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The aggregate uncompressed-size guard runs before staging."""
    monkeypatch.setattr(server, "MAX_PLUGIN_UNPACKED_BYTES", 10)
    with pytest.raises(ValueError, match="unpacked limit"):
        server.install_plugin_tgz(archive({"plugin.json": manifest()}))
    assert not plugin_roots.exists()


def test_backend_uses_manifest_allowlist(plugin_roots: Path) -> None:
    """Only named backend functions can be dispatched."""
    files = {
        "plugin.json": manifest(),
        "www/plugin.js": b"export {};",
        "backend.py": b"def ping(): return {'ok': True}\ndef hidden(): return {'bad': True}\n",
    }
    server.install_plugin_tgz(archive(files))
    assert "sample" not in server.installed_plugin_kinds()
    server.STARTUP_EXTERNAL_PLUGIN_IDS = frozenset({"sample"})
    assert "sample" in server.plugin_tabs()
    assert server.call_plugin_backend("sample", "ping", []) == {"ok": True}
    with pytest.raises(ValueError, match="not allowed"):
        server.call_plugin_backend("sample", "hidden", [])
