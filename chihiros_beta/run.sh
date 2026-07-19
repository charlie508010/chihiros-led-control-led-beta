#!/usr/bin/env bash
set -euo pipefail

OPTIONS_FILE="/data/options.json"
CANONICAL_SOURCE_REPOSITORY="https://github.com/charlie508010/chihiros-led-control-led-beta.git"
SOURCE_REPOSITORY="${CANONICAL_SOURCE_REPOSITORY}"
CONFIGURED_SOURCE_REPOSITORY="${CANONICAL_SOURCE_REPOSITORY}"
SOURCE_BRANCH="main"
GITHUB_TOKEN=""
INSTALL_INTEGRATION="true"
KEEP_RUNNING="true"

if [[ -f "${OPTIONS_FILE}" ]]; then
  eval "$(python3 - <<'PY'
import json
import shlex
from pathlib import Path
data = json.loads(Path("/data/options.json").read_text())
values = {
    "CONFIGURED_SOURCE_REPOSITORY": str(
        data.get("source_repository", "https://github.com/charlie508010/chihiros-led-control-led-beta.git")
    ),
    "SOURCE_BRANCH": str(data.get("source_branch", "main")),
    "GITHUB_TOKEN": str(data.get("github_token", "")),
    "INSTALL_INTEGRATION": str(data.get("install_integration", True)).lower(),
    "KEEP_RUNNING": str(data.get("keep_running", True)).lower(),
}
for key, value in values.items():
    print(f"{key}={shlex.quote(value)}")
PY
)"
fi

if [[ "${CONFIGURED_SOURCE_REPOSITORY}" != "${CANONICAL_SOURCE_REPOSITORY}" ]]; then
  echo "Ignoring legacy source_repository '${CONFIGURED_SOURCE_REPOSITORY}'."
  echo "LED Core always loads '${CANONICAL_SOURCE_REPOSITORY}'."
fi

rm -rf /opt/chihiros-led-core-src
CLONE_REPOSITORY="${SOURCE_REPOSITORY}"
if [[ -n "${GITHUB_TOKEN}" && "${SOURCE_REPOSITORY}" == https://github.com/* ]]; then
  ENCODED_GITHUB_TOKEN="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "${GITHUB_TOKEN}")"
  CLONE_REPOSITORY="${SOURCE_REPOSITORY/https:\/\/github.com\//https:\/\/x-access-token:${ENCODED_GITHUB_TOKEN}@github.com\/}"
fi

git clone --depth 1 --branch "${SOURCE_BRANCH}" "${CLONE_REPOSITORY}" /opt/chihiros-led-core-src

mkdir -p /config/.chihiros
export HASS_CONFIG="/config"
export CHIHIROS_STATE_DB="/config/.chihiros/chihiros_state.sqlite3"
export CHIHIROS_PLUGIN_KIND="core"
export CHIHIROS_UI_PORT="${CHIHIROS_UI_PORT:-8109}"

cp -a /opt/chihiros-led-core-src/chihiros_beta/ui/. /opt/chihiros-led-core-ui/
rm -rf /opt/chihiros-led-core-ui/dashboard
mkdir -p /opt/chihiros-led-core-ui/dashboard
cp -a /opt/chihiros-led-core-src/custom_components/chihiros/www/. /opt/chihiros-led-core-ui/dashboard/
echo "Chihiros dashboard assets installed to add-on UI."

if [[ "${INSTALL_INTEGRATION}" == "true" ]]; then
  mkdir -p /config/custom_components
  rm -rf /config/custom_components/chihiros
  cp -a /opt/chihiros-led-core-src/custom_components/chihiros /config/custom_components/chihiros
  find /config/custom_components/chihiros -type d -name __pycache__ -prune -exec rm -rf {} +
  echo "Chihiros integration installed to /config/custom_components/chihiros"
  echo "Restart Home Assistant after first install or update."
fi

echo "LED Core add-on is running."
echo "CTL is available inside this add-on container as: chihirosctl"

/opt/chihiros-led-core-venv/bin/python /opt/chihiros-led-core-ui/server.py &

if [[ "${KEEP_RUNNING}" == "true" ]]; then
  tail -f /dev/null
fi
