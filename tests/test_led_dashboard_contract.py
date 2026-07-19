"""Regression contracts for the dependency-free LED dashboard frontend."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LED_PANEL = ROOT / "custom_components/chihiros/www/panels/chihiros-led-panel.js"
DASHBOARD = ROOT / "custom_components/chihiros/www/chihiros-led-core-card.js"
DOSER_PLUGIN = ROOT / "custom_components/chihiros/plugins/doser/www/doser-plugin.js"
CTL_PLUGIN = ROOT / "custom_components/chihiros/plugins/ctl/www/ctl-plugin.js"
WIRESHARK_PLUGIN = ROOT / "custom_components/chihiros/plugins/wireshark/www/wireshark-plugin.js"
ADDON_SERVER = ROOT / "chihiros_beta/ui/server.py"


def source(path: Path) -> str:
    """Read one dashboard source file."""
    return path.read_text(encoding="utf-8")


def test_home_assistant_doser_sources_live_only_in_plugin() -> None:
    """Keep optional Doser implementation files out of the Home Assistant LED Core package."""
    integration = ROOT / "custom_components" / "chihiros"
    plugin = integration / "plugins" / "doser"
    required = {
        "backend.py",
        "button.py",
        "dosing.py",
        "entity.py",
        "number.py",
        "protocol.py",
        "registry.py",
        "runtime.py",
        "services.py",
        "storage.py",
        "types.py",
        "watcher.py",
    }
    assert required <= {path.name for path in plugin.glob("*.py")}
    assert not list((integration / "packages" / "doser").glob("*.py"))
    assert not list(integration.glob("doser_*.py"))
    assert not (integration / "dosing.py").exists()
    assert not (integration / "button.py").exists()
    assert not (integration / "number.py").exists()


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


def test_addon_keeps_one_canonical_doser_state_set() -> None:
    """HA Doser states must not create a second empty device beside the local database device."""
    server = source(ADDON_SERVER)

    doser_filter = server.split("is_chihiros_doser_entity = any(", 1)[1].split("is_chihiros_light", 1)[0]
    assert "if is_chihiros_doser_entity:" in doser_filter
    assert "continue" in doser_filter


def test_doser_interval_edit_uses_the_visible_stored_minutes() -> None:
    """The interval edit dialog restores e.g. ``20 min`` instead of falling back to zero."""
    plugin = source(DOSER_PLUGIN)

    assert 'const scheduleState = this.rawState(e.scheduleTimeSensor, "");' in plugin
    assert "const stateIntervalMatch = String(scheduleState).match(" in plugin
    assert "Number.isInteger(stateInterval) && stateInterval >= 0 && stateInterval <= 59" in plugin
    assert 'this.stateAttr(e.scheduleTimeSensor, "interval_minutes", "")' in plugin


def test_doser_timer_list_dialog_supports_24_individual_doses() -> None:
    """Timer-list editing exposes time and amount rows with the app limits."""
    plugin = source(DOSER_PLUGIN)
    dashboard = source(DASHBOARD)
    services = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "services.py")
    protocol = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "protocol.py")

    assert "data-schedule-timer-list" in plugin
    assert "data-schedule-timer-time" in plugin
    assert "data-schedule-timer-ml" in plugin
    assert "data-schedule-timer-remove" in plugin
    assert "data-schedule-unsent-warning" in plugin
    assert "Änderung noch nicht an das Gerät gesendet." in plugin
    assert "entries.length < 1 || entries.length > 24" in plugin
    assert "following - current < 10" in plugin
    assert 'timer_hint: "Bis zu 24 Einzeldosierungen; mindestens 10 Minuten Abstand."' in dashboard
    assert "Timerlisten brauchen 1 bis 24 Einzeldosierungen" in services
    assert "Zwischen Timer-Einzeldosierungen muessen mindestens 10 Minuten liegen" in services
    assert "TIMER_ENTRIES_PER_FRAME = 13" in protocol
    assert "TIMER_MAX_ENTRIES = 24" in protocol
    assert "frames.append(create_command_encoding(165, 21" in protocol


def test_doser_custom_dialog_uses_daily_amount_and_window_dose_counts() -> None:
    """Custom schedules expose app-style windows and enforce the 24/30 limits."""
    plugin = source(DOSER_PLUGIN)
    dashboard = source(DASHBOARD)
    services = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "services.py")
    protocol = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "protocol.py")

    assert 'kindOption("window", this.tr("custom_schedule"))' in plugin
    assert "data-schedule-window-list" in plugin
    assert "data-schedule-window-start" in plugin
    assert "data-schedule-window-end" in plugin
    assert "data-schedule-window-doses" in plugin
    assert "data.windows = windowEntries" in plugin
    assert 'custom_schedule: "Benutzerdefiniert"' in dashboard
    assert 'window_daily_amount: "Tagesdosierung gesamt"' in dashboard
    assert "totalDoses > 24" in plugin
    assert "duration > 30 * (doses - 1)" in plugin
    assert "insgesamt hoechstens 24 Dosierungen" in services
    assert "window_schedule_frames" in protocol
    assert "if not send_requested and requested_address:" in services
    assert "store = await async_store_for_device(hass, requested_address, 4)" in services
    assert "doser-schedule-service-v4-local-direct" in services
    assert "(attributes.timer_entries || attributes.window_entries)" in plugin
    assert "const sync = (notify = true)" in plugin
    assert "sync(false);" in plugin
    assert "doser-schedule-overview" in plugin
    assert "scheduleEditMode: false" in plugin
    assert 'data-action="schedule-edit:' in plugin
    assert "scheduleSnapshot" in plugin
    assert ".doser-schedule-overview-list" in dashboard
    assert "setScheduleRequestState(form," in plugin
    assert "data-schedule-request-status" in plugin
    assert 'send ? this.tr("debug_sending") : this.tr("saving")' in plugin
    assert "if (!saveOk || (send && !sendOk)) return;" in plugin
    assert "scheduleRequestSuccess:" in plugin
    assert 'requestSuccess ? "is-ok" : ""' in plugin
    assert 'requestSuccess ? "mdi:check-circle-outline" : "mdi:sync"' in plugin
    assert 'class="led-channel-history-close" data-action="close-dialog"' in plugin
    assert ".doser-schedule-request-status" in dashboard
    assert "doser-schedule-debug-result" in plugin
    assert ".doser-schedule-debug-result" in dashboard
    assert "create_command_encoding(165, 23" in protocol


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


def test_scheduler_row_send_atomically_replaces_device_schedule_with_one_row() -> None:
    """The row send button resets stale device slots and writes only the selected period."""
    panel = source(LED_PANEL)

    assert "async sendLedScheduleRowFromFront(rowIndex)" in panel
    assert "const period = this.ledSchedulePeriodsFromRows([row]" in panel
    assert 'service: "set_schedule"' in panel
    assert "data: { periods: [period], send: true, ...this.ledServiceSelector() }" in panel
    assert "const localPeriods = this.ledSchedulePeriodsFromRows(rows);" in panel
    assert "sendCurrentLedScheduleFromFront" not in panel


def test_scheduler_reset_debug_keeps_delete_and_verification_operations() -> None:
    """Reset diagnostics include delete frames as well as the final status query."""
    services = source(ROOT / "custom_components" / "chihiros" / "packages" / "led" / "services.py")
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
    override_branch = panel.split("if (Array.isArray(this._ledScheduleRowsOverride)) {", 1)[1].split(
        "const storageKeys = this.ledScheduleStorageKeys();", 1
    )[0]

    verification_mapping = (
        'verification_status: String(row && row.verification_status ? row.verification_status : "pending")'
    )
    assert verification_mapping in override_branch
    assert 'verified_at: String(row && row.verified_at ? row.verified_at : "")' in override_branch


def test_new_scheduler_dialog_keeps_entered_times_while_sending() -> None:
    """Status renders during a new-row send must reuse the submitted form values."""
    panel = source(LED_PANEL)

    assert "Array.isArray(dialog.ledScheduleDraftRows)" in panel
    assert "return dialog.ledScheduleDraftRows.map((row) => ({ ...row }));" in panel
    assert "this.dialogState.ledScheduleDraftRows = values.map((row) => ({" in panel


def test_scheduler_verification_waits_once_and_restores_two_visible_rows() -> None:
    """More than two rows use the device's two visible slots only for the delayed check."""
    services = source(ROOT / "custom_components" / "chihiros" / "packages" / "led" / "services.py")

    assert "await asyncio.sleep(60)" in services
    assert "initialize LED schedule storage" in services
    assert '"verification_scheduled": verification_scheduled' in services
    assert "await _remove_stored_schedule_rows(chihiros_data.device, stored_rows[:2])" in services
    assert "restore_rows = stored_rows[:2] if active and len(stored_rows) > 2 else []" in services
    assert "verification_scheduled = active" in services
    assert "chihiros_data.device.replace_settings(settings)," in services
    assert "timeout=LED_VERIFICATION_RESTORE_TIMEOUT" in services


