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

# Wireshark Debug: Rot auf 100% manuell

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | Rot auf 100% manuell |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-21-06-20-43.frames.jsonl` |
| Aktueller Mitschnitt | 5 Frames |
| App-Log | 5 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,2,6,20,25]` | OK |
| 3 | `90` | `9` | `[26,7,2,6,20,25]` | OK |
| 4 | `90` | `5` | `[11,255,255]` | OK |
| 5 | `90` | `7` | `[0,100]` | OK |

Frame `#4` schaltet auf manuellen Modus. Frame `#5` setzt Kanal Rot auf `100`.

## Markierte Frames aus aktuellem Mitschnitt

```text
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 08:20:25.263"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 20, 25], "time": "21.07.2026 08:20:25.571"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 20, 25], "time": "21.07.2026 08:20:25.629"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [11, 255, 255], "time": "21.07.2026 08:20:27.748"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 7, "parm": [0, 100], "time": "21.07.2026 08:20:40.600"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 06:22:33"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 22, 33], "time": "21.07.2026 06:22:33"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 22, 33], "time": "21.07.2026 06:22:33"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [11, 255, 255], "time": "21.07.2026 06:22:33"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 7, "parm": [0, 100], "time": "21.07.2026 06:22:33"}
```

## Rohes Vergleichsergebnis

```text
VERGLEICH
Aktueller Mitschnitt: 5 Frames
App-Log: 5 Frames
#1
  Aktueller Mitschnitt  90|4|[1]
  Vergleich App-Log   : 90|4|[1] ok
#2
  Aktueller Mitschnitt  90|9|[26,7,2,6,20,25]
  Vergleich App-Log   : 90|9|[26,7,2,6,22,33] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,2,6,20,25]
  Vergleich App-Log   : 90|9|[26,7,2,6,22,33] ok
#4
  Aktueller Mitschnitt  90|5|[11,255,255]
  Vergleich App-Log   : 90|5|[11,255,255] ok
#5
  Aktueller Mitschnitt  90|7|[0,100]
  Vergleich App-Log   : 90|7|[0,100] ok
OK: Keine Unterschiede gefunden.
```

# Wireshark Debug: Grün auf 100% manuell

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | Grün auf 100% manuell |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-21-06-26-40.frames.jsonl` |
| Aktueller Mitschnitt | 5 Frames |
| App-Log | 5 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,2,6,26,27]` | OK |
| 3 | `90` | `9` | `[26,7,2,6,26,27]` | OK |
| 4 | `90` | `5` | `[11,255,255]` | OK |
| 5 | `90` | `7` | `[1,100]` | OK |

Frame `#4` schaltet auf manuellen Modus. Frame `#5` setzt Kanal Grün auf `100`.

## Markierte Frames aus aktuellem Mitschnitt

```text
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 08:26:27.168"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 26, 27], "time": "21.07.2026 08:26:27.473"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 26, 27], "time": "21.07.2026 08:26:27.542"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [11, 255, 255], "time": "21.07.2026 08:26:27.661"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 7, "parm": [1, 100], "time": "21.07.2026 08:26:36.224"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 06:28:01"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 28, 1], "time": "21.07.2026 06:28:01"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 28, 1], "time": "21.07.2026 06:28:01"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [11, 255, 255], "time": "21.07.2026 06:28:01"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 7, "parm": [1, 100], "time": "21.07.2026 06:28:01"}
```

## Rohes Vergleichsergebnis

```text
VERGLEICH
Aktueller Mitschnitt: 5 Frames
App-Log: 5 Frames
#1
  Aktueller Mitschnitt  90|4|[1]
  Vergleich App-Log   : 90|4|[1] ok
#2
  Aktueller Mitschnitt  90|9|[26,7,2,6,26,27]
  Vergleich App-Log   : 90|9|[26,7,2,6,28,1] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,2,6,26,27]
  Vergleich App-Log   : 90|9|[26,7,2,6,28,1] ok
#4
  Aktueller Mitschnitt  90|5|[11,255,255]
  Vergleich App-Log   : 90|5|[11,255,255] ok
#5
  Aktueller Mitschnitt  90|7|[1,100]
  Vergleich App-Log   : 90|7|[1,100] ok
OK: Keine Unterschiede gefunden.
```

# Wireshark Debug: Blau auf 100% manuell

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | Blau auf 100% manuell |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-21-06-32-43.frames.jsonl` |
| Aktueller Mitschnitt | 5 Frames |
| App-Log | 5 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,2,6,32,28]` | OK |
| 3 | `90` | `9` | `[26,7,2,6,32,28]` | OK |
| 4 | `90` | `5` | `[11,255,255]` | OK |
| 5 | `90` | `7` | `[2,100]` | OK |

