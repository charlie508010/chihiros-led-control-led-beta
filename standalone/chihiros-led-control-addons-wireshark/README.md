# Wireshark LED HCI plugin

This optional add-on plugin provides ADB connection, HCI capture through root or Android bugreport, log/PCAP
selection, LED frame decoding and packet comparison. It has no Doser, heater or generic CTL dependency.

Install the generated TGZ in LED Core **Config**, then restart the LED-Core add-on. Runtime data is stored below
`/config/.chihiros_led_core/plugin_data/wireshark/`.

## Build

Create the reproducible TGZ from the repository root:

```bash
bash build.sh
```

The result is written to `dist/chihiros-wireshark-<version>.tgz`.

## Start after installation

The plugin has no separate daemon. It is loaded by LED Core when that Home Assistant app starts. After uploading the
TGZ, run this in the Home Assistant terminal:

```bash
bash start.sh
```

Pass a different LED-Core app slug as the first argument if required.
