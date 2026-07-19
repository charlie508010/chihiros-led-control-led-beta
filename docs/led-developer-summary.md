# LED-Entwicklerübersicht

Diese Datei beschreibt den aktuellen Stand des LED-Bereichs für die weitere
Entwicklung. Details zu einzelnen Bytes und beobachteten App-Sequenzen stehen
in [`protocol.md`](protocol.md).

## Abgrenzung

- LED und die allgemeine Konfiguration gehören fest zum Chihiros Core.
- Andere Gerätearten und Diagnosewerkzeuge werden getrennt entwickelt. Neue
  LED-Funktionen dürfen keine Abhängigkeit zu externem Erweiterungscode erzeugen.
- `src/chihiros_led_control/` ist die Quelle der gemeinsam genutzten
  Bibliothek. Die Kopie unter `custom_components/chihiros/vendor/` wird nur
  über `scripts/sync_vendor.py` aktualisiert.

## Datenfluss

### Befehl an ein Gerät

1. Das LED-Dashboard ruft einen Service unter `chihiros_led_core.*` auf.
2. `custom_components/chihiros/packages/led/services.py` löst das Ziel über
   `entry_id`, `entity_id` oder MAC-Adresse auf und validiert Modell und Werte.
3. Der Service ruft den geladenen `ChihirosDevice` aus der Config-Entry-Runtime
   auf.
4. `src/chihiros_led_control/client.py` baut die modellabhängige Operation auf.
5. `src/chihiros_led_control/commands.py` kodiert die BLE-Frames.
6. Der Client sendet die Frames und sammelt Notifications für Coordinator,
   Sensoren und Debug-Ausgabe.

Ein Dashboard-Gerät ist deshalb nicht automatisch ein sendefähiges Gerät. Zum
Senden muss ein geladener Home-Assistant-Config-Entry vorhanden sein. Eine
erkannte MAC-Adresse oder eine alte, aktuell nicht verfügbare Entity genügt
nicht.

### Rückmeldung vom Gerät

1. Der Client dekodiert eingehende `0x5B`-Notifications.
2. `coordinator.py` übernimmt Laufzeit, Firmware, Zeitplanpunkte und Rohdaten.
3. `sensor.py` stellt daraus Firmware-, Laufzeit-, Zeitplan- und
   Last-Notification-Entities bereit.
4. Das Dashboard zeigt Verbindungsdaten, letzte Meldungen und den Abgleich der
   gespeicherten Zeitpläne mit dem Gerätesnapshot an.

## Wichtige Dateien

| Bereich | Datei |
| --- | --- |
| Modell- und Kanaldefinitionen | `src/chihiros_led_control/models.py` |
| BLE-Ablauf und LED-Operationen | `src/chihiros_led_control/client.py` |
| Frame-Erzeugung | `src/chihiros_led_control/commands.py` |
| Frame-Dekodierung | `src/chihiros_led_control/protocol.py` |
| Config-Entry und Hintergrundabfrage | `custom_components/chihiros/__init__.py` |
| Notification-Zustand | `custom_components/chihiros/coordinator.py` |
| Home-Assistant-Sensoren | `custom_components/chihiros/sensor.py` |
| LED-Service-Handler | `custom_components/chihiros/packages/led/services.py` |
| Service-Schemas | `custom_components/chihiros/packages/led/const.py` |
| Zeitplan-Datenbank | `custom_components/chihiros/packages/led/storage.py` |
| LED-Dashboard | `custom_components/chihiros/www/panels/chihiros-led-panel.js` |
| Service-Metadaten | `custom_components/chihiros/services.yaml` |

## Modelle, Kanäle und Helligkeit

Kanalzahl, Kanal-IDs und Maximalwert müssen immer aus `DeviceModel` kommen.
Diese Werte dürfen weder im Backend noch im Dashboard pauschal als vier Kanäle
oder 100 Prozent angenommen werden.

Wichtiger Sonderfall:

- `DYU1000`: WRGB, vier Kanäle, Maximalwert `100`.
- Andere Universal-WRGB-Modelle sind aktuell WRGB mit Maximalwert `100`, bis
  ein Gerätetest einen anderen Wert bestätigt.

`set_brightness()` akzeptiert einen Einzelwert, eine Sequenz oder eine
Zuordnung aus Kanalname/Kanal-ID und Wert. Nicht gesetzte Kanäle dürfen bei
Zeitplanbefehlen als `255` übertragen werden, sofern das Protokoll dies für den
jeweiligen Befehl vorsieht.

## Home-Assistant-Services

Der LED-Bereich registriert derzeit:

| Service | Zweck |
| --- | --- |
| `chihiros_led_core.set_brightness` | Einen oder mehrere Farbkanäle manuell setzen |
| `chihiros_led_core.add_schedule` | Einen Zeitplan hinzufügen oder ersetzen |
| `chihiros_led_core.remove_schedule` | Einen bestimmten Zeitplan entfernen |
| `chihiros_led_core.reset_schedule` | Alle Zeitpläne auf dem Gerät zurücksetzen |
| `chihiros_led_core.set_schedule` | Eine vollständige Liste lokal speichern und optional senden |

Die Zielauflösung sollte bevorzugt mit `entry_id` oder einer zu einem geladenen
Entry gehörenden `entity_id` erfolgen. Die MAC-Adresse bleibt ein Fallback. Bei
Debug-Aufrufen liefern die Services strukturierte Antworten mit Request,
Zusammenfassung, TX/RX-Daten und Fehlerart.

## Relevante Protokollabläufe

- Manuelle Helligkeit: `0x5A`, Mode `0x07`, Parameter
  `[channel_id, brightness]`.
- Manuellen Farbmodus anwenden: `0x5A`, Mode `0x05`.
- Gerätezeit setzen: `0x5A`, Mode `0x09`; die beobachtete App sendet diesen
  Befehl bei vielen Abläufen zweimal.
- Zeitplan schreiben: `0xA5`, Mode `0x19` (`25`).
  Beim Anlegen wird kein implizites `0x5A`, Mode `0x05`,
  `[18, 255, 255]` gesendet. Das gilt auch für Bearbeiten und vollständiges
  Ersetzen. Vollständiges Schreiben sendet ebenfalls keinen Reset-Finalizer
  `[40, 255, 255]`. Der Auto-Modus ist eine separate Aktion.
- Auto-Modus aktivieren: `[18, 255, 255]`, danach `[5, 255, 255]` und
  anschließend alle aktiven, für das Gerät gespeicherten Zeitpläne. Ohne
  gespeicherte Zeitpläne endet der Ablauf nach `[5, 255, 255]`.
  Dashboard und Home-Assistant-Switch verwenden dafür dieselbe zentrale
  Implementierung. Der Dashboard-Aufruf `chihiros_led_core.enable_auto_mode` liefert
  bei aktiviertem Config-Debug die vollständige TX/RX-Ausgabe zurück.
- Zeitplanspeicher löschen: Beim bestätigten Modell `DYU1000` zuerst jeden
  gemeldeten Zeitplan mit `0xA5`, Mode `0x19` und `255` je Kanal löschen.
  Danach schließt `[40, 255, 255]` über `0x5A`, Mode `0x05` den Ablauf ab.
  Vor diesem Finalizer wird der Gerätesnapshot erneut gelesen. `40` wird nur
  gesendet, wenn die frische Antwort keine Zeitplanpunkte mehr enthält.
  Die Auswahl kommt aus `DeviceModel.schedule_reset_parameter` und
  `DeviceModel.schedule_reset_from_snapshot`. Werte wie `4`, `6` und `7`
  sind dynamische Speicheraktionen und kein globaler Modell-Reset.
- Laufzeit/Firmware: Antwort `0x5B`, Mode `0x0A`.
- Zeitplansnapshot: Antwort `0x5B`, Mode `0xFE`.

Die vollständigen Sequenzen, Parameterfelder und Beispiele stehen in
[`protocol.md`](protocol.md). Beobachtete App-Sequenzen haben Vorrang vor
Vermutungen aus einzelnen Frames.

## Zeitpläne

Die lokale Soll-Konfiguration liegt in der SQLite-Tabelle `led_schedules`.
Gespeichert werden unter anderem Gerät, Index, Start, Ende, Kanalwerte, Rampe,
Wochentage, Aktivstatus, Sendestatus und Änderungszeit.

Wichtige Regeln:

- `set_schedule` ersetzt die vollständige aktive Gerätekonfiguration.
- Bearbeiten verwendet die beobachtete Sequenz Auto-Modus, alten Eintrag
  löschen, neuen Eintrag schreiben.
- Löschen muss Kanalzahl, Zeit, Rampe und Wochentage des ursprünglichen Eintrags
  berücksichtigen.
- Ein konfigurierter Rampenwert von `0` wird im Geräteprotokoll mindestens als
  eine Minute dargestellt. Beim Abgleich gelten diese beiden Werte als
  äquivalent.
- Der Snapshot enthält Kurvenpunkte, keine vollständigen lokalen Datensätze.
  Start, Ende und Rampe werden aus den Punkten rekonstruiert.