def test_inactive_schedule_delete_only_removes_selected_row() -> None:
    """Deleting a row must not temporarily remove other stored schedules."""
    services = source(ROOT / "custom_components" / "chihiros" / "packages" / "led" / "services.py")

    assert "active = bool(call.data.get(ATTR_ACTIVE, True))" in services
    assert "restore_rows = stored_rows[:2] if active and len(stored_rows) > 2 else []" in services


def test_scheduler_verification_is_queued_per_schedule_row() -> None:
    """Two rows from one device must retain separate jobs and history results."""
    services = source(ROOT / "custom_components" / "chihiros" / "packages" / "led" / "services.py")
    storage = source(ROOT / "custom_components" / "chihiros" / "packages" / "led" / "storage.py")

    assert "task_key = f\"{device_key}|{target['start']}|{target['end']}\"" in services
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
    assert 'service === "add_schedule" || service === "set_schedule"' in index
    assert "await window.ChihirosAddonApi.refreshDashboard();" in panel


def test_scheduler_crud_and_debug_contracts_remain_available() -> None:
    """Scheduler create/edit/delete flows and config-driven debug remain wired."""
    panel = source(LED_PANEL)

    assert "openNewLedScheduleDialog()" in panel
    assert "openLedScheduleDialog(rowIndex = null)" in panel
    assert "async addLedSchedule(send = true)" in panel
    assert "async deleteLedScheduleRow(rowIndex = null, send = true)" in panel
    assert "Boolean(this.uiSettings && this.uiSettings.dashboardDebug)" in panel
    assert 'type: "debug"' in panel


