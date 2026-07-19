# Chihiros LED Core

Dieses Repository ist die getrennte Arbeitskopie für die LED-Steuerung.

## Aktiver Umfang

- LED-BLE-Verbindung und LED-Protokoll
- LED-Farbkanäle und Leistungsanzeige
- LED-Zeitpläne, Vorlagen und automatische Statusprüfung
- Home-Assistant-Integration und LED-Dashboard
- `chihirosctl led` und `chihirosctl template`

Die eigenständigen Add-ons für Doser, Rührer, Heizer, Wireshark und das allgemeine CTL-Dashboard sind nicht Bestandteil
dieses Repository-Exports.

## Erweiterungen

Weitere Gerätearten werden später als getrennte Plugins oder Pakete angebunden. Sie sollen ihre eigenen Protokoll-,
Service-, UI- und Testmodule besitzen und die LED-Funktionen nicht verändern. Gemeinsame BLE-, Debug-, Speicher- und
Dialogfunktionen dürfen über klar definierte Core-Schnittstellen genutzt werden.

Vorgesehene Struktur:

```text
LED Core
├── gemeinsame BLE- und Debug-Schnittstellen
├── LED-Protokoll, Services, UI und Tests
└── Plugin-Schnittstellen
    ├── Doser (später)
    ├── Rührer (später)
    ├── Heizer (später)
    └── Wireshark/Diagnose (später)
```

Bis die historischen gemeinsam genutzten Module vollständig in Plugins überführt sind, bleiben interne
Kompatibilitätsfunktionen im Quellbaum. Sie werden über den LED-only-CLI-Einstiegspunkt nicht angeboten. Dadurch bleibt
der aktuell funktionierende LED-Stand unverändert und kann schrittweise ohne Eingriff in das ursprüngliche Projekt
bereinigt werden.
