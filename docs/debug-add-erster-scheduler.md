# Wireshark Debug: Add erster Scheduler

Dieses Beispiel dokumentiert einen Wireshark-Vergleich für das Hinzufügen des
ersten LED-Zeitplan-Eintrags. Verglichen werden vier markierte TX-Frames aus dem
aktuellen Mitschnitt mit den passenden Frames aus dem App-Log.

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | Add erster Scheduler |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-20-22-35-25.frames.jsonl` |
| Aktueller Mitschnitt | 4 Frames |
| App-Log | 4 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,1,22,35,22]` | OK |
| 3 | `90` | `9` | `[26,7,1,22,35,22]` | OK |
| 4 | `165` | `25` | `[12,0,18,0,1,127,100,100,100,100,255,255,255,255]` | OK |

Frame `#4` enthält den vollständigen Scheduler-Payload. Die kompletten Bytes
stehen in den Rohdaten unten.

## Markierte Frames aus aktuellem Mitschnitt

```text
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 00:35:22.533"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 1, 22, 35, 22], "time": "21.07.2026 00:35:22.836"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 1, 22, 35, 22], "time": "21.07.2026 00:35:22.938"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 127, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 00:35:24.057"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "20.07.2026 22:38:20"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 1, 22, 38, 20], "time": "20.07.2026 22:38:20"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 1, 22, 38, 20], "time": "20.07.2026 22:38:20"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 127, 100, 100, 100, 100, 255, 255, 255, 255], "time": "20.07.2026 22:38:24"}
```

## Rohes Vergleichsergebnis

```text
VERGLEICH
------------------------------------------------------------------------
Aktueller Mitschnitt: 4 Frames
App-Log: 4 Frames
------------------------------------------------------------------------
#1
  Aktueller Mitschnitt  90|4|[1]
  Vergleich App-Log   : 90|4|[1] ok
#2
  Aktueller Mitschnitt  90|9|[26,7,1,22,35,22]
  Vergleich App-Log   : 90|9|[26,7,1,22,38,20] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,1,22,35,22]
  Vergleich App-Log   : 90|9|[26,7,1,22,38,20] ok
#4
  Aktueller Mitschnitt  165|25|[12,0,18,0,1,127,100,100,100,100,255,255,255,255]
  Vergleich App-Log   : 165|25|[12,0,18,0,1,127,100,100,100,100,255,255,255,255] ok
OK: Keine Unterschiede gefunden.
------------------------------------------------------------------------
```

---

# Wireshark Debug: Edit erster Scheduler auf MO MI FR

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | Edit erster Scheduler auf MO MI FR |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-20-23-49-25.frames.jsonl` |
| Aktueller Mitschnitt | 8 Frames |
| App-Log | 8 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,1,23,49,7]` | OK |
| 3 | `90` | `9` | `[26,7,1,23,49,7]` | OK |
| 4 | `165` | `25` | `[12,0,18,0,1,84,255,255,255,255,255,255,255,255]` | OK |
| 5 | `90` | `5` | `[40,255,255]` | OK |
| 6 | `165` | `25` | `[12,0,18,0,1,84,255,255,255,255,255,255,255,255]` | OK |
| 7 | `90` | `5` | `[40,255,255]` | OK |
| 8 | `165` | `25` | `[12,0,18,0,1,84,100,100,100,100,255,255,255,255]` | OK |

Die Frames `#4`, `#6` und `#8` enthalten vollständige Scheduler-Payloads. Die kompletten Bytes
stehen in den Rohdaten unten.

Bei Geräte-Datum/Zeit-Frames (`90|9`) werden nur Cmd, Mode und die ersten drei Parameterbytes
verglichen. Die Uhrzeitbytes dürfen zwischen App-Mitschnitt und Systemausgabe abweichen.

## Markierte Frames aus aktuellem Mitschnitt

