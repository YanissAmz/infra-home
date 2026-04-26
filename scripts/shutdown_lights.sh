#!/usr/bin/env bash
# Extinction Govee + Hue quand le PC s'éteint.
# Appelé par ambilight-sync.service ExecStopPost.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="${INFRA_HOME_CONFIG:-$SCRIPT_DIR/../ambisync_config/config.yml}"

# Lire les valeurs du config YAML (grep simple, pas besoin de yq)
HUE_BRIDGE=$(grep 'bridge_host:' "$CONFIG" | awk '{print $2}')
HUE_TOKEN=$(grep 'token:' "$CONFIG" | awk '{print $2}')
GOVEE_IP=$(grep 'ip:' "$CONFIG" | head -1 | awk '{print $2}')

# Éteindre Hue lampes 1, 2 + prise smart plug 3
for lid in 1 2 3; do
    curl -sf -X PUT "http://${HUE_BRIDGE}/api/${HUE_TOKEN}/lights/${lid}/state" \
        -d '{"on":false}' --max-time 2 &
done

# Éteindre Govee via LAN API (UDP)
if [ -n "$GOVEE_IP" ]; then
    echo '{"msg":{"cmd":"turn","data":{"value":0}}}' | socat - UDP-SENDTO:"${GOVEE_IP}":4003 2>/dev/null &
fi

wait
echo "[shutdown-lights] Govee + Hue OFF"
