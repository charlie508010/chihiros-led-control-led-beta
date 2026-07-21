"""Regression contracts for the dependency-free LED dashboard frontend."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LED_DASHBOARD = ROOT / "custom_components/chihiros/plugins/led/dashboard"
LED_PANEL = LED_DASHBOARD / "panels/chihiros-led-panel.js"
DASHBOARD = LED_DASHBOARD / "chihiros-led-core-card.js"
ADDON_SERVER = ROOT / "chihiros_beta/ui/server.py"
ADDON_INDEX = ROOT / "chihiros_beta/ui/index.html"
ADDON_RUN = ROOT / "chihiros_beta/run.sh"
ADDON_CONFIG = ROOT / "chihiros_beta/config.yaml"
LED_SERVICES = ROOT / "custom_components/chihiros/plugins/led/services/runtime.py"


def source(path: Path) -> str:
    """Read one dashboard source file."""
    return path.read_text(encoding="utf-8")


def test_led_services_do_not_depend_on_removed_doser_state() -> None:
    """LED-only service validation must use model channels, never Doser runtime fields."""
    services = source(LED_SERVICES)

    assert "dosing_totals" not in services
    assert 'getattr(model, "color_channels", None)' in services


def test_addon_icon_fallback_renders_real_svg_symbols() -> None:
    """The standalone add-on must render LED icons without Home Assistant's ha-icon component."""
    index = source(ADDON_INDEX)

    assert 'const iconShapes = {' in index
    assert 'observedAttributes() { return ["icon"]; }' in index
    assert 'this.innerHTML = `<svg viewBox="0 0 24 24"' in index
    assert 'ha-icon::after' not in index


def test_private_addon_update_installs_the_supervisor_release_or_refreshes_the_runtime() -> None:
    """The update endpoint must install a release and retain the token-backed runtime fallback."""
    dashboard = source(DASHBOARD)
    index = source(ADDON_INDEX)
    server = source(ADDON_SERVER)
    run = source(ADDON_RUN)

    assert 'data-addon-update' in dashboard
    assert 'fetch("./api/addon-update"' in index
    assert 'if request_path == "/api/addon-update":' in server
    assert 'supervisor_request("GET", "/addons/self/info", token)' in server
    assert "source_commit = github_source_commit()" in server
    assert 'f"/addons/{slug}/update" if update_available else "/addons/self/restart"' in server
    assert 'echo "LED Core source commit: ${SOURCE_COMMIT}"' in run
    assert 'export CHIHIROS_SOURCE_COMMIT="${SOURCE_COMMIT}"' in run
    assert "cp -a /opt/chihiros-led-core-src/chihiros_beta/ui/. /opt/chihiros-led-core-ui/" in run


def test_led_core_update_prefers_the_home_assistant_update_entity() -> None:
    """The dashboard must verify service failures instead of displaying an unconditional success message."""
    dashboard = source(DASHBOARD)

    assert 'const updateEntities = ["update.led_core_update", "update.chihiros_core_update"]' in dashboard
    assert 'this._hass.callService("homeassistant", "update_entity"' in dashboard
    assert 'this._hass.callService("update", "install"' in dashboard
    assert "if (refreshError) throw new Error" in dashboard
    assert "if (installError) throw new Error" in dashboard
    assert 'message.includes("502")' in dashboard
    assert "installed === latest" in dashboard


def test_led_discovery_prefers_the_exact_color_entity_alias() -> None:
    """Multiple HA aliases for a color must still resolve to one physical LED channel."""
    panel = source(LED_PANEL)

    assert 'suffix: match ? match[3] : ""' in panel
    assert "Number(left.suffix !== left.color) - Number(right.suffix !== right.color)" in panel
    assert "group.channels.findIndex((existing) => existing.key === channel.key)" in panel


def test_led_core_addon_ignores_a_persisted_legacy_source_repository() -> None:
    """An old add-on option must never load the former combined dashboard."""
    run = source(ADDON_RUN)

    assert 'CANONICAL_SOURCE_REPOSITORY="https://github.com/charlie508010/chihiros-led-control-led-beta.git"' in run
    assert 'SOURCE_REPOSITORY="${CANONICAL_SOURCE_REPOSITORY}"' in run
    assert '"CONFIGURED_SOURCE_REPOSITORY": str(' in run
    assert "Ignoring legacy source_repository" in run


def test_led_core_addon_uses_its_own_ingress_port() -> None:
    """LED Core must not collide with the former combined add-on on port 8099."""
    config = source(ADDON_CONFIG)
    run = source(ADDON_RUN)

    assert "ingress_port: 8109" in config
    assert "webui: http://[HOST]:[PORT:8109]/" in config
    assert 'export CHIHIROS_UI_PORT="${CHIHIROS_UI_PORT:-8109}"' in run


def test_led_core_server_accepts_double_slash_ingress_api_paths() -> None:
    """Ingress may forward //api paths, which must reach the normal API handlers."""
    server = source(ADDON_SERVER)

    assert server.count('request_path = f"/{parsed.path.lstrip(\'/\')}"') == 2
    assert 'if request_path == "/api/dashboard-state":' in server
    assert 'if request_path == "/api/dashboard-settings":' in server
    assert 'if request_path == "/api/ha-service":' in server


def test_led_core_uses_dedicated_opt_paths() -> None:
    """LED Core runtime files must not share generic paths with the combined add-on."""
    dockerfile = source(ROOT / "chihiros_beta" / "Dockerfile")
    run = source(ADDON_RUN)
    server = source(ADDON_SERVER)
    runner = source(ROOT / "chihiros_beta" / "ui" / "chihirosctl_runner.py")
    combined = "\n".join((dockerfile, run, server, runner))

    assert "/opt/chihiros-led-core-src" in combined
    assert "/opt/chihiros-led-core-ui" in combined
    assert "/opt/chihiros-led-core-venv" in combined
    assert "/opt/chihiros-src" not in combined
    assert "/opt/chihiros-addon-ui" not in combined
    assert "/opt/chihiros-venv" not in combined
    assert "Chihiros Beta add-on is running." not in run
    assert 'os.environ.get("CHIHIROS_UI_PORT") or "8109"' in server


