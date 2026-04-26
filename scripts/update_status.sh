#!/bin/bash
# Updates status files for HA to read (runs via cron every 30s).
#
# Reads device IPs and PIHOLE_PASSWORD from .env at the project root.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
fi

DIR="$PROJECT_ROOT/ha_config/status"
TV_IP="${TV_IP:-192.168.1.50}"
FIRESTICK_IP="${FIRESTICK_IP:-192.168.1.51}"
LIVEBOX_IP="${LIVEBOX_IP:-192.168.1.1}"

systemctl is-active ambilight-sync.service > "$DIR/ambisync.txt"
systemctl is-active openrgb-server.service > "$DIR/openrgb.txt"
ping -c1 -W2 "$TV_IP" > /dev/null 2>&1 && echo "ON" > "$DIR/tv.txt" || echo "OFF" > "$DIR/tv.txt"
ping -c1 -W2 "$FIRESTICK_IP" > /dev/null 2>&1 && echo "ON" > "$DIR/firestick.txt" || echo "OFF" > "$DIR/firestick.txt"
ping -c1 -W2 "$LIVEBOX_IP" > /dev/null 2>&1 && echo "ON" > "$DIR/livebox.txt" || echo "OFF" > "$DIR/livebox.txt"

# Pi-hole stats
if [ -n "$PIHOLE_PASSWORD" ]; then
  SID=$(curl -s -X POST http://localhost:8081/api/auth \
    -H 'Content-Type: application/json' \
    -d "{\"password\":\"$PIHOLE_PASSWORD\"}" 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['session']['sid'])" 2>/dev/null)
  if [ -n "$SID" ]; then
    curl -s -H "sid: $SID" http://localhost:8081/api/stats/summary 2>/dev/null \
      | python3 -c "
import sys,json
d=json.load(sys.stdin)
q=d['queries']
print(f\"{q['blocked']}/{q['total']} ({round(q['percent_blocked'],1)}%)\")" \
      > "$DIR/pihole.txt" 2>/dev/null
  fi
fi
