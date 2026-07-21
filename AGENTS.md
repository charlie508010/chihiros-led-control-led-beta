# Repository Guidelines

## Project Structure & Module Organization

This repository contains a Python library/CLI and a Home Assistant custom integration for controlling Chihiros LEDs over Bluetooth LE.

- `src/chihiros_led_control/`: reusable library code and the `chihirosctl` Typer CLI.
- `custom_components/chihiros/`: Home Assistant integration files, translations, and manifest.
- `custom_components/chihiros/vendor/`: vendored copy of the library used by HACS installs.
- `tests/`: pytest tests for protocol encoding, factory behavior, weekday encoding, and vendor sync.
- `scripts/sync_vendor.py`: copies package code into the integration vendor directory.
- `docs/`: architecture and local Home Assistant Docker setup notes.
- `dev/homeassistant/`: local Home Assistant configuration used with Docker Compose.

## Build, Test, and Development Commands

- Always pass `--cache-dir .uv-cache` to `uv` commands so dependency/cache writes stay inside the repo.
- `uv --cache-dir .uv-cache sync --group dev`: install development dependencies.
- `uv --cache-dir .uv-cache run --group dev pytest`: run the test suite.
- `uv --cache-dir .uv-cache run --group dev pre-commit run --all-files`: run formatting, linting, doc, YAML/TOML, and AST checks.
- `uv --cache-dir .uv-cache run chihirosctl --help`: inspect CLI commands after syncing dependencies.
- `uv --cache-dir .uv-cache run python scripts/sync_vendor.py`: refresh `custom_components/chihiros/vendor/` after library changes.
- `uv --cache-dir .uv-cache run python scripts/sync_vendor.py --check`: verify the vendored copy is current.
- `docker compose up`: start the local Home Assistant environment; see `docs/home-assistant-docker.md`.
- When checking JavaScript syntax from WSL, use the installed Windows Node binary: `"/mnt/c/Program Files/nodejs/node.exe" --check <file>`.

## Coding Style & Naming Conventions

Target Python 3.13. Use 4-space indentation, type hints for public APIs, and descriptive snake_case names for modules, functions, and variables. Classes should use PascalCase; constants should use UPPER_SNAKE_CASE.

Ruff is the formatter and linter. The configured line length is 120 characters, and lint rules include docstrings, pycodestyle, pyflakes, imports, and warnings. The vendored integration copy is excluded from Ruff checks; edit `src/chihiros_led_control/` first, then sync vendor code.

## Testing Guidelines

Tests use pytest and live in `tests/` with `test_*.py` names. Prefer focused unit tests for command encoding, protocol behavior, model/factory changes, and Home Assistant-facing compatibility. When changing vendored behavior, run both `pytest` and `scripts/sync_vendor.py --check`.

## Commit & Pull Request Guidelines

Git history uses short imperative subjects, with occasional Conventional Commit prefixes such as `fix:`. Keep commits focused, for example `fix: relax bleak version pin` or `add model code for wrgb2 slim`.

Pull requests should describe the user-visible change, list validation commands run, link related issues, and include screenshots only for Home Assistant UI changes. If library code changes, mention whether the vendored copy was refreshed.

## Security & Configuration Tips

Do not commit Bluetooth device addresses, Home Assistant secrets, tokens, or local `.venv` contents. Keep dependency changes in `pyproject.toml` and `uv.lock` together.

# Projektweite Sicherheits- und Arbeitsregeln für Codex

Diese Regeln gelten für alle Aufgaben in diesem Projekt und dürfen niemals eigenständig geändert, ignoriert oder umgangen werden.

## Grundsatz

Arbeite präzise und möglichst mit minimalen Änderungen. Ändere nur das, was für die aktuelle Aufgabe notwendig ist. Der Schutz vorhandener Daten und Funktionen hat immer höchste Priorität.

## 1. Arbeitsbereich

- Arbeite ausschließlich innerhalb des aktuell freigegebenen Git-Repositories bzw. Arbeitsordners.
- Außerhalb dieses Arbeitsbereichs sind keinerlei Lese-, Schreib-, Änderungs-, Verschiebe-, Umbenennungs- oder Löschzugriffe erlaubt.
- Dies gilt ebenfalls für:
  - übergeordnete Verzeichnisse
  - andere Laufwerke
  - symbolische Links
  - gemountete Verzeichnisse
  - absolute Pfade

## 2. Backup-Pflicht

Vor jeder Änderung an einer Datei muss automatisch ein Backup erstellt werden.

Das Backup muss:
- erfolgreich erstellt werden,
- vor der eigentlichen Änderung existieren,
- innerhalb des Projekts in einem Backup-Ordner gespeichert werden,
- Datum und Uhrzeit im Dateinamen enthalten.

Kann kein Backup erstellt werden, dürfen keine Änderungen erfolgen.

## 3. Nur notwendige Änderungen

- Ändere ausschließlich Dateien, die unmittelbar zur aktuellen Aufgabe gehören.
- Suche nicht eigenständig nach weiteren Dateien, die deiner Meinung nach ebenfalls geändert werden sollten.
- Keine repositoryweiten Änderungen.
- Keine automatischen Refactorings.
- Keine automatischen Formatierungen.
- Keine Umbenennungen.
- Keine Aufräumarbeiten.
- Keine Optimierungen außerhalb der eigentlichen Aufgabe.
- Keine Änderungen an Dateien, die nicht ausdrücklich zur Aufgabe gehören.

## 4. Automatische Änderungen

Normale Änderungen innerhalb des aktuellen Git-Repositories dürfen ohne Rückfrage durchgeführt werden.

