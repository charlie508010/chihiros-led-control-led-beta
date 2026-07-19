window.ChihirosNotificationUi = window.ChihirosNotificationUi || {
  rawHex(notification, stateValue = "") {
    if (typeof notification === "string") return notification.trim();
    const value = notification && typeof notification === "object" ? notification : {};
    return String(
      value.value_hex || value.frame || value.raw || value.hex || value.parm || value.att_hex
      || (/^(?:[0-9a-f]{2}[\s:-]*)+$/i.test(stateValue) ? stateValue : ""),
    ).trim();
  },

  frameModel(notification, stateValue = "") {
    const rawHex = this.rawHex(notification, stateValue);
    const bytes = rawHex.split(/[\s:-]+/).filter(Boolean)
      .map((value) => Number.parseInt(value, 16)).filter(Number.isFinite);
    const params = bytes.length > 7 ? bytes.slice(6, -1) : [];
    const mode = bytes.length > 5 ? bytes[5] : null;
    const values = [];
    if ([0x1E, 0x22].includes(mode) && params.length >= 8) {
      for (let offset = 0; offset + 1 < params.length && values.length < 4; offset += 2) {
        values.push(((params[offset] << 8) | params[offset + 1]) / 10);
      }
    }
    return {
      notification: notification && typeof notification === "object" ? notification : {},
      rawHex,
      bytes,
      command: bytes.length ? bytes[0] : null,
      firmware: bytes.length > 1 ? bytes[1] : null,
      length: bytes.length > 2 ? bytes[2] : null,
      mode,
      params,
      checksum: bytes.length ? bytes[bytes.length - 1] : null,
      values,
    };
  },

  render(card, {
    notifications = [], stateValue = "", emptyText = "", describe = null,
    title = "", subtitle = "", scope = "default",
  } = {}) {
    const hexByte = (value) => Number(value || 0).toString(16).padStart(2, "0").toUpperCase();
    const english = typeof card.language === "function" && card.language() === "en";
    const scopeToken = String(scope || "default").toLowerCase().replace(/[^a-z0-9_-]+/g, "-") || "default";
    const tabGroupName = `chihiros-notification-message-${scopeToken}`;
    const blocks = notifications.map((notification, index) => {
      const model = this.frameModel(notification, stateValue);
      const source = model.notification;
      let parsedType = String(source.parsed_type || source.type || stateValue || card.tr("unknown"));
      let meaning = parsedType;
      const details = [];
      if (model.mode === 0x0A && model.bytes.length >= 14) {
        const runtimeMinutes = (model.bytes[model.bytes.length - 3] << 8) | model.bytes[model.bytes.length - 2];
        parsedType = "RUNTIME";
        meaning = `${card.tr("runtime")}: ${runtimeMinutes >= 5000 ? "≥ " : ""}${runtimeMinutes} min`;
      } else if (model.mode === 0xFE) {
        parsedType = "STATUS_SNAPSHOT";
        meaning = "Status-Snapshot 0xFE";
      }
      const described = typeof describe === "function" ? (describe(model, index) || {}) : {};
      parsedType = described.parsedType || parsedType;
      meaning = described.meaning || meaning;
      if (Array.isArray(described.details)) details.push(...described.details);
      const defaultTabLabels = {
        0x0A: english ? "Runtime" : "Laufzeit",
        0xFE: card.tr("status"),
      };
      const tabLabel = described.tabLabel || defaultTabLabels[model.mode] || parsedType;
      const decodeLines = [
        `${card.tr("direction")}: ${String(source.direction || source.dir || "RX").toUpperCase()}`,
        `${card.tr("command")}: ${model.command === null ? "-" : `0x${hexByte(model.command)}`}`,
        `${card.tr("firmware")}: ${model.firmware ?? source.firmware_version ?? "-"}`,
        `${card.tr("length")}: ${model.length ?? "-"}`,
        `${card.tr("message_id")}: ${model.bytes.length > 4 ? `${hexByte(model.bytes[3])} ${hexByte(model.bytes[4])}` : "-"}`,
        `Mode: ${model.mode === null ? "-" : `0x${hexByte(model.mode)}`}`,
        `${card.tr("parameters")}: ${model.params.length ? model.params.map(hexByte).join(" ") : "-"}`,
        `${card.tr("checksum")}: ${model.checksum === null ? "-" : `0x${hexByte(model.checksum)}`}`,
        `${card.tr("meaning")}: ${meaning}`,
        ...details,
      ];
      const tabId = `chihiros-notification-tab-${scopeToken}-${index}`;
      const modeLabel = model.mode === null ? "" : ` · 0x${hexByte(model.mode)}`;
      const tabTitle = `${index + 1} · ${tabLabel}${modeLabel}`;
      return `
        <input class="led-notification-tab-input" type="radio" name="${tabGroupName}" id="${tabId}" ${index === 0 ? "checked" : ""}>
        <label class="led-notification-tab-label" for="${tabId}">${card.escapeHtml(tabTitle)}</label>
        <div class="led-notification-tab-panel">
          <section class="led-notification-block"><h3>${index + 1}. ${card.tr("decode")} · ${card.escapeHtml(parsedType)}</h3><pre>${card.escapeHtml(decodeLines.join("\n"))}</pre></section>
          <section class="led-notification-block"><h3>${index + 1}. ${card.tr("encode_hex")}</h3><pre>${card.escapeHtml(model.rawHex || card.tr("unknown"))}</pre></section>
        </div>`;
    }).join("");
    const empty = `<section class="led-notification-block wide"><h3>${card.tr("last_notification")}</h3><pre>${card.escapeHtml(emptyText || card.tr("unknown"))}</pre></section>`;
    const dialogTitle = title || card.tr("last_notification");
    const subtitleHtml = subtitle ? `<small>${card.escapeHtml(subtitle)}</small>` : "";
    return card.sharedModalDialog({
      title: dialogTitle,
      sectionClass: "modal card led-notification-dialog",
      headerHtml: `
        <header class="led-channel-history-head">
          <div><h2>${card.escapeHtml(dialogTitle)}</h2>${subtitleHtml}</div>
          <button type="button" class="led-channel-history-close" data-action="close-dialog" title="${card.tr("close")}" aria-label="${card.tr("close")}"><span aria-hidden="true">&#10005;</span></button>
        </header>`,
      bodyHtml: blocks
        ? `<div class="led-notification-tabs" style="--notification-tab-count:${notifications.length}">${blocks}</div>`
        : `<div class="led-notification-grid">${empty}</div>`,
    });
  },
};
