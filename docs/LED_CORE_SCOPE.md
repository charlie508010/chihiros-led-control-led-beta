# Chihiros LED Core

Dieses Repository ist die getrennte Arbeitskopie für die LED-Steuerung.

## Aktiver Umfang

- LED-BLE-Verbindung und LED-Protokoll
- LED-Farbkanäle und Leistungsanzeige
- LED-Zeitpläne, Vorlagen und automatische Statusprüfung
- Home-Assistant-Integration und LED-Dashboard
- `chihirosctl led` und `chihirosctl template`

Die eigenständigen Bereiche für Doser, Rührer, Heizer, Wireshark und das allgemeine CTL-Dashboard sind nicht Bestandteil
des LED Core. Optionaler Gerätecode darf im selben Repository ausschließlich unter einem eigenen Pluginverzeichnis
liegen und wird vom LED Core nicht automatisch importiert oder registriert. Das gilt für Backend, Protokoll,
Home-Assistant-Services, Dashboard, CLI und Tests.

## Erweiterungen

Weitere Gerätearten werden später als getrennte Plugins oder Pakete angebunden. Sie sollen ihre eigenen Protokoll-,
Service-, UI- und Testmodule besitzen und die LED-Funktionen nicht verändern. Gemeinsame BLE-, Debug-, Speicher- und
Dialogfunktionen dürfen über klar definierte Core-Schnittstellen genutzt werden.

Vorgesehene Struktur:

```text
LED Core
├── gemeinsame BLE- und Debug-Schnittstellen
├── LED-Protokoll, Services, UI und Tests
└── plugins/
    ├── doser/ (eigenständig, vom LED Core nicht automatisch geladen)
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

Die Home-Assistant-Doser-Implementierung liegt vollständig unter `custom_components/chihiros/plugins/doser/` und wird
durch einen Architekturtest von den Core-Modulen getrennt gehalten. Historische Doser-, Rührer-, Heizer-, Wireshark-
und allgemeine CTL-Anteile in der gemeinsamen Python-Bibliothek, der CLI oder dem Frontend-Host sind weiterhin
Migrationsreste. Sie werden abhängigkeitsweise in eigene Plugins verschoben; bis dahin darf dieser Export nicht als
vollständig getrennt bezeichnet werden.
