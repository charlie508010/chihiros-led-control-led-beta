window.ChihirosLedPanelMixin = (Base) => class extends Base {
  openDialogState(type, channel = 1, options = {}) {
    const normalizedChannel = Number(channel) || 1;
    const normalizedOptions = options && typeof options === "object" ? options : {};
    if (normalizedOptions.activeTab) {
      this.activeTab = String(normalizedOptions.activeTab);
    }
    this.dialogState = {
      type,
      channel: normalizedChannel,
      ledScheduleNew: Boolean(normalizedOptions.ledScheduleNew),
      ledScheduleEditIndex: Number.isInteger(normalizedOptions.ledScheduleEditIndex)
        ? Number(normalizedOptions.ledScheduleEditIndex)
        : null,
    };
    if (Object.prototype.hasOwnProperty.call(normalizedOptions, "ledScheduleEditorOpen")) {
      this.ledScheduleEditorOpen = Boolean(normalizedOptions.ledScheduleEditorOpen);
    } else if (type === "led-schedule" && Object.prototype.hasOwnProperty.call(this, "ledScheduleEditorOpen")) {
      this.ledScheduleEditorOpen = true;
    } else if (String(type || "").startsWith("led-") && Object.prototype.hasOwnProperty.call(this, "ledScheduleEditorOpen")) {
      this.ledScheduleEditorOpen = false;
    }
    if (type === "led-schedule") {
      this.ledScheduleNewMode = this.dialogState.ledScheduleNew;
      this.ledScheduleEditIndex = this.dialogState.ledScheduleEditIndex;
    }
    this.render();
    if (type === "led-schedule") {
      window.setTimeout(() => {
        const root = this.shadowRoot || this;
        root.querySelector(".led-schedule-dialog-body")?.scrollTo?.(0, 0);
        root.querySelector(".led-schedule-dialog-editor")?.scrollTo?.(0, 0);
        root.querySelector(".led-schedule-modal")?.scrollTo?.(0, 0);
      }, 0);
    }
    return this.dialogState;
  }

  closeDialogState() {
    if (Object.prototype.hasOwnProperty.call(this, "ledScheduleEditorOpen")) {
      this.ledScheduleEditorOpen = false;
    }
    this.ledScheduleNewMode = false;
    this.ledScheduleEditIndex = null;
    this.dialogState = null;
    this.render();
  }

  resolveLedDevices() {
    const configured = Array.isArray(this.config.led_devices) ? this.config.led_devices : null;
    const discovered = this.discoverLedDevices();
    const devices = (configured && configured.length ? configured : discovered)
      .filter((device) => this.isLedDeviceConfig(device));
    const resolved = devices.map((device, index) => ({
      id: String(device.id || `led_${index + 1}`),
      label: String(device.label || device.tab_name || device.name || `${this.tr("device")} ${index + 1}`),
      name: String(device.name || `LED ${index + 1}`),
      address: String(device.address || ""),
      model: String(device.model || "LED"),
      max_brightness: this.resolveLedMaxBrightness(device),
      max_power_watts: this.resolveLedMaxPowerWatts(device),
      power_entity: String(device.power_entity || ""),
      auto_entity: String(device.auto_entity || ""),
      firmware_entity: String(device.firmware_entity || ""),
      runtime_entity: String(device.runtime_entity || String(device.firmware_entity || "").replace(/_firmware_version$/, "_runtime")),
      schedule_entity: String(device.schedule_entity || ""),
      last_notification_entity: String(device.last_notification_entity || ""),
      fan_entity: String(device.fan_entity || ""),
      fan_rpm_entity: String(device.fan_rpm_entity || ""),
      fan_temperature_entity: String(device.fan_temperature_entity || ""),
      has_fan: Boolean(device.has_fan || device.fan_entity || /vivid\s*iii|dyvvd3/i.test(String(device.model || device.name || ""))),
      channels: Array.isArray(device.channels) && device.channels.length ? device.channels.map((channel, chIndex) => ({
        id: Number(channel.id || chIndex + 1),
        name: String(channel.name || `CH${chIndex + 1}`),
        color: String(channel.color || "#2ea8ff"),
        key: String(channel.key || channel.name || `ch${chIndex + 1}`).toLowerCase(),
        value: Number.isFinite(Number(channel.value)) ? Number(channel.value) : 0,
        entity: String(channel.entity || ""),
      })) : [],
    }));
    if (this._hass && this.config.show_fan_demo === true && !resolved.some((device) => this.ledDeviceHasFan(device))) {
      resolved.push({
        id: "facec0000004",
        label: "VIVID III Demo",
        name: "DYVVD3FACEC0000004",
        address: "FA:CE:C0:00:00:04",
        model: "WRGB VIVID III Demo",
        max_brightness: 100,
        max_power_watts: 0,
        power_entity: "",
        auto_entity: "",
        firmware_entity: "",
        runtime_entity: "",
        schedule_entity: "",
        last_notification_entity: "",
        fan_entity: "",
        fan_rpm_entity: "",
        fan_temperature_entity: "",
        has_fan: true,
        fan_demo: true,
        fan_percentage: 30,
        fan_rpm: 600,
        fan_temperature: 25,
        channels: [
          { id: 1, name: "Rot", color: "#ff4d4f", key: "red", value: 30, entity: "" },
          { id: 2, name: "Gruen", color: "#39d353", key: "green", value: 30, entity: "" },
          { id: 3, name: "Blau", color: "#2ea8ff", key: "blue", value: 30, entity: "" },
          { id: 4, name: "Weiss", color: "#f0f6fc", key: "white", value: 30, entity: "" },
        ],
      });
    }
    return resolved;
  }

  discoverLedDevices() {
    if (!this._hass || !this._hass.states) return [];
    const colorMap = [
      ["red", "Rot", "#ff4d4f"],
      ["green", "Gruen", "#39d353"],
      ["blue", "Blau", "#2ea8ff"],
      ["white", "Weiss", "#f0f6fc"],
    ];
    const colorOrder = new Map(colorMap.map(([key], index) => [key, index]));
    const supportedColors = new Set(colorMap.map(([key]) => key));
    const devicePattern = /^(light|switch|sensor|fan)\.([a-z0-9]*[0-9a-f]{12})_(.+)$/;
    const deviceKey = (slug) => {
      const hex = String(slug || "").match(/[0-9a-f]{12}$/i);
      return hex ? hex[0].toLowerCase() : "";
    };
    const deviceAddress = (slug) => {
      const hex = deviceKey(slug);
      return hex ? hex.match(/.{1,2}/g).join(":").toUpperCase() : "";
    };
    const entityColor = (entityId, attrs) => {
      const attrColor = String(attrs.color || "").toLowerCase();
      if (supportedColors.has(attrColor)) return attrColor;
      const match = String(entityId).toLowerCase().match(/^light\.[a-z0-9]*[0-9a-f]{12}_(red|green|blue|white)(?:_\d+)?$/);
      return match ? match[1] : "";
    };
    const groups = new Map();
    Object.entries(this._hass.states).forEach(([entityId, state]) => {
      const match = String(entityId).toLowerCase().match(devicePattern);
      if (!match) return;
      const attrs = state && state.attributes ? state.attributes : {};
      const [, domain, rawDeviceSlug, rawSuffix] = match;
      const deviceSlug = deviceKey(rawDeviceSlug);
      if (!deviceSlug) return;
      const suffix = rawSuffix.replace(/_\d+$/, "");
      if (!groups.has(deviceSlug)) {
        groups.set(deviceSlug, {
          id: deviceSlug,
          label: "LED",
          name: deviceSlug.toUpperCase(),
          address: deviceAddress(deviceSlug),
          model: "LED",
          max_brightness: this.resolveLedMaxBrightness({ id: deviceSlug, name: deviceSlug.toUpperCase(), model: "LED" }),
          max_power_watts: this.resolveLedMaxPowerWatts({
            id: deviceSlug,
            name: deviceSlug.toUpperCase(),
            model: attrs.model,
            max_power_watts: attrs.max_power_watts,
          }),
          power_entity: "",
          auto_entity: "",
          firmware_entity: "",
          runtime_entity: "",
          schedule_entity: "",
          last_notification_entity: "",
          fan_entity: "",
          fan_rpm_entity: "",
          fan_temperature_entity: "",
          has_fan: false,
          channels: [],
        });
      }
      const group = groups.get(deviceSlug);
      if (attrs.model) group.model = String(attrs.model);
      if (Number(attrs.max_power_watts) > 0) group.max_power_watts = Number(attrs.max_power_watts);
      if (domain === "switch" && suffix === "power") group.power_entity = entityId;
      if (domain === "switch" && suffix === "auto_mode") group.auto_entity = entityId;
      if (domain === "sensor" && suffix === "firmware_version") group.firmware_entity = entityId;
      if (domain === "sensor" && (suffix === "runtime" || suffix === "runtime_minutes")) group.runtime_entity = entityId;
      if (domain === "sensor" && suffix === "schedule") group.schedule_entity = entityId;
      if (domain === "sensor" && suffix === "last_notification") group.last_notification_entity = entityId;
      if (domain === "sensor" && (suffix === "fan_rpm" || suffix === "fan_speed")) group.fan_rpm_entity = entityId;
      if (domain === "sensor" && (suffix === "fan_temperature_celsius" || suffix === "temperature")) group.fan_temperature_entity = entityId;
      if (domain === "fan" && suffix === "fan") {
        group.fan_entity = entityId;
        group.has_fan = true;
      }
    });
    const entities = Object.entries(this._hass.states)
      .filter(([entityId, state]) => {
        if (!entityId.startsWith("light.")) return false;
        const attrs = state && state.attributes ? state.attributes : {};
        return Boolean(entityColor(entityId, attrs));
      })
      .map(([entityId, state]) => {
        const attrs = state && state.attributes ? state.attributes : {};
        const color = entityColor(entityId, attrs);
        const name = String(color || attrs.friendly_name || entityId.split(".")[1] || entityId);
        const match = String(entityId).toLowerCase().match(devicePattern);
        return {
          entityId,
          state,
          attrs,
          name,
          color,
          deviceSlug: match ? deviceKey(match[2]) : "led_1",
          suffix: match ? match[3] : "",
        };
      })
      .sort((left, right) => {
        const colorDifference = (colorOrder.get(left.color) ?? 99) - (colorOrder.get(right.color) ?? 99);
        if (colorDifference) return colorDifference;
        return Number(left.suffix !== left.color) - Number(right.suffix !== right.color);
      });
    entities.forEach((item) => {
      if (!groups.has(item.deviceSlug)) {
        groups.set(item.deviceSlug, {
          id: item.deviceSlug,
          label: "LED",
          name: item.deviceSlug.toUpperCase(),
          address: deviceAddress(item.deviceSlug),
          model: "LED",
          max_brightness: this.resolveLedMaxBrightness({ id: item.deviceSlug, name: item.name, model: "LED" }),
          max_power_watts: this.resolveLedMaxPowerWatts({
            id: item.deviceSlug,
            name: item.name,
            model: item.attrs.model,
            max_power_watts: item.attrs.max_power_watts,
          }),
          power_entity: "",
          auto_entity: "",
          firmware_entity: "",
          runtime_entity: "",
          schedule_entity: "",
          last_notification_entity: "",
          fan_entity: "",
          fan_rpm_entity: "",
          fan_temperature_entity: "",
          has_fan: false,
          channels: [],
        });
      }
      const group = groups.get(item.deviceSlug);
      if (item.attrs.model) group.model = String(item.attrs.model);
      if (Number(item.attrs.max_power_watts) > 0) group.max_power_watts = Number(item.attrs.max_power_watts);
      const match = colorMap.find(([key]) => key === item.color);
      const brightness = Number(item.attrs.brightness || 0);
      const channel = {
        id: group.channels.length + 1,
        name: match ? match[1] : String(item.name).replace(/^.* /, "") || `CH${group.channels.length + 1}`,
        color: match ? match[2] : "#2ea8ff",
        key: item.color,
        value: brightness ? Math.round((brightness / 255) * this.inferLedMaxBrightness(item)) : (item.state.state === "on" ? this.inferLedMaxBrightness(item) : 0),
        entity: item.entityId,
        available: !["unavailable", "unknown"].includes(String(item.state.state || "").toLowerCase()),
      };
      const existingIndex = group.channels.findIndex((existing) => existing.key === channel.key);
      if (existingIndex < 0) {
        group.channels.push(channel);
      } else if (!group.channels[existingIndex].available && channel.available) {
        channel.id = group.channels[existingIndex].id;
        group.channels[existingIndex] = channel;
      }
    });
    return Array.from(groups.values())
      .filter((device) => device.channels.length)
      .map((device, index) => ({
        ...device,
        label: `${this.tr("device")} ${index + 1}`,
        model: device.model && device.model !== "LED" ? device.model : (device.channels.length >= 4 ? "WRGB" : "LED"),
        has_fan: Boolean(device.has_fan || device.fan_entity || /vivid\s*iii|dyvvd3/i.test(String(device.model || ""))),
        power_entity: device.power_entity || (device.channels[0] ? device.channels[0].entity : ""),
        channels: device.channels.map(({ available: _available, ...channel }) => channel),
      }));
  }

  isLedDeviceConfig(device = {}) {
    return Boolean(device.address || (Array.isArray(device.channels) && device.channels.length));
  }

  resolveLedMaxBrightness(device = {}) {
    const inferred = this.inferLedMaxBrightness(device);
    const configured = Number(device && device.max_brightness);
    if (Number.isFinite(configured) && configured > 0) return Math.min(100, Math.max(configured, inferred));
    return inferred;
  }

  inferLedMaxBrightness(device = {}) {
    const text = [
      device.model,
      device.name,
      device.label,
      device.id,
      device.address,
    ]
      .filter(Boolean)
      .map((value) => String(value).toLowerCase())
      .join(" ");
    return 100;
  }

  ledMaxBrightness(device = this.activeLedDevice || {}) {
    const value = Number(device && device.max_brightness);
    return Number.isFinite(value) && value > 0 ? Math.min(100, value) : this.inferLedMaxBrightness(device);
  }

  ledBrightnessPctFromValue(value, device = this.activeLedDevice || {}) {
    const max = this.ledMaxBrightness(device);
    return max > 0 ? Math.round((Math.max(0, Math.min(max, Math.round(Number(value || 0)))) / max) * 100) : 0;
  }

  ledMaxPowerWatts(device = this.activeLedDevice || {}) {
    return this.resolveLedMaxPowerWatts(device);
  }

  resolveLedMaxPowerWatts(device = {}) {
    const deviceId = String(device && device.id || "");
    const overrides = this.uiSettings && this.uiSettings.deviceMaxPowerWatts
      ? this.uiSettings.deviceMaxPowerWatts
      : {};
    const manual = Math.max(0, Number(overrides[deviceId]) || 0);
    if (manual > 0) return manual;
    const configured = Math.max(0, Number(device && device.max_power_watts) || 0);
    if (configured > 0) return configured;
    const text = [device.id, device.label, device.name, device.model]
      .filter(Boolean)
      .map((value) => String(value).toLowerCase())
      .join(" ");
    const universalPowerWatts = {
      550: 28,
      600: 29,
      700: 33,
      800: 36,
      920: 55,
      1000: 59,
      1200: 91,
      1500: 100,
    };
    const match = text.match(/dyu(550|600|700|800|920|1000|1200|1500)/);
    return match ? universalPowerWatts[Number(match[1])] : 0;
  }

  supportsLedWattEstimates(device = this.activeLedDevice || {}) {
    return this.ledMaxPowerWatts(device) > 0;
  }

  usesUniversalWrgbPowerProfile(device = this.activeLedDevice || {}) {
    const text = [device && device.id, device && device.name, device && device.model].filter(Boolean).join(" ").toLowerCase();
    return text.includes("universal wrgb") || /dyu(550|600|700|800|920|1000|1200|1500)/.test(text);
  }

  ledWattChannelKey(channel = {}) {
    const text = String(channel.key || channel.name || "").toLowerCase();
    if (text.includes("red") || text.includes("rot")) return "red";
    if (text.includes("green") || text.includes("gruen") || text.includes("grün")) return "green";
    if (text.includes("blue") || text.includes("blau")) return "blue";
    if (text.includes("white") || text.includes("weiss") || text.includes("weiß")) return "white";
    return ({ 1: "red", 2: "green", 3: "blue", 4: "white" })[Number(channel.id)] || "";
  }

  ledWattFormat(value) {
    const rounded = Math.max(0, Number(value) || 0).toFixed(1).replace(/\.0$/, "");
    return this.language() === "de" ? rounded.replace(".", ",") : rounded;
  }

  ledWattInterpolate(points, value = 0) {
    const percent = Math.max(0, Math.min(100, Number(value) || 0));
    for (let index = 1; index < points.length; index += 1) {
      const [upperPercent, upperWatts] = points[index];
      if (percent <= upperPercent) {
        const [lowerPercent, lowerWatts] = points[index - 1];
        const ratio = (percent - lowerPercent) / (upperPercent - lowerPercent);
        return lowerWatts + ((upperWatts - lowerWatts) * ratio);
      }
    }
    return points[points.length - 1][1];
  }

  ledChannelEstimatedWatts(channel, value = 0) {
    const channelPowerPoints = {
      red: [[0, 0], [1, 3], [11, 4], [21, 6], [30, 7], [38, 8], [47, 9], [54, 11], [62, 12], [69, 13], [77, 14], [83, 16], [90, 17], [97, 18], [100, 19]],
      green: [[0, 0], [1, 3], [8, 4], [14, 6], [21, 7], [27, 8], [33, 9], [39, 11], [45, 12], [50, 13], [56, 14], [61, 16], [71, 18], [76, 19], [81, 21], [86, 22], [90, 23], [99, 24], [100, 26]],
      blue: [[0, 0], [1, 2], [2, 3], [20, 4], [38, 6], [55, 7], [71, 8], [87, 9], [100, 9]],
      white: [[0, 0], [1, 1], [11, 1], [30, 2], [100, 12]],
    };
    const points = channelPowerPoints[this.ledWattChannelKey(channel)];
    if (!this.usesUniversalWrgbPowerProfile()) {
      const channelCount = Math.max(1, (this.ledChannels || []).length);
      return this.ledMaxPowerWatts() * Math.max(0, Math.min(100, Number(value) || 0)) / 100 / channelCount;
    }
    if (!points) return 0;
    return this.ledWattInterpolate(points, value) * (this.ledMaxPowerWatts() / 61);
  }

  ledTotalEstimatedWatts(values = []) {
    const channels = (this.ledChannels || [])
      .map((channel) => ({ channel, key: this.ledWattChannelKey(channel) }))
      .filter((item) => item.key);
    const levels = channels.map((item, index) => Math.max(0, Math.min(100, Number(values[index]) || 0)));
    const maxPowerWatts = this.ledMaxPowerWatts();
    if (!this.usesUniversalWrgbPowerProfile()) {
      const average = levels.length ? levels.reduce((sum, level) => sum + level, 0) / levels.length : 0;
      return Math.min(maxPowerWatts, maxPowerWatts * average / 100);
    }
    const completeRgbw = channels.length === 4 && new Set(channels.map((item) => item.key)).size === 4;
    if (completeRgbw && levels.every((level) => Math.abs(level - levels[0]) < 0.001)) {
      const totalPowerPoints = [[0, 0], [1, 3], [11, 8], [30, 17], [100, 61]];
      return Math.min(maxPowerWatts, this.ledWattInterpolate(totalPowerPoints, levels[0]) * (maxPowerWatts / 61));
    }
    const channelPowerShares = { red: 0.273, green: 0.394, blue: 0.136, white: 0.197 };
    return Math.min(maxPowerWatts, channels.reduce(
      (total, item, index) => total + (maxPowerWatts * channelPowerShares[item.key] * levels[index] / 100),
      0,
    ));
  }

  ledWattValuesFromControls() {
    return (this.ledChannels || []).map((channel) => {
      const control = this.querySelector(`input[type="range"][data-led-device-channel="${Number(channel.id)}"]`);
      return control && Number.isFinite(Number(control.value)) ? Number(control.value) : this.ledChannelValue(channel);
    });
  }

  updateLedWattDisplays() {
    if (!this.supportsLedWattEstimates()) return;
    const values = this.ledWattValuesFromControls();
    (this.ledChannels || []).forEach((channel, index) => {
      const field = this.querySelector(`[data-led-channel-watts="${Number(channel.id)}"]`);
      if (!field) return;
      const value = values[index] || 0;
      const watts = this.ledChannelEstimatedWatts(channel, value);
      field.textContent = value > 0 ? `≈ ${this.ledWattFormat(watts)} W` : "0 W";
      field.title = this.tr("estimated_power");
    });
    const total = this.querySelector("[data-led-total-watts]");
    if (total) {
      total.textContent = `${this.tr("total")} ≈ ${this.ledWattFormat(this.ledTotalEstimatedWatts(values))} W / ${this.ledWattFormat(this.ledMaxPowerWatts())} W`;
      total.title = this.tr("estimated_power");
    }
  }

  ledPresetValue(preset, device = this.activeLedDevice || {}) {
    const max = this.ledMaxBrightness(device);
    const presets = { off: 0, low: Math.round(max * 0.25), medium: Math.round(max * 0.6), high: max };
    return presets[preset] ?? presets.medium;
  }

  ledDeviceHasFan(device = this.activeLedDevice || {}) {
    return Boolean(device && (device.has_fan || device.fan_entity || /vivid\s*iii|dyvvd3/i.test(String(device.model || device.name || ""))));
  }

  ledFanEntityValue(entityId, fallback = "-") {
    const state = entityId && this._hass && this._hass.states ? this._hass.states[entityId] : null;
    if (!state || ["unknown", "unavailable"].includes(String(state.state || "").toLowerCase())) return fallback;
    return String(state.state);
  }

  ledFanPercentage(device = this.activeLedDevice || {}) {
    const state = device && device.fan_entity && this._hass && this._hass.states
      ? this._hass.states[device.fan_entity]
      : null;
    const percentage = Number(state && state.attributes && state.attributes.percentage);
    if (Number.isFinite(percentage)) return Math.max(0, Math.min(100, Math.round(percentage)));
    if (device && device.fan_demo) return Math.max(0, Math.min(100, Math.round(Number(device.fan_percentage) || 0)));
    return state && state.state === "on" ? 100 : 0;
  }

  async setLedFanPercentage(rawValue) {
    const device = this.activeLedDevice || {};
    const percentage = Math.max(0, Math.min(100, Math.round(Number(rawValue) || 0)));
    if (device.fan_demo) {
      device.fan_percentage = percentage;
      device.fan_rpm = percentage * 20;
      this.render();
      return true;
    }
    if (!this._hass || !device.fan_entity) return false;
    try {
      await this._hass.callService("fan", "set_percentage", { percentage }, { entity_id: device.fan_entity });
      await this.addLedHistory(this.tr("fan_control"), `${percentage} %`, null, { status: "ok" });
      this.render();
      return true;
    } catch (err) {
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: `FAIL\n${this.tr("fan_control")}\n${err && err.message ? err.message : err}`,
        running: false,
        noChannel: true,
        level: "error",
      };
      this.render();
      return false;
    }
  }

  ledFanControlCard(device = this.activeLedDevice || {}) {
    const percentage = this.ledFanPercentage(device);
    const rpm = device.fan_demo ? String(device.fan_rpm) : this.ledFanEntityValue(device.fan_rpm_entity);
    const temperature = device.fan_demo
      ? String(device.fan_temperature)
      : this.ledFanEntityValue(device.fan_temperature_entity);
    const disabled = device.fan_entity || device.fan_demo ? "" : "disabled";
    return `
      <section class="card led-device-presets-card led-device-fan-card">
        <h2>${this.tr("fan_control")}</h2>
        <div class="led-fan-metrics">
          <span><ha-icon icon="mdi:thermometer"></ha-icon><b>${this.tr("temperature")}</b><strong>${this.escapeHtml(temperature)} °C</strong></span>
          <span><ha-icon icon="mdi:fan"></ha-icon><b>${this.tr("fan_speed")}</b><strong>${this.escapeHtml(rpm)} RPM</strong></span>
        </div>
        <div class="led-fan-control">
          <input type="range" min="0" max="100" step="1" value="${percentage}" data-led-fan-control ${disabled} aria-label="${this.tr("fan_control")}">
          <input type="number" min="0" max="100" step="1" value="${percentage}" data-led-fan-control ${disabled} aria-label="${this.tr("fan_percentage")}">
          <span>%</span>
        </div>
      </section>`;
  }

  applyLedDevice(deviceId, fallback = true) {
    const devices = Array.isArray(this.ledDevices) ? this.ledDevices : [];
    const requestedDevice = devices.find((item) => String(item.id) === String(deviceId));
    const device = requestedDevice || (fallback ? devices[0] : null) || null;
    if (!device && !fallback) return this.activeLedDevice || null;
    this.activeLedDeviceId = device ? device.id : "";
    this.activeLedDevice = device;
    this.ledChannels = device && Array.isArray(device.channels) ? device.channels : [];
    this.ledHistoryOverlay = [];
    if (device) this.fetchLedHistory();
    return device;
  }

  setLedDevice(deviceId) {
    if (deviceId === this.activeLedDeviceId) return;
    this.dialogState = null;
    this.applyLedDevice(deviceId);
    this.render();
  }

  ledDeviceDisplayName(device = {}) {
    const names = this.uiSettings && this.uiSettings.deviceNames ? this.uiSettings.deviceNames : {};
    const customName = String(names[String(device.id || "")] || "").trim();
    return customName || String(device.label || device.name || device.id || "LED");
  }

  openLedDeviceNameDialog() {
    this.dialogState = { type: "led-device-name-editor" };
    this.render();
  }

  saveLedDeviceNameDialog() {
    const root = this.shadowRoot || this;
    const input = root.querySelector("[data-led-device-name]");
    const deviceId = String(this.activeLedDevice && this.activeLedDevice.id || "");
    const name = String(input && input.value || "").trim().slice(0, 48);
    if (!deviceId || !name) return;
    const deviceNames = { ...((this.uiSettings && this.uiSettings.deviceNames) || {}), [deviceId]: name };
    this.uiSettings = { ...(this.uiSettings || {}), deviceNames };
    this.saveUiSettings();
    this.dialogState = null;
    this.render();
  }

  ledDeviceNameDialog() {
    const device = this.activeLedDevice || {};
    return this.sharedModalDialog({
      title: this.tr("change_device_name"),
      sectionClass: "modal card led-auto-mode-modal",
      bodyHtml: `
        <label class="led-device-name-row">
          <span>${this.tr("device_name")}</span>
          <input type="text" maxlength="48" value="${this.escapeHtml(this.ledDeviceDisplayName(device))}" data-led-device-name autofocus>
        </label>`,
      actions: [
        { action: "close-dialog", label: this.tr("cancel"), className: "link", type: "button" },
        { action: "led-device-name-save", label: this.tr("save"), className: "primary", type: "button", icon: "mdi:content-save-outline" },
      ],
    });
  }

  ledDeviceTabs() {
    if (!this.ledDevices || this.ledDevices.length < 2) return "";
    const tabs = this.ledDevices.map((device) => `
        <button type="button" data-led-device="${this.escapeHtml(device.id)}" class="${device.id === this.activeLedDeviceId ? "active" : ""}">
          ${this.escapeHtml(this.ledDeviceDisplayName(device))}
        </button>`).join("");
    return `<nav class="doser-device-tabs" aria-label="LED ${this.escapeHtml(this.tr("device"))}">${tabs}</nav>`;
  }

  ledManualScheduleWarningKey() {
    const device = this.activeLedDevice || {};
    return String(device.id || device.address || "default");
  }

  hasLedSchedules() {
    return this.ledScheduleRows().length > 0;
  }

  setLedManualScheduleWarning(active) {
    this._ledManualScheduleWarnings = this._ledManualScheduleWarnings || {};
    const key = this.ledManualScheduleWarningKey();
    if (active) this._ledManualScheduleWarnings[key] = true;
    else delete this._ledManualScheduleWarnings[key];
  }

  ledManualScheduleWarning() {
    const warnings = this._ledManualScheduleWarnings || {};
    const persisted = this.ledPersistedDeviceStatus();
    const persistedWarning = persisted
      && String(persisted.mode || "").toLowerCase() === "manual"
      && String(persisted.schedule_state || "").toLowerCase() === "manual_override";
    if (!warnings[this.ledManualScheduleWarningKey()] && !persistedWarning) return "";
    return `
      <div class="led-manual-schedule-warning" role="alert">
        <ha-icon icon="mdi:alert-circle"></ha-icon>
        <strong>${this.tr("led_manual_schedule_warning")}</strong>
      </div>`;
  }

  ledDeviceStatusChannels(overrides = {}) {
    return Object.fromEntries((this.ledChannels || []).map((channel) => {
      const key = String(channel && channel.key ? channel.key : `ch${channel.id}`).toLowerCase();
      const value = Object.prototype.hasOwnProperty.call(overrides, key)
        ? Number(overrides[key])
        : this.ledChannelValue(channel);
      return [key, Math.max(0, Math.round(Number(value || 0)))];
    }));
  }

  ledPersistedDeviceStatus() {
    const statuses = this.config && this.config.addon_database && this.config.addon_database.led_device_status
      ? this.config.addon_database.led_device_status
      : {};
    for (const key of this.ledScheduleStorageKeys()) {
      if (statuses && statuses[key] && typeof statuses[key] === "object") return statuses[key];
    }
    return null;
  }

  ledScheduledChannels(periods) {
    const channelsOff = Object.fromEntries(
      (this.ledChannels || []).map((channel) => [String(channel.key || `ch${channel.id}`).toLowerCase(), 0])
    );
    const now = new Date();
    const weekday = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"][now.getDay()];
    const currentMinute = (now.getHours() * 60) + now.getMinutes();
    const toMinute = (value) => {
      const [hour, minute] = String(value || "00:00").split(":").map(Number);
      return (Math.max(0, Math.min(23, hour || 0)) * 60) + Math.max(0, Math.min(59, minute || 0));
    };
    const activePeriod = (Array.isArray(periods) ? periods : []).find((period) => {
      if (!period || period.active === false) return false;
      const weekdays = this.normalizeLedWeekdays(period.weekdays || ["everyday"]);
      if (!weekdays.includes("everyday") && !weekdays.includes(weekday)) return false;
      const start = toMinute(period.start);
      const end = toMinute(period.end);
      return start <= end
        ? currentMinute >= start && currentMinute < end
        : currentMinute >= start || currentMinute < end;
    });
    if (!activePeriod) return channelsOff;
    const levels = activePeriod.levels || activePeriod.brightness || {};
    return { ...channelsOff, ...this.ledScheduleLevelsForDevice(levels) };
  }

  async persistLedDeviceStatus(options = {}) {
    const deviceKey = this.ledHistoryDeviceKey();
    if (!deviceKey) return false;
    const channels = this.ledDeviceStatusChannels(options.channels || {});
    const scheduleCount = Number.isFinite(Number(options.scheduleCount))
      ? Math.max(0, Number(options.scheduleCount))
      : this.ledScheduleRows().filter((row) => row && row.active !== false).length;
    const mode = String(options.mode || "unknown");
    const scheduleState = String(options.scheduleState || (
      scheduleCount <= 0 ? "empty" : (mode === "manual" ? "manual_override" : "configured")
    ));
    try {
      const response = await fetch("./api/led-device-status", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          device_key: deviceKey,
          mode,
          power_state: Object.values(channels).some((value) => Number(value) > 0) ? "on" : "off",
          channels,
          schedule_state: scheduleState,
          schedule_count: scheduleCount,
          last_source: String(options.source || "dashboard"),
          last_action: String(options.action || ""),
          last_channel: options.channel === null || options.channel === undefined ? null : Number(options.channel),
          last_status: String(options.status || "ok"),
        }),
      });
      if (!response.ok) return false;
      const payload = await response.json();
      if (payload && payload.status) {
        this.config = this.config || {};
        this.config.addon_database = this.config.addon_database || {};
        this.config.addon_database.led_device_status = this.config.addon_database.led_device_status || {};
        this.ledScheduleStorageKeys().forEach((key) => {
          this.config.addon_database.led_device_status[key] = payload.status;
        });
      }
      return true;
    } catch (_err) {
      return false;
    }
  }

  ledChannelValue(channel) {
    const max = this.ledMaxBrightness();
    const persisted = this.ledPersistedDeviceStatus();
    const channelKey = String(channel && channel.key ? channel.key : `ch${channel.id}`).toLowerCase();
    if (persisted && persisted.channels && Object.prototype.hasOwnProperty.call(persisted.channels, channelKey)) {
      return Math.max(0, Math.min(max, Math.round(Number(persisted.channels[channelKey] || 0))));
    }
    if (channel.entity && this._hass && this._hass.states[channel.entity]) {
      const state = this._hass.states[channel.entity];
      const brightness = Number(state.attributes && state.attributes.brightness);
      if (Number.isFinite(brightness) && brightness > 0) return Math.round((brightness / 255) * max);
      if (state.state === "off") return 0;
    }
    return Math.max(0, Math.min(max, Math.round(Number(channel.value || 0))));
  }

  ledDeviceIsOn() {
    const overrides = this._ledDevicePowerOverrides || {};
    const key = this.ledManualScheduleWarningKey();
    if (Object.prototype.hasOwnProperty.call(overrides, key)) return Boolean(overrides[key]);
    return (this.ledChannels || []).some((channel) => this.ledChannelValue(channel) > 0);
  }

  async setLedBrightness(entityId, percent, showSuccess = false, historyMeta = null) {
    const max = this.ledMaxBrightness();
    const value = Math.max(0, Math.min(max, Math.round(Number(percent || 0))));
    if (!this._hass || !entityId) return false;
    const channel = (this.ledChannels || []).find((item) => item.entity === entityId);
    const debug = Boolean(this.uiSettings && this.uiSettings.dashboardDebug);
    const channelKey = channel && channel.key ? String(channel.key) : "";
    const serviceData = {
      ...(this.activeLedDevice && this.activeLedDevice.address ? { address: this.activeLedDevice.address } : {}),
      ...(channel && channel.entity ? { entity_id: channel.entity } : {}),
      brightness: channelKey ? { [channelKey]: value } : value,
    };
    const title = "LED Einzelkanal senden";
    try {
      if (channel) channel.value = value;
      this.render();
      const result = await this.runDeviceService({
        service: "set_brightness",
        data: serviceData,
        title,
        debug,
        dialog: debug,
        channel: channel ? channel.id : 1,
        noChannel: true,
      });
      if (!result || !result.ok) throw new Error(result && result.output ? result.output : this.tr("led_set_failed"));
      const action = historyMeta && historyMeta.action ? historyMeta.action : "LED gesetzt";
      const suffix = historyMeta && historyMeta.sourceId ? ` [${historyMeta.sourceId}]` : "";
      const params = historyMeta && historyMeta.params && typeof historyMeta.params === "object" ? historyMeta.params : {};
      const channelLabel = channel
        ? `CH${channel.id} ${this.ledChannelDisplayName(channel)}`
        : (entityId || "LED");
      await this.addLedHistory(action, `${channelLabel}: ${value}/${max}${suffix}`, channel ? channel.id : null, {
        params: {
          ...params,
          ...(channel ? { channel_id: channel.id, channel_key: channel.key, channel_name: channelLabel } : {}),
        },
      });
      await this.persistLedDeviceStatus({
        mode: "manual",
        scheduleState: "manual_override",
        source: "channel",
        action,
        channel: channel ? channel.id : null,
        channels: channelKey ? { [channelKey]: value } : {},
      });
      this.setLedManualScheduleWarning(true);
      if (this._ledDevicePowerOverrides) delete this._ledDevicePowerOverrides[this.ledManualScheduleWarningKey()];
      if (!debug && showSuccess) {
        this.dialogState = { type: "debug", channel: 1, output: `OK\nLED gesetzt\n${entityId}: ${value}/${max}`, running: false, noChannel: true, level: "ok" };
      }
      this.render();
      return true;
    } catch (err) {
      const message = err && err.message ? err.message : err;
      if (!debug) {
        this.dialogState = { type: "debug", channel: channel ? channel.id : 1, output: `FAIL\nLED setzen\n${message}`, running: false, noChannel: true, level: "error" };
      }
      this.render();
      return false;
    }
  }

  async setLedPreset(mode) {
    const value = this.ledPresetValue(mode);
    const supportedKeys = new Set(["red", "green", "blue", "white"]);
    const channels = (this.ledChannels || []).filter((channel) => supportedKeys.has(String(channel && channel.key || "").toLowerCase()));
    const brightness = Object.fromEntries(channels.map((channel) => [String(channel.key).toLowerCase(), value]));
    if (!this._hass || !Object.keys(brightness).length) return;
    const debug = Boolean(this.uiSettings && this.uiSettings.dashboardDebug);
    const data = {
      brightness,
      ...(channels[0] && channels[0].entity ? { entity_id: channels[0].entity } : {}),
      ...(this.activeLedDevice && this.activeLedDevice.address ? { address: this.activeLedDevice.address } : {}),
    };
    const powerKey = this.ledManualScheduleWarningKey();
    const previousPower = this.ledDeviceIsOn();
    this._ledDevicePowerOverrides = this._ledDevicePowerOverrides || {};
    this._ledDevicePowerOverrides[powerKey] = value > 0;
    channels.forEach((channel) => {
      channel.value = value;
    });
    this.render();
    const result = await this.runDeviceService({
      service: "set_brightness",
      data,
      title: mode === "off" ? this.tr("off") : `LED Preset ${value}`,
      debug,
      dialog: debug,
      channel: 1,
      noChannel: true,
    });
    if (result && result.ok) {
      this.setLedManualScheduleWarning(true);
      await this.addLedHistory(
        mode === "off" ? this.tr("off") : `LED Preset ${value}`,
        `${channels.length} Kanal/Kanaele: ${value}`,
        null,
        { status: "ok" },
      );
      await this.persistLedDeviceStatus({
        mode: "manual",
        scheduleState: "manual_override",
        source: mode === "off" ? "device_power" : "preset",
        action: mode === "off" ? this.tr("off") : `LED Preset ${value}`,
        channels: brightness,
      });
      if (!debug) {
        this.dialogState = {
          type: "debug",
          channel: 1,
          output: `OK\n${mode === "off" ? this.tr("off") : `LED Preset ${value}`}\n${channels.length} Kanal/Kanaele`,
          running: false,
          noChannel: true,
          level: "ok",
        };
      }
    } else {
      this._ledDevicePowerOverrides[powerKey] = previousPower;
      if (!debug) {
        this.dialogState = {
          type: "debug",
          channel: 1,
          output: `FAIL\n${mode === "off" ? this.tr("off") : `LED Preset ${value}`}\n${result && result.output ? result.output : this.tr("send_failed")}`,
          running: false,
          noChannel: true,
          level: "error",
        };
      }
    }
    this.render();
    return Boolean(result && result.ok);
  }

  ledScheduleValues() {
    const root = this.shadowRoot || this;
    return Array.from(root.querySelectorAll("[data-led-schedule-row]")).map((row) => {
      const get = (name, fallback) => {
        const el = row.querySelector(`[data-led-schedule-control="${name}"][data-led-schedule-kind="number"]`)
          || row.querySelector(`[data-led-schedule-control="${name}"][data-led-schedule-kind="range"]`)
          || row.querySelector(`[data-led-schedule-control="${name}"][data-led-schedule-kind="hidden"]`)
          || row.querySelector(`[data-led-schedule="${name}"]`);
        return el ? String(el.value || fallback) : fallback;
      };
      const max = this.ledMaxBrightness();
      const level = (name) => Math.max(0, Math.min(max, Math.round(Number(get(name, "0")))));
      const selectedWeekdays = Array.from(row.querySelectorAll("[data-led-schedule-weekday]"))
        .filter((el) => el.classList.contains("active") || el.getAttribute("aria-pressed") === "true")
        .map((el) => String(el.value || "").trim().toLowerCase())
        .filter(Boolean);
      const activeEl = row.querySelector("[data-led-schedule-active]");
      const active = activeEl ? Boolean(activeEl.checked) : true;
      return {
        active,
        start: get("start", "08:00"),
        end: get("end", "20:00"),
        levels: {
          red: level("red"),
          green: level("green"),
          blue: level("blue"),
          white: level("white"),
        },
        ramp: Math.max(1, Math.min(150, Math.round(Number(get("ramp", "1"))))),
        weekdays: selectedWeekdays.length ? (selectedWeekdays.length === 7 ? ["everyday"] : selectedWeekdays) : ["everyday"],
      };
    }).filter((row) => row.start && row.end);
  }

  ledWeekdayOptions() {
    return [
      ["monday", "Mo"],
      ["tuesday", "Di"],
      ["wednesday", "Mi"],
      ["thursday", "Do"],
      ["friday", "Fr"],
      ["saturday", "Sa"],
      ["sunday", "So"],
    ];
  }

  normalizeLedWeekdays(weekdays) {
    const values = Array.isArray(weekdays)
      ? weekdays
      : String(weekdays || "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
    const normalized = values.map((value) => String(value || "").trim().toLowerCase()).filter(Boolean);
    if (!normalized.length || normalized.includes("everyday")) return ["everyday"];
    const allowed = this.ledWeekdayOptions().map(([value]) => value);
    const ordered = allowed.filter((value) => normalized.includes(value));
    return ordered.length === 7 ? ["everyday"] : ordered;
  }

  ledWeekdaysText(weekdays) {
    const values = this.normalizeLedWeekdays(weekdays);
    if (values.length === 1 && values[0] === "everyday") return "Alle Tage";
    const labels = Object.fromEntries(this.ledWeekdayOptions());
    return values.map((value) => labels[value] || value).join(", ");
  }

  ledScheduleLevel(levels, keys) {
    const source = levels && typeof levels === "object" ? levels : {};
    const max = this.ledMaxBrightness();
    const variants = [];
    keys.forEach((key) => {
      variants.push(key);
      variants.push(String(key));
      variants.push(String(key).toLowerCase());
      variants.push(String(key).toUpperCase());
    });
    for (const key of variants) {
      if (Object.prototype.hasOwnProperty.call(source, key)) {
        const value = Number(source[key]);
        return Number.isFinite(value) ? Math.max(0, Math.min(max, Math.round(value))) : 0;
      }
    }
    return 0;
  }

  normalizeLedScheduleLevels(levels) {
    return {
      red: this.ledScheduleLevel(levels, ["red", "rot", "r", 0]),
      green: this.ledScheduleLevel(levels, ["green", "gruen", "grün", "g", 1]),
      blue: this.ledScheduleLevel(levels, ["blue", "blau", "b", 2]),
      white: this.ledScheduleLevel(levels, ["white", "weiss", "weiß", "w", 3]),
    };
  }

  ledSupportedScheduleKeys(device = this.activeLedDevice || {}) {
    const channelKeys = (Array.isArray(device && device.channels) ? device.channels : [])
      .map((channel) => String(channel && channel.key ? channel.key : "").trim().toLowerCase())
      .filter((key) => ["red", "green", "blue", "white"].includes(key));
    if (channelKeys.length) return Array.from(new Set(channelKeys));
    return ["red", "green", "blue", "white"];
  }

  ledScheduleLevelsForDevice(levels, device = this.activeLedDevice || {}) {
    const normalized = this.normalizeLedScheduleLevels(levels);
    const supported = new Set(this.ledSupportedScheduleKeys(device));
    return Object.fromEntries(
      Object.entries(normalized).filter(([key]) => supported.has(String(key).toLowerCase()))
    );
  }

  ledScheduleChannelLabel(key) {
    const labels = {
      red: this.tr("red"),
      green: this.tr("green"),
      blue: this.tr("blue"),
      white: this.tr("white"),
    };
    return labels[String(key || "").toLowerCase()] || String(key || "").toUpperCase();
  }

  ledScheduleTemplateOptions() {
    const inventory = (this.config && this.config.addon_database && this.config.addon_database.templates) || {};
    const standard = Array.isArray(inventory.standard) ? inventory.standard : [];
    const deviceAddress = String(this.activeLedDevice && this.activeLedDevice.address ? this.activeLedDevice.address : "").trim().toUpperCase();
    const localTemplates = this.loadLocalLedTemplates();
    const deviceTemplates = Array.isArray(inventory.devices)
      ? inventory.devices.filter((template) => String(template && template.device_key ? template.device_key : "").trim().toUpperCase() === deviceAddress)
      : [];
    const mapTemplate = (template, scope, labelPrefix) => ({
      value: `${scope}:${String(template.name || "").trim()}`,
      label: `${labelPrefix}${String(template.name || "").trim()}`,
      description: scope === "standard" ? `${this.tr("database")}: ${this.tr("template_standard")}` : `${this.tr("database")}: ${deviceAddress || this.tr("device")}`,
      values: Array.isArray(template.values) ? template.values.map((value) => Number(value)) : [],
    });
    return [
      { value: "custom", label: "Eigene Werte", description: "Manuell", values: [] },
      ...standard.filter((template) => String(template.name || "").trim()).map((template) => mapTemplate(template, "standard", "Standard: ")),
      ...deviceTemplates.filter((template) => String(template.name || "").trim()).map((template) => mapTemplate(template, "device", `${this.tr("device")}: `)),
      ...localTemplates.filter((template) => String(template.name || "").trim()).map((template) => mapTemplate(template, "local", `${this.tr("template_local")}: `)),
    ];
  }

  localLedTemplatesKey(device = this.activeLedDevice || {}) {
    const deviceAddress = String(device && device.address ? device.address : device && device.id ? device.id : "default").trim().toUpperCase();
    return `chihiros-led-schedule-templates:${deviceAddress || "default"}`;
  }

  loadLocalLedTemplates(device = this.activeLedDevice || {}) {
    try {
      const raw = window.localStorage.getItem(this.localLedTemplatesKey(device));
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.filter((template) => template && typeof template === "object") : [];
    } catch (_err) {
      return [];
    }
  }

  saveLocalLedTemplates(templates, device = this.activeLedDevice || {}) {
    try {
      window.localStorage.setItem(this.localLedTemplatesKey(device), JSON.stringify(Array.isArray(templates) ? templates : []));
    } catch (_err) {
      // Local storage can be unavailable in restricted browser modes.
    }
  }

  ledHistoryDeviceKey() {
    const device = this.activeLedDevice || {};
    return String(device.address || device.id || this.activeLedDeviceId || "default").trim().toUpperCase();
  }

  ledScheduleDeviceKey() {
    const device = this.activeLedDevice || {};
    return String(device.address || device.id || this.activeLedDeviceId || "default").trim().toUpperCase();
  }

  ledScheduleStorageKeys() {
    const keys = [
      String(this.activeLedDevice && this.activeLedDevice.address ? this.activeLedDevice.address : "").trim().toUpperCase(),
      this.ledScheduleDeviceKey(),
    ].filter(Boolean);
    return [...new Set(keys)];
  }

  ledServiceSelector(device = this.activeLedDevice || {}) {
    const channels = device === this.activeLedDevice ? this.ledChannels : device.channels;
    const firstEntity = (Array.isArray(channels) ? channels : []).find((channel) => channel && channel.entity);
    return {
      ...(device.address ? { address: device.address } : {}),
      ...(firstEntity && firstEntity.entity ? { entity_id: firstEntity.entity } : {}),
    };
  }

  async fetchLedHistory(force = false) {
    const deviceKey = this.ledHistoryDeviceKey();
    if (!deviceKey) return;
    const loaded = typeof this.fetchCoreHistory === "function" ? await this.fetchCoreHistory({
      device: deviceKey,
      scope: "led",
      overlayKey: "ledHistoryOverlay",
      loadingKey: "_ledHistoryLoadingKey",
      limit: 200,
      force,
      currentDevice: () => this.ledHistoryDeviceKey(),
    }) : false;
    if (!loaded && force) {
      const legacyEntries = this.loadLegacyLocalLedHistory(deviceKey);
      if (legacyEntries.length) {
        this.ledHistoryOverlay = legacyEntries;
        legacyEntries.slice().reverse().forEach((entry) => this.persistLedHistory(entry));
        this.render();
      }
    }
  }

  loadLegacyLocalLedHistory(deviceKey = this.ledHistoryDeviceKey()) {
    try {
      const raw = window.localStorage.getItem(`chihiros-led-history:${deviceKey}`);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.filter((entry) => entry && typeof entry === "object").slice(0, 200) : [];
    } catch (_err) {
      return [];
    }
  }

  async persistLedHistory(entry) {
    if (typeof this.persistCoreHistory !== "function") return false;
    return this.persistCoreHistory(entry, {
      device: this.ledHistoryDeviceKey(),
      scope: "led",
    });
  }

  normalizeLedRampMinutes(value) {
    const minutes = Number(value);
    if (!Number.isFinite(minutes)) return 1;
    if (minutes <= 1) return 1;
    if (minutes <= 30) return 30;
    if (minutes <= 60) return 60;
    if (minutes <= 90) return 90;
    if (minutes <= 120) return 120;
    return 150;
  }

  ledScheduleTemplateByValue(value) {
    const normalized = String(value || "custom").trim().toLowerCase();
    return this.ledScheduleTemplateOptions().find((template) => String(template.value || "").trim().toLowerCase() === normalized) || this.ledScheduleTemplateOptions()[0];
  }

  ledScheduleTemplateLevels(values = []) {
    const max = this.ledMaxBrightness();
    const list = Array.isArray(values) ? values.map((value) => Math.max(0, Math.min(max, Math.round(Number(value || 0))))) : [];
    if (!list.length) return null;
    const supportedKeys = this.ledSupportedScheduleKeys();
    if (list.length === supportedKeys.length) {
      const result = { red: 0, green: 0, blue: 0, white: 0 };
      supportedKeys.forEach((key, index) => {
        result[key] = list[index];
      });
      return result;
    }
    if (list.length === 1) {
      const value = list[0];
      return { red: value, green: value, blue: value, white: value };
    }
    if (list.length === 2) {
      return { red: list[0], green: list[0], blue: list[1], white: list[1] };
    }
    if (list.length === 3) {
      return { red: list[0], green: list[1], blue: list[2], white: list[2] };
    }
    return { red: list[0], green: list[1], blue: list[2], white: list[3] ?? list[2] ?? list[0] };
  }

  ledScheduleTemplateForRow(row) {
    const levels = this.normalizeLedScheduleLevels(row && row.levels ? row.levels : {});
    const templates = this.ledScheduleTemplateOptions().filter((template) => template.value !== "custom");
    const match = templates.find((template) => {
      const templateLevels = this.ledScheduleTemplateLevels(template.values);
      if (!templateLevels) return false;
      return this.ledSupportedScheduleKeys().every((name) => Number(levels[name] || 0) === Number(templateLevels[name] || 0));
    });
    return match ? match.value : "custom";
  }

  ledScheduleRowText(row) {
    const levels = this.normalizeLedScheduleLevels(row && row.levels ? row.levels : {});
    const channels = this.ledSupportedScheduleKeys()
      .map((key) => `${this.ledScheduleChannelLabel(key)} ${Number(levels[key] || 0)} %`)
      .join(" / ");
    return `${channels} · ${this.ledWeekdaysText(row && row.weekdays ? row.weekdays : ["everyday"])}`;
  }

  defaultLedScheduleRows() {
    const max = this.ledMaxBrightness();
    const levels = {
      red: Math.round(max * 0.7),
      green: Math.round(max * 0.7),
      blue: Math.round(max * 0.7),
      white: Math.round(max * 0.7),
    };
    return [
      { start: "08:00", end: "10:00", ramp: 1, weekdays: ["everyday"], levels: { ...levels } },
      { start: "10:00", end: "12:00", ramp: 1, weekdays: ["everyday"], levels: { ...levels } },
      { start: "12:00", end: "14:00", ramp: 1, weekdays: ["everyday"], levels: { ...levels } },
      { start: "14:00", end: "16:00", ramp: 1, weekdays: ["everyday"], levels: { ...levels } },
      { start: "16:00", end: "18:00", ramp: 1, weekdays: ["everyday"], levels: { ...levels } },
      { start: "18:00", end: "20:00", ramp: 1, weekdays: ["everyday"], levels: { ...levels } },
    ];
  }

  defaultNewLedScheduleRow() {
    const max = this.ledMaxBrightness();
    const level = Math.round(max * 0.7);
    return {
      active: true,
      start: "08:00",
      end: "20:00",
      ramp: 1,
      weekdays: ["everyday"],
      levels: { red: level, green: level, blue: level, white: level },
    };
  }

  ensureLedScheduleRowCount(rows, count = 6) {
    const normalizedRows = Array.isArray(rows) ? rows.map((row) => ({
      start: row && row.start ? row.start : "08:00",
      end: row && row.end ? row.end : "20:00",
      ramp: this.normalizeLedRampMinutes(row && row.ramp),
      weekdays: this.normalizeLedWeekdays(row && row.weekdays ? row.weekdays : ["everyday"]),
      levels: this.normalizeLedScheduleLevels(row && row.levels ? row.levels : {}),
      active: row && row.active !== false,
    })) : [];
    if (normalizedRows.length >= count) return normalizedRows;
    const defaults = this.defaultLedScheduleRows();
    for (let index = normalizedRows.length; index < count; index += 1) {
      const fallback = defaults[index] || defaults[defaults.length - 1] || {
        start: "08:00",
        end: "20:00",
        ramp: 1,
        weekdays: ["everyday"],
        levels: { red: 0, green: 0, blue: 0, white: 0 },
      };
      normalizedRows.push({
        start: fallback.start,
        end: fallback.end,
        ramp: this.normalizeLedRampMinutes(fallback.ramp),
        weekdays: this.normalizeLedWeekdays(fallback.weekdays),
        levels: this.normalizeLedScheduleLevels(fallback.levels),
        active: fallback.active !== false,
      });
    }
    return normalizedRows;
  }

  ledScheduleRows() {
    if (Array.isArray(this._ledScheduleRowsOverride)) {
      return this._ledScheduleRowsOverride.map((row) => ({
        start: String(row && row.start ? row.start : "08:00"),
        end: String(row && row.end ? row.end : "20:00"),
        ramp: this.normalizeLedRampMinutes(row && row.ramp),
        levels: this.normalizeLedScheduleLevels(row && row.levels),
        weekdays: this.normalizeLedWeekdays(row && row.weekdays),
        active: row && row.active !== false,
        verification_status: String(row && row.verification_status ? row.verification_status : "pending"),
        verified_at: String(row && row.verified_at ? row.verified_at : ""),
      }));
    }
    const storageKeys = this.ledScheduleStorageKeys();
    const addonMode = Boolean(this.config && this.config.addon_mode);
    const ledSchedules = this.config && this.config.addon_database && this.config.addon_database.led_schedules
      ? this.config.addon_database.led_schedules
      : null;
    if (ledSchedules && storageKeys.length) {
      for (const storageKey of storageKeys) {
        if (!Object.prototype.hasOwnProperty.call(ledSchedules, storageKey)) continue;
        const dbRows = ledSchedules[storageKey];
        if (Array.isArray(dbRows)) {
          if (!dbRows.length) return [];
          return dbRows.map((row) => ({
            start: String(row && row.start ? row.start : "08:00"),
            end: String(row && row.end ? row.end : "20:00"),
            ramp: this.normalizeLedRampMinutes(row && row.ramp),
            levels: this.normalizeLedScheduleLevels(row && row.levels),
            weekdays: this.normalizeLedWeekdays(row && row.weekdays),
            active: row && row.active !== false,
            verification_status: String(row && row.verification_status ? row.verification_status : "pending"),
            verified_at: String(row && row.verified_at ? row.verified_at : ""),
          }));
        }
      }
    }
    // In add-on mode the SQLite rows are the schedule source of truth. Device
    // snapshot points are used only by ledScheduleRowVerification(); they must
    // never be reconstructed into editable database rows during a refresh.
    if (addonMode) {
      return [];
    }
    const state = this.activeLedDevice && this.activeLedDevice.schedule_entity && this._hass
      ? this._hass.states[this.activeLedDevice.schedule_entity]
      : null;
    const points = state && state.attributes && Array.isArray(state.attributes.points) ? state.attributes.points : [];
    const validPoints = points.filter((point) => point && typeof point.time === "string");
    const normalized = validPoints.map((point, index) => {
      const levels = point.levels && typeof point.levels === "object" ? point.levels : {};
      const weekdays = point.weekdays ?? point.weekday ?? "everyday";
      const next = validPoints[index + 1];
      return {
        start: point.time,
        end: next && next.time ? next.time : "23:59",
        ramp: this.normalizeLedRampMinutes(point.ramp),
        levels: this.normalizeLedScheduleLevels(levels),
        weekdays: this.normalizeLedWeekdays(weekdays),
        active: point.active !== false,
      };
    });
    return normalized;
  }

  ledScheduleEditorRows() {
    const dialog = this.dialogState && this.dialogState.type === "led-schedule" ? this.dialogState : null;
    if (dialog && Array.isArray(dialog.ledScheduleDraftRows) && dialog.ledScheduleDraftRows.length) {
      return dialog.ledScheduleDraftRows.map((row) => ({ ...row }));
    }
    if (dialog && Boolean(dialog.ledScheduleNew)) {
      return [this.defaultNewLedScheduleRow()];
    }
    const rows = this.ledScheduleRows();
    const editIndex = dialog ? dialog.ledScheduleEditIndex : null;
    if (Number.isInteger(editIndex) && editIndex >= 0) {
      const row = rows[editIndex];
      return row ? [row] : [];
    }
    return rows;
  }

  ledScheduleSummary(rows) {
    const scheduleRows = rows && rows.length ? rows : this.ledScheduleRows();
    if (!scheduleRows.length) return this.tr("no_schedule_read");
    return scheduleRows.map((row) => {
      return `${row.start}-${row.end} ${this.ledScheduleRowText(row)}`;
    }).join("; ");
  }

  ledScheduleRowsSummary(rows, rowIndexes) {
    const scheduleRows = Array.isArray(rows) ? rows : [];
    const indexes = (Array.isArray(rowIndexes) ? rowIndexes : [rowIndexes])
      .filter((index) => Number.isInteger(index) && index >= 0 && index < scheduleRows.length);
    if (!indexes.length) return this.ledScheduleSummary(scheduleRows);
    return indexes.map((index) => {
      const row = scheduleRows[index];
      return `${this.tr("schedule")} ${index + 1}: ${row.start}-${row.end} ${this.ledScheduleRowText(row)}`;
    }).join("; ");
  }

  ledScheduleSentDetail(rowIndexes) {
    const indexes = (Array.isArray(rowIndexes) ? rowIndexes : [rowIndexes])
      .filter((index) => Number.isInteger(index) && index >= 0)
      .map((index) => index + 1);
    if (!indexes.length) return this.tr("schedule_sent");
    if (indexes.length === 1) return `${this.tr("schedule_sent")} ${indexes[0]}`;
    return `${this.tr("schedules_sent")}: ${indexes.join(", ")}`;
  }

  ledScheduleDeletedDetail(rowIndexes) {
    const indexes = (Array.isArray(rowIndexes) ? rowIndexes : [rowIndexes])
      .filter((index) => Number.isInteger(index) && index >= 0)
      .map((index) => index + 1);
    if (!indexes.length) return this.tr("schedule_deleted");
    if (indexes.length === 1) return `${this.tr("schedule_deleted")} ${indexes[0]}`;
    return `${this.tr("schedules_deleted")}: ${indexes.join(", ")}`;
  }

  ledTimeToMinutes(value) {
    const text = String(value || "").trim();
    const match = text.match(/^(\d{2}):(\d{2})$/);
    if (!match) return null;
    const hours = Number(match[1]);
    const minutes = Number(match[2]);
    if (!Number.isInteger(hours) || !Number.isInteger(minutes) || hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
      return null;
    }
    return (hours * 60) + minutes;
  }

  ledScheduleSegments(row) {
    const start = this.ledTimeToMinutes(row && row.start);
    const end = this.ledTimeToMinutes(row && row.end);
    if (start === null || end === null || start === end) return null;
    if (end > start) return [[start, end]];
    return [[start, 1440], [0, end]];
  }

  ledScheduleConflictText(firstIndex, secondIndex) {
    return `${this.tr("led_schedule_time_conflict")}\n#${firstIndex + 1}: ${this.ledScheduleValuesLabel(firstIndex)}\n#${secondIndex + 1}: ${this.ledScheduleValuesLabel(secondIndex)}\n${this.tr("led_schedule_time_conflict_detail")}`;
  }

  ledScheduleValuesLabel(index) {
    const root = this.shadowRoot || this;
    const row = root.querySelector(`[data-led-schedule-row="${index}"]`);
    if (!row) return "";
    const start = row.querySelector('[data-led-schedule="start"]');
    const end = row.querySelector('[data-led-schedule="end"]');
    return `${String(start && start.value ? start.value : "00:00")} - ${String(end && end.value ? end.value : "00:00")}`;
  }

  validateLedScheduleRows(rows) {
    const normalizedRows = Array.isArray(rows) ? rows : [];
    for (let index = 0; index < normalizedRows.length; index += 1) {
      if (!this.ledScheduleSegments(normalizedRows[index])) {
        return `${this.tr("led_schedule_time_invalid")}\n#${index + 1}: ${String(normalizedRows[index] && normalizedRows[index].start ? normalizedRows[index].start : "00:00")} - ${String(normalizedRows[index] && normalizedRows[index].end ? normalizedRows[index].end : "00:00")}`;
      }
    }
    for (let left = 0; left < normalizedRows.length; left += 1) {
      const leftSegments = this.ledScheduleSegments(normalizedRows[left]) || [];
      for (let right = left + 1; right < normalizedRows.length; right += 1) {
        const rightSegments = this.ledScheduleSegments(normalizedRows[right]) || [];
        const conflict = leftSegments.some(([leftStart, leftEnd]) => (
          rightSegments.some(([rightStart, rightEnd]) => leftStart < rightEnd && rightStart < leftEnd)
        ));
        if (conflict) return this.ledScheduleConflictText(left, right);
      }
    }
    return "";
  }

  setLedScheduleDialogMessage(message, level = "error") {
    this.dialogState = {
      ...(this.dialogState && typeof this.dialogState === "object" ? this.dialogState : {}),
      type: "led-schedule",
      ledScheduleEditorOpen: true,
      ledScheduleMessage: String(message || "").trim(),
      ledScheduleMessageLevel: level,
    };
    this.ledScheduleEditorOpen = true;
  }

  async addLedSchedule(send = true) {
    if (!this._hass) return;
    if (this._ledScheduleSubmitting) return;
    const root = this.shadowRoot || this;
    const debugControl = root.querySelector("[data-led-schedule-debug]");
    const showDebug = debugControl ? Boolean(debugControl.checked) : Boolean(this.dialogState && this.dialogState.ledScheduleDebug);
    if (this.dialogState && this.dialogState.type === "led-schedule") this.dialogState.ledScheduleDebug = showDebug;
    const values = this.ledScheduleValues();
    const currentRows = this.ledScheduleRows();
    const isNewDialog = Boolean(this.dialogState && this.dialogState.type === "led-schedule" && this.dialogState.ledScheduleNew);
    if (this.dialogState && this.dialogState.type === "led-schedule") {
      this.dialogState.ledScheduleDraftRows = values.map((row) => ({
        ...row,
        levels: { ...row.levels },
        weekdays: [...row.weekdays],
      }));
    }
    const editIndex = this.dialogState && this.dialogState.type === "led-schedule" && Number.isInteger(this.dialogState.ledScheduleEditIndex) && this.dialogState.ledScheduleEditIndex >= 0
      ? this.dialogState.ledScheduleEditIndex
      : null;
    const mergedValues = editIndex !== null
      ? currentRows.map((row, index) => (index === editIndex ? { ...values[0] } : { ...row }))
      : (isNewDialog ? [...currentRows.map((row) => ({ ...row })), ...values.map((row) => ({ ...row }))] : values);
    const sentRowIndexes = editIndex !== null
      ? [editIndex]
      : (isNewDialog ? values.map((_, index) => currentRows.length + index) : mergedValues.map((_, index) => index));
    const validationError = this.validateLedScheduleRows(mergedValues);
    if (validationError) {
      this.setLedScheduleDialogMessage(validationError);
      this.render();
      return;
    }
    const address = this.activeLedDevice && this.activeLedDevice.address ? this.activeLedDevice.address : undefined;
    const serviceSelector = this.ledServiceSelector();
    const deviceKey = this.ledScheduleDeviceKey();
    const periods = this.ledSchedulePeriodsFromRows(mergedValues);
    const sendRows = (editIndex !== null || isNewDialog ? values : mergedValues)
      .filter((row) => row && typeof row === "object");
    const sendPeriods = this.ledSchedulePeriodsFromRows(sendRows, this.activeLedDevice || {}, true);
    const previousPeriod = editIndex !== null && currentRows[editIndex] && currentRows[editIndex].active !== false && values[0] && values[0].active !== false
      ? this.ledSchedulePeriodsFromRows([currentRows[editIndex]], this.activeLedDevice || {}, true)[0]
      : null;
    const sendFlat = editIndex !== null || isNewDialog;
    const title = send ? this.tr("led_schedule_save_send") : this.tr("led_schedule_save_local");
    this._ledScheduleRowsOverride = mergedValues;
    this._ledScheduleSubmitting = true;
    this.setLedScheduleDialogMessage(send ? this.tr("sending") : this.tr("saving"), "pending");
    this.render();
    const localData = { periods, send: false, device_key: deviceKey, ...(address ? { address } : {}) };
    const localOk = await this.saveLedScheduleLocal(localData, `${title}\n${periods.length} ${this.tr("led_schedule_rows")}`, true);
    if (!localOk) {
      this.setLedScheduleDialogMessage(`${title}\n${this.tr("local_save_failed")}`);
      this._ledScheduleSubmitting = false;
      this._ledScheduleRowsOverride = null;
      this.render();
      return;
    }
    await this.addLedHistory(this.tr("led_schedule_saved"), this.ledScheduleRowsSummary(mergedValues, sentRowIndexes));
    if (!send) {
      this.ledScheduleEditorOpen = false;
      this.ledScheduleEditIndex = null;
      this.ledScheduleNewMode = false;
      this._ledScheduleSubmitting = false;
      this.render();
      this._ledScheduleRowsOverride = null;
      return;
    }
    const sendResult = await this.runLedScheduleService({
      service: sendFlat ? "add_schedule" : "set_schedule",
      data: sendFlat
        ? {
            ...(sendPeriods[0] || {}),
            enable_auto_mode: isNewDialog,
            ...(previousPeriod ? { previous_period: previousPeriod } : {}),
            ...(previousPeriod && editIndex !== null ? { previous_index: editIndex } : {}),
            ...serviceSelector,
          }
        : { periods: sendPeriods, send: true, ...serviceSelector },
      title: `${title}\n${sendPeriods.length} ${this.tr("led_schedule_rows")}`,
      debug: showDebug,
    });
    const sendOk = Boolean(sendResult && sendResult.ok);
    if (sendOk) {
      await this.saveLedScheduleLocal(
        { periods, send: false, device_key: deviceKey, ...(address ? { address } : {}) },
        `${title}\n${periods.length} ${this.tr("led_schedule_rows")}`,
        true,
      );
      await this.addLedHistory(`${this.tr("led_schedule_sent_action")} ok`, this.ledScheduleSentDetail(sentRowIndexes), null, { status: "ok" });
      if (showDebug) {
        this.setLedScheduleDialogMessage(sendResult && sendResult.output ? sendResult.output : `${title}\nOK`, "ok");
      } else {
        this.setLedScheduleDialogMessage(`${title}\n${this.tr("status")}: ok\n${this.tr("reply")}: ${this.tr("reply_sent")}`, "ok");
      }
    } else {
      await this.addLedHistory(`${this.tr("led_schedule_sent_action")} fail`, this.ledScheduleSentDetail(sentRowIndexes), null, { status: "fail" });
      this.setLedScheduleDialogMessage(sendResult && sendResult.output ? sendResult.output : `${title}\n${this.tr("send_failed")}`);
    }
    this._ledScheduleSubmitting = false;
    this.render();
    this._ledScheduleRowsOverride = null;
  }

  async resetLedSchedule(debugOverride = null) {
    const address = this.activeLedDevice && this.activeLedDevice.address ? this.activeLedDevice.address : undefined;
    const deviceKey = this.ledScheduleDeviceKey();
    const debug = debugOverride === null ? Boolean(this._ledScheduleResetDebug) : Boolean(debugOverride);
    const data = { debug, ...this.ledServiceSelector() };
    this.ledScheduleEditorOpen = false;
    this.ledScheduleEditIndex = null;
    const resetTitle = `${this.tr("led_scheduler")}: ${this.tr("delete")}`;
    const ok = await this.callLedService("reset_schedule", data, resetTitle, { debug });
    this._ledScheduleResetDebug = false;
    if (ok) {
      await this.saveLedScheduleLocal(address ? { address, periods: [], send: false, device_key: deviceKey } : { periods: [], send: false, device_key: deviceKey }, resetTitle, true);
      this._ledScheduleRowsOverride = [];
      this.ledScheduleEditorOpen = false;
      await this.addLedHistory(`${this.tr("led_schedule_sent_action")} ok`, this.tr("schedule_deleted"), null, { status: "ok" });
      await this.persistLedDeviceStatus({
        mode: "automatic",
        scheduleState: "empty",
        scheduleCount: 0,
        source: "scheduler_reset",
        action: this.tr("schedule_deleted"),
      });
      this.render();
    }
  }

  async resetLedDeviceSchedule(debugOverride = null, targetDevice = this.activeLedDevice || {}) {
    const debug = debugOverride === null ? Boolean(this._ledScheduleResetDebug) : Boolean(debugOverride);
    const data = { debug, preserve_local: true, ...this.ledServiceSelector(targetDevice) };
    const ok = await this.callLedService("reset_schedule", data, this.tr("led_reset_device_question"), { debug });
    this._ledScheduleResetDebug = false;
    if (ok) {
      await this.addLedHistory(
        `${this.tr("led_schedule_sent_action")} ok`,
        this.tr("schedules_device_deleted_local_kept"),
        null,
        { status: "ok" },
      );
      await this.persistLedDeviceStatus({
        mode: "automatic",
        scheduleState: "empty",
        scheduleCount: 0,
        source: "scheduler_reset",
        action: this.tr("schedules_device_deleted_local_kept"),
      });
      this.render();
    }
    return ok;
  }

  async sendLedScheduleRowFromFront(rowIndex) {
    if (!this._hass) return;
    const rows = this.ledScheduleRows();
    const index = Number(rowIndex);
    const row = Number.isInteger(index) ? rows[index] : null;
    if (!row) return;
    const period = this.ledSchedulePeriodsFromRows([row], this.activeLedDevice || {}, true)[0];
    const debug = Boolean(this.uiSettings && this.uiSettings.dashboardDebug);
    const title = `${this.tr("led_schedule_save_send")}\n1 ${this.tr("led_schedule_rows")}`;
    const result = await this.runLedScheduleService({
      service: "set_schedule",
      data: { periods: [period], send: true, ...this.ledServiceSelector() },
      title,
      debug,
      dialog: true,
    });
    const ok = Boolean(result && result.ok);
    if (ok) {
      const address = this.activeLedDevice && this.activeLedDevice.address ? this.activeLedDevice.address : undefined;
      const deviceKey = this.ledScheduleDeviceKey();
      const localPeriods = this.ledSchedulePeriodsFromRows(rows);
      await this.saveLedScheduleLocal(
        { periods: localPeriods, send: false, device_key: deviceKey, ...(address ? { address } : {}) },
        title,
        true,
      );
    }
    await this.addLedHistory(
      `${this.tr("led_schedule_sent_action")} ${ok ? "ok" : "fail"}`,
      this.ledScheduleSentDetail([index]),
      null,
      { status: ok ? "ok" : "fail" },
    );
    this.dialogState = {
      type: "debug",
      channel: 1,
      output: debug && result && result.output
        ? result.output
        : (ok ? this.ledScheduleSuccessDialogOutput(this.tr("led_schedule_save_send"), 1, true) : String(result && result.output ? result.output : `FAIL\n${title}`)),
      running: false,
      noChannel: true,
      level: ok ? "ok" : "error",
    };
    this.render();
  }

  async callLedService(service, data, title, options = {}) {
    if (typeof this.callAddonServiceWithDialog === "function") {
      const result = await this.callAddonServiceWithDialog(service, data, {
        ...options,
        channel: 1,
        noChannel: true,
        title,
        payload: data,
      });
      return Boolean(result && result.ok);
    }
    return false;
  }

  ledSchedulePeriodsFromRows(rows, device = this.activeLedDevice || {}, protocol = false) {
    return (Array.isArray(rows) ? rows : []).map((row) => {
      const rampMinutes = this.normalizeLedRampMinutes(row.ramp);
      const period = {
        start: row.start,
        end: row.end,
        brightness: this.ledScheduleLevelsForDevice(row.levels, device),
        levels: this.ledScheduleLevelsForDevice(row.levels, device),
        ramp_up_minutes: rampMinutes,
        weekdays: row.weekdays || ["everyday"],
      };
      if (row.active === false) period.active = false;
      return period;
    });
  }

  syncLocalLedScheduleCache(rows, storageKey = "") {
    const explicitKey = String(storageKey || "").trim().toUpperCase();
    const keys = explicitKey ? [explicitKey] : this.ledScheduleStorageKeys();
    if (!keys.length) return;
    this.config = this.config || {};
    this.config.addon_database = this.config.addon_database || {};
    this.config.addon_database.led_schedules = this.config.addon_database.led_schedules || {};
    const normalizedRows = (Array.isArray(rows) ? rows : []).map((row, index) => ({
      index,
      start: String(row && row.start ? row.start : "08:00"),
      end: String(row && row.end ? row.end : "20:00"),
      levels: this.normalizeLedScheduleLevels(row && row.levels),
      ramp: this.normalizeLedRampMinutes(row && row.ramp),
      weekdays: this.normalizeLedWeekdays(row && row.weekdays),
      active: row && row.active !== false,
      sent: false,
      updated_at: "",
    }));
    keys.forEach((key) => {
      this.config.addon_database.led_schedules[key] = normalizedRows.map((row) => ({ ...row }));
    });
  }

  async saveLedScheduleLocal(data, title, silent = false) {
    try {
      const response = await fetch("./api/led-schedule-local", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(data || {}),
      });
      const payload = await response.json();
      const serviceResponse = payload && payload.result ? payload.result.response || {} : {};
      const ok = Boolean(serviceResponse && serviceResponse.ok);
      if (ok) {
        const periods = Array.isArray(data && data.periods) ? data.periods : [];
        this.syncLocalLedScheduleCache(periods.map((period) => ({
          start: period && period.start ? period.start : "08:00",
          end: period && period.end ? period.end : "20:00",
          levels: period && (period.levels || period.brightness) ? (period.levels || period.brightness) : {},
          ramp: period && period.ramp_up_minutes !== undefined ? period.ramp_up_minutes : 1,
          weekdays: period && period.weekdays ? period.weekdays : ["everyday"],
          active: !(period && period.active === false),
        })), data && (data.address || data.device_key) ? String(data.address || data.device_key) : "");
        if (window.ChihirosAddonApi && typeof window.ChihirosAddonApi.refreshDashboard === "function") {
          await window.ChihirosAddonApi.refreshDashboard();
        }
      }
      if (silent) return ok;
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: [
          ok ? "OK" : "FAIL",
          title,
          serviceResponse && serviceResponse.send_status ? `Status: ${serviceResponse.send_status}` : "",
          serviceResponse && serviceResponse.send_detail ? `${this.tr("reply")}: ${serviceResponse.send_detail}` : "",
        ].filter(Boolean).join("\n"),
        running: false,
        noChannel: true,
        level: ok ? "ok" : "error",
      };
      this.render();
      return ok;
    } catch (err) {
      if (silent) return false;
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: `FAIL\n${title}\n${err && err.message ? err.message : err}`,
        running: false,
        noChannel: true,
        level: "error",
      };
      this.render();
      return false;
    }
  }

  ledScheduleSuccessDialogOutput(title, rows, send = true) {
    const rowCount = `${rows} ${this.tr("led_schedule_rows")}`;
    const lines = [
      "OK",
      String(title || "").trim(),
      `Status: ${send ? "ok" : "local"}`,
      `${this.tr("reply")}: ${send ? this.tr("reply_sent") : this.tr("reply_local")}`,
    ];
    if (send) {
      lines.push("", this.tr("led_schedule_saved"), `${this.tr("status")}: ok`, `${this.tr("reply")}: ${this.tr("reply_sent")}`, "", `${rowCount} ${this.tr("led_schedule_sent")}`);
    }
    return lines.filter(Boolean).join("\n");
  }

  async runLedScheduleService({ service = "set_schedule", data = {}, title = "", debug = false, dialog = false } = {}) {
    if (typeof this.runDeviceService !== "function") return { ok: false, output: `${title}\n${this.tr("service_unavailable")}` };
    const result = await this.runDeviceService({ service, data, title, debug, dialog, channel: 1, noChannel: true });
    if (result && result.ok && data.send !== false) {
      const periods = Array.isArray(data.periods) ? data.periods : this.ledSchedulePeriodsFromRows(this.ledScheduleRows());
      const scheduleCount = periods.filter((period) => period && period.active !== false).length;
      await this.persistLedDeviceStatus({
        mode: "automatic",
        scheduleState: scheduleCount > 0 ? "active" : "empty",
        scheduleCount,
        source: "scheduler",
        action: title || service,
        channels: this.ledScheduledChannels(periods),
      });
    }
    return result;
  }

  async deleteLedScheduleRow(rowIndex = null, send = true) {
    if (this._ledScheduleSubmitting) return false;
    const debugControl = this.querySelector("[data-led-schedule-debug]");
    const debug = debugControl
      ? Boolean(debugControl.checked)
      : Boolean(this.dialogState && this.dialogState.ledScheduleDebug) || Boolean(this.uiSettings && this.uiSettings.dashboardDebug);
    const currentRows = this.ledScheduleRows();
    const index = Number.isInteger(rowIndex) && rowIndex >= 0 ? rowIndex : (
      this.dialogState && this.dialogState.type === "led-schedule" && Number.isInteger(this.dialogState.ledScheduleEditIndex) && this.dialogState.ledScheduleEditIndex >= 0
        ? this.dialogState.ledScheduleEditIndex
        : null
    );
    const deviceKey = this.ledScheduleDeviceKey();
    if (!Number.isInteger(index) || index < 0 || index >= currentRows.length) {
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: `FAIL\n${this.tr("delete")}\n${this.tr("no_schedule_read")}`,
        running: false,
        noChannel: true,
        level: "error",
      };
      this.render();
      return false;
    }
    const deletedRow = currentRows[index];
    const remainingRows = currentRows.filter((_row, currentIndex) => currentIndex !== index);
    if (send) {
      this._ledScheduleSubmitting = true;
    } else {
      this._ledScheduleRowsOverride = remainingRows;
      this.ledScheduleEditorOpen = false;
      this.ledScheduleEditIndex = null;
    }
    if (!remainingRows.length && !send) {
      const address = this.activeLedDevice && this.activeLedDevice.address ? this.activeLedDevice.address : undefined;
      const ok = await this.saveLedScheduleLocal(
        address ? { address, periods: [], send: false, device_key: deviceKey } : { periods: [], send: false, device_key: deviceKey },
        this.tr("delete_send")
      );
      if (ok) this.render();
      return ok;
    }
    const address = this.activeLedDevice && this.activeLedDevice.address ? this.activeLedDevice.address : undefined;
    const deletePeriod = this.ledSchedulePeriodsFromRows(
      [{ ...deletedRow, active: false }],
      this.activeLedDevice || {},
      true,
    )[0] || {};
    const serviceData = send
      ? { ...deletePeriod, delete_only: true, device_key: deviceKey, ...this.ledServiceSelector() }
      : { periods: this.ledSchedulePeriodsFromRows(remainingRows), send: false, device_key: deviceKey };
    if (!send && address) serviceData.address = address;
    const title = `${this.tr("delete_send")}\n1 ${this.tr("led_schedule_rows")}`;
    if (send) {
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: this.tr("debug_sending"),
        running: true,
        debug,
        noChannel: true,
        level: "pending",
      };
      this.render();
    }
    const sendResult = send
      ? await this.runLedScheduleService({ service: "add_schedule", data: serviceData, title, debug, dialog: true })
      : null;
    const ok = send
      ? Boolean(sendResult && sendResult.ok)
      : await this.saveLedScheduleLocal(serviceData, title);
    if (ok) {
      if (send) {
        const localData = { periods: this.ledSchedulePeriodsFromRows(remainingRows), send: false, device_key: deviceKey };
        if (address) localData.address = address;
        await this.saveLedScheduleLocal(localData, title, true);
        this._ledScheduleRowsOverride = remainingRows;
      }
      await this.addLedHistory(
        send ? `${this.tr("led_schedule_sent_action")} ok` : this.tr("schedule_local_deleted"),
        this.ledScheduleDeletedDetail(index),
        null,
        { status: send ? "ok" : "" },
      );
      if (send) {
        this.ledScheduleEditorOpen = false;
        this.ledScheduleEditIndex = null;
        this.dialogState = {
          type: "debug",
          channel: 1,
          output: sendResult && sendResult.output
            ? sendResult.output
            : `OK\n${title}\n${this.tr("status")}: ok\n${this.tr("reply")}: ${this.tr("reply_sent")}`,
          running: false,
          debug,
          noChannel: true,
          level: "ok",
        };
      }
      this.render();
    } else {
      if (send) {
        this.ledScheduleEditorOpen = false;
        this.ledScheduleEditIndex = null;
        this.dialogState = {
          type: "debug",
          channel: 1,
          output: sendResult && sendResult.output ? sendResult.output : `FAIL\n${title}\n${this.tr("send_failed")}`,
          running: false,
          noChannel: true,
          level: "error",
        };
      }
      this._ledScheduleRowsOverride = null;
      this.render();
    }
    this._ledScheduleSubmitting = false;
    this.render();
    return ok;
  }

  ledEntityState(entity, fallback = "-") {
    const state = entity && this._hass && this._hass.states ? this._hass.states[entity] : null;
    if (!state) return fallback;
    if (state.state === "on") return this.tr("on");
    if (state.state === "off") return this.tr("off");
    return String(state.state || fallback);
  }

  formatLedRuntime(value) {
    const totalMinutes = Number.parseInt(String(value), 10);
    if (!Number.isFinite(totalMinutes) || totalMinutes < 0) return String(value || "-");
    const days = Math.floor(totalMinutes / 1440);
    const hours = Math.floor((totalMinutes % 1440) / 60);
    const minutes = totalMinutes % 60;
    const parts = [];
    if (days) parts.push(`${days} ${this.tr(days === 1 ? "runtime_day" : "runtime_days")}`);
    if (hours) parts.push(`${hours} ${this.tr("runtime_hour_short")}`);
    if (minutes || !parts.length) parts.push(`${minutes} ${this.tr("runtime_minute_short")}`);
    return `${totalMinutes >= 5000 ? "≥ " : ""}${parts.join(" ")}`;
  }

  formatLedNotificationTime(device = this.activeLedDevice || {}) {
    const entity = this.resolveLedNotificationEntity(device);
    const state = entity && this._hass && this._hass.states ? this._hass.states[entity] : null;
    const timestamp = state && (state.last_updated || state.last_changed);
    const date = timestamp ? new Date(timestamp) : null;
    if (!date || Number.isNaN(date.getTime())) return "-";
    const configuredTimeZone = String(this._hass && this._hass.config && this._hass.config.time_zone || "").trim();
    return new Intl.DateTimeFormat(this.language() === "de" ? "de-DE" : "en-US", {
      dateStyle: "short",
      timeStyle: "short",
      ...(configuredTimeZone ? { timeZone: configuredTimeZone } : {}),
    }).format(date);
  }

  resolveLedRuntimeEntity(device = this.activeLedDevice || {}) {
    const states = this._hass && this._hass.states ? this._hass.states : {};
    const explicit = String(device && device.runtime_entity ? device.runtime_entity : "");
    const firmwareDerived = String(device && device.firmware_entity ? device.firmware_entity : "")
      .replace(/_firmware_version$/, "_runtime");
    const id = String(device && device.id ? device.id : "").trim().toLowerCase().replace(/[^a-z0-9_]/g, "");
    const idDerived = id ? `sensor.${id}_runtime` : "";
    for (const candidate of [explicit, firmwareDerived, idDerived]) {
      if (candidate && states[candidate]) return candidate;
    }
    const addressToken = String(device && device.address ? device.address : "").toLowerCase().replace(/[^a-f0-9]/g, "");
    return Object.keys(states).find((entityId) => {
      const normalized = String(entityId).toLowerCase();
      return normalized.startsWith("sensor.")
        && (normalized.endsWith("_runtime") || normalized.endsWith("_runtime_minutes"))
        && (!addressToken || normalized.replace(/[^a-f0-9]/g, "").includes(addressToken));
    }) || "";
  }

  resolveLedNotificationEntity(device = this.activeLedDevice || {}) {
    const states = this._hass && this._hass.states ? this._hass.states : {};
    const explicit = String(device && device.last_notification_entity ? device.last_notification_entity : "");
    if (explicit && states[explicit]) return explicit;
    const id = String(device && device.id ? device.id : "").trim().toLowerCase().replace(/[^a-z0-9_]/g, "");
    const candidate = id ? `sensor.${id}_last_notification` : "";
    if (candidate && states[candidate]) return candidate;
    const addressToken = String(device && device.address ? device.address : "").toLowerCase().replace(/[^a-f0-9]/g, "");
    if (!addressToken) return "";
    return Object.keys(states).find((entityId) => {
      const normalized = String(entityId).toLowerCase();
      const entityToken = normalized.replace(/[^a-f0-9]/g, "");
      return normalized.startsWith("sensor.") && normalized.endsWith("_last_notification")
        && entityToken.includes(addressToken);
    }) || "";
  }

  openLedNotificationDialog() {
    const device = this.activeLedDevice || {};
    this.dialogState = {
      type: "led-notification",
      ledDeviceId: String(device.id || ""),
      ledDeviceAddress: String(device.address || "").trim().toUpperCase(),
      notificationEntity: this.resolveLedNotificationEntity(device),
      scheduleRows: this.ledScheduleRows().map((row) => ({ ...row })),
    };
    this.render();
  }

  databaseDiagnosticsEnabled() {
    return Boolean(
      this.config
      && this.config.addon_mode
      && this.config.addon_database
      && this.config.addon_database.database_diagnostics_enabled,
    );
  }

  async openDatabaseStatusDialog() {
    this.dialogState = {
      type: "led-database-status",
      title: this.tr("database_status"),
      loading: true,
      result: null,
    };
    this.render();
    try {
      const api = window.ChihirosAddonApi;
      if (!api || typeof api.databaseStatus !== "function") throw new Error(this.tr("service_unavailable"));
      const device = this.activeLedDevice || {};
      const deviceKey = String(device.address || device.id || "").trim();
      const result = await api.databaseStatus(deviceKey);
      this.dialogState = {
        type: "led-database-status",
        title: this.tr("database_status"),
        loading: false,
        result,
      };
    } catch (err) {
      this.dialogState = {
        type: "led-database-status",
        title: this.tr("database_status"),
        loading: false,
        result: null,
        error: err && err.message ? err.message : String(err),
      };
    }
    this.render();
  }

  databaseStatusCell(column, value) {
    const text = String(value ?? "").trim();
    if (!text) return "-";
    if (column === "levels" || column === "target") {
      try {
        const parsed = JSON.parse(text);
        if (column === "target" && parsed && typeof parsed === "object") {
          const levels = parsed.levels && typeof parsed.levels === "object"
            ? Object.entries(parsed.levels).map(([key, level]) => `${key}: ${level}`).join(" · ")
            : "";
          return [`${parsed.start || "-"} - ${parsed.end || "-"}`, levels].filter(Boolean).join(" · ");
        }
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          return Object.entries(parsed).map(([key, level]) => `${key}: ${level}`).join(" · ") || "-";
        }
      } catch (_err) {
        return text;
      }
    }
    if (column === "restore_rows") {
      try {
        const parsed = JSON.parse(text);
        return Array.isArray(parsed) ? `${parsed.length} ${this.tr("database_rows")}` : text;
      } catch (_err) {
        return text;
      }
    }
    if (column === "ramp_minutes") return `${text} min`;
    if (column === "active") return this.tr(text === "active" ? "active" : "inactive");
    if (column === "verification") {
      const key = text === "verified" ? "verified" : (text === "failed" ? "failed" : "not_checked");
      return this.tr(key);
    }
    if (["verified_at", "due_at", "created_at"].includes(column)) {
      const timestamp = /(?:Z|[+-]\d\d:\d\d)$/.test(text) ? text : `${text.replace(" ", "T")}Z`;
      const date = new Date(timestamp);
      if (!Number.isNaN(date.getTime())) {
        const configuredTimeZone = String(this._hass && this._hass.config && this._hass.config.time_zone || "").trim();
        return new Intl.DateTimeFormat(this.language() === "de" ? "de-DE" : "en-US", {
          dateStyle: "short",
          timeStyle: "medium",
          ...(configuredTimeZone ? { timeZone: configuredTimeZone } : {}),
        }).format(date);
      }
    }
    return text;
  }

  databaseStatusDialog() {
    const state = this.dialogState || {};
    const result = state.result && typeof state.result === "object" ? state.result : {};
    const requests = Array.isArray(result.requests) ? result.requests : [];
    let bodyHtml = `<div class="database-status-loading">${this.escapeHtml(this.tr("loading"))}</div>`;
    if (!state.loading) {
      if (state.error || result.error) {
        bodyHtml = `<div class="database-status-error">${this.escapeHtml(state.error || result.error)}</div>`;
      } else {
        bodyHtml = requests.map((request, index) => {
          const columns = Array.isArray(request.columns) ? request.columns : [];
          const rows = Array.isArray(request.rows) ? request.rows : [];
          const requestName = request.name === "verification_jobs"
            ? this.tr("database_verification_jobs")
            : this.tr("database_stored_schedules");
          const table = rows.length ? `
            <div class="database-result-table-wrap">
              <table class="database-result-table">
                <thead><tr>${columns.map((column) => `<th>${this.escapeHtml(this.tr(`database_column_${column}`))}</th>`).join("")}</tr></thead>
                <tbody>${rows.map((row) => `<tr>${columns.map((column) => `<td>${this.escapeHtml(this.databaseStatusCell(column, row && row[column]))}</td>`).join("")}</tr>`).join("")}</tbody>
              </table>
            </div>` : `<p class="database-empty-result">${this.escapeHtml(this.tr("database_no_rows"))}</p>`;
          return `
            <section class="database-request-card">
              <header>
                <div><small>${this.escapeHtml(this.tr("database_request"))} ${index + 1}</small><h3>${this.escapeHtml(requestName)}</h3></div>
                <span class="database-request-status ${request.status === "ok" ? "ok" : "fail"}">${this.escapeHtml(String(request.status || "-").toUpperCase())}</span>
              </header>
              <h4>${this.escapeHtml(this.tr("database_result"))} · ${rows.length} ${this.escapeHtml(this.tr("database_rows"))}</h4>
              ${table}
            </section>`;
        }).join("") || `<p class="database-empty-result">${this.escapeHtml(this.tr("database_no_rows"))}</p>`;
      }
    }
    return this.sharedModalDialog({
      title: this.tr("database_status"),
      sectionClass: "modal card led-database-status-dialog",
      headerHtml: `
        <header class="led-channel-history-head">
          <div><h2>${this.escapeHtml(this.tr("database_status"))}</h2><small>${this.escapeHtml(String(result.device || (this.activeLedDevice && this.activeLedDevice.address) || "-"))}</small></div>
          <button type="button" class="led-channel-history-close" data-action="close-dialog" title="${this.escapeHtml(this.tr("close"))}" aria-label="${this.escapeHtml(this.tr("close"))}"><span aria-hidden="true">&#10005;</span></button>
        </header>`,
      bodyHtml: `<div class="database-request-list">${bodyHtml}</div>`,
    });
  }

  ledNotificationDialog() {
    const entity = String(this.dialogState && this.dialogState.notificationEntity || "");
    const state = entity && this._hass && this._hass.states ? this._hass.states[entity] : null;
    const attrs = state && state.attributes && typeof state.attributes === "object" ? state.attributes : {};
    const stateValue = String(state && state.state ? state.state : "").trim();
    const notifications = Array.isArray(attrs.notifications) && attrs.notifications.length ? attrs.notifications : [attrs];
    return window.ChihirosNotificationUi.render(this, {
      notifications,
      stateValue,
      describe: (model) => {
        if (model.mode !== 0xFE) return {};
        const points = [];
        for (let offset = 25; offset + 2 < model.bytes.length - 1; offset += 3) {
          const hour = model.bytes[offset];
          const minute = model.bytes[offset + 1];
          const level = model.bytes[offset + 2];
          if (hour <= 23 && minute <= 59 && level <= 100 && (hour || minute || level)) {
            points.push({ time: `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`, level });
          }
        }
        const ranges = this.ledScheduleRangesFromPoints(points);
        const localRows = (Array.isArray(this.dialogState && this.dialogState.scheduleRows)
          ? this.dialogState.scheduleRows
          : []).filter((row) => row && row.active !== false);
        const details = ranges.map((range, rangeIndex) => (
          `${this.tr("schedule")} ${rangeIndex + 1}: ${range.start}-${range.end}, ${range.level} %`
        ));
        details.push(...localRows.map((row, rowIndex) => (
          `${this.tr("template_local")} · ${this.tr("schedule")} ${rowIndex + 1}: ${row.start}-${row.end} ${this.ledScheduleRowText(row)}`
        )));
        return {
          parsedType: "LED_SCHEDULE_SNAPSHOT",
          meaning: `${this.tr("device")}: ${ranges.length} ${this.tr("schedule_count")} · ${this.tr("template_local")}: ${localRows.length} ${this.tr("schedule_count")}`,
          details,
        };
      },
    });
  }

  ledDeviceFeedbackStatus(device = this.activeLedDevice || {}) {
    const states = this._hass && this._hass.states ? this._hass.states : {};
    const entities = [this.resolveLedRuntimeEntity(device), this.resolveLedNotificationEntity(device)].filter(Boolean);
    const feedback = entities.map((entityId) => states[entityId]).filter((state) => {
      const value = String(state && state.state ? state.state : "").toLowerCase();
      return state && value !== "unknown" && value !== "unavailable";
    });
    const latest = feedback.reduce((result, state) => {
      const parsed = Date.parse(String(state.last_updated || state.last_changed || ""));
      return Number.isFinite(parsed) ? Math.max(result, parsed) : result;
    }, 0);
    const online = Boolean(feedback.length) && (!latest || Date.now() - latest <= 20 * 60 * 1000);
    return { online, latest };
  }

  ledAutoModeIsOn(device = this.activeLedDevice || {}) {
    const persisted = this.ledPersistedDeviceStatus();
    const mode = String(persisted && persisted.mode ? persisted.mode : "").trim().toLowerCase();
    if (mode === "automatic" || mode === "auto") return true;
    if (mode === "manual") return false;
    const entity = String(device && device.auto_entity ? device.auto_entity : "");
    const state = entity && this._hass && this._hass.states ? this._hass.states[entity] : null;
    if (state && state.state === "on") return true;
    if (state && state.state === "off") return false;
    return false;
  }

  ledAutoModeState(device = this.activeLedDevice || {}) {
    return this.ledAutoModeIsOn(device) ? this.tr("on") : this.tr("off");
  }

  ledChannelDisplayName(channel) {
    const key = String(channel && (channel.key || channel.name) || "").toLowerCase();
    if (key.includes("red") || key.includes("rot")) return this.tr("red");
    if (key.includes("green") || key.includes("gruen") || key.includes("grün")) return this.tr("green");
    if (key.includes("blue") || key.includes("blau")) return this.tr("blue");
    if (key.includes("white") || key.includes("weiss") || key.includes("weiß")) return this.tr("white");
    return String(channel && channel.name ? channel.name : "");
  }

  ledChannelCard(channel) {
    const value = this.ledChannelValue(channel);
    const max = this.ledMaxBrightness();
    const channelName = this.ledChannelDisplayName(channel);
    const showWatts = this.supportsLedWattEstimates();
    const watts = this.ledChannelEstimatedWatts(channel, value);
    return `
      <section class="card led-channel" style="--led-color:${channel.color}">
        <div class="led-channel-head">
          <h2>CH${channel.id} ${this.escapeHtml(channelName)}</h2>
          <strong>${value} / ${max} %</strong>
        </div>
        <div class="led-channel-body">
          <div class="led-channel-head-actions">
            <button class="led-channel-toggle ${value > 0 ? "active" : ""}" type="button" data-led-channel-action="${value > 0 ? "off" : "on"}" data-led-device-channel="${channel.id}" role="switch" aria-checked="${value > 0 ? "true" : "false"}" title="${this.escapeHtml(`${channelName} ${value > 0 ? this.tr("off") : this.tr("on")}`)}">
              <span class="led-channel-toggle-track"><span></span></span>
              <b>${this.tr(value > 0 ? "on" : "off")}</b>
            </button>
          </div>
          ${showWatts ? `<span class="led-channel-watt" title="${this.escapeHtml(this.tr("estimated_power"))}"><span class="led-watt-bolt" aria-hidden="true">⚡</span><span data-led-channel-watts="${channel.id}">${value > 0 ? `≈ ${this.ledWattFormat(watts)} W` : "0 W"}</span></span>` : ""}
          <button class="led-channel-history-button" type="button" data-led-channel-history="${channel.id}" title="${this.tr("history")}" aria-label="${this.tr("history")}"><ha-icon icon="mdi:history"></ha-icon><span>${this.tr("history")}</span></button>
        </div>
        <div class="led-channel-control">
          <input type="range" min="0" max="${max}" step="1" value="${value}" data-led-number="${this.escapeHtml(channel.entity || "")}" data-led-device-channel="${channel.id}">
          <input class="led-channel-value-input" type="number" min="0" max="${max}" step="1" value="${value}" data-led-number="${this.escapeHtml(channel.entity || "")}" data-led-device-channel="${channel.id}">
        </div>
      </section>`;
  }

  async addLedHistory(action, detail = "", channel = null, options = null) {
    if (typeof this.addCoreHistory !== "function") return null;
    return this.addCoreHistory(action, detail, channel, {
      ...(options && typeof options === "object" ? options : {}),
      device: this.ledHistoryDeviceKey(),
      scope: "led",
      overlayKey: "ledHistoryOverlay",
      limit: 200,
      refresh: () => this.fetchLedHistory(true),
    });
  }

  ledHistorySortValue(entry) {
    if (!entry || typeof entry !== "object") return 0;
    const ts = String(entry.ts || "").trim();
    if (ts) {
      const parsed = Date.parse(ts);
      if (Number.isFinite(parsed)) return parsed;
    }
    const date = String(entry.date || "").trim();
    const time = String(entry.time || "").trim();
    if (date || time) {
      const parsed = Date.parse(`${date || "1970-01-01"}T${time || "00:00:00"}`);
      if (Number.isFinite(parsed)) return parsed;
    }
    return 0;
  }

  sortLedHistoryRows(rows) {
    return [...rows].sort((left, right) => this.ledHistorySortValue(right) - this.ledHistorySortValue(left));
  }

  ledHistoryRows(limit = 8) {
    const rows = [];
    const overlay = Array.isArray(this.ledHistoryOverlay) ? this.ledHistoryOverlay : [];
    overlay.forEach((entry) => rows.push({ ...entry, color: "#03c9ff" }));
    const device = this.activeLedDevice || {};
    const lastState = device.last_notification_entity && this._hass ? this._hass.states[device.last_notification_entity] : null;
    const firmwareState = device.firmware_entity && this._hass ? this._hass.states[device.firmware_entity] : null;
    const runtimeEntity = this.resolveLedRuntimeEntity(device);
    const runtimeState = runtimeEntity && this._hass ? this._hass.states[runtimeEntity] : null;
    if (lastState) {
      rows.push({
        action: this.tr("last_notification"),
        detail: `${lastState.state || "-"} ${lastState.attributes && lastState.attributes.parsed_type ? lastState.attributes.parsed_type : ""}`.trim(),
        color: "#2ea8ff",
      });
    }
    if (firmwareState) {
      rows.push({ action: this.tr("firmware"), detail: String(firmwareState.state || "-"), color: "#39d353" });
    }
    if (runtimeState) {
      rows.push({
        action: this.tr("runtime"),
        detail: `${runtimeState.state || "-"} min`,
        timestamp: runtimeState.last_updated || runtimeState.last_changed || "",
        color: "#f0b429",
      });
    }
    return this.sortLedHistoryRows(rows).slice(0, limit);
  }

  ledHistoryPanel() {
    const rows = this.ledHistoryRows(10);
    return `
      <section class="card history-card led-history-card">
        <h2 class="card-title-action">
          <span>${this.tr("history_total")}</span>
          <button class="mini eye-action" data-action="dialog:led-history-all:1" title="${this.tr("history_total")}"><ha-icon icon="mdi:eye"></ha-icon></button>
        </h2>
        ${this.ledHistoryTimelineMarkup(rows, false)}
      </section>`;
  }

  ledHistoryTimelineMarkup(rows, expanded = false) {
    return this.sharedHistoryTimelineMarkup(rows, {
      emptyLabel: this.tr("led_no_history"),
      expanded,
      color: "#03c9ff",
    });
  }

  ledChannelHistoryRows(channelId, limit = 120) {
    const channel = (this.ledChannels || []).find((item) => Number(item.id) === Number(channelId));
    const entity = channel && channel.entity ? String(channel.entity) : "";
    const rows = (Array.isArray(this.ledHistoryOverlay) ? this.ledHistoryOverlay : [])
      .filter((entry) => Number(entry.channel || 0) === Number(channelId) || (entity && String(entry.detail || "").includes(entity)))
      .map((entry) => ({ ...entry, color: channel && channel.color ? channel.color : "#03c9ff" }));
    return this.sortLedHistoryRows(rows).slice(0, limit);
  }

  ledChannelHistoryDialog() {
    const channelId = this.dialogState && this.dialogState.channel;
    const channel = (this.ledChannels || []).find((item) => Number(item.id) === Number(channelId)) || {};
    const rows = this.ledChannelHistoryRows(channelId, 120);
    const channelName = this.ledChannelDisplayName(channel);
    const color = channel.color || "#03c9ff";
    const items = rows.map((entry) => {
      const detail = String(entry && entry.detail ? entry.detail : "");
      const valueMatch = detail.match(/:\s*(\d+)\s*\/\s*(\d+)/);
      const value = valueMatch ? `${valueMatch[1]} / ${valueMatch[2]}` : "-";
      const switchedOff = /(?:kanal\s+aus|channel\s+off|switch-off)/i.test(`${entry && entry.action ? entry.action : ""} ${detail}`);
      const action = switchedOff ? this.tr("channel_switched_off") : this.tr("brightness_changed");
      const timestamp = String(
        entry && entry.timestamp
        || entry && entry.ts
        || [entry && entry.date ? entry.date : "", entry && entry.time ? entry.time : ""].filter(Boolean).join(" ")
        || ""
      );
      return `
        <article class="led-channel-history-entry">
          <span class="led-channel-history-dot" style="background:${this.escapeHtml(color)};color:${this.escapeHtml(color)}"></span>
          <div class="led-channel-history-copy">
            <strong>${this.escapeHtml(action)}</strong>
            <time>${this.escapeHtml(this.formatHistoryTimestamp(timestamp))}</time>
          </div>
          <span class="led-channel-history-value" style="color:${this.escapeHtml(color)}">${this.escapeHtml(value)}</span>
        </article>`;
    }).join("");
    return this.sharedModalDialog({
      title: `${this.tr("history")} · CH${this.escapeHtml(channel.id || channelId)} ${this.escapeHtml(channelName)}`,
      sectionClass: "modal card history-modal led-channel-history-modal",
      headerHtml: `
        <header class="led-channel-history-head">
          <h2>${this.tr("history")} · CH${this.escapeHtml(channel.id || channelId)} ${this.escapeHtml(channelName)}</h2>
          <button type="button" class="led-channel-history-close" data-action="close-dialog" title="${this.escapeHtml(this.tr("close"))}" aria-label="${this.escapeHtml(this.tr("close"))}"><span aria-hidden="true">&#10005;</span></button>
        </header>`,
      bodyHtml: rows.length
        ? `<div class="led-channel-history-list">${items}</div>`
        : `<div class="history-empty"><ha-icon icon="mdi:history"></ha-icon><span>${this.tr("led_no_history")}</span></div>`,
    });
  }

  ledHistoryAllDialog() {
    const rows = this.filterHistoryEntries(this.ledHistoryRows(200), "led");
    return this.sharedModalDialog({
      title: this.tr("history_total"),
      sectionClass: "modal card history-modal led-history-all-modal",
      headerHtml: `
        <header class="led-channel-history-head">
          <h2>${this.tr("history_total")}</h2>
          <div class="history-dialog-head-actions">
            ${this.historyFiltersMarkup("led")}
            <button type="button" class="led-channel-history-close" data-action="close-dialog" title="${this.escapeHtml(this.tr("close"))}" aria-label="${this.escapeHtml(this.tr("close"))}"><span aria-hidden="true">&#10005;</span></button>
          </div>
        </header>`,
      bodyHtml: this.ledHistoryTimelineMarkup(rows, true),
    });
  }

  ledScheduleTable() {
    const scheduleRows = this.ledScheduleEditorRows();
    const limitClass = scheduleRows.length > 5 ? " scroll-limit-5" : "";
    const max = this.ledMaxBrightness();
    const debugChecked = Boolean(this.dialogState && this.dialogState.ledScheduleDebug);
    const scheduleKeys = this.ledSupportedScheduleKeys();
    const checkControl = (name, label, checked = true) => `
            <div class="led-schedule-color-control color-toggle led-schedule-toggle-control led-schedule-${name}-control">
              <label><span>${label}</span></label>
              <label class="led-schedule-switch">
                <input type="checkbox" data-led-schedule-${name} ${checked ? "checked" : ""}>
                <span>${checked ? this.tr("on") : this.tr("off")}</span>
              </label>
            </div>`;
    const timePickerMarkup = (name, value) => {
      const clean = String(value || (name === "start" ? "08:00" : "20:00"));
      const [hour = "08", minute = "00"] = clean.split(":");
      const hours = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0"));
      const minutes = Array.from({ length: 12 }, (_, index) => String(index * 5).padStart(2, "0"));
      return `
              <strong class="led-schedule-time-field">
                <input type="time" data-led-schedule="${name}" value="${this.escapeHtml(clean)}">
                <button type="button" class="led-schedule-time-picker" data-led-time-picker="${name}" title="${this.escapeHtml(name === "start" ? this.tr("start_time") : this.tr("end_time"))}"><ha-icon icon="mdi:clock-outline"></ha-icon></button>
                <div class="led-time-picker-panel" data-led-time-panel="${name}">
                  <div class="led-time-picker-title">${name === "start" ? this.tr("start_time") : this.tr("end_time")}</div>
                  <div class="led-time-clock-face" aria-label="${this.escapeHtml(this.tr("hours"))}">
                    ${hours.map((item) => `<button type="button" class="${item === hour ? "active" : ""}" data-led-time-part="hour" data-led-time-value="${item}">${item}</button>`).join("")}
                  </div>
                  <div class="led-time-minute-row" aria-label="${this.escapeHtml(this.tr("minutes"))}">
                    ${minutes.map((item) => `<button type="button" class="${item === minute ? "active" : ""}" data-led-time-part="minute" data-led-time-value="${item}">${item}</button>`).join("")}
                  </div>
                  <div class="led-time-picker-actions">
                    <button type="button" data-led-time-cancel>${this.tr("cancel")}</button>
                    <button type="button" class="primary" data-led-time-apply>${this.tr("apply")}</button>
                  </div>
                </div>
              </strong>`;
    };
    const timeControl = (row) => `
            <div class="led-schedule-color-control color-time led-schedule-time-control">
              <label><span>${this.tr("time")}</span></label>
              <div class="led-schedule-row-title">
                <span class="led-schedule-time-action">${this.tr("on")}</span>
                ${timePickerMarkup("start", row.start || "08:00")}
                <span class="led-schedule-time-action">${this.tr("off")}</span>
                ${timePickerMarkup("end", row.end || "20:00")}
              </div>
            </div>`;
    const colorControl = (key, label, value, accentClass = "") => `
            <div class="led-schedule-color-control ${accentClass}">
              <label><span>${label}</span></label>
              <input type="range" min="0" max="${max}" step="1" data-led-schedule-control="${key}" data-led-schedule-kind="range" value="${value}">
              <input type="number" min="0" max="${max}" step="1" data-led-schedule-control="${key}" data-led-schedule-kind="number" value="${value}">
            </div>`;
    const templateControl = (row) => {
      const options = this.ledScheduleTemplateOptions();
      const current = this.ledScheduleTemplateForRow(row);
      const available = options.filter((option) => option.value !== "custom");
      return `
            <div class="led-schedule-color-control color-template led-schedule-template-control">
              <label><span>${this.tr("template")}</span></label>
              <select data-led-schedule-template ${available.length ? "" : "disabled"}>
                ${options.map((option) => `
                  <option value="${this.escapeHtml(option.value)}" ${option.value === current ? "selected" : ""}>${this.escapeHtml(option.label)}</option>
                `).join("")}
              </select>
            </div>`;
    };
    const rampOptions = [
      { value: 1, label: "1", title: "1 min" },
      { value: 30, label: "30", title: this.tr("minutes_30") },
      { value: 60, label: this.tr("hour_1_short"), title: this.tr("hour_1") },
      { value: 90, label: this.tr("hour_1_5_short"), title: this.tr("hour_1_5") },
      { value: 120, label: this.tr("hour_2_short"), title: this.tr("hour_2") },
      { value: 150, label: this.tr("hour_2_5_short"), title: this.tr("hour_2_5") },
    ];
    const rampControl = (value) => {
      const normalized = this.normalizeLedRampMinutes(value);
      return `
            <div class="led-schedule-color-control color-ramp led-schedule-ramp-control">
              <label class="led-schedule-ramp-title">
                <span>${this.tr("sunrise_sunset")}</span>
              </label>
              <div class="led-schedule-ramp-presets" role="group" aria-label="${this.escapeHtml(this.tr("ramp_templates"))}">
                ${rampOptions.map((option) => `
                  <button type="button" class="led-schedule-ramp-chip ${option.value === normalized ? "active" : ""}" data-led-schedule-control="ramp" data-led-schedule-kind="button" data-led-schedule-ramp="${option.value}" title="${this.escapeHtml(option.title)}">
                    <span>${option.label}</span>
                  </button>
                `).join("")}
              </div>
              <input type="hidden" data-led-schedule-control="ramp" data-led-schedule-kind="hidden" value="${normalized}">
            </div>`;
    };
    const weekdayControl = (row) => {
      const weekdays = new Set(this.normalizeLedWeekdays(row.weekdays || ["everyday"]));
      const weekdayAll = weekdays.has("everyday") || weekdays.size === 7;
      const weekdayAllMarkup = `
            <button type="button" class="weekday-chip weekday-all-chip ${weekdayAll ? "active" : ""}" data-led-schedule-weekday-all aria-pressed="${weekdayAll ? "true" : "false"}">
              <span>${this.tr("all")}</span>
            </button>`;
      const weekdayMarkup = this.ledWeekdayOptions().map(([value, label]) => `
            <button type="button" class="weekday-chip ${weekdayAll || weekdays.has(value) ? "active" : ""}" data-led-schedule-weekday value="${value}" aria-pressed="${weekdayAll || weekdays.has(value) ? "true" : "false"}">
              <span>${label}</span>
            </button>`).join("");
      return `
            <div class="led-schedule-color-control color-weekdays led-schedule-weekdays-control">
              <label class="weekday-all weekday-all-center"><span>${this.tr("run_weekdays")}</span></label>
              <div class="weekday-grid">
                ${weekdayAllMarkup}
                ${weekdayMarkup}
              </div>
            </div>`;
    };
    const rows = scheduleRows.map((row, index) => {
      const levels = this.normalizeLedScheduleLevels(row.levels || {});
      return `
        <article class="led-schedule-row-card" data-led-schedule-row="${index}">
          <div class="led-schedule-row-grid">
            ${checkControl("active", this.tr("active"), row.active !== false)}
            ${timeControl(row)}
            ${scheduleKeys.map((key) => colorControl(key, this.ledScheduleChannelLabel(key), levels[key], `color-${key}`)).join("")}
            ${templateControl(row)}
            ${rampControl(row.ramp ?? 1)}
          </div>
          ${weekdayControl(row)}
          ${checkControl("debug", this.tr("debug_capture"), debugChecked)}
        </article>`;
    }).join("");
    return `
      <div class="led-schedule-editor${limitClass}">
        <div class="led-schedule-card-list">${rows}</div>
      </div>`;
  }

  ledScheduleSummaryPanel() {
    const device = this.activeLedDevice || {};
    const scheduleKeys = this.ledSupportedScheduleKeys(device);
    const scheduleRows = this.ledScheduleRows();
    const limitClass = scheduleRows.length > 5 ? " scroll-limit-5" : "";
    const rows = scheduleRows.length ? scheduleRows.map((row, index) => {
      const levels = this.normalizeLedScheduleLevels(row.levels || {});
      const verification = this.ledScheduleRowVerification(row);
      const actions = this.sharedIconActionButtons([
        {
          attrs: `data-led-schedule-edit="${index}"`,
          title: this.tr("edit"),
          icon: "mdi:pencil",
        },
        {
          attrs: `data-led-schedule-delete="${index}"`,
          className: "danger",
          title: this.tr("delete_send"),
          icon: "mdi:calendar-remove",
        },
        {
          attrs: `data-led-schedule-send="${index}"`,
          className: "send",
          title: this.tr("save_send"),
          icon: "mdi:calendar-check",
        },
        {
          attrs: `data-led-schedule-share="${index}"`,
          title: this.tr("share"),
          icon: "mdi:share-variant",
        },
      ]);
      return `
        <tr>
          <td>${index + 1}</td>
          <td class="led-schedule-check-cell"><span class="led-schedule-check-dot ${verification.level}" title="${this.escapeHtml(verification.text)}" aria-label="${this.escapeHtml(verification.text)}"></span></td>
          <td>${this.escapeHtml(row.start || "08:00")} - ${this.escapeHtml(row.end || "20:00")}</td>
          ${scheduleKeys.map((key) => `<td>${Number(levels[key] || 0)} %</td>`).join("")}
          <td>${this.normalizeLedRampMinutes(row.ramp ?? 1)} min</td>
          <td>${this.escapeHtml(this.ledWeekdaysText(row.weekdays || ["everyday"]))}</td>
          <td>${actions}</td>
        </tr>`;
    }).join("") : "";
    const items = rows ? `
        <table class="led-schedule-front-table">
          <thead>
            <tr>
              <th>#</th>
              <th>${this.tr("check_short")}</th>
              <th>${this.tr("time")}</th>
              ${scheduleKeys.map((key) => `<th>${this.ledScheduleChannelLabel(key)}</th>`).join("")}
              <th>Ramp</th>
              <th>${this.tr("weekdays")}</th>
              <th>${this.tr("actions")}</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>` : `
        <div class="empty-state">${this.tr("no_schedule_read")}.</div>`;
    return `
      <section class="card schedule led-schedule-card">
        <div class="config-card-head">
          <div>
            <div class="led-schedule-title-row">
              <h2>${this.tr("led_scheduler")}</h2>
              <span class="led-schedule-count">${scheduleRows.length} ${this.tr("schedule_count")}</span>
            </div>
            <small>${this.tr("led_schedule_summary_subtitle")}</small>
          </div>
          <div class="led-schedule-header-actions">
            <button type="button" class="secondary danger" data-action="led-schedule-reset">
              <ha-icon icon="mdi:calendar-remove"></ha-icon><span>${this.tr("delete_all")}</span>
            </button>
            <button type="button" class="secondary" data-action="led-enable-auto-mode" ${device.auto_entity ? "" : "disabled"}>
              <ha-icon icon="mdi:calendar-sync"></ha-icon><span>${this.tr("enable_auto_mode")}</span>
            </button>
            <button type="button" class="secondary" data-led-schedule-new="1">
              <ha-icon icon="mdi:plus"></ha-icon><span>${this.tr("new")}</span>
            </button>
          </div>
        </div>
        <div class="led-schedule-summary-list${limitClass}">${items}</div>
      </section>`;
  }

  ledScheduleRangesFromPoints(normalized = []) {
    const ranges = [];
    const minuteDistance = (start, end) => {
      const [startHour, startMinute] = String(start).split(":").map(Number);
      const [endHour, endMinute] = String(end).split(":").map(Number);
      return ((endHour * 60 + endMinute) - (startHour * 60 + startMinute) + 1440) % 1440;
    };
    for (let index = 0; index < normalized.length;) {
      const first = normalized[index];
      let valueIndex = index;
      if (first.level === 0) valueIndex += 1;
      if (valueIndex >= normalized.length || normalized[valueIndex].level === 0) {
        index += 1;
        continue;
      }
      const level = normalized[valueIndex].level;
      let start = first.time;
      let ramp = first.level === 0 ? minuteDistance(first.time, normalized[valueIndex].time) : 1;
      if (first.level !== 0 && index > 0 && normalized[index - 1].level === 0) {
        const candidateRamp = minuteDistance(normalized[index - 1].time, first.time);
        if (candidateRamp >= 1 && candidateRamp <= 150) {
          start = normalized[index - 1].time;
          ramp = candidateRamp;
        }
      }
      let endIndex = valueIndex;
      while (endIndex + 1 < normalized.length && normalized[endIndex + 1].level === level) endIndex += 1;
      if (endIndex + 1 < normalized.length && normalized[endIndex + 1].level === 0) {
        const zeroIndex = endIndex + 1;
        ranges.push({ start, end: normalized[zeroIndex].time, level, ramp });
        const followingIndex = zeroIndex + 1;
        const [zeroHour, zeroMinute] = normalized[zeroIndex].time.split(":").map(Number);
        const followingMinutes = followingIndex < normalized.length
          ? normalized[followingIndex].time.split(":").map(Number).reduce((hour, minute) => hour * 60 + minute)
          : -1;
        const sharesBoundary = followingIndex < normalized.length
          && normalized[followingIndex].level !== 0
          && followingMinutes === (zeroHour * 60 + zeroMinute + 1) % 1440;
        index = sharesBoundary ? zeroIndex : followingIndex;
        continue;
      }
      if (endIndex + 1 >= normalized.length) {
        const [lastHour, lastMinute] = normalized[endIndex].time.split(":").map(Number);
        const nextMinute = (lastHour * 60 + lastMinute + 1) % 1440;
        const existingBoundary = normalized
          .slice(0, index)
          .find((point) => {
            if (point.level !== 0) return false;
            const [hour, minute] = point.time.split(":").map(Number);
            return hour * 60 + minute === nextMinute;
          });
        if (!existingBoundary) break;
        ranges.push({ start, end: existingBoundary.time, level, ramp });
        break;
      }
      const [hour, minute] = normalized[endIndex].time.split(":").map(Number);
      const endMinutes = first.level === 0 ? hour * 60 + minute + 1 : ((Number(first.time.slice(0, 2)) + 1) % 24) * 60;
      ranges.push({
        start,
        end: `${String(Math.floor((endMinutes % 1440) / 60)).padStart(2, "0")}:${String(endMinutes % 60).padStart(2, "0")}`,
        level,
        ramp,
      });
      index = endIndex + 1;
    }
    return ranges;
  }

  ledScheduleSnapshotRanges() {
    const device = this.activeLedDevice || {};
    const state = device.schedule_entity && this._hass && this._hass.states ? this._hass.states[device.schedule_entity] : null;
    const points = state && state.attributes && Array.isArray(state.attributes.points) ? state.attributes.points : [];
    const normalized = points.map((point) => {
      const levels = point && point.levels && typeof point.levels === "object" ? point.levels : {};
      return { time: String(point && point.time ? point.time : ""), level: Number(Object.values(levels)[0] || 0) };
    }).filter((point) => /^\d{2}:\d{2}$/.test(point.time));
    return this.ledScheduleRangesFromPoints(normalized);
  }

  ledScheduleRowVerification(row) {
    const storedStatus = String(row && row.verification_status ? row.verification_status : "").toLowerCase();
    if (storedStatus === "verified") return { level: "ok", text: this.tr("verified") };
    if (storedStatus === "failed") return { level: "fail", text: this.tr("mismatch") };
    if (storedStatus === "pending") return { level: "pending", text: this.tr("not_checked") };
    const ranges = this.ledScheduleSnapshotRanges();
    if (!ranges.length) return { level: "pending", text: this.tr("not_checked") };
    const levels = this.normalizeLedScheduleLevels(row && row.levels ? row.levels : {});
    const supportedLevels = this.ledSupportedScheduleKeys(this.activeLedDevice || {}).map((key) => Number(levels[key] || 0));
    const configuredRamp = this.normalizeLedRampMinutes(row && row.ramp);
    const expectedRamp = configuredRamp;
    const matches = ranges.some((range) => (
      range.start === row.start && range.end === row.end && range.ramp === expectedRamp && supportedLevels.includes(range.level)
    ));
    return matches
      ? { level: "ok", text: this.tr("verified") }
      : { level: "fail", text: this.tr("mismatch") };
  }

  ledScheduleDialog() {
    if (!this.dialogState || this.dialogState.type !== "led-schedule") return "";
    const scheduleRows = this.ledScheduleEditorRows();
    const rowCount = scheduleRows.length;
    const editIndex = Number.isInteger(this.dialogState.ledScheduleEditIndex) && this.dialogState.ledScheduleEditIndex >= 0
      ? this.dialogState.ledScheduleEditIndex
      : null;
    const isNewDialog = Boolean(this.dialogState && this.dialogState.type === "led-schedule" && this.dialogState.ledScheduleNew);
    const deleteAction = editIndex !== null ? `led-schedule-delete-row:${editIndex}` : "led-schedule-reset";
    const summary = this.ledScheduleSummary(scheduleRows);
    const message = String(this.dialogState.ledScheduleMessage || "").trim();
    const messageLevel = String(this.dialogState.ledScheduleMessageLevel || "error").trim();
    const visibleMessage = messageLevel === "error" ? message.replace(/^FAIL\s*\n/i, "").trim() : message;
    const messageIsStructuredDebug = message
      && typeof this.debugOutputSections === "function"
      && this.debugOutputSections(message).length > 1
      && typeof this.debugOutputMarkup === "function";
    const messageLevelClass = messageIsStructuredDebug ? "debug" : messageLevel;
    const messageBody = messageIsStructuredDebug
      ? this.debugOutputMarkup(message, "")
      : `<strong>${messageLevel === "error" ? "FAIL" : (messageLevel === "pending" ? this.tr("running") : this.tr("status"))}</strong>
              <pre>${this.escapeHtml(visibleMessage)}</pre>`;
    const submitting = Boolean(this._ledScheduleSubmitting);
    const currentDevice = this.activeLedDevice || {};
    const overviewCards = editIndex === null && !isNewDialog ? `
            <section class="led-schedule-side-card">
              <h3>${this.tr("current_plan")}</h3>
              <p>${this.escapeHtml(summary)}</p>
            </section>
            <section class="led-schedule-side-card compact">
              <h3>${this.tr("device")}</h3>
              <p>${this.escapeHtml(currentDevice.name || "LED")}</p>
              <small>${this.escapeHtml(currentDevice.model || "LED")}</small>
            </section>
            <section class="led-schedule-side-card compact">
              <h3>${this.tr("status")}</h3>
              <p>${rowCount} ${this.tr("led_schedule_rows")}</p>
              <small>${this.tr("max_range")} ${this.ledMaxBrightness()} ${this.tr("max_value").toLowerCase()}</small>
            </section>` : "";
    const metaChips = editIndex === null && !isNewDialog ? `
              <span class="dialog-chip">${rowCount} ${this.tr("led_schedule_rows")}</span>
              <span class="dialog-chip">${this.tr("max_value")} ${this.ledMaxBrightness()}</span>` : "";
    return `
      <div class="modal-backdrop">
        <section class="modal card led-schedule-modal">
          <header class="led-schedule-dialog-head">
            <div>
              <h2>${this.tr("led_scheduler")}</h2>
            </div>
            <div class="led-schedule-dialog-head-actions">
              ${metaChips ? `<div class="led-schedule-dialog-meta">${metaChips}</div>` : ""}
              <button type="button" class="led-schedule-dialog-close" data-action="close-dialog" title="${this.escapeHtml(this.tr("close"))}" aria-label="${this.escapeHtml(this.tr("close"))}" ${submitting ? "disabled" : ""}>
                <span aria-hidden="true">&#10005;</span>
              </button>
            </div>
          </header>
          <div class="led-schedule-dialog-body">
            ${message ? `<div class="led-schedule-dialog-message ${this.escapeHtml(messageLevelClass)}">
              ${messageBody}
            </div>` : ""}
            ${overviewCards}
            <div class="led-schedule-dialog-editor">
              ${this.ledScheduleTable()}
            </div>
          </div>
          <footer class="led-schedule-dialog-footer">
            ${isNewDialog ? "" : `<button type="button" class="secondary danger" data-action="${deleteAction}"><ha-icon icon="mdi:calendar-remove"></ha-icon><span>${this.tr("delete_send")}</span></button>`}
            <div class="led-schedule-dialog-actions">
              <button type="button" class="secondary" data-action="close-dialog" ${submitting ? "disabled" : ""}><ha-icon icon="mdi:close"></ha-icon><span>${this.tr("cancel")}</span></button>
              <button type="button" class="secondary" data-action="led-schedule-save-local" ${submitting ? "disabled" : ""}><ha-icon icon="mdi:content-save-outline"></ha-icon><span>${this.tr("save")}</span></button>
              <button type="button" class="primary" data-action="led-schedule-save" ${submitting ? "disabled" : ""}><ha-icon icon="mdi:calendar-check"></ha-icon><span>${this.tr("save_send")}</span></button>
            </div>
          </footer>
        </section>
      </div>`;
  }

  syncLedScheduleControl(row, name, value, sourceKind = "") {
    const normalized = String(value ?? "");
    const rampValue = name === "ramp" ? this.normalizeLedRampMinutes(normalized) : null;
    const controls = row.querySelectorAll(`[data-led-schedule-control="${name}"]`);
    controls.forEach((control) => {
      if (sourceKind && control.getAttribute("data-led-schedule-kind") === sourceKind) return;
      if (name === "ramp") {
        if (control.getAttribute("data-led-schedule-kind") === "button") {
          const active = Number(control.getAttribute("data-led-schedule-ramp")) === rampValue;
          control.classList.toggle("active", active);
          control.setAttribute("aria-pressed", active ? "true" : "false");
        } else {
          control.value = String(rampValue);
        }
        return;
      }
      control.value = normalized;
    });
  }

  applyLedScheduleTemplate(row, templateValue) {
    const template = this.ledScheduleTemplateByValue(templateValue);
    if (!template || template.value === "custom") return;
    const templateLevels = this.ledScheduleTemplateLevels(template.values);
    if (!templateLevels) return;
    ["red", "green", "blue", "white"].forEach((name) => {
      const value = Math.max(0, Math.min(this.ledMaxBrightness(), Math.round(Number(templateLevels[name] || 0))));
      this.syncLedScheduleControl(row, name, value, "");
    });
    const select = row.querySelector('[data-led-schedule-template]');
    if (select) select.value = template.value;
  }

  syncLedScheduleTemplate(row) {
    const select = row.querySelector('[data-led-schedule-template]');
    if (!select) return;
    select.value = this.ledScheduleTemplateForRow(row);
  }

  ledScheduleRowLevelsFromControls(row) {
    const valueFor = (name) => {
      const el = row.querySelector(`[data-led-schedule-control="${name}"][data-led-schedule-kind="number"]`)
        || row.querySelector(`[data-led-schedule-control="${name}"][data-led-schedule-kind="range"]`);
      return Math.max(0, Math.min(this.ledMaxBrightness(), Math.round(Number(el && el.value ? el.value : 0))));
    };
    return [valueFor("red"), valueFor("green"), valueFor("blue"), valueFor("white")];
  }

  addLedScheduleTemplate(row) {
    if (!row) return;
    const name = String(window.prompt(this.tr("template_name_prompt"), "") || "").trim();
    if (!name) return;
    const templates = this.loadLocalLedTemplates().filter((template) => String(template.name || "").trim().toLowerCase() !== name.toLowerCase());
    templates.push({ name, values: this.ledScheduleRowLevelsFromControls(row) });
    this.saveLocalLedTemplates(templates);
    this.ledScheduleEditorOpen = false;
    this.dialogState = {
      type: "debug",
      channel: 1,
      output: `OK\n${this.tr("template_saved")}\n${name}`,
      running: false,
      noChannel: true,
      level: "ok",
    };
    this.render();
  }

  showLedScheduleTemplates() {
    const lines = this.ledScheduleTemplateOptions()
      .filter((template) => template.value !== "custom")
      .map((template) => `${template.label}: ${(template.values || []).join("/")}`);
    this.ledScheduleEditorOpen = false;
    this.dialogState = {
      type: "debug",
      channel: 1,
      output: `OK\n${this.tr("template_list")}\n${lines.length ? lines.join("\n") : "-"}`,
      running: false,
      noChannel: true,
      level: "ok",
    };
    this.render();
  }

  deleteLedScheduleTemplate(row) {
    const select = row && row.querySelector('[data-led-schedule-template]');
    const value = select ? String(select.value || "") : "";
    if (!value.startsWith("local:")) {
      this.ledScheduleEditorOpen = false;
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: `FAIL\n${this.tr("template_delete_blocked")}`,
        running: false,
        noChannel: true,
        level: "error",
      };
      this.render();
      return;
    }
    const name = value.slice("local:".length);
    const before = this.loadLocalLedTemplates();
    const after = before.filter((template) => String(template.name || "").trim() !== name);
    this.saveLocalLedTemplates(after);
    this.ledScheduleEditorOpen = false;
    this.dialogState = {
      type: "debug",
      channel: 1,
      output: `${before.length === after.length ? "FAIL" : "OK"}\n${before.length === after.length ? this.tr("template_not_found") : this.tr("template_deleted")}\n${name}`,
      running: false,
      noChannel: true,
      level: before.length === after.length ? "error" : "ok",
    };
    this.render();
  }

  currentLedChannelTemplateValues() {
    const values = [0, 0, 0, 0];
    (this.ledChannels || []).slice(0, 4).forEach((channel, index) => {
      values[index] = Math.max(0, Math.min(this.ledMaxBrightness(), Math.round(Number(this.ledChannelValue(channel) || 0))));
    });
    return values;
  }

  ledTemplateFrontValues() {
    const root = this.shadowRoot || this;
    const keys = this.ledSupportedScheduleKeys();
    const fallback = this.currentLedChannelTemplateValues();
    return keys.map((key, index) => {
      const el = root.querySelector(`[data-led-template-control="${key}"][data-led-template-kind="number"]`)
        || root.querySelector(`[data-led-template-control="${key}"][data-led-template-kind="range"]`);
      const raw = el && el.value !== "" ? el.value : fallback[index];
      return Math.max(0, Math.min(this.ledMaxBrightness(), Math.round(Number(raw || 0))));
    });
  }

  syncLedTemplateControl(name, value) {
    const root = this.shadowRoot || this;
    const next = Math.max(0, Math.min(this.ledMaxBrightness(), Math.round(Number(value || 0))));
    root.querySelectorAll(`[data-led-template-control="${name}"]`).forEach((el) => {
      el.value = String(next);
    });
  }

  applyLedFrontTemplate(value) {
    const template = this.ledScheduleTemplateByValue(value);
    if (!template || !Array.isArray(template.values)) {
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: `FAIL\n${this.tr("template_not_found")}`,
        running: false,
        noChannel: true,
        level: "error",
      };
      this.render();
      return;
    }
    const templateLevels = this.ledScheduleTemplateLevels(template.values);
    this.ledSupportedScheduleKeys().forEach((key) => {
      this.syncLedTemplateControl(key, templateLevels[key]);
    });
  }

  addLedFrontTemplate() {
    const name = String(window.prompt(this.tr("template_name_prompt"), "") || "").trim();
    if (!name) return;
    const templates = this.loadLocalLedTemplates().filter((template) => String(template.name || "").trim().toLowerCase() !== name.toLowerCase());
    templates.push({ name, values: this.ledTemplateFrontValues() });
    this.saveLocalLedTemplates(templates);
    this.dialogState = {
      type: "debug",
      channel: 1,
      output: `OK\n${this.tr("template_saved")}\n${name}`,
      running: false,
      noChannel: true,
      level: "ok",
    };
    this.render();
  }

  deleteLedFrontTemplate(value) {
    const selected = String(value || "");
    if (!selected.startsWith("local:")) {
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: `FAIL\n${this.tr("template_delete_blocked")}`,
        running: false,
        noChannel: true,
        level: "error",
      };
      this.render();
      return;
    }
    const name = selected.slice("local:".length);
    const before = this.loadLocalLedTemplates();
    const after = before.filter((template) => String(template.name || "").trim() !== name);
    this.saveLocalLedTemplates(after);
    this.dialogState = {
      type: "debug",
      channel: 1,
      output: `${before.length === after.length ? "FAIL" : "OK"}\n${before.length === after.length ? this.tr("template_not_found") : this.tr("template_deleted")}\n${name}`,
      running: false,
      noChannel: true,
      level: before.length === after.length ? "error" : "ok",
    };
    this.render();
  }

  openLedTemplateDialog(value) {
    const selected = String(value || "");
    const name = selected.startsWith("local:") ? selected.slice("local:".length) : "";
    const template = this.loadLocalLedTemplates().find((item) => String(item.name || "").trim() === name);
    const levels = this.ledScheduleTemplateLevels(template && template.values ? template.values : this.currentLedChannelTemplateValues());
    const keys = this.ledSupportedScheduleKeys();
    this.dialogState = {
      type: "led-template-editor",
      originalName: name,
      name,
      values: keys.map((key) => levels[key]),
    };
    this.render();
  }

  ledTemplateDialogValues() {
    const root = this.shadowRoot || this;
    const name = String(root.querySelector("[data-led-template-name]")?.value || "").trim();
    const keys = this.ledSupportedScheduleKeys();
    const values = keys.map((key, index) => {
      const el = root.querySelector(`[data-led-template-control="${key}"][data-led-template-kind="number"]`)
        || root.querySelector(`[data-led-template-control="${key}"][data-led-template-kind="range"]`);
      const fallback = Array.isArray(this.dialogState && this.dialogState.values) ? this.dialogState.values[index] : 0;
      return Math.max(0, Math.min(this.ledMaxBrightness(), Math.round(Number(el && el.value !== "" ? el.value : fallback || 0))));
    });
    return { name, values };
  }

  saveLedTemplateFromDialog() {
    const current = this.dialogState || {};
    const data = this.ledTemplateDialogValues();
    if (!data.name) {
      this.dialogState = { type: "debug", channel: 1, output: `FAIL\n${this.tr("template_name_prompt")}`, running: false, noChannel: true, level: "error" };
      this.render();
      return;
    }
    const original = String(current.originalName || data.name).trim();
    const templates = this.loadLocalLedTemplates().filter((template) => {
      const itemName = String(template.name || "").trim();
      return itemName.toLowerCase() !== original.toLowerCase() && itemName.toLowerCase() !== data.name.toLowerCase();
    });
    templates.push({ name: data.name, values: data.values });
    this.saveLocalLedTemplates(templates);
    this._ledTemplateSourceFilter = "local";
    this.dialogState = { type: "debug", channel: 1, output: `OK\n${this.tr("template_saved")}\n${data.name}`, running: false, noChannel: true, level: "ok" };
    this.render();
  }

  deleteLedTemplateFromFront(value) {
    return this.deleteLedFrontTemplate(value);
  }

  compatibleLedTemplateTargets() {
    const active = this.activeLedDevice || {};
    const activeCount = Array.isArray(active.channels) && active.channels.length
      ? active.channels.length
      : this.ledSupportedScheduleKeys(active).length;
    return (Array.isArray(this.ledDevices) ? this.ledDevices : []).filter((device) => {
      if (!device || String(device.id || device.address || "") === String(active.id || active.address || "")) return false;
      const channelCount = Array.isArray(device.channels) && device.channels.length
        ? device.channels.length
        : this.ledSupportedScheduleKeys(device).length;
      return channelCount === activeCount;
    });
  }

  openLedTemplateShareDialog(value) {
    const template = this.ledScheduleTemplateByValue(value);
    if (!template || !Array.isArray(template.values)) return;
    const targets = this.compatibleLedTemplateTargets();
    if (!targets.length) {
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: `FAIL\n${this.tr("no_compatible_led")}`,
        running: false,
        noChannel: true,
        level: "error",
      };
      this.render();
      return;
    }
    this.dialogState = {
      type: "led-template-share",
      templateValue: String(value || ""),
      templateName: String(template.label || "").replace(/^[^:]+:\s*/, ""),
      values: template.values.map((item) => Number(item)),
      targetId: String(targets[0].id || targets[0].address || ""),
    };
    this.render();
  }

  saveSharedLedTemplate() {
    const state = this.dialogState || {};
    const root = this.shadowRoot || this;
    const targetId = String(root.querySelector("[data-led-template-share-target]")?.value || state.targetId || "");
    const target = this.compatibleLedTemplateTargets().find((device) => String(device.id || device.address || "") === targetId);
    if (!target) return;
    const name = String(state.templateName || "").trim();
    const templates = this.loadLocalLedTemplates(target).filter(
      (template) => String(template.name || "").trim().toLowerCase() !== name.toLowerCase()
    );
    templates.push({ name, values: Array.isArray(state.values) ? state.values.map((value) => Number(value)) : [] });
    this.saveLocalLedTemplates(templates, target);
    this.dialogState = {
      type: "debug",
      channel: 1,
      output: `OK\n${this.tr("template_shared")}\n${name} -> ${target.label || target.name || target.address}`,
      running: false,
      noChannel: true,
      level: "ok",
    };
    this.render();
  }

  ledTemplateShareDialog() {
    const state = this.dialogState || {};
    const targets = this.compatibleLedTemplateTargets();
    return this.sharedModalDialog({
      title: this.tr("share_template"),
      sectionClass: "modal card led-schedule-modal led-template-share-modal",
      bodyHtml: `
        <div class="led-schedule-editor">
          <article class="led-schedule-row-card">
            <div class="led-schedule-color-control color-template">
              <label><span>${this.tr("template")}</span></label>
              <strong>${this.escapeHtml(state.templateName || "")}</strong>
            </div>
            <div class="led-schedule-color-control color-template">
              <label><span>${this.tr("target_device")}</span></label>
              <select data-led-template-share-target>
                ${targets.map((device) => {
                  const id = String(device.id || device.address || "");
                  const label = device.label || device.name || device.address || id;
                  return `<option value="${this.escapeHtml(id)}" ${id === state.targetId ? "selected" : ""}>${this.escapeHtml(label)}</option>`;
                }).join("")}
              </select>
            </div>
          </article>
        </div>`,
      footerHtml: `
        <div class="led-schedule-actions">
          ${this.sharedDialogActions([
            { action: "close-dialog", label: this.tr("cancel"), className: "secondary", type: "button", icon: "mdi:close" },
            { action: "led-template-share-save", label: this.tr("share"), className: "primary", type: "button", icon: "mdi:share-variant" },
          ])}
        </div>`,
    });
  }

  ledScheduleRowsForDevice(device) {
    const schedules = this.config && this.config.addon_database && this.config.addon_database.led_schedules
      ? this.config.addon_database.led_schedules
      : {};
    const keys = [device && device.address, device && device.id]
      .map((value) => String(value || "").trim().toUpperCase())
      .filter(Boolean);
    const rows = keys.map((key) => schedules[key]).find((value) => Array.isArray(value)) || [];
    return rows.map((row) => ({
      start: String(row && row.start ? row.start : "08:00"),
      end: String(row && row.end ? row.end : "20:00"),
      ramp: this.normalizeLedRampMinutes(row && row.ramp),
      levels: this.normalizeLedScheduleLevels(row && row.levels),
      weekdays: this.normalizeLedWeekdays(row && row.weekdays),
      active: row && row.active !== false,
    }));
  }

  openLedScheduleShareDialog(rowIndex) {
    const row = this.ledScheduleRows()[Number(rowIndex)];
    const targets = this.compatibleLedTemplateTargets();
    if (!row || !targets.length) {
      this.dialogState = { type: "debug", channel: 1, output: `FAIL\n${this.tr("no_compatible_led")}`, running: false, noChannel: true, level: "error" };
      this.render();
      return;
    }
    this.dialogState = {
      type: "led-schedule-share",
      row: JSON.parse(JSON.stringify(row)),
      targetId: String(targets[0].id || targets[0].address || ""),
    };
    this.render();
  }

  async saveSharedLedSchedule() {
    const state = this.dialogState || {};
    const root = this.shadowRoot || this;
    const targetId = String(root.querySelector("[data-led-schedule-share-target]")?.value || state.targetId || "");
    const send = Boolean(root.querySelector("[data-led-schedule-share-send]")?.checked);
    const target = this.compatibleLedTemplateTargets().find((device) => String(device.id || device.address || "") === targetId);
    if (!target || !state.row) return;
    const sharedRow = JSON.parse(JSON.stringify(state.row));
    const targetRows = this.ledScheduleRowsForDevice(target).filter(
      (row) => !(row.start === sharedRow.start && row.end === sharedRow.end)
    );
    targetRows.push(sharedRow);
    const conflict = this.validateLedScheduleRows(targetRows);
    if (conflict) {
      this.dialogState = { type: "debug", channel: 1, output: `FAIL\n${conflict}`, running: false, noChannel: true, level: "error" };
      this.render();
      return;
    }
    const localPeriods = this.ledSchedulePeriodsFromRows(targetRows, target);
    const periods = this.ledSchedulePeriodsFromRows(targetRows, target, true);
    const debug = Boolean(this.uiSettings && this.uiSettings.dashboardDebug);
    let sendOutput = "";
    if (send) {
      const result = await this.runLedScheduleService({
        service: "set_schedule",
        data: { periods, send: true, ...this.ledServiceSelector(target) },
        title: this.tr("share_schedule"),
        debug,
      });
      if (!result || !result.ok) {
        this.dialogState = { type: "debug", channel: 1, output: result && result.output ? result.output : `FAIL\n${this.tr("share_schedule")}`, running: false, noChannel: true, level: "error" };
        this.render();
        return;
      }
      sendOutput = String(result.output || "").trim();
    }
    const address = String(target.address || "");
    const deviceKey = String(target.address || target.id || "").trim().toUpperCase();
    const saved = await this.saveLedScheduleLocal(
      { periods: localPeriods, send, device_key: deviceKey, ...(address ? { address } : {}) },
      this.tr("share_schedule"),
      true,
    );
    this.dialogState = {
      type: "debug",
      channel: 1,
      output: saved && debug && sendOutput
        ? sendOutput
        : `${saved ? "OK" : "FAIL"}\n${this.tr(saved ? "schedule_shared" : "share_schedule")}\n${target.label || target.name || target.address}`,
      running: false,
      noChannel: true,
      level: saved ? "ok" : "error",
    };
    this.render();
  }

  ledScheduleShareDialog() {
    const state = this.dialogState || {};
    const row = state.row || {};
    const targets = this.compatibleLedTemplateTargets();
    return this.sharedModalDialog({
      title: this.tr("share_schedule"),
      sectionClass: "modal card led-schedule-modal led-schedule-share-modal",
      bodyHtml: `
        <div class="led-schedule-editor">
          <article class="led-schedule-row-card">
            <div class="led-schedule-color-control color-time">
              <label><span>${this.tr("time")}</span></label>
              <strong>${this.escapeHtml(row.start || "")} - ${this.escapeHtml(row.end || "")}</strong>
            </div>
            <div class="led-schedule-color-control color-template">
              <label><span>${this.tr("target_device")}</span></label>
              <select data-led-schedule-share-target>
                ${targets.map((device) => {
                  const id = String(device.id || device.address || "");
                  const label = device.label || device.name || device.address || id;
                  return `<option value="${this.escapeHtml(id)}" ${id === state.targetId ? "selected" : ""}>${this.escapeHtml(label)}</option>`;
                }).join("")}
              </select>
            </div>
            <label class="led-schedule-color-control color-toggle">
              <span>${this.tr("send_to_device_now")}</span>
              <input type="checkbox" data-led-schedule-share-send>
            </label>
          </article>
        </div>`,
      footerHtml: `
        <div class="led-schedule-actions">
          ${this.sharedDialogActions([
            { action: "close-dialog", label: this.tr("cancel"), className: "secondary", type: "button", icon: "mdi:close" },
            { action: "led-schedule-share-save", label: this.tr("share"), className: "primary", type: "button", icon: "mdi:share-variant" },
          ])}
        </div>`,
    });
  }

  ledTemplateDialog() {
    const state = this.dialogState || {};
    const max = this.ledMaxBrightness();
    const values = Array.isArray(state.values) ? state.values : this.currentLedChannelTemplateValues();
    const keys = this.ledSupportedScheduleKeys();
    const colorControl = (key, label, value, accentClass = "") => `
            <div class="led-schedule-color-control ${accentClass}">
              <label><span>${label}</span></label>
              <input type="range" min="0" max="${max}" step="1" data-led-template-control="${key}" data-led-template-kind="range" value="${value}">
              <input type="number" min="0" max="${max}" step="1" data-led-template-control="${key}" data-led-template-kind="number" value="${value}">
            </div>`;
    return this.sharedModalDialog({
      title: this.tr("template"),
      sectionClass: "modal card led-schedule-modal led-template-modal",
      bodyHtml: `
        <div class="led-schedule-editor">
          <article class="led-schedule-row-card">
            <div class="led-schedule-row-grid">
              <div class="led-schedule-color-control color-template">
                <label><span>${this.tr("name")}</span></label>
                <input type="text" data-led-template-name value="${this.escapeHtml(state.name || "")}">
              </div>
              ${keys.map((key, index) => colorControl(
                key,
                `CH${index + 1} ${this.ledScheduleChannelLabel(key)}`,
                values[index] || 0,
                `color-${key}`,
              )).join("")}
            </div>
          </article>
        </div>`,
      footerHtml: `
        <div class="led-schedule-actions">
          ${this.sharedDialogActions([
            { action: "close-dialog", label: this.tr("cancel"), className: "secondary", type: "button", icon: "mdi:close" },
            { action: "led-template-save", label: this.tr("save"), className: "primary", type: "button", icon: "mdi:content-save-outline" },
          ])}
        </div>`,
    });
  }

  openLedAutoModeDialog() {
    const device = this.activeLedDevice || {};
    if (!device.auto_entity) return;
    this.dialogState = {
      type: "led-auto-mode-editor",
      entity: device.auto_entity,
      value: this.ledAutoModeIsOn(device) ? "on" : "off",
    };
    this.render();
  }

  openLedDevicePowerDialog() {
    this.dialogState = {
      type: "led-device-power-editor",
      value: this.ledDeviceIsOn() ? "on" : "off",
    };
    this.render();
  }

  async toggleLedDevicePower() {
    return this.setLedPreset(this.ledDeviceIsOn() ? "off" : "high");
  }

  ledDevicePowerDialog() {
    const state = this.dialogState || {};
    const value = String(state.value || "off");
    return this.sharedModalDialog({
      title: this.tr("complete_lamp"),
      sectionClass: "modal card led-auto-mode-modal",
      bodyHtml: `
        <div class="led-auto-mode-choice">
          <button type="button" class="${value === "on" ? "active" : ""}" data-led-device-power-value="on">${this.tr("complete_lamp_on")}</button>
          <button type="button" class="${value === "off" ? "active" : ""}" data-led-device-power-value="off">${this.tr("complete_lamp_off")}</button>
        </div>`,
      actions: [
        { action: "close-dialog", label: this.tr("cancel"), className: "link", type: "button" },
        { action: "led-device-power-send", label: this.tr("send_to_device"), className: "primary", type: "button" },
      ],
    });
  }

  async saveLedDevicePowerDialog() {
    const root = this.shadowRoot || this;
    const active = root.querySelector("[data-led-device-power-value].active");
    const value = String(active ? active.getAttribute("data-led-device-power-value") : "off");
    return this.setLedPreset(value === "on" ? "high" : "off");
  }

  ledAutoModeDialog() {
    const value = String((this.dialogState && this.dialogState.value) || "off");
    return this.sharedModalDialog({
      title: this.tr("auto_mode"),
      sectionClass: "modal card led-auto-mode-modal",
      bodyHtml: `
        <div class="led-auto-mode-choice">
          <button type="button" class="${value === "on" ? "active" : ""}" data-led-auto-mode-value="on">${this.tr("on")}</button>
          <button type="button" class="${value === "off" ? "active" : ""}" data-led-auto-mode-value="off">${this.tr("off")}</button>
        </div>`,
      actions: [
        { action: "close-dialog", label: this.tr("cancel"), className: "link", type: "button" },
        { action: "led-auto-mode-send", label: this.tr("send_to_device"), className: "primary", type: "button" },
      ],
    });
  }

  async saveLedAutoModeDialog() {
    const root = this.shadowRoot || this;
    const active = root.querySelector("[data-led-auto-mode-value].active");
    const value = String(active ? active.getAttribute("data-led-auto-mode-value") : (this.dialogState && this.dialogState.value) || "off");
    const entity = this.dialogState && this.dialogState.entity;
    if (!this._hass || !entity) return;
    try {
      await this._hass.callService("switch", value === "on" ? "turn_on" : "turn_off", {}, { entity_id: entity });
      this.setLedManualScheduleWarning(value !== "on");
      await this.persistLedDeviceStatus({
        mode: value === "on" ? "automatic" : "manual",
        scheduleState: value === "on" ? (this.hasLedSchedules() ? "active" : "empty") : "manual_override",
        source: "auto_mode",
        action: `${this.tr("auto_mode")}: ${value}`,
      });
      this.dialogState = { type: "debug", channel: 1, output: `OK\n${this.tr("auto_mode")}: ${value}`, running: false, noChannel: true, level: "ok" };
    } catch (err) {
      this.dialogState = { type: "debug", channel: 1, output: `FAIL\n${this.tr("auto_mode")}\n${err && err.message ? err.message : err}`, running: false, noChannel: true, level: "error" };
    }
    this.render();
  }

  ledTemplatePanel() {
    const scheduleKeys = this.ledSupportedScheduleKeys();
    const source = String(this._ledTemplateSourceFilter || "standard");
    const templates = this.ledScheduleTemplateOptions().filter((template) => {
      const value = String(template.value || "");
      if (value === "custom") return false;
      return source === "standard" ? value.startsWith("standard:") : !value.startsWith("standard:");
    });
    const limitClass = templates.length > 5 ? " scroll-limit-5" : "";
    const chip = (className, value) => `<span class="led-template-chip ${className}">${Number(value || 0)} %</span>`;
    const rows = templates.length ? templates.map((template) => {
      const levels = this.ledScheduleTemplateLevels(template.values || []) || { red: 0, green: 0, blue: 0, white: 0 };
      const local = String(template.value || "").startsWith("local:");
      const rawLabel = String(template.label || "");
      const localPrefix = `${this.tr("template_local")}: `;
      const displayLabel = source === "local" && rawLabel.startsWith(localPrefix)
        ? rawLabel.slice(localPrefix.length)
        : rawLabel;
      const actionButtons = [];
      if (local) actionButtons.push(
          {
            attrs: `data-led-template-edit="${this.escapeHtml(template.value)}"`,
            title: this.tr("edit"),
            icon: "mdi:pencil",
          },
          {
            attrs: `data-led-template-delete="${this.escapeHtml(template.value)}"`,
            className: "danger",
            title: this.tr("delete"),
            icon: "mdi:delete-outline",
          },
      );
      actionButtons.push({
        attrs: `data-led-template-share="${this.escapeHtml(template.value)}"`,
        title: this.tr("share"),
        icon: "mdi:share-variant",
      });
      const actions = this.sharedIconActionButtons(actionButtons);
      return `
        <tr>
          <td>${this.escapeHtml(displayLabel)}</td>
          ${scheduleKeys.map((key) => `<td>${chip(key, levels[key])}</td>`).join("")}
          <td>${actions}</td>
        </tr>`;
    }).join("") : "";
    return `
      <section class="card led-template-card">
        <div class="config-card-head">
          <div>
            <div class="led-schedule-title-row led-template-title-row">
              <h2>${this.tr("template")}</h2>
              <span class="led-schedule-count led-template-count">${templates.length} ${this.tr("template_count")}</span>
            </div>
            <small>${this.tr("template_list")}</small>
          </div>
          <div class="led-template-header-actions">
            <select data-led-template-source aria-label="${this.tr("template_source")}">
              <option value="standard" ${source === "standard" ? "selected" : ""}>${this.tr("template_standard")}</option>
              <option value="local" ${source === "local" ? "selected" : ""}>${this.tr("template_local")}</option>
            </select>
            <button type="button" class="secondary" data-led-template-edit="">
              <ha-icon icon="mdi:plus"></ha-icon><span>${this.tr("add")}</span>
            </button>
          </div>
        </div>
        ${rows ? `
        <div class="led-template-front-table-wrap${limitClass}">
        <table class="led-template-front-table">
          <thead><tr><th>${this.tr("name")}</th>${scheduleKeys.map((key, index) => `<th>CH${index + 1} ${this.ledScheduleChannelLabel(key)}</th>`).join("")}<th>${this.tr("actions")}</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
        </div>` : `<div class="empty-state">${this.tr("template_not_found")}</div>`}
      </section>`;
  }

  openLedScheduleDialog(rowIndex = null) {
    return this.openDialogState("led-schedule", 1, {
      activeTab: "led",
      ledScheduleEditorOpen: true,
      ledScheduleEditIndex: Number.isInteger(rowIndex) && rowIndex >= 0 ? rowIndex : null,
    });
  }

  openNewLedScheduleDialog() {
    return this.openDialogState("led-schedule", 1, {
      activeTab: "led",
      ledScheduleEditorOpen: true,
      ledScheduleNew: true,
    });
  }

  openLedScheduleResetConfirm() {
    const root = this.shadowRoot || this;
    const dialogDebug = root.querySelector("[data-led-schedule-debug]");
    const targetDevice = this.activeLedDevice
      ? { ...this.activeLedDevice, channels: [...(this.activeLedDevice.channels || [])] }
      : {};
    this._ledScheduleResetDebug = dialogDebug
      ? Boolean(dialogDebug.checked)
      : Boolean(this.uiSettings && this.uiSettings.dashboardDebug);
    this.openConfirmDialog({
      title: this.tr("delete_all"),
      message: this.tr("led_reset_device_question"),
      detail: this.tr("led_reset_device_effect"),
      confirmLabel: this.tr("delete_all"),
      cancelLabel: this.tr("reset_schedule_no"),
      noChannel: true,
      onConfirm: async () => this.resetLedDeviceSchedule(this._ledScheduleResetDebug, targetDevice),
    });
  }

  async enableLedAutoModeFromFront() {
    const device = this.activeLedDevice || {};
    const entity = String(device.auto_entity || "");
    const debug = Boolean(this.uiSettings && this.uiSettings.dashboardDebug);
    if (!this._hass) {
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: `FAIL\n${this.tr("enable_auto_mode")}\n${this.tr("service_unavailable")}`,
        running: false,
        noChannel: true,
        level: "error",
      };
      this.render();
      return false;
    }
    try {
      const periods = this.ledSchedulePeriodsFromRows(this.ledScheduleRows(), this.activeLedDevice || {}, true);
      const result = await this.runDeviceService({
        service: "enable_auto_mode",
        data: this.ledServiceSelector(),
        title: this.tr("enable_auto_mode"),
        debug,
        dialog: false,
        channel: 1,
        noChannel: true,
      });
      if (!result || !result.ok) throw new Error(result && result.output ? result.output : this.tr("send_failed"));
      const serviceOutput = String(result.output || "").trim();
      await this.addLedHistory(this.tr("enable_auto_mode"), entity || device.address || "", null, { status: "ok" });
      this.setLedManualScheduleWarning(false);
      await this.persistLedDeviceStatus({
        mode: "automatic",
        scheduleState: periods.length ? "active" : "empty",
        scheduleCount: periods.filter((period) => period && period.active !== false).length,
        source: "auto_mode",
        action: this.tr("enable_auto_mode"),
      });
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: debug && serviceOutput ? serviceOutput : `OK\n${this.tr("enable_auto_mode")}\n${entity || device.address || ""}`,
        running: false,
        noChannel: true,
        level: "ok",
      };
      this.render();
      return true;
    } catch (err) {
      this.dialogState = {
        type: "debug",
        channel: 1,
        output: `FAIL\n${this.tr("enable_auto_mode")}\n${err && err.message ? err.message : err}`,
        running: false,
        noChannel: true,
        level: "error",
      };
      this.render();
      return false;
    }
  }

  ledPanel() {
    const device = this.activeLedDevice || {};
    const channels = this.ledChannels || [];
    if (!this.ledDevices || !this.ledDevices.length) {
      return `
        <div class="led-page">
          <section class="card">
            <h2>LED</h2>
            <div class="empty-state">${this.tr("no_entities")}</div>
          </section>
        </div>`;
    }
    const columns = Math.max(1, Math.min(4, channels.length || 1));
    const firmware = this.ledEntityState(device.firmware_entity);
    const runtimeEntity = this.resolveLedRuntimeEntity(device);
    const runtime = this.ledEntityState(runtimeEntity);
    const feedbackStatus = this.ledDeviceFeedbackStatus(device);
    const showWatts = this.supportsLedWattEstimates(device);
    const initialWattValues = channels.map((channel) => this.ledChannelValue(channel));
    const unknownValues = new Set(["unknown", "unavailable", String(this.tr("unknown")).trim().toLowerCase()]);
    const firmwareUnknown = unknownValues.has(String(firmware).trim().toLowerCase());
    const channelContent = channels.length
      ? `<div class="led-channels channels-${columns}" style="--channel-columns:${columns}">
            ${channels.map((channel) => this.ledChannelCard(channel)).join("")}
          </div>`
      : `<div class="empty-state">${this.tr("no_led_channels")}.</div>`;
    return `
      ${this.ledDeviceTabs()}
      ${this.ledManualScheduleWarning()}
      <div class="led-page">
        <section class="card small led-connection-card">
          <h2>${this.tr("connection")}</h2>
          <p><b>${this.tr("device")}</b><span>${this.escapeHtml(device.name || device.id || device.label || "LED")}</span></p>
          <p><b>${this.tr("model")}</b><span>${this.escapeHtml(device.model || "LED")}</span></p>
          <p><b>${this.tr("channels")}</b><span>${channels.length}</span></p>
          <p><b>MAC</b><span>${this.escapeHtml(device.address || "-")}</span></p>
          <p><b>${this.tr("status")}</b><span class="${feedbackStatus.online ? "ok" : "is-offline"}">${feedbackStatus.online ? this.tr("online") : this.tr("offline")}</span></p>
          <p><b>${this.tr("runtime")}</b><span>${this.escapeHtml(this.formatLedRuntime(runtime))}</span></p>
          <p><b>${this.tr("last_notification")}</b><span><button type="button" class="led-notification-open" data-action="led-notification-open" title="${this.tr("details")}" aria-label="${this.tr("details")}"><span aria-hidden="true">&#128065;</span></button></span></p>
          <p><b>${this.tr("fetched_at")}</b><span>${this.escapeHtml(this.formatLedNotificationTime(device))}</span></p>
          <p><b>${this.tr("firmware")}</b><span class="${firmwareUnknown ? "is-unknown" : ""}">${this.escapeHtml(firmware)}</span></p>
        </section>
        <section class="card led-device-control-card">
          <section class="led-device-edit-box led-device-control-box">
            <h2>${this.tr("control")}</h2>
            <div class="led-device-edit-actions">
              <div class="action-row led-device-power-row">
                <ha-icon icon="mdi:power"></ha-icon>
                <span>${this.tr("complete_lamp_toggle")}</span>
                <button type="button" class="led-power-toggle ${this.ledDeviceIsOn() ? "active" : ""}" data-action="led-device-power-toggle" role="switch" aria-checked="${this.ledDeviceIsOn() ? "true" : "false"}" title="${this.ledDeviceIsOn() ? this.tr("complete_lamp_off") : this.tr("complete_lamp_on")}">
                  <span class="led-power-toggle-track"><span></span></span>
                  <b>${this.ledDeviceIsOn() ? this.tr("on") : this.tr("off")}</b>
                </button>
              </div>
              ${device.auto_entity ? `
              <div class="action-row led-auto-mode-row">
                <ha-icon icon="mdi:toggle-switch"></ha-icon>
                <span>${this.tr("auto_mode")}</span>
                <b>${this.ledAutoModeState(device)}</b>
              </div>` : ""}
              ${this.databaseDiagnosticsEnabled() ? `
              <div class="action-row led-database-status-row">
                <ha-icon icon="mdi:database-search"></ha-icon>
                <span>${this.tr("database_status")}</span>
                <button type="button" class="led-notification-open" data-action="led-database-status-open" title="${this.tr("details")}" aria-label="${this.tr("details")}"><ha-icon icon="mdi:eye"></ha-icon></button>
              </div>` : ""}
              <div class="action-row led-device-name-edit-row">
                <ha-icon icon="mdi:pencil"></ha-icon>
                <span>${this.tr("change_device_name")}</span>
                <button type="button" class="led-notification-open" data-action="led-device-name-edit" title="${this.tr("change_device_name")}" aria-label="${this.tr("change_device_name")}"><ha-icon icon="mdi:pencil"></ha-icon></button>
              </div>
            </div>
          </section>
        </section>
        ${this.ledDeviceHasFan(device) ? this.ledFanControlCard(device) : `<section class="card led-device-presets-card">
          <h2>${this.tr("presets")}</h2>
          <div class="led-preset-grid">
            <button type="button" data-action="led-preset:low"><ha-icon icon="mdi:weather-sunset"></ha-icon><span>${this.ledPresetValue("low")}</span></button>
            <button type="button" data-action="led-preset:medium"><ha-icon icon="mdi:white-balance-sunny"></ha-icon><span>${this.ledPresetValue("medium")}</span></button>
            <button type="button" data-action="led-preset:high"><ha-icon icon="mdi:brightness-7"></ha-icon><span>${this.ledPresetValue("high")}</span></button>
          </div>
        </section>`}
        <section class="card led-channels-card">
          ${showWatts
            ? `<div class="led-channels-title-row"><h2>${this.tr("color_channels")}</h2><span class="led-total-watt" title="${this.escapeHtml(this.tr("estimated_power"))}"><span class="led-watt-bolt" aria-hidden="true">⚡</span><span data-led-total-watts>${this.tr("total")} ≈ ${this.ledWattFormat(this.ledTotalEstimatedWatts(initialWattValues))} W / ${this.ledWattFormat(this.ledMaxPowerWatts(device))} W</span></span></div>`
            : `<h2>${this.tr("color_channels")}</h2>`}
          ${channelContent}
        </section>
        <div class="middle wide-middle led-middle">
          ${this.ledScheduleSummaryPanel()}
          ${this.ledHistoryPanel()}
        </div>
        ${this.ledTemplatePanel()}
      </div>`;
  }
};
