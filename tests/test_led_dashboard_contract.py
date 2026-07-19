"""Regression contracts for the dependency-free LED dashboard frontend."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LED_PANEL = ROOT / "custom_components/chihiros/www/panels/chihiros-led-panel.js"
DASHBOARD = ROOT / "custom_components/chihiros/www/chihiros-led-core-card.js"
ADDON_SERVER = ROOT / "chihiros_beta/ui/server.py"


def source(path: Path) -> str:
    """Read one dashboard source file."""
    return path.read_text(encoding="utf-8")


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
