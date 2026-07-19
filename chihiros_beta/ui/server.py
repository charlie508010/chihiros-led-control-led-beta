#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import mimetypes
import os
import re
import shlex
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from datetime import time as datetime_time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request
from urllib.parse import parse_qs, unquote, urlparse


def _load_normalize_protocol_debug_text():
    source_root = Path(os.environ.get("CHIHIROS_SOURCE_ROOT", "/opt/chihiros-src"))
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


ROOT = Path("/opt/chihiros-addon-ui")
SOURCE_ROOT = Path(os.environ.get("CHIHIROS_SOURCE_ROOT", "/opt/chihiros-src"))
CONFIG_ROOT = Path(os.environ.get("HASS_CONFIG", "/config"))
DEFAULT_STATE_DB_PATH = Path(
    os.environ.get("CHIHIROS_STATE_DB", str(CONFIG_ROOT / ".chihiros" / "chihiros_state.sqlite3"))
)
HA_STORAGE = CONFIG_ROOT / ".storage"
SETTINGS_PATH = Path(os.environ.get("CHIHIROS_DASHBOARD_SETTINGS", "/data/dashboard_settings.json"))
PLUGIN_ASSET_ROOT = CONFIG_ROOT / ".chihiros" / "plugins"
DEFAULT_CHANNELS = [
    {"id": 1, "name": "Nitrat", "color": "#2ea8ff"},
    {"id": 2, "name": "Phosphat", "color": "#39d353"},
    {"id": 3, "name": "Eisen", "color": "#ff9300"},
    {"id": 4, "name": "Kalium", "color": "#a855f7"},
]
CORE_TABS = ["led", "config"]
SOURCE_PLUGIN_ROOT = SOURCE_ROOT / "custom_components" / "chihiros" / "plugins"
CORE_PLUGIN_KINDS = ["doser", "ruehrer", "heizer", "wireshark", "ctl"]
ADDON_PREFIX = "8ea2de0f_"
PLUGIN_TABS = {
    "core": CORE_TABS,
    "ctl": ["ctl", "config"],
    "doser": ["doser", "config"],
    "ruehrer": ["ruehrer", "config"],
    "heizer": ["heizer", "config"],
}
_PLUGIN_INSTALL_CACHE: tuple[float, list[str]] = (0.0, [])
_PLUGIN_BACKEND_CACHE: dict[str, object] = {}
def plugin_kind() -> str:
    """Return the add-on plugin kind."""
    value = str(os.environ.get("CHIHIROS_PLUGIN_KIND") or "core").strip().lower()
    if value == "core":
        return "core"
    return re.sub(r"[^a-z0-9_]+", "", value) or "core"


def plugin_tabs() -> list[str]:
    """Return tabs enabled for this add-on."""
    kind = plugin_kind()
    if kind != "core":
        return list(PLUGIN_TABS.get(kind, [kind, "config"]))
    installed = set(installed_plugin_kinds())
    ordered = ["led", *[kind for kind in CORE_PLUGIN_KINDS if kind in installed], "config"]
    return ordered


def installed_plugin_kinds() -> list[str]:
    """Return plugin modules bundled with the single Core add-on."""
    global _PLUGIN_INSTALL_CACHE
    now = time.monotonic()
    cached_at, cached = _PLUGIN_INSTALL_CACHE
    if now - cached_at < 10:
        return list(cached)
    bundled = [
        kind for kind in CORE_PLUGIN_KINDS if (SOURCE_PLUGIN_ROOT / kind / "www" / f"{kind}-plugin.js").is_file()
    ]
    configured = [
        re.sub(r"[^a-z0-9_]+", "", item.strip().lower())
        for item in str(os.environ.get("CHIHIROS_ENABLED_PLUGINS") or "").split(",")
        if item.strip()
    ]
    installed = [*bundled, *[item for item in configured if item]]
    seen: set[str] = set()
    deduped: list[str] = []
    for kind in installed:
        if kind in seen:
            continue
        seen.add(kind)
        deduped.append(kind)
    _PLUGIN_INSTALL_CACHE = (now, deduped)
    return list(deduped)