def test_led_core_uses_an_isolated_home_assistant_namespace() -> None:
    """The separated LED integration must coexist with the combined Chihiros integration."""
    manifest = source(ROOT / "custom_components" / "chihiros" / "manifest.json")
    constants = source(ROOT / "custom_components" / "chihiros" / "const.py")
    integration = source(
        ROOT / "custom_components" / "chihiros" / "plugins" / "led" / "integration.py"
    )
    dashboard = source(DASHBOARD)
    panel = source(LED_DASHBOARD / "chihiros-panel.js")
    run = source(ADDON_RUN)

    assert '"domain": "chihiros_led_core"' in manifest
    assert 'DOMAIN = "chihiros_led_core"' in constants
    assert 'FRONTEND_STATIC_URL = "/chihiros_led_core_static"' in integration
    assert 'FRONTEND_PANEL_URL = "chihiros-led-core"' in integration
    assert '"name": "chihiros-led-core-panel"' in integration
    assert 'customElements.define("chihiros-led-core-panel"' in panel
    assert 'domain: "chihiros_led_core"' in dashboard
    assert 'callService("chihiros_led_core"' in dashboard
    assert '/config/custom_components/chihiros_led_core' in run
    assert '/config/.chihiros_led_core/chihiros_led_core.sqlite3' in run
    assert 'rm -rf /config/custom_components/chihiros' not in run


def test_led_core_update_button_uses_the_supervisor_update_flow() -> None:
    """The visible update button installs a Supervisor release and waits for ingress to return."""
    dashboard = source(DASHBOARD)
    server = source(ADDON_SERVER)
    index = source(ADDON_INDEX)

    assert 'typeof api.runAddonUpdate !== "function"' in dashboard
    assert "const result = await api.runAddonUpdate();" in dashboard
    assert 'fetch("./api/addon-update"' in index
    assert 'if request_path == "/api/addon-update":' in server
    assert "source_commit = github_source_commit()" in server
    assert '"Authorization": f"Bearer {github_token}"' in server
    assert 'for path in ("/store/reload", "/addons/reload"):' in server
    assert 'supervisor_request("POST", path, token)' in server
    assert 'f"/addons/{slug}/update" if update_available else "/addons/self/restart"' in server
    assert "reloadWhenReady();" in index
    assert "await this.runAddonUpdate();" in dashboard


def test_led_device_selection_and_confirmed_reset_keep_the_original_target() -> None:
    """Transient HA state updates and confirmation delays must not retarget LED actions."""
    dashboard = source(DASHBOARD)
    panel = source(LED_PANEL)

    assert "const previousLedDevice = this.activeLedDevice || null;" in dashboard
    assert "this.ledDevices = [...this.ledDevices, previousLedDevice];" in dashboard
    assert "const selectedLedDevice = this.ledDevices.find" in dashboard
    assert "applyLedDevice(deviceId, fallback = true)" in panel
    assert "if (!device && !fallback) return this.activeLedDevice || null;" in panel
    assert "targetDevice = this.activeLedDevice || {}" in panel
    assert "...this.ledServiceSelector(targetDevice)" in panel
    assert "this.resetLedDeviceSchedule(this._ledScheduleResetDebug, targetDevice)" in panel


def test_led_notification_dialog_keeps_the_selected_device_target() -> None:
    """A state refresh must not retarget an already opened notification dialog."""
    panel = source(LED_PANEL)

    assert 'notificationEntity: this.resolveLedNotificationEntity(device)' in panel
    assert 'ledDeviceAddress: String(device.address || "").trim().toUpperCase()' in panel
    assert 'const entity = String(this.dialogState && this.dialogState.notificationEntity || "");' in panel
    assert 'if (!addressToken) return "";' in panel
    assert 'const entityToken = normalized.replace(/[^a-f0-9]/g, "");' in panel
    assert "&& entityToken.includes(addressToken);" in panel


def test_parallel_led_core_entities_accept_home_assistant_numeric_suffixes() -> None:
    """A parallel integration must discover entity ids ending in _2, _3, and later suffixes."""
    server = source(ADDON_SERVER)
    panel = source(LED_PANEL)

    assert 'r"(?:_\\d+)?$"' in server
    assert '(red|green|blue|white)(?:_\\d+)?$' in panel
    assert 'const suffix = rawSuffix.replace(/_\\d+$/, "");' in panel
    assert "isNonLedEntity" not in panel


def test_led_device_tabs_deduplicate_parallel_entities_by_mac_address() -> None:
    """Different entity prefixes for the same MAC must remain one physical LED device."""
    panel = source(LED_PANEL)

    assert 'const deviceKey = (slug) =>' in panel
    assert 'return hex ? hex[0].toLowerCase() : "";' in panel
    assert 'const deviceSlug = deviceKey(rawDeviceSlug);' in panel
    assert 'deviceSlug: match ? deviceKey(match[2]) : "led_1"' in panel
    assert 'group.channels.findIndex((existing) => existing.key === channel.key)' in panel


def test_led_device_tabs_use_the_shared_styled_navigation() -> None:
    """LED device selectors must not fall back to unstyled browser buttons."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert '<nav class="doser-device-tabs"' in panel
    assert ".doser-device-tabs button" in dashboard
    assert ".doser-device-tabs button.active" in dashboard


def test_led_device_name_is_editable_and_used_by_the_device_tab() -> None:
    """A locally persisted device name must be rendered in the device selector."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert "ledDeviceDisplayName(device)" in panel
    assert 'data-action="led-device-name-edit"' in panel
    assert 'data-led-device-name' in panel
    assert 'type: "led-device-name-editor"' in panel
    assert "ledDeviceNameDialog()" in panel
    assert 'kind === "led-device-name-save"' in dashboard
    assert "deviceNames: {}" in dashboard
    assert "[deviceId]: name" in panel
    assert "this.saveUiSettings();" in dashboard


def test_led_database_status_action_aligns_with_the_power_toggle() -> None:
    """The database eye must use the same compact left-side control alignment as the power row."""
    dashboard = source(DASHBOARD)

    assert ".led-device-edit-actions .led-database-status-row" in dashboard
    assert "grid-template-columns:28px 266px auto" in dashboard


def test_led_core_storage_stays_separate_from_home_assistant_recorder() -> None:
    """Only LED configuration and diagnostics use the integration-owned SQLite database."""
    server = source(ADDON_SERVER)
    dashboard = source(DASHBOARD)
    run = source(ADDON_RUN)
    library_store = source(ROOT / "src" / "chihiros_led_control" / "store.py")
    integration_store = "\n".join(
        (
            source(ROOT / "custom_components" / "chihiros" / "core" / "storage" / "runtime.py"),
            source(ROOT / "custom_components" / "chihiros" / "plugins" / "led" / "storage" / "history.py"),
        )
    )
    storage_sources = "\n".join((server, library_store, integration_store))

    assert "/config/.chihiros_led_core/chihiros_led_core.sqlite3" in run
    assert "chihiros_state.sqlite3" not in "\n".join((run, server, library_store, integration_store, dashboard))
    assert '"mode": "integration"' in server
    assert "integration_state_db_path" in server
    assert "initialize_led_core_database()" in server
    assert "from chihiros_led_control.store import init_state_db" in server
    assert 'name="diagnostic_retention_days"' in dashboard
    assert "Entity-Zustände, History und Statistiken bleiben im Home-Assistant-Recorder." in dashboard
    assert "DELETE FROM actions WHERE action='LED notification fetch' AND ts < ?" in server
    assert "CREATE TABLE IF NOT EXISTS states" not in storage_sources
    assert "CREATE TABLE IF NOT EXISTS statistics" not in storage_sources