Frame `#4` schaltet auf manuellen Modus. Frame `#5` setzt Kanal Blau auf `100`.

## Markierte Frames aus aktuellem Mitschnitt

```text
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 08:32:28.678"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 32, 28], "time": "21.07.2026 08:32:28.985"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 32, 28], "time": "21.07.2026 08:32:29.064"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [11, 255, 255], "time": "21.07.2026 08:32:29.185"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 7, "parm": [2, 100], "time": "21.07.2026 08:32:39.456"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 06:33:36"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 33, 36], "time": "21.07.2026 06:33:36"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 33, 36], "time": "21.07.2026 06:33:36"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [11, 255, 255], "time": "21.07.2026 06:33:36"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 7, "parm": [2, 100], "time": "21.07.2026 06:33:36"}
```

## Rohes Vergleichsergebnis

```text
VERGLEICH
Aktueller Mitschnitt: 5 Frames
App-Log: 5 Frames
#1
  Aktueller Mitschnitt  90|4|[1]
  Vergleich App-Log   : 90|4|[1] ok
#2
  Aktueller Mitschnitt  90|9|[26,7,2,6,32,28]
  Vergleich App-Log   : 90|9|[26,7,2,6,33,36] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,2,6,32,28]
  Vergleich App-Log   : 90|9|[26,7,2,6,33,36] ok
#4
  Aktueller Mitschnitt  90|5|[11,255,255]
  Vergleich App-Log   : 90|5|[11,255,255] ok
#5
  Aktueller Mitschnitt  90|7|[2,100]
  Vergleich App-Log   : 90|7|[2,100] ok
OK: Keine Unterschiede gefunden.
```

# Wireshark Debug: Auto-Modus aktivieren

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | Auto-Modus aktivieren |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-21-05-35-31.frames.jsonl` |
| Aktueller Mitschnitt | 7 Frames |
| App-Log | 7 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,2,5,35,14]` | OK |
| 3 | `90` | `9` | `[26,7,2,5,35,14]` | OK |
| 4 | `90` | `5` | `[18,255]` | OK |
| 5 | `90` | `5` | `[5,255,255]` | OK |
| 6 | `165` | `25` | `[9,0,17,0,1,127,5,5,5,5,255,255,255,255]` | OK |
| 7 | `165` | `25` | `[17,0,22,0,1,127,65,40,65,50,255,255,255,255]` | OK |

Die Frames `#6`, `#7` enthalten vollständige Scheduler-Payloads. Die kompletten Bytes
stehen in den Rohdaten unten.

## Markierte Frames aus aktuellem Mitschnitt

```text
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 07:35:14.130"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 5, 35, 14], "time": "21.07.2026 07:35:14.437"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 5, 35, 14], "time": "21.07.2026 07:35:14.503"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [18, 255], "time": "21.07.2026 07:35:31.100"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [5, 255, 255], "time": "21.07.2026 07:35:31.243"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [9, 0, 17, 0, 1, 127, 5, 5, 5, 5, 255, 255, 255, 255], "time": "21.07.2026 07:35:31.395"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [17, 0, 22, 0, 1, 127, 65, 40, 65, 50, 255, 255, 255, 255], "time": "21.07.2026 07:35:31.543"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 06:02:49"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 2, 49], "time": "21.07.2026 06:02:49"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 6, 2, 49], "time": "21.07.2026 06:02:49"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [18, 255], "time": "21.07.2026 06:02:49"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [5, 255, 255], "time": "21.07.2026 06:02:49"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [9, 0, 17, 0, 1, 127, 5, 5, 5, 5, 255, 255, 255, 255], "time": "21.07.2026 06:02:49"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [17, 0, 22, 0, 1, 127, 65, 40, 65, 50, 255, 255, 255, 255], "time": "21.07.2026 06:02:49"}
```

## Rohes Vergleichsergebnis

```text
VERGLEICH
Aktueller Mitschnitt: 7 Frames
App-Log: 7 Frames
#1
  Aktueller Mitschnitt  90|4|[1]
  Vergleich App-Log   : 90|4|[1] ok
#2
  Aktueller Mitschnitt  90|9|[26,7,2,5,35,14]
  Vergleich App-Log   : 90|9|[26,7,2,6,2,49] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,2,5,35,14]
  Vergleich App-Log   : 90|9|[26,7,2,6,2,49] ok
#4
  Aktueller Mitschnitt  90|5|[18,255]
  Vergleich App-Log   : 90|5|[18,255] ok
#5
  Aktueller Mitschnitt  90|5|[5,255,255]
  Vergleich App-Log   : 90|5|[5,255,255] ok
#6
  Aktueller Mitschnitt  165|25|[9,0,17,0,1,127,5,5,5,5,255,255,255,255]
  Vergleich App-Log   : 165|25|[9,0,17,0,1,127,5,5,5,5,255,255,255,255] ok
#7
  Aktueller Mitschnitt  165|25|[17,0,22,0,1,127,65,40,65,50,255,255,255,255]
  Vergleich App-Log   : 165|25|[17,0,22,0,1,127,65,40,65,50,255,255,255,255] ok
OK: Keine Unterschiede gefunden.
```

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