```text
Aktueller Mitschnitt: btsnoop_hci_2026-07-20-23-49-25.frames.jsonl
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 01:49:07.457"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 1, 23, 49, 7], "time": "21.07.2026 01:49:07.761"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 1, 23, 49, 7], "time": "21.07.2026 01:49:07.859"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 01:49:17.087"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [40, 255, 255], "time": "21.07.2026 01:49:17.282"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 01:49:21.465"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [40, 255, 255], "time": "21.07.2026 01:49:21.635"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 01:49:22.298"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 00:06:02"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 0, 6, 2], "time": "21.07.2026 00:06:02"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 0, 6, 2], "time": "21.07.2026 00:06:02"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 00:06:05"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [40, 255, 255], "time": "21.07.2026 00:06:05"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 00:06:05"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [40, 255, 255], "time": "21.07.2026 00:06:05"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 00:06:05"}
```

## Rohes Vergleichsergebnis

```text
VERGLEICH
Aktueller Mitschnitt: 8 Frames
App-Log: 8 Frames
#1
  Aktueller Mitschnitt  90|4|[1]
  Vergleich App-Log   : 90|4|[1] ok
#2
  Aktueller Mitschnitt  90|9|[26,7,1,23,49,7]
  Vergleich App-Log   : 90|9|[26,7,2,0,6,2] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,1,23,49,7]
  Vergleich App-Log   : 90|9|[26,7,2,0,6,2] ok
#4
  Aktueller Mitschnitt  165|25|[12,0,18,0,1,84,255,255,255,255,255,255,255,255]
  Vergleich App-Log   : 165|25|[12,0,18,0,1,84,255,255,255,255,255,255,255,255] ok
#5
  Aktueller Mitschnitt  90|5|[40,255,255]
  Vergleich App-Log   : 90|5|[40,255,255] ok
#6
  Aktueller Mitschnitt  165|25|[12,0,18,0,1,84,255,255,255,255,255,255,255,255]
  Vergleich App-Log   : 165|25|[12,0,18,0,1,84,255,255,255,255,255,255,255,255] ok
#7
  Aktueller Mitschnitt  90|5|[40,255,255]
  Vergleich App-Log   : 90|5|[40,255,255] ok
#8
  Aktueller Mitschnitt  165|25|[12,0,18,0,1,84,100,100,100,100,255,255,255,255]
  Vergleich App-Log   : 165|25|[12,0,18,0,1,84,100,100,100,100,255,255,255,255] ok
OK: Keine Unterschiede gefunden.
```

---

# Wireshark Debug: zweiter Scheduler add

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | zweiter Scheduler add |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-21-01-54-30.frames.jsonl` |
| Aktueller Mitschnitt | 6 Frames |
| App-Log | 6 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,2,1,54,19]` | OK |
| 3 | `90` | `9` | `[26,7,2,1,54,19]` | OK |
| 4 | `165` | `25` | `[18,0,22,0,1,42,255,255,255,255,255,255,255,255]` | OK |
| 5 | `165` | `25` | `[18,0,22,0,1,42,255,255,255,255,255,255,255,255]` | OK |
| 6 | `165` | `25` | `[18,0,22,0,1,42,100,100,100,100,255,255,255,255]` | OK |

Die Frames `#4`, `#5` und `#6` enthalten vollständige Scheduler-Payloads. Die kompletten Bytes
stehen in den Rohdaten unten.

Bei Geräte-Datum/Zeit-Frames (`90|9`) werden nur Cmd, Mode und die ersten drei Parameterbytes
verglichen. Die Uhrzeitbytes dürfen zwischen App-Mitschnitt und Systemausgabe abweichen.

## Markierte Frames aus aktuellem Mitschnitt