def test_addon_promotes_only_addresses_with_led_color_light_entities() -> None:
    """Doser or other auxiliary sensors must not create false LED device tabs."""
    server = source(ADDON_SERVER)

    assert 'match.group(1).lower() != "light"' in server
    assert 'match.group(3).lower() not in {' in server
    assert 'if address not in led_addresses:' in server


def test_addon_accepts_only_entities_owned_by_led_core() -> None:
    """Legacy Chihiros and Doser entities must never become LED Core device tabs."""
    server = source(ADDON_SERVER)
    entities = ROOT / "custom_components" / "chihiros" / "plugins" / "led" / "entities"
    light = source(entities / "light.py")
    switch = source(entities / "switch.py")
    sensor = source(entities / "sensor.py")

    assert 'attributes.get("integration_domain") != "chihiros_led_core"' in server
    assert '"integration_domain": DOMAIN' in light
    assert '{"integration_domain": DOMAIN}' in switch
    assert 'integration_attributes = {"integration_domain": DOMAIN}' in sensor


def test_channel_toggle_sends_distinct_on_off_values() -> None:
    """The channel toggle selects one action while keeping distinct send paths."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert 'data-led-channel-action="${value > 0 ? "off" : "on"}"' in panel
    assert 'if (mode === "on")' in dashboard
    assert "const value = Number.isFinite(restore) && restore > 0 ? restore : max;" in dashboard
    assert "this.setLedBrightness(channel.entity, 0, false" in dashboard


def test_slider_and_number_input_share_the_same_channel_send_path() -> None:
    """Range and numeric controls stay synchronized and send through setLedBrightness."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert panel.count('data-led-number="${this.escapeHtml(channel.entity || "")}"') == 2
    assert 'this.querySelectorAll("[data-led-number]")' in dashboard
    assert "syncLedChannelControls();" in dashboard
    assert 'if (entity.startsWith("light.")) this.setLedBrightness(entity, value);' in dashboard
    assert "const value = Math.max(0, Math.min(max, Math.round(Number(rawValue))));" in dashboard
    assert "el.value = String(value);" in dashboard


def test_manual_schedule_warning_is_persisted_and_restored() -> None:
    """Manual channel writes persist manual_override and reload it from device status."""
    panel = source(LED_PANEL)

    assert 'String(persisted.mode || "").toLowerCase() === "manual"' in panel
    assert 'String(persisted.schedule_state || "").toLowerCase() === "manual_override"' in panel
    assert 'scheduleState: "manual_override"' in panel
    assert "this.setLedManualScheduleWarning(true);" in panel
    assert "this.setLedManualScheduleWarning(false);" in panel


def test_manual_channel_history_keeps_human_channel_name() -> None:
    """Total LED history identifies the channel without relying on a stripped entity ID."""
    panel = source(LED_PANEL)

    assert "? `CH${channel.id} ${this.ledChannelDisplayName(channel)}`" in panel
    assert "`${channelLabel}: ${value}/${max}${suffix}`" in panel
    assert "channel_name: channelLabel" in panel


