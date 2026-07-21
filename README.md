# Chihiros LED Control

This repository contains a python **CLI** script as well as a **Home Assistant integration** that can be used to control Chihiros LEDs for aquariums via bluetooth without the vendor app. For this purpose, the protocol to control the LED has been reversed engineered with the help of decompiling the old *Magic App* as well as sniffing and analyzing of bluetooth packages that are sent by the new *My Chihiros App*. The new app is based on flutter and only contains a binary that can not easily be analyzed.

## Supported Devices
- [Chihiros LED A2](https://www.chihirosaquaticstudio.com/products/chihiros-a-ii-built-in-bluetooth)
- [Chihiros WRGB II](https://www.chihirosaquaticstudio.com/products/chihiros-wrgb-ii-led-built-in-bluetooth) (Regular, Pro, Slim; Pro is true WRGB)
- Chihiros WRGB VIVID III (true WRGB, including fan control and fan RPM/temperature sensors)
- Chihiros Tiny Terrarium Egg
- Chihiros C II (RGB, White)
- Chihiros Universal WRGB
- Chihiros Z Light TINY
- Chihiros Commander 1
- Chihiros Commander 4
- other LED models might work as well but are not tested


## Using the Home Assistant integration
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=themicdiet&repository=chihiros-led-control&category=Integration)
### Setup with HACS
- Inside HACS add this repository as a custom repository: ```HACS -> Integrations -> 3 dots on the top right-> Custom repositories```
- Search for ```Chihiros``` in the repositories and download it
- Restart Home Assistant
- Go to the integrations user interface and add the Chihiros integration
- Supported devices should be discovered at this point

### Manual Setup
- Copy the contents of `custom_components/chihiros` to `<config dir>/custom_components/chihiros_led_core`
- Restart Home-Assistant
- Add the Chihiros integration to your Home Assistant instance via the integrations user interface

### Home Assistant services

The integration provides services for changing the auto mode schedule from
**Developer Tools -> Actions** or from automations:

- `chihiros_led_core.add_schedule`: add one schedule period.
- `chihiros_led_core.remove_schedule`: remove one schedule period.
- `chihiros_led_core.reset_schedule`: remove all schedule periods.
- `chihiros_led_core.set_schedule`: replace the complete schedule.

If only one Chihiros device is configured, `entry_id` and `address` can be
omitted. If multiple devices are configured, include either the config entry ID
or Bluetooth address.

Replace the complete schedule:

```yaml
service: chihiros_led_core.set_schedule
data:
  address: "AA:BB:CC:DD:EE:FF"
  periods:
    - start: "08:00"
      end: "12:00"
      brightness: 40
      ramp_up_minutes: 30
      weekdays:
        - monday
        - tuesday
    - start: "09:00"
      end: "17:00"
      brightness: 55
      weekdays:
        - wednesday
        - thursday
```

Add one white or shared-brightness period:

```yaml
service: chihiros_led_core.add_schedule
data:
  start: "08:00"
  end: "18:30"
  brightness: 70
  ramp_up_minutes: 30
  weekdays:
    - monday
    - tuesday
```

Remove a matching period:

```yaml
service: chihiros_led_core.remove_schedule
data:
  start: "08:00"
  end: "18:30"
  ramp_up_minutes: 30
  weekdays:
    - monday
    - tuesday
```

Reset all schedule periods:

```yaml
service: chihiros_led_core.reset_schedule
data:
  address: "AA:BB:CC:DD:EE:FF"
```

Schedule writes are validated before sending commands to the device. Unsupported
channels, invalid brightness values, invalid weekdays, empty replacement
schedules, and multiple replacement periods for the same weekday are rejected.
Known devices replace the previous period for a weekday when another one is
written, so `set_schedule` accepts at most one period per weekday. After writing
a schedule, enable the `Auto Mode` switch to run it.

## Requirements
- a device with bluetooth LE support for sending the commands to the LED
- [uv](https://docs.astral.sh/uv/) for Python environment and dependency management

## Using the CLI
```bash
# setup the environment
uv --cache-dir .uv-cache sync --extra cli

# show help
uv --cache-dir .uv-cache run chihirosctl --help

# discover devices and their address
uv --cache-dir .uv-cache run chihirosctl led list-devices

# turn on the device
uv --cache-dir .uv-cache run chihirosctl led turn-on <device-address>

# turn off the device
uv --cache-dir .uv-cache run chihirosctl led turn-off <device-address>

# manually set the brightness to 100
uv --cache-dir .uv-cache run chihirosctl led set-brightness <device-address> 100

# set the fan to 50 percent on a WRGB VIVID III
uv --cache-dir .uv-cache run chihirosctl led set-fan-speed <device-address> 50

# create an automatic timed setting that turns on the light from 8:00 to 18:00 at brightness 100
uv --cache-dir .uv-cache run chihirosctl led add-setting <device-address> 8:00 18:00 100

# create a setting for specific weekdays with maximum brightness of 75 and ramp up time of 30 minutes
uv --cache-dir .uv-cache run chihirosctl led add-setting <device-address> 9:00 18:00 75 --weekdays monday --weekdays tuesday --ramp-up-in-minutes 30

# manually set the brightness to 60 red, 80 green, 100 blue on RGB models
uv --cache-dir .uv-cache run chihirosctl led set-brightness <device-address> 60 80 100

# create an automatic timed setting that turns on the light from 8:00 to 18:00
uv --cache-dir .uv-cache run chihirosctl led add-setting <device-address> 8:00 18:00 100 100 100

# create a setting for specific weekdays with maximum brightness of 35, 55, 75 and ramp up time of 30 minutes
uv --cache-dir .uv-cache run chihirosctl led add-setting <device-address> 9:00 18:00 35 55 75 --weekdays monday --weekdays tuesday --ramp-up-in-minutes 30

# on true WRGB models, set red, green, blue, and white levels
uv --cache-dir .uv-cache run chihirosctl led add-setting <device-address> 9:00 18:00 35 55 75 40

# enable auto mode to activate the created timed settings
uv --cache-dir .uv-cache run chihirosctl led enable-auto-mode <device-address>

# delete a created setting
uv --cache-dir .uv-cache run chihirosctl led remove-setting <device-address> 8:00 18:00

# reset all created settings
uv --cache-dir .uv-cache run chihirosctl led reset-settings <device-address>

```

### LED CTL commands

| Command | Purpose |
| --- | --- |
| `led list-devices` | Discover supported BLE LEDs |
| `led turn-on` | Switch all LED channels on |
| `led turn-off` | Switch all LED channels off |
| `led set-brightness` | Set one, three, or four channel levels |
| `led set-fan-speed` | Set the VIVID III fan percentage |
| `led add-setting` | Add or update a device schedule |
| `led remove-setting` | Remove a matching device schedule |
| `led reset-settings` | Reset all device schedules |
| `led enable-auto-mode` | Activate the stored automatic schedule |
| `led watch-runtime` | Query and observe runtime/fan notifications |
| `led read-notifications` | Print raw LED notifications for diagnostics |

## Rated power and estimates

Known rated powers and their verification status are listed in [docs/model-power.md](docs/model-power.md). Dashboard
consumption values are estimates, always marked with `≈`: the empirical Universal WRGB curve is retained; other
known models use rated power multiplied by the average channel percentage. A per-device rated-power override in
Config has priority and is intended for controllers or ambiguous model sizes.

## Protocol

The Bluetooth command format and known modes are documented in
[docs/protocol.md](docs/protocol.md).

## Contributing
Reusable library and CLI code lives in `src/chihiros_led_control/`. The Home
Assistant integration lives in `custom_components/chihiros/` and imports the
vendored runtime copy from `custom_components/chihiros/vendor/` so HACS installs
do not require the top-level package.

Set up the development environment with uv:

```bash
uv --cache-dir .uv-cache sync --group dev
uv --cache-dir .uv-cache run --group dev pytest
uv --cache-dir .uv-cache run --group dev pre-commit run --all-files
```

Home Assistant integration tests use the separate `ha-test` dependency group
because they install Home Assistant and its test-time runtime dependencies. Run
them explicitly when changing files under `custom_components/chihiros/`:

```bash
uv --cache-dir .uv-cache run --group ha-test pytest tests/test_home_assistant_integration.py tests/test_manifest_requirements.py
```

The integration test creates a temporary Home Assistant config directory,
symlinks this repository's `custom_components/` directory into it, and patches
storage writes so the test does not need a running Home Assistant instance or
real Bluetooth hardware. The manifest requirements test keeps the integration's
runtime requirement pins aligned with `pyproject.toml`.

After changing library code, refresh the vendored copy:

```bash
uv --cache-dir .uv-cache run python scripts/sync_vendor.py
uv --cache-dir .uv-cache run python scripts/sync_vendor.py --check
```

For local Home Assistant testing with Docker Compose, see [docs/home-assistant-docker.md](docs/home-assistant-docker.md).

See [docs/architecture.md](docs/architecture.md) for the package layout.