Eine Rückfrage ist nicht erforderlich, solange:
- ausschließlich Dateien innerhalb des aktuellen Projekts geändert werden,
- keine Daten gelöscht werden,
- keine gefährlichen Git-Operationen ausgeführt werden,
- keine Systembereiche betroffen sind.

## 5. Löschschutz

Ohne meine ausdrückliche Zustimmung ist verboten:
- Dateien löschen
- Ordner löschen
- Quellcode entfernen
- Funktionen entfernen
- Konfigurationen entfernen
- Dokumentationen entfernen
- Assets entfernen
- Datenbanken löschen oder leeren

Dies gilt ebenfalls für indirekte Löschungen über:
- rm
- rmdir
- del
- git clean
- git reset --hard
- git restore
- git checkout
- Überschreiben mit leerem Inhalt
- automatische Bereinigungen
- rekursive Löschbefehle

## 6. Git-Regeln

Ohne ausdrückliche Freigabe dürfen niemals ausgeführt werden:
- git reset
- git clean
- git rebase
- git merge
- git cherry-pick
- git stash
- git switch
- git checkout auf andere Branches
- Branch löschen
- Branch erstellen
- Force Push
- History umschreiben
- Tags ändern
- Commits erstellen

## 7. Datenbanken und Systemschutz

Ohne ausdrückliche Zustimmung dürfen niemals:
- Datenbanken geändert werden
- Tabellen gelöscht werden
- DELETE
- DROP
- TRUNCATE
- Docker-Volumes geändert werden
- Home-Assistant-Daten verändert werden
- Systemdateien verändert werden

## 8. Transparenz

Vor Beginn kurz anzeigen:
- welche Dateien geändert werden,
- welche Backups erstellt werden.

Nach Abschluss anzeigen:
- welche Dateien geändert wurden,
- wo die Backups liegen,
- dass keine Daten gelöscht wurden,
- dass ausschließlich innerhalb des Git-Repositories gearbeitet wurde.

## 9. Wiederherstellung

Falls versehentlich Dateien geändert oder beschädigt wurden:
- sofort stoppen,
- automatisch aus dem zuvor erstellten Backup wiederherstellen,
- keine weiteren Änderungen durchführen,
- den Vorfall melden.

## 10. Bei Unsicherheit

Wenn nicht eindeutig erkennbar ist,
- welche Dateien geändert werden dürfen,
- ob weitere Dateien betroffen wären,
- ob Daten verloren gehen könnten,

dann sofort anhalten und nachfragen.

Nicht raten.

## 11. Priorität

Die Prioritäten sind immer:
1. Datensicherheit
2. Backup
3. Funktionsfähigkeit
4. Möglichst kleine Änderungen
5. Geschwindigkeit

Lieber einmal zu wenig ändern als versehentlich Daten oder Funktionen verlieren.

Diese Regeln gelten dauerhaft für sämtliche Aufgaben in diesem Projekt.

## 12. Abschlussbefehl nach Änderungen

Nach jeder Änderung muss am Ende der Antwort immer der folgende Befehl ausgegeben werden:

```bash
python scripts/bump_core_version.py --include-worktree --commit "<aktuelle Commit-Beschreibung>"
```

- Keine Versionsnummer und keinen Parameter `--version` angeben.
- Die Commit-Beschreibung muss die jeweils aktuell durchgeführte Änderung beschreiben.
- Beispiel für die Zentralisierung der Doser-BLE-Operationen:

```bash
python scripts/bump_core_version.py --include-worktree --commit "fix: centralize all Doser BLE operations"
```

Der Befehl darf entsprechend den Git-Regeln nur ausgegeben und nicht ohne ausdrückliche Freigabe ausgeführt werden.

## 13. Git-Identität vor Commit und Push

Vor jedem Commit, Push oder History-Rewrite muss die lokale Repository-Git-Identität geprüft werden.

Erlaubt ist ausschließlich:

```text
user.name = charlie508010
user.email = 285831950+charlie508010@users.noreply.github.com
```

Vor jedem Commit oder Push müssen diese Befehle geprüft werden:

```bash
git config --show-origin user.name
git config --show-origin user.email
```

Wenn eine andere Identität aktiv ist, muss sie vor dem Commit ausschließlich lokal für dieses Repository korrigiert werden:

```bash
git config user.name "charlie508010"
git config user.email "285831950+charlie508010@users.noreply.github.com"
```

Globale Git-Konfiguration darf dafür nicht geändert werden.

Commits mit Namen, E-Mail oder GitHub-Zuordnung von `Martin11180`, `martin-oberst@arcor.de` oder anderen privaten Accounts sind verboten.

Nach einem Push muss bei Bedarf geprüft werden, dass GitHub die Commits nicht einem falschen Account zuordnet. Wenn ein falscher Autor sichtbar wird, sofort stoppen und keine weiteren Commits oder Pushes ausführen.

lesen und schreiben auf \\172.20.48.110\config\.chihiros\chihiros_state.sqlite3 erlaube ich mache aber immer ein backup
löschen ist nicht erlaubt

## 14. LED-Core-Abgrenzung

- Dieses Repository ist die eigenständige Arbeitskopie für die LED-Steuerung.
- Änderungen dürfen sich ausschließlich auf LED-Funktionen oder ausdrücklich gemeinsame Core-Schnittstellen beziehen.
- Doser, Rührer, Heizer, Wireshark und allgemeine CTL-Oberflächen dürfen nicht direkt in den LED-Core eingebaut werden.
- Weitere Gerätearten werden später über getrennte Plugins oder Pakete angebunden.
- Ein Plugin darf die geprüften LED-Protokoll-, Scheduler-, Dashboard- oder Home-Assistant-Funktionen nicht verändern.
- Historische interne Kompatibilitätsfunktionen dürfen erst entfernt werden, wenn die LED-Tests ihre Entbehrlichkeit belegen.