def test_scheduler_front_actions_are_bound_to_individual_rows() -> None:
    """Edit, delete, send, and share actions retain their selected row index."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    for attribute in (
        "data-led-schedule-edit",
        "data-led-schedule-delete",
        "data-led-schedule-send",
        "data-led-schedule-share",
    ):
        assert f'{attribute}="${{index}}"' in panel
        assert f"[{attribute}]" in dashboard


def test_scheduler_share_uses_config_debug_dialog() -> None:
    """Schedule sharing keeps config-driven debug output visible."""
    panel = source(LED_PANEL)
    start = panel.index("async saveSharedLedSchedule()")
    end = panel.index("\n  ledScheduleShareDialog()", start)
    implementation = panel[start:end]

    assert "const debug = Boolean(this.uiSettings && this.uiSettings.dashboardDebug);" in implementation
    assert "dialog: debug" in implementation
    assert "debug," in implementation
    assert "saved && debug && sendOutput" in implementation
    assert "const localPayload =" in implementation
    assert "const localDebugOutput =" in implementation
    assert "JSON.stringify(localPayload, null, 2)" in implementation
    assert "debug ? localDebugOutput" in implementation


def test_config_debug_setting_is_persisted_by_addon() -> None:
    """The dashboard debug toggle survives reloads through add-on settings."""
    dashboard = source(DASHBOARD)
    index = source(ADDON_INDEX)
    server = source(ADDON_SERVER)

    assert "dashboardDebug: Boolean(this.config?.dashboard_debug)" in dashboard
    assert 'Object.prototype.hasOwnProperty.call(this.config, "dashboard_debug")' in dashboard
    assert 'key === "dashboardDebug"' in dashboard
    assert "dashboard_debug: value" in dashboard
    assert "database_diagnostics_enabled: data.get" in dashboard
    assert "dashboard_debug: Boolean(this.uiSettings && this.uiSettings.dashboardDebug)" in dashboard
    assert "dashboard_debug: Boolean(addonDatabase && addonDatabase.dashboard_debug)" in index
    assert '"dashboard_debug": bool(data.get("dashboard_debug", False))' in server


def test_debug_sections_restore_headers_after_running_dialog() -> None:
    """Running debug is plain, completed structured debug keeps headers and copy buttons."""
    dashboard = source(DASHBOARD)
    start = dashboard.index("debugOutputMarkup(output = \"\"")
    end = dashboard.index("\n  async copyText", start)
    implementation = dashboard[start:end]

    assert "<pre>${this.escapeHtml(section.value)}</pre>" in implementation
    assert "<header>" in implementation
    assert "copy-debug:${index}" in implementation
    assert "const title = section.title || this.tr(\"debug_output\");" in implementation
    assert "options.debug && !options.running" in dashboard
    assert "...(options.running ? [] : [" in dashboard
    assert '{ action: "copy-debug:all", label: this.tr("copy_all")' in dashboard
    assert ".debug-section-box header" in dashboard


def test_scheduler_row_send_atomically_replaces_device_schedule_with_one_row() -> None:
    """The row send button resets stale device slots and writes only the selected period."""
    panel = source(LED_PANEL)
    start = panel.index("async sendLedScheduleRowFromFront(rowIndex)")
    end = panel.index("\n  async callLedService", start)
    implementation = panel[start:end]

    assert "async sendLedScheduleRowFromFront(rowIndex)" in implementation
    assert "const period = this.ledSchedulePeriodsFromRows([row]" in implementation
    assert 'service: "set_schedule"' in implementation
    assert "data: { periods: [period], send: true, ...this.ledServiceSelector() }" in implementation
    assert "debug && result && result.output" in implementation
    assert "debug," in implementation
    assert "const localPeriods = this.ledSchedulePeriodsFromRows(rows);" in implementation
    assert "sendCurrentLedScheduleFromFront" not in panel


def test_scheduler_reset_debug_keeps_delete_and_verification_operations() -> None:
    """Reset diagnostics include delete frames as well as the final status query."""
    services = source(LED_SERVICES)
    reset_handler = services.split("async def async_reset_schedule", 1)[1].split("async def async_set_schedule", 1)[0]

    assert "debug_last_operation=False" in reset_handler


def test_scheduler_verification_uses_persisted_one_shot_result() -> None:
    """The dashboard marker uses the delayed DB result, not every runtime poll snapshot."""
    panel = source(LED_PANEL)
    server = source(ROOT / "chihiros_beta" / "ui" / "server.py")

    assert 'storedStatus === "verified"' in panel
    assert 'storedStatus === "failed"' in panel
    assert 'storedStatus === "pending"' in panel
    assert "verification_status TEXT NOT NULL DEFAULT 'pending'" in server
    assert "previous.get(signature" in server


def test_scheduler_delete_keeps_verification_for_remaining_rows() -> None:
    """An optimistic delete render must retain the persisted green row markers."""
    panel = source(LED_PANEL)
    override_branch = panel.split("Array.isArray(this._ledScheduleRowsOverride)", 1)[1].split(
        "const storageKeys = this.ledScheduleStorageKeys();", 1
    )[0]

    assert 'String(this._ledScheduleRowsOverrideKey || "") === this.ledScheduleDeviceKey()' in override_branch
    verification_mapping = (
        'verification_status: String(row && row.verification_status ? row.verification_status : "pending")'
    )
    assert verification_mapping in override_branch
    assert 'verified_at: String(row && row.verified_at ? row.verified_at : "")' in override_branch


def test_schedule_rows_override_is_scoped_to_selected_device() -> None:
    """Optimistic schedule rows from one LED must not leak into another LED tab."""
    panel = source(LED_PANEL)

    assert 'String(this._ledScheduleRowsOverrideKey || "") === this.ledScheduleDeviceKey()' in panel
    assert "this._ledScheduleRowsOverrideKey = deviceKey" in panel
    assert 'this._ledScheduleRowsOverrideKey = ""' in panel


def test_new_scheduler_dialog_keeps_entered_times_while_sending() -> None:
    """Status renders during a new-row send must reuse the submitted form values."""
    panel = source(LED_PANEL)

    assert "Array.isArray(dialog.ledScheduleDraftRows)" in panel
    assert "return dialog.ledScheduleDraftRows.map((row) => ({ ...row }));" in panel
    assert "this.dialogState.ledScheduleDraftRows = values.map((row) => ({" in panel


def test_scheduler_verification_waits_once_and_restores_two_visible_rows() -> None:
    """More than two rows use the device's two visible slots only for the delayed check."""
    services = source(LED_SERVICES)

    assert "await asyncio.sleep(60)" in services
    assert "initialize LED schedule storage" in services
    assert "return {}" in services
    assert "await _remove_stored_schedule_rows(chihiros_data.device, stored_rows[:2])" in services
    assert "restore_rows = stored_rows[:2] if active and len(stored_rows) > 2 else []" in services
    assert "_record_or_schedule_led_verification(hass, chihiros_data, device_key, target, restore_rows)" in services
    assert "if not _verification_requires_snapshot(target):" in services
    assert "chihiros_data.device.replace_settings(settings)," in services
    assert "timeout=LED_VERIFICATION_RESTORE_TIMEOUT" in services


def test_inactive_schedule_delete_only_removes_selected_row() -> None:
    """Deleting a row must not temporarily remove other stored schedules."""
    services = source(LED_SERVICES)
    constants = source(ROOT / "custom_components" / "chihiros" / "plugins" / "led" / "const.py")

    assert "active = bool(call.data.get(ATTR_ACTIVE, True))" in services
    assert "restore_rows = stored_rows[:2] if active and len(stored_rows) > 2 else []" in services
    assert 'ATTR_DELETE_ONLY = "delete_only"' in constants
    assert "max_brightness=None if bool(data.get(ATTR_DELETE_ONLY, False)) else brightness_from_service_data(data)" in services


def test_scheduler_verification_is_queued_per_schedule_row() -> None:
    """Two rows from one device must retain separate jobs and history results."""
    services = source(LED_SERVICES)
    storage = source(ROOT / "custom_components" / "chihiros" / "plugins" / "led" / "storage" / "runtime.py")

    assert "return f\"{device_key}|{target['start']}|{target['end']}\"" in services
    assert 'task_key = f"{device_key}|batch"' in services
    assert "if not cancelled:" in services
    assert "finish_led_schedule_verification, device_key, target, status" in services
    assert "PRIMARY KEY (device_key, schedule_signature)" in storage
    assert "WHERE UPPER(device_key)=UPPER(?) AND schedule_signature=?" in storage
    assert 'old_target.get("start") == target["start"]' in storage
    assert "record_led_schedule_verification(device_key, target, status)" in storage


def test_scheduler_verification_refreshes_without_page_reload() -> None:
    """The add-on reloads persisted verification results without another BLE poll."""
    index = source(ROOT / "chihiros_beta" / "ui" / "index.html")
    panel = source(LED_PANEL)

    assert "scheduleVerificationDashboardRefresh()" in index
    assert "}, 70000);" in index
    assert 'service === "add_schedule" || service === "set_schedule" || service === "enable_auto_mode"' in index
    assert "await window.ChihirosAddonApi.refreshDashboard();" in panel


