#!/bin/bash
# Bridge: HA writes command files, this script on host executes them
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CMD_DIR="${INFRA_HOME_CMD_DIR:-$SCRIPT_DIR/../ha_config/commands}"
mkdir -p "$CMD_DIR"

while true; do
  shopt -s nullglob
  for f in "$CMD_DIR"/*.cmd; do
    CMD=$(cat "$f")
    rm -f "$f"
    case "$CMD" in
      ambisync_restart) systemctl restart ambilight-sync.service ;;
      ambisync_stop)    systemctl stop ambilight-sync.service ;;
      ambisync_start)   systemctl start ambilight-sync.service ;;
    esac
  done
  shopt -u nullglob
  sleep 1
done
