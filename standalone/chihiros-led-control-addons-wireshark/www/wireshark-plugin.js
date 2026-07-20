window.ChihirosPlugins = window.ChihirosPlugins || {};

window.ChihirosPlugins.wireshark = {
  id: "wireshark",
  title: "Wireshark",
  tabs: ["wireshark"],
  version: "1.0.0",
  styles() {
    return `
      <style>
        .wireshark-config-fields { display:grid; grid-template-columns:minmax(0, 1fr); gap:10px; margin-top:10px; }
        .wireshark-config-fields label { display:grid; grid-template-columns:126px minmax(0,1fr); gap:8px; align-items:center; min-width:0; color:rgba(255,255,255,.78); font-weight:700; font-size:12px; }
        .wireshark-config-fields input { min-height:34px; min-width:0; border:1px solid rgba(81,154,190,.35); border-radius:6px; background:rgba(255,255,255,.08); color:var(--primary-text-color); padding:0 10px; font:inherit; }
        .wireshark-page { display:grid; grid-template-columns:minmax(0, 1fr); gap:6px; overflow-x:auto; }
        .wireshark-capture-dialog { position:fixed; inset:0; z-index:40; display:grid; place-items:center; background:rgba(0,0,0,.42); backdrop-filter:blur(2px); }
        .wireshark-capture-dialog-card { width:min(460px, calc(100vw - 32px)); border:1px solid rgba(3,201,255,.45); border-radius:6px; background:linear-gradient(145deg, rgba(3,201,255,.16), rgba(11,21,24,.98) 46%, rgba(0,0,0,.96)); box-shadow:0 18px 60px rgba(0,0,0,.48), 0 0 0 1px rgba(255,255,255,.04) inset; padding:16px; }
        .wireshark-capture-dialog-card h2 { margin:0 0 8px; font-size:16px; color:var(--primary-text-color); }
        .wireshark-capture-dialog-card p { margin:0 0 12px; color:rgba(255,255,255,.74); }
        .wireshark-capture-dialog-card span { display:block; color:rgba(255,255,255,.66); font-size:12px; margin-bottom:4px; }
        .wireshark-capture-dialog-card strong { display:block; font:700 20px/1.25 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; margin-bottom:14px; color:#03c9ff; }
        .wireshark-capture-dialog-actions { display:flex; justify-content:flex-end; gap:8px; }
        .wireshark-plugin-card { min-width:0; min-height:0; padding-top:10px; border-color:rgba(3,201,255,.30); background:linear-gradient(145deg, rgba(3,201,255,.055), rgba(57,211,83,.035) 42%, rgba(0,0,0,.16)); box-shadow:inset 3px 0 0 rgba(3,201,255,.30); }
        .wireshark-adb-panel { display:grid; gap:5px; margin-bottom:6px; padding:0 0 6px; border-bottom:1px solid rgba(3,201,255,.16); }
        .adb-file-device-row { display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1fr); gap:8px; align-items:center; }
        .adb-row { display:grid; gap:6px; }
        .adb-row.three { grid-template-columns:minmax(220px, .8fr) 110px 190px minmax(260px, .8fr); align-items:center; }
        .adb-row.file-select { grid-template-columns:minmax(0, 1fr) 144px; align-items:center; }
        .adb-row label { display:grid; grid-template-columns:126px minmax(0, 1fr); gap:8px; align-items:center; color:rgba(255,255,255,.78); font-size:12px; font-weight:700; }
        .adb-row.three .adb-port-field { grid-template-columns:34px minmax(58px, 1fr); }
        .adb-row.three .adb-auth-field { grid-template-columns:36px minmax(90px, 1fr); }
        .adb-row input, .adb-row select { min-height:28px; min-width:0; border:1px solid rgba(81,154,190,.42); border-radius:5px; background:linear-gradient(180deg, rgba(255,255,255,.105), rgba(3,201,255,.045)); color:var(--primary-text-color); padding:0 8px; font:inherit; }
        .adb-row button { min-height:28px; white-space:nowrap; padding:0 10px; }
        .adb-checks { display:flex; flex-wrap:wrap; gap:8px 12px; align-items:center; min-height:24px; color:rgba(255,255,255,.74); font-size:12px; padding-top:0; }
        .adb-checks label { display:inline-flex; align-items:center; gap:5px; }
        .adb-checks input { accent-color:#03c9ff; }
        .adb-state { display:flex; flex-wrap:wrap; gap:8px; margin-left:auto; color:rgba(255,255,255,.64); font-size:12px; }
        .adb-state span { display:inline-flex; align-items:center; min-height:20px; border:1px solid rgba(81,154,190,.25); border-radius:999px; padding:0 8px; background:rgba(0,0,0,.16); }
        .adb-state span.ok { border-color:rgba(57,211,83,.42); color:#66d36d; background:rgba(57,211,83,.08); }
        .plugin-file-button { display:inline-flex; align-items:center; justify-content:center; min-height:30px; border:1px solid rgba(81,154,190,.45); border-radius:6px; background:rgba(0,0,0,.16); color:var(--primary-text-color); padding:0 10px; font-weight:700; cursor:pointer; white-space:nowrap; }
        .plugin-file-button input { display:none; }
        .wireshark-plugin-card textarea { width:100%; min-height:64px; margin-top:6px; border:1px solid rgba(81,154,190,.35); border-radius:5px; background:rgba(0,0,0,.22); color:var(--primary-text-color); padding:8px; resize:vertical; font:11px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
        .wireshark-gui-actions { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; padding:7px 8px; border:1px solid rgba(81,154,190,.18); border-radius:6px; background:linear-gradient(90deg, rgba(3,201,255,.08), rgba(255,147,0,.045), rgba(0,0,0,.08)); align-items:center; }
        .wireshark-gui-actions button { min-height:30px; white-space:nowrap; padding:0 11px; }
        .wireshark-gui-actions .warn { border-color:rgba(255,147,0,.75); color:#ffc078; }
        .wireshark-gui-actions .success { min-height:30px; border:1px solid rgba(57,211,83,.65); border-radius:6px; background:rgba(20,110,54,.45); color:#e9fff0; font:inherit; padding:0 12px; cursor:pointer; }
        .wireshark-gui-actions .danger { min-height:30px; border:1px solid rgba(255,77,79,.65); border-radius:6px; background:rgba(128,28,31,.58); color:#fff1f1; font:inherit; padding:0 12px; cursor:pointer; }
        .wireshark-progress { display:grid; grid-template-columns:180px minmax(0, 1fr) 48px; gap:8px; align-items:center; margin-top:6px; color:rgba(255,255,255,.72); font-size:12px; }
        .wireshark-progress div { height:12px; border:1px solid rgba(81,154,190,.35); border-radius:3px; background:rgba(0,0,0,.18); overflow:hidden; }
        .wireshark-progress i { display:block; height:100%; background:linear-gradient(90deg, #2563eb, #03c9ff); }
        .wireshark-progress b { text-align:right; }
        .plugin-status { margin-top:6px; border-radius:5px; padding:5px 8px; font-weight:700; }
        .plugin-status.ok { border:1px solid rgba(57,211,83,.35); color:#66d36d; background:rgba(57,211,83,.08); }
        .plugin-status.error { border:1px solid rgba(255,77,79,.45); color:#ff8a8a; background:rgba(255,77,79,.08); }
        .packet-list { min-width:0; max-width:100%; border:1px solid rgba(81,154,190,.25); border-radius:4px; background:linear-gradient(180deg, rgba(255,255,255,.035), rgba(0,0,0,.16)); overflow:auto; margin-top:6px; scrollbar-gutter:stable; }
        .packet-list-head, .packet-row { display:grid; grid-template-columns:var(--ws-col-compare,58px) var(--ws-col-row,44px) var(--ws-col-time,150px) var(--ws-col-source,190px) var(--ws-col-destination,190px) var(--ws-col-protocol,120px) var(--ws-col-command,64px) var(--ws-col-mode,64px) var(--ws-col-params,220px) var(--ws-col-encoded,360px); gap:8px; align-items:center; min-width:var(--ws-table-width,1506px); }
        .packet-list-head { min-height:32px; padding:0 10px; border-bottom:1px solid rgba(3,201,255,.14); background:rgba(3,201,255,.07); color:rgba(255,255,255,.68); font-size:11px; font-weight:700; }
        .packet-list-head button { position:relative; min-height:32px; border:0; background:transparent; color:inherit; font:inherit; font-weight:700; padding:0 10px 0 0; text-align:left; cursor:pointer; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .packet-list-head button:hover { color:#03c9ff; }
        .packet-resize { position:absolute; top:5px; right:0; width:9px; height:22px; border-right:2px solid rgba(3,201,255,.5); cursor:col-resize; opacity:.7; touch-action:none; }
        .packet-resize:hover { opacity:1; border-right-color:#03c9ff; }
        .packet-list-body { min-height:86px; max-height:180px; overflow:visible; }
        .packet-row { width:100%; min-height:30px; padding:0 10px; border:0; border-bottom:1px solid rgba(255,255,255,.06); background:transparent; color:inherit; cursor:pointer; text-align:left; font:12px/1.3 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
        .packet-row:hover, .packet-row.active { background:rgba(3,201,255,.12); }
        .packet-row.compare-selected { background:rgba(255,196,0,.10); box-shadow:inset 3px 0 0 rgba(255,196,0,.72); }
        .packet-row.compare-selected.active { background:linear-gradient(90deg, rgba(255,196,0,.16), rgba(3,201,255,.12)); }
        .packet-row span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .packet-compare-head, .packet-compare-cell { display:flex; align-items:center; justify-content:center; min-width:0; }
        .packet-compare-head { color:#ffc400; font-weight:800; }
        .packet-compare-cell input { width:16px; height:16px; accent-color:#ffc400; cursor:pointer; }
        .packet-empty { padding:12px; color:rgba(255,255,255,.58); }
        .wireshark-log-panel { margin-top:6px; }
        .wireshark-log-head { display:block; min-height:24px; color:rgba(255,255,255,.78); font-size:12px; font-weight:700; }
        .wireshark-log-panel textarea { min-height:150px; max-height:210px; margin-top:0; }
        @media (max-width: 700px) {
          .adb-file-device-row, .adb-row.three, .adb-row.file-select, .wireshark-progress { grid-template-columns:1fr; }
          .adb-row label, .adb-row.three .adb-port-field { grid-template-columns:1fr; gap:5px; }
          .packet-list-head, .packet-row { min-width:var(--ws-table-width,1120px); }
        }
      </style>`;
  },

  translations: {
    de: {
      adb_action_running: "ADB-Aktion läuft",
      adb_connect: "ADB verbinden",
      adb_debug_guide: "ADB Debug Anleitung",
      adb_usb: "ADB USB freischalten",
      all_packets: "alle Protokollpakete",
      app_log_loaded: "Vergleich App-Log geladen",
      app_package: "App Paket",
      auto_load_failed: "Auto-Laden fehlgeschlagen",
      browser_file: "Browser-Datei",
      bugreport_fetch: "Bugreport holen",
      capture_dialog_no_root: "Kein Root erkannt. Befehle können jetzt in der App ausgeführt werden.",
      capture_dialog_no_root_hint: "Danach Mitschnitt Ende drücken. Die HCI-Datei wird per Bugreport geholt.",
      capture_dialog_root: "Root erkannt. Befehle können jetzt in der App ausgeführt werden.",
      capture_dialog_root_hint: "Danach Mitschnitt Ende drücken. Die HCI-Datei wird direkt per Root gelesen.",
      capture_end: "Mitschnitt Ende",
      capture_finished: "Mitschnitt fertig",
      capture_folder: "Capture Ordner",
      capture_loaded: "Mitschnitt geladen",
      capture_running: "Mitschnitt läuft",
      capture_snapshot: "Zwischenstand sichern",
      capture_snapshot_count: "Gesicherte Zwischenstände",
      capture_snapshot_failed: "Zwischenstand fehlgeschlagen",
      capture_snapshot_hint: "Langzeitmodus: Der aktuelle HCI-Stand wird alle 15 Minuten gesichert, ohne die Aufnahme zu beenden.",
      capture_snapshot_last: "Letzter Zwischenstand",
      capture_snapshot_next: "Nächster Zwischenstand",
      capture_snapshot_ok: "Zwischenstand gesichert",
      capture_start: "Mitschnitt Start",
      command: "Cmd",
      compare_app_log: "Vergleich App-Log",
      destination: "Destination",
      details_log: "Details / Log",
      device: "Gerät",
      device_mac: "Gerät / MAC",
      device_notify: "Geräte-Notify",
      device_return: "Geräte-Return",
      devices_reloaded: "Geräte aus aktuellem Mitschnitt neu geladen",
      encode_hex: "Encode / Hex",
      extract_frames: "Frames extrahieren",
      file: "Datei",
      file_auto_loaded: "Datei automatisch geladen",
      file_loaded: "Datei geladen",
      files_refreshed: "Dateien aktualisiert",
      frames: "Frames",
      hci_fetched: "HCI Log geholt",
      hci_log_folder: "HCI-Log Ordner",
      load_file: "Datei laden",
      mark_compare: "Für Vergleich markieren",
      clear_marked: "markierte löschen",
      mode: "Mode",
      no_frame_selected: "Kein Frame ausgewählt.",
      no_frames: "Keine Chihiros Frames gefunden.",
      no_log_file: "Keine Logdatei gefunden",
      params: "Parameter / Return",
      protocol: "Protocol",
      ready: "Bereit",
      refresh: "Aktualisieren",
      reload_devices: "Geräte neu laden",
      root_check: "Root prüfen",
      root_direct: "root direkt",
      root_ok: "Root OK",
      root_unchecked: "Root nicht geprüft",
      runtime: "Laufzeit",
      select: "Auswählen",
      source: "Source",
      start: "Start",
      target: "Ziel",
      target_usb: "Ziel: USB/default",
      time: "Zeit",
      wireshark_config: "Wireshark Config",
      wireshark_config_subtitle: "Pfade für HCI-Logs und Capture-Exporte",
    },
    en: {
      adb_action_running: "ADB action running",
      adb_connect: "Connect ADB",
      adb_debug_guide: "ADB debug guide",
      adb_usb: "Enable ADB USB",
      all_packets: "all protocol packets",
      app_log_loaded: "App log comparison loaded",
      app_package: "App package",
      auto_load_failed: "Auto-load failed",
      browser_file: "Browser file",
      bugreport_fetch: "Fetch bugreport",
      capture_dialog_no_root: "Root not detected. Commands can now be run in the app.",
      capture_dialog_no_root_hint: "Then press Capture End. The HCI file will be fetched by bugreport.",
      capture_dialog_root: "Root detected. Commands can now be run in the app.",
      capture_dialog_root_hint: "Then press Capture End. The HCI file will be read directly with root.",
      capture_end: "Capture End",
      capture_finished: "Capture finished",
      capture_folder: "Capture folder",
      capture_loaded: "Capture loaded",
      capture_running: "Capture running",
      capture_snapshot: "Save snapshot",
      capture_snapshot_count: "Saved snapshots",
      capture_snapshot_failed: "Snapshot failed",
      capture_snapshot_hint: "Long capture mode: the current HCI state is saved every 15 minutes without stopping capture.",
      capture_snapshot_last: "Last snapshot",
      capture_snapshot_next: "Next snapshot",
      capture_snapshot_ok: "Snapshot saved",
      capture_start: "Capture Start",
      command: "Cmd",
      compare_app_log: "Compare app log",
      destination: "Destination",
      details_log: "Details / Log",
      device: "Device",
      device_mac: "Device / MAC",
      device_notify: "device notify",
      device_return: "device return",
      devices_reloaded: "Devices reloaded from current capture",
      encode_hex: "Encode / Hex",
      extract_frames: "Extract frames",
      file: "File",
      file_auto_loaded: "File automatically loaded",
      file_loaded: "File loaded",
      files_refreshed: "Files refreshed",
      frames: "Frames",
      hci_fetched: "HCI log fetched",
      hci_log_folder: "HCI log folder",
      load_file: "Load file",
      mark_compare: "Mark for comparison",
      clear_marked: "clear marked",
      mode: "Mode",
      no_frame_selected: "No frame selected.",
      no_frames: "No Chihiros frames found.",
      no_log_file: "No log file found",
      params: "Parameter / Return",
      protocol: "Protocol",
      ready: "Ready",
      refresh: "Refresh",
      reload_devices: "Reload devices",
      root_check: "Check root",
      root_direct: "root direct",
      root_ok: "Root OK",
      root_unchecked: "Root not checked",
      runtime: "Runtime",
      select: "Select",
      source: "Source",
      start: "Start",
      target: "Target",
      target_usb: "Target: USB/default",
      time: "Time",
      wireshark_config: "Wireshark Config",
      wireshark_config_subtitle: "Paths for HCI logs and capture exports",
    },
  },

  tr(card, key) {
    const language = typeof card.language === "function"
      ? card.language()
      : String((card.uiSettings && card.uiSettings.language) || "de");
    const table = language === "en" ? this.translations.en : this.translations.de;
    return (table && table[key]) || this.translations.de[key] || key;
  },

  detailPayload(frame) {
    if (!frame) return null;
    const row = frame.raw_json && typeof frame.raw_json === "object" ? { ...frame.raw_json } : { ...frame };
    if (frame.command !== undefined && frame.command !== "") row.cmd = /^\d+$/.test(String(frame.command)) ? Number(frame.command) : frame.command;
    if (frame.mode !== undefined && frame.mode !== "") row.mode = /^\d+$/.test(String(frame.mode)) ? Number(frame.mode) : frame.mode;
    if (frame.params !== undefined && frame.params !== "") row.parm = frame.params;
    if (frame.hex) row.hex = frame.hex;
    delete row.raw_json;
    return row;
  },

  mergeLogFile(list, logFile) {
    const basename = (value) => String(value || "").split(/[\\/]/).pop();
    const path = String(logFile || "");
    if (!path) return Array.isArray(list) ? list : [];
    const current = Array.isArray(list) ? list.slice() : [];
    if (!current.some((file) => String(file.path || file.name || "") === path || basename(file.path || file.name) === basename(path))) {
      current.unshift({ name: basename(path), path });
    }
    return current;
  },

  bindGlobalCompareHandler() {
    if (window.__chihirosWiresharkCompareBoundVersion === this.version) return;
    window.__chihirosWiresharkCompareBoundVersion = this.version;
    const handleCompareEvent = async (event) => {
      const path = typeof event.composedPath === "function" ? event.composedPath() : [];
      const target = path.find((node) => (
        node &&
        typeof node.getAttribute === "function" &&
        node.hasAttribute("data-wireshark-compare-open")
      )) || (event.target && event.target.closest
        ? event.target.closest("[data-wireshark-compare-open]")
        : null);
      if (!target) return;
      const card = path.find((node) => node && node.localName === "chihiros-led-core-card") ||
        (target.closest ? target.closest("chihiros-led-core-card") : null);
      if (!card || !window.ChihirosPlugins || !window.ChihirosPlugins.wireshark) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const now = Date.now();
      if (card.__wiresharkCompareLastRun && now - card.__wiresharkCompareLastRun < 750) return;
      card.__wiresharkCompareLastRun = now;
      if (typeof card.runWiresharkCompareFromCore === "function") {
        await card.runWiresharkCompareFromCore();
        return;
      }
      const plugin = window.ChihirosPlugins.wireshark;
      const tr = (key) => plugin.tr(card, key);
      card.wiresharkPlugin = {
        ...(card.wiresharkPlugin || {}),
        adbOutput: `${tr("adb_action_running")}: compare-app-log...`,
        loading: true,
        error: "",
      };
      card.render();
      await plugin.runAdbAction(card, "compare-app-log", card.querySelector("[data-wireshark-input]"), tr, plugin.mergeLogFile.bind(plugin));
    };
    document.addEventListener("pointerdown", handleCompareEvent, true);
    document.addEventListener("click", handleCompareEvent, true);
  },

  renderPanel(card) {
    if (!card.config.addon_mode) return "";
    const tr = (key) => this.tr(card, key);
    const state = card.wiresharkPlugin || {};
    const adb = state.adb || {};
    const adbIp = String(adb.adb_ip || "172.20.48.8");
    const adbPort = String(adb.adb_port || "5555");
    const appPackage = String(adb.app_package || "cn.chihiros.chihiros_magic_new");
    const captureFile = String(adb.capture_file || "");
    const authMethod = String(adb.auth_method || "key");
    const files = Array.isArray(state.files) ? state.files : [];
    const basename = (value) => String(value || "").split(/[\\/]/).pop();
    const frames = state.result && Array.isArray(state.result.frames) ? state.result.frames : [];
    const normalizeDeviceKey = (value) => {
      const text = String(value || "").trim();
      return text.includes(":") ? text.toUpperCase() : text;
    };
    const frameDevices = () => {
      const choices = new Map();
      const add = (mac, name) => {
        const key = normalizeDeviceKey(mac);
        if (!key) return;
        const label = String(name || "").trim();
        const text = label || key;
        if (!choices.has(key)) choices.set(key, text);
      };
      frames.forEach((frame) => {
        const raw = frame.raw_json && typeof frame.raw_json === "object" ? frame.raw_json : frame;
        if (raw.names && typeof raw.names === "object") {
          Object.entries(raw.names).forEach(([mac, name]) => add(mac, name));
        }
        if (Array.isArray(raw.macs)) raw.macs.forEach((mac) => add(mac, ""));
        add(raw.src_mac, raw.src_name);
        add(raw.dest_mac, raw.dest_name);
      });
      return Array.from(choices.entries()).map(([value, label]) => ({ value, label }));
    };
    const endpointLabel = (value) => {
      const text = String(value || "").trim();
      const match = text.match(/\(([^)]+)\)\s*$/);
      return match && match[1] ? match[1].trim() : text;
    };
    const endpointText = (mac, name) => {
      const macText = String(mac || "").trim();
      const nameText = String(name || "").trim();
      if (nameText) return endpointLabel(nameText);
      return macText || nameText;
    };
    const selectedDeviceDisplay = () => {
      const mac = normalizeDeviceKey(adb.local_mac || "");
      if (!mac) return tr("device");
      const match = frameDevices().find((item) => item.value === mac);
      if (match && match.label !== mac) return match.label;
      return mac;
    };
    const rowSource = (frame) => {
      if (frame.source) return endpointLabel(frame.source);
      const raw = frame.raw_json && typeof frame.raw_json === "object" ? frame.raw_json : {};
      const direction = String(raw.dir || frame.direction || "").toLowerCase();
      if (direction === "tx") return endpointText(raw.src_mac, raw.src_name) || raw.host_name || "";
      if (direction === "rx") return endpointText(raw.src_mac, raw.src_name) || endpointText(raw.dest_mac, raw.dest_name) || selectedDeviceDisplay();
      return endpointText(raw.src_mac, raw.src_name) || "";
    };
    const rowDestination = (frame) => {
      if (frame.destination) return endpointLabel(frame.destination);
      const raw = frame.raw_json && typeof frame.raw_json === "object" ? frame.raw_json : {};
      const direction = String(raw.dir || frame.direction || "").toLowerCase();
      if (direction === "tx") return endpointText(raw.dest_mac, raw.dest_name) || selectedDeviceDisplay();
      if (direction === "rx") return raw.host_name || endpointText(raw.dest_mac, raw.dest_name) || "";
      return endpointText(raw.dest_mac, raw.dest_name) || "";
    };
    const chihirosProtocol = (command, fallback = "") => {
      const text = String(command ?? "").trim();
      const value = text.toLowerCase().startsWith("0x") ? parseInt(text, 16) : parseInt(text, 10);
      if (value === 90) return "Chihiros 5A";
      if (value === 165) return "Chihiros A5";
      if (value === 91) return "Chihiros 5B";
      return fallback || "";
    };
    const rowProtocol = (frame) => {
      const raw = frame.raw_json && typeof frame.raw_json === "object" ? frame.raw_json : {};
      const chihiros = chihirosProtocol(frame.command || raw.cmd, frame.protocol || "");
      if (chihiros && chihiros !== "ATT") return chihiros;
      const att = String(raw.att || frame.parsed_type || "").trim().toLowerCase();
      if (att === "notify") return "Notify";
      if (att === "indicate") return "Indicate";
      return chihiros || frame.protocol || "";
    };
    const visibleFiles = files.filter((file) => /\.(log|cfa|pcap|pcapng)$/i.test(basename(file.path || file.name)));
    const fileOptions = [`<option value="">${tr("select")}</option>`].concat(visibleFiles.map((file) => {
      const value = String(file.path || file.name || "");
      const label = `${file.name || value} ${file.size ? `(${file.size} B)` : ""}`;
      const selected = value === captureFile || basename(value) === basename(captureFile);
      return `<option value="${card.escapeHtml(value)}" ${selected ? "selected" : ""}>${card.escapeHtml(label)}</option>`;
    })).join("");
    const devices = frameDevices();
    const selectedMac = normalizeDeviceKey(adb.local_mac || "");
    const deviceOptions = [`<option value="">${tr("select")}</option>`].concat(devices.map((item) => (
      `<option value="${card.escapeHtml(item.value)}" ${item.value === selectedMac ? "selected" : ""}>${card.escapeHtml(item.label)}</option>`
    ))).join("");
    const defaultColumnWidths = { compare: 58, row: 44, time: 150, source: 190, destination: 190, protocol: 120, command: 64, mode: 64, params: 220, encoded: 360 };
    const storedWidths = state.columnWidths && typeof state.columnWidths === "object" ? state.columnWidths : {};
    const columnWidths = Object.fromEntries(Object.entries(defaultColumnWidths).map(([key, value]) => [key, Math.max(42, Number(storedWidths[key] || value))]));
    const tableWidth = Object.values(columnWidths).reduce((sum, value) => sum + value, 0) + 8 * (Object.keys(columnWidths).length - 1) + 20;
    const tableStyle = Object.entries(columnWidths).map(([key, value]) => `--ws-col-${key}:${value}px`).concat(`--ws-table-width:${tableWidth}px`).join(";");
    const sortState = state.sort || {};
    const sortKey = String(sortState.key || "");
    const sortDirection = sortState.direction === "desc" ? "desc" : "asc";
    const displayFrames = frames.map((frame, index) => ({ frame, index }));
    const sortValue = (value) => {
      const text = String(value ?? "");
      if (/^\d+$/.test(text)) return [0, Number(text)];
      const number = Number(text);
      if (Number.isFinite(number) && text.trim() !== "") return [1, number];
      return [2, text.toLocaleLowerCase()];
    };
    const rowParams = (frame) => {
      const raw = frame.raw_json && typeof frame.raw_json === "object" ? frame.raw_json : {};
      const command = frame.command || raw.cmd;
      if (chihirosProtocol(command) && Array.isArray(raw.parm)) return `[${raw.parm.join(", ")}]`;
      return frame.parsed_summary || frame.params || "";
    };
    const columnValue = (frame, index, key) => ({
      row: frame.line || index + 1,
      time: frame.timestamp || frame.time || "",
      source: rowSource(frame),
      destination: rowDestination(frame),
      protocol: rowProtocol(frame),
      command: frame.command || "",
      mode: frame.mode || "",
      params: rowParams(frame),
      encoded: frame.hex || "",
    }[key] ?? "");
    if (sortKey) {
      displayFrames.sort((left, right) => {
        const a = sortValue(columnValue(left.frame, left.index, sortKey));
        const b = sortValue(columnValue(right.frame, right.index, sortKey));
        const cmp = a[0] - b[0] || (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0);
        return sortDirection === "desc" ? -cmp : cmp;
      });
    }
    const selectedIndex = Math.max(0, Math.min(Number(state.selectedIndex || 0), Math.max(0, frames.length - 1)));
    const selected = frames[selectedIndex] || null;
    const compareFrameIndexes = new Set((Array.isArray(state.compareFrameIndexes) ? state.compareFrameIndexes : []).map((value) => Number(value)).filter(Number.isInteger));
    const compareCount = compareFrameIndexes.size;
    const rootOk = Boolean(state.rootOk);
    const rootChecked = Boolean(state.rootChecked);
    const rootDirect = Boolean(adb.root_direct);
    const captureRunning = Boolean(state.captureRunning);
    const captureStartedAt = Number(state.captureStartedAt || Date.now());
    const elapsed = captureRunning ? Math.max(0, Math.floor((Date.now() - captureStartedAt) / 1000)) : 0;
    const elapsedText = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;
    const snapshotCount = Number(state.captureSnapshotCount || 0);
    const snapshotLast = state.captureSnapshotLastAt ? new Date(Number(state.captureSnapshotLastAt)).toLocaleString() : "–";
    const snapshotNext = state.captureSnapshotNextAt ? new Date(Number(state.captureSnapshotNextAt)).toLocaleString() : "–";
    const sortSuffix = (key) => sortKey === key ? (sortDirection === "desc" ? " ▼" : " ▲") : "";
    const rows = displayFrames.map(({ frame, index }) => `
          <div role="button" tabindex="0" class="packet-row ${index === selectedIndex ? "active" : ""} ${compareFrameIndexes.has(index) ? "compare-selected" : ""}" data-wireshark-select="${index}">
            <span class="packet-compare-cell"><input type="checkbox" data-wireshark-compare-frame="${index}" ${compareFrameIndexes.has(index) ? "checked" : ""} title="${tr("mark_compare")}" aria-label="${tr("mark_compare")} ${index + 1}"></span>
            <span>${card.escapeHtml(columnValue(frame, index, "row"))}</span>
            <span>${card.escapeHtml(columnValue(frame, index, "time"))}</span>
            <span>${card.escapeHtml(columnValue(frame, index, "source"))}</span>
            <span>${card.escapeHtml(columnValue(frame, index, "destination"))}</span>
            <span>${card.escapeHtml(columnValue(frame, index, "protocol"))}</span>
            <span>${card.escapeHtml(columnValue(frame, index, "command"))}</span>
            <span>${card.escapeHtml(columnValue(frame, index, "mode"))}</span>
            <span>${card.escapeHtml(columnValue(frame, index, "params"))}</span>
            <span>${card.escapeHtml(columnValue(frame, index, "encoded"))}</span>
          </div>`).join("");
    const detailLog = state.updateOutput || (selected ? JSON.stringify(this.detailPayload(selected), null, 2) : tr("no_frame_selected"));
    const result = state.error ? `<div class="plugin-status error">${card.escapeHtml(state.error)}</div>` : "";
    const adbOutput = String(state.adbOutput || "").trim();
    const adbStatus = adbOutput ? `<div class="plugin-status ${/^FAIL\b/i.test(adbOutput) ? "error" : "ok"}">${card.escapeHtml(adbOutput)}</div>` : "";
    const captureDialog = captureRunning ? `
      <div class="wireshark-capture-dialog" role="dialog" aria-label="${card.escapeHtml(tr("capture_running"))}">
        <div class="wireshark-capture-dialog-card">
          <h2>${rootDirect || rootOk ? tr("capture_dialog_root") : tr("capture_dialog_no_root")}</h2>
          <p>${rootDirect || rootOk ? tr("capture_dialog_root_hint") : tr("capture_dialog_no_root_hint")}</p>
          <p>${tr("capture_snapshot_hint")}</p>
          <span>${tr("start")}: ${card.escapeHtml(state.captureStartLabel || "")}</span>
          <strong>${tr("runtime")}: ${elapsedText}</strong>
          <span>${tr("capture_snapshot_count")}: ${snapshotCount}</span>
          <span>${tr("capture_snapshot_last")}: ${card.escapeHtml(snapshotLast)}</span>
          <span>${tr("capture_snapshot_next")}: ${card.escapeHtml(snapshotNext)}</span>
          <div class="wireshark-capture-dialog-actions">
            <button type="button" class="secondary" data-wireshark-adb-action="capture-snapshot" ${state.captureSnapshotRunning ? "disabled" : ""}>${tr("capture_snapshot")}</button>
            <button type="button" class="danger" data-wireshark-adb-action="capture-end">${tr("capture_end")}</button>
          </div>
        </div>
      </div>` : "";
    return `
      ${this.styles()}
      <div class="wireshark-page">
        ${captureDialog}
        <section class="card wireshark-plugin-card">
          <div class="wireshark-adb-panel">
            <div class="adb-file-device-row">
              <div class="adb-row file-select">
                <label><span>${tr("file")}</span><select data-wireshark-adb-field="capture_file">${fileOptions}</select></label>
                <button type="button" class="secondary" data-wireshark-adb-action="list-files">${tr("refresh")}</button>
              </div>
              <div class="adb-row file-select">
                <label><span>${tr("device_mac")}</span><select data-wireshark-device-select>${deviceOptions}</select></label>
                <button type="button" class="secondary" data-wireshark-refresh-devices>${tr("reload_devices")}</button>
              </div>
            </div>
            <div class="adb-row three">
              <label><span>ADB IP</span><input type="text" data-wireshark-adb-field="adb_ip" value="${card.escapeHtml(adbIp)}"></label>
              <label class="adb-port-field"><span>Port</span><input type="text" inputmode="numeric" data-wireshark-adb-field="adb_port" value="${card.escapeHtml(adbPort)}"></label>
              <label class="adb-auth-field"><span>Auth</span><select data-wireshark-adb-field="auth_method">
                <option value="key" ${authMethod === "key" ? "selected" : ""}>key</option>
                <option value="none" ${authMethod === "none" ? "selected" : ""}>none</option>
                <option value="password" ${authMethod === "password" ? "selected" : ""}>password</option>
              </select></label>
              <label><span>${tr("app_package")}</span><input type="text" data-wireshark-adb-field="app_package" value="${card.escapeHtml(appPackage)}"></label>
            </div>
            <div class="adb-checks">
              <label><input type="checkbox" data-wireshark-adb-field="device_notify" ${adb.device_notify === false ? "" : "checked"}>${tr("device_notify")}</label>
              <label><input type="checkbox" data-wireshark-adb-field="device_return" ${adb.device_return === false ? "" : "checked"}>${tr("device_return")}</label>
              <label><input type="checkbox" data-wireshark-adb-field="all_packets" ${adb.all_packets ? "checked" : ""}>${tr("all_packets")}</label>
              <label><input type="checkbox" data-wireshark-adb-field="strip_hci" ${adb.strip_hci ? "checked" : ""}>strip-hci</label>
              <label><input type="checkbox" data-wireshark-adb-field="keep_temp" ${adb.keep_temp ? "checked" : ""}>keep-temp</label>
              <label><input type="checkbox" data-wireshark-adb-field="debug" ${adb.debug ? "checked" : ""}>debug</label>
              <label><input type="checkbox" data-wireshark-adb-field="root_direct" ${adb.root_direct ? "checked" : ""}>${tr("root_direct")}</label>
              <div class="adb-state">
                <span class="${rootOk ? "ok" : ""}">${rootOk ? tr("root_ok") : tr("root_unchecked")}</span>
                <span>${adbIp ? `${tr("target")}: ${card.escapeHtml(adbIp)}:${card.escapeHtml(adbPort)}` : tr("target_usb")}</span>
              </div>
            </div>
          </div>
          <div class="wireshark-gui-actions" aria-label="Wireshark GUI Befehle">
            <button type="button" class="secondary" data-wireshark-adb-action="load-file">${tr("load_file")}</button>
            <label class="plugin-file-button">
              <input type="file" data-wireshark-file accept=".txt,.log,.csv,.json">
              <span>${tr("browser_file")}</span>
            </label>
            <button type="button" class="secondary" data-wireshark-adb-action="btsnoop-jsonl">btsnoop -> JSONL</button>
            <button type="button" class="secondary" data-wireshark-analyze>${tr("extract_frames")}</button>
            <button type="button" class="secondary warn" data-wireshark-adb-action="adb-usb">${tr("adb_usb")}</button>
            <button type="button" class="secondary" data-wireshark-adb-action="connect">${tr("adb_connect")}</button>
            <button type="button" class="secondary" data-wireshark-adb-action="root-check">${tr("root_check")}</button>
            <button type="button" class="secondary" data-wireshark-compare-open>${tr("compare_app_log")}</button>
            <button type="button" class="secondary warn" data-wireshark-compare-test>Compare Test</button>
            ${rootChecked && !rootOk && !rootDirect ? `<button type="button" class="secondary warn" data-wireshark-adb-action="adb-debug-guide">${tr("adb_debug_guide")}</button>` : ""}
            ${rootChecked && !rootOk && !rootDirect ? `<button type="button" class="secondary warn" data-wireshark-adb-action="capture-end">${tr("bugreport_fetch")}</button>` : ""}
            ${rootDirect || rootOk ? `<button type="button" class="success" data-wireshark-adb-action="capture-start">${tr("capture_start")}</button>` : ""}
            ${rootDirect || rootOk ? `<button type="button" class="danger" data-wireshark-adb-action="capture-end">${tr("capture_end")}</button>` : ""}
            ${compareCount ? `<button type="button" class="secondary warn" data-wireshark-compare-clear>${compareCount} ${tr("clear_marked")}</button>` : ""}
          </div>
          <div class="wireshark-progress">
            <span>${card.escapeHtml(state.progressText || tr("ready"))}</span>
            <div><i style="width:${Number(state.loading ? 55 : 100)}%"></i></div>
            <b>${state.loading ? "..." : "100%"}</b>
          </div>
          ${state.result ? `<div class="plugin-status ok">${frames.length} / ${Number(state.result.count || 0)} ${tr("frames")}</div>` : ""}
          ${result}
          ${adbStatus}
          <section class="packet-list legacy-table" style="${card.escapeHtml(tableStyle)}">
            <div class="packet-list-head">
              <span class="packet-compare-head">Vergl.</span>
              <button type="button" data-wireshark-sort="row">#${sortSuffix("row")}<span class="packet-resize" data-wireshark-resize="row"></span></button>
              <button type="button" data-wireshark-sort="time">${tr("time")}${sortSuffix("time")}<span class="packet-resize" data-wireshark-resize="time"></span></button>
              <button type="button" data-wireshark-sort="source">${tr("source")}${sortSuffix("source")}<span class="packet-resize" data-wireshark-resize="source"></span></button>
              <button type="button" data-wireshark-sort="destination">${tr("destination")}${sortSuffix("destination")}<span class="packet-resize" data-wireshark-resize="destination"></span></button>
              <button type="button" data-wireshark-sort="protocol">${tr("protocol")}${sortSuffix("protocol")}<span class="packet-resize" data-wireshark-resize="protocol"></span></button>
              <button type="button" data-wireshark-sort="command">${tr("command")}${sortSuffix("command")}<span class="packet-resize" data-wireshark-resize="command"></span></button>
              <button type="button" data-wireshark-sort="mode">${tr("mode")}${sortSuffix("mode")}<span class="packet-resize" data-wireshark-resize="mode"></span></button>
              <button type="button" data-wireshark-sort="params">${tr("params")}${sortSuffix("params")}<span class="packet-resize" data-wireshark-resize="params"></span></button>
              <button type="button" data-wireshark-sort="encoded">${tr("encode_hex")}${sortSuffix("encoded")}<span class="packet-resize" data-wireshark-resize="encoded"></span></button>
            </div>
            <div class="packet-list-body">
              ${rows || `<div class="packet-empty">${tr("no_frames")}</div>`}
            </div>
          </section>
          <section class="wireshark-log-panel">
            <div class="wireshark-log-head"><span>${tr("details_log")}</span></div>
            <textarea data-wireshark-input spellcheck="false" placeholder="RX: 5B 08 0A 00 01 0A 01 FF FF FF C8 13 88 A4">${card.escapeHtml(detailLog)}</textarea>
          </section>
        </section>
      </div>`;
  },

  renderConfig(card) {
    const tr = (key) => this.tr(card, key);
    const adb = (card.wiresharkPlugin && card.wiresharkPlugin.adb) || {};
    const settings = (card.uiSettings && card.uiSettings.wireshark) || {};
    const hciLogDir = String(adb.hci_log_dir || settings.hci_log_dir || "/config/.chihiros/chihiros_wireshark_control/hci_log");
    const captureDir = String(adb.capture_dir || settings.capture_dir || "/config/.chihiros/chihiros_wireshark_control/captures");
    return `
      ${this.styles()}
      <section class="card config-card plugin-loader-card">
        <div class="config-card-head">
          <div>
            <h2>${tr("wireshark_config")}</h2>
            <small>${tr("wireshark_config_subtitle")}</small>
          </div>
          <span class="db-pill">Wireshark</span>
        </div>
        <div class="wireshark-config-fields">
          <label>
            <span>${tr("hci_log_folder")}</span>
            <input type="text" data-wireshark-adb-field="hci_log_dir" value="${card.escapeHtml(hciLogDir)}">
          </label>
          <label>
            <span>${tr("capture_folder")}</span>
            <input type="text" data-wireshark-adb-field="capture_dir" value="${card.escapeHtml(captureDir)}">
          </label>
        </div>
      </section>`;
  },

  backend(functionName, ...args) {
    const api = window.ChihirosAddonApi;
    if (!api || typeof api.callPluginBackend !== "function") {
      throw new Error("Plugin Backend API nicht verfuegbar");
    }
    return api.callPluginBackend("wireshark", functionName, args);
  },

  backendSettings(card, settings = {}) {
    const language = typeof card.language === "function"
      ? card.language()
      : String((card.uiSettings && card.uiSettings.language) || "de");
    return { ...settings, language: language === "en" ? "en" : "de" };
  },

  async analyzeText(card, input, text, progressText) {
    card.wiresharkPlugin = { ...(card.wiresharkPlugin || {}), text, loading: true, selectedIndex: 0, compareFrameIndexes: [], progressText };
    if (input) input.value = text;
    card.render();
    const analysis = await this.backend("analyze_wireshark_text", text);
    card.wiresharkPlugin = {
      ...(card.wiresharkPlugin || {}),
      text,
      result: analysis,
      loading: false,
      selectedIndex: 0,
      compareFrameIndexes: [],
      progressText: `${progressText}: ${Number(analysis.count || 0)} Frames`,
    };
  },

  async autoLoad(card, input) {
    const tr = (key) => this.tr(card, key);
    card.wiresharkPlugin = card.wiresharkPlugin || {};
    if (card.wiresharkPlugin.autoLoadDone || card.wiresharkPlugin.autoLoading || card.wiresharkPlugin.result) return;
    card.wiresharkPlugin.autoLoading = true;
    const settings = (card.uiSettings && card.uiSettings.wireshark) || {};
    card.wiresharkPlugin.adb = { ...settings, ...(card.wiresharkPlugin.adb || {}) };
    try {
      const listResult = await this.backend("run_wireshark_adb_action", this.backendSettings(card, { ...card.wiresharkPlugin.adb, action: "list-files" }));
      if (Array.isArray(listResult.files)) card.wiresharkPlugin.files = listResult.files;
      const files = Array.isArray(listResult.files) ? listResult.files : [];
      const current = String(card.wiresharkPlugin.adb.capture_file || "");
      const basename = (value) => String(value || "").split(/[\\/]/).pop();
      const selected = files.find((file) => String(file.path || file.name || "") === current || basename(file.path || file.name) === basename(current)) || files[0];
      if (!selected) {
        card.wiresharkPlugin.progressText = tr("no_log_file");
        return;
      }
      card.wiresharkPlugin.adb.capture_file = String(selected.path || selected.name || "");
      const loadResult = await this.backend("run_wireshark_adb_action", this.backendSettings(card, { ...card.wiresharkPlugin.adb, action: "load-file" }));
      if (Array.isArray(loadResult.files)) card.wiresharkPlugin.files = loadResult.files;
      if (loadResult.frames_file) card.wiresharkPlugin.adb.frames_file = String(loadResult.frames_file);
      if (typeof loadResult.text === "string") await this.analyzeText(card, input, loadResult.text, tr("file_auto_loaded"));
    } catch (err) {
      card.wiresharkPlugin.progressText = `${tr("auto_load_failed")}: ${err && err.message ? err.message : err}`;
    } finally {
      card.wiresharkPlugin.autoLoading = false;
      card.wiresharkPlugin.autoLoadDone = true;
      card.render();
    }
  },

  readFields(card) {
    card.wiresharkPlugin = card.wiresharkPlugin || {};
    card.wiresharkPlugin.adb = card.wiresharkPlugin.adb || {};
    card.querySelectorAll("[data-wireshark-adb-field]").forEach((field) => {
      const key = field.getAttribute("data-wireshark-adb-field");
      if (!key) return;
      card.wiresharkPlugin.adb[key] = field.type === "checkbox" ? Boolean(field.checked) : String(field.value || "");
    });
    return card.wiresharkPlugin.adb;
  },

  async runAdbAction(card, action, input, tr, mergeLogFile) {
    const activeInput = input || card.querySelector("[data-wireshark-input]");
    card.wiresharkPlugin = card.wiresharkPlugin || {};
    const settings = (card.uiSettings && card.uiSettings.wireshark) || {};
    card.wiresharkPlugin.adb = { ...settings, ...(card.wiresharkPlugin.adb || {}) };
    const adb = this.readFields(card);
    if (card.wiresharkPlugin.adb && card.wiresharkPlugin.adb.frames_file) {
      adb.frames_file = card.wiresharkPlugin.adb.frames_file;
    }
    if (action === "capture-snapshot") card.wiresharkPlugin.captureSnapshotRunning = true;
    card.wiresharkPlugin.adbOutput = `${tr("adb_action_running")}: ${action}...`;
    card.wiresharkPlugin.loading = action === "compare-app-log";
    card.wiresharkPlugin.error = "";
    card.render();

    try {
      const result = await this.backend("run_wireshark_adb_action", this.backendSettings(card, { ...adb, action }));
      const output = String(result.output || "");
      card.wiresharkPlugin.adbOutput = [`Returncode: ${result.returncode}`, output].join("\n");

      if (action === "list-files" && Array.isArray(result.files)) {
        card.wiresharkPlugin.files = result.files;
        card.wiresharkPlugin.progressText = output || tr("files_refreshed");
      }
      if (action === "pull-hci" && Array.isArray(result.files)) {
        const nextFiles = result.files.filter(Boolean).map((path) => ({ name: String(path).split(/[\\/]/).pop(), path: String(path) }));
        card.wiresharkPlugin.files = nextFiles;
        card.wiresharkPlugin.adb.capture_file = String((result.files || [])[0] || card.wiresharkPlugin.adb.capture_file || "");
        card.wiresharkPlugin.progressText = tr("hci_fetched");
      }
      if (action === "btsnoop-jsonl") {
        if (Array.isArray(result.files)) card.wiresharkPlugin.files = result.files;
        if (result.log_file) {
          card.wiresharkPlugin.files = mergeLogFile(card.wiresharkPlugin.files, result.log_file);
          card.wiresharkPlugin.adb.capture_file = String(result.log_file);
        }
        if (result.frames_file) card.wiresharkPlugin.adb.frames_file = String(result.frames_file);
        card.wiresharkPlugin.progressText = tr("extract_frames");
        if (typeof result.text === "string") {
          await this.analyzeText(card, activeInput, result.text, tr("extract_frames"));
        }
      }
      if (action === "devices") {
        card.wiresharkPlugin.devicesText = output;
        card.wiresharkPlugin.adbConnected = /\bdevice\b/.test(output) && !/\bunauthorized\b|\boffline\b/.test(output);
      }
      if (action === "connect") {
        card.wiresharkPlugin.adbConnected = result.returncode === 0 && !/\bunauthorized\b|\boffline\b|failed/i.test(output);
      }
      if (action === "load-file" && typeof result.text === "string") {
        if (Array.isArray(result.files)) card.wiresharkPlugin.files = result.files;
        if (result.frames_file) card.wiresharkPlugin.adb.frames_file = String(result.frames_file);
        await this.analyzeText(card, activeInput, result.text, tr("file_loaded"));
      }
      if (action === "capture-start") {
        card.wiresharkPlugin.captureRunning = result.returncode === 0;
        card.wiresharkPlugin.captureFinished = false;
        card.wiresharkPlugin.captureStartedAt = Date.now();
        card.wiresharkPlugin.captureSnapshotCount = 0;
        card.wiresharkPlugin.captureSnapshotLastAt = 0;
        card.wiresharkPlugin.captureSnapshotNextAt = Date.now() + 15 * 60 * 1000;
        card.wiresharkPlugin.captureSnapshotRunning = false;
        card.wiresharkPlugin.captureStartLabel = new Date().toLocaleString(this.tr(card, "time") === "Time" ? "en-US" : "de-DE");
        card.wiresharkPlugin.progressText = tr("capture_running");
        window.clearInterval(card.wiresharkCaptureTimer);
        if (card.wiresharkPlugin.captureRunning) {
          card.wiresharkCaptureTimer = window.setInterval(() => {
            if (!card.wiresharkPlugin || !card.wiresharkPlugin.captureRunning) {
              window.clearInterval(card.wiresharkCaptureTimer);
              return;
            }
            if (
              Date.now() >= Number(card.wiresharkPlugin.captureSnapshotNextAt || 0)
              && !card.wiresharkPlugin.captureSnapshotRunning
            ) {
              card.wiresharkPlugin.captureSnapshotNextAt = Date.now() + 15 * 60 * 1000;
              void this.runAdbAction(card, "capture-snapshot", activeInput, tr, mergeLogFile);
            }
            card.render();
          }, 1000);
        }
      }
      if (action === "capture-snapshot") {
        card.wiresharkPlugin.captureSnapshotRunning = false;
        if (result.returncode === 0 && result.snapshot_file) {
          card.wiresharkPlugin.captureSnapshotCount = Number(card.wiresharkPlugin.captureSnapshotCount || 0) + 1;
          card.wiresharkPlugin.captureSnapshotLastAt = Date.now();
          card.wiresharkPlugin.files = mergeLogFile(card.wiresharkPlugin.files, result.snapshot_file);
          card.wiresharkPlugin.progressText = tr("capture_snapshot_ok");
        } else {
          card.wiresharkPlugin.progressText = tr("capture_snapshot_failed");
        }
        card.wiresharkPlugin.captureSnapshotNextAt = Date.now() + 15 * 60 * 1000;
      }
      if (action === "capture-end") {
        card.wiresharkPlugin.captureRunning = false;
        card.wiresharkPlugin.captureFinished = result.returncode === 0;
        card.wiresharkPlugin.progressText = tr("capture_finished");
        window.clearInterval(card.wiresharkCaptureTimer);
        if (Array.isArray(result.files) && result.files.length) {
          card.wiresharkPlugin.files = result.files;
        }
        if (result.log_file) {
          card.wiresharkPlugin.files = mergeLogFile(card.wiresharkPlugin.files, result.log_file);
          card.wiresharkPlugin.adb.capture_file = String(result.log_file);
        }
        if (result.frames_file) card.wiresharkPlugin.adb.frames_file = String(result.frames_file);
        if (typeof result.text === "string") {
          await this.analyzeText(card, activeInput, result.text, tr("capture_loaded"));
        }
      }
      if (action === "compare-app-log") {
        if (result.frames_file) card.wiresharkPlugin.adb.frames_file = String(result.frames_file);
        if (typeof result.text === "string") {
          await this.analyzeText(card, activeInput, result.text, tr("app_log_loaded"));
        } else {
          card.wiresharkPlugin.progressText = tr("app_log_loaded");
          card.wiresharkPlugin.loading = false;
        }
      }
      if (action === "root-check") {
        card.wiresharkPlugin.adbConnected = result.returncode === 0 && !/\bunauthorized\b|\boffline\b/i.test(output);
        card.wiresharkPlugin.rootChecked = true;
        card.wiresharkPlugin.rootOk = /uid=0\(root\)/.test(output);
        if (card.wiresharkPlugin.rootOk) card.wiresharkPlugin.adb.root_direct = true;
      }
    } catch (err) {
      if (action === "capture-snapshot") {
        card.wiresharkPlugin.captureSnapshotRunning = false;
        card.wiresharkPlugin.captureSnapshotNextAt = Date.now() + 15 * 60 * 1000;
      }
      card.wiresharkPlugin.adbOutput = `FAIL\n${err && err.message ? err.message : err}`;
      card.wiresharkPlugin.loading = false;
      card.wiresharkPlugin.error = err && err.message ? err.message : String(err);
    }
    card.render();
  },

  bindEvents(card) {
    const tr = (key) => this.tr(card, key);
    const input = card.querySelector("[data-wireshark-input]");
    const packetList = card.querySelector(".packet-list");
    const mergeLogFile = this.mergeLogFile.bind(this);
    const file = card.querySelector("[data-wireshark-file]");

    if (!card.wiresharkCompareDelegateBound) {
      card.wiresharkCompareDelegateBound = true;
      card.addEventListener("click", async (event) => {
        const path = typeof event.composedPath === "function" ? event.composedPath() : [];
        const button = path.find((node) => (
          node &&
          typeof node.getAttribute === "function" &&
          node.hasAttribute("data-wireshark-compare-open")
        )) || (event.target && event.target.closest
          ? event.target.closest("[data-wireshark-compare-open]")
          : null);
        if (!button || !card.contains(button)) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (typeof card.runWiresharkCompareFromCore === "function") {
          await card.runWiresharkCompareFromCore();
          return;
        }
        await this.runAdbAction(card, "compare-app-log", card.querySelector("[data-wireshark-input]"), tr, mergeLogFile);
      }, true);
    }

    if (packetList) {
      const scroll = (card.wiresharkPlugin && card.wiresharkPlugin.tableScroll) || {};
      packetList.scrollLeft = Number(scroll.left || 0);
      packetList.scrollTop = Number(scroll.top || 0);
      packetList.addEventListener("scroll", () => {
        card.wiresharkPlugin = card.wiresharkPlugin || {};
        card.wiresharkPlugin.tableScroll = {
          left: packetList.scrollLeft,
          top: packetList.scrollTop,
        };
      });
    }

    window.setTimeout(() => this.autoLoad(card, input), 0);

    if (file && input) {
      file.addEventListener("change", async () => {
        const selected = file.files && file.files[0];
        if (!selected) return;
        const text = await selected.text();
        input.value = text;
        card.wiresharkPlugin = { ...(card.wiresharkPlugin || {}), text, selectedIndex: 0, compareFrameIndexes: [] };
        card.render();
      });
    }

    card.querySelectorAll("[data-wireshark-compare-frame]").forEach((el) => {
      el.addEventListener("click", (event) => event.stopPropagation());
      el.addEventListener("change", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const frameIndex = Number(el.getAttribute("data-wireshark-compare-frame"));
        if (!Number.isInteger(frameIndex)) return;
        const current = new Set(((card.wiresharkPlugin && card.wiresharkPlugin.compareFrameIndexes) || []).map((value) => Number(value)).filter(Number.isInteger));
        if (el.checked) current.add(frameIndex);
        else current.delete(frameIndex);
        card.wiresharkPlugin = {
          ...(card.wiresharkPlugin || {}),
          compareFrameIndexes: Array.from(current).sort((left, right) => left - right),
        };
        const row = el.closest("[data-wireshark-select]");
        if (row) row.classList.toggle("compare-selected", el.checked);
      });
    });

    card.querySelectorAll("[data-wireshark-compare-clear]").forEach((el) => {
      el.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        card.wiresharkPlugin = { ...(card.wiresharkPlugin || {}), compareFrameIndexes: [] };
        card.render();
      });
    });

    card.querySelectorAll("[data-wireshark-select]").forEach((el) => {
      el.addEventListener("click", () => {
        const selectedIndex = Number(el.getAttribute("data-wireshark-select") || 0);
        card.wiresharkPlugin = {
          ...(card.wiresharkPlugin || {}),
          selectedIndex,
        };
        card.querySelectorAll("[data-wireshark-select]").forEach((row) => row.classList.toggle("active", row === el));
        const frames = card.wiresharkPlugin.result && Array.isArray(card.wiresharkPlugin.result.frames)
          ? card.wiresharkPlugin.result.frames
          : [];
        const selected = frames[selectedIndex] || null;
        const detail = card.querySelector("[data-wireshark-input]");
        if (detail) detail.value = selected ? JSON.stringify(this.detailPayload(selected), null, 2) : tr("no_frame_selected");
      });
    });

    card.querySelectorAll("[data-wireshark-resize]").forEach((handle) => {
      handle.addEventListener("click", (event) => event.stopPropagation());
      handle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const key = handle.getAttribute("data-wireshark-resize");
        if (!key) return;
        const table = handle.closest(".packet-list");
        const startX = event.clientX;
        const defaults = { row: 44, time: 150, source: 190, destination: 190, protocol: 120, command: 64, mode: 64, params: 220, encoded: 360 };
        const current = (card.wiresharkPlugin && card.wiresharkPlugin.columnWidths) || {};
        const startWidth = Math.max(42, Number(current[key] || defaults[key] || 120));
        const applyWidths = (widths) => {
          if (!table) return;
          const merged = { ...defaults, ...widths };
          Object.entries(merged).forEach(([column, width]) => {
            table.style.setProperty(`--ws-col-${column}`, `${Math.max(42, Number(width || defaults[column] || 120))}px`);
          });
          const tableWidth = Object.values(merged).reduce((sum, value) => sum + Math.max(42, Number(value || 0)), 0) + 8 * (Object.keys(defaults).length - 1) + 20;
          table.style.setProperty("--ws-table-width", `${tableWidth}px`);
        };
        const onMove = (moveEvent) => {
          const nextWidth = Math.max(42, startWidth + moveEvent.clientX - startX);
          card.wiresharkPlugin = card.wiresharkPlugin || {};
          card.wiresharkPlugin.columnWidths = { ...(card.wiresharkPlugin.columnWidths || {}), [key]: nextWidth };
          applyWidths(card.wiresharkPlugin.columnWidths);
        };
        const onUp = () => {
          window.removeEventListener("pointermove", onMove);
          window.removeEventListener("pointerup", onUp);
          card.render();
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
      });
    });

    card.querySelectorAll("[data-wireshark-sort]").forEach((el) => {
      el.addEventListener("click", () => {
        const key = el.getAttribute("data-wireshark-sort");
        card.wiresharkPlugin = card.wiresharkPlugin || {};
        const current = card.wiresharkPlugin.sort || {};
        const direction = current.key === key && current.direction !== "desc" ? "desc" : "asc";
        card.wiresharkPlugin.sort = { key, direction };
        card.render();
      });
    });

    card.querySelectorAll("[data-wireshark-adb-field]").forEach((el) => {
      const save = () => {
        const key = el.getAttribute("data-wireshark-adb-field");
        const adb = this.readFields(card);
        if (key === "hci_log_dir" || key === "capture_dir") {
          card.uiSettings = card.uiSettings || {};
          card.uiSettings.wireshark = card.uiSettings.wireshark || {};
          card.uiSettings.wireshark[key] = String(el.value || "");
          card.saveUiSettings();
        }
        if (key === "root_direct" || adb.root_direct) card.render();
      };
      el.addEventListener("change", save);
    });

    card.querySelectorAll("[data-wireshark-device-select]").forEach((el) => {
      el.addEventListener("change", () => {
        const value = String(el.value || "");
        if (!value) return;
        card.wiresharkPlugin = card.wiresharkPlugin || {};
        card.wiresharkPlugin.adb = card.wiresharkPlugin.adb || {};
        if (/^\d{1,3}(?:\.\d{1,3}){3}:\d+$/.test(value)) {
          const parts = value.split(":");
          card.wiresharkPlugin.adb.adb_port = parts.pop();
          card.wiresharkPlugin.adb.adb_ip = parts.join(":");
        } else {
          card.wiresharkPlugin.adb.local_mac = value.toUpperCase();
        }
        card.render();
      });
    });

    card.querySelectorAll("[data-wireshark-refresh-devices]").forEach((el) => {
      el.addEventListener("click", () => {
        card.wiresharkPlugin = {
          ...(card.wiresharkPlugin || {}),
          progressText: tr("devices_reloaded"),
        };
        card.render();
      });
    });

    card.querySelectorAll("[data-wireshark-adb-action]").forEach((el) => {
      el.addEventListener("click", async () => {
        const action = el.getAttribute("data-wireshark-adb-action");
        if (action === "compare-app-log") return;
        await this.runAdbAction(card, action, input, tr, mergeLogFile);
      });
    });

    card.querySelectorAll("[data-wireshark-analyze]").forEach((button) => {
      button.addEventListener("click", async () => {
        const text = String(((card.wiresharkPlugin || {}).text) || (input && input.value) || "");
        card.wiresharkPlugin = { ...(card.wiresharkPlugin || {}), text, loading: true, selectedIndex: 0 };
        card.render();
        try {
          const result = await this.backend("analyze_wireshark_text", text);
          card.wiresharkPlugin = { ...(card.wiresharkPlugin || {}), text, result, loading: false, selectedIndex: 0 };
        } catch (err) {
          card.wiresharkPlugin = { ...(card.wiresharkPlugin || {}), text, loading: false, error: err && err.message ? err.message : String(err) };
        }
        card.render();
      });
    });
  },
};

window.ChihirosPlugins.wireshark.bindGlobalCompareHandler();
