# ESPHome Chihiros LED Protocol Findings

Diese Hinweise stammen aus dem externen Projekt `BartdeJonge/chihiros-esphome`. Sie dienen nur als zusätzliche
Referenz. Nicht durch eigene Mitschnitte bestätigtes Verhalten bleibt vorläufig.

## Transport

Die LED-Steuerung verwendet Nordic UART über BLE.

| Rolle | UUID |
| --- | --- |
| Service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` |
| Schreiben/RX | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` |
| Notify/TX | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` |

## Frame-Format

```text
[header] [0x01] [len] [0x00] [seq] [cmd] [data...] [xor]
```

Die Prüfsumme ist das XOR aller Bytes nach dem Header und vor der Prüfsumme. Die Sequenz beginnt bei `1` und
überspringt den reservierten Wert `0x5a`.

## Bestätigte LED-Befehle

| Befehl | Parameter | Bedeutung |
| --- | --- | --- |
| `0x5a / 0x04` | `[0x01]` | Authentifizierung und Statusabfrage |
| `0x5a / 0x09` | `[yy, month, weekday, hour, minute, second]` | Gerätezeit setzen |
| `0x5a / 0x05` | `[mode, 0xff, 0xff]` | Moduswechsel |
| `0x5a / 0x07` | `[channel, brightness]` | Manuelle Kanalhelligkeit |
| `0xa5 / 0x19` | Zeit, Rampe, Wochentage und Kanalwerte | LED-Zeitplan |

Der beobachtete WRGB-Zeitplan verwendet:

```text
a5 / 19 [
  on_h, on_m,
  off_h, off_m,
  ramp_min,
  weekdays,
  red, green, blue,
  ff, ff, ff, ff, ff
]
```

Die Wochentagsmaske lautet Montag `64`, Dienstag `32`, Mittwoch `16`, Donnerstag `8`, Freitag `4`, Samstag `2`,
Sonntag `1` und täglich `127`. Die Rampe `90` (`0x5a`) muss wegen des reservierten Bytes vermieden werden.

Eigene Geräte-Mitschnitte und die dokumentierten Abläufe in [`protocol.md`](protocol.md) haben Vorrang.