---

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

Die Frames `#4`, `#5`, `#6` enthalten vollständige Scheduler-Payloads. Die kompletten Bytes
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
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 02:05:14"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 2, 5, 14], "time": "21.07.2026 02:05:14"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 2, 5, 14], "time": "21.07.2026 02:05:14"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 02:05:17"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 02:05:17"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 02:05:17"}
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
  Vergleich App-Log   : 90|9|[26,7,2,2,5,14] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,2,1,54,19]
  Vergleich App-Log   : 90|9|[26,7,2,2,5,14] ok
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

---

# Wireshark Debug: edit scheduler zwei Mi So

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | edit scheduler zwei Mi So |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-21-02-15-06.frames.jsonl` |
| Aktueller Mitschnitt | 6 Frames |
| App-Log | 6 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,2,2,14,53]` | OK |
| 3 | `90` | `9` | `[26,7,2,2,14,53]` | OK |
| 4 | `165` | `25` | `[18,0,22,0,1,42,255,255,255,255,255,255,255,255]` | OK |
| 5 | `165` | `25` | `[18,0,22,0,1,42,255,255,255,255,255,255,255,255]` | OK |
| 6 | `165` | `25` | `[18,0,22,0,1,17,100,100,100,100,255,255,255,255]` | OK |

Die Frames `#4`, `#5`, `#6` enthalten vollständige Scheduler-Payloads. Die kompletten Bytes
stehen in den Rohdaten unten.

Bei Geräte-Datum/Zeit-Frames (`90|9`) werden nur Cmd, Mode und die ersten drei Parameterbytes
verglichen. Die Uhrzeitbytes dürfen zwischen App-Mitschnitt und Systemausgabe abweichen.

## Markierte Frames aus aktuellem Mitschnitt

```text
Aktueller Mitschnitt: btsnoop_hci_2026-07-21-02-15-06.frames.jsonl
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 04:14:53.073"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 2, 14, 53], "time": "21.07.2026 04:14:53.370"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 2, 14, 53], "time": "21.07.2026 04:14:53.445"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 04:14:54.886"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 04:15:03.818"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 17, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 04:15:04.735"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 02:37:39"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 2, 37, 39], "time": "21.07.2026 02:37:39"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 2, 37, 39], "time": "21.07.2026 02:37:39"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 02:37:42"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 42, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 02:37:42"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 17, 100, 100, 100, 100, 255, 255, 255, 255], "time": "21.07.2026 02:37:42"}
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
  Aktueller Mitschnitt  90|9|[26,7,2,2,14,53]
  Vergleich App-Log   : 90|9|[26,7,2,2,37,39] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,2,2,14,53]
  Vergleich App-Log   : 90|9|[26,7,2,2,37,39] ok
#4
  Aktueller Mitschnitt  165|25|[18,0,22,0,1,42,255,255,255,255,255,255,255,255]
  Vergleich App-Log   : 165|25|[18,0,22,0,1,42,255,255,255,255,255,255,255,255] ok
#5
  Aktueller Mitschnitt  165|25|[18,0,22,0,1,42,255,255,255,255,255,255,255,255]
  Vergleich App-Log   : 165|25|[18,0,22,0,1,42,255,255,255,255,255,255,255,255] ok
#6
  Aktueller Mitschnitt  165|25|[18,0,22,0,1,17,100,100,100,100,255,255,255,255]
  Vergleich App-Log   : 165|25|[18,0,22,0,1,17,100,100,100,100,255,255,255,255] ok
OK: Keine Unterschiede gefunden.
```

---
# Wireshark Debug: Delete Scheduler einen

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | Delete Scheduler einen |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-21-03-08-52.frames.jsonl` |
| Aktueller Mitschnitt | 4 Frames |
| App-Log | 4 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,2,3,8,41]` | OK |
| 3 | `90` | `9` | `[26,7,2,3,8,41]` | OK |
| 4 | `165` | `25` | `[12,0,18,0,1,84,255,255,255,255,255,255,255,255]` | OK |

