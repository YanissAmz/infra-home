#!/bin/bash
# Turn off Hue lamps when the PC shuts down (called by hue-shutdown.service ExecStop)
#
# Reads HUE_BRIDGE and HUE_TOKEN from .env at the project root.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
fi

HUE_BRIDGE="${HUE_BRIDGE:-}"
HUE_TOKEN="${HUE_TOKEN:-}"
if [ -z "$HUE_BRIDGE" ] || [ -z "$HUE_TOKEN" ]; then
  echo "shutdown_hue.sh: HUE_BRIDGE and HUE_TOKEN must be set in $ENV_FILE" >&2
  exit 1
fi

# Turn off lamp 1 + lamp 2
curl -s -X PUT "http://$HUE_BRIDGE/api/$HUE_TOKEN/lights/1/state" -d '{"on":false}' --max-time 2
curl -s -X PUT "http://$HUE_BRIDGE/api/$HUE_TOKEN/lights/2/state" -d '{"on":false}' --max-time 2

echo "[hue-shutdown] lights off"