```text
Aktueller Mitschnitt: btsnoop_hci_2026-07-21-01-54-30.frames.jsonl
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 03:54:19.049"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 1, 54, 19], "time": "21.07.2026 03:54:19.353"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 1, 54, 19], "time": "21.07.2026 03:54:19.430"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 03:54:22.984"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 03:54:26.840"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 03:54:29.735"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 01:54:19"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 1, 54, 19], "time": "21.07.2026 01:54:19"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 1, 54, 19], "time": "21.07.2026 01:54:19"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 01:54:23"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 01:54:27"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 01:54:30"}
```

## Rohes Vergleichsergebnis

```text
VERGLEICH
Aktueller Mitschnitt: 6 Frames
App-Log: 6 Frames
#1
  Aktueller Mitschnitt  90|4|[1]
  Vergleich App-Log   : 90|4|[1] ok
#2
  Aktueller Mitschnitt  90|9|[26,7,2,1,54,19]
  Vergleich App-Log   : 90|9|[26,7,2,1,54,19] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,2,1,54,19]
  Vergleich App-Log   : 90|9|[26,7,2,1,54,19] ok
#4
  Aktueller Mitschnitt  165|25|[18,0,22,0,1,42,255,255,255,255,255,255,255,255]
  Vergleich App-Log   : 165|25|[18,0,22,0,1,42,255,255,255,255,255,255,255,255] ok
#5
  Aktueller Mitschnitt  165|25|[18,0,22,0,1,42,255,255,255,255,255,255,255,255]
  Vergleich App-Log   : 165|25|[18,0,22,0,1,42,255,255,255,255,255,255,255,255] ok
#6
  Aktueller Mitschnitt  165|25|[18,0,22,0,1,42,100,100,100,100,255,255,255,255]
  Vergleich App-Log   : 165|25|[18,0,22,0,1,42,100,100,100,100,255,255,255,255] ok
OK: Keine Unterschiede gefunden.
```

---
# Wireshark Debug: Erster Scheduler aktiv

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | Erster Scheduler aktiv |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-21-01-38-10.frames.jsonl` |
| Aktueller Mitschnitt | 4 Frames |
| App-Log | 4 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,2,1,37,54]` | OK |
| 3 | `90` | `9` | `[26,7,2,1,37,54]` | OK |
| 4 | `165` | `25` | `[12,0,18,0,1,84,100,100,100,100,255,255,255,255]` | OK |

Frame `#4` enthält den vollständigen Scheduler-Payload. Die kompletten Bytes stehen in den Rohdaten unten.

Bei Geräte-Datum/Zeit-Frames (`90|9`) werden nur Cmd, Mode und die ersten drei Parameterbytes
verglichen. Die Uhrzeitbytes dürfen zwischen App-Mitschnitt und Systemausgabe abweichen.

## Markierte Frames aus aktuellem Mitschnitt

```text
Aktueller Mitschnitt: btsnoop_hci_2026-07-21-01-38-10.frames.jsonl
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 03:37:54.358"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 1, 37, 54], "time": "21.07.2026 03:37:54.659"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 1, 37, 54], "time": "21.07.2026 03:37:54.737"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 03:37:55.834"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 01:43:37"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 1, 43, 37], "time": "21.07.2026 01:43:37"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 1, 43, 37], "time": "21.07.2026 01:43:37"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 01:43:40"}
```

## Rohes Vergleichsergebnis

```text
VERGLEICH
Aktueller Mitschnitt: 4 Frames
App-Log: 4 Frames
#1
  Aktueller Mitschnitt  90|4|[1]
  Vergleich App-Log   : 90|4|[1] ok
#2
  Aktueller Mitschnitt  90|9|[26,7,2,1,37,54]
  Vergleich App-Log   : 90|9|[26,7,2,1,43,37] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,2,1,37,54]
  Vergleich App-Log   : 90|9|[26,7,2,1,43,37] ok
#4
  Aktueller Mitschnitt  165|25|[12,0,18,0,1,84,100,100,100,100,255,255,255,255]
  Vergleich App-Log   : 165|25|[12,0,18,0,1,84,100,100,100,100,255,255,255,255] ok
OK: Keine Unterschiede gefunden.
```