Frame `#4` enthält den vollständigen Scheduler-Payload. Die kompletten Bytes
stehen in den Rohdaten unten.

## Markierte Frames aus aktuellem Mitschnitt

```text
Aktueller Mitschnitt: btsnoop_hci_2026-07-21-03-08-52.frames.jsonl
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 05:08:41.422"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 3, 8, 41], "time": "21.07.2026 05:08:41.734"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 3, 8, 41], "time": "21.07.2026 05:08:41.793"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 05:08:50.287"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 03:26:07"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 3, 26, 7], "time": "21.07.2026 03:26:07"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 3, 26, 7], "time": "21.07.2026 03:26:07"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [12, 0, 18, 0, 1, 84, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 03:26:11"}
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
  Aktueller Mitschnitt  90|9|[26,7,2,3,8,41]
  Vergleich App-Log   : 90|9|[26,7,2,3,26,7] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,2,3,8,41]
  Vergleich App-Log   : 90|9|[26,7,2,3,26,7] ok
#4
  Aktueller Mitschnitt  165|25|[12,0,18,0,1,84,255,255,255,255,255,255,255,255]
  Vergleich App-Log   : 165|25|[12,0,18,0,1,84,255,255,255,255,255,255,255,255] ok
OK: Keine Unterschiede gefunden.
```

---
# Wireshark Debug: Delete Scheduler letzten

## Übersicht

| Feld | Wert |
| --- | --- |
| Bezeichnung | Delete Scheduler letzten |
| Quelle | Wireshark Vergleich App-Log |
| Datei | `btsnoop_hci_2026-07-21-03-29-58.frames.jsonl` |
| Aktueller Mitschnitt | 5 Frames |
| App-Log | 5 Frames |
| Ergebnis | OK - keine Unterschiede gefunden |

## Vergleich

| # | Capture Cmd | Capture Mode | Capture Parameter | Status |
| ---: | ---: | ---: | --- | --- |
| 1 | `90` | `4` | `[1]` | OK |
| 2 | `90` | `9` | `[26,7,2,3,29,43]` | OK |
| 3 | `90` | `9` | `[26,7,2,3,29,43]` | OK |
| 4 | `165` | `25` | `[18,0,22,0,1,17,255,255,255,255,255,255,255,255]` | OK |
| 5 | `90` | `5` | `[40,255,255]` | OK |

Frame `#4` enthält den vollständigen Scheduler-Payload. Die kompletten Bytes
stehen in den Rohdaten unten.

## Markierte Frames aus aktuellem Mitschnitt

```text
Aktueller Mitschnitt: btsnoop_hci_2026-07-21-03-29-58.frames.jsonl
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 05:29:43.476"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 3, 29, 43], "time": "21.07.2026 05:29:43.783"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 3, 29, 43], "time": "21.07.2026 05:29:43.887"}
[INFO APP]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 17, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 05:29:49.447"}
[INFO APP]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [40, 255, 255], "time": "21.07.2026 05:29:49.585"}
```

## App-Log Frames

```text
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 4, "parm": [1], "time": "21.07.2026 04:18:11"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 4, 18, 11], "time": "21.07.2026 04:18:11"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 9, "parm": [26, 7, 2, 4, 18, 11], "time": "21.07.2026 04:18:11"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 165, "mode": 25, "parm": [18, 0, 22, 0, 1, 17, 255, 255, 255, 255, 255, 255, 255, 255], "time": "21.07.2026 04:18:14"}
[INFO SYSTEM]  {"dir": "tx", "cmd": 90, "mode": 5, "parm": [40, 255, 255], "time": "21.07.2026 04:18:14"}
```

## Rohes Vergleichsergebnis

```text
VERGLEICH
Aktueller Mitschnitt: 5 Frames
App-Log: 5 Frames
#1
  Aktueller Mitschnitt  90|4|[1]
  Vergleich App-Log   : 90|4|[1] ok
#2
  Aktueller Mitschnitt  90|9|[26,7,2,3,29,43]
  Vergleich App-Log   : 90|9|[26,7,2,4,18,11] ok
#3
  Aktueller Mitschnitt  90|9|[26,7,2,3,29,43]
  Vergleich App-Log   : 90|9|[26,7,2,4,18,11] ok
#4
  Aktueller Mitschnitt  165|25|[18,0,22,0,1,17,255,255,255,255,255,255,255,255]
  Vergleich App-Log   : 165|25|[18,0,22,0,1,17,255,255,255,255,255,255,255,255] ok
#5
  Aktueller Mitschnitt  90|5|[40,255,255]
  Vergleich App-Log   : 90|5|[40,255,255] ok
OK: Keine Unterschiede gefunden.
```

---