def test_scheduler_crud_and_debug_contracts_remain_available() -> None:
    """Scheduler create/edit/delete flows and config-driven debug remain wired."""
    panel = source(LED_PANEL)

    assert "openNewLedScheduleDialog()" in panel
    assert "openLedScheduleDialog(rowIndex = null)" in panel
    assert "async addLedSchedule(send = true)" in panel
    assert "async deleteLedScheduleRow(rowIndex = null, send = true)" in panel
    assert "Boolean(this.uiSettings && this.uiSettings.dashboardDebug)" in panel


def test_led_layout_editor_contract_remains_available() -> None:
    """The LED dashboard layout editor must stay user-scoped and mobile-safe."""
    panel = source(LED_PANEL)
    core = source(ROOT / "custom_components" / "chihiros" / "plugins" / "led" / "dashboard" / "chihiros-led-core-card.js")

    assert "ledLayoutUserKey()" in panel
    assert 'return ["channels", "schedule", "history", "templates", "connection", "control", "presets"];' in panel
    assert 'if (item === "middle")' in panel
    assert "chihiros-led-core-layout:${user}:${deviceKey}" in panel
    assert "ledLayoutHasCustomOrder()" in panel
    assert "has-custom-layout" in panel
    assert ".led-layout-page.has-custom-layout > .led-layout-item," in core
    assert ".led-layout-page.is-editing > .led-layout-item { grid-column:auto !important; grid-row:auto !important; order:var(--led-layout-order,0); }" in core
    assert '.led-layout-page.is-editing > [data-led-layout-item="channels"] { grid-column:1 / -1 !important; }' in core
    assert "toggleLedLayoutEditor()" in panel
    assert "resetLedLayoutOrder()" in panel
    assert 'data-led-layout-handle' in panel
    assert "clientX" in core
    assert 'document.createComment("led-layout-swap")' in core
    assert "move_left" in core
    assert "move_right" in core
    assert "layout_item_schedule" in core
    assert "layout_item_history" in core
    assert 'kind === "led-layout-toggle"' in core
    assert 'kind === "led-layout-reset"' in core
    assert 'kind === "led-layout-move"' in core
    assert "bindLedLayoutDrag()" in core
    assert "pointerdown" in core
    assert "touch-action:none" in core
    assert 'type: "debug"' in panel


def test_scheduler_front_delete_opens_running_dialog() -> None:
    """The front delete button uses config debug and acknowledges BLE activity."""
    panel = source(LED_PANEL)
    start = panel.index("async deleteLedScheduleRow(rowIndex = null, send = true)")
    end = panel.index("\n  ledEntityState(", start)
    implementation = panel[start:end]

    assert "if (this._ledScheduleSubmitting) return false;" in implementation
    assert "const debug = Boolean(this.uiSettings && this.uiSettings.dashboardDebug);" in implementation
    assert "data-led-schedule-debug" not in implementation
    assert "ledScheduleDebug" not in implementation
    assert 'output: this.tr("debug_sending")' in implementation
    assert 'running: true' in implementation
    assert "debug, dialog: true" in implementation
    assert (
        "remainingRows.length > 0 ? [{ ...remainingRows[0], active: false }] : "
        "[{ ...deletedRow, active: false }]"
        in implementation
    )
    assert "delete_only: true" in implementation
    assert "delete_only: remainingRows.length > 0" not in implementation
    assert "output: sendResult && sendResult.output" in implementation


def test_led_database_diagnostics_is_configurable_and_opens_from_control() -> None:
    """Scheduler database results remain opt-in and open as named tables."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)
    index = source(ROOT / "chihiros_beta" / "ui" / "index.html")
    server = source(ROOT / "chihiros_beta" / "ui" / "server.py")

    assert "databaseDiagnosticsEnabled()" in panel
    assert 'data-action="led-database-status-open"' in panel
    assert "async openDatabaseStatusDialog()" in panel
    assert "databaseStatusDialog()" in panel
    assert 'class="database-result-table"' in panel
    assert 'this.tr("database_stored_schedules")' in panel
    assert 'this.tr("database_verification_jobs")' in panel
    assert "entry.query" not in panel
    assert 'name="database_diagnostics_enabled"' in dashboard
    assert 'data.get("database_diagnostics_enabled") === "on"' in dashboard
    assert "fetch(`./api/database-status${suffix}`" in index
    assert 'if request_path == "/api/database-status":' in server
    assert "database_diagnostics_status(device)" in server
    assert '"database_diagnostics_enabled": bool(' in server


def test_scheduler_send_keeps_success_visible_until_manual_close() -> None:
    """A successful non-debug send remains visible and provides a header close button."""
    panel = source(LED_PANEL)

    success_message = (
        'this.setLedScheduleDialogMessage(`${title}\\n${this.tr("status")}: ok\\n'
        '${this.tr("reply")}: ${this.tr("reply_sent")}`, "ok");'
    )
    assert success_message in panel
    assert 'class="led-schedule-dialog-close" data-action="close-dialog"' in panel
    assert '<span aria-hidden="true">&#10005;</span>' in panel
    assert "setTimeout(resolve, 2500)" not in panel


def test_german_dashboard_catalog_uses_real_umlauts() -> None:
    """German UI text uses proper characters instead of ASCII substitutions."""
    dashboard = source(DASHBOARD)
    german_catalog = dashboard.split("de: {", 1)[1].split("en: {", 1)[0]

    forbidden = (
        "Geraet",
        "Geraete",
        "Zeitplaene",
        "loeschen",
        "geloescht",
        "fuer",
        "zurueck",
        "ueber",
        "Rueckmeldung",
        "Behaelter",
        "Naechste",
        "ungueltig",
    )
    assert not [word for word in forbidden if word in german_catalog]


def test_dashboard_translation_catalogs_have_matching_keys() -> None:
    """Every core dashboard translation is available in German and English."""
    import re

    dashboard = source(DASHBOARD)
    german_catalog = dashboard.split("de: {", 1)[1].split("en: {", 1)[0]
    english_catalog = dashboard.split("en: {", 1)[1].split("};", 1)[0]
    key_pattern = re.compile(r"^\s*([a-zA-Z0-9_]+):", re.MULTILINE)

    assert set(key_pattern.findall(german_catalog)) == set(key_pattern.findall(english_catalog))


def test_led_history_localizes_legacy_database_text() -> None:
    """Old mixed-language history entries are normalized to the selected UI language."""
    dashboard = source(DASHBOARD)

    for translation_key in (
        "led_schedule_saved",
        "led_schedule_sent_action",
        "schedule_deleted",
        "schedules_device_deleted_local_kept",
        "led_set",
        "enable_auto_mode",
        "all_days",
        "channels",
        "schedule_verification",
    ):
        assert f'this.tr("{translation_key}")' in dashboard
    assert 'failed ? "schedule_verification_failed" : "schedule_verification_ok"' in dashboard
    assert 'localizeLedHistoryText(title = "", detail = "")' in dashboard
    assert "Zeitplaene" in dashboard


def test_complete_lamp_labels_and_auto_mode_status_are_explicit() -> None:
    """Lamp choices are unambiguous and auto mode falls back to persisted device status."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert 'complete_lamp_on: "Lampe komplett einschalten"' in dashboard
    assert 'complete_lamp_off: "Lampe komplett ausschalten"' in dashboard
    assert 'complete_lamp_toggle: "Lampe komplett einschalten / ausschalten"' in dashboard
    assert "ledAutoModeIsOn(device = this.activeLedDevice || {})" in panel
    assert 'mode === "automatic" || mode === "auto"' in panel
    assert "this.ledAutoModeState(device)" in panel
    assert 'data-action="led-device-power-toggle" role="switch"' in panel
    assert 'aria-checked="${this.ledDeviceIsOn() ? "true" : "false"}"' in panel
    assert "async toggleLedDevicePower()" in panel
    assert 'this.tr("complete_lamp_toggle")' in panel
    assert ".led-device-control-card .led-device-edit-actions { grid-template-columns:minmax(0, 1.35fr)" in dashboard


