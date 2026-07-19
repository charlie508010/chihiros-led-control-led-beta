window.ChihirosPlugins = window.ChihirosPlugins || {};


class DoserPluginHelpers {
  async refreshHistory() {
    const entity = this.historyEntity();
    if (!entity) return;
    if (typeof this.refreshEntities === "function") {
      await this.refreshEntities([entity], { lockKey: "_historyRefreshRunning", renderDelay: 350 });
      return;
    }
  }

  async refreshChannelEntities(channel) {
    const e = this.entities(channel);
    const entityIds = [
      this.historyEntity(),
      e.daily,
      e.autoDaily,
      e.manualDaily,
      e.remainingSensor,
      e.scheduleTimeSensor,
      e.scheduleDoseSensor,
      e.calibrationSensor,
      e.active,
    ].filter(Boolean);
    if (typeof this.refreshEntities === "function") {
      await this.refreshEntities(entityIds, { lockKey: "_channelRefreshRunning", renderDelay: 350 });
    }
  }

  doserRefreshEntities() {
    const ids = [this.historyEntity(), this.timerStatusEntity()];
    this.channels.forEach((ch) => {
      const e = this.entities(ch.id);
      ids.push(
        e.daily,
        e.autoDaily,
        e.manualDaily,
        e.remainingSensor,
        e.scheduleTimeSensor,
        e.scheduleDoseSensor,
        e.calibrationSensor,
        e.active,
      );
    });
    return [...new Set(ids.filter(Boolean))];
  }

  async refreshDoserEntities() {
    if (typeof this.refreshEntities === "function") {
      await this.refreshEntities(this.doserRefreshEntities(), { lockKey: "_doserRefreshRunning", renderDelay: 250 });
    }
  }

  async refreshScheduleDialogState(channel) {
    const targetChannel = Number(channel) || 1;
    const prefix = this.entityPrefix();
    const backendEntries = [];
    const backendWindows = [];
    try {
      const api = window.ChihirosAddonApi;
      if (api && typeof api.callPluginBackend === "function" && this.deviceAddress) {
        const schedule = await api.callPluginBackend("doser", "read_schedule", [{
          address: this.deviceAddress,
          channel: targetChannel,
        }]);
        const rawEntries = schedule && Array.isArray(schedule.timer_entries) ? schedule.timer_entries : [];
        for (const entry of rawEntries) {
          const time = String(entry && entry.time || "");
          const ml = Number(entry && entry.ml);
          if (/^\d{2}:\d{2}$/.test(time) && Number.isFinite(ml)) backendEntries.push({ time, ml });
        }
        const rawWindows = schedule && Array.isArray(schedule.window_entries) ? schedule.window_entries : [];
        for (const entry of rawWindows) {
          const start = String(entry && entry.start || "");
          const end = String(entry && entry.end || "");
          const doses = Number(entry && entry.doses);
          if (/^\d{2}:\d{2}$/.test(start) && /^\d{2}:\d{2}$/.test(end) && Number.isInteger(doses)) {
            backendWindows.push({ start, end, doses });
          }
        }
      }
    } catch (_error) {
      // Keep the entity-state fallback for installations without the optional plugin backend.
    }
    let states = [];
    try {
      if (this._hass && typeof this._hass.callWS === "function") {
        const response = await this._hass.callWS({ type: "get_states" });
        states = Array.isArray(response) ? response : [];
      }
    } catch (_error) {
      states = [];
    }
    if (!states.length && this._hass && this._hass.states) {
      states = Object.entries(this._hass.states).map(([entityId, state]) => ({
        ...state,
        entity_id: state && state.entity_id ? state.entity_id : entityId,
      }));
    }
    const channelMarker = `_ch${targetChannel}_`;
    const candidates = states.filter((state) => {
      const entityId = String(state && state.entity_id || "").toLowerCase();
      const attributes = state && state.attributes ? state.attributes : {};
      return entityId.startsWith("sensor.")
        && entityId.startsWith(`sensor.${prefix}_`)
        && entityId.includes(channelMarker)
        && (attributes.timer_entries || attributes.window_entries);
    }).sort((left, right) => {
      const leftId = String(left && left.entity_id || "").toLowerCase();
      const rightId = String(right && right.entity_id || "").toLowerCase();
      const leftMatchesDevice = leftId.startsWith(`sensor.${prefix}_`) ? 1 : 0;
      const rightMatchesDevice = rightId.startsWith(`sensor.${prefix}_`) ? 1 : 0;
      return rightMatchesDevice - leftMatchesDevice;
    });
    const entries = [...backendEntries];
    for (const candidate of entries.length ? [] : candidates) {
      let rawEntries = candidate && candidate.attributes ? candidate.attributes.timer_entries : [];
      if (typeof rawEntries === "string") {
        try {
          rawEntries = JSON.parse(rawEntries);
        } catch (_error) {
          rawEntries = [];
        }
      }
      if (!Array.isArray(rawEntries) && rawEntries && typeof rawEntries === "object") {
        rawEntries = Object.values(rawEntries);
      }
      if (!Array.isArray(rawEntries)) continue;
      for (const entry of rawEntries) {
        const time = String(entry && entry.time || "");
        const ml = Number(entry && entry.ml);
        if (/^\d{2}:\d{2}$/.test(time) && Number.isFinite(ml)) entries.push({ time, ml });
      }
      if (entries.length) break;
    }
    this.doserScheduleDialogState = {
      channel: targetChannel,
      prefix,
      entities: candidates,
      entries,
      windows: backendWindows,
    };
  }

  addHistoryEntries(entries) {
    if (typeof this.addOverlayEntries === "function") {
      this.addOverlayEntries("historyOverlay", entries, 8);
      return;
    }
  }

  nowHistoryEntry(action, pump, detail = "") {
    if (typeof this.nowOverlayEntry === "function") {
      return this.nowOverlayEntry(action, detail, { pump });
    }
    return { action, detail, pump };
  }

  doserAddressFromPrefix(value = "") {
    const compact = String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    const hex = compact.replace(/^dy(?:dose|tdos)/, "");
    return /^[0-9a-f]{12}$/.test(hex) ? hex.match(/.{1,2}/g).join(":").toUpperCase() : "";
  }

  doserPrefixFromText(...values) {
    const text = values.map((value) => String(value || "").toLowerCase()).join(" ");
    const match = text.match(/dy(?:dose|tdos)[0-9a-f]{12}/);
    return match ? match[0] : "";
  }

  isDoserDevicePrefix(value = "") {
    return /^dy(?:dose|tdos)[0-9a-f]{12}$/i.test(String(value || "").trim());
  }

  resolveDoserDevices(defaultChannels = []) {
    const fallbackChannels = Array.isArray(defaultChannels) && defaultChannels.length ? defaultChannels : [
      { id: 1, name: "Nitrat", color: "#2ea8ff" },
      { id: 2, name: "Phosphat", color: "#39d353" },
      { id: 3, name: "Eisen", color: "#ff9300" },
      { id: 4, name: "Kalium", color: "#a855f7" },
    ];
    const configured = Array.isArray(this.config.doser_devices) ? this.config.doser_devices : [];
    const discovered = this.discoverDoserDevices(fallbackChannels);
    const normalizeChannels = (channels) => {
      const items = Array.isArray(channels) && channels.length ? channels : fallbackChannels;
      return items.map((channel, index) => ({
        id: Number(channel.id || index + 1),
        name: String(channel.name || channel.label || `CH${index + 1}`).trim() || `CH${index + 1}`,
        color: String(channel.color || fallbackChannels[index % fallbackChannels.length].color || "#2ea8ff"),
      }));
    };
    const normalizeDoserKey = (value) => {
      const compact = String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
      if (!compact) return "";
      if (compact.startsWith("dydose") || compact.startsWith("dytdos")) return compact;
      if (compact.startsWith("doser")) return "";
      return `dydose${compact}`;
    };
    const deviceKey = (device) => normalizeDoserKey(device.entity_prefix || device.address || device.mac || device.id || device.alias || "");
    const configuredByKey = new Map(configured.map((device) => [deviceKey(device), device]).filter(([key]) => key));
    const validDiscovered = discovered.filter((device) => this.isDoserDevicePrefix(device.entity_prefix || device.id || device.alias));
    const devices = validDiscovered.length
      ? validDiscovered.map((device) => {
        const configuredDevice = configuredByKey.get(deviceKey(device));
        return configuredDevice
          ? {
            ...device,
            ...configuredDevice,
            entity_prefix: device.entity_prefix || configuredDevice.entity_prefix,
            address: configuredDevice.address || configuredDevice.mac || device.address || device.entity_prefix,
            channels: device.channels,
          }
          : device;
      })
      : configured.filter((device) => this.isDoserDevicePrefix(device.entity_prefix || device.id || device.alias));
    return devices.map((device, index) => {
      const id = String(device.id || device.alias || device.address || `device_${index + 1}`);
      const entityPrefix = String(
        device.entity_prefix
        || this.doserPrefixFromText(device.id, device.alias, device.name, device.label, device.address, device.mac)
        || ""
      );
      if (!this.isDoserDevicePrefix(entityPrefix || id)) return null;
      const address = String(
        device.address
        || device.mac
        || this.doserAddressFromPrefix(entityPrefix || device.id || device.alias)
        || entityPrefix
        || device.id
        || id
      );
      return {
        id,
        alias: String(device.alias || id),
        name: `${this.tr("device")} ${index + 1}`,
        model: String(device.model || this.config.model || "Dosing Pump"),
        address,
        entity_prefix: entityPrefix,
        containerFullMl: Number(device.containerFullMl || device.container_full_ml || this.config.container_full_ml || 500),
        channels: normalizeChannels(device.channels),
      };
    }).filter(Boolean);
  }

  discoverDoserDevices(defaultChannels = []) {
    if (!this._hass || !this._hass.states) return [];
    const fallbackChannels = Array.isArray(defaultChannels) && defaultChannels.length ? defaultChannels : [
      { id: 1, name: "CH1", color: "#2ea8ff" },
      { id: 2, name: "CH2", color: "#39d353" },
      { id: 3, name: "CH3", color: "#ff9300" },
      { id: 4, name: "CH4", color: "#a855f7" },
    ];
    const groups = new Map();
    const doserEntity = /^(sensor|number|switch|button)\.(.+)$/;
    const splitDoserEntity = (objectId) => {
      const text = String(objectId || "").toLowerCase();
      const devicePrefixMatch = text.match(/^(dy(?:dose|tdos)[0-9a-f]{12})(?:_(.+))?$/);
      if (devicePrefixMatch) {
        return {
          prefix: devicePrefixMatch[1],
          suffix: devicePrefixMatch[2] || "doser",
        };
      }
      const suffixMatch = text.match(/(?:^|_)((?:ch[1-4]|pump_[1-4]|dose_pump_[1-4]|dosing_pump_[1-4])_.+)$/);
      if (suffixMatch) {
        const suffix = suffixMatch[1];
        return { prefix: text.slice(0, Math.max(0, text.length - suffix.length - 1)), suffix };
      }
      const genericMatch = text.match(/(?:^|_)((?:doser|dosing|dydose|dytdos|daily_dose|dosed_today|remaining_volume|schedule_amount|schedule_time|schedule_active).*)$/);
      if (genericMatch) {
        const suffix = genericMatch[1];
        return { prefix: text.slice(0, Math.max(0, text.length - suffix.length - 1)), suffix };
      }
      return null;
    };
    const channelFromSuffix = (suffix) => {
      const text = String(suffix || "").toLowerCase();
      const match = text.match(/(?:^|_)ch([1-4])(?:_|$)|(?:^|_)pump_([1-4])(?:_|$)|(?:^|_)dose_pump_([1-4])(?:_|$)|(?:^|_)dosing_pump_([1-4])(?:_|$)/);
      const value = match && (match[1] || match[2] || match[3] || match[4]);
      return value ? Number(value) : 0;
    };
    const isDoserSuffix = (suffix) => {
      const text = String(suffix || "").toLowerCase();
      return text.includes("doser")
        || text.includes("dydose")
        || text.includes("dytdos")
        || text.includes("dosing_pump")
        || text.includes("dose_pump")
        || text.includes("dose_volume")
        || text.includes("daily_dose")
        || text.includes("dosed_today")
        || text.includes("pump_")
        || text.includes("manual_daily_dose")
        || text.includes("auto_daily_dose")
        || text.includes("remaining_volume")
        || text.includes("schedule_amount")
        || text.includes("schedule_time")
        || text.includes("schedule_active")
        || text.includes("start_calibration")
        || text.includes("read_daily_values")
        || text.includes("reset_schedule");
    };
    Object.entries(this._hass.states).forEach(([entityId, state]) => {
      const match = String(entityId).toLowerCase().match(doserEntity);
      if (!match) return;
      const split = splitDoserEntity(match[2]);
      const channel = split ? channelFromSuffix(split.suffix) : 0;
      if (!channel) return;
      if (!this.isDoserDevicePrefix(split.prefix)) return;
      const attrs = state && state.attributes ? state.attributes : {};
      const attrText = [
        attrs.friendly_name,
        attrs.device_class,
        attrs.device_name,
        attrs.model,
        attrs.model_name,
        attrs.device_model,
      ].filter(Boolean).join(" ").toLowerCase();
      const attrLooksDoser = ["doser", "dosing", "dose", "pump", "dydose", "dytdos"].some((key) => attrText.includes(key));
      if (!split || !split.prefix || (!isDoserSuffix(split.suffix) && !attrLooksDoser)) return;
      const { prefix } = split;
      if (!groups.has(prefix)) {
        groups.set(prefix, {
          id: prefix,
          alias: prefix,
          name: `${this.tr("device")} ${groups.size + 1}`,
          model: "Dosing Pump",
          address: this.doserAddressFromPrefix(prefix),
          entity_prefix: prefix,
          channels: [],
          containerFullMl: Number(this.config.container_full_ml || 500),
        });
      }
      const group = groups.get(prefix);
      if (channel && !group.channels.some((item) => Number(item.id) === channel)) {
        const fallback = fallbackChannels[channel - 1] || fallbackChannels[0] || {};
        group.channels.push({
          id: channel,
          name: fallback.name || `CH${channel}`,
          color: fallback.color || "#2ea8ff",
        });
      }
    });
    return Array.from(groups.values()).filter((device) => device.channels.length).map((device) => ({
      ...device,
      channels: device.channels.sort((left, right) => Number(left.id) - Number(right.id)),
    }));
  }

