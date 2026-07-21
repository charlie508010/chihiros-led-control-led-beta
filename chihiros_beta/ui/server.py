#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
import mimetypes
import os
import re
import shlex
import sqlite3
import subprocess
import tarfile
import threading
import time
from datetime import datetime, timedelta, timezone
from datetime import time as datetime_time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib import error, request
from urllib.parse import parse_qs, quote, unquote, urlparse


def _load_normalize_protocol_debug_text():
    source_root = Path(os.environ.get("CHIHIROS_SOURCE_ROOT", "/opt/chihiros-led-core-src"))
    candidates = [
        Path(__file__).resolve().parents[2] / "custom_components" / "chihiros" / "debug_schema.py",
        source_root / "custom_components" / "chihiros" / "debug_schema.py",
    ]
    for debug_schema_path in candidates:
        if not debug_schema_path.exists():
            continue
        try:
            spec = importlib.util.spec_from_file_location("chihiros_addon_debug_schema", debug_schema_path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            normalizer = getattr(module, "normalize_protocol_debug_text", None)
            if callable(normalizer):
                return normalizer
        except Exception:
            continue
    return None


_normalize_protocol_debug_text = _load_normalize_protocol_debug_text()
LED_STATUS_WAKE_EVENT = threading.Event()


def normalize_protocol_debug_text(value: str) -> str:
    if callable(_normalize_protocol_debug_text):
        try:
            return str(_normalize_protocol_debug_text(value) or "").strip()
        except Exception:
            pass
    return str(value or "").strip()


ROOT = Path("/opt/chihiros-led-core-ui")
SOURCE_ROOT = Path(os.environ.get("CHIHIROS_SOURCE_ROOT", "/opt/chihiros-led-core-src"))
CONFIG_ROOT = Path(os.environ.get("HASS_CONFIG", "/config"))
DEFAULT_STATE_DB_PATH = Path(
    os.environ.get("CHIHIROS_STATE_DB", str(CONFIG_ROOT / ".chihiros_led_core" / "chihiros_led_core.sqlite3"))
)
HA_STORAGE = CONFIG_ROOT / ".storage"
SETTINGS_PATH = Path(os.environ.get("CHIHIROS_DASHBOARD_SETTINGS", "/data/dashboard_settings.json"))
CORE_TABS = ["led", "config"]
DEFAULT_DIAGNOSTIC_RETENTION_DAYS = 0
EXTERNAL_PLUGIN_ROOT = CONFIG_ROOT / ".chihiros_led_core" / "plugins"
PLUGIN_BACKUP_ROOT = CONFIG_ROOT / ".chihiros_led_core" / "plugin_backups"
PLUGIN_STAGING_ROOT = CONFIG_ROOT / ".chihiros_led_core" / "plugin_staging"
PLUGIN_QUARANTINE_ROOT = CONFIG_ROOT / ".chihiros_led_core" / "plugin_quarantine"
MAX_PLUGIN_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_PLUGIN_UNPACKED_BYTES = 50 * 1024 * 1024
MAX_PLUGIN_FILES = 512
_PLUGIN_BACKEND_CACHE: dict[str, object] = {}
STARTUP_EXTERNAL_PLUGIN_IDS = (
    frozenset(path.parent.name for path in EXTERNAL_PLUGIN_ROOT.glob("*/plugin.json"))
    if EXTERNAL_PLUGIN_ROOT.is_dir()
    else frozenset()
)


def plugin_manifest_rows() -> list[dict[str, object]]:
    """Return validated metadata for packaged and configuration-local plugins."""
    roots = (
        Path(__file__).resolve().parents[2] / "custom_components" / "chihiros" / "plugins",
        SOURCE_ROOT / "custom_components" / "chihiros" / "plugins",
        EXTERNAL_PLUGIN_ROOT,
    )
    plugins: dict[str, dict[str, object]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*/plugin.json")):
            if root == EXTERNAL_PLUGIN_ROOT and path.parent.name not in STARTUP_EXTERNAL_PLUGIN_IDS:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            plugin_id = str(data.get("id") or "").strip()
            if not re.fullmatch(r"[a-z][a-z0-9_]*", plugin_id) or plugin_id in plugins:
                continue
            runtimes = data.get("runtimes", ["home_assistant", "addon"])
            if not isinstance(runtimes, list) or "addon" not in runtimes:
                continue
            try:
                frontend = _safe_plugin_relative_path(data.get("frontend"), allow_empty=True)
                backend_entrypoint = _safe_plugin_relative_path(data.get("backend_entrypoint"), allow_empty=True)
            except ValueError:
                continue
            backend_actions = [
                str(action)
                for action in data.get("backend_actions", [])
                if re.fullmatch(r"[a-z][a-z0-9_]*", str(action))
            ]
            tabs = [
                {
                    "id": str(tab.get("id") or "").strip(),
                    "title": str(tab.get("title") or tab.get("id") or "").strip(),
                    "icon": str(tab.get("icon") or "").strip(),
                }
                for tab in data.get("tabs", [])
                if isinstance(tab, dict) and re.fullmatch(r"[a-z][a-z0-9_]*", str(tab.get("id") or "").strip())
            ]
            plugins[plugin_id] = {
                "id": plugin_id,
                "name": str(data.get("name") or plugin_id),
                "version": str(data.get("version") or "0.0.0"),
                "requires_core": str(data.get("requires_core") or ""),
                "frontend": frontend,
                "module": f"./plugins/{plugin_id}/{frontend}" if frontend else "",
                "backend_entrypoint": backend_entrypoint,
                "backend_actions": backend_actions,
                "runtimes": runtimes,
                "tabs": tabs or [{"id": plugin_id, "title": plugin_id, "icon": ""}],
                "_root": str(path.parent.resolve()),
            }
    return [plugins[key] for key in sorted(plugins)]


def plugin_kind() -> str:
    """Return the fixed add-on kind for the separated LED repository."""
    return "core"


def plugin_tabs() -> list[str]:
    """Return installed plugin tabs followed by the Core configuration tab."""
    tabs = [
        str(tab.get("id") or "")
        for plugin in plugin_manifest_rows()
        for tab in plugin.get("tabs", [])
        if isinstance(tab, dict)
    ]
    tabs = list(dict.fromkeys(tab for tab in tabs if tab))
    if "led" not in tabs:
        tabs.insert(0, "led")
    if "config" not in tabs:
        tabs.append("config")
    return tabs


def installed_plugin_kinds() -> list[str]:
    """Return ids of all discovered plugins."""
    return [str(plugin["id"]) for plugin in plugin_manifest_rows()]


def plugin_assets() -> dict[str, dict[str, object]]:
    """Return public plugin metadata used by the dashboard shell."""
    return {
        str(plugin["id"]): {key: value for key, value in plugin.items() if not key.startswith("_")}
        for plugin in plugin_manifest_rows()
    }


def _safe_plugin_relative_path(value: object, *, allow_empty: bool = False) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text and allow_empty:
        return ""
    candidate = Path(text)
    if not text or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Invalid plugin path: {text!r}")
    return text


def _plugin_manifest(plugin_id: str) -> dict[str, object]:
    for plugin in plugin_manifest_rows():
        if plugin.get("id") == plugin_id:
            return plugin
    raise ValueError(f"Plugin not installed: {plugin_id}")


def call_plugin_backend(plugin_id: str, action: str, args: list[object]) -> object:
    """Call one explicitly allowlisted action from an installed add-on plugin."""
    plugin = _plugin_manifest(plugin_id)
    if action not in plugin.get("backend_actions", []):
        raise ValueError(f"Plugin action not allowed: {plugin_id}.{action}")
    backend_entrypoint = str(plugin.get("backend_entrypoint") or "")
    if not backend_entrypoint:
        raise ValueError(f"Plugin has no backend: {plugin_id}")
    root = Path(str(plugin["_root"])).resolve()
    backend_path = (root / backend_entrypoint).resolve()
    if root not in backend_path.parents or not backend_path.is_file():
        raise ValueError(f"Plugin backend not found: {plugin_id}")
    module = _PLUGIN_BACKEND_CACHE.get(plugin_id)
    if module is None:
        spec = importlib.util.spec_from_file_location(f"chihiros_addon_plugin_{plugin_id}", backend_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Plugin backend cannot be loaded: {plugin_id}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _PLUGIN_BACKEND_CACHE[plugin_id] = module
    function = getattr(module, action, None)
    if not callable(function):
        raise ValueError(f"Plugin action missing: {plugin_id}.{action}")
    return function(*args)


def install_plugin_tgz(payload: bytes) -> dict[str, object]:
    """Install a validated TGZ without deleting an existing or rejected plugin."""
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    files: list[tuple[PurePosixPath, bytes]] = []
    seen: set[str] = set()
    total_size = 0
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) > MAX_PLUGIN_FILES:
            raise ValueError(f"Plugin archive contains more than {MAX_PLUGIN_FILES} entries")
        for member in members:
            name = member.name.replace("\\", "/").removeprefix("./")
            relative = PurePosixPath(name)
            if not name or relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe plugin archive path: {member.name}")
            normalized = relative.as_posix()
            if normalized in seen:
                raise ValueError(f"Duplicate plugin archive path: {normalized}")
            seen.add(normalized)
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError(f"Unsupported plugin archive entry: {normalized}")
            total_size += member.size
            if total_size > MAX_PLUGIN_UNPACKED_BYTES:
                raise ValueError("Plugin archive exceeds the 50 MiB unpacked limit")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"Plugin archive entry cannot be read: {normalized}")
            files.append((relative, extracted.read()))
    manifest_payload = next((content for path, content in files if path.as_posix() == "plugin.json"), None)
    if manifest_payload is None:
        raise ValueError("Plugin archive must contain plugin.json at its root")
    try:
        manifest = json.loads(manifest_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ValueError("Plugin manifest is not valid UTF-8 JSON") from err
    if not isinstance(manifest, dict):
        raise ValueError("Plugin manifest must contain an object")
    plugin_id = str(manifest.get("id") or "").strip()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", plugin_id) or plugin_id in {"led", "config"}:
        raise ValueError(f"Invalid or reserved plugin id: {plugin_id!r}")
    runtimes = manifest.get("runtimes")
    if not isinstance(runtimes, list) or "addon" not in runtimes:
        raise ValueError("Uploaded plugins must declare the addon runtime")
    requires_core = str(manifest.get("requires_core") or "").strip()
    if len(requires_core) > 64 or not re.fullmatch(r"[0-9A-Za-z.*+<>=!~^, -]*", requires_core):
        raise ValueError("Plugin requires_core is invalid")
    frontend = _safe_plugin_relative_path(manifest.get("frontend"), allow_empty=True)
    backend = _safe_plugin_relative_path(manifest.get("backend_entrypoint"), allow_empty=True)
    actions = manifest.get("backend_actions", [])
    if not isinstance(actions, list) or any(not re.fullmatch(r"[a-z][a-z0-9_]*", str(item)) for item in actions):
        raise ValueError("Plugin backend_actions must contain safe action names")
    available = {path.as_posix() for path, _content in files}
    if frontend and frontend not in available:
        raise ValueError(f"Plugin frontend not found in archive: {frontend}")
    if backend and backend not in available:
        raise ValueError(f"Plugin backend not found in archive: {backend}")

    PLUGIN_STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    stage = PLUGIN_STAGING_ROOT / f"{plugin_id}-{timestamp}"
    stage.mkdir(parents=False, exist_ok=False)
    try:
        for relative, content in files:
            target = stage.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        EXTERNAL_PLUGIN_ROOT.mkdir(parents=True, exist_ok=True)
        target = EXTERNAL_PLUGIN_ROOT / plugin_id
        backup_path: Path | None = None
        if target.exists():
            PLUGIN_BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
            backup_path = PLUGIN_BACKUP_ROOT / f"{plugin_id}-{timestamp}"
            target.replace(backup_path)
        try:
            stage.replace(target)
        except OSError:
            if backup_path is not None and backup_path.exists() and not target.exists():
                backup_path.replace(target)
            raise
    except Exception:
        if stage.exists():
            PLUGIN_QUARANTINE_ROOT.mkdir(parents=True, exist_ok=True)
            stage.replace(PLUGIN_QUARANTINE_ROOT / stage.name)
        raise
    _PLUGIN_BACKEND_CACHE.pop(plugin_id, None)
    return {
        "ok": True,
        "plugin": plugin_id,
        "version": str(manifest.get("version") or "0.0.0"),
        "backup": str(backup_path) if backup_path is not None else "",
        "restart_required": True,
    }


def uninstall_plugin(plugin_id: str) -> dict[str, object]:
    """Deactivate an external plugin by moving it to a dated, recoverable backup."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", plugin_id) or plugin_id in {"led", "config"}:
        raise ValueError(f"Invalid or reserved plugin id: {plugin_id!r}")
    target = (EXTERNAL_PLUGIN_ROOT / plugin_id).resolve()
    external_root = EXTERNAL_PLUGIN_ROOT.resolve()
    if external_root not in target.parents or not target.is_dir():
        raise ValueError(f"External plugin not installed: {plugin_id}")
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    PLUGIN_BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    backup_path = PLUGIN_BACKUP_ROOT / f"{plugin_id}-{timestamp}-uninstalled"
    target.replace(backup_path)
    _PLUGIN_BACKEND_CACHE.pop(plugin_id, None)
    return {
        "ok": True,
        "plugin": plugin_id,
        "backup": str(backup_path),
        "restart_required": True,
    }


def addon_info_is_installed(data: dict[str, object]) -> bool:
    """Return true only for add-ons installed on this Home Assistant host."""
    if data.get("installed") is True:
        return True
    state = str(data.get("state") or "").strip().lower()
    if state in {"started", "stopped", "startup", "shutdown", "error"}:
        return True
    return bool(data.get("version")) and bool(data.get("options"))


def plugin_title() -> str:
    """Return the display title for this LED add-on."""
    return "LED Core"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        request_path = f"/{parsed.path.lstrip('/')}"
        if request_path == "/api/status":
            self.send_json(
                200,
                {
                    "status": "online",
                    "dashboard": (ROOT / "dashboard" / "chihiros-led-core-card.js").is_file(),
                    "plugin_kind": plugin_kind(),
                    "plugin_title": plugin_title(),
                    "enabled_tabs": plugin_tabs(),
                    "installed_plugins": installed_plugin_kinds(),
                    "plugin_assets": plugin_assets(),
                },
            )
            return
        if request_path == "/api/dashboard-state":
            self.send_json(200, build_dashboard_state())
            return
        if request_path == "/api/ha-state":
            params = parse_qs(parsed.query)
            self.read_ha_state(str((params.get("entity_id") or [""])[0]).strip())
            return
        if request_path == "/api/dashboard-settings":
            self.send_json(200, dashboard_settings())
            return
        if request_path == "/api/database-status":
            params = parse_qs(parsed.query)
            device = str((params.get("device") or [""])[0]).strip()
            self.send_json(200, database_diagnostics_status(device))
            return
        if request_path == "/api/led-device-status":
            params = parse_qs(parsed.query)
            device = str((params.get("device") or [""])[0]).strip()
            self.send_json(200, {"status": led_device_status(device)})
            return
        if request_path in ("/api/history", "/api/led-history"):
            params = parse_qs(parsed.query)
            device = str((params.get("device") or [""])[0]).strip()
            limit_text = str((params.get("limit") or ["200"])[0]).strip()
            scope = "led" if request_path == "/api/led-history" else str((params.get("scope") or [""])[0]).strip()
            try:
                limit = max(1, min(500, int(limit_text)))
            except ValueError:
                limit = 200
            self.send_json(200, {"entries": history_action_entries(device, limit, scope)})
            return
        self.serve_static(request_path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        request_path = f"/{parsed.path.lstrip('/')}"
        if request_path == "/api/ctl":
            self.run_ctl(self.read_json())
            return
        if request_path == "/api/dashboard-settings":
            self.save_dashboard_settings(self.read_json())
            return
        if request_path == "/api/ha-service":
            self.call_ha_service(self.read_json())
            return
        if request_path == "/api/led-schedule-local":
            self.save_led_schedule_local(self.read_json())
            return
        if request_path == "/api/led-device-status":
            self.save_led_device_status(self.read_json())
            return
        if request_path in ("/api/history", "/api/led-history"):
            self.save_history(self.read_json(), default_scope="led" if request_path == "/api/led-history" else "")
            return
        if request_path == "/api/plugins/install":
            self.install_plugin_archive(parsed)
            return
        if request_path == "/api/plugins/uninstall":
            self.uninstall_plugin_archive(self.read_json())
            return
        if request_path == "/api/plugin-backend":
            self.run_plugin_backend(self.read_json())
            return
        if request_path == "/api/addon-refresh":
            self.refresh_addon_update_source(self.read_json())
            return
        if request_path == "/api/addon-update":
            self.install_addon_source_update(self.read_json())
            return
        self.send_json(404, {"message": "Not found"})

    def install_plugin_archive(self, _parsed: object) -> None:
        """Validate and atomically install one configuration-local TGZ plugin."""
        try:
            content_length = int(self.headers.get("content-length", "0") or "0")
        except ValueError:
            content_length = 0
        if content_length <= 0 or content_length > MAX_PLUGIN_ARCHIVE_BYTES:
            self.send_json(413, {"message": "Plugin archive must be between 1 byte and 25 MiB"})
            return
        content_type = str(self.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if content_type not in {"application/gzip", "application/x-gzip", "application/octet-stream"}:
            self.send_json(415, {"message": "Only .tgz gzip archives are supported"})
            return
        payload = self.rfile.read(content_length)
        try:
            result = install_plugin_tgz(payload)
        except (OSError, ValueError, tarfile.TarError) as err:
            self.send_json(400, {"message": str(err)})
            return
        self.send_json(200, result)

    def run_plugin_backend(self, body: bytes) -> None:
        """Dispatch one allowlisted add-on plugin action."""
        try:
            data = json.loads(body.decode("utf-8") or "{}")
            plugin_id = str(data.get("plugin") or "").strip()
            action = str(data.get("action") or "").strip()
            args = data.get("args", [])
            if not re.fullmatch(r"[a-z][a-z0-9_]*", plugin_id):
                raise ValueError("Invalid plugin id")
            if not re.fullmatch(r"[a-z][a-z0-9_]*", action):
                raise ValueError("Invalid plugin action")
            if not isinstance(args, list):
                raise ValueError("Plugin args must be a list")
            result = call_plugin_backend(plugin_id, action, args)
        except (json.JSONDecodeError, TypeError, ValueError) as err:
            self.send_json(400, {"message": str(err)})
            return
        self.send_json(200, result if isinstance(result, dict) else {"result": result})

    def uninstall_plugin_archive(self, body: bytes) -> None:
        """Move one installed external plugin to the retained backup directory."""
        try:
            data = json.loads(body.decode("utf-8") or "{}")
            plugin_id = str(data.get("plugin") or "").strip()
            result = uninstall_plugin(plugin_id)
        except (json.JSONDecodeError, OSError, ValueError) as err:
            self.send_json(400, {"message": str(err)})
            return
        self.send_json(200, result)

    def save_dashboard_settings(self, body: bytes) -> None:
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json(400, {"message": "Invalid JSON"})
            return
        try:
            settings = normalize_dashboard_settings(data)
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        except ValueError as err:
            self.send_json(400, {"message": str(err)})
            return
        self.send_json(200, dashboard_settings())

    def save_led_device_status(self, body: bytes) -> None:
        try:
            data = json.loads(body.decode("utf-8") or "{}")
            if not isinstance(data, dict):
                raise ValueError("Statusdaten muessen ein Objekt sein")
            status = upsert_led_device_status(data)
        except (json.JSONDecodeError, ValueError, TypeError) as err:
            self.send_json(400, {"message": str(err)})
            return
        self.send_json(200, {"ok": True, "status": status})

    def call_ha_service(self, body: bytes) -> None:
        def synthetic_service_response(service_name: str, service_payload: dict[str, object]) -> dict[str, object]:
            send_flag = bool(service_payload.get("send", True))
            if service_name == "set_schedule":
                rows = len(service_payload.get("periods", []) or [])
                return {
                    "ok": True,
                    "send_status": "ok" if send_flag else "local",
                    "send_detail": "an Geraet gesendet" if send_flag else "nur lokal gespeichert",
                    "summary": f"LED schedule rows: {rows}",
                }
            if service_name == "reset_schedule":
                return {
                    "ok": True,
                    "send_status": "ok",
                    "send_detail": "an Geraet gesendet",
                    "summary": "LED schedule reset",
                }
            return {
                "ok": True,
                "send_status": "ok",
                "send_detail": "an Geraet gesendet",
            }

        def fail_response(message: str, *, debug_output: str = "") -> None:
            self.send_json(
                200,
                {
                    "result": {
                        "response": {
                            "ok": False,
                            "send_status": "fail",
                            "send_detail": message,
                            "debug_output": debug_output,
                        }
                    }
                },
            )

        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json(400, {"message": "Invalid JSON"})
            return
        domain = str(data.get("domain") or "").strip()
        service = str(data.get("service") or "").strip()
        payload = data.get("service_data", {})
        target = data.get("target", {})
        return_response = bool(data.get("return_response", False))
        if not re.fullmatch(r"[a-zA-Z0-9_]+", domain) or not re.fullmatch(r"[a-zA-Z0-9_]+", service):
            self.send_json(400, {"message": "Ungueltiger Home Assistant Service"})
            return
        if not isinstance(payload, dict):
            self.send_json(400, {"message": "service_data muss ein Objekt sein"})
            return
        if target and not isinstance(target, dict):
            self.send_json(400, {"message": "target muss ein Objekt sein"})
            return
        payload = {key: value for key, value in payload.items() if key != "device_key"}
        if isinstance(target, dict) and target.get("entity_id") and "entity_id" not in payload:
            payload = {**payload, "entity_id": target.get("entity_id")}
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            fail_response("SUPERVISOR_TOKEN fehlt")
            return
        try:
            print(
                "[ha-service] request",
                json.dumps(
                    {
                        "domain": domain,
                        "service": service,
                        "return_response": return_response,
                        "payload_keys": sorted(payload.keys()),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            suffix = "?return_response" if return_response else ""
            result = homeassistant_request("POST", f"/api/services/{domain}/{service}{suffix}", token, payload)
        except ValueError as err:
            message = str(err)
            print(f"[ha-service] primary-error {message}", flush=True)
            retry_without_response = return_response and (
                "Service does not support responses" in message
                or "Home Assistant API Fehler 400" in message
                or "400: Bad Request" in message
                or "Home Assistant API Fehler 500" in message
                or "500 Internal Server Error" in message
                or "Server got itself in trouble" in message
            )
            if not retry_without_response:
                service_exists, known_services = homeassistant_service_exists(token, domain, service)
                detail = f"{message}\nService registriert: {'ja' if service_exists else 'nein'}"
                if known_services:
                    detail += f"\nBekannte Services in {domain}: {', '.join(known_services)}"
                fail_response(detail)
                return
            try:
                print(f"[ha-service] fallback-without-return-response {domain}.{service}", flush=True)
                result = homeassistant_request("POST", f"/api/services/{domain}/{service}", token, payload)
            except ValueError as fallback_err:
                print(f"[ha-service] fallback-error {fallback_err}", flush=True)
                service_exists, known_services = homeassistant_service_exists(token, domain, service)
                detail = f"{fallback_err}\nService registriert: {'ja' if service_exists else 'nein'}"
                if known_services:
                    detail += f"\nBekannte Services in {domain}: {', '.join(known_services)}"
                fail_response(
                    detail,
                    debug_output=(
                        f"Debug\nService: {domain}.{service}\nInitial error: {message}\nFallback error: {fallback_err}"
                    ),
                )
                return
            print(f"[ha-service] fallback-ok {domain}.{service}", flush=True)
            fallback_response = synthetic_service_response(service, payload)
            self.send_json(
                200,
                {
                    "result": {
                        "response": {
                            **fallback_response,
                            "debug_output": (
                                "Debug\n"
                                f"Service: {domain}.{service}\n"
                                "Home Assistant Response-Aufruf wurde automatisch ohne return_response wiederholt.\n"
                                "Der Aufruf wurde automatisch ohne return_response wiederholt."
                            ),
                            "response_fallback": True,
                        }
                    }
                },
            )
            return
        except Exception as err:
            print(f"[ha-service] unexpected-error {type(err).__name__}: {err}", flush=True)
            fail_response(f"ha-service unexpected error: {type(err).__name__}: {err}")
            return
        print(f"[ha-service] success {domain}.{service}", flush=True)
        self.send_json(200, {"result": sanitize_ha_service_result(result)})

    def read_ha_state(self, entity_id: str) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+", entity_id):
            self.send_json(400, {"message": "Ungueltige entity_id"})
            return
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            self.send_json(500, {"message": "SUPERVISOR_TOKEN fehlt"})
            return
        try:
            state = homeassistant_request("GET", f"/api/states/{entity_id}", token)
        except ValueError as err:
            self.send_json(500, {"message": str(err)})
            return
        self.send_json(200, state if isinstance(state, dict) else {"state": "unknown", "attributes": {}})

    def save_history(self, body: bytes, default_scope: str = "") -> None:
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json(400, {"message": "Invalid JSON"})
            return
        device = str(data.get("device") or data.get("device_address") or "").strip().upper()
        action = str(data.get("action") or "").strip()
        detail = str(data.get("detail") or "").strip()
        status = str(data.get("status") or "").strip()
        scope = str(data.get("scope") or default_scope or "").strip()
        if not device:
            self.send_json(400, {"message": "History device fehlt"})
            return
        if not action:
            self.send_json(400, {"message": "History action fehlt"})
            return
        channel: int | None = None
        if data.get("channel") not in (None, ""):
            try:
                channel = int(data.get("channel")) - 1
            except (TypeError, ValueError):
                channel = None
        params = data.get("params", {})
        if not isinstance(params, dict):
            params = {}
        if scope:
            params = {**params, "scope": scope}
        try:
            record_history(device, action, channel, params, status, detail)
        except sqlite3.Error as err:
            self.send_json(500, {"message": f"SQLite Fehler: {err}"})
            return
        self.send_json(200, {"ok": True})

    def save_led_schedule_local(self, body: bytes) -> None:
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json(400, {"message": "Invalid JSON"})
            return
        address = str(data.get("address") or "").strip().upper()
        device_key = str(data.get("device_key") or "").strip().upper()
        periods = data.get("periods")
        if not address and not device_key:
            self.send_json(400, {"message": "LED address fehlt"})
            return
        if not isinstance(periods, list):
            self.send_json(400, {"message": "periods fehlt"})
            return
        try:
            save_led_schedule_rows_local(address or device_key, periods)
        except (OSError, sqlite3.Error, ValueError, TypeError) as err:
            self.send_json(
                200,
                {
                    "result": {
                        "response": {
                            "ok": False,
                            "send_status": "fail",
                            "send_detail": f"Lokales Speichern fehlgeschlagen: {err}",
                        }
                    }
                },
            )
            return
        self.send_json(
            200,
            {
                "result": {
                    "response": {
                        "ok": True,
                        "send_status": "local",
                        "send_detail": "nur lokal gespeichert",
                    }
                }
            },
        )

    def run_ctl(self, body: bytes) -> None:
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json(400, {"message": "Invalid JSON"})
            return

        command = str(data.get("command") or "").strip()
        if not command.startswith("chihirosctl "):
            self.send_json(400, {"message": "Only chihirosctl commands are allowed"})
            return
        if any(token in command for token in [";", "&", "|", "`", "$(", ">", "<"]):
            self.send_json(400, {"message": "Shell operators are not allowed"})
            return

        try:
            parts = shlex.split(command)
        except ValueError as err:
            self.send_json(400, {"message": str(err)})
            return

        try:
            result = subprocess.run(
                parts,
                cwd="/opt/chihiros-led-core-src",
                env={
                    **os.environ,
                    "PYTHONPATH": "/opt/chihiros-led-core-src/src:/opt/chihiros-led-core-src/custom_components/chihiros/vendor:/opt/chihiros-led-core-src",
                },
                text=True,
                capture_output=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.send_json(504, {"message": "Command timed out"})
            return

        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        self.send_json(
            200 if result.returncode == 0 else 500,
            {"returncode": result.returncode, "output": output or "(no output)"},
        )

    def refresh_addon_update_source(self, body: bytes) -> None:
        try:
            json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            pass
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            self.send_json(200, {"output": "Supervisor reload uebersprungen: SUPERVISOR_TOKEN fehlt"})
            return
        results = []
        for path in ("/store/reload", "/addons/reload"):
            try:
                supervisor_request("POST", path, token)
                results.append(f"{path}: OK")
            except ValueError as err:
                results.append(f"{path}: nicht erlaubt ({err})")
        self.send_json(200, {"output": "\n".join(results)})

    def install_addon_source_update(self, body: bytes) -> None:
        """Install an available Supervisor update, or refresh the runtime source as a fallback."""
        try:
            json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json(400, {"message": "Invalid JSON"})
            return
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            self.send_json(503, {"message": "SUPERVISOR_TOKEN fehlt"})
            return
        try:
            source_commit = github_source_commit()
            for path in ("/store/reload", "/addons/reload"):
                supervisor_request("POST", path, token)
            response = supervisor_request("GET", "/addons/self/info", token)
        except ValueError as err:
            self.send_json(502, {"message": str(err)})
            return

        info_obj = response.get("data") if isinstance(response.get("data"), dict) else response
        info = info_obj if isinstance(info_obj, dict) else {}
        slug = str(info.get("slug") or "").strip()
        if not slug or not re.fullmatch(r"[a-z0-9_]+", slug):
            self.send_json(502, {"message": "LED-Core-Add-on-Slug konnte nicht ermittelt werden"})
            return
        installed_version = str(info.get("version") or "").strip()
        latest_version = str(info.get("version_latest") or "").strip()
        update_available = info.get("update_available") is True or (
            bool(installed_version and latest_version) and installed_version != latest_version
        )
        runtime_commit = str(os.environ.get("CHIHIROS_SOURCE_COMMIT") or "").strip()
        action = "update" if update_available else "restart"
        message = (
            f"LED Core wird durch Supervisor von {installed_version or '?'} auf {latest_version or '?'} aktualisiert."
            if update_available
            else f"Keine neue Add-on-Version gemeldet. Laufzeit wird mit Git-Commit {source_commit} neu geladen."
        )

        self.send_json(
            202,
            {
                "status": "updating" if update_available else "restarting",
                "action": action,
                "source_commit": source_commit,
                "runtime_commit": runtime_commit,
                "installed_version": installed_version,
                "latest_version": latest_version,
                "message": message,
            },
        )

        def apply_update() -> None:
            time.sleep(1)
            try:
                endpoint = f"/addons/{slug}/update" if update_available else "/addons/self/restart"
                supervisor_request("POST", endpoint, token)
            except ValueError as err:
                print(f"LED Core update failed ({action}): {err}")

        threading.Thread(target=apply_update, name="led-core-source-update", daemon=True).start()

    def update_debug_output(self, state: object, label: str) -> str:
        lines = [label]
        if not isinstance(state, dict):
            lines.append("nicht vorhanden")
            return "\n".join(lines)
        attrs_obj = state.get("attributes")
        attrs = attrs_obj if isinstance(attrs_obj, dict) else {}
        lines.append(f"state: {state.get('state')}")
        lines.append(f"restored: {bool(attrs.get('restored'))}")
        lines.append(f"installed_version: {attrs.get('installed_version') or ''}")
        lines.append(f"latest_version: {attrs.get('latest_version') or ''}")
        lines.append(f"in_progress: {bool(attrs.get('in_progress'))}")
        supported_features = attrs.get("supported_features")
        lines.append(f"supported_features: {supported_features if supported_features is not None else ''}")
        lines.append(f"release_url: {attrs.get('release_url') if attrs.get('release_url') is not None else ''}")
        return "\n".join(lines)

    def read_json(self) -> bytes:
        length = int(self.headers.get("content-length", "0") or "0")
        return self.rfile.read(length) if length > 0 else b"{}"

    def serve_static(self, raw_path: str) -> None:
        path = unquote(raw_path).lstrip("/") or "index.html"
        root = ROOT
        allowed_roots = [ROOT.resolve()]
        if path.startswith("plugins/"):
            parts = path.split("/", 2)
            if len(parts) != 3 or not re.fullmatch(r"[a-z][a-z0-9_]*", parts[1]):
                self.send_json(404, {"message": "Not found"})
                return
            try:
                plugin = _plugin_manifest(parts[1])
            except ValueError:
                self.send_json(404, {"message": "Not found"})
                return
            root = Path(str(plugin["_root"])).resolve()
            path = parts[2]
            allowed_roots = [root]
        target = (root / path).resolve()
        if not target.is_file() or not any(target == allowed or allowed in target.parents for allowed in allowed_roots):
            self.send_json(404, {"message": "Not found"})
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        payload = target.read_bytes()
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, status: int, data: dict[str, object]) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def state_obj(value: object, unit: str = "", **attrs: object) -> dict[str, object]:
    attributes = {key: item for key, item in attrs.items() if item is not None}
    if unit:
        attributes["unit_of_measurement"] = unit
    return {"state": str(value), "attributes": attributes}


def github_source_commit() -> str:
    """Verify private GitHub access and return the configured branch head."""
    options_path = Path("/data/options.json")
    try:
        options = json.loads(options_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ValueError("Add-on-Konfiguration konnte nicht gelesen werden") from err
    github_token = str(options.get("github_token") or "").strip()
    source_branch = str(options.get("source_branch") or "main").strip() or "main"
    if not github_token:
        raise ValueError("GitHub-Token fehlt in der LED-Core-Add-on-Konfiguration")
    url = (
        "https://api.github.com/repos/charlie508010/chihiros-led-control-led-beta/commits/"
        f"{quote(source_branch, safe='')}"
    )
    req = request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "User-Agent": "chihiros-led-core-addon",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            payload = response.read().decode("utf-8")
    except error.HTTPError as err:
        if err.code in (401, 403, 404):
            raise ValueError(
                "GitHub-Zugriff fehlgeschlagen: Token, Repository-Berechtigung oder Branch prüfen"
            ) from err
        raise ValueError(f"GitHub API Fehler {err.code}") from err
    except OSError as err:
        raise ValueError(f"GitHub nicht erreichbar: {err}") from err
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as err:
        raise ValueError("GitHub hat keine gültige Commit-Antwort geliefert") from err
    commit = str(data.get("sha") or "") if isinstance(data, dict) else ""
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ValueError("GitHub hat keinen gültigen Branch-Commit geliefert")
    return commit[:12]


def supervisor_request(method: str, path: str, token: str, body: dict[str, object] | None = None) -> dict[str, object]:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = request.Request(f"http://supervisor{path}", data=payload, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=180) as response:
            payload = response.read().decode("utf-8")
    except error.HTTPError as err:
        payload = err.read().decode("utf-8", errors="replace")
        raise ValueError(f"Supervisor API Fehler {err.code}: {payload}") from err
    except OSError as err:
        raise ValueError(f"Supervisor API nicht erreichbar: {err}") from err
    try:
        data = json.loads(payload or "{}")
    except json.JSONDecodeError as err:
        raise ValueError(f"Supervisor API hat kein JSON geliefert: {payload}") from err
    if isinstance(data, dict) and data.get("result") == "error":
        raise ValueError(str(data.get("message") or data))
    return data if isinstance(data, dict) else {"data": data}


def homeassistant_request(method: str, path: str, token: str, body: dict[str, object] | None = None) -> object:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = request.Request(f"http://supervisor/core{path}", data=payload, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=90) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        request_body = ""
        if body is not None:
            request_body = json.dumps(body, ensure_ascii=False)
        detail = raw.strip() or err.reason or "Bad Request"
        raise ValueError(
            f"Home Assistant API Fehler {err.code}: {detail}\nPfad: {path}\nRequest JSON: {request_body}"
        ) from err
    except OSError as err:
        raise ValueError(f"Home Assistant API nicht erreichbar: {err}") from err
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def homeassistant_service_exists(token: str, domain: str, service: str) -> tuple[bool, list[str]]:
    """Return whether a Home Assistant service is registered."""
    try:
        data = homeassistant_request("GET", "/api/services", token)
    except ValueError:
        return False, []
    if not isinstance(data, list):
        return False, []
    for item in data:
        if not isinstance(item, dict):
            continue
        if str(item.get("domain") or "") != domain:
            continue
        services = item.get("services")
        if not isinstance(services, dict):
            return False, []
        known = sorted(str(name) for name in services.keys())
        return service in services, known
    return False, []


def _clean_debug_output(value: object) -> str:
    """Remove empty protocol markers from plain debug text."""
    text = str(value or "")
    text = re.sub(r"(?:^|\n)Request JSON:\n\{.*?\}(?=\n[A-Z][A-Za-z ]*:|\Z)", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = normalize_protocol_debug_text(text)
    return re.sub(r"(?:\n\s*)+Raw Debug:?\s*$", "", text, flags=re.IGNORECASE).strip()


def sanitize_ha_service_result(value: object) -> object:
    """Clean HA service debug payloads before the add-on UI receives them."""
    if isinstance(value, list):
        return [sanitize_ha_service_result(item) for item in value]
    if not isinstance(value, dict):
        return value

    title_value = str(value.get("title") or "").strip().lower() if isinstance(value, dict) else ""
    if title_value in {"raw debug", "protocol debug"}:
        normalized_section = dict(value)
        section_text = str(normalized_section.get("value") or normalized_section.get("text") or "").strip()
        normalized_section["title"] = "Raw Debug"
        normalized_section["value"] = normalize_protocol_debug_text(section_text)
        value = normalized_section

    cleaned: dict[str, object] = {}
    for key, item in value.items():
        if key == "debug_output":
            debug_output = _clean_debug_output(item)
            if debug_output:
                cleaned[key] = debug_output
            continue
        if key == "sections" and isinstance(item, list):
            sections: list[object] = []
            for section in item:
                if not isinstance(section, dict):
                    sections.append(sanitize_ha_service_result(section))
                    continue
                title = str(section.get("title") or "").strip().lower()
                section_value = str(section.get("value") or section.get("text") or "").strip()
                if title == "request json":
                    continue
                if title == "response json":
                    continue
                if title == "protocol debug" and (not section_value or section_value.lower() == "protocol debug"):
                    continue
                if title == "protocol debug":
                    section = {**section, "title": "Raw Debug", "value": normalize_protocol_debug_text(section_value)}
                elif title == "raw debug":
                    section = {**section, "value": normalize_protocol_debug_text(section_value)}
                sections.append(sanitize_ha_service_result(section))
            if sections:
                cleaned[key] = sections
            continue
        cleaned[key] = sanitize_ha_service_result(item)
    return cleaned


def parse_ts(value: str) -> tuple[str, str]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.date().isoformat(), parsed.strftime("%H:%M:%S")
    except ValueError:
        return "", ""


def _history_sort_key(entry: dict[str, object]) -> str:
    return str(entry.get("ts") or f"{entry.get('date', '')}T{entry.get('time', '')}")


def ensure_actions_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            device_alias TEXT DEFAULT '',
            device_address TEXT DEFAULT '',
            action TEXT NOT NULL,
            channel INTEGER,
            params_json TEXT DEFAULT '{}',
            status TEXT DEFAULT '',
            output TEXT DEFAULT ''
        )
        """
    )


def record_history(
    device: str,
    action: str,
    channel: int | None,
    params: dict[str, object],
    status: str,
    output: str,
) -> None:
    path = current_state_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        ensure_actions_table(conn)
        conn.execute(
            """
            INSERT INTO actions(ts, device_alias, device_address, action, channel, params_json, status, output)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                device,
                device,
                action,
                channel,
                json.dumps(params or {}, ensure_ascii=False),
                status,
                output,
            ),
        )


def history_action_entries(device: str, limit: int = 200, scope: str = "") -> list[dict[str, object]]:
    normalized = str(device or "").strip().upper()
    if not normalized:
        return []
    scope_filter = str(scope or "").strip().lower()
    scope_sql = ""
    sql_params: list[object] = [normalized, normalized]
    if scope_filter == "led":
        scope_sql = """
          AND (
            json_extract(params_json, '$.scope') = 'led'
            OR action LIKE 'LED%'
            OR action LIKE 'Zeitplan%'
            OR action LIKE 'Scheduler%'
            OR action LIKE 'Schedule%'
            OR action LIKE 'an Geraet%'
            OR action LIKE 'sent to device%'
          )
        """
    entries: list[dict[str, object]] = []
    for row in sqlite_rows(
        f"""
        SELECT ts, action, channel AS ch, params_json, status, output
        FROM actions
        WHERE (UPPER(device_address)=UPPER(?) OR UPPER(device_alias)=UPPER(?))
        {scope_sql}
        ORDER BY id DESC
        LIMIT ?
        """,
        (*sql_params, max(1, min(500, int(limit)))),
    ):
        date_text, time_text = parse_ts(str(row.get("ts") or ""))
        entry: dict[str, object] = {
            "ts": str(row.get("ts") or ""),
            "date": date_text,
            "time": time_text,
            "action": str(row.get("action") or ""),
            "detail": str(row.get("output") or row.get("status") or ""),
            "status": str(row.get("status") or ""),
        }
        channel = row.get("ch")
        if channel is not None:
            try:
                entry["channel"] = int(channel) + 1
            except (TypeError, ValueError):
                pass
        params = row.get("params_json")
        if params:
            try:
                parsed = json.loads(str(params))
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                entry["params"] = parsed
        entries.append(entry)
    return entries


def build_dashboard_state() -> dict[str, object]:
    """Build the standalone dashboard state from LED entities only."""
    states: dict[str, dict[str, object]] = {}
    settings = dashboard_settings()
    settings["templates"] = led_templates()
    settings["led_schedules"] = {}
    settings["led_device_status"] = {}
    cleanup_led_diagnostics(settings)
    led_addresses: set[str] = set()
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    entity_pattern = re.compile(
        r"^(light|switch|sensor)\.([a-z0-9]*[0-9a-f]{12})_"
        r"(red|green|blue|white|power|auto_mode|schedule|firmware_version|runtime|runtime_minutes|last_notification)"
        r"(?:_\d+)?$",
        re.IGNORECASE,
    )
    if token:
        try:
            ha_states = homeassistant_request("GET", "/api/states", token)
            if isinstance(ha_states, list):
                matched_states: list[tuple[dict[str, object], re.Match[str]]] = []
                for item in ha_states:
                    if not isinstance(item, dict):
                        continue
                    entity_id = str(item.get("entity_id") or "")
                    match = entity_pattern.match(entity_id)
                    if not match:
                        continue
                    attributes = item.get("attributes", {})
                    if not isinstance(attributes, dict) or attributes.get("integration_domain") != "chihiros_led_core":
                        continue
                    matched_states.append((item, match))
                    if match.group(1).lower() != "light" or match.group(3).lower() not in {
                        "red",
                        "green",
                        "blue",
                        "white",
                    }:
                        continue
                    compact = match.group(2)[-12:]
                    led_addresses.add(":".join(compact[index : index + 2] for index in range(0, 12, 2)).upper())

                for item, match in matched_states:
                    compact = match.group(2)[-12:]
                    address = ":".join(compact[index : index + 2] for index in range(0, 12, 2)).upper()
                    if address not in led_addresses:
                        continue
                    entity_id = str(item.get("entity_id") or "")
                    attrs = item.get("attributes", {})
                    states[entity_id] = {
                        "state": str(item.get("state") or "unknown"),
                        "attributes": attrs if isinstance(attrs, dict) else {},
                        "last_changed": str(item.get("last_changed") or ""),
                        "last_updated": str(item.get("last_updated") or ""),
                    }
        except ValueError:
            pass
        try:
            update_state = homeassistant_request("GET", "/api/states/update.led_core_update", token)
            if isinstance(update_state, dict) and update_state.get("entity_id"):
                states[str(update_state["entity_id"])] = {
                    "state": str(update_state.get("state") or "unknown"),
                    "attributes": update_state.get("attributes", {})
                    if isinstance(update_state.get("attributes"), dict)
                    else {},
                }
        except ValueError:
            pass

    for address in sorted(led_addresses):
        settings["led_schedules"][address] = led_schedule_rows(address)
        settings["led_device_status"][address] = led_device_status(address)

    return {
        "status": "online",
        "plugin_kind": plugin_kind(),
        "plugin_title": plugin_title(),
        "enabled_tabs": plugin_tabs(),
        "installed_plugins": installed_plugin_kinds(),
        "plugin_assets": plugin_assets(),
        "devices": [],
        "states": states,
        "database": settings,
        "state_db_path": str(current_state_db_path()),
    }


def led_templates() -> dict[str, object]:
    def decode_values(raw: str) -> list[int]:
        try:
            values = json.loads(raw or "[]")
        except json.JSONDecodeError:
            return []
        return [int(value) for value in values] if isinstance(values, list) else []

    standard = []
    for row in sqlite_rows("SELECT name, values_json, updated_at FROM ctl_standard_templates ORDER BY name"):
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        standard.append(
            {
                "name": name,
                "values": decode_values(str(row.get("values_json") or "[]")),
                "updated_at": str(row.get("updated_at") or ""),
            }
        )
    devices = []
    for row in sqlite_rows(
        "SELECT device_key, name, values_json, updated_at FROM ctl_device_templates ORDER BY device_key, name"
    ):
        device_key = str(row.get("device_key") or "").strip().upper()
        name = str(row.get("name") or "").strip()
        if not device_key or not name:
            continue
        devices.append(
            {
                "device_key": device_key,
                "name": name,
                "values": decode_values(str(row.get("values_json") or "[]")),
                "updated_at": str(row.get("updated_at") or ""),
            }
        )
    return {"standard": standard, "devices": devices}


def led_schedule_rows(device: str) -> list[dict[str, object]]:
    key = str(device or "").strip().upper()
    if not key:
        return []
    with sqlite3.connect(current_state_db_path()) as conn:
        ensure_led_schedule_table(conn)

    def decode_json(raw: object, fallback: object) -> object:
        try:
            value = json.loads(str(raw or ""))
        except (TypeError, json.JSONDecodeError):
            return fallback
        return value

    rows: list[dict[str, object]] = []
    for row in sqlite_rows(
        """
        SELECT schedule_index, start_time, end_time, levels_json, ramp_up_minutes, weekdays_json, active, sent, updated_at,
               verification_status, verified_at
        FROM led_schedules
        WHERE UPPER(device_key)=UPPER(?)
        ORDER BY schedule_index ASC
        """,
        (key,),
    ):
        levels = decode_json(row.get("levels_json"), {})
        weekdays = decode_json(row.get("weekdays_json"), ["everyday"])
        stored_ramp = max(1, int(row.get("ramp_up_minutes") or 1))
        rows.append(
            {
                "index": int(row.get("schedule_index") or 0),
                "start": str(row.get("start_time") or ""),
                "end": str(row.get("end_time") or ""),
                "levels": levels if isinstance(levels, dict) else {},
                # A stored 1 can originate from the protocol minimum used for
                # a configured zero-minute ramp. Expose the configured value.
                "ramp": stored_ramp,
                "weekdays": weekdays if isinstance(weekdays, list) else ["everyday"],
                "active": bool(int(row.get("active") if row.get("active") is not None else 1)),
                "sent": bool(int(row.get("sent") or 0)),
                "updated_at": str(row.get("updated_at") or ""),
                "verification_status": str(row.get("verification_status") or "pending"),
                "verified_at": str(row.get("verified_at") or ""),
            }
        )
    return rows


def ensure_led_device_status_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS led_device_status (
            device_key TEXT PRIMARY KEY,
            mode TEXT NOT NULL DEFAULT 'unknown',
            power_state TEXT NOT NULL DEFAULT 'unknown',
            channels_json TEXT NOT NULL DEFAULT '{}',
            schedule_state TEXT NOT NULL DEFAULT 'unknown',
            schedule_count INTEGER NOT NULL DEFAULT 0,
            schedule_window TEXT NOT NULL DEFAULT '',
            last_source TEXT NOT NULL DEFAULT '',
            last_action TEXT NOT NULL DEFAULT '',
            last_channel INTEGER,
            last_status TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    columns = {
        str(row.get("name") or "") for row in sqlite_rows_with_conn(conn, "PRAGMA table_info(led_device_status)")
    }
    if "schedule_window" not in columns:
        conn.execute("ALTER TABLE led_device_status ADD COLUMN schedule_window TEXT NOT NULL DEFAULT ''")


def led_device_status(device: str) -> dict[str, object] | None:
    key = str(device or "").strip().upper()
    if not key:
        return None
    rows = sqlite_rows(
        """
        SELECT device_key, mode, power_state, channels_json, schedule_state,
               schedule_count, schedule_window, last_source, last_action, last_channel, last_status, updated_at
        FROM led_device_status
        WHERE UPPER(device_key)=UPPER(?)
        LIMIT 1
        """,
        (key,),
    )
    if not rows:
        return None
    row = rows[0]
    try:
        channels = json.loads(str(row.get("channels_json") or "{}"))
    except json.JSONDecodeError:
        channels = {}
    row["channels"] = channels if isinstance(channels, dict) else {}
    row.pop("channels_json", None)
    return row


def upsert_led_device_status(data: dict[str, object]) -> dict[str, object]:
    device_key = str(data.get("device_key") or data.get("address") or "").strip().upper()
    if not device_key:
        raise ValueError("device_key fehlt")
    mode = str(data.get("mode") or "unknown").strip().lower()
    power_state = str(data.get("power_state") or "unknown").strip().lower()
    schedule_state = str(data.get("schedule_state") or "unknown").strip().lower()
    if mode not in {"unknown", "manual", "automatic"}:
        raise ValueError("mode muss unknown, manual oder automatic sein")
    if power_state not in {"unknown", "on", "off"}:
        raise ValueError("power_state muss unknown, on oder off sein")
    if schedule_state not in {"unknown", "empty", "configured", "active", "manual_override"}:
        raise ValueError("ungueltiger schedule_state")
    raw_channels = data.get("channels") or {}
    if not isinstance(raw_channels, dict):
        raise ValueError("channels muss ein Objekt sein")
    channels = {str(key): int(value) for key, value in raw_channels.items()}
    schedule_count = max(0, int(data.get("schedule_count") or 0))
    schedule_window = str(data.get("schedule_window") or "").strip()
    raw_channel = data.get("last_channel")
    last_channel = int(raw_channel) if raw_channel is not None else None
    updated_at = datetime.now(timezone.utc).isoformat()
    path = current_state_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        ensure_led_device_status_table(conn)
        conn.execute(
            """
            INSERT INTO led_device_status(
                device_key, mode, power_state, channels_json, schedule_state, schedule_count, schedule_window,
                last_source, last_action, last_channel, last_status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_key) DO UPDATE SET
                mode=excluded.mode,
                power_state=excluded.power_state,
                channels_json=excluded.channels_json,
                schedule_state=excluded.schedule_state,
                schedule_count=excluded.schedule_count,
                schedule_window=CASE
                    WHEN excluded.schedule_window='' THEN led_device_status.schedule_window
                    ELSE excluded.schedule_window
                END,
                last_source=excluded.last_source,
                last_action=excluded.last_action,
                last_channel=excluded.last_channel,
                last_status=excluded.last_status,
                updated_at=excluded.updated_at
            """,
            (
                device_key,
                mode,
                power_state,
                json.dumps(channels, ensure_ascii=False, sort_keys=True),
                schedule_state,
                schedule_count,
                schedule_window,
                str(data.get("last_source") or ""),
                str(data.get("last_action") or ""),
                last_channel,
                str(data.get("last_status") or "ok"),
                updated_at,
            ),
        )
    LED_STATUS_WAKE_EVENT.set()
    return led_device_status(device_key) or {}


def reconcile_led_device_statuses(now: datetime | None = None) -> int:
    """Advance persisted automatic LED states when schedule windows change."""
    path = current_state_db_path()
    if not path.exists():
        return 0
    current = now or datetime.now()
    weekday = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[current.weekday()]
    current_minute = (current.hour * 60) + current.minute
    changed = 0

    def minute_of(value: object) -> int:
        try:
            hour_text, minute_text = str(value or "00:00").split(":", 1)
            return (max(0, min(23, int(hour_text))) * 60) + max(0, min(59, int(minute_text)))
        except (TypeError, ValueError):
            return 0

    with sqlite3.connect(path, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        ensure_led_device_status_table(conn)
        status_rows = conn.execute(
            "SELECT device_key, mode, channels_json, schedule_state, schedule_count, schedule_window, power_state FROM led_device_status"
        ).fetchall()
        for status_row in status_rows:
            device_key = str(status_row["device_key"])
            schedule_rows = conn.execute(
                """
                SELECT start_time, end_time, levels_json, weekdays_json, active
                FROM led_schedules
                WHERE UPPER(device_key)=UPPER(?)
                ORDER BY schedule_index
                """,
                (device_key,),
            ).fetchall()
            configured = [row for row in schedule_rows if bool(int(row["active"] or 0))]
            all_channels: set[str] = set()
            active_levels: dict[str, int] | None = None
            active_window = "off"
            for schedule_index, row in enumerate(configured):
                try:
                    levels = json.loads(str(row["levels_json"] or "{}"))
                except json.JSONDecodeError:
                    levels = {}
                if not isinstance(levels, dict):
                    levels = {}
                all_channels.update(str(key) for key in levels)
                try:
                    weekdays = json.loads(str(row["weekdays_json"] or "[]"))
                except json.JSONDecodeError:
                    weekdays = ["everyday"]
                if not isinstance(weekdays, list):
                    weekdays = ["everyday"]
                normalized_days = {str(day).strip().lower() for day in weekdays}
                if "everyday" not in normalized_days and weekday not in normalized_days:
                    continue
                start = minute_of(row["start_time"])
                end = minute_of(row["end_time"])
                in_window = start <= end and start <= current_minute < end
                if start > end:
                    in_window = current_minute >= start or current_minute < end
                if in_window and active_levels is None:
                    active_levels = {str(key): max(0, int(value)) for key, value in levels.items()}
                    active_window = f"{schedule_index}:{row['start_time']}-{row['end_time']}"

            try:
                previous_channels = json.loads(str(status_row["channels_json"] or "{}"))
            except json.JSONDecodeError:
                previous_channels = {}
            if isinstance(previous_channels, dict):
                all_channels.update(str(key) for key in previous_channels)
            channels = {key: 0 for key in sorted(all_channels)}
            if active_levels is not None:
                channels.update(active_levels)
            schedule_count = len(configured)
            schedule_state = "active" if active_levels is not None else ("configured" if configured else "empty")
            power_state = "on" if any(value > 0 for value in channels.values()) else "off"
            previous_window = str(status_row["schedule_window"] or "")
            if previous_window and previous_window == active_window:
                continue
            conn.execute(
                """
                UPDATE led_device_status
                SET mode='automatic', power_state=?, channels_json=?, schedule_state=?, schedule_count=?, schedule_window=?,
                    last_source='scheduler_clock', last_action=?, last_status='ok', updated_at=?
                WHERE device_key=?
                """,
                (
                    power_state,
                    json.dumps(channels, ensure_ascii=False, sort_keys=True),
                    schedule_state,
                    schedule_count,
                    active_window,
                    "Zeitplan gestartet" if active_levels is not None else "Zeitplan beendet",
                    datetime.now(timezone.utc).isoformat(),
                    device_key,
                ),
            )
            changed += 1
    return changed


def seconds_until_next_led_schedule_boundary(now: datetime | None = None) -> float | None:
    """Return seconds until the next configured LED start or end boundary."""
    current = now or datetime.now()
    rows = sqlite_rows(
        """
        SELECT start_time, end_time, weekdays_json
        FROM led_schedules
        WHERE active=1
        """
    )
    candidates: list[datetime] = []
    weekday_names = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    for row in rows:
        try:
            start_hour, start_minute = (int(value) for value in str(row.get("start_time") or "00:00").split(":", 1))
            end_hour, end_minute = (int(value) for value in str(row.get("end_time") or "00:00").split(":", 1))
        except (TypeError, ValueError):
            continue
        try:
            weekdays = json.loads(str(row.get("weekdays_json") or "[]"))
        except json.JSONDecodeError:
            weekdays = ["everyday"]
        normalized_days = {str(day).strip().lower() for day in weekdays} if isinstance(weekdays, list) else {"everyday"}
        for day_offset in range(8):
            schedule_date = current.date() + timedelta(days=day_offset)
            if "everyday" not in normalized_days and weekday_names[schedule_date.weekday()] not in normalized_days:
                continue
            start_at = datetime.combine(schedule_date, datetime_time(start_hour, start_minute))
            end_date = (
                schedule_date
                if (end_hour, end_minute) > (start_hour, start_minute)
                else schedule_date + timedelta(days=1)
            )
            end_at = datetime.combine(end_date, datetime_time(end_hour, end_minute))
            candidates.extend(boundary for boundary in (start_at, end_at) if boundary > current)
    if not candidates:
        return None
    return max(0.1, (min(candidates) - current).total_seconds() + 0.1)


def led_status_reconcile_loop() -> None:
    """Keep LED status rows aligned with exact schedule boundaries and writes."""
    while True:
        try:
            reconcile_led_device_statuses()
        except (OSError, sqlite3.Error, ValueError) as err:
            print(f"LED status reconcile failed: {err}", flush=True)
        delay = seconds_until_next_led_schedule_boundary()
        LED_STATUS_WAKE_EVENT.wait(delay)
        LED_STATUS_WAKE_EVENT.clear()


def ensure_led_schedule_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS led_schedules (
            device_key TEXT NOT NULL,
            schedule_index INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            levels_json TEXT NOT NULL DEFAULT '{}',
            ramp_up_minutes INTEGER NOT NULL DEFAULT 1,
            weekdays_json TEXT NOT NULL DEFAULT '[]',
            active INTEGER NOT NULL DEFAULT 1,
            sent INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'addon',
            updated_at TEXT NOT NULL DEFAULT '',
            schedule_signature TEXT NOT NULL DEFAULT '',
            verification_status TEXT NOT NULL DEFAULT 'pending',
            verified_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    columns = {str(row.get("name") or "") for row in sqlite_rows_with_conn(conn, "PRAGMA table_info(led_schedules)")}
    if "weekdays_json" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN weekdays_json TEXT NOT NULL DEFAULT '[]'")
    if "active" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    if "sent" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN sent INTEGER NOT NULL DEFAULT 0")
    if "source" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN source TEXT NOT NULL DEFAULT 'addon'")
    if "updated_at" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
    if "schedule_signature" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN schedule_signature TEXT NOT NULL DEFAULT ''")
    if "verification_status" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'pending'")
    if "verified_at" not in columns:
        conn.execute("ALTER TABLE led_schedules ADD COLUMN verified_at TEXT NOT NULL DEFAULT ''")


def sqlite_rows_with_conn(
    conn: sqlite3.Connection, query: str, params: tuple[object, ...] = ()
) -> list[dict[str, object]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def save_led_schedule_rows_local(device: str, periods: list[dict[str, object]]) -> None:
    device_key = str(device or "").strip().upper()
    if not device_key:
        raise ValueError("device_key fehlt")
    path = current_state_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat()
    with sqlite3.connect(path) as conn:
        ensure_led_schedule_table(conn)
        previous = {
            str(row[0]): (str(row[1]), str(row[2]))
            for row in conn.execute(
                "SELECT schedule_signature, verification_status, verified_at FROM led_schedules WHERE UPPER(device_key)=UPPER(?)",
                (device_key,),
            ).fetchall()
        }
        conn.execute("DELETE FROM led_schedules WHERE UPPER(device_key)=UPPER(?)", (device_key,))
        for index, period in enumerate(periods):
            levels = period.get("levels", period.get("brightness", {}))
            weekdays = period.get("weekdays") or ["everyday"]
            stored_ramp_up_minutes = max(1, int(period.get("ramp_up_minutes") or 1))
            signature = json.dumps(
                {
                    "start": str(period.get("start") or ""),
                    "end": str(period.get("end") or ""),
                    "levels": {
                        str(key): int(value)
                        for key, value in sorted((levels if isinstance(levels, dict) else {}).items())
                    },
                    "ramp": stored_ramp_up_minutes,
                    "weekdays": sorted(
                        str(value) for value in (weekdays if isinstance(weekdays, list) else ["everyday"])
                    ),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            verification_status, verified_at = previous.get(signature, ("pending", ""))
            conn.execute(
                """
                INSERT INTO led_schedules(
                    device_key, schedule_index, start_time, end_time, levels_json,
                    ramp_up_minutes, weekdays_json, active, sent, source, updated_at,
                    schedule_signature, verification_status, verified_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_key,
                    index,
                    str(period.get("start") or ""),
                    str(period.get("end") or ""),
                    json.dumps(levels if isinstance(levels, dict) else {}, ensure_ascii=False),
                    stored_ramp_up_minutes,
                    json.dumps(weekdays if isinstance(weekdays, list) else ["everyday"], ensure_ascii=False),
                    0 if period.get("active") is False else 1,
                    0,
                    "addon",
                    now,
                    signature,
                    verification_status,
                    verified_at,
                ),
            )
    LED_STATUS_WAKE_EVENT.set()


def normalize_dashboard_settings(data: dict[str, object]) -> dict[str, object]:
    try:
        retention_days = int(data.get("diagnostic_retention_days") or DEFAULT_DIAGNOSTIC_RETENTION_DAYS)
    except (TypeError, ValueError):
        retention_days = DEFAULT_DIAGNOSTIC_RETENTION_DAYS
    return {
        "mode": "integration",
        "state_db_path": str(DEFAULT_STATE_DB_PATH),
        "database_diagnostics_enabled": bool(data.get("database_diagnostics_enabled", False)),
        "dashboard_debug": bool(data.get("dashboard_debug", False)),
        "diagnostic_retention_days": max(0, min(3650, retention_days)),
    }


def dashboard_settings() -> dict[str, object]:
    settings = normalize_dashboard_settings(read_json_file(SETTINGS_PATH))
    settings["effective_state_db_path"] = str(current_state_db_path(settings))
    settings["integration_state_db_path"] = str(DEFAULT_STATE_DB_PATH)
    return settings


def current_state_db_path(settings: dict[str, object] | None = None) -> Path:
    del settings
    return DEFAULT_STATE_DB_PATH


def cleanup_led_diagnostics(settings: dict[str, object] | None = None) -> int:
    """Remove expired periodic LED diagnostics when retention is explicitly enabled."""
    selected = settings or normalize_dashboard_settings(read_json_file(SETTINGS_PATH))
    retention_days = int(selected.get("diagnostic_retention_days") or 0)
    path = current_state_db_path(selected)
    if retention_days <= 0 or not path.exists():
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    with sqlite3.connect(path, timeout=10) as conn:
        ensure_actions_table(conn)
        cursor = conn.execute(
            "DELETE FROM actions WHERE action='LED notification fetch' AND ts < ?",
            (cutoff,),
        )
    return max(0, int(cursor.rowcount or 0))


def read_json_file(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def database_diagnostics_enabled() -> bool:
    """Return whether database access diagnostics are enabled."""
    return bool(normalize_dashboard_settings(read_json_file(SETTINGS_PATH))["database_diagnostics_enabled"])


def database_diagnostics_status(device: str = "") -> dict[str, object]:
    """Return the two scheduler database results for one LED device."""
    enabled = database_diagnostics_enabled()
    path = current_state_db_path()
    device_key = str(device or "").strip().upper()
    opened = False
    error_message = ""
    requests: list[dict[str, object]] = []
    if enabled and path.exists():
        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2) as conn:
                conn.row_factory = sqlite3.Row
                table_names = {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?)",
                        ("led_schedules", "led_schedule_verification_jobs"),
                    ).fetchall()
                }
                schedule_rows: list[dict[str, object]] = []
                if "led_schedules" in table_names:
                    schedule_rows = [
                        dict(row)
                        for row in conn.execute(
                            """
                            SELECT schedule_index AS position,
                                   start_time || ' - ' || end_time AS time_window,
                                   levels_json AS levels,
                                   ramp_up_minutes AS ramp_minutes,
                                   CASE active WHEN 1 THEN 'active' ELSE 'inactive' END AS active,
                                   verification_status AS verification,
                                   verified_at
                            FROM led_schedules
                            WHERE UPPER(device_key)=UPPER(?)
                            ORDER BY schedule_index
                            """,
                            (device_key,),
                        ).fetchall()
                    ]
                requests.append(
                    {
                        "name": "stored_schedules",
                        "status": "ok" if "led_schedules" in table_names else "unavailable",
                        "columns": [
                            "position",
                            "time_window",
                            "levels",
                            "ramp_minutes",
                            "active",
                            "verification",
                            "verified_at",
                        ],
                        "rows": schedule_rows,
                    }
                )

                verification_rows: list[dict[str, object]] = []
                if "led_schedule_verification_jobs" in table_names:
                    verification_rows = [
                        dict(row)
                        for row in conn.execute(
                            """
                            SELECT target_json AS target,
                                   restore_json AS restore_rows,
                                   due_at,
                                   created_at
                            FROM led_schedule_verification_jobs
                            WHERE UPPER(device_key)=UPPER(?)
                            ORDER BY due_at
                            """,
                            (device_key,),
                        ).fetchall()
                    ]
                requests.append(
                    {
                        "name": "verification_jobs",
                        "status": "ok" if "led_schedule_verification_jobs" in table_names else "unavailable",
                        "columns": ["target", "restore_rows", "due_at", "created_at"],
                        "rows": verification_rows,
                    }
                )
            opened = True
        except sqlite3.Error as err:
            error_message = str(err)
    return {
        "enabled": enabled,
        "device": device_key,
        "path": str(path),
        "exists": path.exists(),
        "open": opened,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "error": error_message,
        "requests": requests,
    }


def sqlite_rows(query: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
    path = current_state_db_path()
    if not path.exists():
        return []
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(query, params).fetchall()]
    except sqlite3.Error:
        return []


def initialize_led_core_database() -> None:
    """Create the dedicated LED Core database and its local-only tables."""
    from chihiros_led_control.store import init_state_db

    init_state_db()
    path = current_state_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as conn:
        ensure_actions_table(conn)
        ensure_led_schedule_table(conn)
        ensure_led_device_status_table(conn)


if __name__ == "__main__":
    port = int(os.environ.get("CHIHIROS_UI_PORT") or "8109")
    initialize_led_core_database()
    threading.Thread(target=led_status_reconcile_loop, name="led-status-reconcile", daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"{plugin_title()} web UI listening on port {port}")
    server.serve_forever()
