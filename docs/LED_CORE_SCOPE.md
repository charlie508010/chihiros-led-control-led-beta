# Chihiros LED Core

Dieses Repository ist die getrennte Arbeitskopie für die LED-Steuerung.

## Aktiver Umfang

- LED-BLE-Verbindung und LED-Protokoll
- LED-Farbkanäle und Leistungsanzeige
- LED-Zeitpläne, Vorlagen und automatische Statusprüfung
- Home-Assistant-Integration und LED-Dashboard
- `chihirosctl led` und `chihirosctl template`

Die eigenständigen Bereiche für Doser, Rührer, Heizer, Wireshark und das allgemeine CTL-Dashboard sind nicht Bestandteil
dieses Repositories. Das gilt für Backend, Protokoll, Home-Assistant-Services, Dashboard, CLI und Tests.

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

## Getrennte Entwicklung

- Dieses Repository enthält ausschließlich den stabilen LED Core und seine klar definierten Erweiterungsschnittstellen.
- Die LED-Entwicklung erfolgt direkt in diesem Repository. Änderungen aus einem Geräteprojekt dürfen nicht den
  LED-Protokoll-, Scheduler-, Dashboard- oder Home-Assistant-Code überschreiben.
- Doser und weitere Gerätearten werden in eigenen Repositories entwickelt und getestet.
- Gemeinsame Funktionen werden erst nach Prüfung als kleine, geräteunabhängige Core-Schnittstelle übernommen.
- Gerätefunktionen werden später einzeln als versionierte Plugins oder Pakete angebunden. Es werden keine vollständigen
  Entwicklungsstände eines anderen Geräterepositories ungeprüft in den LED Core kopiert.
- Während einer direkten gemeinsamen Arbeit an demselben Stand wird vorher vereinbart, wer den Stand bearbeitet. Der
  andere Entwickler beginnt erst nach Commit und Aktualisierung des gemeinsamen Branches.

Historische Doser-, Rührer-, Heizer-, Wireshark- und allgemeine CTL-Kompatibilitätsdateien im aktuellen Export sind
Migrationsreste und gehören nicht zum Zielstand. Sie werden abhängigkeitsweise entfernt; bis dahin darf dieser Export
nicht als vollständig getrennt bezeichnet werden.