  applyDoserDevice(deviceId, updateRender = true) {
    const devices = Array.isArray(this.doserDevices) ? this.doserDevices : [];
    const selected = devices.find((device) =>
      String(device.id) === String(deviceId)
      || String(device.alias) === String(deviceId)
      || String(device.address) === String(deviceId)
      || String(device.entity_prefix || "") === String(deviceId)
    ) || devices[0] || null;
    const fallbackChannels = [
      { id: 1, name: "Nitrat", color: "#2ea8ff" },
      { id: 2, name: "Phosphat", color: "#39d353" },
      { id: 3, name: "Eisen", color: "#ff9300" },
      { id: 4, name: "Kalium", color: "#a855f7" },
    ];
    const baseChannels = selected && Array.isArray(selected.channels) && selected.channels.length ? selected.channels : [];
    this.activeDoserDevice = selected || null;
    this.activeDoserDeviceId = selected ? String(selected.id || selected.alias || selected.address || "") : "";
    this.baseChannels = baseChannels.map((channel, index) => ({
      id: Number(channel.id || index + 1),
      name: String(channel.name || channel.label || `CH${index + 1}`),
      color: String(channel.color || fallbackChannels[index % fallbackChannels.length].color),
    }));
    this.channels = this.baseChannels.map((channel) => ({ ...channel }));
    this.deviceName = String(selected && (selected.name || selected.label) || this.config.name || "Chihiros Doser");
    this.deviceModel = String(selected && selected.model || this.config.model || "Dosing Pump");
    const entityPrefix = String(selected && selected.entity_prefix || "");
    const rawAddress = String(selected && (selected.address || selected.mac) || this.config.address || this.activeDoserDeviceId || "");
    const detectedPrefix = this.doserPrefixFromText(entityPrefix, rawAddress, selected && selected.id, selected && selected.alias, selected && selected.name);
    this.deviceAddress = this.doserAddressFromPrefix(detectedPrefix || entityPrefix || rawAddress) || (/^doser_\d+$/i.test(rawAddress) ? "" : rawAddress);
    this.containerFullMl = Number(selected && selected.containerFullMl || selected && selected.container_full_ml || this.config.container_full_ml || 500);
    if (updateRender !== false) this.render();
    return selected;
  }

  setDoserDevice(deviceId) {
    this.applyDoserDevice(deviceId, true);
  }

  doserSafetySettings() {
    const safety = this.uiSettings && this.uiSettings.doserSafety ? this.uiSettings.doserSafety : {};
    return {
      maxAutoMl: Number(safety.maxAutoMl || this.config.max_auto_ml || 50.0),
      maxManualMl: Number(safety.maxManualMl || this.config.max_manual_ml || 50.0),
      maxDailyMl: Number(safety.maxDailyMl || this.config.max_daily_ml || 250.0),
    };
  }

  saveDoserSafetySettings(maxAutoMl, maxManualMl, maxDailyMl) {
    this.uiSettings = this.uiSettings || {};
    this.uiSettings.doserSafety = {
      maxAutoMl: Number(maxAutoMl),
      maxManualMl: Number(maxManualMl),
      maxDailyMl: Number(maxDailyMl),
    };
    if (typeof this.saveUiSettings === "function") this.saveUiSettings();
  }

  doserDeviceTabs() {
    const active = String(this.activeDoserDeviceId || "");
    const devices = Array.isArray(this.doserDevices) ? this.doserDevices : [];
    if (!devices.length) return "";
    return `
      <div class="doser-device-tabs">
        ${devices.map((device) => {
          const id = String(device.id || device.alias || device.address || "");
          const label = String(device.name || device.label || id || "Device");
          return `<button type="button" data-doser-device="${this.escapeHtml(id)}" class="${id === active ? "active" : ""}">${this.escapeHtml(label)}</button>`;
        }).join("")}
      </div>`;
  }

  openDialog(type, channel = 1) {
    if (String(type || "").startsWith("led-")) {
      return typeof this.openDialogState === "function"
        ? this.openDialogState(type, channel, { activeTab: "led" })
        : (() => {
            this.activeTab = "led";
            this.dialogState = { type, channel: Number(channel) || 1 };
            this.render();
            return this.dialogState;
          })();
    }
    if (type === "reset-schedule") {
      this.openDoserScheduleResetConfirm(Number(channel) || 1);
      return null;
    }
    const state = typeof this.openDialogState === "function"
      ? this.openDialogState(type, channel)
      : (() => {
          this.dialogState = { type, channel: Number(channel) || 1 };
          this.render();
          return this.dialogState;
        })();
    if (type === "schedule") {
      this.dialogState = { ...this.dialogState, scheduleEditMode: false };
      this.render();
      this.refreshChannelEntities(Number(channel) || 1);
    }
    return state;
  }

  openDoserScheduleResetConfirm(channel = 1) {
    if (typeof this.openConfirmDialog !== "function") return;
    const targetChannel = Number(channel) || 1;
    const ch = this.channels.find((item) => item.id === targetChannel) || this.channels[0] || { id: targetChannel, name: "" };
    this.openConfirmDialog({
      channel: targetChannel,
      title: this.tr("reset_schedule"),
      message: `CH${ch.id} ${ch.name || ""}`.trim(),
      detail: `${this.tr("reset_schedule_question")}\n\n${this.tr("reset_schedule_effect")}`,
      confirmLabel: this.tr("reset_schedule_yes"),
      cancelLabel: this.tr("reset_schedule_no"),
      onConfirm: async () => {
        this.closeDialog();
        await this.runDeviceService({
          service: "reset_doser_schedule",
          data: { pump: targetChannel, send: true },
          title: this.tr("reset_schedule"),
          dialog: true,
          channel: targetChannel,
          noChannel: false,
        });
        await this.refreshHistory();
      },
      onCancel: async () => this.closeDialog(),
    });
  }

  closeDialog() {
    if (typeof this.closeDialogState === "function") {
      return this.closeDialogState();
    }
    this.dialogState = null;
    this.render();
  }

  selectedWeekdayAllows(date, weekdaysValue) {
    const values = String(weekdaysValue || "everyday").split(",").filter(Boolean);
    if (!values.length || values.includes("everyday")) return true;
    const names = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
    return values.includes(names[date.getDay()]);
  }

  minutesUntilNextSchedule(kind, value, weekdaysValue) {
    const now = new Date();
    const candidate = new Date(now);
    if (kind === "interval") {
      const minute = Number.parseInt(value, 10);
      if (!Number.isInteger(minute) || minute < 0 || minute > 59) return null;
      candidate.setSeconds(0, 0);
      candidate.setMinutes(minute);
      if (candidate <= now) candidate.setHours(candidate.getHours() + 1);
      while (!this.selectedWeekdayAllows(candidate, weekdaysValue)) candidate.setHours(candidate.getHours() + 1);
      return Math.ceil((candidate - now) / 60000);
    }
    if (!/^\d{2}:\d{2}$/.test(String(value || ""))) return null;
    const [hourText, minuteText] = String(value).split(":");
    const hour = Number.parseInt(hourText, 10);
    const minute = Number.parseInt(minuteText, 10);
    if (!Number.isInteger(hour) || !Number.isInteger(minute)) return null;
    candidate.setHours(hour, minute, 0, 0);
    if (candidate <= now) candidate.setDate(candidate.getDate() + 1);
    while (!this.selectedWeekdayAllows(candidate, weekdaysValue)) candidate.setDate(candidate.getDate() + 1);
    return Math.ceil((candidate - now) / 60000);
  }

  updateScheduleTimeWarning(form) {
    const input = form && form.querySelector("[data-schedule-time]");
    const warning = form && form.querySelector("[data-schedule-time-warning]");
    if (warning) warning.hidden = true;
    if (input) input.setCustomValidity("");
    return true;
  }

  timerEntryRow(entry = {}, index = 0) {
    const time = /^\d{2}:\d{2}$/.test(String(entry.time || "")) ? String(entry.time) : "00:00";
    const ml = Number.isFinite(Number(entry.ml)) ? Number(entry.ml).toFixed(1) : "1.0";
    return `<div class="doser-timer-entry" data-schedule-timer-entry>
      <b>${index + 1}</b>
      <label><span>${this.tr("timer_time")}</span><input type="time" value="${time}" data-schedule-timer-time></label>
      <label><span>${this.tr("timer_amount")}</span><input type="number" min="0.1" max="999.9" step="0.1" value="${ml}" data-schedule-timer-ml></label>
      <button type="button" class="secondary" data-schedule-timer-remove>${this.tr("timer_remove")}</button>
    </div>`;
  }

  timerEntriesFromForm(form) {
    return Array.from(form.querySelectorAll("[data-schedule-timer-entry]")).map((row) => ({
      time: String(row.querySelector("[data-schedule-timer-time]")?.value || ""),
      ml: Number.parseFloat(row.querySelector("[data-schedule-timer-ml]")?.value || ""),
    }));
  }

  windowEntryRow(entry = {}, index = 0) {
    const start = /^\d{2}:\d{2}$/.test(String(entry.start || "")) ? String(entry.start) : "00:00";
    const end = /^\d{2}:\d{2}$/.test(String(entry.end || "")) ? String(entry.end) : "00:30";
    const doses = Number.isInteger(Number(entry.doses)) ? Number(entry.doses) : 1;
    return `<div class="doser-window-entry" data-schedule-window-entry>
      <b>${index + 1}</b>
      <label><span>${this.tr("window_start")}</span><input type="time" value="${start}" data-schedule-window-start></label>
      <label><span>${this.tr("window_end")}</span><input type="time" value="${end}" data-schedule-window-end></label>
      <label><span>${this.tr("window_doses")}</span><input type="number" min="1" max="24" step="1" value="${doses}" data-schedule-window-doses></label>
      <button type="button" class="secondary" data-schedule-window-remove>${this.tr("timer_remove")}</button>
    </div>`;
  }

  windowEntriesFromForm(form) {
    return Array.from(form.querySelectorAll("[data-schedule-window-entry]")).map((row) => ({
      start: String(row.querySelector("[data-schedule-window-start]")?.value || ""),
      end: String(row.querySelector("[data-schedule-window-end]")?.value || ""),
      doses: Number.parseInt(row.querySelector("[data-schedule-window-doses]")?.value || "", 10),
    }));
  }

