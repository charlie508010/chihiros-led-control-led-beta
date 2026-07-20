# Architecture

The repository is split into a reusable LED protocol core, a self-contained Home Assistant integration, and an
add-on dashboard. Device types other than LEDs are deliberately not part of this core.

```text
Home Assistant Bluetooth -> integration -> LED plugin -> vendored protocol package -> BLE LED
          |                     |             |
          |                     +-> entities  +-> scheduler snapshots
          +-> entity state ----------------------------------------------+
                                                                          v
Browser <-> add-on HTTP API <-> dashboard <-> SQLite state + external plugin directory
```

## Components

| Path | Responsibility |
| --- | --- |
| `src/chihiros_led_control/` | Source of truth for protocol, models, store, scheduler and `chihirosctl` |
| `custom_components/chihiros/plugins/led/` | Built-in LED plugin, entities, services and dashboard panel |
| `custom_components/chihiros/plugins/led/vendor/` | Synced runtime copy used by Home Assistant/HACS |
| `custom_components/chihiros/core/` | Stable plugin loader and shared Home Assistant interfaces |
| `chihiros_beta/ui/` | Add-on HTTP server, shell and Config tab |
| `.chihiros_led_core/plugins/` | Validated external add-on plugins installed from TGZ |
| `.chihiros_led_core/plugin_data/` | Per-plugin runtime data; never executable plugin source |
| `.chihiros_led_core/plugin_backups/` | Dated, retained plugin versions replaced by an update |
| SQLite state | Device aliases, local names, templates, schedules and UI state |

An installed plugin declares its runtime (`home_assistant`, `addon`), optional frontend module, tabs, backend entry
point and an explicit backend-action allowlist. The installer validates and stages a TGZ, moves an old version to the
backup directory, then publishes the staged directory atomically. A newly installed frontend is not imported until
the add-on is restarted. Plugins cannot replace the built-in LED tab, scheduler, or protocol package.

## Vendor synchronization

Do not edit vendored files directly. Change `src/chihiros_led_control/`, then run:

```bash
uv --cache-dir .uv-cache run python scripts/sync_vendor.py
uv --cache-dir .uv-cache run python scripts/sync_vendor.py --check
```