- Der bisher dekodierte Snapshot liefert nur einen Helligkeitswert pro
  Zeitfenster. Einzelne WRGB-Werte und Wochentage können damit nicht sicher
  bestätigt werden.

Die Spalte `OK` im Dashboard zeigt daher einen bestmöglichen Geräteabgleich,
keine vollständige Byte-für-Byte-Bestätigung aller lokalen Felder.

## Automatische Statusabfrage

Für jeden geladenen LED-Config-Entry läuft eine aktive Abfrage:

- sofort beim Start des Entries;
- danach alle 15 Minuten;
- mit sauberer Abmeldung beim Entladen des Entries.

Sie sendet `5A 01 06 00 <msg-id> 04 01 <checksum>` und wartet standardmäßig drei
Sekunden auf Antworten. Erwartet werden insbesondere Laufzeit/Firmware und der
Zeitplansnapshot. Der aktuelle Stand ist über die Runtime-, Schedule- und
Last-Notification-Sensoren sowie im Verbindungsbereich des Dashboards sichtbar.
Jeder Abruf erzeugt zusätzlich genau einen Eintrag in der LED-Gesamthistorie.
Der Eintrag ist nur dann `OK`, wenn mindestens eine neue Geräteantwort erkannt
wurde; fehlende Antworten und BLE-Fehler werden als `FAIL` protokolliert.
Eine gemeinsame Sperre serialisiert die Abfragen aller LED-Entries und hält
zwischen zwei Geräten mindestens fünf Sekunden Abstand.
Die genaue Dekodierung ist im Abschnitt
„Home-Assistant-Hintergrunddienst für LED-Notifications“ in
[`protocol.md`](protocol.md) beschrieben.

## Dashboard

Das LED-Dashboard enthält aktuell:

- modellabhängige Farbkanäle mit Toggle, Slider, Zahlenfeld und Historie;
- Zeitplanliste mit Geräteabgleich, Anlegen, Bearbeiten, Aktivieren, Löschen,
  Teilen und vollständigem Reset;
- Standard- und lokale Vorlagen, einschließlich Teilen zwischen Geräten mit
  gleicher Kanalzahl;
- Gesamthistorie;
- Verbindung mit Modell, Kanälen, MAC, Online-Status, Laufzeit, letzter
  Notification und Firmware;
- Steuerung für die komplette Lampe und Anzeige des Auto-Modus;
- modellabhängige Helligkeitsvoreinstellungen.

Sprache und Debug-Verhalten werden aus der Core-Konfiguration übernommen. Neue
sichtbare Texte müssen in Deutsch und Englisch vorhanden sein. Deutsche Texte
sollen echte Umlaute verwenden.

## Bekannte Grenzen

- Bluetooth kann nur von einem aktiven Client zuverlässig belegt werden. Ist
  die Lampe mit einem anderen Telefon verbunden, muss das Dashboard einen
  verständlichen Verbindungshinweis statt eines internen Config-Entry-Fehlers
  zeigen.
- `Online` bedeutet, dass ein nutzbarer Home-Assistant-Zustand oder eine
  aktuelle Rückmeldung vorhanden ist. Es ist keine dauerhafte BLE-Verbindung.
- Zeitplanverifikation ist wegen des kompakten Snapshot-Formats nur teilweise
  möglich.
- Neue Geräte dürfen erst nach geprüftem Kanal-Mapping und geprüftem
  Maximalwert in `models.py` spezialisiert werden.

## Prüfungen vor einer Übergabe

```bash
uv --cache-dir .uv-cache run python scripts/sync_vendor.py
uv --cache-dir .uv-cache run python scripts/sync_vendor.py --check
uv --cache-dir .uv-cache run --group dev pytest
uv --cache-dir .uv-cache run --group dev pre-commit run --all-files
```

Mindestens manuell prüfen:

1. Kanal ein/aus, Slider und Zahlenfeld für jedes unterstützte Kanal-Mapping.
2. Vollständige Lampe ein/aus und Rückkehr zum Auto-Modus.
3. Zeitplan anlegen, bearbeiten, deaktivieren, aktivieren, teilen und löschen.
4. Zeitplan mit `0`, `1` und `30` Minuten Rampe gegen den Gerätesnapshot.
5. Neustart: lokale Daten, Hinweise und letzter Geräteabgleich bleiben korrekt.
6. Zwei LED-Geräte mit unterschiedlicher MAC und unabhängigem Snapshot.
7. DYU1000 mit vier Kanälen und Werten bis `100`.
8. Fehlerfall mit durch ein anderes Gerät belegter Bluetooth-Verbindung.