def test_scheduler_front_delete_opens_running_dialog() -> None:
    """The front delete button immediately acknowledges the click while BLE is running."""
    panel = source(LED_PANEL)
    start = panel.index("async deleteLedScheduleRow(rowIndex = null, send = true)")
    end = panel.index("\n  ledEntityState(", start)
    implementation = panel[start:end]

    assert "if (this._ledScheduleSubmitting) return false;" in implementation
    assert "debug, dialog: true" in implementation


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
    assert 'if parsed.path == "/api/database-status":' in server
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


def test_manual_doser_debug_uses_the_config_setting_and_response_service() -> None:
    """Manual dosing inherits dashboard debug instead of adding another form checkbox."""
    plugin = source(DOSER_PLUGIN)

    assert "`dose-inline:${ch}`" in plugin
    assert "`press:${e.doseNow}`" not in plugin
    assert 'if (kind === "dose-inline")' in plugin
    assert "const debug = Boolean(this.uiSettings && this.uiSettings.dashboardDebug);" in plugin
    assert 'service: "dose_ml"' in plugin
    assert "data: { pump: channel, ml }" in plugin
    assert "dialog: debug" in plugin


def test_doser_calibration_keeps_prime_debug_and_reminder_wired() -> None:
    """Calibration exposes safe hose fill, config debug, and persisted renewal metadata."""
    plugin = source(DOSER_PLUGIN)
    dashboard = source(DASHBOARD)
    services = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "services.py")
    storage = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "storage.py")
    protocol = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "protocol.py")

    assert 'service: "prime_doser_calibration"' in plugin
    assert "data-calibration-prime-duration" in plugin
    assert 'data-action="calibration-open-measure:${ch.id}"' in plugin
    assert 'data-action="calibration-start-next:${ch.id}"' in plugin
    assert 'data-action="calibration-test:${ch.id}"' in plugin
    assert 'data-action="calibration-test-yes:${ch.id}"' in plugin
    assert 'data-action="calibration-test-retry:${ch.id}"' in plugin
    assert "calibrationIllustration(kind)" in plugin
    assert 'this.calibrationIllustration("hose")' in plugin
    assert 'this.calibrationIllustration("measure")' in plugin
    assert 'this.calibrationIllustration("exact")' in plugin
    assert 'this.calibrationIllustration("dry")' in plugin
    assert 'this.calibrationIllustration("test")' in plugin
    assert 'this.calibrationIllustration("done")' in plugin
    assert '${this.tr("step_label")} 3 · ${this.tr("measured_save")}' in plugin
    assert '${this.tr("measure_exact_hint")}' in plugin
    assert 'name="measured_ml" type="number" min="0.2" max="255.95" step="0.05"' in plugin
    assert "step: result && result.ok ? 3 : 2" in plugin
    assert 'service: "test_doser_calibration"' in plugin
    assert "step: result && result.ok ? 5 : 4" in plugin
    assert "step: 6" in plugin
    assert 'class="calibration-summary"' in plugin
    assert "calibratedDisplay: calibratedDisplay.toLocaleString()" in plugin
    assert "reminderDisplay: reminderDisplay.toLocaleDateString()" in plugin
    assert 'calibration_summary_reminder: "Erneut kalibrieren am"' in dashboard
    assert 'measure_prepare_text: "Messzylinder an das Ende des Dosierschlauchs stellen' in dashboard
    assert 'start_measure_hint: "Es werden ungefähr 2–4 mL dosiert.' in dashboard
    assert 'measure_exact_hint: "Messzylinder auf eine ebene Fläche stellen' in dashboard
    assert "Boolean(card.uiSettings && card.uiSettings.dashboardDebug)" in plugin
    assert 'name="reminder_days"' not in plugin
    assert "reminder_days: 30" in plugin
    assert 'calibrationSensor: this.entity("sensor", ch, "calibration")' in dashboard
    assert (
        ".calibration-modal { width:min(620px, calc(100vw - 40px)); max-height:calc(100vh - 40px); overflow:auto; }"
    ) in dashboard
    assert ".calibration-debug-output { min-height:80px; max-height:min(32vh, 300px); }" in dashboard
    assert ".sticky-actions { position:sticky; bottom:0;" in dashboard
    assert "SERVICE_PRIME_DOSER_CALIBRATION" in services
    assert "SERVICE_TEST_DOSER_CALIBRATION" in services
    assert "async_record_calibration" in services
    assert "CREATE TABLE IF NOT EXISTS doser_calibrations" in storage
    assert "params[2 + int(pump_idx)] = 1 if active else 0" in protocol
    assert "return divmod(hundredths_ml, 100)" in protocol
    assert "[25 + int(pump_idx), 255, 255]" in protocol
    calibration_prepare = protocol.split("def calibration_prepare_frames", 1)[1].split(
        "def calibration_prime_frames", 1
    )[0]
    assert "create_command_encoding(90," not in calibration_prepare
    assert 'connection_prelude="doser_manual"' in services
    assert "immediate_after_prelude=True" in services
    assert "async with operation_lock:" in services
    assert 'send_locked = getattr(device, "_send_command_locked", None)' in services