def plugin_assets() -> dict[str, dict[str, object]]:
    """Return browser-loadable plugin asset modules."""
    assets: dict[str, dict[str, object]] = {}
    kinds = installed_plugin_kinds()
    seen: set[str] = set()
    for kind in kinds:
        if kind in seen:
            continue
        seen.add(kind)
        module_path = SOURCE_PLUGIN_ROOT / kind / "www" / f"{kind}-plugin.js"
        if not module_path.is_file():
            module_path = PLUGIN_ASSET_ROOT / kind / f"{kind}-plugin.js"
        if module_path.is_file():
            assets[kind] = {
                "module": f"./plugins/{kind}/{kind}-plugin.js",
                "mtime": int(module_path.stat().st_mtime),
            }
    return assets


def plugin_backend(kind: str) -> object:
    """Load a plugin backend module without keeping plugin code in core."""
    key = re.sub(r"[^a-z0-9_]+", "", kind.lower())
    if not key:
        raise RuntimeError("Plugin name fehlt")
    if key in _PLUGIN_BACKEND_CACHE:
        return _PLUGIN_BACKEND_CACHE[key]

    candidates = [
        SOURCE_ROOT / "custom_components" / "chihiros" / "plugins" / key / "backend.py",
        Path.cwd() / "custom_components" / "chihiros" / "plugins" / key / "backend.py",
        PLUGIN_ASSET_ROOT / key / "backend.py",
    ]
    backend_path = next((path for path in candidates if path.is_file()), None)
    if backend_path is None:
        raise RuntimeError(f"Plugin Backend nicht gefunden: {key}")

    spec = importlib.util.spec_from_file_location(f"chihiros_{key}_plugin_backend", backend_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Plugin Backend kann nicht geladen werden: {backend_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _PLUGIN_BACKEND_CACHE[key] = module
    return module


def call_plugin_backend(kind: str, function_name: str, *args: object) -> object:
    """Call a function from a plugin backend module."""
    backend = plugin_backend(kind)
    func = getattr(backend, function_name, None)
    if not callable(func):
        raise RuntimeError(f"Plugin Funktion fehlt: {kind}.{function_name}")
    return func(*args)


def addon_info_is_installed(data: dict[str, object]) -> bool:
    """Return true only for add-ons installed on this Home Assistant host."""
    if data.get("installed") is True:
        return True
    state = str(data.get("state") or "").strip().lower()
    if state in {"started", "stopped", "startup", "shutdown", "error"}:
        return True
    return bool(data.get("version")) and bool(data.get("options"))


def plugin_title() -> str:
    """Return the display title for this add-on."""
    titles = {
        "core": "LED Core",
        "doser": "Chihiros Doser",
        "ruehrer": "Chihiros Ruehrer",
        "heizer": "Chihiros Heizer",
    }
    kind = plugin_kind()
    if kind == "core":
        return titles["core"]
    return titles.get(kind, f"Chihiros {kind.replace('_', ' ').title()}")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
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
        if parsed.path == "/api/dashboard-state":
            self.send_json(200, build_dashboard_state())
            return
        if parsed.path == "/api/ha-state":
            params = parse_qs(parsed.query)
            self.read_ha_state(str((params.get("entity_id") or [""])[0]).strip())
            return
        if parsed.path == "/api/dashboard-settings":
            self.send_json(200, dashboard_settings())
            return
        if parsed.path == "/api/database-status":
            params = parse_qs(parsed.query)
            device = str((params.get("device") or [""])[0]).strip()
            self.send_json(200, database_diagnostics_status(device))
            return
        if parsed.path == "/api/led-device-status":
            params = parse_qs(parsed.query)
            device = str((params.get("device") or [""])[0]).strip()
            self.send_json(200, {"status": led_device_status(device)})
            return
        if parsed.path in ("/api/history", "/api/led-history"):
            params = parse_qs(parsed.query)
            device = str((params.get("device") or [""])[0]).strip()
            limit_text = str((params.get("limit") or ["200"])[0]).strip()
            scope = "led" if parsed.path == "/api/led-history" else str((params.get("scope") or [""])[0]).strip()
            try:
                limit = max(1, min(500, int(limit_text)))
            except ValueError:
                limit = 200
            self.send_json(200, {"entries": history_action_entries(device, limit, scope)})
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/ctl":
            self.run_ctl(self.read_json())
            return
        if parsed.path == "/api/dashboard-settings":
            self.save_dashboard_settings(self.read_json())
            return
        if parsed.path == "/api/ha-service":
            self.call_ha_service(self.read_json())
            return
        if parsed.path == "/api/led-schedule-local":
            self.save_led_schedule_local(self.read_json())
            return
        if parsed.path == "/api/led-device-status":
            self.save_led_device_status(self.read_json())
            return
        if parsed.path in ("/api/history", "/api/led-history"):
            self.save_history(self.read_json(), default_scope="led" if parsed.path == "/api/led-history" else "")
            return
        if parsed.path == "/api/plugin-backend":
            self.run_plugin_backend(self.read_json())
            return
        if parsed.path == "/api/addon-refresh":
            self.refresh_addon_update_source(self.read_json())
            return
        self.send_json(404, {"message": "Not found"})

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
        except subprocess.TimeoutExpired:
            self.send_json(504, {"message": "Command timed out"})
            return

        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        self.send_json(
            200 if result.returncode == 0 else 500,
            {"returncode": result.returncode, "output": output or "(no output)"},
        )

    def run_plugin_backend(self, body: bytes) -> None:
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json(400, {"message": "Invalid JSON"})
            return
        plugin = re.sub(r"[^a-z0-9_]+", "", str(data.get("plugin") or "").strip().lower())
        function = re.sub(r"[^a-zA-Z0-9_]+", "", str(data.get("function") or "").strip())
        args = data.get("args", [])
        if not plugin or not function:
            self.send_json(400, {"message": "Plugin oder Funktion fehlt"})
            return
        if not isinstance(args, list):
            self.send_json(400, {"message": "args muss eine Liste sein"})
            return
        try:
            result = call_plugin_backend(plugin, function, *args)
        except ValueError as err:
            self.send_json(400, {"message": str(err)})
            return
        except RuntimeError as err:
            self.send_json(500, {"message": str(err)})
            return
        self.send_json(200, result if isinstance(result, dict) else {"result": result})

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
            root = SOURCE_PLUGIN_ROOT
            path = path.removeprefix("plugins/")
            allowed_roots = [SOURCE_PLUGIN_ROOT.resolve(), PLUGIN_ASSET_ROOT.resolve()]
        target = (root / path).resolve()
        if (
            path.startswith("ctl/")
            or path.startswith("doser/")
            or path.startswith("ruehrer/")
            or path.startswith("heizer/")
            or path.startswith("wireshark/")
        ):
            if not target.is_file():
                parts = path.split("/", 1)
                if len(parts) == 2 and parts[1] == f"{parts[0]}-plugin.js":
                    source_fallback = (SOURCE_PLUGIN_ROOT / parts[0] / "www" / parts[1]).resolve()
                    if source_fallback.is_file():
                        target = source_fallback
                if not target.is_file():
                    fallback = (PLUGIN_ASSET_ROOT / path).resolve()
                    if fallback.is_file():
                        target = fallback
        if not target.is_file() or not any(str(target).startswith(str(allowed)) for allowed in allowed_roots):
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


def entity_prefix(address: str) -> str:
    compact = re.sub(r"[^a-z0-9]", "", address.lower())
    if compact.startswith(("dydose", "dytdos")):
        return compact
    return f"dydose{compact}" if compact else "dydosedoser1"


def doser_display_alias(address: str, fallback: str) -> str:
    compact = re.sub(r"[^A-Z0-9]", "", address.upper())
    match = re.match(r"^(DYDOSE[A-Z]{2}|DYTDOS[A-Z]{2})", compact)
    return match.group(1) if match else fallback


def channel_slug(ch_id: int, name: str) -> str:
    suffix = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"ch{ch_id}_{suffix}" if suffix else f"ch{ch_id}"


def parse_ts(value: str) -> tuple[str, str]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.date().isoformat(), parsed.strftime("%H:%M:%S")
    except ValueError:
        return "", ""


def _history_sort_key(entry: dict[str, object]) -> str:
    return str(entry.get("ts") or f"{entry.get('date', '')}T{entry.get('time', '')}")


def latest_auto_totals(device: str) -> list[float]:
    values = [0.0, 0.0, 0.0, 0.0]
    seen: set[int] = set()
    for row in sqlite_rows(
        """
        SELECT channel, ml
        FROM doser_auto_totals
        WHERE device_key=?
        ORDER BY day DESC, updated_at DESC, mode DESC
        """,
        (device.upper(),),
    ):
        channel = int(row.get("channel", -1))
        if 0 <= channel < 4 and channel not in seen:
            values[channel] = float(row.get("ml") or 0.0)
            seen.add(channel)
    return values


def schedule_by_channel(device: str) -> dict[int, dict[str, object]]:
    schedules: dict[int, dict[str, object]] = {}
    for row in sqlite_rows(
        """
        SELECT *
        FROM doser_schedules
        WHERE device_key=?
        ORDER BY channel, updated_at DESC, schedule_time
        """,
        (device.upper(),),
    ):
        channel = int(row.get("channel", -1))
        if 0 <= channel < 4 and channel not in schedules:
            schedules[channel] = row
    return schedules


def history_entries(device: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for row in sqlite_rows(
        """
        SELECT ts, action, channel AS ch, params_json, status, output
        FROM actions
        WHERE UPPER(device_address)=UPPER(?) OR UPPER(device_alias)=UPPER(?)
        ORDER BY id DESC
        LIMIT 120
        """,
        (device, device),
    ):
        date_text, time_text = parse_ts(str(row.get("ts") or ""))
        channel = row.get("ch")
        entry: dict[str, object] = {
            "ts": str(row.get("ts") or ""),
            "date": date_text,
            "time": time_text,
            "action": str(row.get("action") or ""),
            "detail": str(row.get("output") or row.get("status") or ""),
            "status": str(row.get("status") or ""),
        }
        if channel is not None:
            try:
                entry["pump"] = int(channel) + 1
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

    for row in sqlite_rows(
        """
        SELECT ts, channel AS ch, ml
        FROM manual_history
        WHERE device_key=?
        ORDER BY id DESC
        LIMIT 80
        """,
        (device.upper(),),
    ):
        date_text, time_text = parse_ts(str(row.get("ts") or ""))
        channel = int(row.get("ch") or 0)
        ml = float(row.get("ml") or 0.0)
        entries.append(
            {
                "date": date_text,
                "time": time_text,
                "ts": str(row.get("ts") or ""),
                "pump": channel + 1,
                "action": "Manuelle Dosierung",
                "detail": f"{ml:.1f} mL",
            }
        )
    ext = load_doser_ext_store(device)
    raw = ext.get("action_log", [])
    if isinstance(raw, list):
        entries.extend(entry for entry in raw[:80] if isinstance(entry, dict))

    seen: set[tuple[str, str, object, str]] = set()
    deduped: list[dict[str, object]] = []
    for entry in sorted(entries, key=_history_sort_key, reverse=True):
        key = (
            str(entry.get("ts") or entry.get("date") or ""),
            str(entry.get("action") or ""),
            entry.get("pump"),
            str(entry.get("detail") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped[:80]


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


def doser_devices() -> list[dict[str, object]]:
    settings = dashboard_settings()
    if settings.get("mode") == "custom":
        rows = sqlite_devices()
        if not rows:
            rows = ha_chihiros_doser_entries()
    else:
        rows = ha_chihiros_doser_entries()
        if not rows:
            rows = sqlite_devices()
    devices = []
    for index, row in enumerate(rows[:4], start=1):
        address = str(row.get("address") or row.get("alias") or f"doser_{index}")
        names = local_channel_names(address)
        channels = [
            {**channel, "name": str(names.get(channel["id"] - 1) or channel["name"])} for channel in DEFAULT_CHANNELS
        ]
        devices.append(
            {
                "id": str(row.get("alias") or f"doser_{index}"),
                "label": str(row.get("label") or f"Geraet {index}"),
                "name": str(row.get("label") or row.get("alias") or f"Doser {index}"),
                "address": address,
                "model": str(row.get("model") or "Dosing Pump"),
                "entity_prefix": entity_prefix(address),
                "container_full_ml": 500,
                "entities": {},
                "channels": channels,
            }
        )
    return devices


def build_dashboard_state() -> dict[str, object]:
    states: dict[str, dict[str, object]] = {}
    settings = dashboard_settings()
    settings["templates"] = led_templates()
    settings["led_schedules"] = {}
    settings["led_device_status"] = {}
    led_addresses: set[str] = set()
    devices = doser_devices()
    for device in devices:
        address = str(device["address"])
        prefix = str(device["entity_prefix"])
        ext = load_doser_ext_store(address)
        containers = container_values(address, ext)
        manual = manual_daily_values(address, ext)
        auto = latest_auto_totals(address)
        schedules = schedule_by_channel(address)
        channels = list(device["channels"])  # type: ignore[arg-type]

        for channel in channels:
            ch_id = int(channel["id"])
            index = ch_id - 1
            slug = channel_slug(ch_id, str(channel["name"]))
            schedule = schedules.get(index, {})
            schedule_time = str(schedule.get("schedule_time") or "Unbekannt")
            schedule_amount = float(schedule.get("dose_ml") or 0.0)
            schedule_type_id = int(schedule.get("schedule_type_id") or 1)
            active = bool(schedule.get("enabled", False))
            remaining = float(containers.get(str(index), 0.0))
            auto_ml = float(auto[index])
            manual_ml = float(manual[index])
            daily_ml = auto_ml + manual_ml

            states[f"sensor.{prefix}_{slug}_daily_dose"] = state_obj(f"{daily_ml:.1f}", "mL")
            states[f"sensor.{prefix}_{slug}_auto_daily_dose"] = state_obj(f"{auto_ml:.1f}", "mL")
            states[f"sensor.{prefix}_{slug}_manual_daily_dose"] = state_obj(f"{manual_ml:.1f}", "mL")
            states[f"sensor.{prefix}_{slug}_remaining"] = state_obj(f"{remaining:.1f}", "mL")
            states[f"sensor.{prefix}_{slug}_schedule_time"] = state_obj(
                schedule_time,
                schedule_type_id=schedule_type_id,
                schedule_kind=str(schedule.get("schedule_kind") or "single_dose"),
            )
            states[f"sensor.{prefix}_{slug}_schedule_amount"] = state_obj(f"{schedule_amount:.1f}", "mL")
            states[f"switch.{prefix}_{slug}_schedule_active"] = state_obj("on" if active else "off")
            states[f"number.{prefix}_{slug}_schedule_amount"] = state_obj(f"{schedule_amount:.1f}", "mL")
            states[f"number.{prefix}_{slug}_remaining_volume"] = state_obj(f"{remaining:.1f}", "mL")
            states[f"number.{prefix}_pump_{ch_id}_dose_volume"] = state_obj("1.0", "mL")
            states[f"button.{prefix}_dose_pump_{ch_id}"] = state_obj("unknown")
            states[f"button.{prefix}_{slug}_reset_schedule"] = state_obj("unknown")
            states[f"button.{prefix}_{slug}_start_calibration"] = state_obj("unknown")

        states[f"sensor.{prefix}_doser_history"] = state_obj(
            "OK",
            entries=history_entries(address),
            low_container_push_enabled=False,
            low_container_push_targets=[],
        )
        states[f"sensor.{prefix}_doser_timer_status"] = state_obj("OK")
        states[f"switch.{prefix}_low_container_notification"] = state_obj("off")

    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if token:
        try:
            ha_states = homeassistant_request("GET", "/api/states", token)
            if isinstance(ha_states, list):
                for item in ha_states:
                    if not isinstance(item, dict):
                        continue
                    entity_id = str(item.get("entity_id") or "")
                    domain = entity_id.split(".", 1)[0]
                    if domain not in {"light", "switch", "button", "number", "sensor", "binary_sensor", "climate"}:
                        continue
                    attrs = item.get("attributes", {})
                    friendly = str(attrs.get("friendly_name") if isinstance(attrs, dict) else "")
                    haystack = f"{entity_id} {friendly}".lower()
                    is_non_led_device = any(
                        key in haystack
                        for key in ("doser", "dosing", "dose", "pump", "ruehrer", "rührer", "stirrer", "mixer", "mix")
                    )
                    color = str(attrs.get("color") if isinstance(attrs, dict) else "").lower()
                    is_chihiros_light = domain == "light" and (
                        not is_non_led_device
                        and (
                            color in {"red", "green", "blue", "white"}
                            or bool(
                                re.match(
                                    r"^light\.[a-z0-9]*[0-9a-f]{12}_(red|green|blue|white)$", entity_id, re.IGNORECASE
                                )
                            )
                        )
                    )
                    is_chihiros_led_entity = bool(
                        not is_non_led_device
                        and re.match(
                            r"^(light|switch|sensor)\.[a-z0-9]*[0-9a-f]{12}_(red|green|blue|white|power|auto_mode|schedule|firmware_version|runtime|runtime_minutes|last_notification)$",
                            entity_id,
                            re.IGNORECASE,
                        )
                    )
                    is_chihiros_doser_entity = any(
                        key in haystack
                        for key in (
                            "doser",
                            "dosing",
                            "dydose",
                            "dytdos",
                            "dose_pump",
                            "dose_volume",
                            "daily_dose",
                            "dosed_today",
                            "manual_daily_dose",
                            "auto_daily_dose",
                            "remaining_volume",
                            "schedule_amount",
                            "schedule_time",
                            "schedule_active",
                            "pump_",
                        )
                    )
                    # The add-on already exposes one canonical Doser state set from its local database above.
                    # Importing the integration's differently named Doser entities creates a second, empty device tab.
                    if is_chihiros_doser_entity:
                        continue
                    if not (
                        is_chihiros_light
                        or is_chihiros_led_entity
                        or any(key in haystack for key in ("chihiros", "ruehrer", "stirrer", "heizer"))
                    ):
                        continue
                    states[entity_id] = {
                        "state": str(item.get("state") or "unknown"),
                        "attributes": attrs if isinstance(attrs, dict) else {},
                        "last_changed": str(item.get("last_changed") or ""),
                        "last_updated": str(item.get("last_updated") or ""),
                    }
                    match = re.match(
                        r"^(light|switch|sensor)\.([a-z0-9]*[0-9a-f]{12})_(red|green|blue|white|power|auto_mode|schedule|firmware_version|runtime|runtime_minutes|last_notification)$",
                        entity_id,
                        re.IGNORECASE,
                    )
                    if match:
                        address = ":".join(match.group(2)[-12:][index : index + 2] for index in range(0, 12, 2)).upper()
                        if address:
                            led_addresses.add(address)
        except ValueError:
            pass
        try:
            update_state = homeassistant_request("GET", "/api/states/update.chihiros_beta_update", token)
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
        "devices": devices,
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
    columns = {str(row.get("name") or "") for row in sqlite_rows_with_conn(conn, "PRAGMA table_info(led_device_status)")}
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
            end_date = schedule_date if (end_hour, end_minute) > (start_hour, start_minute) else schedule_date + timedelta(days=1)
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
    mode = str(data.get("mode") or "hass").strip().lower()
    if mode not in {"hass", "custom"}:
        raise ValueError("mode must be hass or custom")
    state_db = str(data.get("state_db_path") or DEFAULT_STATE_DB_PATH).strip()
    if mode == "custom" and not state_db:
        raise ValueError("state_db_path is required for custom mode")
    return {
        "mode": mode,
        "state_db_path": state_db or str(DEFAULT_STATE_DB_PATH),
        "database_diagnostics_enabled": bool(data.get("database_diagnostics_enabled", False)),
    }


def dashboard_settings() -> dict[str, object]:
    settings = normalize_dashboard_settings(read_json_file(SETTINGS_PATH))
    settings["effective_state_db_path"] = str(current_state_db_path(settings))
    settings["hass_state_db_path"] = str(DEFAULT_STATE_DB_PATH)
    return settings


def current_state_db_path(settings: dict[str, object] | None = None) -> Path:
    selected = settings or normalize_dashboard_settings(read_json_file(SETTINGS_PATH))
    if selected.get("mode") == "custom":
        return Path(str(selected.get("state_db_path") or DEFAULT_STATE_DB_PATH))
    return DEFAULT_STATE_DB_PATH


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


def ha_chihiros_doser_entries() -> list[dict[str, object]]:
    data = read_json_file(HA_STORAGE / "core.config_entries")
    entries = data.get("data", {}).get("entries", []) if isinstance(data.get("data"), dict) else []
    rows = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or entry.get("domain") != "chihiros":
            continue
        entry_data = entry.get("data", {})
        if not isinstance(entry_data, dict):
            continue
        address = str(entry_data.get("address") or "").strip()
        if not address:
            continue
        pump_count = int(entry_data.get("pump_count") or entry_data.get("dosing_pump_count") or 0)
        model_text = " ".join(
            [
                address,
                str(entry.get("title") or ""),
                *(str(entry_data.get(key) or "") for key in ("device_type", "model", "model_name", "name")),
            ]
        ).lower()
        is_doser_entry = any(key in model_text for key in ("doser", "dosing", "dose", "pump", "dydose", "dytdos"))
        if pump_count <= 0 and not is_doser_entry and not has_doser_state(address):
            continue
        alias = doser_display_alias(address, f"doser_{len(rows) + 1}")
        rows.append(
            {
                "alias": alias,
                "address": address.upper(),
                "label": str(entry.get("title") or entry_data.get("name") or alias),
                "model": str(entry_data.get("device_type") or "Dosing Pump"),
            }
        )
    return rows


def has_doser_state(address: str) -> bool:
    key = address.upper()
    if sqlite_rows("SELECT 1 FROM containers WHERE device_key=? LIMIT 1", (key,)):
        return True
    if sqlite_rows("SELECT 1 FROM doser_schedules WHERE device_key=? LIMIT 1", (key,)):
        return True
    if sqlite_rows("SELECT 1 FROM doser_auto_totals WHERE device_key=? LIMIT 1", (key,)):
        return True
    return bool(load_doser_ext_store(address))


def sqlite_devices() -> list[dict[str, object]]:
    rows = sqlite_rows(
        """
        SELECT DISTINCT device_key AS address FROM containers
        UNION
        SELECT DISTINCT device_key AS address FROM doser_schedules
        UNION
        SELECT DISTINCT device_key AS address FROM doser_auto_totals
        UNION
        SELECT DISTINCT device_key AS address FROM manual_history
        ORDER BY address
        """
    )
    return [
        {"alias": f"doser_{index}", "address": str(row["address"]), "label": f"Geraet {index}", "model": "Dosing Pump"}
        for index, row in enumerate(rows, start=1)
        if row.get("address")
    ]


def load_doser_ext_store(address: str) -> dict[str, object]:
    key = address.upper().lower().replace(":", "_")
    raw = read_json_file(HA_STORAGE / f"chihiros_doser_ext_{key}")
    data = raw.get("data", raw)
    return data if isinstance(data, dict) else {}


def local_channel_names(address: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for row in sqlite_rows(
        "SELECT key, value FROM ctl_settings WHERE key LIKE ?",
        (f"channel_name.doser.{address.upper()}.%",),
    ):
        try:
            out[int(str(row.get("key", "")).rsplit(".", 1)[-1])] = str(row.get("value", ""))
        except (TypeError, ValueError):
            continue
    return out


def container_values(address: str, ext: dict[str, object]) -> dict[str, float]:
    values = {str(index): 500.0 for index in range(4)}
    raw = ext.get("containers_ml")
    if isinstance(raw, dict):
        for key, value in raw.items():
            values[str(key)] = float(value or 0.0)
    for row in sqlite_rows(
        "SELECT channel, volume_ml FROM containers WHERE device_key=? ORDER BY channel",
        (address.upper(),),
    ):
        values[str(int(row["channel"]))] = float(row.get("volume_ml") or 0.0)
    return values


def manual_daily_values(address: str, ext: dict[str, object]) -> list[float]:
    values = [0.0, 0.0, 0.0, 0.0]
    raw = ext.get("manual_daily_ml")
    if isinstance(raw, dict):
        for key, value in raw.items():
            try:
                channel = int(key)
            except (TypeError, ValueError):
                continue
            if 0 <= channel < 4:
                values[channel] = float(value or 0.0)
    today = datetime.now().date().isoformat()
    for row in sqlite_rows(
        "SELECT channel, ml FROM manual_daily WHERE device_key=? AND day=?",
        (address.upper(), today),
    ):
        channel = int(row.get("channel", -1))
        if 0 <= channel < 4:
            values[channel] = float(row.get("ml") or 0.0)
    return values


if __name__ == "__main__":
    port = int(os.environ.get("CHIHIROS_UI_PORT") or "8099")
    threading.Thread(target=led_status_reconcile_loop, name="led-status-reconcile", daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"{plugin_title()} web UI listening on port {port}")
    server.serve_forever()
