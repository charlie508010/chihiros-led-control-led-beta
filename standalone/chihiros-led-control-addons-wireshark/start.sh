#!/usr/bin/env bash
set -euo pipefail

app_slug="${1:-d8cbe98f_chihiros_led_core}"
if ! command -v ha >/dev/null 2>&1; then
  echo "Error: Home Assistant CLI 'ha' was not found. Run this script in the Home Assistant terminal." >&2
  exit 1
fi

echo "Restarting LED Core app: ${app_slug}"
ha apps restart "${app_slug}"
echo "LED Core restart requested. Reload the dashboard after about 20 seconds."