def test_channel_history_uses_readable_value_cards() -> None:
    """Per-channel history hides entity IDs and presents actions, times, and values clearly."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert 'class="led-channel-history-entry"' in panel
    assert "detail.match(/:\\s*(\\d+)\\s*\\/\\s*(\\d+)/)" in panel
    assert 'this.tr("brightness_changed")' in panel
    assert 'this.tr("channel_switched_off")' in panel
    assert ".led-channel-history-list { display:grid;" in dashboard
    assert 'class="led-channel-history-close" data-action="close-dialog"' in panel
    assert "if (list) list.scrollTop = 0;" in dashboard


def test_connection_panel_shows_runtime_sensor() -> None:
    """LED runtime is discovered and rendered in minutes in the connection panel."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert 'suffix === "runtime" || suffix === "runtime_minutes"' in panel
    assert 'replace(/_firmware_version$/, "_runtime")' in panel
    assert "this.ledEntityState(runtimeEntity)" in panel
    assert 'this.tr("runtime")' in panel
    assert "formatLedRuntime(value)" in panel
    assert "Math.floor(totalMinutes / 1440)" in panel
    assert "this.formatLedRuntime(runtime)" in panel
    assert "formatLedNotificationTime(device = this.activeLedDevice || {})" in panel
    assert 'this.tr("last_notification")' in panel
    assert 'this.tr("fetched_at")' in panel
    assert "grid-template-columns:minmax(0, 1.35fr) minmax(170px, .65fr)" in dashboard
    assert "grid-template-columns:28px max-content auto; justify-content:start" in dashboard
    assert 'runtime: "Laufzeit"' in dashboard
    assert 'runtime: "Runtime"' in dashboard
    assert "resolveLedRuntimeEntity(device = this.activeLedDevice || {})" in panel
    assert "const runtimeEntity = this.resolveLedRuntimeEntity(device);" in panel
    assert "ledDeviceFeedbackStatus(device = this.activeLedDevice || {})" in panel
    assert "20 * 60 * 1000" in panel
    assert 'this.tr("offline")' in panel
    assert '<p><b>${this.tr("channels")}</b><span>${channels.length}</span></p>' in panel
    assert "device.name || device.id || device.label" in panel
    assert ".card.led-connection-card p { flex:0 0 auto; min-height:24px;" in dashboard
    assert '<p><b>${this.tr("firmware")}</b><span class="${firmwareUnknown ? "is-unknown" : ""}">' in panel
    assert '<p><b>${this.tr("source")}</b><span>Home Assistant</span></p>' not in panel
    assert '<p><b>BLE</b><span>${this.tr("ble_on_action")}</span></p>' not in panel
    assert 'data-action="led-notification-open"' in panel
    assert "ledNotificationDialog()" in panel
    notification_ui = source(LED_DASHBOARD / "chihiros-notification-ui.js")
    assert "value.value_hex || value.frame || value.raw" in notification_ui
    assert "value.hex || value.parm || value.att_hex" in notification_ui
    assert "Array.isArray(attrs.notifications)" in panel
    assert "ledScheduleRangesFromPoints(normalized = [])" in panel
    assert "candidateRamp >= 1 && candidateRamp <= 150" in panel
    assert "const expectedRamp = configuredRamp;" in panel
    assert "if (minutes <= 1) return 1;" in panel
    assert "if (!Number.isFinite(minutes)) return 1;" in panel
    assert 'ramp: Math.max(1, Math.min(150, Math.round(Number(get("ramp", "1")))))' in panel
    assert "rampControl(row.ramp ?? 1)" in panel
    assert "if (addonMode) {" in panel
    assert "range.ramp === expectedRamp" in panel
    assert "ledScheduleRowVerification(row)" in panel
    assert "const existingBoundary = normalized" in panel
    assert "ranges.push({ start, end: existingBoundary.time, level, ramp });" in panel
    assert 'class="led-schedule-check-dot ${verification.level}"' in panel
    assert '<th>${this.tr("check_short")}</th>' in panel
    assert ".led-schedule-front-table td:nth-child(3) { min-width:100px; white-space:nowrap; }" in dashboard
    assert ".led-schedule-front-table td { border:1px solid rgba(255,255,255,.12); padding:7px 8px; text-align:left; vertical-align:middle; white-space:nowrap; }" in dashboard
    assert (
        '<th>#</th>\n              <th>${this.tr("check_short")}</th>\n              <th>${this.tr("time")}</th>'
    ) in panel
    assert 'card.tr("meaning")' in notification_ui
    assert '<h3>${this.tr("notification_type")}</h3>' not in panel
    assert 'direction: "Richtung"' in dashboard
    assert 'direction: "Direction"' in dashboard