def test_manual_doser_debug_comparison_keeps_connection_prelude() -> None:
    """The compact comparison must retain both the 90 prelude and 165 Doser frames."""
    services = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "services.py")

    assert "render_protocol_debug(tx_commands={0x5A, 0xA5}, dedupe_rx=True)" in services


def test_doser_schedule_uses_shared_integration_device() -> None:
    """Schedule sending must not create a second BLE client beside the integration device."""
    services = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "services.py")

    schedule_sender = services.split("async def _send_doser_schedule(", 1)[1]
    assert "dosing_device = cast(DosingChihirosClient, chihiros_data.device)" in schedule_sender
    assert "await dosing_device.add_schedule(" in schedule_sender
    assert "await dosing_device.add_interval_schedule(" in schedule_sender
    assert "async_ble_device_from_address" not in schedule_sender


def test_doser_schedule_errors_never_hide_the_exception_type() -> None:
    """An exception without text must still identify its type and include device debug."""
    services = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "services.py")

    assert "error_text = str(ex).strip() or type(ex).__name__" in services
    assert "debug_output = debug_output or _device_protocol_debug(chihiros_data.device)" in services


def test_doser_total_reads_use_shared_integration_device() -> None:
    """Background and button total reads must not open competing BLE clients."""
    button = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "button.py")
    watcher = source(ROOT / "custom_components" / "chihiros" / "plugins" / "doser" / "watcher.py")

    assert "await dosing_device.read_auto_totals(" in button
    assert "await dosing_device.read_auto_totals(" in watcher
    assert "async_ble_device_from_address" not in button
    assert "async_ble_device_from_address" not in watcher


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


