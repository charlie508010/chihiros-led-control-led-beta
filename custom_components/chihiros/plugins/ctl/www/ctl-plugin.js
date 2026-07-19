window.ChihirosPlugins = window.ChihirosPlugins || {};

window.ChihirosPlugins.ctl = {
  id: "ctl",
  title: "CTL",
  tabs: ["ctl"],
  version: "0.1.0",
  translations: {
    de: {
      ctl_commands: "CTL Befehle",
      ctl_area: "Bereich",
      ctl_no_commands: "Keine CTL-Befehle für diesen Bereich vorhanden.",
      ctl_preview: "Befehl",
      ctl_running: "CTL-Befehl wird ausgeführt...",
      ctl_failed: "CTL fehlgeschlagen",
      command_copied: "Befehl kopiert",
      copy_command: "Befehl kopieren",
      run_command: "Befehl ausführen",
      database: "Datenbank",
      database_subtitle: "Quelle für Add-on-Dashboard, CTL-Konfiguration und Tageswerte",
      own_database: "Eigene DB",
      active_sqlite: "Aktive SQLite",
      reload: "Neu laden",
      ctl_config_title: "CTL Einstellungen",
      ctl_config_subtitle: "Aliase, Anzeigenamen, Kanalnamen, Sicherheit und Rührer-Verknüpfung",
      ctl_config_mask_title: "CTL Config Eingabemasken",
      ctl_config_no_input: "Keine Eingabe nötig.",
      ctl_config_save: "Speichern",
      ctl_config_readonly: "Anzeige- und Löschaktionen",
      ctl_panel_title: "CTL",
      ctl_panel_subtitle: "Kommandos kopieren und lokal testen",
      ctl_device_placeholder: "doser_1 oder MAC",
      config: "Config",
      language_label: "Sprache",
      language_de: "Deutsch",
      language_en: "English",
      language: "Sprache",
      kind: "Typ",
      index: "Index",
      address: "Adresse/Alias",
      alias: "Alias",
      name: "Name",
      model: "Modell",
      channel: "Kanal ID",
      channel_name: "Kanalname",
      max_single_ml: "Max Einzel mL",
      max_daily_ml: "Max Tag mL",
      stirrer_alias: "Rührer-Alias",
      device: "Gerät",
      device_name: "Gerätename",
      device_model: "Gerätemodell",
      channel_name_save: "Kanalname speichern",
      save_all: "SPEICHERN",
      database_migrate: "Datenbank migrieren",
      basis: "Basis",
      general_device: "Gerät allgemein",
      doser: "Doser",
      led: "LED",
      ruehrer: "Rührer",
      heizer: "Heizer",
      names_channels: "Namen und Kanäle",
      safety_links: "Sicherheit und Links",
      stirrer_runtime: "Rührer-Laufzeit",
      data_base: "Datenbank",
      no_entities: "Keine passenden Home-Assistant-Entities gefunden.",
      reload: "Neu laden",
      select: "Auswählen",
    },
    en: {
      ctl_commands: "CTL commands",
      ctl_area: "Area",
      ctl_no_commands: "No CTL commands available for this area.",
      ctl_preview: "Command",
      ctl_running: "Running CTL command...",
      ctl_failed: "CTL failed",
      command_copied: "Command copied",
      copy_command: "Copy command",
      run_command: "Run command",
      database: "Database",
      database_subtitle: "Source for add-on dashboard, CTL config and daily values",
      own_database: "Own DB",
      active_sqlite: "Active SQLite",
      reload: "Reload",
      ctl_config_title: "CTL settings",
      ctl_config_subtitle: "Aliases, display names, channel names, safety and stirrer links",
      ctl_config_mask_title: "CTL config input masks",
      ctl_config_no_input: "No input required.",
      ctl_config_save: "Save",
      ctl_config_readonly: "View and delete actions",
      ctl_panel_title: "CTL",
      ctl_panel_subtitle: "Copy commands and test locally",
      ctl_device_placeholder: "doser_1 or MAC",
      config: "Config",
      language_label: "Language",
      language_de: "German",
      language_en: "English",
      language: "Language",
      kind: "Type",
      index: "Index",
      address: "Address/Alias",
      alias: "Alias",
      name: "Name",
      model: "Model",
      channel: "Channel ID",
      channel_name: "Channel name",
      max_single_ml: "Max single mL",
      max_daily_ml: "Max daily mL",
      stirrer_alias: "Stirrer alias",
      device: "Device",
      device_name: "Device name",
      device_model: "Device model",
      channel_name_save: "Save channel name",
      save_all: "SAVE",
      database_migrate: "Migrate database",
      basis: "Base",
      general_device: "General device",
      doser: "Doser",
      led: "LED",
      ruehrer: "Stirrer",
      heizer: "Heater",
      names_channels: "Names and channels",
      safety_links: "Safety and links",
      stirrer_runtime: "Stirrer runtime",
      data_base: "Database",
      no_entities: "No matching Home Assistant entities found.",
      reload: "Reload",
      select: "Select",
    },
  },

  tr(card, key) {
    const language = typeof card.language === "function"
      ? card.language()
      : String((card.uiSettings && card.uiSettings.language) || "de");
    const table = language === "en" ? this.translations.en : this.translations.de;
    return (table && table[key]) || this.translations.de[key] || key;
  },

  localizeLegacyText(card, value) {
    const text = String(value || "");
    const language = typeof card.language === "function" ? card.language() : "de";
    if (language !== "en") return text;
    const replacements = [
      ["Alle Geräte", "All devices"], ["Geräte", "Devices"], ["Gerät", "Device"],
      ["Gerätename", "Device name"], ["Namen und Kanäle", "Names and channels"],
      ["Rührer-Laufzeit", "Stirrer runtime"], ["Rührer", "Stirrer"], ["Behälter", "Container"],
      ["Zeitplan", "Schedule"], ["Zeitfenster", "Time window"], ["Helligkeit", "Brightness"],
      ["Sprache", "Language"], ["Schlüssel", "Key"], ["Wert", "Value"], ["Modell", "Model"],
      ["Kanalname", "Channel name"], ["Wochentage", "Weekdays"], ["Sekunden", "Seconds"],
      ["Minuten", "Minutes"], ["Von", "From"], ["Bis", "To"], ["Kein", "None"],
      ["Alle", "All"], ["suchen", "search"], ["speichern", "save"], ["anzeigen", "show"],
      ["löschen", "delete"], ["setzen", "set"], ["entfernen", "remove"],
      ["zurücksetzen", "reset"], ["aktivieren", "enable"], ["deaktivieren", "disable"],
      ["einschalten", "turn on"], ["ausschalten", "turn off"], ["Laufen lassen", "Run"],
      ["allgemein", "general"], ["nach Typ", "by type"], ["mit Name und", "with name and"],
    ];
    return replacements.reduce((result, [from, to]) => result.replaceAll(from, to), text);
  },

  styles() {
    return `
      <style>
        .ctl-plugin-page { display:grid; grid-template-columns:1fr; gap:12px; }
        .ctl-plugin-card { min-width:0; min-height:0; padding-top:10px; border-color:rgba(3,201,255,.30); background:linear-gradient(145deg, rgba(3,201,255,.055), rgba(57,211,83,.035) 42%, rgba(0,0,0,.16)); box-shadow:inset 3px 0 0 rgba(3,201,255,.30); }
        .ctl-plugin-card .config-card-head { margin-bottom:10px; }
        .ctl-plugin-card .config-card-head small { display:block; color:rgba(255,255,255,.58); line-height:1.35; }
        .ctl-device-row { display:grid; grid-template-columns:minmax(0, 1fr) 64px; gap:8px; margin:8px 0 12px; }
        .ctl-device-row input { min-height:34px; border:1px solid rgba(81,154,190,.35); border-radius:6px; background:rgba(255,255,255,.08); color:var(--primary-text-color); padding:0 10px; font:inherit; }
        .ctl-device-row button { min-height:34px; border:1px solid rgba(3,201,255,.65); border-radius:6px; background:rgba(0,122,166,.18); color:var(--primary-text-color); font:inherit; font-weight:700; cursor:pointer; }
        .ctl-area-row { display:grid; grid-template-columns:110px minmax(0, 1fr); gap:8px; align-items:center; margin:8px 0; }
        .ctl-area-row span { color:rgba(255,255,255,.78); font-size:12px; font-weight:800; text-transform:uppercase; }
        .ctl-area-row select { min-height:36px; border:1px solid rgba(81,154,190,.35); border-radius:7px; background:rgba(255,255,255,.08); color:var(--primary-text-color); padding:0 10px; font:inherit; }
        .ctl-group { margin-top:12px; padding-top:10px; border-top:1px solid rgba(255,255,255,.08); }
        .ctl-group:first-of-type { margin-top:0; padding-top:0; border-top:0; }
        .ctl-group h3 { margin:0 0 7px; font-size:13px; color:rgba(255,255,255,.78); letter-spacing:0; }
        .ctl-command-list { display:grid; grid-template-columns:1fr; gap:4px; }
        .ctl-command { display:grid; grid-template-columns:minmax(0, 1fr) 24px; align-items:center; gap:3px 8px; min-height:30px; width:100%; border:1px solid rgba(81,154,190,.18); border-radius:6px; background:rgba(0,0,0,.16); color:inherit; cursor:pointer; text-align:left; padding:4px 8px; }
        .ctl-command:hover { border-color:rgba(3,201,255,.55); background:rgba(0,122,166,.14); }
        .ctl-command span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:700; color:rgba(255,255,255,.88); }
        .ctl-command code { grid-column:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font:12px/1.3 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color:rgba(255,255,255,.86); }
        .ctl-command ha-icon { grid-column:2; grid-row:1 / span 2; --mdc-icon-size:18px; justify-self:end; color:#03c9ff; }
        .ctl-command-form { display:grid; gap:8px; border:1px solid rgba(81,154,190,.20); border-radius:8px; background:rgba(0,0,0,.14); padding:10px; }
        .ctl-command-form-head { display:grid; grid-template-columns:minmax(0, 1fr) auto; align-items:center; gap:8px; }
        .ctl-command-form-head strong { color:rgba(255,255,255,.88); font-size:13px; }
        .ctl-command-form-fields { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:8px; }
        .ctl-command-form-fields label { display:grid; gap:4px; color:rgba(255,255,255,.70); font-size:12px; font-weight:700; }
        .ctl-command-form-fields input, .ctl-command-form-fields select { min-height:34px; min-width:0; border:1px solid rgba(81,154,190,.30); border-radius:6px; background:rgba(255,255,255,.07); color:var(--primary-text-color); padding:0 9px; font:inherit; }
        .ctl-weekday-chips { display:flex; flex-wrap:wrap; gap:5px; }
        .ctl-weekday-chips button { min-height:30px; border:1px solid rgba(81,154,190,.32); border-radius:7px; background:rgba(0,0,0,.14); color:var(--primary-text-color); font-weight:800; cursor:pointer; padding:0 9px; }
        .ctl-weekday-chips button.active { border-color:#03c9ff; background:rgba(0,122,166,.24); color:#88ddff; }
        .ctl-command-preview { display:grid; grid-template-columns:72px minmax(0, 1fr); gap:8px; align-items:center; border:1px solid rgba(255,255,255,.08); border-radius:6px; background:rgba(0,0,0,.16); padding:7px 8px; }
        .ctl-command-preview span { color:rgba(255,255,255,.58); font-size:12px; font-weight:800; text-transform:uppercase; }
        .ctl-command-preview code { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font:12px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color:rgba(255,255,255,.86); }
        .ctl-command-form .ctl-command-run { min-height:32px; border:1px solid rgba(3,201,255,.55); border-radius:6px; background:rgba(0,122,166,.16); color:var(--primary-text-color); font:inherit; font-weight:800; cursor:pointer; padding:0 12px; }
        .ctl-config-card { grid-column:1 / -1; }
        .ctl-config-fields { display:grid; grid-template-columns:repeat(4, minmax(160px, 1fr)); gap:10px; margin:12px 0 14px; }
        .ctl-config-fields label { display:grid; gap:5px; min-width:0; font-weight:700; color:rgba(255,255,255,.78); }
        .ctl-config-fields span { font-size:12px; }
        .ctl-config-fields input, .ctl-config-fields select { min-height:36px; min-width:0; border:1px solid rgba(81,154,190,.35); border-radius:6px; background:rgba(255,255,255,.08); color:var(--primary-text-color); padding:0 10px; font:inherit; }
        .ctl-config-save-row { display:flex; justify-content:flex-end; margin:-2px 0 12px; }
        .ctl-config-save-row .primary { display:inline-flex; align-items:center; justify-content:center; gap:8px; min-width:170px; }
        .ctl-config-save-row ha-icon { --mdc-icon-size:18px; }
        .ctl-form-wrap { display:grid; grid-template-columns:1fr; gap:14px; padding-top:12px; border-top:1px solid rgba(255,255,255,.08); }
        .ctl-form-section { display:grid; gap:8px; }
        .ctl-form-section h3 { margin:0; color:rgba(255,255,255,.80); font-size:13px; }
        .ctl-config-form-grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px; }
        .ctl-config-form { min-width:0; border:1px solid rgba(81,154,190,.22); border-radius:8px; background:rgba(0,0,0,.14); padding:10px; display:grid; gap:10px; }
        .ctl-config-form-head { display:grid; grid-template-columns:minmax(0, 1fr) auto; align-items:center; gap:10px; }
        .ctl-config-form-head strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:rgba(255,255,255,.88); font-size:13px; }
        .ctl-config-form-head button { min-height:32px; display:inline-flex; align-items:center; justify-content:center; gap:7px; border:1px solid rgba(3,201,255,.55); border-radius:6px; background:rgba(0,122,166,.16); color:var(--primary-text-color); cursor:pointer; padding:0 10px; }
        .ctl-config-form-head button:hover { border-color:#03c9ff; background:rgba(0,122,166,.28); }
        .ctl-config-form-head button ha-icon { --mdc-icon-size:17px; color:#03c9ff; }
        .ctl-config-form-head button b { font:700 12px/1 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
        .ctl-form-fields { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:8px; }
        .ctl-form-fields label { display:grid; gap:4px; min-width:0; color:rgba(255,255,255,.70); font-size:12px; font-weight:700; }
        .ctl-form-fields input, .ctl-form-fields select { min-height:34px; min-width:0; border:1px solid rgba(81,154,190,.30); border-radius:6px; background:rgba(255,255,255,.07); color:var(--primary-text-color); padding:0 9px; font:inherit; }
        .ctl-form-empty { color:rgba(255,255,255,.58); font-size:12px; }
        .ctl-readonly-details { margin-top:14px; border-top:1px solid rgba(255,255,255,.08); padding-top:10px; }
        .ctl-readonly-details summary { cursor:pointer; color:rgba(255,255,255,.78); font-weight:700; }
        .ctl-readonly-grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px; margin-top:10px; }
        .ctl-read-section h3 { margin:0 0 7px; color:rgba(255,255,255,.70); font-size:12px; }
        .ctl-read-section > div { display:grid; gap:6px; }
        .ctl-read-action { min-height:32px; display:grid; grid-template-columns:20px minmax(0, 1fr); align-items:center; gap:8px; border:1px solid rgba(81,154,190,.22); border-radius:6px; background:rgba(0,0,0,.12); color:inherit; cursor:pointer; text-align:left; padding:0 8px; }
        .ctl-read-action ha-icon { --mdc-icon-size:16px; color:#03c9ff; }
        .ctl-read-action span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; font-weight:700; }
        .ctl-action-wrap { display:grid; grid-template-columns:1fr; gap:12px; padding-top:12px; border-top:1px solid rgba(255,255,255,.08); }
        .ctl-action-section { min-width:0; }
        .ctl-action-section h3 { margin:0 0 8px; color:rgba(255,255,255,.78); font-size:13px; }
        .ctl-command-form-list { display:grid; grid-template-columns:1fr; gap:6px; }
        .ctl-command-row { display:grid; grid-template-columns:190px minmax(0, 1fr) 150px; gap:8px; align-items:center; min-height:38px; border:1px solid rgba(81,154,190,.18); border-radius:7px; background:rgba(0,0,0,.14); padding:6px; }
        .ctl-command-row > span { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:rgba(255,255,255,.78); font-weight:700; font-size:12px; }
        .ctl-command-row input { min-height:32px; min-width:0; border:1px solid rgba(81,154,190,.30); border-radius:6px; background:rgba(255,255,255,.07); color:var(--primary-text-color); padding:0 9px; font:12px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
        .ctl-command-row button { min-height:32px; display:inline-flex; align-items:center; justify-content:center; gap:7px; border:1px solid rgba(3,201,255,.55); border-radius:6px; background:rgba(0,122,166,.16); color:var(--primary-text-color); cursor:pointer; }
        .ctl-command-row button:hover { border-color:#03c9ff; background:rgba(0,122,166,.28); }
        .ctl-command-row button ha-icon { --mdc-icon-size:17px; color:#03c9ff; }
        .ctl-command-row button b { font:700 12px/1 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
        .ctl-path-strip { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; padding-top:10px; border-top:1px solid rgba(255,255,255,.08); }
        .ctl-path-strip span { min-width:0; max-width:100%; display:inline-flex; gap:8px; align-items:center; border:1px solid rgba(81,154,190,.20); border-radius:999px; background:rgba(0,0,0,.16); padding:4px 10px; color:rgba(255,255,255,.78); font:12px/1.3 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .ctl-path-strip b { color:rgba(255,255,255,.58); font:700 12px/1.3 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
        .ctl-page { display:grid; grid-template-columns:repeat(2, minmax(280px, 1fr)); gap:12px; align-items:start; }
        .ctl-card { grid-column:1 / -1; max-height:calc(100vh - 150px); overflow:auto; }
        .ctl-update-row { display:flex; justify-content:flex-end; margin-top:10px; }
        .ctl-update-row button { min-height:34px; border:1px solid rgba(255,147,0,.58); border-radius:6px; background:rgba(255,147,0,.10); color:#ffc078; font:inherit; font-weight:700; cursor:pointer; padding:0 12px; }
        @media (max-width: 1100px) {
          .ctl-config-fields, .ctl-config-form-grid, .ctl-readonly-grid { grid-template-columns:repeat(2, minmax(0, 1fr)); }
          .ctl-command-row { grid-template-columns:150px minmax(0, 1fr) 140px; }
        }
        @media (max-width: 700px) {
          .ctl-page, .ctl-config-fields, .ctl-config-form-grid, .ctl-readonly-grid, .ctl-form-fields, .ctl-command-form-fields, .ctl-area-row { grid-template-columns:1fr; }
          .ctl-device-row, .ctl-command-row, .ctl-config-form-head, .ctl-inline-row, .plugin-loader-row { grid-template-columns:1fr; gap:5px; }
          .ctl-command-row button, .ctl-config-form-head button, .plugin-actions button, .plugin-loader-row button { width:100%; }
          .ctl-card { max-height:none; }
        }
      </style>`;
  },

  ctlLedMaxBrightness(card) {
    const ctl = (card && card.ctlConfig) || {};
    const ledDevice = (card && card.activeLedDevice) || {};
    const text = String([
      ctl.model,
      ctl.address,
      card && card.ctlDevice,
      ledDevice.model,
      ledDevice.name,
      ledDevice.address,
    ].filter(Boolean).join(" ")).toLowerCase();
    return 100;
  },

  commandGroups(card) {
    const ledMax = this.ctlLedMaxBrightness(card);
    const ledExample = `${ledMax} ${ledMax} ${ledMax} ${ledMax}`;
    return [
      {
        title: "Doser",
        prefix: "chihirosctl doser",
        commands: [
          "dose-ml {device} --pump 1 --ml 0.2 --debug",
          "show-schedules {device}",
          "clear-schedule {device} --ch-id 1",
          "add-setting-dosing-pump {device} 08:00 --ch-id 1 --ch-ml 0.2",
          "add-interval {device} --ch-id 1 --ch-ml 5.0 --interval 0",
          "enable-schedule {device} --ch-id 1",
          "disable-schedule {device} --ch-id 1",
          "show-auto-totals {device}",
          "read-auto-totals {device} --debug",
          "show-manual-totals {device}",
          "show-daily-totals {device}",
          "set-auto-total {device} --ch-id 1 --ml 0.0",
          "clear-auto-totals {device}",
          "show-containers {device}",
          "set-container {device} --ch-id 1 --ml 500.0",
          "add-container {device} --ch-id 1 --delta 100.0",
          "show-history {device}",
          "clear-history {device}",
        ],
      },
      {
        title: "LED",
        prefix: "chihirosctl led",
        commands: [
          "list-devices",
          "turn-on {device}",
          "turn-off {device}",
          `set-brightness {device} ${ledExample}`,
          `add-setting {device} 08:00 20:00 ${ledExample}`,
          "remove-setting {device} 08:00 20:00",
          "reset-settings {device}",
          "enable-auto-mode {device}",
          "read-notifications {device} --notification-wait 5",
        ],
      },
      {
        title: "Ruehrer",
        prefix: "chihirosctl magstirrer",
        commands: [
          "show {device}",
          "set-channel-name CH1 --ch-id 0 --device {device}",
          "show-channel-names",
          "set-power {device} --on",
          "run-for {device} --seconds 10",
          "enable-auto-mode {device} --ch-id 0 --on",
          "set-timers {device} --ch-id 0 --timer 08:00=360",
          "clear-timers {device} --ch-id 0",
          "set-runtime-speed {device} --ch-id 0 --runtime-minutes 90 --speed 70",
          "add-setting {device} 08:00 --ch-id 0 --value 360",
          "enable-schedule {device} 08:00 --ch-id 0 --value 360",
          "disable-schedule {device} --ch-id 0",
          "show-schedules {device}",
          "clear-schedules {device} --ch-id 0",
        ],
      },
      {
        title: "Config",
        prefix: "chihirosctl config",
        commands: [
          "path",
          "set-language de",
          "show-language",
          "delete-language",
          "list-devices",
          "list-devices --kind doser",
          "resolve {device}",
          "list",
          "set-device doser 1 {device}",
          "show-device doser doser_1",
          "delete-device doser doser_1",
          "set-doser 1 {device}",
          "show-doser 1",
          "delete-doser",
          "set-led 1 {device}",
          "show-led 1",
          "delete-led",
          "set-magstirrer 1 {device}",
          "show-magstirrer 1",
          "delete-magstirrer",
          "set-doser-safety --max-single-ml 50 --max-daily-ml 250",
          "show-doser-safety",
          "delete-doser-safety",
          "set-doser-magstirrer-link {device} {device} --doser-ch-id 0",
          "set-doser-magstirrer-link-active {device} --doser-ch-id 0 --enabled",
          "show-magstirrer-defaults",
          "set-magstirrer-defaults --lead-time 10 --speed 10",
          "set-magstirrer-runtime {device} --ch-id 0 --runtime-min 10 --speed 10",
          "delete-magstirrer-runtime {device} --ch-id 0",
          "show-magstirrer-runtime",
          "show-doser-magstirrer-links",
          "delete-doser-magstirrer-link {device} --doser-ch-id 0",
          "db-info",
          "db-migrate",
          "list-profiles",
          "set-device-name doser {device} Doser",
          "delete-device-name doser {device}",
          "set-device-model doser {device} DosingPump",
          "delete-device-model doser {device}",
          "set-channel-name doser {device} CH1 --ch-id 0",
          "delete-channel-name doser {device} --ch-id 0",
          "show-local-names",
        ],
      },
      {
        title: "Template",
        prefix: "chihirosctl template",
        commands: [
          "load-template-standart {device} --template-name standard",
          `set-template-standart --template-name standard ${ledExample}`,
          `create-standard-template --template-name standard ${ledExample}`,
          `set-template {device} --template-name day ${ledExample}`,
          `create-template {device} --template-name day ${ledExample}`,
          "load-template {device} --template-name day",
          "delete-template {device} --template-name day",
          "show {device}",
          "list-templates {device}",
          "list-standard-templates",
          "delete-standard-template --template-name standard",
          `set-on-preset {device} ${ledExample}`,
          "show-on-preset {device}",
          "clear-on-preset {device}",
        ],
      },
    ];
  },

  resolveCommand(text, device) {
    const ref = String(device || "doser_1").trim() || "doser_1";
    return String(text || "").replaceAll("{device}", ref);
  },

  shellQuote(value) {
    const text = String(value || "");
    if (/^[A-Za-z0-9_./:@+-]+$/.test(text)) return text || "''";
    return `'${text.replaceAll("'", "'\\''")}'`;
  },

  formText(values, key, fallback = "") {
    return String(values[key] || fallback).trim();
  },

  configFormGroups(card, ctl, kind, index, deviceRef, channel) {
    const stirrer = String(ctl.stirrerAddress || "ruehrer_1").trim() || "ruehrer_1";
    const numberValue = (value, fallback) => (Number.isFinite(Number(value)) ? Number(value) : fallback);
    return [
      {
        title: this.tr(card, "basis"),
        forms: [
          {
            title: "Sprache speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [{ name: "language", label: this.tr(card, "language"), type: "select", value: ctl.language || "de", options: [["de", "Deutsch"], ["en", "English"]] }],
            build: (values) => `chihirosctl config set-language ${this.formText(values, "language", "de")}`,
          },
          {
            title: "Freien Config-Wert speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [
              { name: "key", label: "Schluessel", value: "example.key" },
              { name: "value", label: "Wert", value: "example-value" },
            ],
            build: (values) => `chihirosctl config set ${this.formText(values, "key", "example.key")} ${this.shellQuote(this.formText(values, "value", "example-value"))}`,
          },
        ],
      },
      {
        title: this.tr(card, "general_device"),
        forms: [
          {
            title: "Gerät speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [
              { name: "kind", label: this.tr(card, "kind"), type: "select", value: kind, options: [["doser", "Doser"], ["led", "LED"], ["ruehrer", "Ruehrer"], ["heizer", "Heizer"]] },
              { name: "index", label: this.tr(card, "index"), type: "number", value: index, min: 1, max: 4, step: 1 },
              { name: "address", label: this.tr(card, "address"), value: deviceRef },
              { name: "alias", label: this.tr(card, "alias"), value: `${kind}_${index}` },
              { name: "label", label: this.tr(card, "name"), value: ctl.name || "Doser" },
              { name: "model", label: this.tr(card, "model"), value: ctl.model || "DosingPump" },
            ],
            build: (values) => {
              const base = `chihirosctl config set-device ${this.formText(values, "kind", kind)} ${numberValue(values.index, index)} ${this.formText(values, "address", deviceRef)}`;
              const alias = this.formText(values, "alias");
              const label = this.formText(values, "label");
              const model = this.formText(values, "model");
              return [
                base,
                alias ? `--alias ${alias}` : "",
                label ? `--label ${this.shellQuote(label)}` : "",
                model ? `--model ${this.shellQuote(model)}` : "",
              ].filter(Boolean).join(" ");
            },
          },
        ],
      },
      {
        title: this.tr(card, "doser"),
        forms: [
          {
            title: "Doser-Alias speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [
              { name: "index", label: "Doser Nummer", type: "number", value: index, min: 1, max: 4, step: 1 },
              { name: "address", label: this.tr(card, "address"), value: deviceRef },
            ],
            build: (values) => `chihirosctl config set-doser ${numberValue(values.index, index)} ${this.formText(values, "address", deviceRef)}`,
          },
        ],
      },
      {
        title: this.tr(card, "led"),
        forms: [
          {
            title: "LED-Alias speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [
              { name: "index", label: "LED Nummer", type: "number", value: index, min: 1, max: 4, step: 1 },
              { name: "address", label: this.tr(card, "address"), value: deviceRef },
            ],
            build: (values) => `chihirosctl config set-led ${numberValue(values.index, index)} ${this.formText(values, "address", deviceRef)}`,
          },
        ],
      },
      {
        title: this.tr(card, "ruehrer"),
        forms: [
          {
            title: "Ruehrer-Alias speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [
              { name: "index", label: "Ruehrer Nummer", type: "number", value: index, min: 1, max: 4, step: 1 },
              { name: "address", label: this.tr(card, "address"), value: stirrer },
            ],
            build: (values) => `chihirosctl config set-magstirrer ${numberValue(values.index, index)} ${this.formText(values, "address", stirrer)}`,
          },
        ],
      },
      {
        title: this.tr(card, "names_channels"),
        forms: [
          {
            title: "Gerätename speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [
              { name: "kind", label: this.tr(card, "kind"), type: "select", value: kind, options: [["doser", "Doser"], ["led", "LED"], ["ruehrer", "Ruehrer"], ["heizer", "Heizer"]] },
              { name: "device", label: this.tr(card, "device"), value: deviceRef },
              { name: "name", label: this.tr(card, "device_name"), value: ctl.name || "Doser" },
            ],
            build: (values) => `chihirosctl config set-device-name ${this.formText(values, "kind", kind)} ${this.formText(values, "device", deviceRef)} ${this.shellQuote(this.formText(values, "name", "Doser"))}`,
          },
          {
            title: "Modell speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [
              { name: "kind", label: this.tr(card, "kind"), type: "select", value: kind, options: [["doser", "Doser"], ["led", "LED"], ["ruehrer", "Ruehrer"], ["heizer", "Heizer"]] },
              { name: "device", label: this.tr(card, "device"), value: deviceRef },
              { name: "model", label: this.tr(card, "device_model"), value: ctl.model || "DosingPump" },
            ],
            build: (values) => `chihirosctl config set-device-model ${this.formText(values, "kind", kind)} ${this.formText(values, "device", deviceRef)} ${this.shellQuote(this.formText(values, "model", "DosingPump"))}`,
          },
          {
            title: "Kanalname speichern",
            button: this.tr(card, "channel_name_save"),
            fields: [
              { name: "kind", label: this.tr(card, "kind"), type: "select", value: kind, options: [["doser", "Doser"], ["led", "LED"], ["ruehrer", "Ruehrer"], ["heizer", "Heizer"]] },
              { name: "device", label: this.tr(card, "device"), value: deviceRef },
              { name: "channel", label: this.tr(card, "channel"), type: "number", value: channel, min: 0, max: 3, step: 1 },
              { name: "channelName", label: this.tr(card, "channel_name"), value: ctl.channelName || `CH${channel + 1}` },
            ],
            build: (values) => `chihirosctl config set-channel-name ${this.formText(values, "kind", kind)} ${this.formText(values, "device", deviceRef)} ${this.shellQuote(this.formText(values, "channelName", `CH${channel + 1}`))} --ch-id ${numberValue(values.channel, channel)}`,
          },
        ],
      },
      {
        title: this.tr(card, "safety_links"),
        forms: [
          {
            title: "Doser-Schutz speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [
              { name: "maxSingleMl", label: this.tr(card, "max_single_ml"), type: "number", value: ctl.maxSingleMl || 50, min: 0.2, step: 0.1 },
              { name: "maxDailyMl", label: this.tr(card, "max_daily_ml"), type: "number", value: ctl.maxDailyMl || 250, min: 0.2, step: 0.1 },
            ],
            build: (values) => `chihirosctl config set-doser-safety --max-single-ml ${numberValue(values.maxSingleMl, 50)} --max-daily-ml ${numberValue(values.maxDailyMl, 250)}`,
          },
          {
            title: "Doser/Ruehrer-Link speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [
              { name: "doser", label: this.tr(card, "doser"), value: deviceRef },
              { name: "stirrer", label: this.tr(card, "ruehrer"), value: stirrer },
              { name: "channel", label: this.tr(card, "channel"), type: "number", value: channel, min: 0, max: 3, step: 1 },
              { name: "enabled", label: "Status", type: "select", value: "enabled", options: [["enabled", "Aktiv"], ["disabled", "Inaktiv"]] },
            ],
            build: (values) => `chihirosctl config set-doser-magstirrer-link ${this.formText(values, "doser", deviceRef)} ${this.formText(values, "stirrer", stirrer)} --doser-ch-id ${numberValue(values.channel, channel)} --${this.formText(values, "enabled", "enabled")}`,
          },
        ],
      },
      {
        title: this.tr(card, "stirrer_runtime"),
        forms: [
          {
            title: "Ruehrer-Defaults speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [
              { name: "leadTime", label: "Vorlauf Minuten", type: "number", value: 10, min: 0, max: 59, step: 1 },
              { name: "speed", label: "Speed", type: "number", value: 10, min: 0, max: 20, step: 1 },
            ],
            build: (values) => `chihirosctl config set-magstirrer-defaults --lead-time ${numberValue(values.leadTime, 10)} --speed ${numberValue(values.speed, 10)}`,
          },
          {
            title: "Ruehrer-Runtime speichern",
            button: this.tr(card, "ctl_config_save"),
            fields: [
              { name: "stirrer", label: this.tr(card, "ruehrer"), value: stirrer },
              { name: "channel", label: this.tr(card, "channel"), type: "number", value: channel, min: 0, max: 3, step: 1 },
              { name: "runtime", label: "Laufzeit Minuten", type: "number", value: 10, min: 0, max: 59, step: 1 },
              { name: "speed", label: "Speed", type: "number", value: 10, min: 0, max: 20, step: 1 },
              { name: "reserved", label: "Reserved", type: "number", value: 0, min: 0, max: 255, step: 1 },
            ],
            build: (values) => `chihirosctl config set-magstirrer-runtime ${this.formText(values, "stirrer", stirrer)} --ch-id ${numberValue(values.channel, channel)} --runtime-min ${numberValue(values.runtime, 10)} --speed ${numberValue(values.speed, 10)} --reserved ${numberValue(values.reserved, 0)}`,
          },
        ],
      },
      {
        title: this.tr(card, "data_base"),
        forms: [
          {
            title: this.tr(card, "database_migrate"),
            button: this.tr(card, "ctl_config_save"),
            fields: [],
            build: () => "chihirosctl config db-migrate",
          },
        ],
      },
    ];
  },

  configFormField(card, field) {
    const attrs = [
      `name="${card.escapeHtml(field.name)}"`,
      `data-ctl-form-field="${card.escapeHtml(field.name)}"`,
    ];
    if (field.min !== undefined) attrs.push(`min="${card.escapeHtml(field.min)}"`);
    if (field.max !== undefined) attrs.push(`max="${card.escapeHtml(field.max)}"`);
    if (field.step !== undefined) attrs.push(`step="${card.escapeHtml(field.step)}"`);
    if (field.type === "select") {
      const options = (field.options || []).map(([value, label]) => `
              <option value="${card.escapeHtml(value)}" ${String(field.value) === String(value) ? "selected" : ""}>${card.escapeHtml(label)}</option>`).join("");
      return `
            <label>
              <span>${card.escapeHtml(this.localizeLegacyText(card, field.label))}</span>
              <select ${attrs.join(" ")}>${options}</select>
            </label>`;
    }
    return `
            <label>
              <span>${card.escapeHtml(this.localizeLegacyText(card, field.label))}</span>
              <input type="${card.escapeHtml(field.type || "text")}" value="${card.escapeHtml(field.value ?? "")}" ${attrs.join(" ")}>
            </label>`;
  },

  updateConfigFromFields(card) {
    card.ctlConfig = card.ctlConfig || {};
    const numeric = new Set(["index", "channel", "maxSingleMl", "maxDailyMl"]);
    card.querySelectorAll("[data-ctl-config-field]").forEach((el) => {
      const key = el.getAttribute("data-ctl-config-field");
      if (!key) return;
      card.ctlConfig[key] = numeric.has(key) ? Number(el.value || 0) : String(el.value || "").trim();
    });
    if (card.ctlConfig.address) card.ctlDevice = String(card.ctlConfig.address).trim() || card.ctlDevice || "doser_1";
  },

  configCommands(card, field = "all") {
    const ctl = card.ctlConfig || {};
    const kind = String(ctl.kind || "doser");
    const index = Math.max(1, Number(ctl.index || 1));
    const deviceRef = String(ctl.address || card.ctlDevice || `${kind}_${index}`).trim() || `${kind}_${index}`;
    const channel = Math.max(0, Number(ctl.channel || 0));
    const commands = {
      language: [`chihirosctl config set-language ${ctl.language || "de"}`],
      kind: [`chihirosctl config set-device ${kind} ${index} ${deviceRef}`],
      index: [`chihirosctl config set-device ${kind} ${index} ${deviceRef}`],
      address: [`chihirosctl config set-device ${kind} ${index} ${deviceRef}`],
      name: [`chihirosctl config set-device-name ${kind} ${deviceRef} ${this.shellQuote(ctl.name || "Doser")}`],
      model: [`chihirosctl config set-device-model ${kind} ${deviceRef} ${this.shellQuote(ctl.model || "DosingPump")}`],
      channel: [`chihirosctl config set-channel-name ${kind} ${deviceRef} ${this.shellQuote(ctl.channelName || `CH${channel + 1}`)} --ch-id ${channel}`],
      channelName: [`chihirosctl config set-channel-name ${kind} ${deviceRef} ${this.shellQuote(ctl.channelName || `CH${channel + 1}`)} --ch-id ${channel}`],
      maxSingleMl: [`chihirosctl config set-doser-safety --max-single-ml ${Number(ctl.maxSingleMl || 50)} --max-daily-ml ${Number(ctl.maxDailyMl || 250)}`],
      maxDailyMl: [`chihirosctl config set-doser-safety --max-single-ml ${Number(ctl.maxSingleMl || 50)} --max-daily-ml ${Number(ctl.maxDailyMl || 250)}`],
      stirrerAddress: [],
    };
    if (kind === "doser" && String(ctl.stirrerAddress || "").trim()) {
      commands.stirrerAddress = [`chihirosctl config set-doser-magstirrer-link ${deviceRef} ${String(ctl.stirrerAddress).trim()} --doser-ch-id ${channel}`];
    }
    if (field !== "all") return commands[field] || [];
    return [
      ...commands.language,
      ...commands.kind,
      ...commands.name,
      ...commands.model,
      ...commands.channelName,
      ...commands.maxSingleMl,
      ...commands.stirrerAddress,
    ];
  },

  configCommandCatalog(card, ctl, kind, index, deviceRef, channel) {
    const quotedName = this.shellQuote(ctl.name || "Doser");
    const quotedModel = this.shellQuote(ctl.model || "DosingPump");
    const quotedChannelName = this.shellQuote(ctl.channelName || `CH${channel + 1}`);
    const stirrer = String(ctl.stirrerAddress || "ruehrer_1").trim() || "ruehrer_1";
    return [
      {
        title: "Basis",
        commands: [
          ["SQLite-Pfad anzeigen", "chihirosctl config path"],
          ["Alle gespeicherten Werte anzeigen", "chihirosctl config list"],
          ["Werte nach Prefix anzeigen", "chihirosctl config list --prefix doser_safety"],
          ["Einzelnen Wert speichern", "chihirosctl config set example.key example-value"],
          ["Einzelnen Wert anzeigen", "chihirosctl config get example.key"],
          ["Einzelnen Wert löschen", "chihirosctl config delete example.key"],
        ],
      },
      {
        title: "Gerät allgemein",
        commands: [
          ["Gerät speichern", `chihirosctl config set-device ${kind} ${index} ${deviceRef}`],
          ["Gerät mit Name und Modell speichern", `chihirosctl config set-device ${kind} ${index} ${deviceRef} --alias ${kind}_${index} --label ${quotedName} --model ${quotedModel}`],
          ["Gerät anzeigen", `chihirosctl config show-device ${kind} ${kind}_${index}`],
          ["Gerät löschen", `chihirosctl config delete-device ${kind} ${kind}_${index}`],
          ["Alle Geräte anzeigen", "chihirosctl config list-devices"],
          ["Geräte nach Typ anzeigen", `chihirosctl config list-devices --kind ${kind}`],
          ["Alias aufloesen", `chihirosctl config resolve ${deviceRef}`],
          ["Profile anzeigen", `chihirosctl config list-profiles --kind ${kind}`],
        ],
      },
      {
        title: "Doser",
        commands: [
          ["Doser speichern", `chihirosctl config set-doser ${index} ${deviceRef}`],
          ["Doser anzeigen", `chihirosctl config show-doser ${index}`],
          ["Doser löschen", `chihirosctl config delete-doser ${index}`],
        ],
      },
      {
        title: "LED",
        commands: [
          ["LED speichern", `chihirosctl config set-led ${index} ${deviceRef}`],
          ["LED anzeigen", `chihirosctl config show-led ${index}`],
          ["LED löschen", `chihirosctl config delete-led ${index}`],
        ],
      },
      {
        title: "Rührer",
        commands: [
          ["Rührer speichern", `chihirosctl config set-magstirrer ${index} ${deviceRef}`],
          ["Rührer anzeigen", `chihirosctl config show-magstirrer ${index}`],
          ["Rührer löschen", `chihirosctl config delete-magstirrer ${index}`],
        ],
      },
      {
        title: "Namen und Kanäle",
        commands: [
          ["Sprache speichern", `chihirosctl config set-language ${ctl.language || "de"}`],
          ["Sprache anzeigen", "chihirosctl config show-language"],
          ["Sprache löschen", "chihirosctl config delete-language"],
          ["Gerätename speichern", `chihirosctl config set-device-name ${kind} ${deviceRef} ${quotedName}`],
          ["Gerätename löschen", `chihirosctl config delete-device-name ${kind} ${deviceRef}`],
          ["Modell speichern", `chihirosctl config set-device-model ${kind} ${deviceRef} ${quotedModel}`],
          ["Modell löschen", `chihirosctl config delete-device-model ${kind} ${deviceRef}`],
          ["Kanalname speichern", `chihirosctl config set-channel-name ${kind} ${deviceRef} ${quotedChannelName} --ch-id ${channel}`],
          ["Kanalname löschen", `chihirosctl config delete-channel-name ${kind} ${deviceRef} --ch-id ${channel}`],
          ["Lokale Namen anzeigen", `chihirosctl config show-local-names --kind ${kind} --device ${deviceRef}`],
        ],
      },
      {
        title: "Sicherheit und Links",
        commands: [
          ["Doser-Schutz speichern", `chihirosctl config set-doser-safety --max-single-ml ${Number(ctl.maxSingleMl || 50)} --max-daily-ml ${Number(ctl.maxDailyMl || 250)}`],
          ["Doser-Schutz anzeigen", "chihirosctl config show-doser-safety"],
          ["Doser-Schutz löschen", "chihirosctl config delete-doser-safety"],
          ["Doser/Rührer-Link speichern", `chihirosctl config set-doser-magstirrer-link ${deviceRef} ${stirrer} --doser-ch-id ${channel}`],
          ["Doser/Rührer-Link aktivieren", `chihirosctl config set-doser-magstirrer-link-active ${deviceRef} --doser-ch-id ${channel} --enabled`],
          ["Doser/Rührer-Link deaktivieren", `chihirosctl config set-doser-magstirrer-link-active ${deviceRef} --doser-ch-id ${channel} --disabled`],
          ["Doser/Rührer-Links anzeigen", "chihirosctl config show-doser-magstirrer-links"],
          ["Doser/Rührer-Link löschen", `chihirosctl config delete-doser-magstirrer-link ${deviceRef} --doser-ch-id ${channel}`],
        ],
      },
      {
        title: "Rührer-Laufzeit",
        commands: [
          ["Rührer-Defaults anzeigen", "chihirosctl config show-magstirrer-defaults"],
          ["Rührer-Defaults speichern", "chihirosctl config set-magstirrer-defaults --lead-time 10 --speed 10"],
          ["Rührer-Laufzeit speichern", `chihirosctl config set-magstirrer-runtime ${stirrer} --ch-id ${channel} --runtime-min 10 --speed 10`],
          ["Rührer-Laufzeit anzeigen", "chihirosctl config show-magstirrer-runtime"],
          ["Rührer-Laufzeit löschen", `chihirosctl config delete-magstirrer-runtime ${stirrer} --ch-id ${channel}`],
        ],
      },
      {
        title: "Datenbank",
        commands: [
          ["Datenbank-Info anzeigen", "chihirosctl config db-info"],
          ["Datenbank migrieren", "chihirosctl config db-migrate"],
        ],
      },
    ];
  },

  actionLabel(command) {
    const text = String(command || "");
    if (text.includes(" delete-") || text.includes(" config delete ")) return "LOESCHEN";
    if (text.includes(" show-") || text.includes(" list") || text.includes(" path") || text.includes(" resolve ") || text.includes(" get ") || text.includes("db-info")) return "ANZEIGEN";
    if (text.includes("db-migrate")) return "MIGRIEREN";
    if (text.includes(" --disabled")) return "DEAKTIVIEREN";
    if (text.includes(" --enabled")) return "AKTIVIEREN";
    return "SPEICHERN";
  },

  backend(functionName, ...args) {
    const api = window.ChihirosAddonApi;
    if (!api || typeof api.callPluginBackend !== "function") {
      throw new Error("Plugin Backend API nicht verfuegbar");
    }
    return api.callPluginBackend("ctl", functionName, args);
  },

  async runCommand(card, command, title = "CTL", noChannel = true) {
    const api = window.ChihirosAddonApi;
    if (!api || typeof api.callPluginBackend !== "function") {
      throw new Error("Plugin Backend API nicht verfuegbar");
    }
    card.dialogState = {
      type: "debug",
      channel: 1,
      output: `${this.tr(card, "ctl_running")}\n$ ${command}`,
      debug: false,
      running: true,
      noChannel,
      level: "pending",
    };
    card.render();
    try {
      const result = await this.backend("run_command", command);
      const output = String(result.output || this.tr(card, "ctl_failed"));
      card.dialogState = {
        type: "debug",
        channel: 1,
        output: [`OK`, `$ ${command}`, output].filter(Boolean).join("\n"),
        debug: false,
        running: false,
        noChannel,
        level: "ok",
      };
    } catch (err) {
      const data = err && err.data ? err.data : {};
      const output = data.output || (err && err.message ? err.message : err) || this.tr(card, "ctl_failed");
      const returncode = data.returncode !== undefined ? `Returncode: ${data.returncode}` : "";
      card.dialogState = {
        type: "debug",
        channel: 1,
        output: [`FAIL`, `$ ${command}`, returncode, output].filter(Boolean).join("\n"),
        debug: false,
        running: false,
        noChannel,
        level: "error",
      };
    }
    card.render();
  },

  async runCommands(card, commands, title = "CTL Config speichern") {
    const list = (Array.isArray(commands) ? commands : []).map((item) => String(item || "").trim()).filter(Boolean);
    if (!list.length) return;
    card.dialogState = {
      type: "debug",
      channel: 1,
      output: [`${title}...`, ...list.map((command) => `$ ${command}`)].join("\n"),
      debug: false,
      running: true,
      noChannel: true,
      level: "pending",
    };
    card.render();
    const output = [];
    let failed = false;
    for (const command of list) {
      output.push(`$ ${command}`);
      try {
        const result = await this.backend("run_command", command);
        output.push(String(result.output || "OK"));
      } catch (err) {
        failed = true;
        const data = err && err.data ? err.data : {};
        const returncode = data.returncode !== undefined ? `Returncode: ${data.returncode}` : "";
        output.push(["FAIL", returncode, data.output || (err && err.message ? err.message : err)].filter(Boolean).join("\n"));
        break;
      }
    }
    card.dialogState = {
      type: "debug",
      channel: 1,
      output: [failed ? "FAIL" : "OK", title, ...output].join("\n"),
      debug: false,
      running: false,
      noChannel: true,
      level: failed ? "error" : "ok",
    };
    card.render();
  },

  ctlAreaOptions() {
    return [
      ["led", "LED"],
      ["doser", "Doser"],
      ["ruehrer", "Ruehrer"],
      ["heizer", "Heizer"],
      ["wireshark", "Wireshark"],
    ];
  },

  ctlBrightnessFields(max) {
    return [
      { name: "red", label: "CH1 Rot", type: "number", value: max, min: 0, max, step: 1 },
      { name: "green", label: "CH2 Gruen", type: "number", value: max, min: 0, max, step: 1 },
      { name: "blue", label: "CH3 Blau", type: "number", value: max, min: 0, max, step: 1 },
      { name: "white", label: "CH4 Weiss", type: "number", value: max, min: 0, max, step: 1 },
    ];
  },

  ctlCommandDefinitions(card) {
    const device = String(card.ctlDevice || "doser_1").trim() || "doser_1";
    const ledMax = this.ctlLedMaxBrightness(card);
    const brightness = (values) => ["red", "green", "blue", "white"].map((key) => Number(values[key] || 0)).join(" ");
    const weekdays = (values) => {
      const raw = String(values.weekdays || "none");
      if (!raw || raw === "none") return "";
      if (raw === "everyday") return "--weekdays everyday";
      return raw.split(",").filter(Boolean).map((day) => `--weekdays ${day}`).join(" ");
    };
    const defs = [
      { kind: "led", title: "Geräte suchen", fields: [], build: () => "chihirosctl led list-devices" },
      { kind: "led", title: "LED einschalten", fields: [{ name: "device", label: "Device", type: "device", value: device }], build: (v) => `chihirosctl led turn-on ${v.device}` },
      { kind: "led", title: "LED ausschalten", fields: [{ name: "device", label: "Device", type: "device", value: device }], build: (v) => `chihirosctl led turn-off ${v.device}` },
      { kind: "led", title: "Helligkeit setzen", fields: [{ name: "device", label: "Device", type: "device", value: device }, ...this.ctlBrightnessFields(ledMax)], build: (v) => `chihirosctl led set-brightness ${v.device} ${brightness(v)}` },
      { kind: "led", title: "Zeitfenster setzen", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "start", label: "Von", type: "time", value: "08:00" }, { name: "end", label: "Bis", type: "time", value: "20:00" }, ...this.ctlBrightnessFields(ledMax), { name: "ramp", label: "Ramp", type: "ramp", value: "0" }, { name: "weekdays", label: "Wochentage", type: "weekdays", value: "everyday" }], build: (v) => `chihirosctl led add-setting ${v.device} ${v.start} ${v.end} ${brightness(v)} --ramp-up-in-minutes ${v.ramp} ${weekdays(v)}`.trim() },
      { kind: "led", title: "Zeitfenster entfernen", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "start", label: "Von", type: "time", value: "08:00" }, { name: "end", label: "Bis", type: "time", value: "20:00" }, { name: "weekdays", label: "Wochentage", type: "weekdays", value: "none" }], build: (v) => `chihirosctl led remove-setting ${v.device} ${v.start} ${v.end} ${weekdays(v)}`.trim() },
      { kind: "led", title: "Zeitplan zurücksetzen", fields: [{ name: "device", label: "Device", type: "device", value: device }], build: (v) => `chihirosctl led reset-settings ${v.device}` },
      { kind: "led", title: "Auto Mode aktivieren", fields: [{ name: "device", label: "Device", type: "device", value: device }], build: (v) => `chihirosctl led enable-auto-mode ${v.device}` },
      { kind: "led", title: "Gerätemeldungen abrufen", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "wait", label: "Wartezeit (s)", type: "number", value: 5, min: 0, max: 30, step: 0.5 }], build: (v) => `chihirosctl --debug led read-notifications ${v.device} --notification-wait ${v.wait}` },
      { kind: "led", title: "Template speichern", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "template", label: "Name", value: "day" }, ...this.ctlBrightnessFields(ledMax)], build: (v) => `chihirosctl template set-template ${v.device} --template-name ${this.shellQuote(v.template)} ${brightness(v)}` },
      { kind: "led", title: "Template laden", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "template", label: "Name", value: "day" }], build: (v) => `chihirosctl template load-template ${v.device} --template-name ${this.shellQuote(v.template)}` },
      { kind: "led", title: "Template löschen", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "template", label: "Name", value: "day" }], build: (v) => `chihirosctl template delete-template ${v.device} --template-name ${this.shellQuote(v.template)}` },

      { kind: "doser", title: "Dosieren", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "pump", label: "Kanal", type: "channel1", value: "1" }, { name: "ml", label: "ml", type: "number", value: 0.2, min: 0, max: 100, step: 0.1 }], build: (v) => `chihirosctl doser dose-ml ${v.device} --pump ${v.pump} --ml ${v.ml} --debug` },
      { kind: "doser", title: "Schedule anzeigen", fields: [{ name: "device", label: "Device", type: "device", value: device }], build: (v) => `chihirosctl doser show-schedules ${v.device}` },
      { kind: "doser", title: "Schedule löschen", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "pump", label: "Kanal", type: "channel1", value: "1" }], build: (v) => `chihirosctl doser clear-schedule ${v.device} --ch-id ${v.pump}` },
      { kind: "doser", title: "Dosis-Zeit setzen", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "time", label: "Zeit", type: "time", value: "08:00" }, { name: "pump", label: "Kanal", type: "channel1", value: "1" }, { name: "ml", label: "ml", type: "number", value: 0.2, min: 0, max: 100, step: 0.1 }, { name: "weekdays", label: "Wochentage", type: "weekdays", value: "everyday" }], build: (v) => `chihirosctl doser add-setting-dosing-pump ${v.device} ${v.time} --ch-id ${v.pump} --ch-ml ${v.ml} ${weekdays(v)}`.trim() },
      { kind: "doser", title: "Behälter setzen", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "pump", label: "Kanal", type: "channel1", value: "1" }, { name: "ml", label: "ml", type: "number", value: 500, min: 0, max: 5000, step: 1 }], build: (v) => `chihirosctl doser set-container ${v.device} --ch-id ${v.pump} --ml ${v.ml}` },

      { kind: "ruehrer", title: "Anzeigen", fields: [{ name: "device", label: "Device", type: "device", value: device }], build: (v) => `chihirosctl magstirrer show ${v.device}` },
      { kind: "ruehrer", title: "Power", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "power", label: "Power", type: "onoff", value: "on" }], build: (v) => `chihirosctl magstirrer set-power ${v.device} --${v.power}` },
      { kind: "ruehrer", title: "Laufen lassen", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "seconds", label: "Sekunden", type: "number", value: 10, min: 1, max: 3600, step: 1 }], build: (v) => `chihirosctl magstirrer run-for ${v.device} --seconds ${v.seconds}` },
      { kind: "ruehrer", title: "Runtime/Speed setzen", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "ch", label: "Kanal", type: "channel0", value: "0" }, { name: "runtime", label: "Minuten", type: "number", value: 90, min: 1, max: 240, step: 1 }, { name: "speed", label: "Speed", type: "number", value: 70, min: 1, max: 100, step: 1 }], build: (v) => `chihirosctl magstirrer set-runtime-speed ${v.device} --ch-id ${v.ch} --runtime-minutes ${v.runtime} --speed ${v.speed}` },
      { kind: "ruehrer", title: "Timer setzen", fields: [{ name: "device", label: "Device", type: "device", value: device }, { name: "ch", label: "Kanal", type: "channel0", value: "0" }, { name: "time", label: "Zeit", type: "time", value: "08:00" }, { name: "seconds", label: "Sekunden", type: "number", value: 360, min: 1, max: 3600, step: 1 }, { name: "weekdays", label: "Wochentage", type: "weekdays", value: "everyday" }], build: (v) => `chihirosctl magstirrer set-timers ${v.device} --ch-id ${v.ch} --timer ${v.time}=${v.seconds} ${weekdays(v)}`.trim() },
    ];
    return defs;
  },

  ctlFieldMarkup(card, field, formIndex) {
    const name = card.escapeHtml(field.name);
    const value = card.escapeHtml(field.value ?? "");
    const attrs = `data-ctl-command-field="${name}" name="${name}"`;
    const label = `<span>${card.escapeHtml(this.localizeLegacyText(card, field.label || field.name))}</span>`;
    const options = (items) => items.map(([val, text]) => `<option value="${card.escapeHtml(val)}" ${String(field.value) === String(val) ? "selected" : ""}>${card.escapeHtml(text)}</option>`).join("");
    if (field.type === "channel0") return `<label>${label}<select ${attrs}>${options([["0", "CH0"], ["1", "CH1"], ["2", "CH2"], ["3", "CH3"]])}</select></label>`;
    if (field.type === "channel1") return `<label>${label}<select ${attrs}>${options([["1", "CH1"], ["2", "CH2"], ["3", "CH3"], ["4", "CH4"]])}</select></label>`;
    if (field.type === "ramp") return `<label>${label}<select ${attrs}>${options([["0", "0"], ["30", "30 Min"], ["60", "1 Std"], ["90", "1.5 Std"], ["120", "2 Std"], ["150", "2.5 Std"]])}</select></label>`;
    if (field.type === "onoff") return `<label>${label}<select ${attrs}>${options([["on", "An"], ["off", "Aus"]])}</select></label>`;
    if (field.type === "weekdays") {
      const selected = new Set(String(field.value || "none").split(",").filter(Boolean));
      const days = [["none", "Kein"], ["everyday", "Alle"], ["monday", "Mo"], ["tuesday", "Di"], ["wednesday", "Mi"], ["thursday", "Do"], ["friday", "Fr"], ["saturday", "Sa"], ["sunday", "So"]];
      return `<label class="ctl-weekday-field">${label}<input type="hidden" ${attrs} value="${value}"><div class="ctl-weekday-chips">${days.map(([val, text]) => `<button type="button" class="${selected.has(val) ? "active" : ""}" data-ctl-weekday="${card.escapeHtml(val)}" data-ctl-weekday-form="${formIndex}">${text}</button>`).join("")}</div></label>`;
    }
    const type = field.type === "time" ? "time" : (field.type === "number" ? "number" : "text");
    const extra = [
      field.min !== undefined ? `min="${card.escapeHtml(field.min)}"` : "",
      field.max !== undefined ? `max="${card.escapeHtml(field.max)}"` : "",
      field.step !== undefined ? `step="${card.escapeHtml(field.step)}"` : "",
      field.type === "device" ? "pattern=\"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$|^[A-Za-z0-9_.:-]+$\"" : "",
    ].filter(Boolean).join(" ");
    return `<label>${label}<input type="${type}" ${attrs} value="${value}" ${extra}></label>`;
  },

  ctlCommandForm(card, definition, index) {
    const values = {};
    (definition.fields || []).forEach((field) => { values[field.name] = field.value ?? ""; });
    const preview = definition.build(values);
    const fields = (definition.fields || []).length
      ? `<div class="ctl-command-form-fields">${definition.fields.map((field) => this.ctlFieldMarkup(card, field, index)).join("")}</div>`
      : `<div class="ctl-form-empty">${this.tr(card, "ctl_config_no_input")}</div>`;
    return `
      <form class="ctl-command-form" data-ctl-command-form="${index}">
        <div class="ctl-command-form-head">
          <strong>${card.escapeHtml(this.localizeLegacyText(card, definition.title))}</strong>
          <button type="submit" class="ctl-command-run">${card.config.addon_mode ? this.tr(card, "run_command") : this.tr(card, "copy_command")}</button>
        </div>
        ${fields}
        <div class="ctl-command-preview"><span>${this.tr(card, "ctl_preview")}</span><code data-ctl-command-preview>${card.escapeHtml(preview)}</code></div>
      </form>`;
  },

  renderPanel(card) {
    const area = String(card.ctlCommandKind || "led");
    const definitions = this.ctlCommandDefinitions(card).filter((definition) => definition.kind === area);
    card.ctlCommandFormIndex = definitions;
    const areaOptions = this.ctlAreaOptions().map(([value, label]) => `<option value="${card.escapeHtml(value)}" ${area === value ? "selected" : ""}>${card.escapeHtml(label)}</option>`).join("");
    const groups = definitions.length
      ? `<div class="ctl-command-list">${definitions.map((definition, index) => this.ctlCommandForm(card, definition, index)).join("")}</div>`
      : `<div class="empty-note">${this.tr(card, "ctl_no_commands")}</div>`;
    return `
      ${this.styles()}
      <div class="ctl-plugin-page">
        ${card.pageHeader(this.tr(card, "ctl_panel_title"), this.tr(card, "ctl_panel_subtitle"), "mdi:console")}
        <section class="card config-card ctl-plugin-card ctl-card">
          <h2>${this.tr(card, "ctl_commands")}</h2>
          <label class="ctl-area-row">
            <span>${this.tr(card, "ctl_area")}</span>
            <select data-ctl-command-kind>${areaOptions}</select>
          </label>
          <div class="ctl-device-row">
            <input type="text" data-ctl-device value="${card.escapeHtml(card.ctlDevice || "doser_1")}" placeholder="${this.tr(card, "ctl_device_placeholder")}">
            <button type="button" data-ctl-device-save>OK</button>
          </div>
          ${groups}
        </section>
      </div>`;
  },

  renderConfig(card) {
    const db = card.config.addon_database || {};
    const effectiveState = String(db.effective_state_db_path || db.state_db_path || "/config/.chihiros/chihiros_state.sqlite3");
    const ctl = card.ctlConfig || {};
    const deviceRef = String(ctl.address || card.ctlDevice || "doser_1");
    const kind = String(ctl.kind || "doser");
    const index = Number(ctl.index || 1);
    const channel = Number(ctl.channel || 0);
    card.ctlConfigFormIndex = [];
    const formGroups = this.configFormGroups(card, ctl, kind, index, deviceRef, channel).map((group) => {
      const forms = group.forms.map((form) => {
        const formIndex = card.ctlConfigFormIndex.length;
        card.ctlConfigFormIndex.push(form);
        const fields = form.fields.length
          ? `<div class="ctl-form-fields">${form.fields.map((field) => this.configFormField(card, field)).join("")}</div>`
          : `<div class="ctl-form-empty">${this.tr(card, "ctl_config_no_input")}</div>`;
        return `
          <form class="ctl-config-form" data-ctl-config-form="${formIndex}">
            <div class="ctl-config-form-head">
              <strong>${card.escapeHtml(this.localizeLegacyText(card, form.title))}</strong>
              <button type="submit">
                <ha-icon icon="mdi:content-save-outline"></ha-icon>
                <b>${form.button || this.tr(card, "ctl_config_save")}</b>
              </button>
            </div>
            ${fields}
          </form>`;
      }).join("");
      return `
        <div class="ctl-form-section">
          <h3>${card.escapeHtml(this.localizeLegacyText(card, group.title))}</h3>
          <div class="ctl-config-form-grid">${forms}</div>
        </div>`;
    }).join("");
    const readOnlyGroups = this.configCommandCatalog(card, ctl, kind, index, deviceRef, channel)
      .map((group) => {
        const buttons = group.commands
          .filter(([_label, text]) => !String(text).includes(" set") && !String(text).includes("db-migrate"))
          .map(([label, text]) => `
            <button type="button" class="ctl-read-action" data-copy="${card.escapeHtml(text)}">
              <ha-icon icon="mdi:eye-outline"></ha-icon>
              <span>${card.escapeHtml(this.localizeLegacyText(card, label))}</span>
            </button>`).join("");
        return buttons ? `<div class="ctl-read-section"><h3>${card.escapeHtml(this.localizeLegacyText(card, group.title))}</h3><div>${buttons}</div></div>` : "";
      })
      .join("");
    const readOnlyPanel = readOnlyGroups ? `
      <details class="ctl-readonly-details">
        <summary>${this.tr(card, "ctl_config_readonly")}</summary>
        <div class="ctl-readonly-grid">${readOnlyGroups}</div>
      </details>` : "";
    return `
      ${this.styles()}
      <section class="card config-card ctl-plugin-card ctl-config-card">
        <div class="config-card-head">
          <div>
            <h2>${this.tr(card, "ctl_config_title")}</h2>
            <small>${this.tr(card, "ctl_config_subtitle")}</small>
          </div>
          <span class="db-pill">Config</span>
        </div>
        <div class="ctl-config-fields">
          <label class="ctl-config-field">
            <span>${this.tr(card, "language")}</span>
            <select data-ctl-config-field="language">
              <option value="de" ${ctl.language === "de" ? "selected" : ""}>${this.tr(card, "language_de")}</option>
              <option value="en" ${ctl.language === "en" ? "selected" : ""}>${this.tr(card, "language_en")}</option>
            </select>
          </label>
          <label class="ctl-config-field">
            <span>${this.tr(card, "kind")}</span>
            <select data-ctl-config-field="kind">
              <option value="doser" ${kind === "doser" ? "selected" : ""}>Doser</option>
              <option value="led" ${kind === "led" ? "selected" : ""}>LED</option>
              <option value="ruehrer" ${kind === "ruehrer" ? "selected" : ""}>Ruehrer</option>
              <option value="heizer" ${kind === "heizer" ? "selected" : ""}>Heizer</option>
            </select>
          </label>
          <label class="ctl-config-field">
            <span>${this.tr(card, "index")}</span>
            <input type="number" min="1" max="4" step="1" data-ctl-config-field="index" value="${card.escapeHtml(index)}">
          </label>
          <label class="ctl-config-field">
            <span>${this.tr(card, "address")}</span>
            <input type="text" data-ctl-config-field="address" value="${card.escapeHtml(deviceRef)}">
          </label>
          <label class="ctl-config-field">
            <span>${this.tr(card, "name")}</span>
            <input type="text" data-ctl-config-field="name" value="${card.escapeHtml(ctl.name || "Doser")}">
          </label>
          <label class="ctl-config-field">
            <span>${this.tr(card, "model")}</span>
            <input type="text" data-ctl-config-field="model" value="${card.escapeHtml(ctl.model || "DosingPump")}">
          </label>
          <label class="ctl-config-field">
            <span>${this.tr(card, "channel")}</span>
            <input type="number" min="0" max="3" step="1" data-ctl-config-field="channel" value="${card.escapeHtml(channel)}">
          </label>
          <label class="ctl-config-field">
            <span>${this.tr(card, "channel_name")}</span>
            <input type="text" data-ctl-config-field="channelName" value="${card.escapeHtml(ctl.channelName || "CH1")}">
          </label>
          <label class="ctl-config-field">
            <span>${this.tr(card, "max_single_ml")}</span>
            <input type="number" min="0" step="0.1" data-ctl-config-field="maxSingleMl" value="${card.escapeHtml(ctl.maxSingleMl || 50)}">
          </label>
          <label class="ctl-config-field">
            <span>${this.tr(card, "max_daily_ml")}</span>
            <input type="number" min="0" step="0.1" data-ctl-config-field="maxDailyMl" value="${card.escapeHtml(ctl.maxDailyMl || 250)}">
          </label>
          <label class="ctl-config-field">
            <span>${this.tr(card, "stirrer_alias")}</span>
            <input type="text" data-ctl-config-field="stirrerAddress" value="${card.escapeHtml(ctl.stirrerAddress || "ruehrer_1")}">
          </label>
        </div>
        <div class="ctl-config-save-row">
          <button type="button" class="primary" data-ctl-config-save="all">
            <ha-icon icon="mdi:content-save-all-outline"></ha-icon>
            <span>${this.tr(card, "save_all")}</span>
          </button>
        </div>
        <h2 class="sub-head">${this.tr(card, "ctl_config_mask_title")}</h2>
        <div class="ctl-form-wrap">
          ${formGroups}
        </div>
        ${readOnlyPanel}
        <div class="ctl-path-strip">
          <span><b>SQLite</b>${card.escapeHtml(effectiveState)}</span>
        </div>
      </section>`;
  },

  bindEvents(card) {
    card.querySelectorAll("[data-copy]").forEach((el) => {
      el.addEventListener("click", () => this.runCommand(card, el.getAttribute("data-copy") || "", "CTL", true));
    });
    const ctlDeviceInput = card.querySelector("[data-ctl-device]");
    const ctlDeviceSave = card.querySelector("[data-ctl-device-save]");
    if (ctlDeviceInput) {
      const saveCtlDevice = () => {
        card.ctlDevice = String(ctlDeviceInput.value || "").trim() || "doser_1";
        ctlDeviceInput.value = card.ctlDevice;
        card.ctlConfig = card.ctlConfig || {};
        card.ctlConfig.address = card.ctlDevice;
        card.render();
      };
      ctlDeviceInput.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") saveCtlDevice();
      });
      ctlDeviceInput.addEventListener("change", saveCtlDevice);
      if (ctlDeviceSave) ctlDeviceSave.addEventListener("click", saveCtlDevice);
    }
    const ctlCommandKind = card.querySelector("[data-ctl-command-kind]");
    if (ctlCommandKind) {
      ctlCommandKind.addEventListener("change", () => {
        card.ctlCommandKind = String(ctlCommandKind.value || "led");
        card.render();
      });
    }
    const collectCommandValues = (form) => {
      const values = {};
      form.querySelectorAll("[data-ctl-command-field]").forEach((field) => {
        values[field.getAttribute("data-ctl-command-field")] = field.value;
      });
      return values;
    };
    const updateCommandPreview = (form) => {
      const index = Number(form.getAttribute("data-ctl-command-form"));
      const definition = card.ctlCommandFormIndex && card.ctlCommandFormIndex[index];
      const preview = form.querySelector("[data-ctl-command-preview]");
      if (!definition || !preview) return "";
      const command = definition.build(collectCommandValues(form));
      preview.textContent = command;
      return command;
    };
    card.querySelectorAll("[data-ctl-command-form]").forEach((form) => {
      form.querySelectorAll("[data-ctl-command-field]").forEach((field) => {
        field.addEventListener("input", () => updateCommandPreview(form));
        field.addEventListener("change", () => updateCommandPreview(form));
      });
      form.querySelectorAll("[data-ctl-weekday]").forEach((chip) => {
        chip.addEventListener("click", () => {
          const value = chip.getAttribute("data-ctl-weekday");
          const hidden = form.querySelector("[data-ctl-command-field='weekdays']");
          if (!hidden) return;
          if (value === "none" || value === "everyday") {
            form.querySelectorAll("[data-ctl-weekday]").forEach((item) => item.classList.remove("active"));
            chip.classList.add("active");
            hidden.value = value;
          } else {
            form.querySelectorAll("[data-ctl-weekday='none'], [data-ctl-weekday='everyday']").forEach((item) => item.classList.remove("active"));
            chip.classList.toggle("active");
            const selected = Array.from(form.querySelectorAll("[data-ctl-weekday].active"))
              .map((item) => item.getAttribute("data-ctl-weekday"))
              .filter((item) => item && item !== "none" && item !== "everyday");
            hidden.value = selected.length ? selected.join(",") : "none";
            if (!selected.length) form.querySelector("[data-ctl-weekday='none']")?.classList.add("active");
          }
          updateCommandPreview(form);
        });
      });
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        if (!form.reportValidity()) return;
        const command = updateCommandPreview(form);
        if (command) await this.runCommand(card, command, "CTL", true);
      });
    });
    card.querySelectorAll("[data-ctl-config-field]").forEach((el) => {
      const save = () => {
        const key = el.getAttribute("data-ctl-config-field");
        if (!key) return;
        card.ctlConfig = card.ctlConfig || {};
        const numeric = new Set(["index", "channel", "maxSingleMl", "maxDailyMl"]);
        card.ctlConfig[key] = numeric.has(key) ? Number(el.value || 0) : String(el.value || "").trim();
        if (key === "address") card.ctlDevice = String(el.value || "").trim() || card.ctlDevice || "doser_1";
      };
      el.addEventListener("change", save);
      el.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") save();
      });
    });
    card.querySelectorAll("[data-ctl-config-save]").forEach((el) => {
      el.addEventListener("click", async () => {
        const field = el.getAttribute("data-ctl-config-save") || "all";
        this.updateConfigFromFields(card);
        await this.runCommands(
          card,
          this.configCommands(card, field),
          field === "all" ? "Alle CTL Config Werte speichern" : `CTL Config speichern: ${field}`,
        );
      });
    });
    card.querySelectorAll("[data-ctl-config-form]").forEach((form) => {
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const index = Number(form.getAttribute("data-ctl-config-form"));
        const definition = card.ctlConfigFormIndex && card.ctlConfigFormIndex[index];
        if (!definition || typeof definition.build !== "function") return;
        const values = {};
        form.querySelectorAll("[data-ctl-form-field]").forEach((field) => {
          values[field.getAttribute("data-ctl-form-field")] = field.value;
        });
        await this.runCommands(card, [definition.build(values)], this.localizeLegacyText(card, definition.title));
      });
    });
    card.querySelectorAll("[data-ctl-command-run]").forEach((el) => {
      el.addEventListener("click", async () => {
        const row = el.closest(".ctl-command-row");
        const input = row ? row.querySelector("input") : null;
        const command = input ? String(input.value || "").trim() : "";
        if (command) await this.runCommands(card, [command], "CTL Config Befehl speichern");
      });
    });
  },
};
