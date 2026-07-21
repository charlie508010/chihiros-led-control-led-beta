import "./chihiros-notification-ui.js?v=0.1.1";
import "./panels/chihiros-led-panel.js?v=0.2.1144";

class ChihirosLedCoreCard extends window.ChihirosLedPanelMixin(HTMLElement) {
  setConfig(config) {
    this.config = config || {};
    const previousLedDeviceId = this.activeLedDeviceId || "";
    const previousLedDevice = this.activeLedDevice || null;
    this.ledDevices = this.resolveLedDevices();
    const selectedLedDevice = this.ledDevices.find(
      (device) => String(device.id) === String(previousLedDeviceId),
    );
    if (selectedLedDevice) {
      this.applyLedDevice(previousLedDeviceId, false);
    } else if (previousLedDeviceId && previousLedDevice) {
      this.ledDevices = [...this.ledDevices, previousLedDevice];
    } else {
      this.activeLedDeviceId = (this.ledDevices[0] && this.ledDevices[0].id) || "";
      this.applyLedDevice(this.activeLedDeviceId, false);
    }
    this.uiSettings = this.loadUiSettings();
    this.applyChannelNames();
    this.activeTab = this.enabledCoreTabs().includes(this.uiSettings.activeTab)
      ? this.uiSettings.activeTab
      : this.enabledCoreTabs()[0];
    this.dialogState = this.dialogState || null;
    this.ledScheduleEditorOpen = Boolean(this.ledScheduleEditorOpen);
  }

  set hass(hass) {
    this._hass = hass;
    const previousLedDeviceId = this.activeLedDeviceId || "";
    const previousLedDevice = this.activeLedDevice || null;
    this.ledDevices = this.resolveLedDevices();
    const stillAvailable = this.ledDevices.some(
      (device) => String(device.id) === String(previousLedDeviceId),
    );
    if (stillAvailable) {
      this.activeLedDeviceId = previousLedDeviceId;
      this.applyLedDevice(this.activeLedDeviceId, false);
    } else if (!previousLedDeviceId) {
      this.activeLedDeviceId = (this.ledDevices[0] && this.ledDevices[0].id) || "";
      this.applyLedDevice(this.activeLedDeviceId, false);
    } else if (previousLedDevice) {
      this.ledDevices = [...this.ledDevices, previousLedDevice];
    }
    if (!this.dialogState) this.render();
  }

  connectedCallback() {
    this.render();
  }

  loadUiSettings() {
    const defaults = {
      language: String(this.config?.language || "").toLowerCase().startsWith("en") ? "en" : "de",
      showMac: this.config?.show_mac !== false,
      dashboardDebug: Boolean(this.config?.dashboard_debug),
      activeTab: "led",
      channelNames: {},
      deviceNames: {},
      deviceMaxPowerWatts: {},
    };
    try {
      const raw = window.localStorage.getItem(this.uiSettingsKey());
      const settings = raw ? { ...defaults, ...JSON.parse(raw) } : defaults;
      if (this.config?.addon_mode && Object.prototype.hasOwnProperty.call(this.config, "dashboard_debug")) {
        settings.dashboardDebug = Boolean(this.config.dashboard_debug);
      }
      return settings;
    } catch (_err) {
      return defaults;
    }
  }

  enabledCoreTabs() {
    const configured = Array.isArray(this.config?.enabled_tabs) ? this.config.enabled_tabs : ["led", "config"];
    const enabled = configured
      .map((tab) => String(tab || "").trim())
      .filter((tab, index, tabs) => (
        ["led", "config"].includes(tab) || Boolean(window.ChihirosPlugins && window.ChihirosPlugins[tab])
      ) && tabs.indexOf(tab) === index);
    return enabled.length ? enabled : ["led"];
  }

  coreTabIcon(tab) {
    if (tab === "config") {
      return `<svg class="tab-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1"/></svg>`;
    }
    return `<svg class="tab-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h16v8H4z"/><path d="M7 8V5m5 3V5m5 3V5M7 19v-3m5 3v-3m5 3v-3"/></svg>`;
  }

  pluginTitle(tab) {
    const plugin = window.ChihirosPlugins && window.ChihirosPlugins[tab];
    if (!plugin) return String(tab || "");
    if (typeof plugin.title === "function") return plugin.title(this);
    return String(plugin.title || tab);
  }

  pluginPanel(tab) {
    const plugin = window.ChihirosPlugins && window.ChihirosPlugins[tab];
    if (!plugin || typeof plugin.renderPanel !== "function") return "";
    return String(plugin.renderPanel(this) || "");
  }

  coreTabBar() {
    return `
      <nav class="device-tabs" aria-label="Chihiros LED Core">
        ${this.enabledCoreTabs().map((tab) => `
          <button type="button" data-tab="${tab}" class="${this.activeTab === tab ? "active" : ""}">
            ${this.coreTabIcon(tab)}
            <span>${["led", "config"].includes(tab) ? this.tr(tab) : this.escapeHtml(this.pluginTitle(tab))}</span>
          </button>`).join("")}
        ${this.config?.addon_mode ? `
          <button type="button" class="addon-update-button" data-addon-update>
            <svg class="tab-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></svg>
            <span data-addon-update-label>${this.tr("update")}</span>
          </button>` : ""}
      </nav>`;
  }

  addonDatabasePanel() {
    if (!this.config?.addon_mode) return "";
    const database = this.config.addon_database || {};
    const stateDbPath = String(
      database.state_db_path || database.integration_state_db_path || "/config/.chihiros_led_core/chihiros_led_core.sqlite3",
    );
    const effectiveState = String(database.effective_state_db_path || stateDbPath);
    const diagnosticsEnabled = Boolean(database.database_diagnostics_enabled);
    const retentionDays = Math.max(0, Math.min(3650, Number(database.diagnostic_retention_days) || 0));
    return `
      <section class="card config-card database-card">
        <div class="config-card-head">
          <div><h2>${this.tr("database")}</h2><small>${this.tr("database_subtitle")}</small></div>
          <span class="db-pill">${this.tr("integration_database")}</span>
        </div>
        <form data-addon-db-form>
          <small class="settings-note">${this.tr("recorder_storage_hint")}</small>
          <div class="db-current"><p><b>${this.tr("active_sqlite")}</b><span>${this.escapeHtml(effectiveState)}</span></p></div>
          <label class="config-check">
            <input type="checkbox" name="database_diagnostics_enabled" ${diagnosticsEnabled ? "checked" : ""}>
            <span><b>${this.tr("database_diagnostics")}</b><small>${this.tr("database_diagnostics_hint")}</small></span>
          </label>
          <label class="config-row wide">
            <span>${this.tr("diagnostic_retention")}</span>
            <input type="number" name="diagnostic_retention_days" min="0" max="3650" step="1" value="${retentionDays}">
          </label>
          <small class="settings-note">${this.tr("diagnostic_retention_hint")}</small>
          <div class="db-actions">
            <button type="button" class="link" data-addon-db-refresh>${this.tr("reload").toUpperCase()}</button>
            <button type="submit" class="primary">${this.tr("save").toUpperCase()}</button>
          </div>
        </form>
      </section>`;
  }

  configPanel() {
    const language = this.language();
    const showMac = this.uiSettings?.showMac !== false;
    const dashboardDebug = Boolean(this.uiSettings?.dashboardDebug);
    const powerOverrides = this.uiSettings?.deviceMaxPowerWatts || {};
    const pluginRows = Object.values(this.config?.plugin_assets || {})
      .filter((plugin) => plugin && plugin.id && plugin.id !== "led")
      .map((plugin) => `<div class="config-row wide">
        <span><strong>${this.escapeHtml(plugin.name || plugin.id)}</strong> · ${this.tr("version")} ${this.escapeHtml(plugin.version || "-")}</span>
        <button type="button" class="danger" data-plugin-uninstall="${this.escapeHtml(plugin.id)}">${this.tr("remove")}</button>
      </div>`).join("");
    const powerRows = (this.ledDevices || []).map((device) => {
      const id = String(device.id || "");
      const label = String(device.label || device.name || id);
      const value = Number(powerOverrides[id]);
      return `<label class="config-row wide"><span>${this.escapeHtml(label)} · W</span><input type="number" min="0.1" max="1000" step="0.1" value="${Number.isFinite(value) && value > 0 ? value : ""}" data-device-power-watts="${this.escapeHtml(id)}" placeholder="${this.tr("automatic")}"></label>`;
    }).join("");
    return `
      <div class="config-page">
        ${this.addonDatabasePanel()}
        <section class="card config-card">
          <h2>${this.tr("display")}</h2>
          <label class="config-row">
            <span>${this.tr("language_label")}</span>
            <select data-ui-setting="language">
              <option value="de" ${language === "de" ? "selected" : ""}>${this.tr("language_de")}</option>
              <option value="en" ${language === "en" ? "selected" : ""}>${this.tr("language_en")}</option>
            </select>
          </label>
          <label class="config-check">
            <input type="checkbox" data-ui-setting="showMac" ${showMac ? "checked" : ""}>
            <span>${this.tr("show_mac")}</span>
          </label>
          <label class="config-check">
            <input type="checkbox" data-ui-setting="dashboardDebug" ${dashboardDebug ? "checked" : ""}>
            <span>${this.tr("dashboard_debug")}</span>
          </label>
          <small class="settings-note">${this.tr("dashboard_debug_hint")}</small>
          <h3>${this.tr("rated_power")}</h3>
          <small class="settings-note">${this.tr("rated_power_hint")}</small>
          ${powerRows || `<small class="settings-note">${this.tr("no_device")}</small>`}
        </section>
        ${this.config?.addon_mode ? `<section class="card config-card">
          <h2>${this.tr("installed_plugins")}</h2>
          ${pluginRows || `<small class="settings-note">${this.tr("no_external_plugins")}</small>`}
          <small class="settings-note" data-plugin-uninstall-status></small>
        </section>
        <section class="card config-card">
          <h2>${this.tr("plugin_install")}</h2>
          <p class="settings-note">${this.tr("plugin_install_hint")}</p>
          <label class="config-row wide">
            <span>${this.tr("plugin_archive")}</span>
            <input type="file" accept=".tgz,.tar.gz,application/gzip" data-plugin-archive>
          </label>
          <div class="db-actions"><button type="button" class="primary" data-plugin-install>${this.tr("install")}</button></div>
          <small class="settings-note" data-plugin-install-status></small>
        </section>` : ""}
      </div>`;
  }

  updateDebug(state, label) {
    const lines = [label || "Update state"];
    if (!state) return `${lines[0]}: nicht vorhanden`;
    const attrs = state.attributes || {};
    lines.push(`state: ${state.state || ""}`);
    lines.push(`restored: ${Boolean(attrs.restored)}`);
    lines.push(`installed_version: ${attrs.installed_version || ""}`);
    lines.push(`latest_version: ${attrs.latest_version || ""}`);
    lines.push(`in_progress: ${Boolean(attrs.in_progress)}`);
    return lines.join("\n");
  }