---

# Wireshark Debug: Erster Scheduler Inaktiv

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | Erster Scheduler Inaktiv |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-20-23-49-25.frames.jsonl` |
| Aktueller Mitschnitt | 8 Frames |
| App-Log | 8 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,1,23,49,7]` | OK |
| 3 | `90` | `9` | `[26,7,1,23,49,7]` | OK |
| 4 | `165` | `25` | `[12,0,18,0,1,84,255,255,255,255,255,255,255,255]` | OK |
| 5 | `90` | `5` | `[40,255,255]` | OK |
| 6 | `165` | `25` | `[12,0,18,0,1,84,255,255,255,255,255,255,255,255]` | OK |
| 7 | `90` | `5` | `[40,255,255]` | OK |
| 8 | `165` | `25` | `[12,0,18,0,1,84,100,100,100,100,255,255,255,255]` | OK |

Die Frames `#4`, `#6` und `#8` enthalten vollständige Scheduler-Payloads. Die kompletten Bytes
stehen in den Rohdaten unten.

Bei Geräte-Datum/Zeit-Frames (`90|9`) werden nur Cmd, Mode und die ersten drei Parameterbytes
verglichen. Die Uhrzeitbytes dürfen zwischen App-Mitschnitt und Systemausgabe abweichen.

## Markierte Frames aus aktuellem Mitschnitt

```text
Aktueller Mitschnitt: btsnoop_hci_2026-07-20-23-49-25.frames.jsonl
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 01:49:07.457"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 1, 23, 49, 7], "time": "21.07.2026 01:49:07.761"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 1, 23, 49, 7], "time": "21.07.2026 01:49:07.859"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 01:49:17.087"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [40, 255, 255], "time": "21.07.2026 01:49:17.282"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 01:49:21.465"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [40, 255, 255], "time": "21.07.2026 01:49:21.635"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 01:49:22.298"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 01:22:03"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 1, 22, 3], "time": "21.07.2026 01:22:03"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 1, 22, 3], "time": "21.07.2026 01:22:03"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 01:22:06"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [40, 255, 255], "time": "21.07.2026 01:22:06"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 01:22:06"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [40, 255, 255], "time": "21.07.2026 01:22:06"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 01:22:06"}
```

## Rohes Vergleichsergebnis

```text
VERGLEICH
Aktueller Mitschnitt: 8 Frames
App-Log: 8 Frames
#1
  Aktueller Mitschnitt  90|4|[1]
  Vergleich App-Log   : 90|4|[1] ok
#2
  Aktueller Mitschnitt  90|9|[26,7,1,23,49,7]
  Vergleich App-Log   : 90|9|[26,7,2,1,22,3] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,1,23,49,7]
  Vergleich App-Log   : 90|9|[26,7,2,1,22,3] ok
#4
  Aktueller Mitschnitt  165|25|[12,0,18,0,1,84,255,255,255,255,255,255,255,255]
  Vergleich App-Log   : 165|25|[12,0,18,0,1,84,255,255,255,255,255,255,255,255] ok
#5
  Aktueller Mitschnitt  90|5|[40,255,255]
  Vergleich App-Log   : 90|5|[40,255,255] ok
#6
  Aktueller Mitschnitt  165|25|[12,0,18,0,1,84,255,255,255,255,255,255,255,255]
  Vergleich App-Log   : 165|25|[12,0,18,0,1,84,255,255,255,255,255,255,255,255] ok
#7
  Aktueller Mitschnitt  90|5|[40,255,255]
  Vergleich App-Log   : 90|5|[40,255,255] ok
#8
  Aktueller Mitschnitt  165|25|[12,0,18,0,1,84,100,100,100,100,255,255,255,255]
  Vergleich App-Log   : 165|25|[12,0,18,0,1,84,100,100,100,100,255,255,255,255] ok
OK: Keine Unterschiede gefunden.
```
