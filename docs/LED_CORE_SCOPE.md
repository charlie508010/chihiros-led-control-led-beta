# Chihiros LED Core

Dieses Repository ist die getrennte Arbeitskopie für die LED-Steuerung.

## Aktiver Umfang

- LED-BLE-Verbindung und LED-Protokoll
- LED-Farbkanäle und Leistungsanzeige
- LED-Zeitpläne, Vorlagen und automatische Statusprüfung
- Home-Assistant-Integration und LED-Dashboard
- `chihirosctl led` und `chihirosctl template`

Andere Gerätearten und allgemeine Diagnose-Dashboards sind nicht Bestandteil des LED Core. Ihr Code wird in getrennten
Repositories entwickelt und vom LED Core weder importiert noch registriert. Das gilt für Backend, Protokoll,
Home-Assistant-Services, Dashboard, CLI und Tests.

## Erweiterungen

Weitere Gerätearten werden später als getrennte Plugins oder Pakete angebunden. Sie sollen ihre eigenen Protokoll-,
Service-, UI- und Testmodule besitzen und die LED-Funktionen nicht verändern. Gemeinsame BLE-, Debug-, Speicher- und
Dialogfunktionen dürfen über klar definierte Core-Schnittstellen genutzt werden.

Aktuelle Struktur:

```text
LED Core
├── gemeinsame BLE- und Debug-Schnittstellen
└── LED-Protokoll, Services, UI und Tests
```

## Getrennte Entwicklung

- Dieses Repository enthält ausschließlich den stabilen LED Core und seine klar definierten Erweiterungsschnittstellen.
- Die LED-Entwicklung erfolgt direkt in diesem Repository. Änderungen aus einem Geräteprojekt dürfen nicht den
  LED-Protokoll-, Scheduler-, Dashboard- oder Home-Assistant-Code überschreiben.
- Weitere Gerätearten werden in eigenen Repositories entwickelt und getestet.
- Gemeinsame Funktionen werden erst nach Prüfung als kleine, geräteunabhängige Core-Schnittstelle übernommen.
- Gerätefunktionen werden später einzeln als versionierte Plugins oder Pakete angebunden. Es werden keine vollständigen
  Entwicklungsstände eines anderen Geräterepositories ungeprüft in den LED Core kopiert.
- Während einer direkten gemeinsamen Arbeit an demselben Stand wird vorher vereinbart, wer den Stand bearbeitet. Der
  andere Entwickler beginnt erst nach Commit und Aktualisierung des gemeinsamen Branches.

Dieser Export enthält ausschließlich den LED Core. Erweiterungen werden später nur über klar definierte, optionale
Schnittstellen angebunden und bleiben außerhalb dieses Repositories.