  async runAddonUpdate() {
    this.dialogState = {
      type: "debug",
      channel: 1,
      output: "OK\nLED Core wird aktualisiert und neu gestartet...",
      running: true,
      noChannel: true,
      level: "pending",
    };
    this.render();
    try {
      const serviceFailure = (result) => {
        const response = result && typeof result === "object"
          ? (result.response || result.serviceResponse || null)
          : null;
        if (!response || typeof response !== "object") return "";
        if (response.ok !== false && String(response.send_status || "").toLowerCase() !== "fail") return "";
        return String(response.send_detail || response.message || response.error || "Home-Assistant-Service fehlgeschlagen");
      };
      const updateEntities = ["update.led_core_update", "update.chihiros_core_update"];
      let updateEntity = "";
      let updateState = null;
      if (this._hass && typeof this._hass.callApi === "function") {
        for (const candidate of updateEntities) {
          try {
            updateState = await this._hass.callApi("GET", `states/${candidate}`);
            if (updateState) {
              updateEntity = candidate;
              break;
            }
          } catch (_err) {
            // Try the next known entity name before using the Supervisor endpoint.
          }
        }
      }
      if (updateEntity && this._hass && typeof this._hass.callService === "function") {
        const refreshResult = await this._hass.callService("homeassistant", "update_entity", { entity_id: updateEntity });
        const refreshError = serviceFailure(refreshResult);
        if (refreshError) throw new Error(`homeassistant.update_entity fehlgeschlagen: ${refreshError}`);
        for (let attempt = 0; attempt < 30; attempt += 1) {
          updateState = await this._hass.callApi("GET", `states/${updateEntity}`);
          if (String(updateState && updateState.state || "").toLowerCase() === "on") break;
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
        }
        if (String(updateState && updateState.state || "").toLowerCase() === "on") {
          let startError = "";
          try {
            const installResult = await this._hass.callService("update", "install", { backup: false }, { entity_id: updateEntity });
            const installError = serviceFailure(installResult);
            if (installError) throw new Error(installError);
          } catch (error) {
            startError = error && error.message ? error.message : String(error);
          }
          for (let poll = 0; poll < 30; poll += 1) {
            await new Promise((resolve) => window.setTimeout(resolve, 1000));
            try {
              updateState = await this._hass.callApi("GET", `states/${updateEntity}`);
            } catch (error) {
              const message = error && error.message ? error.message : String(error);
              if (message.includes("502") || message.toLowerCase().includes("bad gateway")) continue;
              throw error;
            }
            const attrs = updateState && updateState.attributes ? updateState.attributes : {};
            if (String(updateState && updateState.state || "").toLowerCase() !== "on" && !attrs.in_progress) break;
          }
          const attrs = updateState && updateState.attributes ? updateState.attributes : {};
          const installed = String(attrs.installed_version || "");
          const latest = String(attrs.latest_version || "");
          if (installed && latest && installed === latest
            && String(updateState && updateState.state || "").toLowerCase() !== "on") {
            this.dialogState = {
              type: "debug",
              channel: 1,
              output: `OK\nUpdate abgeschlossen.\n${updateEntity}\nInstalliert: ${installed}\nLatest: ${latest}`,
              running: false,
              noChannel: true,
              level: "ok",
            };
            this.render();
            return;
          }
          if (startError) throw new Error(`update.install fehlgeschlagen: ${startError}`);
          this.dialogState = {
            type: "debug",
            channel: 1,
            output: `OK\nUpdate über ${updateEntity} gestartet.`,
            running: false,
            noChannel: true,
            level: "ok",
          };
          this.render();
          return;
        }
      }
      const api = window.ChihirosAddonApi;
      if (!api || typeof api.runAddonUpdate !== "function") throw new Error("LED-Core-Update-Endpunkt fehlt");
      const result = await api.runAddonUpdate();
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: `OK\n${String(result && result.message ? result.message : "LED Core wird neu gestartet.")}`,
        running: false,
        noChannel: true,
        level: "ok",
      };
      this.render();
    } catch (error) {
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: `FAIL\n${error && error.message ? error.message : error}`,
        running: false,
        noChannel: true,
        level: "error",
      };
      this.render();
    }
  }

  bindCoreEvents() {
    this.querySelectorAll("[data-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        const tab = String(button.getAttribute("data-tab") || "led");
        if (!this.enabledCoreTabs().includes(tab)) return;
        this.activeTab = tab;
        this.uiSettings = { ...(this.uiSettings || {}), activeTab: tab };
        this.saveUiSettings();
        this.render();
      });
    });
    this.querySelectorAll("[data-ui-setting]").forEach((input) => {
      input.addEventListener("change", async () => {
        const key = String(input.getAttribute("data-ui-setting") || "");
        if (!key) return;
        const value = input.type === "checkbox" ? Boolean(input.checked) : String(input.value || "");
        this.uiSettings = { ...(this.uiSettings || {}), [key]: value };
        this.saveUiSettings();
        if (key === "dashboardDebug") {
          const api = window.ChihirosAddonApi;
          const addonDatabase = { ...((this.config && this.config.addon_database) || {}) };
          this.config = {
            ...(this.config || {}),
            dashboard_debug: value,
            addon_database: { ...addonDatabase, dashboard_debug: value },
          };
          if (api && typeof api.saveDatabaseConfig === "function") {
            try {
              await api.saveDatabaseConfig({ ...addonDatabase, dashboard_debug: value });
            } catch (_err) {
              // Keep the local setting even if the add-on endpoint is temporarily unavailable.
            }
          }
        }
        this.render();
      });
    });
    this.querySelectorAll("[data-addon-db-form]").forEach((form) => {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const api = window.ChihirosAddonApi;
        if (!api || typeof api.saveDatabaseConfig !== "function") return;
        const data = new FormData(form);
        try {
          await api.saveDatabaseConfig({
            database_diagnostics_enabled: data.get("database_diagnostics_enabled") === "on",
            diagnostic_retention_days: Number(data.get("diagnostic_retention_days") || 0),
            dashboard_debug: Boolean(this.uiSettings && this.uiSettings.dashboardDebug),
          });
        } catch (error) {
          this.dialogState = {
            type: "debug",
            output: `FAIL\n${error && error.message ? error.message : error}`,
            running: false,
            level: "error",
          };
          this.render();
        }
      });
    });
    this.querySelectorAll("[data-addon-db-refresh]").forEach((button) => {
      button.addEventListener("click", async () => {
        const api = window.ChihirosAddonApi;
        if (api && typeof api.refreshDashboard === "function") await api.refreshDashboard();
      });
    });
    this.querySelectorAll("[data-addon-update]").forEach((button) => {
      button.addEventListener("click", async () => {
        const label = button.querySelector("[data-addon-update-label]");
        button.disabled = true;
        if (label) label.textContent = this.tr("updating");
        try {
          await this.runAddonUpdate();
        } catch (error) {
          button.disabled = false;
          if (label) label.textContent = this.tr("update");
          this.dialogState = {
            type: "debug",
            output: `FAIL\n${error && error.message ? error.message : error}`,
            running: false,
            level: "error",
          };
          this.render();
        }
      });
    });
    this.querySelectorAll("[data-device-power-watts]").forEach((input) => {
      input.addEventListener("change", () => {
        const id = String(input.getAttribute("data-device-power-watts") || "");
        const value = Number(input.value);
        const current = { ...((this.uiSettings && this.uiSettings.deviceMaxPowerWatts) || {}) };
        if (Number.isFinite(value) && value >= 0.1 && value <= 1000) current[id] = value;
        else delete current[id];
        this.uiSettings = { ...(this.uiSettings || {}), deviceMaxPowerWatts: current };
        this.saveUiSettings();
        this.render();
      });
    });
    this.querySelectorAll("[data-plugin-install]").forEach((button) => {
      button.addEventListener("click", async () => {
        const input = this.querySelector("[data-plugin-archive]");
        const status = this.querySelector("[data-plugin-install-status]");
        const file = input && input.files && input.files[0];
        if (!file) {
          if (status) status.textContent = this.tr("plugin_select_first");
          return;
        }
        button.disabled = true;
        if (status) status.textContent = this.tr("plugin_installing");
        try {
          const api = window.ChihirosAddonApi;
          if (!api || typeof api.installPlugin !== "function") throw new Error(this.tr("service_unavailable"));
          const result = await api.installPlugin(file);
          if (status) status.textContent = `${this.tr("plugin_installed")}: ${result.plugin} ${result.version}. ${this.tr("restart_addon")}`;
        } catch (error) {
          if (status) status.textContent = `${this.tr("plugin_install_failed")}: ${error && error.message ? error.message : error}`;
        } finally {
          button.disabled = false;
        }
      });
    });
    this.querySelectorAll("[data-plugin-uninstall]").forEach((button) => {
      button.addEventListener("click", async () => {
        const plugin = String(button.getAttribute("data-plugin-uninstall") || "");
        const status = this.querySelector("[data-plugin-uninstall-status]");
        if (!plugin || !window.confirm(this.tr("plugin_uninstall_confirm").replace("{plugin}", plugin))) return;
        button.disabled = true;
        if (status) status.textContent = this.tr("plugin_uninstalling");
        try {
          const api = window.ChihirosAddonApi;
          if (!api || typeof api.uninstallPlugin !== "function") throw new Error(this.tr("service_unavailable"));
          const result = await api.uninstallPlugin(plugin);
          if (status) status.textContent = `${this.tr("plugin_uninstalled")}: ${result.plugin}. ${this.tr("restart_addon")}`;
        } catch (error) {
          if (status) status.textContent = `${this.tr("plugin_uninstall_failed")}: ${error && error.message ? error.message : error}`;
        } finally {
          button.disabled = false;
        }
      });
    });
  }

  async addCoreHistory(action, detail = "", channel = null, options = {}) {
    const now = new Date();
    const overlayKey = String(options.overlayKey || "historyOverlay");
    const current = Array.isArray(this[overlayKey]) ? this[overlayKey] : [];
    const params = options.params && typeof options.params === "object" ? options.params : {};
    const status = Object.prototype.hasOwnProperty.call(options, "status") ? String(options.status || "") : "";
    const limit = Math.max(1, Math.min(500, Number(options.limit || 200)));
    const entry = {
      ts: now.toISOString(),
      date: now.toISOString().slice(0, 10),
      time: now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      action,
      detail,
      channel,
      status,
      params,
    };
    this[overlayKey] = [entry, ...current].slice(0, limit);
    this.render();
    const persisted = await this.persistCoreHistory(entry, options);
    if (persisted && typeof options.refresh === "function") await options.refresh();
    return entry;
  }

  applyChannelNames() {
    const names = (this.uiSettings && this.uiSettings.channelNames) || {};
    const baseChannels = Array.isArray(this.baseChannels) ? this.baseChannels : [];
    this.channels = baseChannels.map((channel) => ({
      ...channel,
      name: String(names[channel.id] || channel.name || "").trim() || channel.name,
    }));
  }

  async callAddonServiceWithDialog(service, data = {}, options = {}) {
    const mergedOptions = {
      noChannel: true,
      returnResponse: true,
      ...options,
    };
    const response = await this.callChihirosWithDialog(service, data, mergedOptions);
    const serviceResponse = this.serviceResponse(response, service);
    return {
      ok: this.serviceSendOk(serviceResponse),
      response,
      serviceResponse,
    };
  }

  async callChihiros(service, data = {}, returnResponse = false) {
    if (!this._hass) return;
    const serviceData = {
      address: this.deviceAddress,
      ...data,
    };
    const skipDashboardRefresh = Boolean(serviceData.__skip_dashboard_refresh);
    const cleanServiceData = Object.fromEntries(
      Object.entries(serviceData).filter(([key]) => key !== "__skip_dashboard_refresh")
    );
    const isMissingResponseSupport = (err) => {
      const message = String(err && err.message ? err.message : err || "");
      const body = String(err && err.body ? err.body : "");
      const code = Number(err && (err.code ?? err.status_code ?? err.status) || 0);
      return /Service does not support responses/i.test(message)
        || /Service does not support responses/i.test(body)
        || /400:\s*Bad Request/i.test(message)
        || /400:\s*Bad Request/i.test(body)
        || (code === 400 && (/Bad Request/i.test(message) || /Bad Request/i.test(body)));
    };
    const fallbackResponse = (err) => ({
      response: {
        ok: true,
        send_status: "ok",
        send_detail: "an Gerät gesendet",
        debug_output: "",
        response_fallback: true,
        response_fallback_error: String((err && err.message) || (err && err.body) || err || "400 Bad Request"),
      },
    });
    try {
      if (returnResponse && this._hass.connection && this._hass.connection.sendMessagePromise) {
        return await this._hass.connection.sendMessagePromise({
          type: "call_service",
          domain: "chihiros_led_core",
          service,
          service_data: cleanServiceData,
          return_response: true,
          skip_dashboard_refresh: skipDashboardRefresh,
        });
      }
      return await this._hass.callService("chihiros_led_core", service, {
        ...cleanServiceData,
      }, undefined, true, returnResponse);
    } catch (err) {
      if (!returnResponse || !isMissingResponseSupport(err)) throw err;
      await this._hass.callService("chihiros_led_core", service, { ...cleanServiceData });
      return fallbackResponse(err);
    }
  }

  async callChihirosWithDialog(service, data = {}, options = {}) {
    const channel = Number(options.channel || 1);
    const debug = Boolean(options.debug);
    const wantsResponse = options.returnResponse !== undefined ? Boolean(options.returnResponse) : false;
    this.dialogState = { type: "debug", channel, output: this.tr("debug_sending"), running: true, debug, noChannel: Boolean(options.noChannel), level: "pending" };
    this.render();
    try {
      const response = await this.callChihiros(service, data, wantsResponse);
      const output = this.serviceResultOutput(service, response, debug, options);
      this.dialogState = {
        type: "debug",
        channel,
        output,
        debug,
        noChannel: Boolean(options.noChannel),
        running: false,
        level: output.trim().startsWith("FAIL") ? "error" : "ok",
      };
      this.render();
      return response;
    } catch (err) {
      this.dialogState = {
        type: "debug",
        channel,
        output: `FAIL\nService: chihiros_led_core.${service}\n${err && err.message ? err.message : err}`,
        debug,
        noChannel: Boolean(options.noChannel),
        running: false,
        level: "error",
      };
      this.render();
      return null;
    }
  }

  closeDialog() {
    const state = this.dialogState || {};
    if (
      state.type === "led-template-editor"
      && state.templateLivePreviewChanged
      && typeof this.restoreLedAutoModeAfterTemplatePreview === "function"
    ) {
      if (typeof this.setLedManualScheduleWarning === "function") this.setLedManualScheduleWarning(false);
      this.restoreLedAutoModeAfterTemplatePreview();
    }
    return this.closeDialogState();
  }

  escapeHtml(value = "") {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async fetchCoreHistory(options = {}) {
    const deviceKey = String(options.device || "").trim().toUpperCase();
    const overlayKey = String(options.overlayKey || "historyOverlay");
    const loadingKey = String(options.loadingKey || `_${overlayKey}LoadingKey`);
    const scope = String(options.scope || "").trim();
    const limit = Math.max(1, Math.min(500, Number(options.limit || 200)));
    const force = Boolean(options.force);
    if (!deviceKey || (!force && this[loadingKey] === deviceKey)) return false;
    this[loadingKey] = deviceKey;
    try {
      const params = new URLSearchParams({ device: deviceKey, limit: String(limit) });
      if (scope) params.set("scope", scope);
      const response = await fetch(`./api/history?${params.toString()}`);
      if (!response.ok) return false;
      const data = await response.json();
      const entries = Array.isArray(data && data.entries) ? data.entries : [];
      const currentDevice = typeof options.currentDevice === "function"
        ? String(options.currentDevice() || "").trim().toUpperCase()
        : deviceKey;
      if (currentDevice !== deviceKey) return false;
      this[overlayKey] = entries.filter((entry) => entry && typeof entry === "object").slice(0, limit);
      this.render();
      return true;
    } catch (_err) {
      return false;
    } finally {
      if (this[loadingKey] === deviceKey) this[loadingKey] = "";
    }
  }

  filterHistoryEntries(entries = [], scope = "history") {
    const rows = Array.isArray(entries) ? entries : [];
    const selected = this.historyCombinedFilterValue(scope);
    if (selected.startsWith("status:")) {
      return rows.filter((entry) => this.historyEntryStatus(entry) === selected.slice(7));
    }
    if (selected.startsWith("type:")) {
      return rows.filter((entry) => this.historyEntryType(entry) === selected.slice(5));
    }
    return rows;
  }

  formatDebugJsonBlock(label, value) {
    if (value === undefined) return "";
    return `${label}:\n${JSON.stringify(value, null, 2)}`;
  }

  formatHistoryTimestamp(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    const parsed = new Date(text.includes("T") ? text : text.replace(" ", "T"));
    if (!Number.isFinite(parsed.getTime())) return text;
    const configuredTimeZone = String(this._hass && this._hass.config && this._hass.config.time_zone || "").trim();
    return new Intl.DateTimeFormat(this.language() === "en" ? "en-US" : "de-DE", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      ...(configuredTimeZone ? { timeZone: configuredTimeZone } : {}),
    }).format(parsed);
  }

  formatSharedDebugData(service, serviceResponse, options = {}) {
    const debugData = serviceResponse && serviceResponse.debug_data && typeof serviceResponse.debug_data === "object"
      ? serviceResponse.debug_data
      : null;
    const sectionOutput = Array.isArray(debugData && debugData.sections)
      ? debugData.sections.map((section) => this.formatSharedDebugSection(section)).filter(Boolean).join("\n\n")
      : "";
    if (sectionOutput) return sectionOutput;
    const rawDebug = this.normalizeDebugOutput(
      debugData && debugData.raw_debug !== undefined
        ? debugData.raw_debug
        : (serviceResponse && serviceResponse.debug_output ? serviceResponse.debug_output : "")
    );
    const debugService = debugData && debugData.service ? String(debugData.service) : `chihiros_led_core.${service}`;
    const lines = ["Debug", `Service: ${debugService}`];
    if (debugData && debugData.summary) lines.push(`Summary: ${debugData.summary}`);
    if (debugData && debugData.device) lines.push(`Device: ${debugData.device}`);
    if (debugData && debugData.address) lines.push(`Address: ${debugData.address}`);
    if (debugData && debugData.action) lines.push(`Action: ${debugData.action}`);
    const blocks = [lines.join("\n")];
    const responseJson = debugData && Object.prototype.hasOwnProperty.call(debugData, "response")
      ? debugData.response
      : serviceResponse;
    const detailsJson = debugData && Object.prototype.hasOwnProperty.call(debugData, "details")
      ? debugData.details
      : undefined;
    const detailsBlock = this.formatDebugJsonBlock("Details JSON", detailsJson);
    if (detailsBlock) blocks.push(detailsBlock);
    if (rawDebug) {
      const duplicateLines = new Set(["Debug", ...lines.slice(1)].map((line) => String(line || "").trim()).filter(Boolean));
      const sanitizedRawDebug = this.stripDebugMetaLines(
        this.stripDebugJsonBlocks(rawDebug, ["Request JSON", "Response JSON", "Details JSON"]),
        ["Summary", "Device", "Address", "Action", "Service"]
      );
      const rawLines = sanitizedRawDebug
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line && !duplicateLines.has(line) && !/^Protocol Debug$/i.test(line) && !/^Raw Debug$/i.test(line) && !/^[{}]+$/.test(line));
      const filteredRawDebug = rawLines.join("\n");
      if (filteredRawDebug) {
        blocks.push(`Raw Debug:\n${filteredRawDebug}`);
      }
    }
    return blocks.filter(Boolean).join("\n\n");
  }

  formatSharedDebugSection(section = {}) {
    if (!section || typeof section !== "object") return "";
    const title = String(section.title || "").trim();
    const type = String(section.type || "").trim().toLowerCase();
    const titleKey = title.toLowerCase();
    if (type === "json" && Object.prototype.hasOwnProperty.call(section, "value")) {
      if (titleKey === "request json") return "";
      if (titleKey === "response json") return "";
      return this.formatDebugJsonBlock(title || "JSON", section.value);
    }
    const value = String(section.value || section.text || "").trim();
    if (titleKey === "protocol debug") {
      const normalized = this.normalizeDebugOutput(value);
      return normalized && normalized.toLowerCase() !== "protocol debug" ? `Raw Debug\n${normalized}` : "";
    }
    if (titleKey === "raw debug") {
      const normalized = this.normalizeDebugOutput(value);
      return normalized ? `Raw Debug\n${normalized}` : "";
    }
    if (!value) return "";
    return title ? `${title}\n${value}` : value;
  }

  getCardSize() {
    return 8;
  }

  historyCombinedFilterValue(scope = "history") {
    const value = String((this._historyFilters && this._historyFilters[scope]) || "all").toLowerCase();
    const allowed = new Set([
      "all",
      "status:ok",
      "status:error",
      "type:scheduler",
      "type:device",
      "type:control",
      "type:settings",
      "type:other",
    ]);
    return allowed.has(value) ? value : "all";
  }

  historyEntryStatus(entry = {}) {
    const normalized = this.normalizeHistoryEntry(entry);
    const rawStatus = String(entry && entry.status ? entry.status : "").trim().toLowerCase();
    const suffixStatus = String(normalized.title || "").match(/\s+(ok|fail|failed|failure|error)$/i)?.[1]?.toLowerCase() || "";
    const status = rawStatus || suffixStatus;
    if (["fail", "failed", "failure", "error"].includes(status)) return "error";
    if (["ok", "success", "successful"].includes(status)) return "ok";
    return "other";
  }

  historyEntryType(entry = {}) {
    const normalized = this.normalizeHistoryEntry(entry);
    const text = [entry && entry.action, normalized.title]
      .map((value) => String(value || "").trim().toLowerCase())
      .filter(Boolean)
      .join(" ");
    if (/einstellung|setting|datenbank|database|vorlage|preset/.test(text)) return "settings";
    if (/scheduler|schedule|zeitplan|timer|auto[ -]?mode|automodus/.test(text)) return "scheduler";
    if (/ger(?:ä|ae)temeld|notification|firmware|laufzeit|runtime|tageswert|daily (?:value|total)|ger(?:ä|ae)teinformation|device information/.test(text)) return "device";
    if (/manuell|manual|led gesetzt|led set|an ger(?:ä|ae)t gesendet|device send|einschalten|ausschalten/.test(text)) return "control";
    return "other";
  }

  historyFiltersMarkup(scope = "history") {
    const selected = this.historyCombinedFilterValue(scope);
    const option = (value, label) => `<option value="${value}" ${selected === value ? "selected" : ""}>${label}</option>`;
    return `<div class="history-filter-bar">
      <label class="history-status-filter history-combined-filter">
        <span>${this.tr("history_filter")}</span>
        <select data-history-filter="${this.escapeHtml(scope)}">
          ${option("all", this.tr("all"))}
          <optgroup label="${this.tr("status")}">
            ${option("status:ok", "OK")}
            ${option("status:error", "ERROR / FAIL")}
          </optgroup>
          <optgroup label="${this.tr("history_type")}">
            ${option("type:scheduler", this.tr("history_type_scheduler"))}
            ${option("type:device", this.tr("history_type_device"))}
            ${option("type:control", this.tr("history_type_control"))}
            ${option("type:settings", this.tr("history_type_settings"))}
            ${option("type:other", this.tr("history_type_other"))}
          </optgroup>
        </select>
      </label>
    </div>`;
  }

  language() {
    const uiLanguage = String((this.uiSettings && this.uiSettings.language) || "").toLowerCase();
    if (uiLanguage === "de" || uiLanguage === "en") return uiLanguage;
    const configured = String(this.config.language || "").toLowerCase();
    if (configured === "de" || configured === "en") return configured;
    const hassLanguage = String(
      (this._hass && this._hass.locale && this._hass.locale.language) ||
      (this._hass && this._hass.language) ||
      ""
    ).toLowerCase();
    const lang = configured || hassLanguage;
    return lang.startsWith("en") ? "en" : "de";
  }

  localizeLedHistoryText(title = "", detail = "") {
    const currentSavedTitle = this.tr("led_schedule_saved");
    const currentSentText = this.tr("led_schedule_sent");
    const currentLocalText = this.tr("led_schedule_not_sent");
    const normalizedTitle = String(title || "").trim();
    const normalizedDetail = String(detail || "").trim();
    let localizedDetail = normalizedDetail
      .replace(/\b(?:Alle Tage|Every day)\b/gi, this.tr("all_days"))
      .replace(/\b(?:Kanal\/Kanaele|Kanal\/Kanäle|Channels?)\b/gi, this.tr("channels"))
      .replace(/\bZeitplaene\b/gi, "Zeitpläne")
      .replace(/\bGeraet\b/gi, "Gerät")
      .replace(/\bgeloescht\b/gi, "gelöscht")
      .replace(/\bunveraendert\b/gi, "unverändert");
    localizedDetail = localizedDetail
      .replace(/^(?:Zeitplan|Schedule)\s+(\d+)\s+(?:gesendet|sent)$/i, (_match, index) => `${this.tr("schedule")} ${index} ${this.tr("led_schedule_sent")}`)
      .replace(/^(?:Zeitplan|Schedule)\s+(\d+):/i, (_match, index) => `${this.tr("schedule")} ${index}:`)
      .replace(/Alle Zeitpläne am Gerät gelöscht; lokal unverändert/gi, this.tr("schedules_device_deleted_local_kept"));
    const detailRowsMatch = localizedDetail.match(/^(\d+)\s+.+?(?:sent to device|an Ger(?:ae|ä)t gesendet|lokal gespeichert, nicht gesendet)$/i);
    const isSavedTitle = /^(schedule saved|zeitplan gespeichert)$/i.test(normalizedTitle);
    const isScheduleSavedDetail = /(schedule rows sent to device|zeitplan-zeilen an geraet gesendet)$/i.test(normalizedDetail);
    const isLocalSavedDetail = /(saved locally, not sent|lokal gespeichert, nicht gesendet)$/i.test(normalizedDetail);
    if (/^schedule$/i.test(normalizedTitle)) {
      return { title: this.tr("schedule"), detail: localizedDetail };
    }
    if (/^last notification$/i.test(normalizedTitle)) {
      return { title: this.tr("last_notification"), detail: localizedDetail };
    }
    if (/^led notification fetch$/i.test(normalizedTitle)) {
      const received = normalizedDetail.match(/^(\d+) notification\(s\) received$/i);
      return {
        title: this.tr("notification_fetch"),
        detail: /insufficient authorization/i.test(normalizedDetail)
          ? this.tr("notification_fetch_unauthorized")
          : (received
            ? `${received[1]} ${this.tr("notification_fetch_received")}`
            : (/^no device notification received$/i.test(normalizedDetail) ? this.tr("notification_fetch_none") : localizedDetail)),
      };
    }
    if (/^led schedule verification$/i.test(normalizedTitle)) {
      const range = normalizedDetail.match(/^(\d{2}:\d{2}-\d{2}:\d{2}):/);
      const failed = /:\s*failed$/i.test(normalizedDetail);
      return {
        title: this.tr("schedule_verification"),
        detail: `${range ? `${range[1]} · ` : ""}${this.tr(failed ? "schedule_verification_failed" : "schedule_verification_ok")}`,
      };
    }
    if (/^firmware$/i.test(normalizedTitle)) {
      return { title: this.tr("firmware"), detail: localizedDetail };
    }
    if (/^schedule sensor$/i.test(normalizedTitle)) {
      return { title: this.tr("schedule_sensor"), detail: localizedDetail };
    }
    if (isSavedTitle) {
      if (detailRowsMatch && isScheduleSavedDetail) {
        return { title: currentSavedTitle, detail: `${detailRowsMatch[1]} ${this.tr("led_schedule_rows")} ${currentSentText}` };
      }
      if (detailRowsMatch && isLocalSavedDetail) {
        return { title: currentSavedTitle, detail: `${detailRowsMatch[1]} ${this.tr("led_schedule_rows")} ${currentLocalText}` };
      }
      if (isScheduleSavedDetail) return { title: currentSavedTitle, detail: currentSentText };
      if (isLocalSavedDetail) return { title: currentSavedTitle, detail: currentLocalText };
      return { title: currentSavedTitle, detail: localizedDetail };
    }
    if (/^(schedule sent to device|zeitplan an ger(?:ae|ä)t gesendet)(?:\s+(ok|fail))?$/i.test(normalizedTitle)) {
      const status = normalizedTitle.match(/\s+(ok|fail)$/i)?.[1] || "";
      return { title: `${this.tr("led_schedule_sent_action")}${status ? ` ${status}` : ""}`, detail: localizedDetail };
    }
    if (/^(schedule deleted|zeitplan gel(?:oe|ö)scht)$/i.test(normalizedTitle)) {
      return { title: this.tr("schedule_deleted"), detail: localizedDetail };
    }
    if (/^(led gesetzt|led set)$/i.test(normalizedTitle)) {
      return { title: this.tr("led_set"), detail: localizedDetail };
    }
    if (/^(enable auto mode|auto-modus aktivieren)$/i.test(normalizedTitle)) {
      return { title: this.tr("enable_auto_mode"), detail: localizedDetail };
    }
    if (/^(off|aus)$/i.test(normalizedTitle)) {
      return { title: this.tr("off"), detail: localizedDetail };
    }
    if (/^(on|an)$/i.test(normalizedTitle)) {
      return { title: this.tr("on"), detail: localizedDetail };
    }
    return { title: normalizedTitle, detail: localizedDetail };
  }

  normalizeDebugOutput(debugOutput = "") {
    let text = String(debugOutput || "");
    for (let index = 0; index < 2; index += 1) {
      const trimmed = text.trim();
      if (!(trimmed.startsWith("\"") && trimmed.endsWith("\""))) break;
      try {
        const parsed = JSON.parse(trimmed);
        if (typeof parsed !== "string") break;
        text = parsed;
      } catch (_err) {
        break;
      }
    }
    if (text.includes("\\n") || text.includes("\\t") || text.includes("\\r") || text.includes("\\\"")) {
      const slashPlaceholder = "\uE000";
      text = text
        .replace(/\\\\/g, slashPlaceholder)
        .replace(/\\r\\n/g, "\n")
        .replace(/\\n/g, "\n")
        .replace(/\\r/g, "\r")
        .replace(/\\t/g, "\t")
        .replace(/\\"/g, "\"")
        .replace(new RegExp(slashPlaceholder, "g"), "\\");
    }
    const lines = text.split("\n").map((line) => line.trimEnd());
    const filtered = [];
    let skipJsonBlock = false;
    let jsonDepth = 0;
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        if (!skipJsonBlock) filtered.push(line);
        continue;
      }
      if (/^Service Debug Marker:/i.test(trimmed)) continue;
      if (/^Response JSON:/i.test(trimmed)) {
        skipJsonBlock = true;
        jsonDepth = 0;
        continue;
      }
      if (skipJsonBlock) {
        jsonDepth += (trimmed.match(/\{/g) || []).length;
        jsonDepth -= (trimmed.match(/\}/g) || []).length;
        if (trimmed === "{") {
          jsonDepth = Math.max(jsonDepth, 1);
          continue;
        }
        if (jsonDepth <= 0 && !trimmed.startsWith("\"")) {
          skipJsonBlock = false;
        }
        if (skipJsonBlock) continue;
      }
      filtered.push(line);
    }
    const compact = filtered.filter((line) => line.trim());
    const reordered = [];
    const pendingDebug = [];
    let index = 0;
    while (index < compact.length) {
      const line = compact[index];
      const trimmed = line.trim();
      if (trimmed.startsWith("DEBUG") && trimmed.includes("Sending commands [")) {
        pendingDebug.push(line);
        index += 1;
        continue;
      }
      if (!trimmed.startsWith("[TX #")) {
        reordered.push(line);
        index += 1;
        continue;
      }
      const txBlock = [line];
      if (pendingDebug.length) txBlock.unshift(pendingDebug.shift());
      index += 1;
      while (index < compact.length) {
        const current = compact[index];
        const currentTrimmed = current.trim();
        const isSeparator = currentTrimmed && [...new Set(currentTrimmed)].length === 1 && currentTrimmed[0] === "-";
        if (isSeparator) {
          const next = compact[index + 1] || "";
          const nextTrimmed = String(next).trim();
          if (nextTrimmed.startsWith("DEBUG") && nextTrimmed.includes("Sending commands [")) {
            pendingDebug.push(next);
            reordered.push(...txBlock, current);
            index += 2;
            break;
          }
          const debugInside = txBlock.filter((entry) => {
            const value = String(entry).trim();
            return value.startsWith("DEBUG") && value.includes("Sending commands [");
          });
          const otherInside = txBlock.filter((entry) => {
            const value = String(entry).trim();
            return !(value.startsWith("DEBUG") && value.includes("Sending commands ["));
          });
          reordered.push(...debugInside, ...otherInside, current);
          index += 1;
          break;
        }
        txBlock.push(current);
        index += 1;
      }
      if (txBlock.length && (index >= compact.length)) {
        const debugInside = txBlock.filter((entry) => {
          const value = String(entry).trim();
          return value.startsWith("DEBUG") && value.includes("Sending commands [");
        });
        const otherInside = txBlock.filter((entry) => {
          const value = String(entry).trim();
          return !(value.startsWith("DEBUG") && value.includes("Sending commands ["));
        });
        reordered.push(...debugInside, ...otherInside);
      }
    }
    const collapsed = [];
    let previousSeparator = false;
    for (const line of reordered) {
      const trimmed = String(line).trim();
      const isSeparator = trimmed && [...new Set(trimmed)].length === 1 && trimmed[0] === "-";
      if (isSeparator && previousSeparator) continue;
      collapsed.push(line);
      previousSeparator = Boolean(isSeparator);
    }
    return collapsed.join("\n");
  }

  normalizeHistoryEntry(entry = {}, options = {}) {
    const source = entry && typeof entry === "object" ? entry : {};
    const color = String(source.color || options.color || "#03c9ff");
    const rawTitle = String(
      source.title
      || options.title
      || source.action
      || "History"
    );
    const timestamp = String(
      source.timestamp
      || source.ts
      || [source.date || "", source.time || ""].filter(Boolean).join(" ").trim()
      || options.timestamp
      || ""
    );
    let detail = String(source.detail || options.detail || "");
    if (Array.isArray(options.detailParts)) {
      detail = options.detailParts.filter(Boolean).join(" · ");
    }
    const translated = this.localizeLedHistoryText(rawTitle, detail);
    return {
      ...source,
      title: translated.title,
      detail: translated.detail,
      timestamp,
      color,
      actionTarget: source.actionTarget || options.actionTarget || "",
    };
  }

  openConfirmDialog(options = {}) {
    const confirmId = `confirm-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    this._confirmDialogActions = this._confirmDialogActions || {};
    this._confirmDialogActions[confirmId] = {
      onConfirm: typeof options.onConfirm === "function" ? options.onConfirm : null,
      onCancel: typeof options.onCancel === "function" ? options.onCancel : null,
    };
    this.dialogState = {
      type: "confirm",
      channel: Number(options.channel || 1),
      title: String(options.title || this.tr("reset_schedule")),
      message: String(options.message || ""),
      detail: String(options.detail || ""),
      confirmLabel: String(options.confirmLabel || this.tr("reset_schedule_yes")),
      cancelLabel: String(options.cancelLabel || this.tr("reset_schedule_no")),
      confirmId,
      noChannel: Boolean(options.noChannel),
    };
    this.render();
  }

  async persistCoreHistory(entry, options = {}) {
    try {
      const response = await fetch("./api/history", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          device: String(options.device || "").trim().toUpperCase(),
          scope: String(options.scope || "").trim(),
          action: entry && entry.action ? entry.action : "History",
          detail: entry && entry.detail ? entry.detail : "",
          channel: entry && entry.channel ? entry.channel : null,
          status: entry && Object.prototype.hasOwnProperty.call(entry, "status") ? entry.status : "",
          params: entry && entry.params && typeof entry.params === "object" ? entry.params : {},
        }),
      });
      return response.ok;
    } catch (_err) {
      return false;
    }
  }

  async resolveConfirmDialog(confirmed) {
    const state = this.dialogState;
    const confirmId = state && state.confirmId ? String(state.confirmId) : "";
    const actions = (this._confirmDialogActions && confirmId) ? this._confirmDialogActions[confirmId] : null;
    if (this._confirmDialogActions && confirmId) delete this._confirmDialogActions[confirmId];
    if (!actions) {
      this.closeDialog();
      return;
    }
    if (confirmed) {
      if (actions.onConfirm) await actions.onConfirm();
      return;
    }
    if (actions.onCancel) await actions.onCancel();
    else this.closeDialog();
  }

  async runDeviceService({ service = "", data = {}, title = "", debug = false, dialog = false, channel = 1, noChannel = true } = {}) {
    const serviceData = debug ? { ...data, debug: true } : data;
    if (dialog && typeof this.callAddonServiceWithDialog === "function") {
      const result = await this.callAddonServiceWithDialog(service, serviceData, {
        channel,
        noChannel,
        title,
        payload: serviceData,
        debug,
      });
      return {
        ok: Boolean(result && result.ok),
        output: typeof this.serviceResultOutput === "function"
          ? this.serviceResultOutput(service, result && result.response, debug, { title, payload: serviceData })
          : `${result && result.ok ? "OK" : "FAIL"}\n${title}`,
        response: result && result.response,
        serviceResponse: result && result.serviceResponse,
      };
    }
    if (typeof this.callChihiros !== "function") return { ok: false, output: `${title}\n${this.tr("service_unavailable")}` };
    try {
      const response = await this.callChihiros(service, serviceData, true);
      const serviceResponse = typeof this.serviceResponse === "function" ? this.serviceResponse(response, service) : response;
      const ok = typeof this.serviceSendOk === "function" ? this.serviceSendOk(serviceResponse) : true;
      const output = typeof this.serviceResultOutput === "function"
        ? this.serviceResultOutput(service, response, debug, { title, payload: serviceData })
        : `${ok ? "OK" : "FAIL"}\n${title}`;
      return { ok, output, response, serviceResponse };
    } catch (err) {
      return { ok: false, output: `FAIL\n${title}\n${err && err.message ? err.message : err}` };
    }
  }

  saveUiSettings() {
    try {
      window.localStorage.setItem(this.uiSettingsKey(), JSON.stringify(this.uiSettings || {}));
    } catch (_err) {
      // Local storage can be unavailable in restricted browser modes.
    }
  }

  serviceResponse(response, service = "") {
    if (!response) return response;
    const payload = response.response !== undefined ? response.response : response;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return payload;
    if (payload.debug_output !== undefined || payload.debug_data !== undefined || payload.send_status !== undefined || payload.ok !== undefined) return payload;
    const serviceKey = service ? `chihiros_led_core.${service}` : "";
    if (serviceKey && payload[serviceKey]) return payload[serviceKey];
    if (service && payload[service]) return payload[service];
    const values = Object.values(payload).filter((value) => value && typeof value === "object" && !Array.isArray(value));
    const match = values.find((value) => value.debug_output !== undefined || value.debug_data !== undefined || value.send_status !== undefined || value.ok !== undefined);
    return match || payload;
  }

  serviceResultOutput(service, response, debug = false, options = {}) {
    const serviceResponse = this.serviceResponse(response, service);
    const ok = this.serviceSendOk(serviceResponse);
    const title = options && options.title ? String(options.title) : "";
    const serviceLabel = String(service || "").includes(".") ? String(service || "") : `chihiros_led_core.${service}`;
    const status = serviceResponse && serviceResponse.send_status ? String(serviceResponse.send_status) : "";
    const reply = serviceResponse && serviceResponse.send_detail ? String(serviceResponse.send_detail) : "";
    const debugOutput = this.normalizeDebugOutput(serviceResponse && serviceResponse.debug_output ? serviceResponse.debug_output : "");
    const header = [
      ok ? "OK" : "FAIL",
      title,
      status ? `Status: ${status}` : "",
      reply ? `Antwort: ${reply}` : "",
    ].filter(Boolean).join("\n");
    const cleanupFinalDebug = (text) => String(text || "")
      .split("\n")
      .filter((line) => line.trim().toLowerCase() !== "protocol debug")
      .join("\n")
      .replace(/(?:\n\s*)+Raw Debug:\s*$/i, "")
      .replace(/(?:\n\s*)+Raw Debug\s*$/i, "")
      .trim();
    if (debug && (serviceResponse && serviceResponse.debug_data || debugOutput)) {
      return cleanupFinalDebug(`${header}\n\n${this.formatSharedDebugData(service, serviceResponse, options)}`);
    }
    if (debug && serviceResponse && serviceResponse.response_fallback) {
      return cleanupFinalDebug(`${header}\n\nDebug\nService: ${serviceLabel}\nHome Assistant nutzt noch die alte Service-Registrierung ohne Response-Support.\nDer Aufruf wurde automatisch ohne return_response wiederholt.`);
    }
    if (debug && options && options.payload !== undefined) {
      return cleanupFinalDebug(`${header}\n\nDebug\nService: ${serviceLabel}\nPayload:\n${JSON.stringify(options.payload, null, 2)}`);
    }
    return cleanupFinalDebug(header || this.tr("debug_empty"));
  }

  serviceSendOk(serviceResponse) {
    if (!serviceResponse || typeof serviceResponse !== "object") return true;
    if (serviceResponse.ok === false) return false;
    if (serviceResponse.ok === true) return true;
    return !serviceResponse.send_status || serviceResponse.send_status === "ok" || serviceResponse.send_status === "local";
  }

  setNumber(entity, value) {
    const number = Number.parseFloat(value);
    if (!entity || !this._hass || !Number.isFinite(number)) return;
    this._hass.callService("number", "set_value", { entity_id: entity, value: number });
  }

  sharedDebugDialog(options = {}) {
    const levelClass = options.level === "error" ? " error" : "";
    const title = String(options.title || (options.debug ? this.tr("debug_output") : this.tr("result_output")));
    const output = String(options.output || "");
    return this.sharedModalDialog({
      title,
      sectionClass: `modal card debug-modal${levelClass}`,
      bodyHtml: options.debug && !options.running
        ? this.debugOutputMarkup(output, levelClass)
        : `<div class="debug-output${levelClass}">${this.escapeHtml(output)}</div>`,
      actions: [
        ...(options.running ? [] : [{ action: "copy-debug:all", label: this.tr("copy_all"), className: "secondary", type: "button" }]),
        { action: "close-dialog", label: this.tr("close"), className: "link", type: "button", attrs: "data-close-dialog" },
      ],
    });
  }

  debugOutputSections(output = "") {
    const text = String(output || "").trim();
    if (!text) return [];
    const markers = ["Status", "Debug", "Doku / Kopieren", "Raw Debug", "VERGLEICH APP-LOG", "GERÄTEANTWORT", "Details JSON"];
    const lines = text.split(/\r?\n/);
    const sections = [];
    let current = { title: "", lines: [] };
    const push = () => {
      const value = current.lines.join("\n").trim();
      if (current.title || value) sections.push({ title: current.title, value });
    };
    lines.forEach((line) => {
      const trimmed = line.trim().replace(/:$/, "");
      if (/^box neu$/i.test(trimmed)) {
        push();
        current = { title: "", lines: [] };
        return;
      }
      if (/^bottom zum kop/i.test(trimmed)) return;
      if (markers.some((marker) => marker.toLowerCase() === trimmed.toLowerCase())) {
        push();
        current = { title: trimmed, lines: [] };
        return;
      }
      current.lines.push(line);
    });
    push();
    return sections.filter((section) => section.title || section.value);
  }

  debugOutputMarkup(output = "", levelClass = "") {
    const sections = this.debugOutputSections(output);
    if (!sections.length) return `<div class="debug-output${levelClass}">${this.escapeHtml(output)}</div>`;
    return `<div class="debug-section-list${levelClass}">${sections.map((section, index) => {
      const title = section.title || this.tr("debug_output");
      return `
        <section class="debug-section-box">
          <header>
            <span>${this.escapeHtml(title)}</span>
            <button type="button" data-action="copy-debug:${index}">${this.escapeHtml(this.tr("copy"))}</button>
          </header>
          <pre>${this.escapeHtml(section.value)}</pre>
        </section>`;
    }).join("")}</div>`;
  }

  async copyText(text = "") {
    const value = String(text || "");
    if (!value) return false;
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
      return true;
    }
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    if (!copied) throw new Error(this.tr("copy_failed"));
    return true;
  }

  async copyWithFeedback(button, text = "") {
    if (!button) {
      await this.copyText(text);
      return;
    }
    const originalLabel = button.textContent;
    button.disabled = true;
    try {
      await this.copyText(text);
      button.textContent = this.tr("copied");
      button.classList.add("ok");
    } catch (err) {
      button.textContent = this.tr("copy_failed");
      button.classList.add("error");
      throw err;
    } finally {
      window.setTimeout(() => {
        button.textContent = originalLabel;
        button.disabled = false;
        button.classList.remove("ok", "error");
      }, 1400);
    }
  }

  sharedDialogActions(buttons = []) {
    const items = Array.isArray(buttons) ? buttons : [];
    return items.map((button) => {
      const type = String(button && button.type ? button.type : "button");
      const action = button && button.action ? ` data-action="${this.escapeHtml(String(button.action))}"` : "";
      const classes = String(button && button.className ? button.className : "").trim();
      const attrs = String(button && button.attrs ? button.attrs : "");
      const icon = button && button.icon
        ? `<ha-icon icon="${this.escapeHtml(String(button.icon))}"></ha-icon>`
        : "";
      const label = button && button.label ? `<span>${this.escapeHtml(String(button.label))}</span>` : "";
      return `<button type="${type}" class="${this.escapeHtml(classes)}"${action}${attrs ? ` ${attrs}` : ""}>${icon}${label}</button>`;
    }).join("");
  }

  sharedHistoryIconSymbol(title = "") {
    const text = String(title || "").toLowerCase();
    if (text.includes("firmware")) return "&#9881;";
    if (text.includes("meldung") || text.includes("notification")) return "&#128276;";
    if (text.includes("laufzeit") || text.includes("runtime")) return "&#9201;";
    if (text.includes("zeitplan") || text.includes("schedule")) return "&#128197;";
    if (text.includes("gelöscht") || text.includes("deleted") || text.includes("reset")) return "&#128465;";
    if (text.includes("gespeichert") || text.includes("saved")) return "&#128190;";
    if (text.includes("gesendet") || text.includes("sent")) return "&#8599;";
    if (text.includes("auto")) return "&#8635;";
    return "&#9679;";
  }

  sharedHistoryTimelineMarkup(entries = [], options = {}) {
    const rows = Array.isArray(entries) ? entries : [];
    const emptyLabel = String(options.emptyLabel || this.tr("no_history"));
    const emptyAction = options.emptyAction ? String(options.emptyAction) : "";
    const rowAction = typeof options.rowAction === "function" ? options.rowAction : null;
    const colorFallback = String(options.color || "#03c9ff");
    const expanded = Boolean(options.expanded);
    if (!rows.length) {
      return `
        <div class="history-empty"${emptyAction ? ` data-action="${this.escapeHtml(emptyAction)}"` : ""}>
          <ha-icon icon="mdi:history"></ha-icon>
          <span>${this.escapeHtml(emptyLabel)}</span>
        </div>`;
    }
    const items = rows.map((entry) => {
      const action = rowAction ? rowAction(entry) : (entry && entry.actionTarget ? String(entry.actionTarget) : "");
      const normalized = this.normalizeHistoryEntry(entry, {
        title: entry && entry.action ? entry.action : "History",
        color: entry && entry.color ? entry.color : colorFallback,
      });
      const rawStatus = String(entry && entry.status ? entry.status : "").trim().toLowerCase();
      const suffixStatus = String(normalized.title || "").match(/\s+(ok|fail|error)$/i)?.[1]?.toLowerCase() || "";
      const status = rawStatus || suffixStatus;
      const failed = ["fail", "failed", "failure", "error"].includes(status);
      const title = String(normalized.title || "History").replace(/\s+(?:ok|fail|error)$/i, "").trim();
      const detail = String(normalized.detail || "")
        .replace(/\b(?:light|switch|sensor)\.[a-z0-9_.]+\b/gi, "")
        .replace(/(?:^|\s*[·;]\s*)Status:\s*(?:ok|fail)(?=\s*[·;]|$)/gi, "")
        .replace(/\s*[·;]\s*$/, "")
        .trim();
      const timestamp = this.formatHistoryTimestamp(normalized.timestamp);
      const color = failed ? "#ff5b63" : String(normalized.color || colorFallback);
      return `
        <article class="led-history-timeline-entry ${failed ? "fail" : ""}"${action ? ` data-action="${this.escapeHtml(action)}"` : ""}>
          <span class="led-history-timeline-icon" style="color:${this.escapeHtml(color)}" aria-hidden="true">${this.sharedHistoryIconSymbol(title)}</span>
          <div class="led-history-timeline-copy">
            <div><strong>${this.escapeHtml(title)}</strong>${status ? `<span class="led-history-status ${failed ? "fail" : status}">${this.escapeHtml(status.toUpperCase())}</span>` : ""}${timestamp ? `<time>${this.escapeHtml(timestamp)}</time>` : ""}</div>
            ${detail ? `<p>${this.escapeHtml(detail)}</p>` : ""}
          </div>
        </article>`;
    }).join("");
    return `<div class="led-history-timeline ${expanded ? "expanded" : ""}">${items}</div>`;
  }

  sharedIconActionButtons(buttons = [], options = {}) {
    const items = Array.isArray(buttons) ? buttons : [];
    const wrapperClass = String(options.wrapperClass || "led-schedule-front-actions").trim();
    const defaultButtonClass = String(options.buttonClass || "mini").trim();
    const html = items.map((button) => {
      const type = String(button && button.type ? button.type : "button");
      const action = button && button.action ? ` data-action="${this.escapeHtml(String(button.action))}"` : "";
      const attrs = String(button && button.attrs ? button.attrs : "");
      const classes = [defaultButtonClass, String(button && button.className ? button.className : "").trim()]
        .filter(Boolean)
        .join(" ");
      const title = button && button.title ? ` title="${this.escapeHtml(String(button.title))}"` : "";
      const icon = button && button.icon
        ? `<ha-icon icon="${this.escapeHtml(String(button.icon))}"></ha-icon>`
        : "";
      const label = button && button.label ? `<span>${this.escapeHtml(String(button.label))}</span>` : "";
      return `<button class="${this.escapeHtml(classes)}" type="${type}"${action}${title}${attrs ? ` ${attrs}` : ""}>${icon}${label}</button>`;
    }).join("");
    return `<div class="${this.escapeHtml(wrapperClass)}">${html}</div>`;
  }

  sharedModalDialog(options = {}) {
    const title = String(options.title || "");
    const sectionClass = String(options.sectionClass || "modal card");
    const headerHtml = options.headerHtml ? String(options.headerHtml) : `<h2>${this.escapeHtml(title)}</h2>`;
    const bodyHtml = options.bodyHtml ? String(options.bodyHtml) : "";
    const footerHtml = options.footerHtml ? String(options.footerHtml) : "";
    const actionsHtml = Array.isArray(options.actions) && options.actions.length
      ? `<div class="modal-actions${options.actionsClass ? ` ${this.escapeHtml(String(options.actionsClass))}` : ""}">${this.sharedDialogActions(options.actions)}</div>`
      : "";
    return `
      <div class="modal-backdrop">
        <section class="${this.escapeHtml(sectionClass)}">
          ${headerHtml}
          ${bodyHtml}
          ${footerHtml || actionsHtml}
        </section>
      </div>`;
  }

  stripDebugJsonBlocks(debugOutput = "", labels = []) {
    const labelSet = new Set((Array.isArray(labels) ? labels : []).map((label) => String(label || "").trim().toLowerCase()).filter(Boolean));
    if (!labelSet.size) return String(debugOutput || "");
    const lines = String(debugOutput || "").split("\n");
    const filtered = [];
    let skipJsonBlock = false;
    let jsonDepth = 0;
    for (const line of lines) {
      const trimmed = line.trim();
      const normalized = trimmed.toLowerCase();
      if (!skipJsonBlock && labelSet.has(normalized.replace(/:$/, ""))) {
        skipJsonBlock = true;
        jsonDepth = 0;
        continue;
      }
      if (skipJsonBlock) {
        jsonDepth += (trimmed.match(/\{/g) || []).length;
        jsonDepth -= (trimmed.match(/\}/g) || []).length;
        if (trimmed === "{") {
          jsonDepth = Math.max(jsonDepth, 1);
          continue;
        }
        if (jsonDepth <= 0 && !trimmed.startsWith("\"")) {
          skipJsonBlock = false;
        }
        if (skipJsonBlock) continue;
        if (!trimmed) continue;
      }
      filtered.push(line);
    }
    return filtered.join("\n");
  }

  stripDebugMetaLines(debugOutput = "", labels = []) {
    const labelSet = new Set((Array.isArray(labels) ? labels : []).map((label) => String(label || "").trim().toLowerCase()).filter(Boolean));
    if (!labelSet.size) return String(debugOutput || "");
    return String(debugOutput || "")
      .split("\n")
      .filter((line) => {
        const trimmed = String(line || "").trim().toLowerCase();
        if (!trimmed) return true;
        if (trimmed === "debug") return false;
        return ![...labelSet].some((label) => trimmed === label || trimmed.startsWith(`${label}:`));
      })
      .join("\n");
  }

  tr(key) {
    const dict = {
      de: {
        unknown: "Unbekannt",
        press: "Drücken",
        start: "Start",
        change: "Ändern",
        add: "Hinzufügen",
        show: "Anzeigen",
        edit: "Bearbeiten",
        details: "Details",
        close: "Schließen",
        cancel: "Abbrechen",
        apply: "Übernehmen",
        save: "Speichern",
        save_send: "Speichern und senden",
        delete: "Löschen",
        delete_send: "Löschen und senden",
        delete_all: "Alle Zeitpläne auf Gerät löschen",
        enable_auto_mode: "Auto-Modus aktivieren",
        new: "Neu",
        on: "an",
        off: "aus",
        auto_mode: "Auto Mode",
        control: "Steuerung",
        send_to_device: "An Gerät senden",
        until: "bis",
        template: "Vorlage",
        template_name_prompt: "Name für Vorlage",
        template_saved: "Template gespeichert",
        template_deleted: "Vorlage gelöscht",
        template_delete_blocked: "Nur lokale Vorlagen können im Dialog gelöscht werden.",
        template_not_found: "Template nicht gefunden",
        template_live_preview: "Live-Vorschau",
        template_live_preview_hint: "Änderungen sofort an das Gerät senden",
        template_live_preview_sent: "Live-Vorschau gesendet",
        template_live_preview_failed: "Live-Vorschau fehlgeschlagen",
        template_list: "Vorlagenliste",
        template_count: "Vorlagen",
        schedule_count: "Zeitpläne",
        template_source: "Template-Quelle",
        template_standard: "Standard",
        template_local: "Lokal",
        share: "Teilen",
        share_template: "Template teilen",
        target_device: "Zielgerät",
        template_shared: "Template geteilt",
        no_compatible_led: "Keine andere LED mit gleicher Kanalanzahl gefunden.",
        share_schedule: "Zeitplan teilen",
        schedule_shared: "Zeitplan geteilt",
        send_to_device_now: "Direkt an Gerät senden",
        start_time: "Startzeit",
        end_time: "Endzeit",
        switch_on: "Einschalten",
        switch_off: "Ausschalten",
        hours: "Stunden",
        minutes: "Minuten",
        all: "Alle",
        run_weekdays: "An welchen Tagen ausführen",
        sunrise_sunset: "Sonnenaufgang / Sonnenuntergang",
        ramp_templates: "Ramp-Vorlagen",
        minutes_0: "0 Minuten",
        minutes_30: "30 Minuten",
        hour_1_short: "1 Std",
        hour_1: "1 Stunde",
        hour_1_5_short: "1.5 Std",
        hour_1_5: "1 Stunde 30 Minuten",
        hour_2_short: "2 Std",
        hour_2: "2 Stunden",
        hour_2_5_short: "2.5 Std",
        hour_2_5: "2 Stunden 30 Minuten",
        red: "Rot",
        green: "Grün",
        blue: "Blau",
        white: "Weiß",
        color_channels: "Farbkanäle",
        total: "Gesamt",
        complete_lamp: "Lampe komplett",
        complete_lamp_toggle: "Lampe komplett einschalten / ausschalten",
        complete_lamp_on: "Lampe komplett einschalten",
        complete_lamp_off: "Lampe komplett ausschalten",
        led_scheduler: "LED Zeitplan",
        led_schedule_summary_subtitle: "Zusammenfassung der aktiven Zeitfenster",
        led_schedule_save_send: "LED Zeitplan speichern und senden",
        led_schedule_save_local: "LED Zeitplan speichern",
        led_schedule_saved: "Zeitplan gespeichert",
        led_schedule_sent_action: "Zeitplan an Gerät gesendet",
        led_schedule_sent: "an Gerät gesendet",
        led_schedule_not_sent: "lokal gespeichert, nicht gesendet",
        led_schedule_rows: "Zeitplan-Zeilen",
        schedule_sent: "Zeitplan gesendet",
        schedules_sent: "Zeitpläne gesendet",
        schedule_deleted: "Zeitplan gelöscht",
        schedules_deleted: "Zeitpläne gelöscht",
        schedule_local_deleted: "Zeitplan lokal gelöscht",
        schedules_device_deleted_local_kept: "Alle Zeitpläne am Gerät gelöscht; lokale Daten unverändert",
        led_set: "LED gesetzt",
        all_days: "Alle Tage",
        channels: "Kanäle",
        brightness_changed: "Helligkeit geändert",
        channel_switched_off: "Kanal ausgeschaltet",
        sending: "Senden läuft...",
        saving: "Speichern läuft...",
        local_save_failed: "Lokales Speichern fehlgeschlagen",
        send_failed: "Senden fehlgeschlagen",
        service_unavailable: "Service nicht verfügbar",
        led_set_failed: "LED konnte nicht gesetzt werden",
        notification_fetch: "Gerätemeldungen abrufen",
        notification_fetch_none: "Keine Geräteantwort empfangen",
        notification_fetch_received: "Geräterückmeldungen empfangen",
        notification_fetch_unauthorized: "BLE-Zugriff abgelehnt. Andere Bluetooth-Verbindungen zum Gerät trennen.",
        no_led_channels: "Keine Chihiros-LED-Kanäle gefunden",
        reply: "Antwort",
        reply_sent: "an Gerät gesendet",
        reply_local: "nur lokal gespeichert",
        running: "LÄUFT",
        last_notification: "Letzte Meldung",
        fetched_at: "Geholt um",
        notification_type: "Meldungstyp",
        raw_frame: "Rohframe",
        decode: "Dekodierung",
        encode_hex: "Encode / Hex",
        parameters: "Parameter",
        message_id: "Message-ID",
        checksum: "Prüfsumme",
        direction: "Richtung",
        command: "Befehl",
        length: "Länge",
        meaning: "Bedeutung",
        verified: "Geprüft",
        schedule_verification: "Zeitplan geprüft",
        schedule_verification_ok: "Gerätezeitplan stimmt überein",
        schedule_verification_failed: "Gerätezeitplan weicht ab",
        check_short: "OK",
        mismatch: "Abweichung",
        not_checked: "Nicht geprüft",
        schedule_count: "Zeitpläne",
        firmware: "Firmware",
        runtime: "Laufzeit",
        runtime_day: "Tag",
        runtime_days: "Tage",
        runtime_hour_short: "Std.",
        runtime_minute_short: "Min.",
        schedule_sensor: "Zeitplan-Sensor",
        no_schedule_read: "Kein Zeitplan gelesen",
        led_manual_schedule_warning: "Manuelle Steuerung ist aktiv. Automatikmodus wieder aktivieren, bevor automatische Zeitpläne ausgeführt werden.",
        max_value: "Max",
        max_range: "Bereich",
        current_plan: "Aktueller Plan",
        device: "Gerät",
        device_name: "Gerätename",
        change_device_name: "Gerätename ändern",
        led: "LED",
        config: "Config",
        display: "Anzeige",
        language_label: "Sprache",
        language_de: "Deutsch",
        language_en: "Englisch",
        show_mac: "MAC-Adresse anzeigen",
        channel_names: "Kanalnamen",
        database: "Datenbank",
        database_subtitle: "Scheduler, Vorlagen, Übertragungsstatus und Diagnosen",
        integration_database: "LED-Core-Speicher",
        plugin_install: "Plugin installieren",
        installed_plugins: "Installierte Plugins",
        no_external_plugins: "Keine externen Plugins installiert.",
        version: "Version",
        remove: "Entfernen",
        plugin_install_hint: "Vertrauenswürdiges TGZ hochladen. Das Plugin wird erst nach einem Neustart des LED-Core-Add-ons geladen.",
        plugin_archive: "TGZ-Datei",
        plugin_select_first: "Bitte zuerst eine TGZ-Datei auswählen.",
        plugin_installing: "Plugin wird geprüft und installiert …",
        plugin_installed: "Plugin installiert",
        plugin_install_failed: "Plugin-Installation fehlgeschlagen",
        plugin_uninstall_confirm: "Plugin {plugin} entfernen? Es wird in ein datiertes Backup verschoben.",
        plugin_uninstalling: "Plugin wird sicher entfernt …",
        plugin_uninstalled: "Plugin entfernt",
        plugin_uninstall_failed: "Plugin konnte nicht entfernt werden",
        restart_addon: "LED-Core-Add-on neu starten.",
        install: "Installieren",
        rated_power: "Nennleistung",
        estimated_power: "Geschätzter Verbrauch; kein Messwert",
        rated_power_hint: "Optionale Leistung für Controller oder Modelle ohne eindeutig erkennbare Größe. Sie hat Vorrang vor der automatischen Erkennung.",
        automatic: "automatisch",
        recorder_storage_hint: "Entity-Zustände, History und Statistiken bleiben im Home-Assistant-Recorder.",
        own_database: "Eigene DB",
        active_sqlite: "Aktive SQLite",
        database_diagnostics: "DB-Diagnose",
        database_diagnostics_hint: "Gespeicherte LED-Zeitpläne und offene Prüfaufträge anzeigen",
        diagnostic_retention: "Diagnose-Aufbewahrung (Tage)",
        diagnostic_retention_hint: "0 = unbegrenzt; betrifft nur regelmäßige BLE-Diagnosemeldungen.",
        database_status: "Scheduler-Datenbankstatus",
        database_open: "Geöffnet",
        database_closed: "Nicht geöffnet",
        database_stored_schedules: "Gespeicherte Zeitpläne",
        database_verification_jobs: "Offene Zeitplanprüfungen",
        database_request: "Abfrage",
        database_no_rows: "Kein Ergebnis für dieses Gerät.",
        database_result: "Ergebnis",
        loading: "Wird geladen...",
        inactive: "Inaktiv",
        failed: "Fehlgeschlagen",
        database_column_position: "Nr.",
        database_column_time_window: "Zeit",
        database_column_levels: "Kanäle",
        database_column_ramp_minutes: "Rampe",
        database_column_active: "Aktiv",
        database_column_verification: "Prüfung",
        database_column_verified_at: "Geprüft am",
        database_column_target: "Zielzeitplan",
        database_column_restore_rows: "Wiederherstellung",
        database_column_due_at: "Fällig",
        database_column_created_at: "Erstellt",
        database_file: "Datei",
        database_size: "Größe",
        database_rows: "Zeilen",
        database_parameters: "Parameter",
        error: "Fehler",
        reload: "Neu laden",
        update: "Update",
        updating: "Update läuft …",
        command_copied: "Befehl kopiert",
        copy: "Kopieren",
        copy_all: "Alles kopieren",
        copied: "Kopiert",
        copy_failed: "Kopieren fehlgeschlagen",
        no_entities: "Keine passenden Home-Assistant-Entities gefunden.",
        status: "Status",
        active: "Aktiv",
        today: "Heute",
        time: "Zeit",
        planned_amount: "Planmenge",
        history: "Historie",
        history_total: "Historie gesamt",
        history_filter: "Filter",
        history_type: "Art",
        history_type_scheduler: "Scheduler",
        history_type_device: "Geräteinformation",
        history_type_control: "Steuerung",
        history_type_settings: "Einstellungen",
        history_type_other: "Sonstige",
        led_no_history: "Noch keine LED-Aktionen gespeichert",
        channel: "Kanal",
        schedule: "Zeitplan",
        scheduler: "Scheduler",
        amount: "Menge",
        weekdays: "Wochentage",
        actions: "Aktionen",
        everyday: "täglich",
        every_day: "Jeden Tag",
        reset: "Zurücksetzen",
        reset_schedule: "Zeitplan zurücksetzen",
        reset_schedule_question: "Soll der Zeitplan für diesen Kanal wirklich zurückgesetzt werden?",
        reset_schedule_effect: "Dabei wird der Scheduler für diesen Kanal am Gerät deaktiviert und lokal gelöscht. Der Sendestatus wird in der Datenbank gespeichert.",
        led_reset_schedule_question: "Soll der LED-Zeitplan wirklich gelöscht und an das Gerät gesendet werden?",
        led_reset_schedule_effect: "Der aktuelle LED-Zeitplan wird am Gerät zurückgesetzt. Diese Aktion kann nicht automatisch rückgängig gemacht werden.",
        led_reset_device_question: "Alle Zeitpläne nur am Gerät löschen?",
        led_reset_device_effect: "Die lokal gespeicherten Zeitpläne bleiben unverändert.",
        reset_schedule_yes: "Ja, zurücksetzen",
        reset_schedule_no: "Nein, behalten",
        connection: "Verbindung",
        device: "Gerät",
        model: "Modell",
        source: "Quelle",
        ble_on_action: "bei Aktion",
        presets: "Voreinstellungen",
        fan_control: "Lüftersteuerung",
        fan_speed: "Lüfterdrehzahl",
        fan_percentage: "Lüfterleistung",
        temperature: "Temperatur",
        online: "Online",
        offline: "Offline",
        schedule_edit: "Zeitplan bearbeiten",
        debug_output: "Debug Ausgabe",
        result_output: "Rückmeldung",
        debug_capture: "Debug-Ausgabe anzeigen",
        debug_output_short: "Debug ausgeben",
        dashboard_debug: "Dashboard-Debug für Einzelaktionen",
        dashboard_debug_hint: "Zeigt bei einzelnen Geräteaktionen ein Debug-Fenster mit HA-Aufruf, Payload und Protokolldaten.",
        debug_sending: "Sende Zeitplan an das Gerät...",
        debug_empty: "Keine Debug-Ausgabe zurückgegeben.",
        led_schedule_time_invalid: "Ungültiges Zeitfenster",
        led_schedule_time_conflict: "Zeitfenster überschneidet vorhandenen Eintrag",
        led_schedule_time_conflict_detail: "Bitte Zeiten so ändern, dass sich keine Bereiche überlappen.",
      },
      en: {
        unknown: "Unknown",
        press: "Press",
        start: "Start",
        change: "Change",
        add: "Add",
        show: "Show",
        edit: "Edit",
        details: "Details",
        close: "Close",
        cancel: "Cancel",
        apply: "Apply",
        save: "Save",
        save_send: "Save and send",
        delete: "Delete",
        delete_send: "Delete and send",
        delete_all: "Delete all schedules on device",
        enable_auto_mode: "Enable auto mode",
        new: "New",
        on: "on",
        off: "off",
        auto_mode: "Auto Mode",
        control: "Control",
        send_to_device: "Send to device",
        until: "to",
        template: "Template",
        template_name_prompt: "Template name",
        template_saved: "Template saved",
        template_deleted: "Template deleted",
        template_delete_blocked: "Only local templates can be deleted in the dialog.",
        template_not_found: "Template not found",
        template_live_preview: "Live preview",
        template_live_preview_hint: "Send changes directly to the device",
        template_live_preview_sent: "Live preview sent",
        template_live_preview_failed: "Live preview failed",
        template_list: "Template list",
        template_count: "templates",
        schedule_count: "schedules",
        template_source: "Template source",
        template_standard: "Standard",
        template_local: "Local",
        share: "Share",
        share_template: "Share template",
        target_device: "Target device",
        template_shared: "Template shared",
        no_compatible_led: "No other LED with the same number of channels was found.",
        share_schedule: "Share schedule",
        schedule_shared: "Schedule shared",
        send_to_device_now: "Send directly to device",
        start_time: "Start time",
        end_time: "End time",
        switch_on: "Turn on",
        switch_off: "Turn off",
        hours: "Hours",
        minutes: "Minutes",
        all: "All",
        run_weekdays: "Run on days",
        sunrise_sunset: "Sunrise / sunset",
        ramp_templates: "Ramp presets",
        minutes_0: "0 minutes",
        minutes_30: "30 minutes",
        hour_1_short: "1 h",
        hour_1: "1 hour",
        hour_1_5_short: "1.5 h",
        hour_1_5: "1 hour 30 minutes",
        hour_2_short: "2 h",
        hour_2: "2 hours",
        hour_2_5_short: "2.5 h",
        hour_2_5: "2 hours 30 minutes",
        red: "Red",
        green: "Green",
        blue: "Blue",
        white: "White",
        color_channels: "Color channels",
        total: "Total",
        complete_lamp: "Complete lamp",
        complete_lamp_toggle: "Turn complete lamp on / off",
        complete_lamp_on: "Turn complete lamp on",
        complete_lamp_off: "Turn complete lamp off",
        led_scheduler: "LED Scheduler",
        led_schedule_summary_subtitle: "Summary of active time windows",
        led_schedule_save_send: "Save and send LED schedule",
        led_schedule_save_local: "Save LED schedule",
        led_schedule_saved: "Schedule saved",
        led_schedule_sent_action: "Schedule sent to device",
        led_schedule_sent: "sent to device",
        led_schedule_not_sent: "saved locally, not sent",
        led_schedule_rows: "schedule rows",
        schedule_sent: "Schedule sent",
        schedules_sent: "Schedules sent",
        schedule_deleted: "Schedule deleted",
        schedules_deleted: "Schedules deleted",
        schedule_local_deleted: "Schedule deleted locally",
        schedules_device_deleted_local_kept: "All schedules deleted from device; local data unchanged",
        led_set: "LED set",
        all_days: "Every day",
        channels: "Channels",
        brightness_changed: "Brightness changed",
        channel_switched_off: "Channel switched off",
        sending: "Sending...",
        saving: "Saving...",
        local_save_failed: "Saving locally failed",
        send_failed: "Sending failed",
        service_unavailable: "Service unavailable",
        led_set_failed: "LED could not be set",
        notification_fetch: "Fetch device notifications",
        notification_fetch_none: "No device notification received",
        notification_fetch_received: "device notifications received",
        notification_fetch_unauthorized: "BLE access rejected. Disconnect other Bluetooth connections to the device.",
        no_led_channels: "No Chihiros LED channels found",
        reply: "Response",
        reply_sent: "sent to device",
        reply_local: "saved locally only",
        running: "RUNNING",
        last_notification: "Last notification",
        fetched_at: "Fetched at",
        notification_type: "Notification type",
        raw_frame: "Raw frame",
        decode: "Decode",
        encode_hex: "Encode / Hex",
        parameters: "Parameters",
        message_id: "Message ID",
        checksum: "Checksum",
        direction: "Direction",
        command: "Command",
        length: "Length",
        meaning: "Meaning",
        verified: "Verified",
        schedule_verification: "Schedule verified",
        schedule_verification_ok: "Device schedule matches",
        schedule_verification_failed: "Device schedule differs",
        check_short: "OK",
        mismatch: "Mismatch",
        not_checked: "Not checked",
        schedule_count: "Schedules",
        firmware: "Firmware",
        runtime: "Runtime",
        runtime_day: "day",
        runtime_days: "days",
        runtime_hour_short: "hr",
        runtime_minute_short: "min",
        schedule_sensor: "Schedule sensor",
        no_schedule_read: "No schedule read",
        led_manual_schedule_warning: "Manual control is active. Enable automatic mode again before automatic schedules can run.",
        max_value: "Max",
        max_range: "Range",
        current_plan: "Current plan",
        device: "Device",
        device_name: "Device name",
        change_device_name: "Change device name",
        led: "LED",
        config: "Config",
        display: "Display",
        language_label: "Language",
        language_de: "German",
        language_en: "English",
        show_mac: "Show MAC address",
        channel_names: "Channel names",
        database: "Database",
        database_subtitle: "Schedules, templates, transfer status and diagnostics",
        integration_database: "LED Core storage",
        plugin_install: "Install plugin",
        installed_plugins: "Installed plugins",
        no_external_plugins: "No external plugins installed.",
        version: "Version",
        remove: "Remove",
        plugin_install_hint: "Upload a trusted TGZ. The plugin is loaded only after restarting the LED Core add-on.",
        plugin_archive: "TGZ file",
        plugin_select_first: "Select a TGZ file first.",
        plugin_installing: "Validating and installing plugin …",
        plugin_installed: "Plugin installed",
        plugin_install_failed: "Plugin installation failed",
        plugin_uninstall_confirm: "Remove plugin {plugin}? It will be moved to a dated backup.",
        plugin_uninstalling: "Safely removing plugin …",
        plugin_uninstalled: "Plugin removed",
        plugin_uninstall_failed: "Plugin could not be removed",
        restart_addon: "Restart the LED Core add-on.",
        install: "Install",
        rated_power: "Rated power",
        estimated_power: "Estimated consumption; not a measured value",
        rated_power_hint: "Optional power for controllers or models whose size cannot be detected. It takes precedence over automatic detection.",
        automatic: "automatic",
        recorder_storage_hint: "Entity states, history and statistics remain in the Home Assistant Recorder.",
        own_database: "Own DB",
        active_sqlite: "Active SQLite",
        database_diagnostics: "DB diagnostics",
        database_diagnostics_hint: "Show stored LED schedules and pending verification jobs",
        diagnostic_retention: "Diagnostic retention (days)",
        diagnostic_retention_hint: "0 = unlimited; only periodic BLE diagnostic messages are affected.",
        database_status: "Scheduler database status",
        database_open: "Open",
        database_closed: "Not open",
        database_stored_schedules: "Stored schedules",
        database_verification_jobs: "Pending schedule verifications",
        database_request: "Request",
        database_no_rows: "No result for this device.",
        database_result: "Result",
        loading: "Loading...",
        inactive: "Inactive",
        failed: "Failed",
        database_column_position: "No.",
        database_column_time_window: "Time",
        database_column_levels: "Channels",
        database_column_ramp_minutes: "Ramp",
        database_column_active: "Active",
        database_column_verification: "Verification",
        database_column_verified_at: "Verified at",
        database_column_target: "Target schedule",
        database_column_restore_rows: "Restore rows",
        database_column_due_at: "Due",
        database_column_created_at: "Created",
        database_file: "File",
        database_size: "Size",
        database_rows: "Rows",
        database_parameters: "Parameters",
        error: "Error",
        reload: "Reload",
        update: "Update",
        updating: "Updating …",
        command_copied: "Command copied",
        copy: "Copy",
        copy_all: "Copy all",
        copied: "Copied",
        copy_failed: "Copy failed",
        no_entities: "No matching Home Assistant entities found.",
        status: "Status",
        active: "Active",
        today: "Today",
        time: "Time",
        planned_amount: "Planned amount",
        history: "History",
        history_total: "Full history",
        history_filter: "Filter",
        history_type: "Type",
        history_type_scheduler: "Scheduler",
        history_type_device: "Device information",
        history_type_control: "Control",
        history_type_settings: "Settings",
        history_type_other: "Other",
        led_no_history: "No LED actions saved yet",
        channel: "Channel",
        schedule: "Schedule",
        scheduler: "Scheduler",
        amount: "Amount",
        weekdays: "Weekdays",
        actions: "Actions",
        everyday: "daily",
        every_day: "Every day",
        reset: "Reset",
        reset_schedule: "Reset schedule",
        reset_schedule_question: "Do you really want to reset the schedule for this channel?",
        reset_schedule_effect: "This disables the scheduler for this channel on the device and removes it locally. The send status is stored in the database.",
        led_reset_schedule_question: "Do you really want to delete the LED schedule and send the reset to the device?",
        led_reset_schedule_effect: "The current LED schedule will be reset on the device. This action cannot be automatically undone.",
        led_reset_device_question: "Delete all schedules from the device only?",
        led_reset_device_effect: "Locally stored schedules remain unchanged.",
        reset_schedule_yes: "Yes, reset",
        reset_schedule_no: "No, keep it",
        connection: "Connection",
        device: "Device",
        model: "Model",
        source: "Source",
        ble_on_action: "on action",
        presets: "Presets",
        fan_control: "Fan control",
        fan_speed: "Fan speed",
        fan_percentage: "Fan output",
        temperature: "Temperature",
        online: "Online",
        offline: "Offline",
        schedule_edit: "Edit schedule",
        debug_output: "Debug output",
        result_output: "Response",
        debug_capture: "Show debug output",
        debug_output_short: "Output debug",
        dashboard_debug: "Dashboard debug for single actions",
        dashboard_debug_hint: "Shows a debug window with the HA action, payload, and protocol data for individual device actions.",
        debug_sending: "Sending schedule to device...",
        debug_empty: "No debug output returned.",
        led_schedule_time_invalid: "Invalid time window",
        led_schedule_time_conflict: "Time window overlaps an existing entry",
        led_schedule_time_conflict_detail: "Please change the times so no ranges overlap.",
      },
    };
    const lang = this.language();
    return (dict[lang] && dict[lang][key]) || dict.de[key] || key;
  }

  uiSettingsKey() {
    return `chihiros-led-core-card:${String(this.deviceAddress || "default").toLowerCase()}:ui`;
  }

  dialog() {
    if (this.dialogState?.type === "debug") return this.sharedDebugDialog({
      title: this.dialogState.title || (this.dialogState.debug ? this.tr("debug_output") : this.tr("result_output")),
      output: this.dialogState.output || "",
      debug: Boolean(this.dialogState.debug),
      running: Boolean(this.dialogState.running),
      level: this.dialogState.level || "",
    });
    if (this.dialogState?.type === "confirm") return this.sharedModalDialog({
      title: this.dialogState.title || this.tr("reset_schedule"),
      sectionClass: "modal card debug-modal",
      bodyHtml: `<div class="debug-output">${this.escapeHtml([this.dialogState.message || "", this.dialogState.detail || ""].filter(Boolean).join("\n\n"))}</div>`,
      actions: [
        { action: "confirm-dialog-no", label: this.dialogState.cancelLabel || this.tr("reset_schedule_no"), className: "link", type: "button" },
        { action: "confirm-dialog-yes", label: this.dialogState.confirmLabel || this.tr("reset_schedule_yes"), className: "primary", type: "button" },
      ],
    });
    if (this.ledScheduleEditorOpen) return this.ledScheduleDialog();
    const type = String(this.dialogState?.type || "");
    if (type === "led-history-all") return this.ledHistoryAllDialog();
    if (type === "led-history") return this.ledChannelHistoryDialog();
    if (type === "led-notification") return this.ledNotificationDialog();
    if (type === "led-database-status") return this.databaseStatusDialog();
    if (type === "led-template-editor") return this.ledTemplateDialog();
    if (type === "led-template-share") return this.ledTemplateShareDialog();
    if (type === "led-schedule-share") return this.ledScheduleShareDialog();
    if (type === "led-auto-mode-editor") return this.ledAutoModeDialog();
    if (type === "led-device-power-editor") return this.ledDevicePowerDialog();
    if (type === "led-device-name-editor") return this.ledDeviceNameDialog();
    return "";
  }

  bindLedEvents() {
    this.querySelectorAll("[data-led-device]").forEach((el) => {
      el.addEventListener("click", () => this.setLedDevice(el.getAttribute("data-led-device")));
    });
    this.querySelectorAll("[data-led-schedule-edit]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopImmediatePropagation();
        const rowIndex = Number(el.getAttribute("data-led-schedule-edit"));
        this.openLedScheduleDialog(Number.isInteger(rowIndex) ? rowIndex : null);
      });
    });
    this.querySelectorAll("[data-led-schedule-new]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopImmediatePropagation();
        this.openNewLedScheduleDialog();
      });
    });
    this.querySelectorAll("[data-led-number]").forEach((el) => {
      const syncLedChannelControls = () => {
        const rawValue = String(el.value ?? "").trim();
        if (!rawValue || !Number.isFinite(Number(rawValue))) return null;
        const max = typeof this.ledMaxBrightness === "function" ? this.ledMaxBrightness() : 100;
        const value = Math.max(0, Math.min(max, Math.round(Number(rawValue))));
        el.value = String(value);
        const channel = Number(el.getAttribute("data-led-device-channel"));
        this.querySelectorAll(`[data-led-device-channel="${channel}"][data-led-number]`).forEach((peer) => {
          if (peer !== el) peer.value = String(value);
          if (el.type === "range" && peer.type === "number") delete peer.dataset.ledDirty;
        });
        return value;
      };
      const save = () => {
        if (el.type === "number" && el.dataset.ledDirty !== "1") return;
        const inputValue = syncLedChannelControls();
        if (inputValue === null) return;
        const entity = el.getAttribute("data-led-number");
        const channel = Number(el.getAttribute("data-led-device-channel"));
        let value = inputValue;
        const pendingKey = `${entity || "local"}:${channel}`;
        const pending = this._ledChannelInputValues && this._ledChannelInputValues[pendingKey];
        if (pending && Number.isFinite(Number(pending.value)) && Date.now() - Number(pending.at || 0) < 2500) {
          value = Number(pending.value);
        }
        const max = typeof this.ledMaxBrightness === "function" ? this.ledMaxBrightness() : 100;
        value = Math.max(0, Math.min(max, Math.round(value)));
        delete el.dataset.ledDirty;
        if (entity) {
          this._ledChannelSaveTimers = this._ledChannelSaveTimers || {};
          const key = `${entity}:${channel}`;
          if (this._ledChannelSaveTimers[key]) window.clearTimeout(this._ledChannelSaveTimers[key]);
          this._ledChannelSaveTimers[key] = window.setTimeout(() => {
            delete this._ledChannelSaveTimers[key];
            if (entity.startsWith("light.")) this.setLedBrightness(entity, value);
            else this.setNumber(entity, value);
          }, 120);
          return;
        }
        const ledChannel = (this.ledChannels || []).find((item) => item.id === channel);
        if (ledChannel) ledChannel.value = value;
        this.render();
      };
      el.addEventListener("change", save);
      el.addEventListener("keydown", (ev) => {
        if (el.type === "number" && ev.key === "Enter") {
          el.dataset.ledDirty = "1";
          save();
        }
      });
      el.addEventListener("input", () => {
        if (el.type === "number") el.dataset.ledDirty = "1";
        const value = syncLedChannelControls();
        if (value === null) return;
        const channel = Number(el.getAttribute("data-led-device-channel"));
        const entity = el.getAttribute("data-led-number");
        this._ledChannelInputValues = this._ledChannelInputValues || {};
        this._ledChannelInputValues[`${entity || "local"}:${channel}`] = { value, at: Date.now() };
        const ledChannel = (this.ledChannels || []).find((item) => item.id === channel);
        if (ledChannel) ledChannel.value = value;
        if (typeof this.updateLedWattDisplays === "function") this.updateLedWattDisplays();
      });
    });
    this.querySelectorAll("[data-led-fan-control]").forEach((el) => {
      const syncFanControls = () => {
        const value = Math.max(0, Math.min(100, Math.round(Number(el.value) || 0)));
        this.querySelectorAll("[data-led-fan-control]").forEach((peer) => {
          peer.value = String(value);
        });
        return value;
      };
      el.addEventListener("input", syncFanControls);
      el.addEventListener("change", () => this.setLedFanPercentage(syncFanControls()));
      el.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") this.setLedFanPercentage(syncFanControls());
      });
    });
    this.querySelectorAll("[data-led-channel-action]").forEach((el) => {
      el.addEventListener("click", async () => {
        const channelId = Number(el.getAttribute("data-led-device-channel"));
        const mode = String(el.getAttribute("data-led-channel-action") || "").trim().toLowerCase();
        const channel = (this.ledChannels || []).find((item) => Number(item.id) === channelId);
        if (!channel || (mode !== "on" && mode !== "off")) return;
        const saveTimerKey = `${channel.entity || "local"}:${channelId}`;
        if (this._ledChannelSaveTimers && this._ledChannelSaveTimers[saveTimerKey]) {
          window.clearTimeout(this._ledChannelSaveTimers[saveTimerKey]);
          delete this._ledChannelSaveTimers[saveTimerKey];
        }
        if (this._ledChannelInputValues) delete this._ledChannelInputValues[saveTimerKey];
        const max = typeof this.ledMaxBrightness === "function" ? this.ledMaxBrightness() : 100;
        const current = typeof this.ledChannelValue === "function" ? this.ledChannelValue(channel) : Number(channel.value || 0);
        this._ledChannelLastOnValues = this._ledChannelLastOnValues || {};
        if (mode === "on") {
          const restore = Number(this._ledChannelLastOnValues[channelId] || channel.value || max);
          const value = Number.isFinite(restore) && restore > 0 ? restore : max;
          if (channel.entity) {
            const ok = await this.setLedBrightness(channel.entity, value, false, {
              action: "LED Kanal AN",
              sourceId: `channel-switch-on-ch${channelId}`,
              params: { source_id: `channel-switch-on-ch${channelId}`, source_type: "channel_switch", mode: "on", channel_id: channelId },
            });
            if (ok) {
              this.setLedManualScheduleWarning(true);
              this.render();
            }
          }
          else {
            channel.value = value;
            this.render();
          }
          return;
        }
        if (current > 0) this._ledChannelLastOnValues[channelId] = current;
        if (channel.entity) {
          const ok = await this.setLedBrightness(channel.entity, 0, false, {
            action: "LED Kanal AUS",
            sourceId: `channel-switch-off-ch${channelId}`,
            params: { source_id: `channel-switch-off-ch${channelId}`, source_type: "channel_switch", mode: "off", channel_id: channelId },
          });
          if (ok) {
            this.setLedManualScheduleWarning(true);
            this.render();
          }
        }
        else {
          channel.value = 0;
          this.render();
        }
      });
    });
    this.querySelectorAll("[data-number]").forEach((el) => {
      el.addEventListener("change", () => this.setNumber(el.getAttribute("data-number"), el.value));
      el.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") this.setNumber(el.getAttribute("data-number"), el.value);
      });
    });
    this.querySelectorAll("[data-led-channel-history]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopImmediatePropagation();
        const channel = Number(el.getAttribute("data-led-channel-history") || 1);
        this.openDialogState("led-history", channel, { activeTab: "led" });
        window.requestAnimationFrame(() => {
          const list = this.querySelector(".led-channel-history-list");
          if (list) list.scrollTop = 0;
        });
      });
    });
    this.querySelectorAll("[data-action]").forEach((el) => {
      el.addEventListener("click", async (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        const action = el.getAttribute("data-action") || "";
        const [kind, entity, extra] = action.split(":");
        const asyncAction = [
          "led-preset",
          "led-schedule-add",
          "led-schedule-save",
          "led-schedule-save-local",
          "led-schedule-delete-row",
          "led-enable-auto-mode",
          "led-schedule-share-save",
          "led-auto-mode-send",
          "led-device-power-send",
          "led-device-power-toggle",
          "led-database-status-open",
          "confirm-dialog-yes",
          "confirm-dialog-no",
        ].includes(kind);
        if (asyncAction) el.disabled = true;
        try {
          if (kind === "press") this.press(entity);
          if (kind === "more") this.moreInfo(entity);
          if (kind === "debug-test-led-schedule") {
            this.dialogState = {
              type: "debug",
              channel: 1,
              output: "OK\nTest Dialog\nWenn du das hier siehst, funktioniert der Klick- und Debug-Dialogpfad.",
              running: false,
              noChannel: true,
              level: "ok",
            };
            this.render();
          }
          if (kind === "led-schedule-edit") this.openLedScheduleDialog();
          if (kind === "led-schedule-new") this.openNewLedScheduleDialog();
          if (kind === "led-preset") await this.setLedPreset(entity);
          if (kind === "led-schedule-add" || kind === "led-schedule-save") await this.addLedSchedule(true);
          if (kind === "led-schedule-save-local") await this.addLedSchedule(false);
          if (kind === "led-schedule-delete-row" && typeof this.deleteLedScheduleRow === "function") await this.deleteLedScheduleRow(Number(entity), true);
          if (kind === "led-schedule-reset" && typeof this.openLedScheduleResetConfirm === "function") this.openLedScheduleResetConfirm();
          if (kind === "led-enable-auto-mode" && typeof this.enableLedAutoModeFromFront === "function") await this.enableLedAutoModeFromFront();
          if (kind === "led-template-save" && typeof this.saveLedTemplateFromDialog === "function") await this.saveLedTemplateFromDialog();
          if (kind === "led-template-share-save" && typeof this.saveSharedLedTemplate === "function") this.saveSharedLedTemplate();
          if (kind === "led-schedule-share-save" && typeof this.saveSharedLedSchedule === "function") await this.saveSharedLedSchedule();
          if (kind === "led-auto-mode-edit" && typeof this.openLedAutoModeDialog === "function") this.openLedAutoModeDialog();
          if (kind === "led-auto-mode-send" && typeof this.saveLedAutoModeDialog === "function") await this.saveLedAutoModeDialog();
          if (kind === "led-device-power-edit" && typeof this.openLedDevicePowerDialog === "function") this.openLedDevicePowerDialog();
          if (kind === "led-device-power-send" && typeof this.saveLedDevicePowerDialog === "function") await this.saveLedDevicePowerDialog();
          if (kind === "led-device-power-toggle" && typeof this.toggleLedDevicePower === "function") await this.toggleLedDevicePower();
          if (kind === "led-notification-open" && typeof this.openLedNotificationDialog === "function") this.openLedNotificationDialog();
          if (kind === "led-database-status-open" && typeof this.openDatabaseStatusDialog === "function") await this.openDatabaseStatusDialog();
          if (kind === "led-device-name-edit" && typeof this.openLedDeviceNameDialog === "function") this.openLedDeviceNameDialog();
          if (kind === "led-device-name-save" && typeof this.saveLedDeviceNameDialog === "function") this.saveLedDeviceNameDialog();
          if (kind === "dialog") {
            if (String(entity || "").startsWith("led-")) {
              this.openDialogState(entity, Number(extra), { activeTab: "led" });
            } else {
              this.openDialog(entity, Number(extra));
            }
          }
          if (kind === "confirm-dialog-yes" && typeof this.resolveConfirmDialog === "function") await this.resolveConfirmDialog(true);
          if (kind === "confirm-dialog-no" && typeof this.resolveConfirmDialog === "function") await this.resolveConfirmDialog(false);
          if (kind === "copy-debug") {
            const output = String(
              (this.dialogState && (this.dialogState.output || this.dialogState.ledScheduleMessage)) || "",
            );
            if (entity === "all") {
              await this.copyWithFeedback(el, output);
            } else {
              const index = Number(entity);
              const sections = this.debugOutputSections(output);
              const section = Number.isInteger(index) ? sections[index] : null;
              await this.copyWithFeedback(el, section ? section.value : output);
            }
          }
          if (kind === "close-dialog") this.closeDialog();
        } catch (err) {
          this.dialogState = {
            type: "debug",
            output: `FAIL\n${err && err.message ? err.message : err}`,
            level: "error",
            noChannel: true,
          };
          this.render();
        } finally {
          if (asyncAction && el.isConnected) el.disabled = false;
        }
      });
    });
    this.querySelectorAll("[data-close-dialog]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        this.closeDialog();
      });
    });
    this.querySelectorAll("[data-led-schedule-weekday-all]").forEach((el) => {
      el.addEventListener("click", () => {
        const row = el.closest("[data-led-schedule-row]");
        if (!row) return;
        const active = !(el.classList.contains("active") || el.getAttribute("aria-pressed") === "true");
        el.classList.toggle("active", active);
        el.setAttribute("aria-pressed", active ? "true" : "false");
        row.querySelectorAll("[data-led-schedule-weekday]").forEach((day) => {
          day.classList.toggle("active", active);
          day.setAttribute("aria-pressed", active ? "true" : "false");
        });
        if (typeof this.updateScheduleTimeWarning === "function") this.updateScheduleTimeWarning(row);
      });
    });
    this.querySelectorAll("[data-led-schedule-weekday]").forEach((el) => {
      el.addEventListener("click", () => {
        const row = el.closest("[data-led-schedule-row]");
        if (!row) return;
        const active = !(el.classList.contains("active") || el.getAttribute("aria-pressed") === "true");
        el.classList.toggle("active", active);
        el.setAttribute("aria-pressed", active ? "true" : "false");
        const days = Array.from(row.querySelectorAll("[data-led-schedule-weekday]"));
        const all = row.querySelector("[data-led-schedule-weekday-all]");
        const allActive = days.length > 0 && days.every((day) => day.classList.contains("active") || day.getAttribute("aria-pressed") === "true");
        if (all) {
          all.classList.toggle("active", allActive);
          all.setAttribute("aria-pressed", allActive ? "true" : "false");
        }
        if (typeof this.updateScheduleTimeWarning === "function") this.updateScheduleTimeWarning(row);
      });
    });
    this.querySelectorAll("[data-led-schedule-control]").forEach((el) => {
      const sync = () => {
        const row = el.closest("[data-led-schedule-row]");
        if (!row) return;
        const name = el.getAttribute("data-led-schedule-control");
        const kind = el.getAttribute("data-led-schedule-kind") || "";
        const value = el.value;
        if (typeof this.syncLedScheduleControl === "function") {
          this.syncLedScheduleControl(row, name, value, kind);
        }
        if (name !== "template" && typeof this.syncLedScheduleTemplate === "function") this.syncLedScheduleTemplate(row);
        if (typeof this.updateScheduleTimeWarning === "function") this.updateScheduleTimeWarning(row);
      };
      el.addEventListener("input", sync);
      el.addEventListener("change", sync);
    });
    this.querySelectorAll("[data-led-schedule-template]").forEach((el) => {
      el.addEventListener("change", () => {
        const row = el.closest("[data-led-schedule-row]");
        if (!row) return;
        if (typeof this.applyLedScheduleTemplate === "function") {
          this.applyLedScheduleTemplate(row, el.value);
        }
        if (typeof this.updateScheduleTimeWarning === "function") this.updateScheduleTimeWarning(row);
      });
    });
    this.querySelectorAll("[data-led-template-action]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        const row = el.closest("[data-led-schedule-row]");
        const action = el.getAttribute("data-led-template-action");
        if (action === "add" && typeof this.addLedScheduleTemplate === "function") this.addLedScheduleTemplate(row);
        if (action === "show" && typeof this.showLedScheduleTemplates === "function") this.showLedScheduleTemplates();
        if (action === "delete" && typeof this.deleteLedScheduleTemplate === "function") this.deleteLedScheduleTemplate(row);
      });
    });
    this.querySelectorAll("[data-led-template-edit]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (typeof this.openLedTemplateDialog === "function") this.openLedTemplateDialog(el.getAttribute("data-led-template-edit"));
      });
    });
    this.querySelectorAll("[data-led-template-source]").forEach((el) => {
      el.addEventListener("change", () => {
        this._ledTemplateSourceFilter = String(el.value || "standard") === "local" ? "local" : "standard";
        this.render();
      });
    });
    this.querySelectorAll("[data-led-template-delete]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (typeof this.deleteLedTemplateFromFront === "function") this.deleteLedTemplateFromFront(el.getAttribute("data-led-template-delete"));
      });
    });
    this.querySelectorAll("[data-led-template-share]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (typeof this.openLedTemplateShareDialog === "function") this.openLedTemplateShareDialog(el.getAttribute("data-led-template-share"));
      });
    });
    this.querySelectorAll("[data-led-schedule-delete]").forEach((el) => {
      el.addEventListener("click", async (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (typeof this.deleteLedScheduleRow === "function") await this.deleteLedScheduleRow(Number(el.getAttribute("data-led-schedule-delete")), true);
      });
    });
    this.querySelectorAll("[data-led-schedule-send]").forEach((el) => {
      el.addEventListener("click", async (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (typeof this.sendLedScheduleRowFromFront === "function") await this.sendLedScheduleRowFromFront(Number(el.getAttribute("data-led-schedule-send")));
      });
    });
    this.querySelectorAll("[data-led-schedule-share]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (typeof this.openLedScheduleShareDialog === "function") this.openLedScheduleShareDialog(Number(el.getAttribute("data-led-schedule-share")));
      });
    });
    this.querySelectorAll("[data-led-template-control]").forEach((el) => {
      const sync = () => {
        const name = el.getAttribute("data-led-template-control");
        if (name && typeof this.syncLedTemplateControl === "function") {
          this.syncLedTemplateControl(name, el.value);
        }
        if (typeof this.queueLedTemplateLivePreview === "function") this.queueLedTemplateLivePreview(false, name);
      };
      el.addEventListener("input", sync);
      el.addEventListener("change", sync);
    });
    this.querySelectorAll("[data-led-template-live-preview]").forEach((el) => {
      el.addEventListener("change", () => {
        if (typeof this.setLedTemplateLivePreviewEnabled === "function") {
          this.setLedTemplateLivePreviewEnabled(Boolean(el.checked));
        }
        if (typeof this.queueLedTemplateLivePreview === "function") this.queueLedTemplateLivePreview(true);
      });
    });
    this.querySelectorAll("[data-led-auto-mode-value]").forEach((el) => {
      el.addEventListener("click", () => {
        this.querySelectorAll("[data-led-auto-mode-value]").forEach((item) => item.classList.remove("active"));
        el.classList.add("active");
      });
    });
    this.querySelectorAll("[data-led-device-power-value]").forEach((el) => {
      el.addEventListener("click", () => {
        this.querySelectorAll("[data-led-device-power-value]").forEach((item) => item.classList.remove("active"));
        el.classList.add("active");
      });
    });
    this.querySelectorAll("[data-led-schedule-ramp]").forEach((el) => {
      el.addEventListener("click", () => {
        const row = el.closest("[data-led-schedule-row]");
        if (!row) return;
        const value = Number(el.getAttribute("data-led-schedule-ramp"));
        const hidden = row.querySelector('[data-led-schedule-control="ramp"][data-led-schedule-kind="hidden"]');
        if (hidden) hidden.value = String(value);
        if (typeof this.syncLedScheduleControl === "function") {
          this.syncLedScheduleControl(row, "ramp", value, "");
        }
        if (typeof this.updateScheduleTimeWarning === "function") this.updateScheduleTimeWarning(row);
      });
    });
    this.querySelectorAll("[data-led-time-picker]").forEach((el) => {
      el.addEventListener("click", () => {
        const field = el.closest(".led-schedule-time-field");
        if (!field) return;
        const input = field.querySelector("input[type='time']");
        const [hour = "08", minute = "00"] = String(input && input.value ? input.value : "08:00").split(":");
        const open = field.classList.contains("open");
        this.querySelectorAll(".led-schedule-time-field.open").forEach((item) => item.classList.remove("open"));
        field.dataset.pendingHour = hour;
        field.dataset.pendingMinute = minute;
        field.querySelectorAll('[data-led-time-part="hour"]').forEach((button) => {
          button.classList.toggle("active", button.getAttribute("data-led-time-value") === hour);
        });
        field.querySelectorAll('[data-led-time-part="minute"]').forEach((button) => {
          button.classList.toggle("active", button.getAttribute("data-led-time-value") === minute);
        });
        field.classList.toggle("open", !open);
      });
    });
    this.querySelectorAll("[data-led-time-part]").forEach((el) => {
      el.addEventListener("click", () => {
        const field = el.closest(".led-schedule-time-field");
        const input = field && field.querySelector("input[type='time']");
        if (!input) return;
        const part = el.getAttribute("data-led-time-part");
        const value = String(el.getAttribute("data-led-time-value") || "00").padStart(2, "0");
        if (part === "hour") field.dataset.pendingHour = value;
        if (part === "minute") field.dataset.pendingMinute = value;
        field.querySelectorAll(`[data-led-time-part="${part}"]`).forEach((button) => {
          button.classList.toggle("active", button === el);
        });
      });
    });
    this.querySelectorAll("[data-led-time-cancel]").forEach((el) => {
      el.addEventListener("click", () => {
        const field = el.closest(".led-schedule-time-field");
        if (field) field.classList.remove("open");
      });
    });
    this.querySelectorAll("[data-led-time-apply]").forEach((el) => {
      el.addEventListener("click", () => {
        const field = el.closest(".led-schedule-time-field");
        const input = field && field.querySelector("input[type='time']");
        if (!field || !input) return;
        const [currentHour = "08", currentMinute = "00"] = String(input.value || "08:00").split(":");
        const hour = String(field.dataset.pendingHour || currentHour).padStart(2, "0");
        const minute = String(field.dataset.pendingMinute || currentMinute).padStart(2, "0");
        input.value = `${hour}:${minute}`;
        field.classList.remove("open");
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
    });
    this.querySelectorAll("[data-led-schedule-active]").forEach((el) => {
      el.addEventListener("change", () => {
        const label = el.closest(".led-schedule-switch");
        const text = label && label.querySelector("span");
        if (text) text.textContent = el.checked ? "An" : "Aus";
      });
    });  }

  render() {
    if (!this._hass) return;
    this.innerHTML = `
      <style>
        :host { display:block; color: var(--primary-text-color); }
        .wrap { max-width: 1640px; margin: 0 auto; padding: 0 14px 24px; }
        .ui-icon { width:20px; height:20px; display:inline-block; flex:0 0 20px; fill:none; stroke:currentColor; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; color:#3d82b8; }
        .device-tabs { position:sticky; top:0; z-index:100; display:flex; flex-wrap:wrap; gap:8px; margin:0 -14px 18px; padding:6px 8px; border:1px solid rgba(81,154,190,.22); border-top:0; border-radius:0 0 8px 8px; background:rgba(5,14,17,.98); backdrop-filter:blur(8px); box-shadow:0 10px 24px rgba(0,0,0,.22); }
        .device-tabs button { min-height:32px; min-width:104px; border:1px solid rgba(81,154,190,.28); border-radius:7px; background:rgba(10,18,21,.88); color:var(--primary-text-color); font:inherit; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; gap:8px; padding:0 12px; }
        .device-tabs button:hover { border-color:rgba(3,201,255,.52); background:rgba(0,122,166,.12); }
        .device-tabs button.active { border-color:#03c9ff; color:#03c9ff; background:rgba(0,122,166,.18); font-weight:700; }
        .device-tabs .tab-icon { width:18px; height:18px; flex:0 0 18px; color:currentColor; fill:none; stroke:currentColor; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }
        .device-tabs button[data-tab="led"] .tab-icon { color:#ffd43b; }
        .device-tabs button[data-tab="config"] .tab-icon { color:#a78bfa; }
        .device-tabs .addon-update-button { margin-left:auto; border-color:rgba(255,147,0,.58); color:#ffc078; background:rgba(255,147,0,.10); }
        .device-tabs .addon-update-button:hover { border-color:#ff9300; background:rgba(255,147,0,.18); }
        .device-tabs .addon-update-button .tab-icon { color:#ff9300; }
        .device-tabs button.active .tab-icon { filter:drop-shadow(0 0 7px currentColor); }
        .doser-device-tabs { display:flex; flex-wrap:wrap; gap:8px; margin:-2px 0 12px; }
        .doser-device-tabs button { min-height:32px; min-width:96px; border:1px solid rgba(81,154,190,.28); border-radius:8px; background:rgba(10,18,21,.72); color:var(--primary-text-color); font:inherit; cursor:pointer; padding:0 12px; }
        .doser-device-tabs button.active { border-color:#03c9ff; color:#03c9ff; background:rgba(0,122,166,.18); font-weight:700; }
        .page-hero { grid-column:1 / -1; min-height:76px; display:grid; grid-template-columns:52px minmax(0, 1fr); align-items:center; gap:12px; margin:0 0 12px; padding:12px 14px; border:1px solid rgba(81,154,190,.24); border-radius:8px; background:linear-gradient(135deg, rgba(0,122,166,.18), rgba(14,24,27,.92)); }
        .page-hero-icon { width:44px; height:44px; display:flex; align-items:center; justify-content:center; border-radius:8px; border:1px solid rgba(3,201,255,.35); background:rgba(3,201,255,.10); }
        .page-hero-icon ha-icon { --mdc-icon-size:28px; color:#03c9ff; }
        .page-hero h1 { margin:0; font-size:21px; font-weight:700; }
        .page-hero p { margin:4px 0 0; color:rgba(255,255,255,.66); line-height:1.35; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .ha-tab-page { display:grid; grid-template-columns:1fr; gap:12px; }
        .ha-entities-card { min-height:220px; }
        .entity-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:8px 14px; }
        .led-page { display:grid; grid-template-columns:minmax(0, 1.25fr) minmax(280px, .75fr); gap:12px; align-items:start; }
        .led-connection-card { grid-column:2; grid-row:3; min-height:150px; width:100%; height:100%; align-self:stretch; display:flex; flex-direction:column; gap:3px; padding-top:11px; padding-bottom:11px; }
        .led-connection-card h2 { margin:0 0 3px; }
        .card.led-connection-card p { flex:0 0 auto; min-height:24px; align-items:center; margin:0; line-height:1.2; }
        .led-connection-card p span { text-align:right; overflow-wrap:anywhere; }
        .led-device-control-card { grid-column:1; grid-row:4; min-height:132px; }
        .led-device-presets-card { grid-column:2; grid-row:4; min-height:132px; }
        .led-device-presets-card h2 { margin:0 0 12px; }
        .led-device-head { display:grid; grid-template-columns:48px 1fr auto; align-items:start; gap:12px; margin-bottom:10px; }
        .led-device-head > ha-icon { --mdc-icon-size:38px; color:#f0f6fc; }
        .led-device-head h2 { margin-bottom:2px; }
        .led-device-head span, .led-device-head small { display:block; color:rgba(255,255,255,.66); line-height:1.35; }
        .led-device-head b { align-self:start; padding:3px 10px; border-radius:999px; background:rgba(57,211,83,.14); border:1px solid rgba(57,211,83,.35); font-size:12px; }
        .led-device-edit-box { margin:10px 0 0; padding:10px; border:1px solid rgba(81,154,190,.22); border-radius:8px; background:rgba(0,0,0,.14); }
        .led-device-control-card .led-device-edit-box { margin:0; padding:0; border:0; background:transparent; display:grid; grid-template-columns:1fr; gap:10px; align-items:center; }
        .led-device-control-card .led-device-edit-box h2 { grid-column:1; margin:0; }
        .led-device-edit-box h3 { margin:0 0 8px; color:rgba(255,255,255,.82); font-size:12px; font-weight:800; letter-spacing:.03em; text-transform:uppercase; }
        .led-device-edit-actions { display:grid; gap:7px; }
        .led-device-name-row { display:grid; grid-template-columns:minmax(120px, auto) minmax(160px, 1fr); align-items:center; gap:10px; margin:0 0 14px; }
        .led-device-name-row input { min-height:34px; border:1px solid rgba(81,154,190,.35); border-radius:6px; background:rgba(255,255,255,.08); color:var(--primary-text-color); padding:0 10px; font:inherit; }
        .led-device-name-row button { min-height:34px; }
        .led-device-control-card .led-device-edit-actions { grid-template-columns:minmax(0, 1.35fr) minmax(170px, .65fr); gap:18px; align-items:center; }
        .led-device-edit-actions .led-auto-mode-row { grid-template-columns:28px minmax(0,1fr) auto; }
        .led-device-edit-actions .led-device-power-row { grid-template-columns:28px max-content auto; justify-content:start; column-gap:10px; }
        .led-device-edit-actions .led-database-status-row { grid-template-columns:28px 266px auto; justify-content:start; column-gap:10px; }
        .led-device-power-row > span { white-space:nowrap; }
        .led-power-toggle { display:flex; align-items:center; gap:8px; min-width:76px; padding:3px 7px; border:0; background:transparent; color:var(--primary-text-color); cursor:pointer; }
        .led-power-toggle-track { position:relative; display:block; width:34px; height:18px; flex:0 0 34px; border-radius:9px; background:rgba(255,255,255,.20); border:1px solid rgba(255,255,255,.24); transition:background .16s ease,border-color .16s ease; }
        .led-power-toggle-track > span { position:absolute; top:2px; left:2px; width:12px; height:12px; border-radius:50%; background:#d8e1e5; transition:transform .16s ease,background .16s ease; }
        .led-power-toggle.active .led-power-toggle-track { background:rgba(57,211,83,.38); border-color:rgba(57,211,83,.72); }
        .led-power-toggle.active .led-power-toggle-track > span { transform:translateX(16px); background:#73ef89; }
        .led-power-toggle b { min-width:24px; color:#03c9ff; text-align:left; }
        .led-auto-mode-row .mini { border:1px solid rgba(81,154,190,.35); border-radius:6px; width:32px; height:32px; display:flex; align-items:center; justify-content:center; padding:0; background:rgba(0,0,0,.16); color:#03c9ff; cursor:pointer; }
        .led-device-edit-box .led-preset-grid { margin-top:10px; padding-top:10px; border-top:1px solid rgba(255,255,255,.08); }
        .led-device-control-card .led-info-list { padding-left:18px; border-left:1px solid rgba(255,255,255,.08); }
        .led-info-list { display:grid; gap:7px; margin:0; }
        .led-info-list b.is-unknown { color:rgba(255,255,255,.48); font-weight:600; }
        .led-device-presets-card .led-preset-grid { grid-template-columns:repeat(3, minmax(0, 1fr)); margin:0; }
        .led-device-fan-card { display:grid; gap:9px; }
        .led-device-fan-card h2 { margin:0; }
        .led-fan-metrics { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:8px; }
        .led-fan-metrics > span { min-width:0; display:grid; grid-template-columns:22px minmax(0,1fr); align-items:center; gap:2px 6px; padding:7px 8px; border:1px solid rgba(81,154,190,.26); border-radius:7px; background:rgba(0,0,0,.16); }
        .led-fan-metrics ha-icon { grid-row:1 / 3; --mdc-icon-size:20px; color:#03c9ff; }
        .led-fan-metrics b { color:rgba(255,255,255,.62); font-size:10px; text-transform:uppercase; }
        .led-fan-metrics strong { overflow:hidden; color:var(--primary-text-color); font-size:13px; text-overflow:ellipsis; white-space:nowrap; }
        .led-fan-control { display:grid; grid-template-columns:minmax(0,1fr) 64px auto; align-items:center; gap:8px; }
        .led-fan-control input[type="range"] { width:100%; min-width:0; accent-color:#03c9ff; }
        .led-fan-control input[type="number"] { width:64px; min-height:32px; box-sizing:border-box; border:1px solid rgba(3,201,255,.35); border-radius:7px; background:rgba(255,255,255,.06); color:var(--primary-text-color); padding:4px 7px; text-align:right; font:inherit; font-weight:800; }
        .led-fan-control > span { color:rgba(255,255,255,.68); font-weight:800; }
        .led-channels-card { grid-column:1 / -1; grid-row:1; min-height:220px; }
        .led-channels-title-row { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:8px 12px; margin-bottom:12px; }
        .led-channels-title-row h2 { margin:0; }
        .led-total-watt, .led-channel-watt { display:inline-flex; align-items:center; justify-content:center; gap:3px; min-height:24px; box-sizing:border-box; border:1px solid rgba(245,166,35,.28); border-radius:6px; background:rgba(0,0,0,.24); color:rgba(255,255,255,.88); font-size:11px; font-weight:750; line-height:1; white-space:nowrap; }
        .led-watt-bolt { color:#f6ad2f; filter:drop-shadow(0 0 3px rgba(246,173,47,.24)); }
        .led-total-watt { padding:4px 8px; }
        .led-channel-watt { min-width:68px; padding:3px 6px; color:rgba(255,255,255,.86); }
        .led-manual-schedule-warning { display:flex; align-items:center; gap:10px; min-height:42px; margin:0 0 12px; padding:9px 12px; border:1px solid rgba(255,76,76,.72); border-left:4px solid #ff4c4c; border-radius:6px; background:rgba(132,20,20,.28); color:#ffb4b4; }
        .led-manual-schedule-warning ha-icon { --mdc-icon-size:22px; flex:0 0 auto; color:#ff5c5c; }
        .led-manual-schedule-warning strong { line-height:1.35; }
        .led-channels { display:grid; grid-template-columns:repeat(var(--channel-columns, 4), minmax(0,1fr)); gap:12px; }
        .empty-state { min-height:120px; display:flex; align-items:center; justify-content:center; border:1px dashed rgba(81,154,190,.32); border-radius:8px; color:rgba(255,255,255,.62); background:rgba(0,0,0,.12); }
        .led-channel { min-height:154px; display:grid; gap:10px; }
        .led-channel-head { min-width:0; display:flex; align-items:center; justify-content:space-between; gap:8px; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,.09); }
        .led-channel-head h2 { min-width:0; margin:0; padding:0; border:0; font-size:16px; font-weight:700; white-space:nowrap; }
        .led-channel-head > strong { font-size:16px; text-align:right; white-space:nowrap; }
        .led-channel-head-actions { display:flex; align-items:center; gap:3px; }
        .led-channel-toggle { display:flex; align-items:center; gap:7px; min-width:66px; padding:3px 5px 3px 0; border:0; background:transparent; color:var(--primary-text-color); cursor:pointer; }
        .led-channel-toggle-track { position:relative; display:block; width:34px; height:18px; flex:0 0 34px; border:1px solid rgba(255,255,255,.24); border-radius:9px; background:rgba(255,255,255,.20); transition:background .16s ease,border-color .16s ease; }
        .led-channel-toggle-track > span { position:absolute; top:2px; left:2px; width:12px; height:12px; border-radius:50%; background:#d8e1e5; transition:transform .16s ease,background .16s ease; }
        .led-channel-toggle.active .led-channel-toggle-track { border-color:color-mix(in srgb, var(--led-color) 72%, transparent); background:color-mix(in srgb, var(--led-color) 38%, transparent); }
        .led-channel-toggle.active .led-channel-toggle-track > span { transform:translateX(16px); background:var(--led-color); }
        .led-channel-toggle b { min-width:20px; color:rgba(255,255,255,.50); font-size:11px; text-align:left; }
        .led-channel-toggle.active b { color:var(--led-color); }
        .led-channel-body { display:flex; align-items:center; justify-content:space-between; gap:8px; min-height:34px; }
        .led-channel-control { display:grid; grid-template-columns:minmax(0,1fr) 76px; gap:10px; align-items:center; }
        .led-channel input[type="range"] { width:100%; min-height:18px; padding:0; accent-color:color-mix(in srgb, var(--led-color) 68%, #111 32%); filter:drop-shadow(0 0 3px color-mix(in srgb, var(--led-color) 48%, transparent)); background:transparent; }
        .led-channel input[type="range"]::-webkit-slider-runnable-track { height:5px; border-radius:999px; background:color-mix(in srgb, var(--led-color) 68%, #111 32%); }
        .led-channel input[type="range"]::-webkit-slider-thumb { margin-top:-6px; }
        .led-channel input[type="range"]::-moz-range-track { height:5px; border-radius:999px; background:color-mix(in srgb, var(--led-color) 42%, #111 58%); }
        .led-channel input[type="range"]::-moz-range-progress { height:5px; border-radius:999px; background:color-mix(in srgb, var(--led-color) 68%, #111 32%); }
        .led-channel input[type="number"] { min-height:34px; border:1px solid color-mix(in srgb, var(--led-color) 42%, transparent); background:rgba(255,255,255,.06); color:var(--primary-text-color); border-radius:9px; padding:6px 8px; text-align:right; font-weight:800; }
        .led-channel-value-input { display:block; width:76px; box-sizing:border-box; }
        .led-channel-history-button { min-width:64px; height:30px; display:inline-flex; align-items:center; justify-content:center; gap:5px; padding:0 6px; border:1px solid rgba(81,154,190,.18); border-radius:7px; background:transparent; color:rgba(91,184,236,.72); font:inherit; font-size:10px; font-weight:700; cursor:pointer; }
        .led-channel-history-button:hover { border-color:rgba(43,155,216,.52); background:rgba(43,155,216,.09); color:#70c9f6; }
        .led-channel-history-button ha-icon { --mdc-icon-size:17px; }
        .led-actions { display:grid; grid-template-columns:repeat(3, 32px); gap:8px; justify-content:end; }
        .led-actions .mini { border:1px solid rgba(81,154,190,.35); border-radius:6px; width:32px; height:32px; display:flex; align-items:center; justify-content:center; padding:0; }
        .led-preset-grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:8px; margin-top:12px; }
        .led-device-control-box .led-preset-grid { grid-template-columns:repeat(3, minmax(0, 1fr)); }
        .led-preset-grid button { min-height:38px; border:1px solid rgba(81,154,190,.35); background:rgba(0,0,0,.16); color:var(--primary-text-color); border-radius:7px; display:flex; align-items:center; justify-content:center; gap:8px; }
        .led-middle { grid-column:1 / -1; grid-row:2; }
        .led-schedule-card { grid-column:1 / -1; }
        .led-middle .led-schedule-card { grid-column:auto; }
        .led-middle .led-history-card { grid-column:auto; }
        .led-template-card { grid-column:1; grid-row:3; min-height:150px; }
        .led-template-title-row { display:flex; align-items:center; gap:8px; }
        .led-template-count { min-width:24px; min-height:20px; display:inline-flex; align-items:center; justify-content:center; padding:0 7px; border:1px solid rgba(3,201,255,.34); border-radius:999px; background:rgba(3,201,255,.10); color:#65dfff; font-size:11px; font-weight:800; white-space:nowrap; }
        .led-schedule-title-row { display:flex; align-items:center; gap:8px; }
        .led-schedule-count { min-width:24px; min-height:20px; display:inline-flex; align-items:center; justify-content:center; padding:0 7px; border:1px solid rgba(3,201,255,.28); border-radius:999px; background:rgba(3,201,255,.08); color:#65dfff; font-size:11px; font-weight:800; white-space:nowrap; }
        .led-template-header-actions { display:flex; align-items:center; gap:8px; }
        .led-template-header-actions select { min-width:128px; min-height:34px; border:1px solid rgba(125,211,252,.36); border-radius:7px; background:rgba(0,0,0,.18); color:var(--primary-text-color); padding:0 30px 0 10px; font:inherit; }
        .led-template-front-actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
        .led-template-front-actions button { min-height:34px; border:1px solid rgba(125,211,252,.36); border-radius:8px; background:rgba(125,211,252,.08); color:#7dd3fc; font:inherit; font-weight:800; display:inline-flex; align-items:center; justify-content:center; gap:7px; padding:0 12px; cursor:pointer; }
        .led-template-front-actions button:hover { border-color:rgba(125,211,252,.72); background:rgba(125,211,252,.16); }
        .led-template-front-table { width:100%; margin-top:0; border-collapse:collapse; font-size:12px; }
        .led-template-front-table-wrap { max-width:100%; overflow-x:scroll; scrollbar-gutter:stable; scrollbar-width:auto; scrollbar-color:#03c9ff rgba(255,255,255,.12); padding-bottom:5px; }
        .led-template-front-table-wrap::-webkit-scrollbar { height:10px; }
        .led-template-front-table-wrap::-webkit-scrollbar-track { border:1px solid rgba(81,154,190,.24); border-radius:999px; background:rgba(255,255,255,.08); }
        .led-template-front-table-wrap::-webkit-scrollbar-thumb { border:2px solid rgba(9,18,21,.9); border-radius:999px; background:#03c9ff; }
        .led-template-front-table-wrap.scroll-limit-5 { max-height:228px; overflow-y:auto; margin-top:0; padding-right:4px; }
        .led-template-front-table-wrap.scroll-limit-5 .led-template-front-table { margin-top:0; }
        .led-template-front-table-wrap.scroll-limit-5 thead th { position:sticky; top:0; z-index:2; background:#132125; }
        .led-template-front-table th, .led-template-front-table td { border:1px solid rgba(255,255,255,.12); padding:7px 8px; text-align:left; vertical-align:middle; white-space:nowrap; }
        .led-template-front-table th { color:rgba(255,255,255,.74); font-weight:800; text-transform:uppercase; letter-spacing:.02em; }
        .led-template-front-table th:first-child, .led-template-front-table td:first-child { min-width:170px; }
        .led-template-front-table td:first-child { color:inherit; font-weight:inherit; }
        .led-template-front-table th:last-child, .led-template-front-table td:last-child { width:76px; text-align:right; }
        .led-template-chip { display:inline; color:var(--chip-color, #7dd3fc); font-size:inherit; font-weight:inherit; line-height:inherit; white-space:nowrap; }
        .led-template-chip.red { --chip-color:#ff8a8a; --chip-border:rgba(255,77,90,.52); --chip-bg:rgba(255,77,90,.12); }
        .led-template-chip.green { --chip-color:#70f08b; --chip-border:rgba(57,211,83,.52); --chip-bg:rgba(57,211,83,.12); }
        .led-template-chip.blue { --chip-color:#75caff; --chip-border:rgba(46,168,255,.52); --chip-bg:rgba(46,168,255,.12); }
        .led-template-chip.white { --chip-color:#f2fbff; --chip-border:rgba(238,247,255,.52); --chip-bg:rgba(238,247,255,.10); }
        .led-schedule-card table input { width:100%; min-width:54px; min-height:30px; border:1px solid rgba(81,154,190,.38); background:rgba(255,255,255,.08); color:var(--primary-text-color); border-radius:6px; padding:5px 7px; }
        .led-schedule-card td:nth-child(1) { width:40px; color:rgba(255,255,255,.65); font-weight:700; }
        .led-schedule-card td:nth-child(n+4):nth-child(-n+8) { width:76px; }
        .led-schedule-front-table { width:100%; border-collapse:collapse; font-size:12px; }
        .led-schedule-front-table th,
        .led-schedule-front-table td { border:1px solid rgba(255,255,255,.12); padding:7px 8px; text-align:left; vertical-align:middle; white-space:nowrap; }
        .led-schedule-front-table th { color:rgba(255,255,255,.74); font-weight:800; text-transform:uppercase; letter-spacing:.02em; }
        .led-schedule-front-table td:nth-child(1) { width:38px; color:#03c9ff; font-weight:800; }
        .led-schedule-front-table th:nth-child(2),
        .led-schedule-front-table td:nth-child(2) { width:34px; min-width:34px; padding-left:4px; padding-right:4px; text-align:center; }
        .led-schedule-front-table th:nth-child(3),
        .led-schedule-front-table td:nth-child(3) { min-width:100px; white-space:nowrap; }
        .led-schedule-front-actions { display:flex; justify-content:flex-end; gap:7px; }
        .led-schedule-header-actions { display:flex; align-items:center; justify-content:flex-end; gap:8px; flex-wrap:wrap; }
        .led-schedule-check-cell { text-align:center; }
        .led-schedule-check-dot { display:inline-block; width:10px; height:10px; border-radius:50%; background:#7c898f; box-shadow:0 0 7px rgba(124,137,143,.45); }
        .led-schedule-check-dot.ok { background:#209f49; box-shadow:0 0 6px rgba(32,159,73,.55); }
        .led-schedule-check-dot.fail { background:#ff4d57; box-shadow:0 0 8px rgba(255,77,87,.72); }
        .led-schedule-front-actions .mini { border:1px solid rgba(81,154,190,.35); border-radius:7px; width:32px; height:32px; display:flex; align-items:center; justify-content:center; padding:0; background:rgba(0,0,0,.16); color:var(--primary-text-color); }
        .led-schedule-front-actions .mini ha-icon { --mdc-icon-size:18px; color:#03c9ff; }
        .led-schedule-front-actions .mini.danger ha-icon { color:#ffdd70; }
        .led-schedule-front-actions .mini.send ha-icon { color:#39d353; }
        .led-schedule-modal { width:min(680px, calc(100vw - 28px)); max-width:calc(100vw - 28px); max-height:calc(100vh - 28px); padding:0; overflow:hidden; display:grid; grid-template-rows:auto minmax(0, 1fr) auto; border:1px solid rgba(3,201,255,.22); background:linear-gradient(180deg, rgba(12,20,23,.98), rgba(8,14,17,.99)); box-shadow:0 28px 80px rgba(0,0,0,.52); }
        .led-schedule-dialog-head { display:flex; align-items:flex-start; justify-content:space-between; gap:14px; padding:18px 20px 14px; border-bottom:1px solid rgba(255,255,255,.08); background:linear-gradient(180deg, rgba(3,201,255,.10), rgba(0,0,0,0)); }
        .led-schedule-dialog-head-actions { display:flex; align-items:center; justify-content:flex-end; gap:10px; }
        .led-schedule-dialog-close { width:34px; height:34px; flex:0 0 34px; display:grid; place-items:center; padding:0; border:1px solid rgba(81,154,190,.35); border-radius:7px; background:rgba(0,0,0,.18); color:var(--primary-text-color); }
        .led-schedule-dialog-close span { font-size:20px; line-height:1; }
        .led-schedule-dialog-head h2 { margin:0 0 6px; font-size:20px; }
        .led-schedule-dialog-head p { margin:0; color:rgba(255,255,255,.66); font-size:12px; line-height:1.45; }
        .led-schedule-dialog-meta { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:8px; }
        .dialog-chip { display:inline-flex; align-items:center; min-height:30px; padding:0 10px; border-radius:999px; border:1px solid rgba(3,201,255,.24); background:rgba(0,122,166,.14); color:#88ddff; font-size:12px; font-weight:700; white-space:nowrap; }
        .led-schedule-dialog-body { min-height:0; overflow:auto; display:grid; grid-template-columns:1fr; gap:12px; padding:16px 20px 14px; }
        .led-schedule-dialog-message { width:100%; min-width:0; max-width:100%; overflow:visible; box-sizing:border-box; border:1px solid rgba(255,77,79,.72); border-radius:10px; background:rgba(80,8,14,.72); color:#ffe8e8; padding:10px 12px; }
        .led-schedule-dialog-message.pending { max-height:none; overflow:visible; border-color:rgba(3,201,255,.58); background:rgba(3,42,58,.62); color:#d8f8ff; }
        .led-schedule-dialog-message.ok { border-color:rgba(57,211,83,.62); background:rgba(10,58,32,.62); color:#e7ffed; }
        .led-schedule-dialog-message.debug { border-color:rgba(3,201,255,.38); background:rgba(0,0,0,.14); color:#e7f8ff; padding:0; }
        .led-schedule-dialog-message strong { display:block; margin-bottom:6px; color:#ff9a9a; font-size:12px; letter-spacing:.06em; }
        .led-schedule-dialog-message.pending strong { color:#8eefff; }
        .led-schedule-dialog-message.ok strong { color:#8cffaa; }
        .led-schedule-dialog-message pre { max-width:100%; margin:0; white-space:pre-wrap; overflow-wrap:anywhere; word-break:break-word; font:12px/1.45 ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace; }
        .led-schedule-side-card { border:1px solid rgba(81,154,190,.18); border-radius:14px; background:rgba(0,0,0,.16); padding:14px; box-shadow:0 10px 24px rgba(0,0,0,.18); }
        .led-schedule-side-card h3 { margin:0 0 8px; font-size:13px; letter-spacing:.03em; text-transform:uppercase; color:#88ddff; }
        .led-schedule-side-card p { margin:0; color:rgba(255,255,255,.86); line-height:1.45; word-break:break-word; }
        .led-schedule-side-card small { display:block; margin-top:6px; color:rgba(255,255,255,.58); line-height:1.35; }
        .led-schedule-side-card.compact p { font-size:18px; font-weight:700; }
        .led-schedule-dialog-editor { min-width:0; }
        .led-schedule-editor { overflow:visible; }
        .led-schedule-editor.scroll-limit-5 { overflow:visible; padding-right:4px; }
        .led-schedule-card-list { display:grid; gap:12px; }
        .led-schedule-row-card { border:1px solid rgba(81,154,190,.22); border-radius:16px; background:rgba(0,0,0,.18); padding:12px; box-shadow:0 10px 28px rgba(0,0,0,.18); display:grid; gap:12px; }
        .led-schedule-row-head { display:grid; grid-template-columns:40px minmax(0,1fr) auto; gap:12px; align-items:center; padding:10px 12px; border:1px solid rgba(81,154,190,.22); border-left:4px solid #03c9ff; border-radius:12px; background:rgba(0,0,0,.14); }
        .led-schedule-row-index { display:flex; align-items:center; justify-content:center; width:32px; height:32px; border-radius:10px; background:rgba(3,201,255,.12); color:#03c9ff; font-weight:800; }
        .led-schedule-time-icon { justify-self:center; width:32px; height:32px; border-radius:10px; padding:6px; background:rgba(3,201,255,.12); color:#03c9ff; box-sizing:border-box; }
        .led-schedule-row-title { display:flex; align-items:center; justify-content:center; gap:8px; flex-wrap:wrap; color:rgba(255,255,255,.78); font-weight:700; min-width:0; }
        .led-schedule-row-title strong { font-size:15px; }
        .led-schedule-row-title span { color:rgba(255,255,255,.45); font-size:12px; }
        .led-schedule-row-title input { min-height:34px; min-width:104px; border:1px solid rgba(81,154,190,.34); background:rgba(255,255,255,.06); color:var(--primary-text-color); border-radius:8px; padding:7px 9px; }
        .led-schedule-time-action { color:rgba(255,255,255,.66) !important; font-size:11px !important; font-weight:800; text-transform:uppercase; white-space:nowrap; }
        .led-schedule-color-control.color-toggle { border-left-color:#03c9ff; grid-template-columns:minmax(84px, 120px) minmax(0,1fr); }
        .led-schedule-color-control.color-time { border-left-color:#03c9ff; grid-template-columns:minmax(84px, 120px) minmax(0,1fr); }
        .led-schedule-toggle-control { min-height:58px; }
        .led-schedule-debug-control { grid-template-columns:minmax(180px, 1fr) auto; }
        .led-schedule-debug-control > label span { white-space:nowrap; }
        .led-schedule-switch { justify-self:end; display:inline-grid; grid-auto-flow:column; grid-auto-columns:max-content; align-items:center; gap:8px; color:rgba(255,255,255,.84); font-size:12px; font-weight:700; text-transform:uppercase; white-space:nowrap; }
        .led-schedule-switch input { width:18px; height:18px; accent-color:#03c9ff; }
        .led-schedule-time-control .led-schedule-row-title { display:grid; grid-template-columns:auto minmax(0, 1fr) auto minmax(0, 1fr); align-items:center; justify-content:stretch; gap:8px; width:100%; min-width:0; }
        .led-schedule-time-field { position:relative; display:grid; grid-template-columns:minmax(0, 1fr) 34px; gap:6px; align-items:center; min-width:0; width:100%; }
        .led-schedule-time-field input { min-width:0; width:100%; }
        .led-schedule-time-picker { display:inline-flex; align-items:center; justify-content:center; width:34px; height:34px; border:1px solid rgba(81,154,190,.34); border-radius:8px; background:rgba(3,201,255,.08); color:#03c9ff; cursor:pointer; }
        .led-schedule-time-picker:hover { border-color:rgba(3,201,255,.6); background:rgba(3,201,255,.16); }
        .led-schedule-time-picker ha-icon { --mdc-icon-size:18px; }
        .led-time-picker-panel { position:absolute; z-index:12; top:calc(100% + 8px); right:0; width:244px; padding:12px; border:1px solid rgba(81,154,190,.42); border-radius:12px; background:#111b1e; box-shadow:0 18px 42px rgba(0,0,0,.46); display:none; gap:10px; }
        .led-schedule-time-field.open .led-time-picker-panel { display:grid; }
        .led-time-picker-title { color:#03c9ff; font-size:12px; font-weight:800; text-transform:uppercase; text-align:center; }
        .led-time-clock-face { display:grid; grid-template-columns:repeat(6, 1fr); gap:5px; }
        .led-time-minute-row { display:grid; grid-template-columns:repeat(6, 1fr); gap:5px; padding-top:8px; border-top:1px solid rgba(255,255,255,.08); }
        .led-time-clock-face button,
        .led-time-minute-row button { min-height:30px; border:1px solid rgba(81,154,190,.28); border-radius:999px; background:rgba(0,0,0,.18); color:rgba(255,255,255,.84); font-size:12px; font-weight:700; cursor:pointer; }
        .led-time-clock-face button:hover,
        .led-time-minute-row button:hover,
        .led-time-clock-face button.active,
        .led-time-minute-row button.active { border-color:rgba(3,201,255,.74); background:rgba(3,201,255,.2); color:#8ee6ff; }
        .led-time-picker-actions { display:flex; justify-content:flex-end; gap:8px; padding-top:8px; border-top:1px solid rgba(255,255,255,.08); }
        .led-time-picker-actions button { min-height:32px; border:1px solid rgba(81,154,190,.34); border-radius:8px; background:rgba(0,0,0,.18); color:rgba(255,255,255,.86); padding:0 10px; cursor:pointer; }
        .led-time-picker-actions button.primary { border-color:rgba(3,201,255,.64); background:rgba(3,201,255,.18); color:#8ee6ff; }
        .led-schedule-active-toggle { display:inline-flex; align-items:center; gap:7px; color:rgba(255,255,255,.82); font-size:12px; font-weight:700; text-transform:uppercase; white-space:nowrap; }
        .led-schedule-active-toggle input { accent-color:#03c9ff; }
        .led-schedule-row-inline-actions { display:flex; gap:8px; justify-content:flex-end; }
        .led-schedule-row-grid { display:grid; grid-template-columns:1fr; gap:10px; }
        .led-schedule-color-control { display:grid; grid-template-columns:minmax(84px, 120px) minmax(0,1fr) 94px; gap:10px; align-items:center; padding:10px 12px; border:1px solid rgba(81,154,190,.22); border-left-width:4px; border-left-style:solid; border-radius:12px; background:rgba(0,0,0,.14); }
        .led-schedule-row-grid > .led-schedule-color-control { grid-template-columns:minmax(68px, 82px) minmax(0,1fr) 94px; }
        .led-schedule-row-grid > .led-schedule-color-control.color-toggle,
        .led-schedule-row-grid > .led-schedule-color-control.color-time,
        .led-schedule-row-grid > .led-schedule-color-control.color-template { grid-template-columns:minmax(68px, 82px) minmax(0,1fr); }
        .led-schedule-row-grid > .led-schedule-color-control.color-template { grid-template-columns:minmax(68px, 82px) minmax(0,1fr) auto; }
        .led-schedule-color-control > label { color:rgba(255,255,255,.82); font-size:12px; font-weight:700; letter-spacing:.02em; text-transform:uppercase; padding-left:6px; }
        .led-schedule-color-control input[type="range"] { width:100%; min-height:18px; padding:0; }
        .led-schedule-color-control input[type="number"] { min-height:36px; border:1px solid rgba(81,154,190,.34); background:rgba(255,255,255,.06); color:var(--primary-text-color); border-radius:10px; padding:7px 9px; text-align:right; }
        .led-schedule-color-control.color-red { border-left-color:#ff4d4f; }
        .led-schedule-color-control.color-red input[type="range"] { accent-color:#ff4d4f; }
        .led-schedule-color-control.color-red input[type="number"] { border-color:rgba(255,77,79,.32); }
        .led-schedule-color-control.color-green { border-left-color:#39d353; }
        .led-schedule-color-control.color-green input[type="range"] { accent-color:#39d353; }
        .led-schedule-color-control.color-green input[type="number"] { border-color:rgba(57,211,83,.32); }
        .led-schedule-color-control.color-blue { border-left-color:#2ea8ff; }
        .led-schedule-color-control.color-blue input[type="range"] { accent-color:#2ea8ff; }
        .led-schedule-color-control.color-blue input[type="number"] { border-color:rgba(46,168,255,.32); }
        .led-schedule-color-control.color-white { border-left-color:#f0f6fc; }
        .led-schedule-color-control.color-white input[type="range"] { accent-color:#f0f6fc; }
        .led-schedule-color-control.color-white input[type="number"] { border-color:rgba(240,246,252,.32); }
        .led-schedule-color-control.color-template { border-left-color:#7dd3fc; grid-template-columns:minmax(84px, 120px) minmax(0,1fr); }
        .led-template-live-preview-row { display:grid; grid-template-columns:minmax(84px, 120px) minmax(0,1fr) auto; gap:10px; align-items:center; padding:10px 12px; border:1px solid rgba(125,211,252,.28); border-left:4px solid #03c9ff; border-radius:12px; background:rgba(3,201,255,.06); }
        .led-template-live-preview-row input[type="checkbox"] { width:18px; height:18px; accent-color:#03c9ff; }
        .led-template-live-preview-title { color:rgba(255,255,255,.90); font-size:12px; font-weight:800; letter-spacing:.02em; text-transform:uppercase; padding-left:6px; }
        .led-template-live-preview-text { display:grid; gap:2px; min-width:0; }
        .led-template-live-preview-text small { color:rgba(255,255,255,.64); font-size:11px; line-height:1.25; }
        .led-template-live-preview-text em { color:#7dd3fc; font-size:11px; font-style:normal; }
        .led-template-live-preview-text em[data-level="ok"] { color:#39d353; }
        .led-template-live-preview-text em[data-level="error"] { color:#ff6b6b; }
        .led-template-live-preview-text em[data-level="pending"] { color:#f6ad2f; }
        .led-template-live-preview-log { max-height:132px; overflow:auto; margin:0; padding:9px 10px; border:1px solid rgba(3,201,255,.24); border-radius:10px; background:rgba(0,0,0,.22); color:#b8f7ff; font:11px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space:pre-wrap; overflow-wrap:anywhere; }
        .led-schedule-template-control select {
          min-height:36px;
          border:1px solid rgba(125,211,252,.32);
          background:rgba(125,211,252,.08);
          color:var(--primary-text-color);
          border-radius:10px;
          padding:0 10px;
          font:inherit;
          width:100%;
        }
        .led-schedule-template-control small { color:#7dd3fc; font-size:12px; font-weight:700; white-space:nowrap; }
        .led-template-actions { grid-column:2 / -1; display:flex; gap:6px; justify-content:flex-start; flex-wrap:wrap; }
        .led-template-actions button { min-height:32px; border:1px solid rgba(125,211,252,.34); border-radius:8px; background:rgba(125,211,252,.08); color:#7dd3fc; font-size:12px; font-weight:800; cursor:pointer; padding:0 10px; }
        .led-template-actions button:hover { border-color:rgba(125,211,252,.72); background:rgba(125,211,252,.16); }
        .led-schedule-color-control.color-ramp { border-left-color:#ff8a3d; }
        .led-schedule-row-grid > .led-schedule-color-control.color-ramp { grid-template-columns:1fr; }
        .led-schedule-ramp-control {
          display:grid;
          grid-template-columns:1fr;
          gap:8px;
          min-height:78px;
          padding-top:12px;
          padding-bottom:12px;
          background:linear-gradient(180deg, rgba(255,138,61,.055), rgba(255,138,61,.025));
        }
        .led-schedule-ramp-title {
          display:flex;
          align-items:center;
          justify-content:flex-start;
          color:rgba(255,235,222,.9);
          white-space:normal;
          width:100%;
        }
        .led-schedule-ramp-title span { overflow:visible; text-overflow:clip; white-space:normal; }
        .led-schedule-ramp-presets {
          display:flex;
          flex-wrap:wrap;
          gap:6px;
          width:100%;
          justify-content:flex-start;
        }
        .led-schedule-ramp-chip {
          display:inline-flex;
          align-items:center;
          justify-content:center;
          min-height:30px;
          padding:7px 10px;
          border-radius:8px;
          border:1px solid rgba(255,138,61,.28);
          background:rgba(255,138,61,.08);
          color:#ffb071;
          font-weight:700;
          font-size:11px;
          line-height:1.1;
          white-space:nowrap;
          min-width:0;
          flex:0 0 auto;
          width:auto;
          cursor:pointer;
          transition:background .15s ease, border-color .15s ease, box-shadow .15s ease, color .15s ease;
        }
        .led-schedule-ramp-chip:hover { border-color:rgba(255,138,61,.56); background:rgba(255,138,61,.14); color:#ffd0ad; }
        .led-schedule-ramp-chip.active {
          background:linear-gradient(180deg, rgba(255,138,61,.28), rgba(255,138,61,.14));
          border-color:rgba(255,138,61,.76);
          box-shadow:0 0 0 1px rgba(255,138,61,.18) inset;
        }
        .led-schedule-row-weekdays { display:grid; gap:8px; }
        .schedule-weekdays { display:grid; gap:8px; }
        .weekday-all { display:inline-flex; align-items:center; gap:8px; font-weight:700; color:rgba(255,255,255,.78); }
        .weekday-grid { display:grid; grid-template-columns:repeat(7, minmax(0, 1fr)); gap:6px; }
        .weekday-chip { display:inline-flex; align-items:center; justify-content:center; gap:6px; min-height:32px; border:1px solid rgba(81,154,190,.34); border-radius:8px; background:rgba(0,0,0,.16); padding:4px 8px; color:rgba(255,255,255,.88); font-size:12px; font-weight:700; }
        .led-schedule-dialog-footer { display:grid; grid-template-columns:auto minmax(0, 1fr); align-items:center; gap:12px; padding:14px 20px 18px; border-top:1px solid rgba(255,255,255,.08); background:rgba(0,0,0,.18); }
        .led-schedule-dialog-footer > button.secondary.danger { justify-self:start; }
        .led-schedule-dialog-actions { display:flex; flex-wrap:nowrap; justify-content:flex-end; gap:8px; min-width:0; margin-left:auto; }
        .led-schedule-dialog-actions button { flex:0 0 auto; }
        .led-schedule-dialog-footer button { min-height:38px; border-radius:8px; padding:0 10px; white-space:nowrap; font-size:13px; }
        .led-schedule-dialog-footer button:disabled { opacity:.55; cursor:wait; }
        .led-schedule-dialog-footer .danger { border-color:rgba(255,196,0,.42); color:#ffdd70; background:rgba(255,196,0,.08); }
        .led-schedule-dialog-footer .danger:hover { border-color:rgba(255,196,0,.8); background:rgba(255,196,0,.14); }
        .led-schedule-summary-list { display:grid; gap:8px; max-width:100%; overflow-x:scroll; scrollbar-gutter:stable; scrollbar-width:auto; scrollbar-color:#03c9ff rgba(255,255,255,.12); padding-bottom:5px; }
        .led-schedule-summary-list::-webkit-scrollbar { height:10px; }
        .led-schedule-summary-list::-webkit-scrollbar-track { border:1px solid rgba(81,154,190,.24); border-radius:999px; background:rgba(255,255,255,.08); }
        .led-schedule-summary-list::-webkit-scrollbar-thumb { border:2px solid rgba(9,18,21,.9); border-radius:999px; background:#03c9ff; }
        .led-schedule-summary-list.scroll-limit-5 { max-height:292px; overflow-y:auto; padding-right:4px; }
        .schedule-summary-row { display:grid; grid-template-columns:24px 130px minmax(0,1fr) 20px; align-items:center; gap:10px; min-height:40px; width:100%; padding:0 10px; border:1px solid rgba(81,154,190,.24); border-radius:8px; background:rgba(0,0,0,.14); color:inherit; font:inherit; text-align:left; cursor:pointer; }
        .schedule-summary-row:hover { border-color:rgba(3,201,255,.45); background:rgba(0,122,166,.12); }
        .schedule-summary-index { color:#03c9ff; font-weight:700; }
        .schedule-summary-time { font-weight:700; }
        .schedule-summary-data { color:rgba(255,255,255,.75); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .schedule-summary-row ha-icon { --mdc-icon-size:18px; color:#03c9ff; justify-self:end; }
        .schedule-weekdays { display:grid; gap:8px; min-width:260px; }
        .weekday-all { display:inline-flex; align-items:center; gap:8px; font-weight:700; color:rgba(255,255,255,.74); }
        .weekday-grid { display:grid; grid-template-columns:repeat(8, minmax(0, 1fr)); gap:6px; }
        .weekday-chip {
          display:inline-flex;
          align-items:center;
          justify-content:center;
          min-height:30px;
          border:1px solid rgba(81,154,190,.34);
          border-radius:6px;
          background:rgba(0,0,0,.14);
          padding:4px 8px;
          color:rgba(255,255,255,.88);
          font-size:12px;
          font-weight:700;
          cursor:pointer;
          transition:background .15s ease, border-color .15s ease, color .15s ease, box-shadow .15s ease;
        }
        .weekday-all-chip { min-width:56px; }
        .weekday-chip:hover { border-color:rgba(3,201,255,.52); background:rgba(0,122,166,.16); }
        .weekday-chip.active,
        .weekday-chip[aria-pressed="true"] {
          border-color:rgba(3,201,255,.72);
          background:rgba(0,122,166,.24);
          color:#88ddff;
          box-shadow:0 0 0 1px rgba(3,201,255,.12) inset;
        }
        .weekday-chip span { white-space:nowrap; }
        .led-schedule-color-control.led-schedule-weekdays-control {
          display:grid;
          grid-template-columns:1fr;
          gap:8px;
          padding:10px 12px 12px;
          border:1px solid rgba(81,154,190,.22);
          border-left-width:4px;
          border-left-style:solid;
          border-left-color:#03c9ff;
          border-radius:12px;
          background:rgba(0,0,0,.14);
        }
        .led-schedule-weekdays-control .weekday-all-center {
          justify-content:flex-start;
          text-align:left;
          width:100%;
        }
        .led-schedule-weekdays-control .weekday-all-center span {
          width:100%;
          text-align:left;
        }
        .led-schedule-weekdays-control .weekday-grid {
          justify-content:center;
          grid-template-columns:repeat(auto-fit, minmax(56px, 1fr));
          width:100%;
          max-width:100%;
          justify-items:stretch;
        }
        .led-schedule-weekdays-control .weekday-chip {
          min-width:0;
          width:100%;
        }
        .led-history-card { min-height:220px; }
        .led-schedule-table { display:grid; gap:8px; }
        .led-schedule-row { display:grid; grid-template-columns:repeat(2, minmax(92px, 1.2fr)) repeat(4, minmax(72px, .8fr)) minmax(72px, .8fr); gap:8px; align-items:end; padding:0; border:0; background:transparent; }
        .led-schedule-current { margin:0; color:rgba(255,255,255,.62); font-size:12px; line-height:1.4; }
        .led-schedule-actions { display:flex; flex-wrap:nowrap; justify-content:flex-end; gap:8px; margin:12px 0 0; padding-top:12px; border-top:1px solid rgba(255,255,255,.08); }
        .led-schedule-actions button { box-sizing:border-box; min-height:40px; min-width:78px; border:1px solid rgba(81,154,190,.42); background:rgba(0,0,0,.18); color:var(--primary-text-color); border-radius:8px; display:inline-flex; align-items:center; justify-content:center; gap:6px; padding:0 8px; font:inherit; line-height:1; white-space:nowrap; }
        .led-schedule-actions button ha-icon { --mdc-icon-size:18px; flex:0 0 18px; }
        .led-schedule-actions button.danger { min-width:128px; }
        .led-schedule-actions button.primary { min-width:136px; border-color:rgba(0,188,245,.7); background:rgba(0,128,168,.48); }
        .config-page { display:grid; grid-template-columns:minmax(0, 1fr); gap:12px; align-items:start; }
        .config-card { min-height:auto; }
        .config-card-head { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:10px; }
        .config-card-head h2 { margin-bottom:2px; }
        .config-card-head small { display:block; color:rgba(255,255,255,.58); line-height:1.35; }
        .config-row { display:grid; grid-template-columns:120px minmax(0, 1fr); gap:12px; align-items:center; min-height:44px; margin:8px 0; font-weight:600; }
        .config-row.wide { grid-template-columns:120px minmax(0, 1fr); }
        .config-row select, .config-row input { min-height:36px; border:1px solid rgba(81,154,190,.35); border-radius:6px; background:rgba(255,255,255,.08); color:var(--primary-text-color); padding:0 10px; font:inherit; }
        .config-check { display:flex; align-items:center; gap:10px; min-height:40px; margin:8px 0; font-weight:600; }
        .config-check input { width:18px; height:18px; }
        .database-card { min-height:auto; }
        .db-pill { border:1px solid rgba(3,201,255,.55); border-radius:999px; color:#03c9ff; padding:3px 10px; font-size:12px; font-weight:700; white-space:nowrap; }
        .db-mode { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:8px 0 12px; }
        .db-mode label { min-height:38px; border:1px solid rgba(81,154,190,.3); border-radius:8px; display:flex; align-items:center; justify-content:center; gap:8px; cursor:pointer; background:rgba(10,18,21,.65); font-weight:700; }
        .db-mode label.active { border-color:#03c9ff; background:rgba(0,122,166,.18); color:#03c9ff; }
        .db-mode input { accent-color:#03c9ff; }
        .db-current { margin-top:10px; border-top:1px solid rgba(255,255,255,.08); padding-top:10px; display:grid; gap:6px; }
        .db-current p { display:grid; grid-template-columns:120px minmax(0,1fr); gap:10px; margin:0; font-size:12px; }
        .db-current b { color:rgba(255,255,255,.68); }
        .db-current span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color:rgba(255,255,255,.86); }
        .db-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:12px; }
        .db-actions .primary { min-height:34px; border:1px solid rgba(3,201,255,.65); border-radius:6px; background:rgba(0,122,166,.18); color:var(--primary-text-color); font:inherit; font-weight:700; cursor:pointer; padding:0 14px; }
        .entity-row { display:grid; grid-template-columns:28px minmax(0,1fr) auto; align-items:center; gap:10px; min-height:34px; width:100%; padding:0; border:0; border-bottom:1px solid rgba(255,255,255,.07); background:transparent; color:inherit; font:inherit; text-align:left; cursor:pointer; }
        .entity-row:last-child { border-bottom:0; }
        .entity-row span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .entity-row b { color:rgba(255,255,255,.9); font-weight:700; }
        .empty-note { min-height:120px; display:flex; align-items:center; color:rgba(255,255,255,.66); }
        .top { display:grid; grid-template-columns: 1fr 1fr 1fr; gap:12px; margin-bottom:12px; }
        .top-four { grid-template-columns: 1fr 1fr 1fr 1fr; }
        .top-front { grid-template-columns: 1.25fr 1fr 1fr 1fr; }
        .top-split { grid-template-columns: 1fr 1fr; }
        .channels { display:grid; grid-template-columns: repeat(var(--channel-columns, 4), minmax(0,1fr)); gap:12px; }
        .channels-1 { grid-template-columns:1fr; }
        .channels-2 { grid-template-columns:repeat(2, minmax(0,1fr)); }
        .channels-3 { grid-template-columns:repeat(3, minmax(0,1fr)); }
        .channels-4 { grid-template-columns:repeat(4, minmax(0,1fr)); }
        .middle { display:grid; grid-template-columns: 1.05fr .95fr; gap:12px; margin-top:12px; }
        .wide-middle { grid-template-columns: 1.25fr .75fr; }
        .single-middle { grid-template-columns:1fr; }
        .side-stack { display:grid; grid-template-columns:1fr; gap:10px; }
        .quick { display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:10px; }
        .card, .tile { border:1px solid rgba(81,154,190,.30); border-radius:8px; background:linear-gradient(135deg, rgba(21,32,35,.98), rgba(8,15,18,.98)); box-shadow:0 10px 30px rgba(0,0,0,.18); }
        .card { padding:12px 14px; }
        h1, h2 { margin:0; font-weight:500; letter-spacing:0; }
        h1 { font-size:20px; margin-bottom:18px; }
        h2 { font-size:18px; margin-bottom:12px; }
        .brand b { display:block; font-size:16px; margin-bottom:12px; }
        .brand span { display:block; line-height:1.45; color:rgba(255,255,255,.82); }
        .top-card { min-height: 132px; }
        .tools-card { min-height: 190px; }
        .sub-head { margin-top:12px; margin-bottom:6px; font-size:15px; font-weight:700; }
        .row, .action-row { display:grid; grid-template-columns:28px 1fr auto; align-items:center; gap:8px; min-height:30px; border:0; color:inherit; background:transparent; width:100%; text-align:left; padding:0; font:inherit; }
        ha-icon { color:#3d82b8; }
        .row strong { font-weight:500; }
        .action-row small { display:block; margin-top:2px; color:rgba(255,255,255,.58); font-size:11px; line-height:1.25; }
        .action-row .timer-range { max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .action-row b, .add, .link { color:#03c9ff; font-weight:600; }
        .toggle { width:34px; height:18px; border-radius:999px; background:#586069; position:relative; border:1px solid rgba(255,255,255,.18); }
        .toggle:after { content:''; position:absolute; width:14px; height:14px; top:1px; left:2px; border-radius:50%; background:#d0d7de; }
        .toggle.on { background:#007aa6; border-color:#03c9ff; }
        .toggle.on:after { left:17px; background:#2bd2ff; }
        .section-title { margin:16px 0 8px 16px; }
        .channels-panel { padding: 12px 12px; margin-top: 8px; }
        .channels-panel > h2 { margin: 0 0 10px 4px; }
        .channel-card { min-height: 188px; border-bottom-left-radius:8px; border-bottom-right-radius:8px; }
        .channel-card.inactive { filter:grayscale(.85); opacity:.62; }
        .channel-card.inactive h2 i { background:#77808a; box-shadow:none; }
        .channel-card.inactive .bottle i { opacity:.35; }
        .channel-card.auto-locked { filter:grayscale(.72); }
        .channel-card.auto-locked .row:first-of-type { color:rgba(255,255,255,.62); }
        .channel-card.auto-locked .row:first-of-type ha-icon { color:#9aa0a6; }
        .channel-card h2 { font-weight:700; position:relative; padding-bottom:10px; border-bottom:1px solid rgba(255,255,255,.09); }
        .channel-card h2 i { float:right; width:10px; height:10px; margin-top:7px; border-radius:50%; background:var(--dot); box-shadow:0 0 13px var(--dot); }
        .sub { margin:8px 0 4px; font-weight:700; font-size:12px; color:rgba(255,255,255,.78); }
        .bottle-wrap { display:grid; grid-template-columns:48px 1fr; gap:12px; align-items:center; margin:8px 0 8px; }
        .bottle { width:30px; height:44px; border:2px solid rgba(255,255,255,.5); border-radius:6px 6px 8px 8px; position:relative; margin-left:4px; background:rgba(0,0,0,.24); overflow:hidden; }
        .bottle:before { content:''; position:absolute; width:14px; height:7px; border:2px solid rgba(255,255,255,.5); border-bottom:0; border-radius:4px 4px 0 0; top:-8px; left:6px; }
        .bottle i { position:absolute; left:3px; right:3px; bottom:3px; height:var(--level, 68%); border-radius:4px; background:linear-gradient(180deg, color-mix(in srgb, var(--fill) 38%, white), var(--fill)); opacity:var(--fill-opacity, .72); box-shadow:0 0 6px color-mix(in srgb, var(--fill) 28%, transparent); transition:height .2s ease, opacity .2s ease; }
        .bottle-text { display:grid; grid-template-columns:1fr auto; align-items:center; gap:10px; min-width:0; }
        .bottle-text strong { font-size:16px; font-weight:600; justify-self:end; white-space:nowrap; }
        .bottle-text span { color:rgba(255,255,255,.72); font-size:12px; min-width:0; }
        .tiles { display:grid; grid-template-columns:repeat(3,1fr); gap:6px; margin-top:6px; }
        .tiles.compact-actions { grid-template-columns:repeat(3,1fr); }
        .tile { min-height:58px; color:inherit; cursor:pointer; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; font:inherit; }
        .tile ha-icon { --mdc-icon-size:28px; }
        .tile.accent ha-icon { color:#ffc400; }
        .manual-control { margin-top:8px; padding-top:8px; border-top:1px solid rgba(255,255,255,.09); display:grid; grid-template-columns:auto minmax(104px, 1fr) 38px; gap:8px; align-items:center; }
        .manual-control.blocked label { opacity:.58; filter:grayscale(.9); }
        .manual-control label { display:flex; gap:10px; align-items:center; min-width:0; }
        .manual-input { min-height:28px; display:flex; align-items:center; justify-content:flex-end; gap:7px; background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.12); border-bottom-color:rgba(255,255,255,.55); border-radius:6px 6px 2px 2px; padding:1px 8px; min-width:0; }
        .manual-input input { width:58px; height:24px; color:var(--primary-text-color); background:transparent; border:0; text-align:right; font:inherit; outline:0; }
        .manual-input input:disabled { color:rgba(255,255,255,.52); }
        .manual-input span { color:rgba(255,255,255,.72); }
        .schedule table { width:100%; border-collapse:collapse; font-size:12px; }
        .schedule th, .schedule td { border:1px solid rgba(255,255,255,.12); padding:6px 8px; text-align:left; }
        .schedule tr.inactive-row { color:rgba(255,255,255,.48); filter:grayscale(.85); }
        .schedule tr.auto-locked-row { color:rgba(255,255,255,.56); background:rgba(130,130,130,.08); filter:grayscale(.75); }
        .schedule-lock { display:inline-flex; align-items:center; gap:7px; color:rgba(255,255,255,.64); font-weight:600; }
        .schedule-lock ha-icon { --mdc-icon-size:17px; color:#9aa0a6; }
        .schedule td:nth-child(2) { white-space:nowrap; }
        .schedule-toggle { display:inline-flex; align-items:center; gap:8px; border:0; background:transparent; color:inherit; font:inherit; cursor:pointer; padding:0; }
        .schedule-toggle .toggle { flex:0 0 auto; }
        .tabs { display:grid; grid-template-columns:repeat(4,1fr); background:rgba(0,0,0,.32); border-radius:7px; overflow:hidden; margin-bottom:12px; }
        .tabs span, .tabs b { padding:7px; text-align:center; font-weight:500; }
        .tabs b { color:#03c9ff; border-bottom:2px solid #03c9ff; }
        .legend { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px; }
        .mini, .add, .link { border:0; background:transparent; cursor:pointer; font:inherit; }
        .quick .tile { min-height:88px; }
        .quick .tile ha-icon { --mdc-icon-size:48px; color:#4c84b4; }
        .manual-panel, .auto-panel { min-height: 0; }
        .mini.edit { padding:0; width:24px; height:24px; display:inline-flex; align-items:center; justify-content:center; }
        .mini.edit ha-icon, .mini.edit .ui-icon { --mdc-icon-size:20px; width:20px; height:20px; }
        .value-row { display:grid; grid-template-columns:12px 28px 1fr auto; align-items:center; gap:8px; min-height:30px; border-bottom:1px solid rgba(255,255,255,.07); cursor:pointer; }
        .value-row:last-child { border-bottom:0; }
        .value-row strong { justify-self:end; text-align:right; min-width:76px; padding-left:12px; }
        .value-row strong { font-weight:700; }
        .history-card { min-height: 130px; }
        .card-title-action { display:flex; align-items:center; justify-content:space-between; gap:10px; }
        .eye-action { width:28px; height:28px; display:inline-flex; align-items:center; justify-content:center; color:#2b8fcd; }
        .eye-action ha-icon, .eye-action .ui-icon { --mdc-icon-size:20px; width:20px; height:20px; }
        .front-history { min-height: 142px; }
        .front-history-list { max-height:270px; overflow-y:auto; padding-right:4px; }
        .led-history-timeline { position:relative; display:grid; grid-auto-rows:max-content; align-content:start; max-height:270px; overflow-y:auto; padding:2px 5px 2px 0; }
        .led-history-timeline.expanded { max-height:min(72vh, 760px); padding-top:8px; }
        .led-history-timeline-entry { position:relative; display:grid; grid-template-columns:30px minmax(0,1fr); gap:7px; min-height:46px; padding:5px 4px 5px 0; }
        .led-history-timeline-entry[data-action] { cursor:pointer; }
        .led-history-timeline-entry[data-action]:hover .led-history-timeline-copy { background:rgba(43,155,216,.05); }
        .led-history-timeline-entry:not(:last-child)::after { content:""; position:absolute; left:14px; top:34px; bottom:-4px; width:1px; background:rgba(81,154,190,.22); }
        .led-history-timeline-icon { z-index:1; width:28px; height:28px; display:grid; place-items:center; border:1px solid currentColor; border-radius:50%; background:#0d1a1e; font-size:14px; line-height:1; }
        .led-history-timeline-copy { min-width:0; display:grid; gap:1px; padding-bottom:4px; border-bottom:1px solid rgba(255,255,255,.06); }
        .led-history-timeline-copy > div { display:flex; align-items:center; gap:7px; min-width:0; }
        .led-history-timeline-copy strong { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; }
        .led-history-timeline-copy p { margin:0; color:rgba(255,255,255,.68); font-size:10px; line-height:1.3; overflow-wrap:anywhere; }
        .led-history-timeline-copy time { margin-left:auto; flex:0 0 auto; color:rgba(255,255,255,.48); font-size:10px; text-align:right; }
        .led-history-status { flex:0 0 auto; padding:1px 5px; border:1px solid rgba(57,211,83,.45); border-radius:4px; color:#73ef89; font-size:9px; font-weight:800; }
        .led-history-status.fail { border-color:rgba(255,91,99,.55); color:#ff7d84; }
        .history-empty { min-height:88px; display:flex; align-items:center; gap:10px; color:rgba(255,255,255,.68); cursor:pointer; }
        .channel-history { margin-top:7px; padding-top:7px; border-top:1px solid rgba(255,255,255,.09); cursor:pointer; }
        .channel-history-title { display:grid; grid-template-columns:24px 1fr; align-items:center; gap:10px; min-height:26px; }
        .channel-history-title ha-icon, .channel-history-title .ui-icon { color:#2b8fcd; --mdc-icon-size:20px; width:20px; height:20px; }
        .channel-history-scroll { max-height:88px; overflow-y:auto; padding-right:4px; }
        .channel-history-row { display:grid; gap:1px; min-height:28px; padding:4px 0 4px 34px; border-bottom:1px solid rgba(255,255,255,.06); }
        .channel-history-row:last-child { border-bottom:0; }
        .channel-history-row span { font-weight:600; font-size:12px; }
        .channel-history-row small { color:rgba(255,255,255,.62); font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .channel-history-empty { padding:5px 0 4px 34px; color:rgba(255,255,255,.55); font-size:12px; }
        .settings { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; }
        .settings-stack { display:grid; grid-template-columns:1fr; gap:12px; }
        .small { min-height:96px; }
        .small p { display:grid; grid-template-columns:1fr auto; margin:7px 0; }
        .settings-note, .input-hint { color:rgba(255,255,255,.58); font-size:11px; line-height:1.35; }
        .settings-note { display:block; margin:2px 0 8px; }
        .ok { color:#39d353; }
        .is-offline { color:#ff5b63; }
        .modal-backdrop { position:fixed; inset:0; z-index:1000; background:rgba(0,0,0,.58); display:flex; align-items:center; justify-content:center; padding:20px; }
        .modal { box-sizing:border-box; width:min(520px, calc(100vw - 40px)); max-width:100%; }
        .modal.led-schedule-modal { width:min(680px, calc(100vw - 28px)); max-width:calc(100vw - 28px); min-width:0; }
        .modal form { display:grid; gap:12px; }
        .modal label { display:grid; gap:6px; font-weight:600; }
        .modal [data-schedule-time-field][hidden], .modal [data-schedule-amount-field][hidden] { display:none; }
        .modal [data-schedule-ml][readonly] { color:rgba(255,255,255,.72); background:rgba(255,255,255,.04); cursor:not-allowed; }
        .modal [data-schedule-ml][readonly] { appearance:textfield; -moz-appearance:textfield; }
        .modal [data-schedule-ml][readonly]::-webkit-inner-spin-button, .modal [data-schedule-ml][readonly]::-webkit-outer-spin-button { margin:0; appearance:none; -webkit-appearance:none; }
        .input-hint-red { color:#ff4d4f; font-weight:700; line-height:1; }
        .modal .check { display:flex; flex-wrap:wrap; align-items:center; gap:8px; font-weight:500; }
        .modal .check .input-hint { flex:1 0 100%; margin-left:24px; }
        .modal input, .modal select, .modal textarea { min-height:38px; border:1px solid rgba(81,154,190,.35); border-radius:6px; background:rgba(255,255,255,.08); color:var(--primary-text-color); padding:0 10px; font:inherit; }
        .modal input[type="checkbox"] { width:16px; height:16px; min-height:0; padding:0; accent-color:#03c9ff; }
        .modal textarea { min-height:76px; padding:8px 10px; resize:vertical; line-height:1.35; }
        .modal-actions { display:flex; justify-content:flex-end; gap:10px; padding-top:6px; }
        .dialog-history { display:grid; gap:2px; margin-top:6px; }
        .dialog-history-list { margin-top:8px; padding-top:8px; border-top:1px solid rgba(255,255,255,.10); max-height:min(38vh, 360px); overflow-y:auto; padding-right:4px; }
        .history-modal { width:min(680px, calc(100vw - 40px)); max-height:calc(100vh - 40px); max-height:calc(100dvh - 40px); display:flex; flex-direction:column; overflow:hidden; }
        .history-modal > h2, .history-modal > .led-channel-history-head, .history-modal > .history-filter-bar, .history-modal > .modal-actions { flex:0 0 auto; }
        .history-filter-bar { display:flex; flex-wrap:wrap; justify-content:flex-end; align-items:center; gap:8px 14px; margin:8px 0 2px; }
        .history-status-filter { display:grid; grid-template-columns:auto minmax(140px, 210px); align-items:center; gap:8px; margin:0; font-size:13px; }
        .history-status-filter span { color:rgba(255,255,255,.72); font-weight:700; }
        .history-status-filter select { min-height:34px; margin:0; padding:5px 32px 5px 10px; }
        .history-modal > .dialog-history { flex:0 1 auto; max-height:min(28vh, 230px); overflow-y:auto; padding-right:4px; }
        .history-modal > .dialog-history-list { flex:1 1 auto; min-height:0; max-height:none; }
        .dialog-history-list .led-history-timeline.expanded { max-height:none; overflow:visible; }
        .led-history-all-modal > .led-history-timeline.expanded { flex:1 1 auto; min-height:0; max-height:none; overflow-y:auto; }
        .led-channel-history-list { display:grid; gap:8px; flex:1 1 auto; min-height:0; max-height:none; overflow-y:auto; padding-right:5px; }
        .led-channel-history-head { display:flex; align-items:center; justify-content:space-between; gap:12px; padding-bottom:12px; border-bottom:1px solid rgba(255,255,255,.10); }
        .led-channel-history-head h2 { margin:0; }
        .history-dialog-head-actions { display:flex; align-items:center; justify-content:flex-end; gap:10px; min-width:0; }
        .history-dialog-head-actions .history-filter-bar { flex-wrap:nowrap; margin:0; }
        .led-channel-history-close { width:34px; height:34px; display:grid; place-items:center; padding:0; border:1px solid rgba(81,154,190,.35); border-radius:7px; background:rgba(0,0,0,.18); color:var(--primary-text-color); cursor:pointer; }
        .led-channel-history-close span { font-size:20px; line-height:1; }
        .led-notification-open { width:30px; height:30px; display:grid; place-items:center; padding:0; border:1px solid rgba(81,154,190,.35); border-radius:6px; background:rgba(0,0,0,.18); color:#03c9ff; cursor:pointer; }
        .led-notification-open span { font-size:17px; line-height:1; }
        .led-notification-dialog { width:min(780px, calc(100vw - 40px)); height:min(680px, calc(100vh - 40px)); max-height:calc(100vh - 40px); display:flex; flex-direction:column; overflow:hidden; }
        .led-notification-dialog > .led-channel-history-head { flex:0 0 auto; }
        .led-notification-grid { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); align-content:start; gap:10px; margin-top:12px; padding-right:4px; min-height:0; overflow-y:auto; }
        .led-notification-tabs { display:grid; grid-template-columns:repeat(var(--notification-tab-count, 1), minmax(0,1fr)); grid-template-rows:auto minmax(0,1fr); gap:10px 6px; flex:1 1 auto; min-height:0; margin-top:12px; }
        .led-notification-tab-input { position:absolute; inline-size:1px; block-size:1px; opacity:0; pointer-events:none; }
        .led-notification-tab-label { grid-row:1; min-width:0; padding:9px 8px; border:1px solid rgba(81,154,190,.30); border-radius:7px; background:rgba(0,0,0,.18); color:rgba(255,255,255,.68); font-size:12px; font-weight:800; text-align:center; cursor:pointer; }
        .led-notification-tab-input:checked + .led-notification-tab-label { border-color:#03c9ff; background:rgba(3,201,255,.12); color:#7be6ff; box-shadow:inset 0 -2px 0 #03c9ff; }
        .led-notification-tab-panel { display:none; grid-column:1 / -1; grid-row:2; grid-template-columns:minmax(0,2fr) minmax(0,1fr); gap:10px; min-height:0; overflow:auto; padding-right:4px; }
        .led-notification-tab-input:checked + .led-notification-tab-label + .led-notification-tab-panel { display:grid; }
        .led-notification-block { min-width:0; padding:11px; border:1px solid rgba(81,154,190,.22); border-radius:7px; background:rgba(0,0,0,.18); }
        .led-notification-block.wide { grid-column:1 / -1; }
        .led-notification-block h3 { margin:0 0 8px; color:#69dcff; font-size:12px; text-transform:uppercase; }
        .led-notification-block pre { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; color:var(--primary-text-color); font:12px/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; }
        @media (pointer:coarse) {
          input[type="range"][data-led-number],
          input[type="range"][data-led-schedule-control],
          input[type="range"][data-led-template-control],
          input[type="range"][data-led-fan-control] { touch-action:pan-y; }
        }
        @media (max-width:700px) {
          .led-page { grid-template-columns:minmax(0,1fr); }
          .led-channels-card { grid-column:1; grid-row:1; }
          .led-middle { grid-column:1; grid-row:2; grid-template-columns:minmax(0,1fr); }
          .led-template-card { grid-column:1; grid-row:3; }
          .led-connection-card { grid-column:1; grid-row:4; }
          .led-device-control-card { grid-column:1; grid-row:5; min-width:0; }
          .led-device-presets-card { grid-column:1; grid-row:6; }
          .led-page .led-channels { grid-template-columns:minmax(0,1fr); }
          .led-device-control-card .led-device-edit-actions { grid-template-columns:minmax(0,1fr); gap:8px; }
          .led-device-edit-actions .action-row { grid-template-columns:28px minmax(0,1fr) auto; justify-content:stretch; }
          .led-device-power-row > span { white-space:normal; overflow-wrap:anywhere; }
          .led-schedule-row-grid > .led-schedule-color-control.led-schedule-time-control { grid-template-columns:minmax(0,1fr); }
          .led-schedule-time-control .led-schedule-row-title { grid-template-columns:auto minmax(0,1fr); }
          .led-schedule-row-grid > .led-schedule-color-control.led-schedule-debug-control { grid-template-columns:minmax(0,1fr) auto; }
          .led-template-live-preview-row { grid-template-columns:minmax(0,1fr) auto; }
          .led-template-live-preview-title { grid-column:1; }
          .led-template-live-preview-text { grid-column:1; }
          .led-schedule-debug-control > label span { white-space:normal; overflow-wrap:anywhere; }
          .led-schedule-weekdays-control .weekday-grid { grid-template-columns:repeat(4, minmax(0,1fr)); }
          .led-schedule-weekdays-control .weekday-chip { box-sizing:border-box; padding:4px; }
          .config-card-head { flex-direction:column; align-items:stretch; }
          .led-template-header-actions, .led-schedule-header-actions { width:100%; justify-content:flex-start; }
          .led-template-header-actions select { flex:1 1 auto; min-width:0; }
          .led-notification-tabs { grid-template-columns:repeat(2, minmax(0,1fr)); }
          .led-notification-tab-panel { grid-template-columns:1fr; }
        }
        .led-database-status-dialog { width:min(1040px, calc(100vw - 32px)); max-height:calc(100vh - 32px); overflow:hidden; }
        .database-request-list { display:grid; gap:12px; margin-top:12px; max-height:calc(100vh - 150px); overflow:auto; padding-right:3px; }
        .database-request-card { min-width:0; border:1px solid rgba(81,154,190,.24); border-radius:8px; background:rgba(0,0,0,.18); padding:12px; }
        .database-request-card > header { display:flex; align-items:center; justify-content:space-between; gap:12px; padding-bottom:9px; border-bottom:1px solid rgba(255,255,255,.08); }
        .database-request-card small { display:block; color:rgba(255,255,255,.48); font-size:10px; font-weight:800; text-transform:uppercase; }
        .database-request-card h3 { margin:2px 0 0; color:#75dfff; font-size:15px; }
        .database-request-card h4 { margin:10px 0 7px; color:rgba(255,255,255,.68); font-size:11px; text-transform:uppercase; }
        .database-request-status { padding:3px 7px; border:1px solid rgba(255,77,87,.52); border-radius:5px; background:rgba(255,77,87,.10); color:#ff8a92; font-size:10px; font-weight:900; }
        .database-request-status.ok { border-color:rgba(57,211,83,.46); background:rgba(57,211,83,.10); color:#70ed89; }
        .database-result-table-wrap { max-width:100%; overflow:auto; }
        .database-result-table { width:100%; min-width:720px; border-collapse:collapse; font-size:11px; }
        .database-result-table th, .database-result-table td { border:1px solid rgba(255,255,255,.11); padding:7px 8px; text-align:left; vertical-align:top; }
        .database-result-table th { position:sticky; top:0; background:#132125; color:rgba(255,255,255,.70); font-weight:800; text-transform:uppercase; white-space:nowrap; }
        .database-result-table td { max-width:280px; overflow-wrap:anywhere; }
        .database-empty-result, .database-status-loading, .database-status-error { margin:0; padding:16px; border:1px dashed rgba(81,154,190,.28); border-radius:7px; color:rgba(255,255,255,.62); text-align:center; }
        .database-status-error { border-color:rgba(255,77,87,.42); color:#ff9ca2; }
        .led-channel-history-entry { display:grid; grid-template-columns:10px minmax(0,1fr) auto; gap:10px; align-items:center; min-height:54px; padding:9px 11px; border:1px solid rgba(81,154,190,.18); border-radius:7px; background:rgba(255,255,255,.025); }
        .led-channel-history-dot { width:9px; height:9px; border-radius:50%; box-shadow:0 0 10px currentColor; }
        .led-channel-history-copy { min-width:0; display:grid; gap:3px; }
        .led-channel-history-copy strong { font-size:13px; font-weight:700; }
        .led-channel-history-copy time { color:rgba(255,255,255,.58); font-size:11px; }
        .led-channel-history-value { min-width:66px; padding:5px 8px; border:1px solid currentColor; border-radius:6px; background:rgba(0,0,0,.24); font-size:12px; font-weight:800; text-align:center; }
        .dialog-history-list .channel-history-row small { white-space:normal; overflow:visible; text-overflow:clip; line-height:1.35; }
        .primary { min-height:36px; border:1px solid #03c9ff; border-radius:7px; background:#007aa6; color:#fff; font:inherit; padding:0 14px; cursor:pointer; }
        .secondary { min-height:34px; border:1px solid rgba(81,154,190,.45); border-radius:7px; background:rgba(10,18,21,.88); color:var(--primary-text-color); font:inherit; padding:0 12px; cursor:pointer; display:inline-flex; align-items:center; gap:8px; justify-content:center; }
        .secondary ha-icon, .secondary .ui-icon { color:#ffc400; }
        .debug-modal { width:min(760px, calc(100vw - 40px)); }
        .debug-output { max-height:min(62vh, 620px); overflow:auto; white-space:pre-wrap; word-break:break-word; border:1px solid rgba(255,255,255,.12); border-radius:7px; background:rgba(0,0,0,.42); color:var(--primary-text-color); padding:12px; font:12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
        .debug-section-list { display:grid; gap:10px; max-height:min(66vh, 680px); overflow:auto; padding-right:4px; }
        .debug-section-box { min-width:0; border:1px solid rgba(81,154,190,.28); border-radius:7px; background:rgba(0,0,0,.22); overflow:hidden; }
        .debug-section-box header { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 10px; border-bottom:1px solid rgba(81,154,190,.20); background:rgba(3,201,255,.07); color:#7be6ff; font-size:12px; font-weight:800; text-transform:uppercase; }
        .debug-section-box header button { min-height:28px; border:1px solid rgba(81,154,190,.42); border-radius:5px; background:rgba(0,0,0,.20); color:var(--primary-text-color); font:12px/1.2 inherit; padding:0 10px; cursor:pointer; text-transform:none; }
        .debug-section-box pre { margin:0; max-height:min(34vh, 360px); overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; padding:12px; color:var(--primary-text-color); font:12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
        .debug-modal.error { border-color:rgba(255,77,79,.75); box-shadow:0 0 0 1px rgba(255,77,79,.32), 0 18px 60px rgba(0,0,0,.45); }
        .debug-modal.error h2 { color:#ff8a8a; }
        .debug-output.error { border-color:rgba(255,77,79,.78); background:rgba(75,0,0,.46); color:#ffd8d8; }
        .led-auto-mode-modal { width:min(420px, calc(100vw - 40px)); }
        .led-auto-mode-choice { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:12px 0; }
        .led-auto-mode-choice button { min-height:42px; border:1px solid rgba(81,154,190,.35); border-radius:8px; background:rgba(0,0,0,.16); color:var(--primary-text-color); font:inherit; font-weight:800; cursor:pointer; }
        .led-auto-mode-choice button.active { border-color:#03c9ff; background:rgba(0,122,166,.28); color:#88ddff; }
        .step { border:1px solid rgba(255,255,255,.10); border-radius:7px; padding:10px; background:rgba(0,0,0,.14); display:grid; gap:8px; }
        .active-step { border-color:rgba(3,201,255,.35); background:rgba(3,201,255,.06); }
        .step b { font-size:13px; }
        .step span { color:rgba(255,255,255,.72); line-height:1.35; }
        .sticky-actions { position:sticky; bottom:0; z-index:2; margin-top:12px; border-top:1px solid rgba(255,255,255,.10); background:linear-gradient(180deg, rgba(15,25,28,.96), rgba(8,15,18,.99)); padding:12px 0 2px; }
        @media (max-width: 1300px) { .top-four { grid-template-columns:1fr 1fr; } .led-channels { grid-template-columns:repeat(2, minmax(0,1fr)); } }
        @media (max-width: 1100px) { .led-schedule-side-card.compact p { font-size:16px; } .led-schedule-color-control { grid-template-columns:minmax(84px, 120px) minmax(0,1fr) 94px; } }
        @media (max-width: 1100px) { .led-schedule-ramp-presets { justify-content:flex-start; } }
        @media (max-width: 1100px) { .led-device-control-card .led-device-edit-box { grid-template-columns:1fr; } .led-device-control-card .led-device-edit-box h2 { grid-column:1; } .led-device-control-card .led-info-list { padding:10px 0 0; border-left:0; border-top:1px solid rgba(255,255,255,.08); } }
        @media (max-width: 900px) { .led-schedule-modal { width:calc(100vw - 18px); } .led-schedule-dialog-head, .led-schedule-dialog-body, .led-schedule-dialog-footer { padding-left:14px; padding-right:14px; } .led-schedule-dialog-footer { grid-template-columns:1fr; } .led-schedule-dialog-actions { width:100%; flex-wrap:wrap; justify-content:stretch; margin-left:0; } .led-schedule-dialog-actions button, .led-schedule-dialog-footer .danger { flex:1 1 auto; } }
      </style>
      <div class="wrap">
        ${this.coreTabBar()}
        ${this.activeTab === "config" ? this.configPanel() : (this.activeTab === "led" ? this.ledPanel() : this.pluginPanel(this.activeTab))}
      </div>
      ${this.dialog()}`;
    this.bindCoreEvents();
    if (this.activeTab === "led") this.bindLedEvents();
    if (!["led", "config"].includes(this.activeTab)) {
      const plugin = window.ChihirosPlugins && window.ChihirosPlugins[this.activeTab];
      if (plugin && typeof plugin.bindEvents === "function") plugin.bindEvents(this);
    }
  }
}

customElements.define("chihiros-led-core-card", ChihirosLedCoreCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "chihiros-led-core-card",
  name: "Chihiros LED Core Card",
  description: "Chihiros LED Core dashboard card",
});