def test_total_history_timestamp_uses_configured_language_and_first_row() -> None:
    """Timeline timestamps use DE/US ordering and share the action row."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert "formatLedHistoryTimestamp(value)" not in panel
    assert "formatHistoryTimestamp(value)" in dashboard
    assert 'this.language() === "en" ? "en-US" : "de-DE"' in dashboard
    assert '${timestamp ? `<time>${this.escapeHtml(timestamp)}</time>` : ""}</div>' in dashboard
    assert ".modal { box-sizing:border-box; width:min(520px, calc(100vw - 40px)); max-width:100%; }" in dashboard
    assert ".led-history-timeline { position:relative; display:grid; grid-auto-rows:max-content; align-content:start;" in dashboard
    assert ".led-history-timeline-copy time { margin-left:auto;" in dashboard


def test_mobile_led_dashboard_uses_single_column_and_scrolling_tables() -> None:
    """Mobile LED cards stay within the viewport while wide tables scroll locally."""
    dashboard = source(DASHBOARD)

    assert ".led-template-front-table-wrap { max-width:100%; overflow-x:scroll;" in dashboard
    assert ".led-template-front-table-wrap::-webkit-scrollbar { height:10px; }" in dashboard
    assert ".led-template-front-table-wrap::-webkit-scrollbar-thumb" in dashboard
    assert ".led-schedule-summary-list { display:grid; gap:8px; max-width:100%; overflow-x:scroll;" in dashboard
    assert "scrollbar-gutter:stable; scrollbar-width:auto; scrollbar-color:#03c9ff" in dashboard
    assert ".led-schedule-summary-list::-webkit-scrollbar { height:10px; }" in dashboard
    assert ".led-schedule-summary-list::-webkit-scrollbar-thumb" in dashboard
    assert "@media (pointer:coarse)" in dashboard
    assert 'input[type="range"][data-led-number],' in dashboard
    assert 'input[type="range"][data-led-schedule-control],' in dashboard
    assert 'input[type="range"][data-led-template-control],' in dashboard
    assert 'input[type="range"][data-led-fan-control] { touch-action:pan-y; }' in dashboard
    assert "@media (max-width:700px)" in dashboard
    assert ".led-page { grid-template-columns:minmax(0,1fr); }" in dashboard
    assert ".led-middle { grid-column:1; grid-row:2; grid-template-columns:minmax(0,1fr); }" in dashboard
    assert ".led-page .led-channels { grid-template-columns:minmax(0,1fr); }" in dashboard
    assert ".led-device-control-card .led-device-edit-actions { grid-template-columns:minmax(0,1fr); gap:8px; }" in dashboard
    assert ".led-device-edit-actions .action-row { grid-template-columns:28px minmax(0,1fr) auto;" in dashboard
    assert ".led-device-power-row > span { white-space:normal; overflow-wrap:anywhere; }" in dashboard
    assert ".led-schedule-row-grid > .led-schedule-color-control.led-schedule-time-control" in dashboard
    assert ".led-schedule-time-control .led-schedule-row-title { grid-template-columns:auto minmax(0,1fr); }" in dashboard
    assert "data-led-schedule-debug" not in dashboard
    assert ".led-schedule-color-control.led-schedule-weekdays-control {" in dashboard
    assert "grid-template-columns:repeat(auto-fit, minmax(56px, 1fr));" in dashboard
    assert ".led-schedule-weekdays-control .weekday-grid { grid-template-columns:repeat(4, minmax(0,1fr)); }" in dashboard
    assert ".led-schedule-weekdays-control .weekday-chip { box-sizing:border-box; padding:4px; }" in dashboard
    assert ".config-card-head { flex-direction:column; align-items:stretch; }" in dashboard


def test_template_panel_shows_filtered_template_count() -> None:
    """The template header reports the number of rows in the selected source."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert '${templates.length} ${this.tr("template_count")}' in panel
    assert 'template_count: "Vorlagen"' in dashboard
    assert 'template_count: "templates"' in dashboard
    assert 'template_list: "Vorlagenliste"' in dashboard
    assert ".led-template-count {" in dashboard
    assert 'const localPrefix = `${this.tr("template_local")}: `;' in panel


def test_template_panel_shows_local_schedule_count() -> None:
    """The template panel keeps schedule counts and local labels visible."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert "this.dialogState = { ...(this.dialogState || {}), values };" in panel
    assert "rawLabel.slice(localPrefix.length)" in panel
    assert '${scheduleRows.length} ${this.tr("schedule_count")}' in panel
    assert 'schedule_count: "Zeitpläne"' in dashboard
    assert 'schedule_count: "schedules"' in dashboard
    assert ".led-schedule-count {" in dashboard


def test_template_dialog_live_preview_debugs_without_dashboard_refresh() -> None:
    """Template live preview shows the service payload and does not reload the dialog."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)
    index = source(ROOT / "chihiros_beta" / "ui" / "index.html")

    assert "data-led-template-live-preview" in panel
    assert "queueLedTemplateLivePreview" in panel
    assert "sendLedTemplateLivePreview" in panel
    assert "setLedTemplateLivePreviewEnabled(Boolean(el.checked))" in dashboard
    assert "templateLivePreview: Boolean(enabled)" in panel
    assert 'data-led-template-live-preview ${state.templateLivePreview ? "checked" : ""}' in panel
    assert "this.queueLedTemplateLivePreview(false, name)" in dashboard
    assert "async sendLedTemplateLivePreview(channelKey = \"\")" in panel
    assert 'const key = force && !this._ledTemplateLivePreviewChannel ? "__clear_all__"' in panel
    assert "data-led-template-live-preview-log" in panel
    assert "const showDebug = Boolean(this.uiSettings && this.uiSettings.dashboardDebug);" in panel
    assert "if (showDebug) {" in panel
    assert "debug: showDebug" in panel
    assert "__skip_dashboard_refresh: true" in panel
    assert "skip_dashboard_refresh: skipDashboardRefresh" in dashboard
    assert "if (!skipDashboardRefresh) await refreshDashboard();" in index
    assert 'template_live_preview: "Live-Vorschau"' in dashboard
    assert 'template_live_preview: "Live preview"' in dashboard


def test_template_live_preview_restores_auto_mode_on_dialog_close() -> None:
    """Closing the template dialog silently restores automatic mode after live changes."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert 'state.type === "led-template-editor"' in dashboard
    assert "state.templateLivePreviewChanged" in dashboard
    assert "restoreLedAutoModeAfterTemplatePreview" in dashboard
    assert "this.setLedManualScheduleWarning(false);" in dashboard
    assert "templateLivePreviewChanged: true" in panel
    assert "async restoreLedAutoModeAfterTemplatePreview()" in panel
    assert "async saveLedTemplateFromDialog()" in panel
    assert "await this.restoreLedAutoModeAfterTemplatePreview();" in panel
    assert "await this.saveLedTemplateFromDialog()" in dashboard
    assert 'service: "enable_auto_mode"' in panel
    assert "template_live_preview_close" in panel
    assert "data: { periods, __skip_dashboard_refresh: true, ...this.ledServiceSelector() }" in panel
    assert "dialog: false" in panel
    assert 'class="led-schedule-dialog-head"' in panel
    assert 'class="led-schedule-dialog-close" data-action="close-dialog"' in panel


def test_channel_power_uses_single_toggle() -> None:
    """Each LED channel exposes one stateful on/off toggle."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert 'class="led-channel-toggle ${value > 0 ? "active" : ""}"' in panel
    assert 'data-led-channel-action="${value > 0 ? "off" : "on"}"' in panel
    assert 'role="switch" aria-checked="${value > 0 ? "true" : "false"}"' in panel
    assert 'this.querySelectorAll("[data-led-channel-action]")' in dashboard
    assert ".led-channel-toggle-track {" in dashboard


