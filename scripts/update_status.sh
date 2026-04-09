#!/bin/bash
# Updates status files for HA to read (runs via cron every 30s)
DIR="/home/yaniss/projects/infra-home/ha_config/status"
systemctl is-active ambilight-sync.service > "$DIR/ambisync.txt"
systemctl is-active openrgb-server.service > "$DIR/openrgb.txt"
ping -c1 -W2 192.168.68.52 > /dev/null 2>&1 && echo "ON" > "$DIR/tv.txt" || echo "OFF" > "$DIR/tv.txt"
ping -c1 -W2 192.168.1.13 > /dev/null 2>&1 && echo "ON" > "$DIR/firestick.txt" || echo "OFF" > "$DIR/firestick.txt"
ping -c1 -W2 192.168.1.1 > /dev/null 2>&1 && echo "ON" > "$DIR/livebox.txt" || echo "OFF" > "$DIR/livebox.txt"
# Pi-hole stats
PIHOLE_PASS=$(grep PIHOLE_PASSWORD /home/yaniss/projects/infra-home/.env | cut -d= -f2)
SID=$(curl -s -X POST http://localhost:8081/api/auth -H 'Content-Type: application/json' -d "{\"password\":\"$PIHOLE_PASS\"}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['session']['sid'])" 2>/dev/null)
if [ -n "$SID" ]; then
  curl -s -H "sid: $SID" http://localhost:8081/api/stats/summary 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
q=d['queries']
print(f\"{q['blocked']}/{q['total']} ({round(q['percent_blocked'],1)}%)\")" > "$DIR/pihole.txt" 2>/dev/null
fi
