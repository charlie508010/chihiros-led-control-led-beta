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

| # | Aktueller Mitschnitt | App-Log | Status |
| ---: | --- | --- | --- |
| 1 | `90|4|[1]` | `90|4|[1]` | OK |
| 2 | `90|9|[26,7,1,22,35,22]` | `90|9|[26,7,1,22,38,20]` | OK |
| 3 | `90|9|[26,7,1,22,35,22]` | `90|9|[26,7,1,22,38,20]` | OK |
| 4 | `165|25|[...]` | `165|25|[...]` | OK |

Frame `#4` enthält den vollständigen Scheduler-Payload. Die kompletten Bytes
stehen in den Rohdaten unten.

## Markierte Frames aus aktuellem Mitschnitt

```text
[INFO APP] {"time":"21.07.2026 00:35:22.533","dir":"tx","cmd":90,"mode":4,"parm":[1]}
[INFO APP] {"time":"21.07.2026 00:35:22.836","dir":"tx","cmd":90,"mode":9,"parm":[26,7,1,22,35,22]}
[INFO APP] {"time":"21.07.2026 00:35:22.938","dir":"tx","cmd":90,"mode":9,"parm":[26,7,1,22,35,22]}
[INFO APP] {"time":"21.07.2026 00:35:24.057","dir":"tx","cmd":165,"mode":25,"parm":[12,0,18,0,1,127,100,100,100,100,255,255,255,255]}
```

## App-Log Frames

```text
[INFO] {"dir":"tx","cmd":90,"mode":4,"parm":[1],"time":"20.07.2026 22:38:20"}
[INFO] {"dir":"tx","cmd":90,"mode":9,"parm":[26,7,1,22,38,20],"time":"20.07.2026 22:38:20"}
[INFO] {"dir":"tx","cmd":90,"mode":9,"parm":[26,7,1,22,38,20],"time":"20.07.2026 22:38:20"}
[INFO] {"dir":"tx","cmd":165,"mode":25,"parm":[12,0,18,0,1,127,100,100,100,100,255,255,255,255],"time":"20.07.2026 22:38:24"}
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