def test_universal_wrgb_1000_shows_live_estimated_wattage() -> None:
    """Configured Universal WRGB products expose calculated channel and total wattage."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)
    light = source(ROOT / "custom_components" / "chihiros" / "plugins" / "led" / "entities" / "light.py")

    assert "max_power_watts: this.resolveLedMaxPowerWatts(device)" in panel
    assert '"max_power_watts": self._device.model.max_power_watts' in light
    assert 'text.includes("universal wrgb")' in panel
    assert "const universalPowerWatts = {" in panel
    assert "1000: 59" in panel
    assert "const match = text.match(/dyu(550|600|700|800|920|1000|1200|1500)/);" in panel
    assert (
        "red: [[0, 0], [1, 3], [11, 4], [21, 6], [30, 7], [38, 8], [47, 9], [54, 11], [62, 12], "
        "[69, 13], [77, 14], [83, 16], [90, 17], [97, 18], [100, 19]]"
    ) in panel
    assert (
        "green: [[0, 0], [1, 3], [8, 4], [14, 6], [21, 7], [27, 8], [33, 9], [39, 11], [45, 12], "
        "[50, 13], [56, 14], [61, 16], [71, 18], [76, 19], [81, 21], [86, 22], [90, 23], [99, 24], "
        "[100, 26]]"
    ) in panel
    assert "blue: [[0, 0], [1, 2], [2, 3], [20, 4], [38, 6], [55, 7], [71, 8], [87, 9], [100, 9]]" in panel
    assert "white: [[0, 0], [1, 1], [11, 1], [30, 2], [100, 12]]" in panel
    assert "const totalPowerPoints = [[0, 0], [1, 3], [11, 8], [30, 17], [100, 61]];" in panel
    assert "const channelPowerShares = { red: 0.273, green: 0.394, blue: 0.136, white: 0.197 };" in panel
    assert "maxPowerWatts * channelPowerShares[item.key] * levels[index] / 100" in panel
    assert "this.ledWattInterpolate(points, value) * (this.ledMaxPowerWatts() / 61)" in panel
    assert "return Math.min(maxPowerWatts, channels.reduce(" in panel
    assert "W / ${this.ledWattFormat(this.ledMaxPowerWatts(device))} W" in panel
    assert 'data-led-channel-watts="${channel.id}"' in panel
    assert "data-led-total-watts" in panel
    assert 'field.textContent = value > 0 ? `≈ ${this.ledWattFormat(watts)} W` : "0 W";' in panel
    assert 'if (typeof this.updateLedWattDisplays === "function") this.updateLedWattDisplays();' in dashboard
    assert ".led-watt-bolt { color:#f6ad2f;" in dashboard
    assert 'total: "Gesamt"' in dashboard
    assert 'total: "Total"' in dashboard


def test_enable_auto_mode_button_uses_response_service_instead_of_schedule_write() -> None:
    """Auto-mode activation uses its debug-capable 18, 5, schedules service."""
    panel = source(LED_PANEL)
    start = panel.index("async enableLedAutoModeFromFront()")
    end = panel.index("\n  ledPanel()", start)
    implementation = panel[start:end]

    assert 'service: "enable_auto_mode"' in implementation
    assert "this.runDeviceService({" in implementation
    assert "data: { periods, ...this.ledServiceSelector() }" in implementation
    assert "dialog: debug" in implementation
    assert "output: debug && serviceOutput ? serviceOutput" in implementation
    assert 'service: "set_schedule"' not in implementation
    assert "Auto-Mode-Entitaet nicht gefunden" not in implementation
    assert '"verification_scheduled": bool(verification_rows)' in source(LED_SERVICES)


def test_vivid_iii_replaces_presets_with_fan_status_and_control() -> None:
    """Fan-equipped LED models expose temperature, RPM, and percentage control."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert "const devicePattern = /^(light|switch|sensor|fan)" in panel
    assert 'suffix === "fan_rpm" || suffix === "fan_speed"' in panel
    assert 'suffix === "fan_temperature_celsius" || suffix === "temperature"' in panel
    assert 'domain === "fan" && suffix === "fan"' in panel
    assert "ledDeviceHasFan(device" in panel
    assert "this.ledDeviceHasFan(device) ? this.ledFanControlCard(device)" in panel
    assert 'this._hass.callService("fan", "set_percentage", { percentage }' in panel
    assert 'data-led-fan-control' in panel
    assert 'fan_control: "Lüftersteuerung"' in dashboard
    assert 'fan_control: "Fan control"' in dashboard
    assert 'this.querySelectorAll("[data-led-fan-control]")' in dashboard
    assert ".led-fan-metrics {" in dashboard


def test_vivid_iii_fake_is_discoverable_as_dashboard_demo_device() -> None:
    """The fake VIVID III name ends in its compact MAC so dashboard grouping can find it."""
    fake = source(ROOT / "custom_components" / "chihiros" / "plugins" / "led" / "testing" / "fake.py")

    assert 'name="DYVVD3FACEC0000004"' in fake
    assert 'address=f"{FAKE_ADDRESS_PREFIX}:00:00:04"' in fake
    assert "async def query_status_active" in fake
    assert "temperature_celsius=25" in fake


def test_dashboard_adds_local_vivid_demo_without_real_fan_device() -> None:
    """The standalone panel exposes a harmless local fan demo as a third device."""
    panel_shell = source(LED_DASHBOARD / "chihiros-panel.js")
    panel = source(LED_PANEL)

    assert "show_fan_demo: true" in panel_shell
    assert "this.config.show_fan_demo === true" in panel
    assert '!resolved.some((device) => this.ledDeviceHasFan(device))' in panel
    assert 'label: "VIVID III Demo"' in panel
    assert 'address: "FA:CE:C0:00:00:04"' in panel
    assert "fan_demo: true" in panel
    assert "device.fan_rpm = percentage * 20" in panel