def test_plugin_translation_catalogs_are_complete_and_use_real_umlauts() -> None:
    """CTL and Wireshark provide matching DE/EN keys and proper German characters."""
    import re

    key_pattern = re.compile(r"^\s*([a-zA-Z0-9_]+):", re.MULTILINE)
    forbidden = ("Geraet", "Geraete", "fuer", "ausgefuehrt", "laeuft", "pruefen", "ausgewaehlt")

    for path in (CTL_PLUGIN, WIRESHARK_PLUGIN):
        plugin = source(path)
        german_catalog = plugin.split("de: {", 1)[1].split("en: {", 1)[0]
        english_catalog = plugin.split("en: {", 1)[1].split("},", 1)[0]
        assert set(key_pattern.findall(german_catalog)) == set(key_pattern.findall(english_catalog))
        assert not [word for word in forbidden if word in german_catalog]


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
    assert "Zeitplaene" in dashboard  # Legacy database spelling remains accepted during normalization.


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
    notification_ui = source(ROOT / "custom_components/chihiros/www/chihiros-notification-ui.js")
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
    assert (
        '<th>#</th>\n              <th>${this.tr("check_short")}</th>\n              <th>${this.tr("time")}</th>'
    ) in panel
    assert 'card.tr("meaning")' in notification_ui
    assert '<h3>${this.tr("notification_type")}</h3>' not in panel
    assert 'direction: "Richtung"' in dashboard
    assert 'direction: "Direction"' in dashboard