  validateWindowEntries(entries) {
    if (!Array.isArray(entries) || !entries.length) return this.tr("window_count_error");
    let totalDoses = 0;
    for (const entry of entries) {
      const startMatch = String(entry.start || "").match(/^(\d{2}):(\d{2})$/);
      const endMatch = String(entry.end || "").match(/^(\d{2}):(\d{2})$/);
      const start = startMatch ? Number(startMatch[1]) * 60 + Number(startMatch[2]) : Number.NaN;
      const end = endMatch ? Number(endMatch[1]) * 60 + Number(endMatch[2]) : Number.NaN;
      const doses = Number(entry.doses);
      if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || start > 1439 || end < 0 || end > 1439
        || !Number.isInteger(doses) || doses < 1 || doses > 24 || end < start || (end === start && doses > 1)) {
        return this.tr("window_count_error");
      }
      const duration = end - start;
      if (doses > 1 && duration > 30 * (doses - 1)) return this.tr("window_gap_error");
      totalDoses += doses;
    }
    if (totalDoses > 24) return this.tr("window_count_error");
    return "";
  }

  updateTimerTotal(form) {
    const amount = form && form.querySelector("[data-schedule-ml]");
    if (!amount) return;
    const total = this.timerEntriesFromForm(form).reduce((sum, entry) =>
      sum + (Number.isFinite(entry.ml) ? entry.ml : 0), 0);
    amount.value = (Math.round(total * 10) / 10).toFixed(1);
  }

  schedulePendingSendKey(channel) {
    return `${String(this.deviceAddress || "").toUpperCase()}:CH${Number(channel) || 1}`;
  }

  markScheduleUnsent(form) {
    const warning = form && form.querySelector("[data-schedule-unsent-warning]");
    if (warning) warning.hidden = false;
  }

  setScheduleRequestState(form, state = "pending", message = "", detail = "") {
    const banner = form && form.querySelector("[data-schedule-request-status]");
    if (!banner) return;
    banner.hidden = false;
    banner.classList.toggle("is-error", state === "error");
    banner.classList.toggle("is-ok", state === "ok");
    const label = banner.querySelector("strong");
    const output = banner.querySelector("small");
    if (label) label.textContent = message;
    if (output) {
      output.textContent = detail;
      output.hidden = !detail;
    }
    form.querySelectorAll("button").forEach((button) => {
      button.disabled = state === "pending";
    });
  }

  scheduleHasPendingSend(channel) {
    const pending = this.doserPendingScheduleSends || {};
    return pending[this.schedulePendingSendKey(channel)] === true;
  }

  setSchedulePendingSend(channel, pending) {
    this.doserPendingScheduleSends = this.doserPendingScheduleSends || {};
    const key = this.schedulePendingSendKey(channel);
    if (pending) this.doserPendingScheduleSends[key] = true;
    else delete this.doserPendingScheduleSends[key];
  }

  validateTimerEntries(entries) {
    if (!Array.isArray(entries) || entries.length < 1 || entries.length > 24) return this.tr("timer_count_error");
    const normalized = entries.map((entry) => {
      const match = String(entry.time || "").match(/^(\d{2}):(\d{2})$/);
      const hour = match ? Number.parseInt(match[1], 10) : Number.NaN;
      const minute = match ? Number.parseInt(match[2], 10) : Number.NaN;
      const ml = Number(entry.ml);
      return { ...entry, minutes: hour * 60 + minute, valid: hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59 && ml >= 0.1 };
    });
    if (normalized.some((entry) => !entry.valid)) return this.tr("timer_count_error");
    normalized.sort((left, right) => left.minutes - right.minutes);
    if (new Set(normalized.map((entry) => entry.minutes)).size !== normalized.length) return this.tr("timer_gap_error");
    for (let index = 0; index < normalized.length; index += 1) {
      const current = normalized[index].minutes;
      const following = normalized[(index + 1) % normalized.length].minutes + (index === normalized.length - 1 ? 1440 : 0);
      if (following - current < 10) return this.tr("timer_gap_error");
    }
    return "";
  }

  refreshTimerEntryRows(form) {
    const rows = Array.from(form.querySelectorAll("[data-schedule-timer-entry]"));
    rows.forEach((row, index) => {
      const number = row.querySelector("b");
      if (number) number.textContent = String(index + 1);
      const remove = row.querySelector("[data-schedule-timer-remove]");
      if (remove) remove.disabled = rows.length <= 1;
    });
    const add = form.querySelector("[data-schedule-timer-add]");
    if (add) add.disabled = rows.length >= 24;
    this.updateTimerTotal(form);
  }

  bindScheduleTimerControls(form) {
    const rows = form.querySelector("[data-schedule-timer-rows]");
    const bindAmount = (input) => input.addEventListener("input", () => {
      this.updateTimerTotal(form);
      this.markScheduleUnsent(form);
    });
    const bindTime = (input) => input.addEventListener("input", () => this.markScheduleUnsent(form));
    const bindRemove = (button) => button.addEventListener("click", () => {
      button.closest("[data-schedule-timer-entry]")?.remove();
      this.refreshTimerEntryRows(form);
      this.markScheduleUnsent(form);
    });
    form.querySelectorAll("[data-schedule-timer-remove]").forEach(bindRemove);
    form.querySelectorAll("[data-schedule-timer-ml]").forEach(bindAmount);
    form.querySelectorAll("[data-schedule-timer-time]").forEach(bindTime);
    const add = form.querySelector("[data-schedule-timer-add]");
    if (add && rows) add.addEventListener("click", () => {
      const count = rows.querySelectorAll("[data-schedule-timer-entry]").length;
      if (count >= 24) return;
      rows.insertAdjacentHTML("beforeend", this.timerEntryRow({ time: "00:00", ml: 1.0 }, count));
      const newRow = rows.lastElementChild;
      const button = newRow?.querySelector("[data-schedule-timer-remove]");
      if (button) bindRemove(button);
      const amount = newRow?.querySelector("[data-schedule-timer-ml]");
      if (amount) bindAmount(amount);
      const time = newRow?.querySelector("[data-schedule-timer-time]");
      if (time) bindTime(time);
      this.refreshTimerEntryRows(form);
      this.markScheduleUnsent(form);
      window.requestAnimationFrame(() => {
        rows.scrollTop = rows.scrollHeight;
        newRow?.querySelector("[data-schedule-timer-time]")?.focus({ preventScroll: true });
      });
    });
    this.refreshTimerEntryRows(form);
  }

  refreshWindowEntryRows(form) {
    const rows = Array.from(form.querySelectorAll("[data-schedule-window-entry]"));
    rows.forEach((row, index) => {
      const number = row.querySelector("b");
      if (number) number.textContent = String(index + 1);
      const remove = row.querySelector("[data-schedule-window-remove]");
      if (remove) remove.disabled = rows.length <= 1;
    });
    const total = rows.reduce((sum, row) => sum + Number(row.querySelector("[data-schedule-window-doses]")?.value || 0), 0);
    const count = form.querySelector("[data-schedule-window-total]");
    if (count) count.textContent = `${total} / 24`;
    const add = form.querySelector("[data-schedule-window-add]");
    if (add) add.disabled = total >= 24;
  }

  bindScheduleWindowControls(form) {
    const rows = form.querySelector("[data-schedule-window-rows]");
    const bindInput = (input) => input.addEventListener("input", () => {
      this.refreshWindowEntryRows(form);
      this.markScheduleUnsent(form);
    });
    const bindRemove = (button) => button.addEventListener("click", () => {
      button.closest("[data-schedule-window-entry]")?.remove();
      this.refreshWindowEntryRows(form);
      this.markScheduleUnsent(form);
    });
    form.querySelectorAll("[data-schedule-window-entry] input").forEach(bindInput);
    form.querySelectorAll("[data-schedule-window-remove]").forEach(bindRemove);
    const add = form.querySelector("[data-schedule-window-add]");
    if (add && rows) add.addEventListener("click", () => {
      const count = rows.querySelectorAll("[data-schedule-window-entry]").length;
      rows.insertAdjacentHTML("beforeend", this.windowEntryRow({ start: "00:00", end: "00:30", doses: 1 }, count));
      const newRow = rows.lastElementChild;
      newRow?.querySelectorAll("input").forEach(bindInput);
      const remove = newRow?.querySelector("[data-schedule-window-remove]");
      if (remove) bindRemove(remove);
      this.refreshWindowEntryRows(form);
      this.markScheduleUnsent(form);
      window.requestAnimationFrame(() => newRow?.querySelector("[data-schedule-window-start]")?.focus());
    });
    this.refreshWindowEntryRows(form);
  }

  bindScheduleWeekdayControls(form) {
    const value = form.querySelector("[data-schedule-weekdays]");
    const everyday = form.querySelector("[data-schedule-everyday]");
    const buttons = Array.from(form.querySelectorAll("[data-schedule-weekday]"));
    if (!value || !everyday || !buttons.length) return;
    const sync = (notify = true) => {
      if (everyday.checked) {
        buttons.forEach((button) => {
          button.classList.remove("active");
          button.disabled = true;
        });
        value.value = "everyday";
      } else {
        buttons.forEach((button) => { button.disabled = false; });
        const selected = buttons.filter((button) => button.classList.contains("active"));
        if (!selected.length) {
          buttons[0].classList.add("active");
          selected.push(buttons[0]);
        }
        if (selected.length === buttons.length) {
          everyday.checked = true;
          buttons.forEach((button) => {
            button.classList.remove("active");
            button.disabled = true;
          });
          value.value = "everyday";
        } else {
          value.value = selected.map((button) => button.dataset.scheduleWeekday).join(",");
        }
      }
      if (notify) value.dispatchEvent(new Event("change", { bubbles: true }));
    };
    everyday.addEventListener("change", () => {
      if (!everyday.checked) buttons.forEach((button) => button.classList.remove("active"));
      sync();
    });
    buttons.forEach((button) => button.addEventListener("click", () => {
      if (everyday.checked) {
        everyday.checked = false;
        buttons.forEach((item) => item.classList.remove("active"));
      }
      button.classList.toggle("active");
      sync();
    }));
    sync(false);
  }

  updateScheduleTimeInput(form) {
    const kind = form && form.querySelector("[data-schedule-kind]");
    const input = form && form.querySelector("[data-schedule-time]");
    const label = form && form.querySelector("[data-schedule-time-label]");
    const amount = form && form.querySelector("[data-schedule-ml]");
    const amountLabel = form && form.querySelector("[data-schedule-amount-label]");
    const amountHint = form && form.querySelector("[data-schedule-ml-hint]");
    const timeField = form && form.querySelector("[data-schedule-time-field]");
    const amountField = form && form.querySelector("[data-schedule-amount-field]");
    const timerList = form && form.querySelector("[data-schedule-timer-list]");
    const windowList = form && form.querySelector("[data-schedule-window-list]");
    if (!kind || !input || !label) return;
    const timerMode = kind.value === "timer";
    const windowMode = kind.value === "window";
    if (timeField) timeField.hidden = timerMode || windowMode;
    if (amountField) amountField.hidden = false;
    if (timerList) timerList.hidden = !timerMode;
    if (windowList) windowList.hidden = !windowMode;
    if (amountLabel) amountLabel.textContent = windowMode ? this.tr("window_daily_amount") : this.tr("amount");
    if (amount) {
      amount.readOnly = timerMode;
      amount.toggleAttribute("aria-readonly", timerMode);
    }
    if (timerMode) {
      this.updateTimerTotal(form);
      this.updateScheduleTimeWarning(form);
      return;
    }
    if (windowMode) {
      if (amount) amount.min = "0.2";
      if (amountHint) amountHint.hidden = true;
      this.updateScheduleTimeWarning(form);
      return;
    }
    if (kind.value === "interval") {
      let current = Number.parseInt(input.value, 10);
      if (/^\d{2}:\d{2}$/.test(input.value)) current = Number.parseInt(input.value.slice(3, 5), 10);
      input.type = "number";
      input.min = "0";
      input.max = "59";
      input.step = "1";
      input.value = Number.isInteger(current) && current >= 0 && current <= 59 ? String(current) : "0";
      label.textContent = this.tr("interval_minutes");
      if (amount) amount.min = "5.0";
      if (amountHint) amountHint.hidden = false;
      this.updateScheduleTimeWarning(form);
      return;
    }
    input.type = "time";
    input.removeAttribute("min");
    input.removeAttribute("max");
    input.removeAttribute("step");
    if (!/^\d{2}:\d{2}$/.test(input.value)) {
      const minute = Number.parseInt(input.value, 10);
      input.value = Number.isInteger(minute) && minute >= 0 && minute <= 59 ? `00:${String(minute).padStart(2, "0")}` : "00:00";
    }
    label.textContent = this.tr("time");
    if (amount) amount.min = "0.2";
    if (amountHint) amountHint.hidden = true;
    this.updateScheduleTimeWarning(form);
  }

  async saveScheduleDialog(form, send = true) {
    const channel = Number(form.channel.value);
    const ml = Number.parseFloat(form.ml.value);
    const scheduleKind = form.kind.value || "single_dose";
    const debug = Boolean(form.debug && form.debug.checked);
    const e = this.entities(channel);
    const autoLimitReached = this.autoLimitReached(e);
    const validFromTomorrow = Boolean(form.valid_from_tomorrow && form.valid_from_tomorrow.checked) || autoLimitReached;
    const active = validFromTomorrow ? true : form.active.checked;
    if (!Number.isFinite(channel) || (!Number.isFinite(ml) && scheduleKind !== "timer")) return;
    let displayTime = form.time.value || "00:00";
    const data = {
      pump: channel,
      active,
      kind: scheduleKind,
      ml,
      weekdays: String(form.weekdays.value || "everyday").split(",").filter(Boolean),
      send,
      valid_from_tomorrow: validFromTomorrow,
    };
    if (debug) data.debug = true;
    if (scheduleKind === "timer") {
      const timerEntries = this.timerEntriesFromForm(form);
      const timerError = this.validateTimerEntries(timerEntries);
      if (timerError) {
        const firstInput = form.querySelector("[data-schedule-timer-time]");
        if (firstInput) {
          firstInput.setCustomValidity(timerError);
          firstInput.reportValidity();
          firstInput.addEventListener("input", () => firstInput.setCustomValidity(""), { once: true });
        }
        return;
      }
      timerEntries.sort((left, right) => left.time.localeCompare(right.time));
      data.timers = timerEntries;
      data.ml = Math.round(timerEntries.reduce((total, entry) => total + Number(entry.ml), 0) * 10) / 10;
      data.time = timerEntries[0].time;
      displayTime = `${timerEntries.length} ${this.tr("single_dose")}`;
    }
    if (scheduleKind === "window") {
      const windowEntries = this.windowEntriesFromForm(form);
      const windowError = this.validateWindowEntries(windowEntries);
      if (windowError) {
        const firstInput = form.querySelector("[data-schedule-window-start]");
        if (firstInput) {
          firstInput.setCustomValidity(windowError);
          firstInput.reportValidity();
          firstInput.addEventListener("input", () => firstInput.setCustomValidity(""), { once: true });
        }
        return;
      }
      windowEntries.sort((left, right) => left.start.localeCompare(right.start));
      data.windows = windowEntries;
      displayTime = windowEntries[0].start;
    }
    if (scheduleKind !== "interval" && scheduleKind !== "timer") data.time = displayTime;
    if (scheduleKind === "interval") {
      const interval = Number.parseInt(form.time.value, 10);
      if (!Number.isInteger(interval) || interval < 0 || interval > 59) {
        form.time.focus();
        form.time.reportValidity();
        return;
      }
      if (ml < 5.0) {
        form.ml.min = "5.0";
        form.ml.focus();
        form.ml.reportValidity();
        return;
      }
      data.interval = interval;
      displayTime = `00:${String(interval).padStart(2, "0")}`;
    }
    this.setScheduleRequestState(
      form,
      "pending",
      send ? this.tr("debug_sending") : this.tr("saving"),
    );
    const result = await this.runDeviceService({
      service: "set_doser_schedule",
      data,
      title: this.tr("schedule"),
      debug,
      dialog: false,
      channel,
      noChannel: false,
    });
    if (!result || !result.response) {
      this.setScheduleRequestState(
        form,
        "error",
        send ? this.tr("send_failed") : this.tr("local_save_failed"),
        result && result.output ? result.output : this.tr("service_unavailable"),
      );
      return;
    }
    const state = active ? "aktiv" : "inaktiv";
    const serviceResponse = result.serviceResponse || this.serviceResponse(result.response, "set_doser_schedule");
    const sendOk = !serviceResponse
      || serviceResponse.ok === true
      || !serviceResponse.send_status
      || serviceResponse.send_status === "ok";
    const saveOk = !serviceResponse || serviceResponse.ok === true;
    if (saveOk) {
      if (send && sendOk) this.setSchedulePendingSend(channel, false);
      if (!send) this.setSchedulePendingSend(channel, true);
    }
    const historyEntries = [
      this.nowHistoryEntry("Zeitplan gespeichert", channel, `${state}, ${scheduleKind}, ${displayTime}, ${Number(data.ml).toFixed(1)} mL${validFromTomorrow ? ", gueltig ab morgen" : ""}`),
    ];
    if (send) {
      historyEntries.unshift(this.nowHistoryEntry(sendOk ? "Geraet senden OK" : "Geraet senden FAIL", channel, serviceResponse && serviceResponse.send_detail ? serviceResponse.send_detail : "an Geraet gesendet"));
    }
    if (!saveOk || (send && !sendOk)) {
      this.setScheduleRequestState(
        form,
        "error",
        send ? this.tr("send_failed") : this.tr("local_save_failed"),
        result.output || (serviceResponse && serviceResponse.send_detail) || "",
      );
    }
    this.addHistoryEntries(historyEntries);
    await this.refreshChannelEntities(channel);
    await this.refreshHistory();
    if (!saveOk || (send && !sendOk)) return;
    if (saveOk) {
      await this.refreshScheduleDialogState(channel);
      this.dialogState = {
        type: "schedule",
        channel,
        scheduleEditMode: false,
        scheduleRequestSuccess: {
          message: send ? this.tr("schedule_sent") : this.tr("led_schedule_saved"),
          detail: send
            ? ((serviceResponse && serviceResponse.send_detail) || this.tr("reply_sent"))
            : this.tr("led_schedule_not_sent"),
        },
        scheduleSnapshot: {
          kind: scheduleKind,
          time: data.time || displayTime,
          interval: data.interval,
          ml: Number(data.ml),
          timers: Array.isArray(data.timers) ? data.timers : [],
          windows: Array.isArray(data.windows) ? data.windows : [],
          weekdays: data.weekdays,
          active,
          validFromTomorrow,
          debugOutput: debug ? result.output : "",
        },
      };
      this.render();
    }
  }

  async saveContainerDialog(form) {
    const channel = Number(form.channel.value);
    const ml = Number.parseFloat(form.ml.value);
    if (!Number.isFinite(channel) || !Number.isFinite(ml)) return;
    await this.runDeviceService({
      service: "set_doser_container",
      data: { pump: channel, ml },
      title: this.tr("container_volume"),
      dialog: true,
      channel,
      noChannel: false,
    });
    await this.refreshChannelEntities(channel);
  }

  async saveSafetyDialog(form) {
    const maxAutoMl = Number.parseFloat(form.max_auto_ml.value);
    const maxManualMl = Number.parseFloat(form.max_manual_ml.value);
    const maxDailyMl = Number.parseFloat(form.max_daily_ml.value);
    if (!Number.isFinite(maxAutoMl) || !Number.isFinite(maxManualMl) || !Number.isFinite(maxDailyMl)) return;
    const result = await this.runDeviceService({
      service: "set_doser_safety",
      data: { max_auto_ml: maxAutoMl, max_manual_ml: maxManualMl, max_daily_ml: maxDailyMl },
      title: this.tr("safety"),
      dialog: true,
      channel: 1,
      noChannel: true,
    });
    if (!result || !result.response) return;
    this.saveDoserSafetySettings(maxAutoMl, maxManualMl, maxDailyMl);
    await this.refreshHistory();
  }

  async saveAutoFillDialog(form) {
    const enabled = Boolean(form.enabled && form.enabled.checked);
    const targets = Array.from(form.querySelectorAll("[name='target']"))
      .map((select) => String(select.value || "").trim())
      .filter(Boolean)
      .slice(0, 3);
    const message = String(form.message.value || "").trim();
    const result = await this.runDeviceService({
      service: "set_doser_push_settings",
      data: { enabled, targets, message },
      title: this.tr("push_settings"),
      dialog: true,
      channel: 1,
      noChannel: true,
    });
    if (!result || !result.response) return;
    await this.refreshDoserEntities();
  }

  async saveManualDialog(form) {
    const channel = Number(form.channel.value);
    const ml = Number.parseFloat(form.ml.value);
    const debug = Boolean(this.uiSettings && this.uiSettings.dashboardDebug);
    if (!Number.isFinite(channel) || !Number.isFinite(ml)) return;
    const safety = this.doserSafetySettings();
    const e = this.entities(channel);
    const currentManual = this.numericValue(e.manualDaily, 0);
    if (form.dose_now.checked && currentManual + ml > safety.maxManualMl) {
      this.dialogState = {
        type: "debug",
        channel,
        output: `FAIL\nUeberdosierungsschutz\nCH${channel}: Manuell ${(currentManual + ml).toFixed(1)} mL > Limit ${safety.maxManualMl.toFixed(1)} mL`,
        running: false,
        level: "error",
      };
      this.render();
      return;
    }
    const currentDaily = this.numericValue(e.daily, 0);
    if (form.dose_now.checked && currentDaily + ml > safety.maxDailyMl) {
      this.dialogState = {
        type: "debug",
        channel,
        output: `FAIL\nUeberdosierungsschutz\nCH${channel}: Tagesmenge ${(currentDaily + ml).toFixed(1)} mL > Limit ${safety.maxDailyMl.toFixed(1)} mL`,
        running: false,
        level: "error",
      };
      this.render();
      return;
    }
    await this._hass.callService("number", "set_value", { entity_id: e.manual, value: ml });
    if (form.dose_now.checked) {
      const result = await this.runDeviceService({
        service: "dose_ml",
        data: { pump: channel, ml },
        title: this.tr("manual_dose"),
        debug,
        dialog: debug,
        channel,
        noChannel: false,
      });
      if (!result || !result.ok) {
        this.dialogState = {
          type: "debug",
          channel,
          output: result && result.output ? result.output : `FAIL\n${this.tr("manual_dose")}`,
          running: false,
          level: "error",
          debug,
        };
        this.render();
        return;
      }
      if (debug) {
        await this.refreshChannelEntities(channel);
        return;
      }
    }
    this.dialogState = {
      type: "debug",
      channel,
      output: `OK\n${this.tr("manual")}\n${ml.toFixed(1)} mL${form.dose_now.checked ? `\n${this.tr("dose_now")}` : ""}`,
      running: false,
    };
    this.render();
    await this.refreshChannelEntities(channel);
  }

  async saveCalibrationDialog(form) {
    const channel = Number(this.dialogState && this.dialogState.channel);
    if (!Number.isFinite(channel)) return;
    try {
      const debug = Boolean(this.uiSettings && this.uiSettings.dashboardDebug);
      const measured = Number.parseFloat(String(form.measured_ml.value || "").replace(",", "."));
      if (!Number.isFinite(measured)) {
        window.alert(this.tr("enter_measured"));
        return;
      }
      const data = {
        pump: channel,
        ml: measured,
        reminder_days: 30,
      };
      const result = await this.runDeviceService({
        service: "submit_doser_calibration",
        data,
        title: this.tr("calibration"),
        debug,
        dialog: false,
        channel,
        noChannel: false,
      });
      if (!result || !result.ok) {
        this.dialogState = {
          type: "calibration",
          channel,
          step: 3,
          calibrationOutput: result && result.output ? result.output : `FAIL\n${this.tr("calibration_failed")}`,
        };
        this.render();
        return;
      }
      await this.refreshChannelEntities(channel);
      const calibratedDisplay = new Date();
      const reminderDisplay = new Date(calibratedDisplay.getTime() + 30 * 86400000);
      this.dialogState = {
        type: "calibration",
        channel,
        step: 4,
        measuredMl: measured,
        calibratedDisplay: calibratedDisplay.toLocaleString(),
        reminderDisplay: reminderDisplay.toLocaleDateString(),
        calibrationOutput: debug ? result.output : "",
        calibrationSaved: true,
      };
      this.render();
    } catch (err) {
      this.dialogState = {
        type: "debug",
        channel,
        output: `FAIL\n${this.tr("calibration_failed")}: ${(err && err.message) || err}`,
        running: false,
      };
      this.render();
    }
  }


  bottleVisual(ch, e) {
    const remaining = this.numericValue(e.remainingSensor, 0);
    const full = Number.isFinite(this.containerFullMl) && this.containerFullMl > 0 ? this.containerFullMl : 500;
    const percent = Math.max(0, Math.min(100, Math.round((remaining / full) * 100)));
    const level = Math.max(6, Math.min(82, percent));
    const fillOpacity = Math.max(0.38, Math.min(0.78, 0.32 + percent / 180));
    return `
        <div class="bottle-wrap" data-action="dialog:container:${ch.id}">
        <div class="bottle" style="--fill:${ch.color};--level:${level}%;--fill-opacity:${fillOpacity}"><i></i></div>
        <div class="bottle-text">
          <span>${this.tr("container_volume")}</span>
          <strong>${this.state(e.remainingSensor)}</strong>
        </div>
      </div>`;
  }

  manualControl(e, ch) {
    const safety = this.doserSafetySettings();
    const currentManual = this.numericValue(e.manualDaily, 0);
    const nextManual = currentManual + this.numericValue(e.manual, 0);
    const manualBlocked = nextManual > safety.maxManualMl;
    return `
      <div class="manual-control ${manualBlocked ? "blocked" : ""}">
        <label data-action="dialog:manual:${ch}"><ha-icon icon="mdi:cup-water"></ha-icon><span>${this.tr("manual")}</span></label>
        <div class="manual-input">
          <input type="number" min="0.2" max="999.9" step="0.1" value="${this.numericState(e.manual)}" data-number="${e.manual}">
          <span>mL</span>
        </div>
        <button class="dose-inline ${manualBlocked ? "blocked" : ""}" data-action="${manualBlocked ? `manual-blocked:${ch}` : `dose-inline:${ch}`}" title="${manualBlocked ? this.tr("manual_blocked") : this.tr("dose")}">
          <ha-icon icon="mdi:play-circle"></ha-icon>
        </button>
      </div>`;
  }

  historyEntries(limit = 8) {
    const entity = this.historyEntity();
    const attrs = this._hass && this._hass.states[entity] ? this._hass.states[entity].attributes : {};
    const storedEntries = Array.isArray(attrs.entries) ? attrs.entries : [];
    const overlayEntries = Array.isArray(this.historyOverlay) ? this.historyOverlay : [];
    const seen = new Set();
    const entries = [...storedEntries, ...overlayEntries].filter((entry) => {
      const key = `${entry.date || ""}|${entry.time || ""}|${entry.pump || ""}|${entry.action || ""}|${entry.detail || ""}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    const enriched = entries.map((entry, index) => {
      if (entry.action !== "set_doser_schedule_send") return entry;
      const scheduleEntry = entries.slice(index + 1).find((candidate) => (
        candidate.action === "set_doser_schedule"
        && Number(candidate.pump || 0) === Number(entry.pump || 0)
      ));
      if (!scheduleEntry) return entry;
      const scheduleParams = scheduleEntry.params && typeof scheduleEntry.params === "object" ? scheduleEntry.params : {};
      const sendParams = entry.params && typeof entry.params === "object" ? entry.params : {};
      return { ...entry, params: { ...scheduleParams, ...sendParams } };
    });
    return enriched.slice(0, limit);
  }

  doserNotificationSummary() {
    const timerEntity = this.timerStatusEntity();
    const timerState = this._hass && timerEntity ? this._hass.states[timerEntity] : null;
    const attrs = timerState && timerState.attributes ? timerState.attributes : {};
    const historyEntry = this.historyEntries(120).find((entry) => entry.action === "doser_notification_poll") || {};
    const status = String(attrs.last_notification_status || historyEntry.status || "").toLowerCase();
    const timestamp = String(attrs.last_notification_at || historyEntry.ts || "");
    return {
      status,
      timestamp,
      statusText: status === "ok"
        ? "OK"
        : (status === "error" || status === "fail" ? "ERROR" : this.tr("unknown")),
    };
  }

  doserStatusSnapshotDetails(model) {
    const params = Array.isArray(model.params) ? model.params : [];
    if (params.length < 43) return [];
    const english = this.language() === "en";
    const kindByMarker = {
      0: english ? "Single dose" : "Einzeldosis",
      1: english ? "24h/interval" : "24h/Intervall",
      2: english ? "Timer list" : "Timerliste",
      3: english ? "Custom" : "Benutzerdefiniert",
      4: english ? "inactive/empty" : "inaktiv/leer",
    };
    const blockStarts = [3, 12, 21, 30];
    const details = [
      `${english ? "Header/status" : "Header/Status"}=[${params.slice(0, 3).join(", ")}] (${english ? "bit layout unknown" : "Bitbelegung offen"})`,
    ];
    blockStarts.forEach((blockStart, channelIndex) => {
      const marker = Number(params[blockStart]);
      const parts = [`CH${channelIndex + 1}: ${kindByMarker[marker] || (english ? "Unknown type" : "Art unbekannt")}`, `marker=${marker}`];
      if (marker === 0) {
        const hour = Number(params[blockStart + 1]);
        const minute = Number(params[blockStart + 2]);
        if (hour <= 23 && minute <= 59) {
          parts.push(`${english ? "Time" : "Zeit"}=${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`);
        }
      } else if ([2, 3].includes(marker)) {
        const times = [];
        [1, 3, 5].forEach((offset) => {
          const hour = Number(params[blockStart + offset]);
          const minute = Number(params[blockStart + offset + 1]);
          if (hour <= 23 && minute <= 59 && (hour || minute)) {
            times.push(`${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`);
          }
        });
        if (times.length) parts.push(`${english ? "Times" : "Zeiten"}=${times.join(",")}`);
      }
      const dailyMl = ((Number(params[blockStart + 7]) * 256) + Number(params[blockStart + 8])) / 10;
      parts.push(`${english ? "Scheduled amount" : "Planmenge"}=${Number(params[39 + channelIndex])} mL`);
      parts.push(`${english ? "Auto today" : "Auto-heute"}=${dailyMl.toFixed(1)} mL`);
      details.push(parts.join(", "));
    });
    return details;
  }

  doserNotificationDialog() {
    const entry = this.historyEntries(200).find((item) => item.action === "doser_notification_poll") || {};
    const params = entry.params && typeof entry.params === "object" ? entry.params : {};
    const timerEntity = this.timerStatusEntity();
    const timerState = this._hass && timerEntity ? this._hass.states[timerEntity] : null;
    const timerAttrs = timerState && timerState.attributes ? timerState.attributes : {};
    const rawFrames = Array.isArray(params.raw_frames) && params.raw_frames.length
      ? params.raw_frames
      : (Array.isArray(timerAttrs.last_notification_frames) ? timerAttrs.last_notification_frames : []);
    const fallbackMeaning = this.historyDetailText(entry.detail || "") || this.tr("unknown");
    const device = this.activeDoserDevice || {};
    const deviceLabel = String(device.name || device.label || this.deviceName || this.tr("doser"));
    const deviceAddress = String(this.deviceAddress || device.address || device.id || "");
    const dialogScope = String(device.entity_prefix || deviceAddress || this.activeDoserDeviceId || "doser");
    return window.ChihirosNotificationUi.render(this, {
      notifications: rawFrames,
      title: this.tr("last_notification"),
      subtitle: [deviceLabel, deviceAddress].filter(Boolean).join(" · "),
      scope: dialogScope,
      emptyText: this.language() === "en"
        ? "No raw frames stored yet. They will appear after the next 15-minute poll."
        : "Noch keine Rohframes gespeichert. Sie erscheinen nach dem nächsten 15-Minuten-Abruf.",
      describe: (model) => {
        if (model.mode === 0xFE) {
          return {
            parsedType: "DOSER_STATUS_SNAPSHOT",
            tabLabel: this.language() === "en" ? "Status" : "Status",
            meaning: "Doser-Status-Snapshot 0xFE",
            details: this.doserStatusSnapshotDetails(model),
          };
        }
        if (![0x0A, 0x1E, 0x22].includes(model.mode)) {
          return { parsedType: "DOSER_NOTIFICATION", meaning: fallbackMeaning };
        }
        return {};
      },
    });
  }

  channelHistoryRows(channel, limit = 3, compact = true) {
    const entries = this.historyEntries(Math.max(60, limit * 8)).filter((entry) => Number(entry.pump || 0) === Number(channel)).slice(0, limit);
    if (!entries.length) {
      return `<div class="channel-history-empty">${this.tr("no_history")}</div>`;
    }
    return entries.map((entry) => {
      const detailText = this.historyDetailText(entry.detail || "");
      const detail = detailText ? ` · ${detailText}` : "";
      return `
        <div class="channel-history-row" data-action="dialog:history:${channel}">
          <span>${this.historyActionText(entry.action || "")}</span>
          <small>${this.formatHistoryTimestamp(entry.ts || `${entry.date || ""} ${entry.time || ""}`)}${compact ? "" : detail}</small>
        </div>`;
    }).join("");
  }

  channelCard(ch) {
    const e = this.entities(ch.id);
    const active = this.isOn(e.active);
    const autoLocked = this.autoLimitReached(e);
    return `
      <section class="channel">
        <div class="channel-card card ${active ? "" : "inactive"} ${autoLocked ? "auto-locked" : ""}" style="--dot:${ch.color}">
          <h2>CH${ch.id} ${ch.name}<i></i></h2>
          <div class="sub">${this.tr("status")}</div>
          ${this.bottleVisual(ch, e)}
          ${this.row(autoLocked ? "mdi:lock-outline" : "mdi:calendar-check", this.tr("active"), autoLocked ? this.tr("auto_limit_reached") : (active ? this.tr("on") : this.tr("off")), `dialog:schedule:${ch.id}`)}
          ${this.row("mdi:eye", this.tr("today"), this.state(e.daily), `more:${e.daily}`)}
          ${this.row("mdi:clock-outline", this.tr("time"), this.state(e.scheduleTimeSensor), `dialog:schedule:${ch.id}`)}
          ${this.row("mdi:cup-water", this.tr("planned_amount"), this.state(e.scheduleDoseSensor), `dialog:schedule:${ch.id}`)}
          ${this.row("mdi:eye", this.tr("history"), this.tr("details"), `dialog:history:${ch.id}`)}
          ${this.manualControl(e, ch.id)}
        </div>
      </section>`;
  }

  scheduleTable() {
    const rows = this.channels.map((ch) => {
      const e = this.entities(ch.id);
      const active = this.isOn(e.active);
      const autoLocked = this.autoLimitReached(e);
      const actions = this.sharedIconActionButtons([
        {
          action: `dialog:schedule:${ch.id}`,
          title: this.tr("edit"),
          icon: "mdi:pencil",
        },
        {
          action: `dialog:reset-schedule:${ch.id}`,
          title: this.tr("reset"),
          icon: "mdi:calendar-remove",
        },
      ]);
      return `
        <tr class="${active ? "" : "inactive-row"} ${autoLocked ? "auto-locked-row" : ""}">
          <td><span class="legend" style="background:${ch.color}"></span>CH${ch.id} ${ch.name}</td>
          <td>${autoLocked ? `<span class="schedule-lock"><ha-icon icon="mdi:lock-outline"></ha-icon>${this.tr("auto_limit_reached")}</span>` : this.scheduleToggle(e.active)}</td>
          <td>${this.scheduleKindLabel(e.scheduleTimeSensor)}</td>
          <td>${this.state(e.scheduleTimeSensor)}</td>
          <td>${this.state(e.scheduleDoseSensor)}</td>
          <td>${this.tr("everyday")}</td>
          <td>${actions}</td>
        </tr>`;
    }).join("");
    return `
      <section class="card schedule">
        <h2>${this.tr("schedule_title")}</h2>
        <table>
        <thead><tr><th>${this.tr("channel")}</th><th>${this.tr("schedule")}</th><th>${this.tr("scheduler")}</th><th>${this.tr("time")}</th><th>${this.tr("amount")}</th><th>${this.tr("weekdays")}</th><th>${this.tr("actions")}</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </section>`;
  }

  manualPanel(compact = false) {
    const rows = this.channels.map((ch) => {
      const e = this.entities(ch.id);
      return `
        <div class="value-row" data-action="more:${e.manualDaily}">
          <span class="legend" style="background:${ch.color}"></span>
          <ha-icon icon="mdi:hand-water"></ha-icon>
          <span>CH${ch.id} ${ch.name}</span>
          <strong>${this.stateFallback(e.manualDaily, "", "0.0 mL")}</strong>
        </div>`;
    }).join("");
    return `<section class="card manual-panel ${compact ? "top-card" : ""}"><h2>${this.tr("manual")}</h2>${rows}</section>`;
  }

  autoPanel(compact = false) {
    const rows = this.channels.map((ch) => {
      const e = this.entities(ch.id);
      return `
        <div class="value-row" data-action="more:${e.autoDaily}">
          <span class="legend" style="background:${ch.color}"></span>
          <ha-icon icon="mdi:calendar-sync"></ha-icon>
          <span>CH${ch.id} ${ch.name}</span>
          <strong>${this.stateFallback(e.autoDaily, "", "0.0 mL")}</strong>
        </div>`;
    }).join("");
    return `<section class="card auto-panel ${compact ? "top-card" : ""}"><h2>${this.tr("automatic")}</h2>${rows}</section>`;
  }

  dailyPanel(compact = false) {
    const rows = this.channels.map((ch) => {
      const e = this.entities(ch.id);
      return `
        <div class="value-row" data-action="more:${e.daily}">
          <span class="legend" style="background:${ch.color}"></span>
          <ha-icon icon="mdi:eye"></ha-icon>
          <span>CH${ch.id} ${ch.name}</span>
          <strong>${this.stateFallback(e.daily, "", "0.0 mL")}</strong>
        </div>`;
    }).join("");
    return `<section class="card daily-panel ${compact ? "top-card" : ""}"><h2>${this.tr("daily_amounts")}</h2>${rows}</section>`;
  }

  containerPanel(compact = false) {
    const rows = this.channels.map((ch) => {
      const e = this.entities(ch.id);
      return `
        <div class="container-row" data-action="dialog:container:${ch.id}">
          <span class="legend" style="background:${ch.color}"></span>
          <ha-icon icon="mdi:bottle-tonic-outline"></ha-icon>
          <span>CH${ch.id} ${ch.name}</span>
          <strong>${this.state(e.remainingSensor)}</strong>
          <button class="mini edit" data-action="dialog:container:${ch.id}" title="Bearbeiten">
            <ha-icon icon="mdi:pencil"></ha-icon>
          </button>
        </div>`;
    }).join("");
    return `<section class="card containers ${compact ? "top-card" : ""}"><h2>${this.tr("container")}</h2>${rows}</section>`;
  }

  historyActionText(action = "") {
    const german = {
      set_doser_schedule: "Zeitplan gespeichert",
      set_doser_schedule_send: "Zeitplan an Gerät gesendet",
      reset_doser_schedule: "Zeitplan zurückgesetzt",
      reset_doser_schedule_send: "Zurücksetzen an Gerät gesendet",
      set_doser_safety: "Dosierschutz gespeichert",
      auto_total_checkpoint: "Tageswerte geprüft",
      doser_notification_poll: "15-Minuten-Meldung",
      "Behaelter gesetzt": "Behälter gesetzt",
      "Geraet senden FAIL": "An Gerät senden fehlgeschlagen",
      "Geraet senden OK": "An Gerät gesendet",
      "Geraet senden nicht angefordert": "Nicht an Gerät gesendet",
      "Push Behaelterstand": "Behälterstand gesendet",
      "Tageswerte vom Geraet": "Tageswerte vom Gerät",
      "Zeitplan zurueckgesetzt": "Zeitplan zurückgesetzt",
    };
    const english = {
      set_doser_schedule: "Schedule saved",
      set_doser_schedule_send: "Schedule sent to device",
      reset_doser_schedule: "Schedule reset",
      reset_doser_schedule_send: "Schedule reset sent to device",
      set_doser_safety: "Dosing protection saved",
      auto_total_checkpoint: "Daily totals checked",
      doser_notification_poll: "15-minute notification",
      "Auto-Differenz": "Auto difference",
      "Automatische Dosierung": "Automatic dose",
      "Behaelter gesetzt": "Container updated",
      "Geraet senden FAIL": "Device send failed",
      "Geraet senden OK": "Device send OK",
      "Geraet senden nicht angefordert": "Device send not requested",
      "Kalibrierung gespeichert": "Calibration saved",
      "Kalibrierung gestartet": "Calibration started",
      "Manuelle Dosierung": "Manual dose",
      "Push Behaelterstand": "Container push",
      "Scheduler erfolgreich": "Scheduler successful",
      "Tageswerte vom Geraet": "Daily values from device",
      "Zeitplan gespeichert": "Schedule saved",
      "Zeitplan zurueckgesetzt": "Schedule reset",
    };
    const map = this.language() === "en" ? english : german;
    return map[action] || action || this.tr("actions");
  }

  historyTitleText(entry, channel) {
    const action = entry.action || "";
    const actionText = this.historyActionText(action);
    const channelTitleActions = new Set([
      "Scheduler erfolgreich",
      "Zeitplan gespeichert",
      "set_doser_schedule",
      "set_doser_schedule_send",
      "Geraet senden OK",
      "Geraet senden FAIL",
      "Geraet senden nicht angefordert",
    ]);
    return channel && channelTitleActions.has(action) ? `${actionText} ${channel}` : actionText;
  }

  historyDetailText(detail = "") {
    if (this.language() !== "en" || !detail) return detail;
    return String(detail)
      .replaceAll("an Geraet gesendet", "sent to device")
      .replaceAll("nicht an Geraet gesendet", "not sent to device")
      .replaceAll("nur lokal gespeichert", "saved locally only")
      .replaceAll("lokal zurueckgesetzt", "reset locally")
      .replaceAll("Zeitplan gesendet", "schedule sent")
      .replaceAll("Zeitplan deaktiviert", "schedule disabled")
      .replaceAll("Zeitplan nicht gesendet", "schedule not sent")
      .replaceAll("ausgefuehrt um", "executed at")
      .replaceAll("aktiv", "active")
      .replaceAll("inaktiv", "inactive")
      .replaceAll("taeglich", "daily")
      .replaceAll("Einzeldosis", "single dose")
      .replaceAll("Intervall", "interval");
  }

  historyParamsText(entry = {}) {
    let params = entry && entry.params && typeof entry.params === "object" ? entry.params : {};
    if (typeof entry.params === "string") {
      try { params = JSON.parse(entry.params); } catch (_error) { params = {}; }
    }
    const action = String(entry.action || "");
    const scheduleAction = action === "set_doser_schedule" || action === "set_doser_schedule_send";
    if (!scheduleAction) return "";
    const parts = [];
    const active = params.active;
    if (active !== undefined) parts.push(active ? this.tr("active") : this.tr("inactive"));
    const kind = String(params.schedule_kind || params.kind || "");
    const kindLabels = {
      single_dose: this.tr("single_dose"),
      interval: this.tr("interval"),
      timer: this.tr("timer_list"),
      window: this.tr("time_window"),
    };
    if (kind) parts.push(kindLabels[kind] || kind);
    if (params.time) parts.push(String(params.time));
    if (params.interval_minutes !== undefined && params.interval_minutes !== null) {
      parts.push(`${params.interval_minutes} min`);
    }
    if (params.ml !== undefined && params.ml !== null) parts.push(`${Number(params.ml).toFixed(1)} mL`);
    const weekdays = Array.isArray(params.weekdays) ? params.weekdays : [];
    if (weekdays.length) {
      const weekdayLabels = {
        everyday: this.tr("everyday"),
        monday: this.language() === "en" ? "Mon" : "Mo",
        tuesday: this.language() === "en" ? "Tue" : "Di",
        wednesday: this.language() === "en" ? "Wed" : "Mi",
        thursday: this.language() === "en" ? "Thu" : "Do",
        friday: this.language() === "en" ? "Fri" : "Fr",
        saturday: this.language() === "en" ? "Sat" : "Sa",
        sunday: this.language() === "en" ? "Sun" : "So",
      };
      parts.push(weekdays.map((day) => weekdayLabels[day] || day).join(", "));
    }
    if (params.valid_from_tomorrow) parts.push(this.tr("valid_from_tomorrow"));
    return parts.join(" · ");
  }

  historyPanel(compact = false) {
    const entity = this.historyEntity();
    const entries = this.historyEntries(compact ? 4 : 10);
    const normalizedEntries = entries.map((entry) => {
      const pump = Number(entry.pump || 0);
      const ch = this.channels.find((item) => item.id === pump);
      const color = ch ? ch.color : "#3d82b8";
      const channel = ch ? `CH${ch.id} ${ch.name}` : this.tr("doser");
      return this.normalizeHistoryEntry(entry, {
        title: this.historyTitleText(entry, ch ? channel : ""),
        detailParts: [channel, this.historyParamsText(entry), this.historyDetailText(entry.detail || "")],
        color,
        actionTarget: pump ? `dialog:history:${pump}` : `more:${entity}`,
      });
    });
    return this.sharedHistoryPanel({
      title: this.tr("history_total"),
      action: "dialog:history-all:1",
      emptyLabel: this.tr("no_history"),
      entries: normalizedEntries,
      className: compact ? "top-card front-history" : "",
    });
  }

  settings() {
    const lowNotification = this.lowContainerNotificationSwitch();
    const pushSettings = this.lowContainerPushSettings();
    const pushTargetText = pushSettings.targets.length ? pushSettings.targets.map((target) => `notify.${target}`).join(", ") : this.tr("no_push_target");
    const macRow = this.uiSettings && this.uiSettings.showMac === false ? "" : `<p><b>MAC</b><span>${this.deviceAddress}</span></p>`;
    const safety = this.doserSafetySettings();
    const device = this.activeDoserDevice || {};
    const deviceIdentifier = String(
      device.entity_prefix || device.alias || device.id || this.deviceName || "Chihiros Doser"
    ).toUpperCase();
    const notification = this.doserNotificationSummary();
    const notificationFailed = notification.status === "error" || notification.status === "fail";
    const notificationClass = notificationFailed ? "is-offline" : (notification.status === "ok" ? "ok" : "is-unknown");
    const notificationTime = notification.timestamp ? this.formatHistoryTimestamp(notification.timestamp) : this.tr("unknown");
    return `
      <h2 class="section-title">${this.tr("settings")}</h2>
      <div class="settings doser-settings-layout">
        <div class="doser-settings-main">
          <div class="settings-stack">
            <section class="card small">
              <h2>${this.tr("overdose")}</h2>
              <p><b>${this.tr("auto_limit")}</b><span>${safety.maxAutoMl.toFixed(1)} ml</span></p>
              <p><b>${this.tr("manual_limit")}</b><span>${safety.maxManualMl.toFixed(1)} ml</span></p>
              <p><b>${this.tr("daily_limit")}</b><span>${safety.maxDailyMl.toFixed(1)} ml</span></p>
              <small class="settings-note">${this.tr("manual_limit_note")}</small>
              <button class="link" data-action="dialog:safety:1">${this.tr("edit").toUpperCase()}</button>
            </section>
            <section class="card small">
              <h2>${this.tr("auto_fill")}</h2>
              <p><b>${this.tr("status")}</b><span>${this.tr("off")}</span></p>
              <p><b>${this.tr("threshold")}</b><span>10 %</span></p>
              <p><b>${this.tr("low_container_push")}</b>${this.scheduleToggle(lowNotification)}</p>
              <p><b>${this.tr("push_targets")}</b><span>${pushTargetText}</span></p>
              <button class="link" data-action="dialog:auto-fill:1">${this.tr("change").toUpperCase()}</button>
            </section>
          </div>
          ${this.topActions()}
        </div>
        <section class="card small doser-connection-card">
          <h2>${this.tr("connection")}</h2>
          <p><b>${this.tr("device")}</b><span>${this.escapeHtml(deviceIdentifier)}</span></p>
          <p><b>${this.tr("model")}</b><span>${this.escapeHtml(this.deviceModel)}</span></p>
          <p><b>${this.tr("channels")}</b><span>${this.channels.length}</span></p>
          ${macRow}
          <p><b>${this.tr("status")}</b><span class="ok">${this.tr("online")}</span></p>
          <p><b>${this.language() === "en" ? "15-minute notification" : "15-Minuten-Meldung"}</b><span class="${notificationClass}">${this.escapeHtml(notification.statusText)}</span></p>
          <p><b>${this.tr("fetched_at")}</b><span>${this.escapeHtml(notificationTime)}</span></p>
          <p><b>${this.tr("last_notification")}</b><span><button type="button" class="led-notification-open" data-action="dialog:doser-notification:1" title="${this.tr("details")}" aria-label="${this.tr("details")}"><span aria-hidden="true">&#128065;</span></button></span></p>
        </section>
      </div>`;
  }

  dialog() {
    if (!this.dialogState) return "";
    if (this.dialogState.type === "led-schedule" && typeof this.ledScheduleDialog === "function") return this.ledScheduleDialog();
    if (this.dialogState.type === "test-led-schedule" && typeof this.testLedScheduleDialog === "function") return this.testLedScheduleDialog();
    if (this.dialogState.type === "led-history-all" && typeof this.ledHistoryAllDialog === "function") return this.ledHistoryAllDialog();
    if (this.dialogState.type === "led-history" && typeof this.ledChannelHistoryDialog === "function") return this.ledChannelHistoryDialog();
    if (this.dialogState.type === "led-template-editor" && typeof this.ledTemplateDialog === "function") return this.ledTemplateDialog();
    if (this.dialogState.type === "led-auto-mode-editor" && typeof this.ledAutoModeDialog === "function") return this.ledAutoModeDialog();
    const ch = this.channels.find((item) => item.id === this.dialogState.channel) || this.channels[0];
    const e = this.entities(ch.id);
    if (this.dialogState.type === "schedule") return this.scheduleDialog(ch, e);
    if (this.dialogState.type === "container") return this.containerDialog(ch, e);
    if (this.dialogState.type === "manual") return this.manualDialog(ch, e);
    if (this.dialogState.type === "safety") return this.safetyDialog();
    if (this.dialogState.type === "auto-fill") return this.autoFillDialog();
    if (this.dialogState.type === "calibration") return this.calibrationDialog(ch);
    if (this.dialogState.type === "history") return this.historyDialog(ch, e);
    if (this.dialogState.type === "history-all") return this.historyAllDialog();
    if (this.dialogState.type === "doser-notification") return this.doserNotificationDialog();
    if (this.dialogState.type === "debug") return this.debugDialog(ch);
    return "";
  }

  channelOptions(selected) {
    return this.channels.map((ch) =>
      `<option value="${ch.id}" ${ch.id === selected ? "selected" : ""}>CH${ch.id} ${ch.name}</option>`
    ).join("");
  }

  scheduleDialog(ch, e) {
    const snapshot = this.dialogState && this.dialogState.scheduleSnapshot
      && Number(this.dialogState.channel) === Number(ch.id)
      ? this.dialogState.scheduleSnapshot
      : null;
    const requestSuccess = this.dialogState && this.dialogState.scheduleRequestSuccess
      && Number(this.dialogState.channel) === Number(ch.id)
      ? this.dialogState.scheduleRequestSuccess
      : null;
    const scheduleKind = snapshot && snapshot.kind ? snapshot.kind : this.scheduleKindFromId(e.scheduleTimeSensor);
    const scheduleState = this.rawState(e.scheduleTimeSensor, "");
    const stateIntervalMatch = String(scheduleState).match(/^(?:\d{1,2}:)?(\d{1,2})(?:\s*min)?$/i);
    const stateInterval = stateIntervalMatch ? Number.parseInt(stateIntervalMatch[1], 10) : Number.NaN;
    const attrInterval = Number.parseInt(this.stateAttr(e.scheduleTimeSensor, "interval_minutes", ""), 10);
    const intervalMinutes = Number.isInteger(stateInterval) && stateInterval >= 0 && stateInterval <= 59
      ? stateInterval
      : (Number.isInteger(attrInterval) && attrInterval >= 0 && attrInterval <= 59 ? attrInterval : 0);
    const storedTime = snapshot && snapshot.time ? snapshot.time : this.rawState(e.scheduleTimeSensor, "00:00");
    const time = scheduleKind === "interval"
      ? (snapshot && Number.isInteger(snapshot.interval) ? snapshot.interval : intervalMinutes)
      : storedTime;
    const timeInputType = scheduleKind === "interval" ? "number" : "time";
    const timeInputLimits = scheduleKind === "interval" ? ' min="0" max="59" step="1"' : "";
    const timeLabel = scheduleKind === "interval" ? this.tr("interval_minutes") : this.tr("time");
    const ml = snapshot && Number.isFinite(Number(snapshot.ml))
      ? Number(snapshot.ml).toFixed(1)
      : this.numericState(e.scheduleDoseSensor, "2.0");
    const scheduleEntity = e.scheduleTimeSensor && this._hass && this._hass.states
      ? this._hass.states[e.scheduleTimeSensor]
      : null;
    const scheduleAmountEntity = e.scheduleDoseSensor && this._hass && this._hass.states
      ? this._hass.states[e.scheduleDoseSensor]
      : null;
    const normalizeTimerEntries = (entity) => {
      let rawEntries = entity && entity.attributes ? entity.attributes.timer_entries : [];
      if (typeof rawEntries === "string") {
        try {
          rawEntries = JSON.parse(rawEntries);
        } catch (_error) {
          rawEntries = [];
        }
      }
      if (!Array.isArray(rawEntries) && rawEntries && typeof rawEntries === "object") {
        rawEntries = Object.values(rawEntries);
      }
      if (!Array.isArray(rawEntries)) return [];
      return rawEntries.map((entry) => {
        if (!entry || typeof entry !== "object") return null;
        const hour = Number.parseInt(entry.hour, 10);
        const minute = Number.parseInt(entry.minute, 10);
        const fallbackTime = Number.isInteger(hour) && Number.isInteger(minute)
          ? `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`
          : "";
        return { time: String(entry.time || fallbackTime), ml: Number(entry.ml) };
      }).filter((entry) => entry && /^\d{2}:\d{2}$/.test(entry.time) && Number.isFinite(entry.ml));
    };
    const normalizeWindowEntries = (entity) => {
      let rawEntries = entity && entity.attributes ? entity.attributes.window_entries : [];
      if (typeof rawEntries === "string") {
        try {
          rawEntries = JSON.parse(rawEntries);
        } catch (_error) {
          rawEntries = [];
        }
      }
      if (!Array.isArray(rawEntries) && rawEntries && typeof rawEntries === "object") rawEntries = Object.values(rawEntries);
      if (!Array.isArray(rawEntries)) return [];
      return rawEntries.map((entry) => ({
        start: String(entry && entry.start || ""),
        end: String(entry && entry.end || ""),
        doses: Number(entry && entry.doses),
      })).filter((entry) => /^\d{2}:\d{2}$/.test(entry.start)
        && /^\d{2}:\d{2}$/.test(entry.end) && Number.isInteger(entry.doses));
    };
    const entityPrefix = this.entityPrefix();
    const channelMarker = `_ch${Number(ch.id)}_`;
    const discoveredTimerEntities = this._hass && this._hass.states
      ? Object.entries(this._hass.states)
        .filter(([entityId, entity]) => {
          const objectId = String(entityId || "").toLowerCase();
          const attributes = entity && entity.attributes ? entity.attributes : {};
          const friendlyName = String(attributes.friendly_name || "").toLowerCase();
          const friendlyChannel = new RegExp(`(^|\\s)ch${Number(ch.id)}(\\s|$)`).test(friendlyName);
          return objectId.startsWith("sensor.")
            && (objectId.includes(channelMarker) || friendlyChannel)
            && (attributes.timer_entries || attributes.window_entries);
        })
        .sort(([leftId], [rightId]) => {
          const leftMatchesDevice = String(leftId).toLowerCase().startsWith(`sensor.${entityPrefix}_`) ? 1 : 0;
          const rightMatchesDevice = String(rightId).toLowerCase().startsWith(`sensor.${entityPrefix}_`) ? 1 : 0;
          return rightMatchesDevice - leftMatchesDevice;
        })
        .map(([_entityId, entity]) => entity)
      : [];
    const cachedDialogState = this.doserScheduleDialogState
      && Number(this.doserScheduleDialogState.channel) === Number(ch.id)
      ? this.doserScheduleDialogState
      : null;
    const cachedDialogEntities = cachedDialogState && Array.isArray(cachedDialogState.entities)
      ? cachedDialogState.entities
      : [];
    const cachedTimerEntries = cachedDialogState && Array.isArray(cachedDialogState.entries)
      ? cachedDialogState.entries
      : [];
    const cachedWindowEntries = cachedDialogState && Array.isArray(cachedDialogState.windows)
      ? cachedDialogState.windows
      : [];
    const timerEntryEntities = [
      ...cachedDialogEntities,
      scheduleEntity,
      scheduleAmountEntity,
      ...discoveredTimerEntities,
    ].filter(Boolean);
    const snapshotTimerEntries = snapshot && Array.isArray(snapshot.timers) ? snapshot.timers : [];
    const snapshotWindowEntries = snapshot && Array.isArray(snapshot.windows) ? snapshot.windows : [];
    const storedTimerEntries = snapshotTimerEntries.length
      ? snapshotTimerEntries
      : (cachedTimerEntries.length
      ? cachedTimerEntries
      : (timerEntryEntities
        .map((entity) => normalizeTimerEntries(entity))
        .find((entries) => entries.length) || []));
    const storedWindowEntries = snapshotWindowEntries.length
      ? snapshotWindowEntries
      : (cachedWindowEntries.length
      ? cachedWindowEntries
      : (timerEntryEntities
        .map((entity) => normalizeWindowEntries(entity))
        .find((entries) => entries.length) || []));
    const storedWeekdays = snapshot && Array.isArray(snapshot.weekdays)
      ? snapshot.weekdays
      : (scheduleEntity && Array.isArray(scheduleEntity.attributes.weekdays)
      ? scheduleEntity.attributes.weekdays.map((day) => String(day).toLowerCase())
      : ["everyday"]);
    const everydaySelected = !storedWeekdays.length || storedWeekdays.includes("everyday");
    const weekdayOptions = [
      ["monday", "Mo"], ["tuesday", "Di"], ["wednesday", "Mi"], ["thursday", "Do"],
      ["friday", "Fr"], ["saturday", "Sa"], ["sunday", "So"],
    ];
    const timerEntries = storedTimerEntries.length
      ? storedTimerEntries
      : (scheduleKind === "timer"
        ? []
        : [{ time: /^\d{2}:\d{2}$/.test(String(time)) ? String(time) : "00:00", ml: Number(ml) || 1.0 }]);
    const windowEntries = storedWindowEntries.length
      ? storedWindowEntries
      : [{ start: "00:00", end: "00:30", doses: 1 }];
    const autoLocked = this.autoLimitReached(e);
    const pendingSend = this.scheduleHasPendingSend(ch.id);
    const editMode = Boolean(this.dialogState && this.dialogState.scheduleEditMode);
    const scheduleActive = snapshot && typeof snapshot.active === "boolean" ? snapshot.active : this.isOn(e.active);
    const validFromTomorrow = snapshot && typeof snapshot.validFromTomorrow === "boolean"
      ? snapshot.validFromTomorrow
      : autoLocked;
    const kindLabels = {
      single_dose: this.tr("single_dose"),
      interval: this.tr("interval"),
      timer: this.tr("timer_list"),
      window: this.tr("custom_schedule"),
    };
    const overviewRows = scheduleKind === "timer"
      ? timerEntries.map((entry, index) => `<div class="doser-schedule-overview-row"><b>${index + 1}</b><span>${this.escapeHtml(entry.time)}</span><strong>${Number(entry.ml).toFixed(1)} mL</strong></div>`).join("")
      : (scheduleKind === "window"
        ? windowEntries.map((entry, index) => `<div class="doser-schedule-overview-row"><b>${index + 1}</b><span>${this.escapeHtml(entry.start)}–${this.escapeHtml(entry.end)}</span><strong>${Number(entry.doses)} ${this.tr("single_dose")}</strong></div>`).join("")
        : `<div class="doser-schedule-overview-row"><b>1</b><span>${scheduleKind === "interval" ? `${Number(time)} min` : this.escapeHtml(time)}</span><strong>${Number(ml).toFixed(1)} mL</strong></div>`);
    const kindOption = (value, label) =>
      `<option value="${value}" ${scheduleKind === value ? "selected" : ""}>${label}</option>`;
    return this.sharedModalDialog({
      title: this.tr("schedule_edit"),
      sectionClass: "modal card doser-schedule-modal",
      headerHtml: `
        <header class="led-channel-history-head">
          <h2>${this.tr("schedule_edit")}</h2>
          <button type="button" class="led-channel-history-close" data-action="close-dialog" title="${this.tr("close")}" aria-label="${this.tr("close")}"><span aria-hidden="true">&#10005;</span></button>
        </header>`,
      bodyHtml: `
        <form data-dialog-form="schedule">
          <div class="doser-schedule-unsent-warning" data-schedule-unsent-warning role="alert" aria-live="polite" ${pendingSend ? "" : "hidden"}>
            <ha-icon icon="mdi:alert-circle-outline"></ha-icon>
            <strong>${this.language() === "en" ? "Changes have not yet been sent to the device." : "Änderung noch nicht an das Gerät gesendet."}</strong>
          </div>
          <div class="doser-schedule-request-status ${requestSuccess ? "is-ok" : ""}" data-schedule-request-status role="status" aria-live="polite" ${requestSuccess ? "" : "hidden"}>
            <ha-icon icon="${requestSuccess ? "mdi:check-circle-outline" : "mdi:sync"}"></ha-icon><div><strong>${requestSuccess ? this.escapeHtml(requestSuccess.message) : ""}</strong><small ${requestSuccess && requestSuccess.detail ? "" : "hidden"}>${requestSuccess ? this.escapeHtml(requestSuccess.detail || "") : ""}</small></div>
          </div>
          <section class="doser-schedule-overview" ${editMode ? "hidden" : ""}>
            <div class="doser-schedule-overview-head">
              <div><strong>${this.language() === "en" ? "Schedule overview" : "Zeitplanübersicht"}</strong><small>CH${ch.id} ${this.escapeHtml(ch.name)} · ${this.escapeHtml(kindLabels[scheduleKind] || scheduleKind)}</small></div>
              <button type="button" class="secondary icon" data-action="schedule-edit:${ch.id}" title="${this.tr("edit")}" aria-label="${this.tr("edit")}"><ha-icon icon="mdi:pencil"></ha-icon></button>
            </div>
            <div class="doser-schedule-overview-meta">
              <span>${this.tr("status")}<strong>${scheduleActive ? this.tr("active") : this.tr("inactive")}</strong></span>
              <span>${scheduleKind === "window" ? this.tr("window_daily_amount") : this.tr("amount")}<strong>${Number(ml).toFixed(1)} mL</strong></span>
              <span>${this.tr("weekdays")}<strong>${everydaySelected ? this.tr("every_day") : storedWeekdays.join(", ")}</strong></span>
            </div>
            <div class="doser-schedule-overview-list">${overviewRows}</div>
            ${snapshot && snapshot.debugOutput ? `<details class="doser-schedule-debug-result"><summary>${this.tr("debug_output")}</summary><pre>${this.escapeHtml(snapshot.debugOutput)}</pre></details>` : ""}
          </section>
          <div class="doser-schedule-scroll" ${editMode ? "" : "hidden"}>
          <label class="doser-schedule-inline">${this.tr("channel")}<select name="channel" data-dialog-channel-select="schedule">${this.channelOptions(ch.id)}</select></label>
          <label class="doser-schedule-inline">${this.tr("mode")}<select name="kind" data-schedule-kind>${kindOption("single_dose", this.tr("single_dose"))}${kindOption("interval", this.tr("interval"))}${kindOption("timer", this.tr("timer_list"))}${kindOption("window", this.tr("custom_schedule"))}</select></label>
          <label class="check doser-schedule-inline"><span>${this.tr("active")}</span><input type="checkbox" name="active" ${autoLocked || scheduleActive ? "checked" : ""} ${autoLocked ? "disabled" : ""}></label>
          <label class="check doser-schedule-inline ${autoLocked ? "auto-locked-check" : ""}"><span>${this.tr("valid_from_tomorrow")}</span><input type="checkbox" name="valid_from_tomorrow" ${validFromTomorrow ? "checked" : ""} ${autoLocked ? "disabled" : ""}>${autoLocked ? `<small class="input-hint">${this.tr("auto_limit_reached_note")}</small>` : ""}</label>
          <label class="check doser-schedule-inline"><span>${this.tr("debug_output_short")}</span><input type="checkbox" name="debug"></label>
          <label data-schedule-time-field><span data-schedule-time-label>${timeLabel}</span><input name="time" type="${timeInputType}" value="${time}"${timeInputLimits} data-schedule-time><small class="input-hint-red" data-schedule-time-warning hidden></small></label>
          <label class="doser-schedule-inline" data-schedule-amount-field><span data-schedule-amount-label>${scheduleKind === "window" ? this.tr("window_daily_amount") : this.tr("amount")}</span><input name="ml" type="number" min="${scheduleKind === "interval" ? "5.0" : "0.2"}" max="999.9" step="0.1" value="${ml}" data-schedule-ml><small class="input-hint-red" data-schedule-ml-hint ${scheduleKind === "interval" ? "" : "hidden"}>Minimum 5,0 mL</small></label>
          <section class="doser-timer-list" data-schedule-timer-list ${scheduleKind === "timer" ? "" : "hidden"}>
            <div class="doser-timer-list-head"><strong>${this.tr("timer_list")}</strong><small>${this.tr("timer_hint")}</small></div>
            <div class="doser-timer-rows" data-schedule-timer-rows>${timerEntries.map((entry, index) => this.timerEntryRow(entry, index)).join("")}</div>
            <button type="button" class="secondary" data-schedule-timer-add>${this.tr("timer_add")}</button>
          </section>
          <section class="doser-window-list" data-schedule-window-list ${scheduleKind === "window" ? "" : "hidden"}>
            <div class="doser-timer-list-head"><strong>${this.tr("custom_schedule")}</strong><small>${this.tr("window_hint")}</small></div>
            <div class="doser-window-total">${this.tr("window_total_doses")}: <strong data-schedule-window-total>0 / 24</strong></div>
            <div class="doser-window-rows" data-schedule-window-rows>${windowEntries.map((entry, index) => this.windowEntryRow(entry, index)).join("")}</div>
            <button type="button" class="secondary" data-schedule-window-add>${this.tr("window_add")}</button>
          </section>
          <section class="doser-weekday-picker">
            <div class="doser-weekday-head"><strong>${this.tr("weekdays")}</strong><label class="check"><span>${this.tr("every_day")}</span><input type="checkbox" data-schedule-everyday ${everydaySelected ? "checked" : ""}></label></div>
            <div class="doser-weekday-buttons">${weekdayOptions.map(([day, label]) => `<button type="button" class="${!everydaySelected && storedWeekdays.includes(day) ? "active" : ""}" data-schedule-weekday="${day}" ${everydaySelected ? "disabled" : ""}>${label}</button>`).join("")}</div>
            <input type="hidden" name="weekdays" value="${everydaySelected ? "everyday" : storedWeekdays.join(",")}" data-schedule-weekdays>
          </section>
          </div>
          <footer class="led-schedule-dialog-footer doser-schedule-dialog-footer">
            <button type="button" class="secondary danger" data-action="dialog:reset-schedule:${ch.id}"><ha-icon icon="mdi:calendar-remove"></ha-icon><span>${this.tr("delete_send")}</span></button>
            <div class="led-schedule-dialog-actions">
              <button type="button" class="secondary" data-action="close-dialog"><ha-icon icon="mdi:close"></ha-icon><span>${this.tr("cancel")}</span></button>
              ${editMode ? `<button type="button" class="secondary" data-action="schedule-overview:${ch.id}"><ha-icon icon="mdi:arrow-left"></ha-icon><span>${this.language() === "en" ? "Overview" : "Übersicht"}</span></button>
              <button type="submit" class="secondary" data-schedule-send="false"><ha-icon icon="mdi:content-save-outline"></ha-icon><span>${this.tr("save")}</span></button>` : `<button type="button" class="secondary" data-action="schedule-edit:${ch.id}"><ha-icon icon="mdi:pencil"></ha-icon><span>${this.tr("edit")}</span></button>`}
              <button type="submit" class="primary" data-schedule-send="true"><ha-icon icon="mdi:calendar-check"></ha-icon><span>${pendingSend && !editMode ? (this.language() === "en" ? "Send to device" : "An Gerät senden") : this.tr("save_send")}</span></button>
            </div>
          </footer>
        </form>`,
    });
  }

  containerDialog(ch, e) {
    return this.sharedModalDialog({
      title: this.tr("container_edit"),
      bodyHtml: `
        <form data-dialog-form="container">
          <label>${this.tr("channel")}<select name="channel">${this.channelOptions(ch.id)}</select></label>
          <label>${this.tr("container_volume")}<input name="ml" type="number" min="0" max="9999" step="0.1" value="${this.numericState(e.remainingSensor, "0.0")}"></label>
          <div class="modal-actions">
            ${this.sharedDialogActions([
              { action: "close-dialog", label: this.tr("cancel"), className: "link", type: "button" },
              { label: this.tr("save"), className: "primary", type: "submit" },
            ])}
          </div>
        </form>`,
    });
  }

  autoFillDialog() {
    const settings = this.lowContainerPushSettings();
    const targets = [settings.targets[0] || "", settings.targets[1] || "", settings.targets[2] || ""];
    return this.sharedModalDialog({
      title: this.tr("auto_fill_edit"),
      bodyHtml: `
        <form data-dialog-form="auto-fill">
          <label class="check"><input type="checkbox" name="enabled" ${settings.enabled ? "checked" : ""}> ${this.tr("low_container_push")}</label>
          <label>${this.tr("push_message")}<textarea name="message" rows="3">${this.escapeHtml(settings.message)}</textarea><small class="input-hint">${this.tr("push_message_hint")}</small></label>
          <label>${this.tr("push_target_1")}<select name="target">${this.notifyOptions(targets[0])}</select></label>
          <label>${this.tr("push_target_2")}<select name="target">${this.notifyOptions(targets[1])}</select></label>
          <label>${this.tr("push_target_3")}<select name="target">${this.notifyOptions(targets[2])}</select></label>
          <div class="modal-actions">
            ${this.sharedDialogActions([
              { action: "close-dialog", label: this.tr("cancel"), className: "link", type: "button" },
              { label: this.tr("save"), className: "primary", type: "submit" },
            ])}
          </div>
        </form>`,
    });
  }

  manualDialog(ch, e) {
    return this.sharedModalDialog({
      title: this.tr("manual_dose"),
      bodyHtml: `
        <form data-dialog-form="manual">
          <label>${this.tr("channel")}<select name="channel">${this.channelOptions(ch.id)}</select></label>
          <label>${this.tr("amount")}<input name="ml" type="number" min="0.2" max="999.9" step="0.1" value="${this.numericState(e.manual)}"></label>
          <label class="check"><input type="checkbox" name="dose_now"> ${this.tr("dose_now")}</label>
          <div class="modal-actions">
            ${this.sharedDialogActions([
              { action: "close-dialog", label: this.tr("cancel"), className: "link", type: "button" },
              { label: this.tr("save"), className: "primary", type: "submit" },
            ])}
          </div>
        </form>`,
    });
  }

  safetyDialog() {
    const safety = this.doserSafetySettings();
    return this.sharedModalDialog({
      title: this.tr("safety_edit"),
      bodyHtml: `
        <form data-dialog-form="safety">
          <label>${this.tr("max_auto_ml")}<input name="max_auto_ml" type="number" min="0.2" max="999.9" step="0.1" value="${safety.maxAutoMl.toFixed(1)}"></label>
          <label>${this.tr("max_manual_ml")}<input name="max_manual_ml" type="number" min="0" max="999.9" step="0.1" value="${safety.maxManualMl.toFixed(1)}"><small class="input-hint">${this.tr("manual_limit_note")}</small></label>
          <label>${this.tr("max_daily_ml")}<input name="max_daily_ml" type="number" min="0.2" max="9999.9" step="0.1" value="${safety.maxDailyMl.toFixed(1)}"></label>
          <div class="modal-actions">
            ${this.sharedDialogActions([
              { action: "close-dialog", label: this.tr("cancel"), className: "link", type: "button" },
              { label: this.tr("save"), className: "primary", type: "submit" },
            ])}
          </div>
        </form>`,
    });
  }

  calibrationIllustration(kind) {
    if (kind === "done") {
      return `<div class="calibration-illustration"><svg viewBox="0 0 220 138" aria-hidden="true">
        <circle cx="110" cy="62" r="43" fill="none" stroke="currentColor" stroke-width="7"/>
        <path class="accent" d="M87 62l16 16 32-36" fill="none" stroke="currentColor" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M74 119h72" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>
      </svg></div>`;
    }
    const dry = kind === "dry";
    const liquidY = kind === "test" ? 72 : kind === "exact" ? 82 : 91;
    const pump = kind === "hose" || kind === "measure";
    return `<div class="calibration-illustration"><svg viewBox="0 0 220 138" aria-hidden="true">
      ${pump ? `<rect x="24" y="20" width="58" height="45" rx="10" fill="none" stroke="currentColor" stroke-width="6"/><circle class="accent" cx="53" cy="42" r="6" fill="currentColor"/><path d="M53 65v18c0 8 8 8 16 8h24" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>` : ""}
      <path d="M105 26h42l-10 16v68l21 13H94l21-13V42z" fill="none" stroke="currentColor" stroke-width="6" stroke-linejoin="round"/>
      ${dry ? "" : `<path class="accent" d="M114 ${liquidY}h24v28l12 8h-48l12-8z" fill="currentColor" opacity=".58"/><path class="accent" d="M112 ${liquidY}h28" stroke="currentColor" stroke-width="3"/>`}
      <path d="M123 52h15m-15 11h15m-15 11h15m-15 11h15" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
      ${kind === "hose" ? `<path class="accent" d="M93 91c0 8-12 8-12 0 0-4 6-11 6-11s6 7 6 11z" fill="currentColor"/>` : ""}
      ${kind === "exact" || kind === "test" ? `<path class="accent" d="M164 ${liquidY}h30m-8-8 8 8-8 8" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>` : ""}
      ${dry ? `<path class="accent" d="M171 34v18m-9-9h18m-14-13 10 10m0-10-10 10" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>` : ""}
    </svg></div>`;
  }

  calibrationDialog(ch) {
    const step = Number(this.dialogState && this.dialogState.step ? this.dialogState.step : 1);
    const e = this.entities(ch.id);
    const calibrationOutput = String((this.dialogState && this.dialogState.calibrationOutput) || "");
    const measured = this.stateAttr(e.calibrationSensor, "measured_ml", "");
    const calibratedAt = this.stateAttr(e.calibrationSensor, "calibrated_at", "");
    const reminderAt = this.stateAttr(e.calibrationSensor, "reminder_at", "");
    const latestCalibration = calibratedAt
      ? `${this.tr("calibration_last")}: ${calibratedAt}${measured ? ` · ${measured} mL` : ""}${reminderAt ? ` · ${this.tr("calibration_reminder_at")}: ${reminderAt}` : ""}`
      : `${this.tr("calibration_last")}: ${this.tr("calibration_not_recorded")}`;
    const debugHtml = calibrationOutput
      ? `<pre class="debug-output calibration-debug-output">${this.escapeHtml(calibrationOutput)}</pre>`
      : "";
    if (step <= 1) {
      return `
        <div class="modal-backdrop">
          <section class="modal card calibration-modal">
            <h2>${this.tr("calibrate")} · CH${ch.id} ${ch.name}</h2>
            <div class="calibration-steps">
              <div class="step active-step">
                <b>${this.tr("step_label")} 1</b>
                <span>${this.tr("prepare_text")}</span>
                ${this.calibrationIllustration("hose")}
                <label>${this.tr("fill_duration")}<input type="number" min="0.5" max="30" step="0.5" value="3.0" data-calibration-prime-duration></label>
                <button type="button" class="secondary" data-action="calibration-prime:${ch.id}">
                  <ha-icon icon="mdi:water-pump"></ha-icon>
                  ${this.tr("hose_fill")}
                </button>
                <small class="input-hint">${this.tr("hose_fill_hint")}</small>
                <span>${this.escapeHtml(latestCalibration)}</span>
              </div>
            </div>
            ${debugHtml}
            <div class="modal-actions sticky-actions">
              <button type="button" class="link" data-action="close-dialog">${this.tr("cancel")}</button>
              <button type="button" class="secondary" data-action="calibration-open-measure:${ch.id}">
                <ha-icon icon="mdi:arrow-right-circle"></ha-icon>
                ${this.tr("next")}
              </button>
            </div>
          </section>
        </div>`;
    }
    if (step === 2) {
      return `
        <div class="modal-backdrop">
          <section class="modal card calibration-modal">
            <h2>${this.tr("calibrate")} · CH${ch.id} ${ch.name}</h2>
            <div class="calibration-steps">
              <div class="step active-step">
                <b>${this.tr("step_label")} 2</b>
                <span>${this.tr("measure_prepare_text")}</span>
                ${this.calibrationIllustration("measure")}
                <button type="button" class="secondary" data-action="calibration-start-next:${ch.id}">
                  <ha-icon icon="mdi:cup-water"></ha-icon>
                  ${this.tr("start_measure")}
                </button>
                <small class="input-hint">${this.tr("start_measure_hint")}</small>
                <span>${this.escapeHtml(latestCalibration)}</span>
              </div>
            </div>
            ${debugHtml}
            <div class="modal-actions sticky-actions">
              <button type="button" class="link" data-action="close-dialog">${this.tr("cancel")}</button>
            </div>
          </section>
        </div>`;
    }
    if (step === 4) {
      return `
        <div class="modal-backdrop">
          <section class="modal card calibration-modal">
            <h2>${this.tr("calibrate")} · CH${ch.id} ${ch.name}</h2>
            <div class="calibration-steps">
              <div class="step active-step">
                <b>${this.tr("step_label")} 4</b>
                <span>${this.tr("calibration_test_prepare")}</span>
                ${this.calibrationIllustration("dry")}
                <button type="button" class="primary" data-action="calibration-test:${ch.id}">
                  <ha-icon icon="mdi:cup-water"></ha-icon>
                  ${this.tr("calibration_test_dose")}
                </button>
              </div>
            </div>
            ${debugHtml}
            <div class="modal-actions sticky-actions">
              <button type="button" class="link" data-action="close-dialog">${this.tr("cancel")}</button>
            </div>
          </section>
        </div>`;
    }
    if (step === 5) {
      return `
        <div class="modal-backdrop">
          <section class="modal card calibration-modal">
            <h2>${this.tr("calibrate")} · CH${ch.id} ${ch.name}</h2>
            <div class="calibration-steps">
              <div class="step active-step">
                <b>${this.tr("step_label")} 5</b>
                <span>${this.tr("calibration_test_question")}</span>
                ${this.calibrationIllustration("test")}
                <button type="button" class="primary" data-action="calibration-test-yes:${ch.id}">${this.tr("calibration_test_yes")}</button>
                <button type="button" class="secondary" data-action="calibration-test-retry:${ch.id}">${this.tr("calibration_test_retry")}</button>
              </div>
            </div>
            ${debugHtml}
          </section>
        </div>`;
    }
    if (step >= 6) {
      const summaryMeasured = Number(this.dialogState && this.dialogState.measuredMl);
      const measuredText = Number.isFinite(summaryMeasured)
        ? `${summaryMeasured.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} mL`
        : `${measured || "–"} mL`;
      const calibratedText = (this.dialogState && this.dialogState.calibratedDisplay) || calibratedAt || new Date().toLocaleString();
      const reminderText = (this.dialogState && this.dialogState.reminderDisplay) || reminderAt || new Date(Date.now() + 30 * 86400000).toLocaleDateString();
      return `
        <div class="modal-backdrop">
          <section class="modal card calibration-modal">
            <h2>${this.tr("calibration_completed")} · CH${ch.id} ${ch.name}</h2>
            <div class="calibration-steps">
              <div class="step active-step">
                <b>${this.tr("step_label")} 6</b>
                ${this.calibrationIllustration("done")}
                <div class="calibration-summary">
                  <div><span>${this.tr("calibration_summary_measured")}</span><strong>${this.escapeHtml(measuredText)}</strong></div>
                  <div><span>${this.tr("calibration_summary_test")}</span><strong>4,00 mL</strong></div>
                  <div><span>${this.tr("calibration_summary_date")}</span><strong>${this.escapeHtml(calibratedText)}</strong></div>
                  <div><span>${this.tr("calibration_summary_reminder")}</span><strong>${this.escapeHtml(reminderText)}</strong></div>
                </div>
              </div>
            </div>
            <div class="modal-actions sticky-actions">
              <button type="button" class="primary" data-action="close-dialog">${this.tr("close")}</button>
            </div>
          </section>
        </div>`;
    }
    return `
      <div class="modal-backdrop">
        <section class="modal card calibration-modal">
          <h2>${this.tr("calibrate")} · CH${ch.id} ${ch.name}</h2>
          <form data-dialog-form="calibration">
            <div class="calibration-steps">
              <div class="step active-step">
                <b>${this.tr("step_label")} 3 · ${this.tr("measured_save")}</b>
                <span>${this.tr("measure_exact_hint")}</span>
                ${this.calibrationIllustration("exact")}
                <label>${this.tr("measured_amount")}<input name="measured_ml" type="number" min="0.2" max="255.95" step="0.05" placeholder="z.B. 3,50"></label>
              </div>
            </div>
            ${debugHtml}
            <div class="modal-actions sticky-actions">
              <button type="button" class="link" data-action="close-dialog">${this.tr("cancel")}</button>
              <button type="submit" class="primary">${this.tr("next")}</button>
            </div>
          </form>
        </section>
      </div>`;
  }

  debugDialog(ch) {
    const suffix = this.dialogState && this.dialogState.noChannel ? "" : ` · CH${ch.id} ${ch.name}`;
    return this.sharedDebugDialog({
      title: `${this.dialogState && this.dialogState.debug ? this.tr("debug_output") : this.tr("result_output")}${suffix}`,
      output: this.dialogState && this.dialogState.output ? this.dialogState.output : "",
      debug: Boolean(this.dialogState && this.dialogState.debug),
      level: this.dialogState && this.dialogState.level ? this.dialogState.level : "",
    });
  }

  historyDialog(ch, e) {
    const bodyHtml = `
      <div class="dialog-history">
        ${this.row("mdi:calendar-check", this.tr("active"), this.isOn(e.active) ? this.tr("on") : this.tr("off"), `more:${e.active}`)}
        ${this.row("mdi:eye", this.tr("today_total"), this.stateFallback(e.daily, "", "0.0 mL"), `more:${e.daily}`)}
        ${this.row("mdi:calendar-sync", this.tr("auto_today"), this.stateFallback(e.autoDaily, e.daily), `more:${e.autoDaily}`)}
        ${this.row("mdi:hand-water", this.tr("manual_today"), this.stateFallback(e.manualDaily, "", "0.0 mL"), `more:${e.manualDaily}`)}
        ${this.row("mdi:bottle-tonic-outline", this.tr("container_volume"), this.state(e.remainingSensor), `more:${e.remainingSensor}`)}
        ${this.row("mdi:clock-outline", this.tr("next_time"), this.state(e.scheduleTimeSensor), `more:${e.scheduleTimeSensor}`)}
        ${this.row("mdi:cup-water", this.tr("planned_amount"), this.state(e.scheduleDoseSensor), `more:${e.scheduleDoseSensor}`)}
      </div>`;
    const entries = this.historyEntries(120)
      .filter((entry) => Number(entry.pump || 0) === Number(ch.id))
      .map((entry) => ({
        ...entry,
        title: this.historyTitleText(entry, `CH${ch.id} ${ch.name}`),
        detail: [this.historyParamsText(entry), this.historyDetailText(entry.detail || "")].filter(Boolean).join(" · "),
        timestamp: String(entry.ts || `${entry.date || ""} ${entry.time || ""}`).trim(),
        color: ch.color || "#3d82b8",
      }));
    return this.sharedHistoryDialog({
      title: `${this.tr("history")} · CH${ch.id} ${ch.name}`,
      bodyHtml,
      entries: entries.map((entry) => this.normalizeHistoryEntry(entry)),
      emptyLabel: this.tr("no_history"),
      color: ch.color || "#3d82b8",
    });
  }

  historyAllDialog() {
    const entries = this.historyEntries(500);
    return this.sharedHistoryDialog({
      title: this.tr("history_total"),
      entries: entries.map((entry) => {
        const pump = Number(entry.pump || 0);
        const ch = this.channels.find((item) => item.id === pump);
        const color = ch ? ch.color : "#3d82b8";
        const channel = ch ? `CH${ch.id} ${ch.name}` : this.tr("doser");
        return this.normalizeHistoryEntry(entry, {
          title: this.historyTitleText(entry, ch ? channel : ""),
          detailParts: [channel, this.historyParamsText(entry), this.historyDetailText(entry.detail || "")],
          color,
          actionTarget: pump ? `dialog:history:${pump}` : `more:${this.historyEntity()}`,
        });
      }),
      emptyLabel: this.tr("no_history"),
      emptyAction: `more:${this.historyEntity()}`,
      color: "#3d82b8",
    });
  }


}

window.ChihirosPlugins.doser = {
  id: "doser",
  title: "Doser",
  tabs: ["doser"],
  version: "0.1.17",
  attach(card) {
    const helper = new DoserPluginHelpers();
    const coreOwnedMethods = new Set(["dialog", "openDialog", "closeDialog"]);
    for (const name of Object.getOwnPropertyNames(DoserPluginHelpers.prototype)) {
      if (name === "constructor") continue;
      if (coreOwnedMethods.has(name)) continue;
      const value = helper[name];
      if (typeof value === "function") card[name] = value.bind(card);
    }
    card.__doser_helpers_attached = true;
    const defaultChannels = (card.config && Array.isArray(card.config.channels) && card.config.channels.length)
      ? card.config.channels
      : [
      { id: 1, name: "Nitrat", color: "#2ea8ff" },
      { id: 2, name: "Phosphat", color: "#39d353" },
      { id: 3, name: "Eisen", color: "#ff9300" },
      { id: 4, name: "Kalium", color: "#a855f7" },
      ];
    card.baseChannels = defaultChannels;
    card.channels = Array.isArray(card.channels) && card.channels.length ? card.channels : defaultChannels;
    card.doserDevices = typeof card.resolveDoserDevices === "function" ? card.resolveDoserDevices(defaultChannels) : [];
    const selectedExists = card.doserDevices.some((device) => String(device.id) === String(card.activeDoserDeviceId));
    card.activeDoserDeviceId = selectedExists ? card.activeDoserDeviceId : ((card.doserDevices[0] && card.doserDevices[0].id) || "");
    if (typeof card.applyDoserDevice === "function") card.applyDoserDevice(card.activeDoserDeviceId, false);
    return card;
  },

  renderPanel(card) {
    const api = this.attach(card);
    if (!api.doserDevices || !api.doserDevices.length) {
      return `
        <section class="card">
          <h2>${card.escapeHtml(this.title || "Doser")}</h2>
          <div class="empty-note">${card.escapeHtml(card.tr("no_entities"))}</div>
        </section>`;
    }
    const columns = Math.max(1, Math.min(4, api.channels.length || 1));
    return `
        ${api.doserDeviceTabs()}
        <div class="top top-four">
          ${api.autoPanel(true)}
          ${api.manualPanel(true)}
          ${api.dailyPanel(true)}
          ${api.containerPanel(true)}
        </div>
        <section class="card channels-panel">
          <div class="channels channels-${columns}" style="--channel-columns:${columns}">${api.channels.map((ch) => api.channelCard(ch)).join("")}</div>
        </section>
        <div class="middle wide-middle">
          ${api.scheduleTable()}
          ${api.historyPanel()}
        </div>
        ${api.settings()}`;
  },

  canHandleDialog(type) {
    return new Set([
      "schedule",
      "container",
      "manual",
      "safety",
      "auto-fill",
      "calibration",
      "history",
      "history-all",
      "doser-notification",
    ]).has(String(type || ""));
  },

  dialog(card) {
    const api = this.attach(card);
    return DoserPluginHelpers.prototype.dialog.call(api);
  },

  bindEvents(card) {
    const api = this.attach(card);
    if (api.activeTab !== "doser") return;
    card.querySelectorAll("[data-action]").forEach((el) => {
      el.addEventListener("click", async () => {
        const action = el.getAttribute("data-action") || "";
        const [kind, entity, extra] = action.split(":");
        if (kind === "manual-blocked") {
          const channel = Number(entity);
          card.dialogState = {
            type: "debug",
            channel,
            output: `FAIL\nUeberdosierungsschutz\nCH${channel}: ${card.tr("manual_blocked")}`,
            running: false,
            level: "error",
          };
          card.render();
        }
        if (kind === "dose-inline") {
          const channel = Number(entity);
          const channelEntities = card.entities(channel);
          const input = channelEntities && channelEntities.manual
            ? card.querySelector(`[data-number="${channelEntities.manual}"]`)
            : null;
          const ml = Number.parseFloat(input ? input.value : card.numericState(channelEntities.manual));
          const debug = Boolean(card.uiSettings && card.uiSettings.dashboardDebug);
          if (!Number.isFinite(channel) || !Number.isFinite(ml) || ml <= 0) return;
          const result = await card.runDeviceService({
            service: "dose_ml",
            data: { pump: channel, ml },
            title: card.tr("manual_dose"),
            debug,
            dialog: debug,
            channel,
            noChannel: false,
          });
          if (!result || !result.ok) {
            card.dialogState = {
              type: "debug",
              channel,
              output: result && result.output ? result.output : `FAIL\n${card.tr("manual_dose")}`,
              running: false,
              level: "error",
              debug,
            };
            card.render();
            return;
          }
          await card.refreshChannelEntities(channel);
        }
        if (kind === "dialog") {
          if (entity === "schedule") await card.refreshScheduleDialogState(Number(extra));
          card.openDialog(entity, Number(extra));
        }
        if (kind === "schedule-edit" && card.dialogState && card.dialogState.type === "schedule") {
          card.dialogState = { ...card.dialogState, scheduleEditMode: true, scheduleRequestSuccess: null };
          card.render();
        }
        if (kind === "schedule-overview" && card.dialogState && card.dialogState.type === "schedule") {
          card.dialogState = { ...card.dialogState, scheduleEditMode: false };
          card.render();
        }
        if (kind === "calibration-start") {
          const debug = Boolean(card.uiSettings && card.uiSettings.dashboardDebug);
          await card.runDeviceService({
            service: "start_doser_calibration",
            data: { pump: Number(entity) },
            title: card.tr("calibration"),
            debug,
            dialog: true,
            channel: Number(entity),
            noChannel: false,
          });
        }
        if (kind === "calibration-prime") {
          const channel = Number(entity);
          const input = card.querySelector("[data-calibration-prime-duration]");
          const duration = Number.parseFloat(input ? input.value : "3");
          const debug = Boolean(card.uiSettings && card.uiSettings.dashboardDebug);
          const result = await card.runDeviceService({
            service: "prime_doser_calibration",
            data: { pump: channel, duration: Number.isFinite(duration) ? duration : 3 },
            title: card.tr("hose_fill"),
            debug,
            dialog: false,
            channel,
            noChannel: false,
          });
          const rawOutput = result && result.output ? result.output : "FAIL";
          const appConnectionBusy = (!result || !result.ok)
            && /500\s+Internal Server Error|Server got itself in trouble/i.test(rawOutput);
          const calibrationOutput = appConnectionBusy
            ? `FAIL\n${card.tr("hose_fill")}\n\n${card.tr("doser_app_connection_busy")}\n\n${card.tr("debug_output")}:\n${rawOutput}`
            : rawOutput;
          card.dialogState = {
            type: "calibration",
            channel,
            step: 1,
            calibrationOutput: debug || !result || !result.ok ? calibrationOutput : "",
          };
          card.render();
        }
        if (kind === "calibration-open-measure") {
          const channel = Number(entity);
          card.dialogState = {
            ...card.dialogState,
            type: "calibration",
            channel,
            step: 2,
          };
          card.render();
        }
        if (kind === "calibration-start-next") {
          const channel = Number(entity);
          const debug = Boolean(card.uiSettings && card.uiSettings.dashboardDebug);
          const result = await card.runDeviceService({
            service: "start_doser_calibration",
            data: { pump: channel },
            title: card.tr("start_measure"),
            debug,
            dialog: false,
            channel,
            noChannel: false,
          });
          card.dialogState = {
            type: "calibration",
            channel,
            step: result && result.ok ? 3 : 2,
            calibrationOutput: debug || !result || !result.ok ? (result && result.output ? result.output : "FAIL") : "",
          };
          card.render();
        }
        if (kind === "calibration-test") {
          const channel = Number(entity);
          const debug = Boolean(card.uiSettings && card.uiSettings.dashboardDebug);
          const result = await card.runDeviceService({
            service: "test_doser_calibration",
            data: { pump: channel },
            title: card.tr("calibration_test_dose"),
            debug,
            dialog: false,
            channel,
            noChannel: false,
          });
          card.dialogState = {
            ...card.dialogState,
            type: "calibration",
            channel,
            step: result && result.ok ? 5 : 4,
            calibrationOutput: debug || !result || !result.ok ? (result && result.output ? result.output : "FAIL") : "",
          };
          card.render();
        }
        if (kind === "calibration-test-yes") {
          const channel = Number(entity);
          await card.refreshChannelEntities(channel);
          card.dialogState = {
            ...card.dialogState,
            type: "calibration",
            channel,
            step: 6,
          };
          card.render();
        }
        if (kind === "calibration-test-retry") {
          card.dialogState = {
            type: "calibration",
            channel: Number(entity),
            step: 2,
            calibrationOutput: "",
          };
          card.render();
        }
        if (kind === "close-dialog") card.closeDialog();
      });
    });
    card.querySelectorAll("[data-dialog-form]").forEach((form) => {
      const kind = form.querySelector("[data-schedule-kind]");
      if (kind) {
        kind.addEventListener("change", () => {
          card.updateScheduleTimeInput(form);
          card.markScheduleUnsent(form);
        });
        const time = form.querySelector("[data-schedule-time]");
        const amount = form.querySelector("[data-schedule-ml]");
        const weekdays = form.querySelector("[data-schedule-weekdays]");
        const active = form.querySelector('[name="active"]');
        const validFromTomorrow = form.querySelector('[name="valid_from_tomorrow"]');
        if (time) time.addEventListener("input", () => {
          card.updateScheduleTimeWarning(form);
          card.markScheduleUnsent(form);
        });
        if (time) time.addEventListener("change", () => card.updateScheduleTimeWarning(form));
        if (amount) amount.addEventListener("input", () => card.markScheduleUnsent(form));
        if (weekdays) weekdays.addEventListener("change", () => {
          card.updateScheduleTimeWarning(form);
          card.markScheduleUnsent(form);
        });
        if (active) active.addEventListener("change", () => card.markScheduleUnsent(form));
        if (validFromTomorrow) {
          validFromTomorrow.addEventListener("change", () => card.markScheduleUnsent(form));
        }
        card.updateScheduleTimeInput(form);
        card.bindScheduleTimerControls(form);
        card.bindScheduleWindowControls(form);
        card.bindScheduleWeekdayControls(form);
      }
      const channel = form.querySelector("[data-dialog-channel-select]");
      if (channel) {
        channel.addEventListener("change", async () => {
          if (channel.getAttribute("data-dialog-channel-select") === "schedule") {
            await card.refreshScheduleDialogState(Number(channel.value));
          }
          card.openDialog(channel.getAttribute("data-dialog-channel-select"), Number(channel.value));
        });
      }
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const type = form.getAttribute("data-dialog-form");
        if (type === "schedule") await card.saveScheduleDialog(form, ev.submitter?.dataset.scheduleSend !== "false");
        if (type === "container") await card.saveContainerDialog(form);
        if (type === "manual") await card.saveManualDialog(form);
        if (type === "safety") await card.saveSafetyDialog(form);
        if (type === "auto-fill") await card.saveAutoFillDialog(form);
        if (type === "calibration") await card.saveCalibrationDialog(form);
      });
    });
  },
};