def test_led_and_doser_histories_use_shared_clean_timeline() -> None:
    """LED and Doser histories share one readable central timeline renderer."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)
    doser = source(DOSER_PLUGIN)

    assert "ledHistoryTimelineMarkup(rows, expanded = false)" in panel
    assert "return this.sharedHistoryTimelineMarkup(rows" in panel
    assert "return this.sharedHistoryPanel({" in doser
    assert "return this.sharedHistoryDialog({" in doser
    assert 'set_doser_schedule: "Zeitplan gespeichert"' in doser
    assert "this.historyParamsText(entry)" in doser
    assert 'data-addon-update="${this.addonSlug}"' not in doser
    assert "source.title\n      || options.title\n      || source.action" in dashboard
    assert "device.entity_prefix || device.alias || device.id" in doser
    assert '<p><b>${this.tr("channels")}</b><span>${this.channels.length}</span></p>' in doser
    assert "<p><b>BLE</b>" not in doser
    assert '<p><b>${this.tr("source")}</b>' not in doser
    assert 'class="led-history-timeline-entry' in dashboard
    assert '.replace(/\\b(?:light|switch|sensor)\\.[a-z0-9_.]+\\b/gi, "")' in dashboard
    assert ".led-history-timeline { position:relative;" in dashboard
    assert 'class="led-channel-history-close" data-action="close-dialog"' in panel
    assert 'return "&#9201;"' in dashboard
    assert 'return "&#128276;"' in dashboard
    assert 'return "&#8599;"' in dashboard
    assert 'return "&#128190;"' in dashboard
    assert 'return "&#128465;"' in dashboard
    assert 'return "&#128167;"' in dashboard
    assert "[this.resolveLedRuntimeEntity(device), this.resolveLedNotificationEntity(device)]" in panel
    assert "this._hass.config.time_zone" in dashboard
    assert "|| source.ts" in dashboard
    assert "|| entry && entry.ts" in panel
    assert 'entry.ts || `${entry.date || ""} ${entry.time || ""}`' in doser


def test_total_history_timestamp_uses_configured_language_and_first_row() -> None:
    """Timeline timestamps use DE/US ordering and share the action row."""
    panel = source(LED_PANEL)
    dashboard = source(DASHBOARD)

    assert "formatLedHistoryTimestamp(value)" not in panel
    assert "formatHistoryTimestamp(value)" in dashboard
    assert 'this.language() === "en" ? "en-US" : "de-DE"' in dashboard
    assert '${timestamp ? `<time>${this.escapeHtml(timestamp)}</time>` : ""}</div>' in dashboard
    assert ".led-history-timeline-copy time { margin-left:auto;" in dashboard


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
    assert "rawLabel.slice(localPrefix.length)" in panel
    assert '${scheduleRows.length} ${this.tr("schedule_count")}' in panel
    assert 'schedule_count: "Zeitpläne"' in dashboard
    assert 'schedule_count: "schedules"' in dashboard
    assert ".led-schedule-count {" in dashboard


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
    light = source(ROOT / "custom_components" / "chihiros" / "light.py")

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
    assert 'service: "set_schedule"' not in implementation
    assert "Auto-Mode-Entitaet nicht gefunden" not in implementation


def test_led_panel_does_not_load_device_plugins() -> None:
    """The LED Core entry point must not load optional device plugins."""
    panel_loader = source(ROOT / "custom_components/chihiros/www/chihiros-panel.js")

    assert 'enabled_tabs: ["led", "config"]' in panel_loader
    assert "installed_plugins: []" in panel_loader
    for plugin in ("doser", "wireshark", "ctl", "ruehrer", "heizer"):
        assert f"/chihiros_plugin_static/{plugin}/" not in panel_loader


def test_wireshark_long_capture_saves_periodic_snapshots() -> None:
    """Long captures save a root HCI snapshot every 15 minutes without ending capture."""
    plugin = source(WIRESHARK_PLUGIN)

    assert 'this.runAdbAction(card, "capture-snapshot"' in plugin
    assert "15 * 60 * 1000" in plugin
    assert 'data-wireshark-adb-action="capture-snapshot"' in plugin
    assert 'capture_snapshot_hint: "Langzeitmodus:' in plugin


def test_wireshark_compare_keeps_raw_notifications_visible() -> None:
    """The compare dialog includes selected Notify rows even without cmd/mode fields."""
    dashboard = source(DASHBOARD)

    assert "return `[INFO NOTIFY]  ${JSON.stringify(notification)}`;" in dashboard
    assert "raw.value_hex || raw.att_hex || raw.hex || frame.hex" in dashboard
    assert "language: this.language()," in dashboard


def test_led_notification_poll_uses_shared_device_poller() -> None:
    """LED supplies only its query details to the shared 15-minute poller."""
    integration = source(ROOT / "custom_components" / "chihiros" / "__init__.py")
    dashboard = source(DASHBOARD)
    panel = source(LED_PANEL)
    sensor = source(ROOT / "custom_components" / "chihiros" / "sensor.py")
    notification_poll = source(ROOT / "custom_components/chihiros/common/notification_poll.py")
    notification_ui = source(ROOT / "custom_components/chihiros/www/chihiros-notification-ui.js")

    notification_import = 'import "./chihiros-notification-ui.js?v='
    panel_import = 'import "./panels/chihiros-led-panel.js?v='
    assert notification_import in dashboard
    assert panel_import in dashboard
    assert dashboard.index(notification_import) < dashboard.index(panel_import)
    assert "NOTIFICATION_POLL_INTERVAL = timedelta(minutes=15)" in notification_poll
    assert "async_poll_device_notifications(" in integration
    assert 'device_type="led"' in integration
    assert "expected_modes=(0x0A, 0xFE)" in integration
    assert "async_track_notification_poll(hass, _async_poll_runtime)" in integration
    assert "if runtime.client.model.color_channels:" in integration
    assert "dosing_totals" not in integration
    assert "await runtime.client.query_status_active()" in integration
    assert "const nonLedDeviceKeys =" in panel
    assert '"doser", "dosing", "dose", "dydose", "dytdos", "pump"' in panel
    assert ".filter((device) => this.isLedDeviceConfig(device))" in panel
    assert "self._attr_force_update = description.key == ATTR_LAST_NOTIFICATION" in sensor
    assert 'return `${totalMinutes >= 5000 ? "≥ " : ""}${parts.join(" ")}`;' in panel
    assert "const localRows = this.ledScheduleRows().filter((row) => row && row.active !== false);" in panel
    assert '${this.tr("template_local")}: ${localRows.length} ${this.tr("schedule_count")}' in panel
    assert "window.ChihirosNotificationUi.render(this" in panel
    assert "window.ChihirosNotificationUi.render(this" in source(
        ROOT / "custom_components/chihiros/plugins/doser/www/doser-plugin.js"
    )
    doser_plugin = source(ROOT / "custom_components/chihiros/plugins/doser/www/doser-plugin.js")
    assert "doserStatusSnapshotDetails(model)" in doser_plugin
    assert '2: english ? "Timer list" : "Timerliste"' in doser_plugin
    assert '3: english ? "Custom" : "Benutzerdefiniert"' in doser_plugin
    assert "details: this.doserStatusSnapshotDetails(model)" in doser_plugin
    assert "this.__notificationDialogCaptureBound" in dashboard
    assert 'action === "led-notification-open"' in dashboard
    assert 'action.startsWith("dialog:doser-notification:")' in dashboard
    assert 'isDoser ? "doser-notification" : "led-notification"' in dashboard
    assert '["led-notification", "doser-notification"].includes' in dashboard
    assert "this.closeDialogState();" in dashboard
    assert "height:min(680px, calc(100vh - 40px))" in dashboard
    assert ".led-notification-dialog > .led-channel-history-head { flex:0 0 auto; }" in dashboard
    assert "min-height:0; overflow-y:auto" in dashboard
    assert 'sectionClass: "modal card led-notification-dialog"' in notification_ui
    assert "chihiros-notification-message-${scopeToken}" in notification_ui
    assert "chihiros-notification-tab-${scopeToken}-${index}" in notification_ui
    assert 'class="led-notification-tab-label"' in notification_ui
    assert 'class="led-notification-tab-panel"' in notification_ui
    assert "--notification-tab-count:${notifications.length}" in notification_ui
    active_tab_selector = (
        ".led-notification-tab-input:checked + .led-notification-tab-label + .led-notification-tab-panel"
    )
    assert active_tab_selector in dashboard
    assert 'subtitle: [deviceLabel, deviceAddress].filter(Boolean).join(" · ")' in doser_plugin
    assert "scope: dialogScope" in doser_plugin
    assert '0x0A: english ? "Runtime" : "Laufzeit"' in notification_ui
    assert '0x1E: english ? "Total values" : "Gesamtwerte"' in notification_ui
    assert '0x22: english ? "Daily values" : "Tageswerte"' in notification_ui
