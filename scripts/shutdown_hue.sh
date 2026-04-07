#!/bin/bash
# Éteint les lampes Hue quand le PC s'arrête
# Appelé par hue-shutdown.service (ExecStop)
HUE_BRIDGE="192.168.1.59"
HUE_TOKEN="***SCRUBBED***"

# Éteindre lampe 1 + lampe 2
curl -s -X PUT "http://$HUE_BRIDGE/api/$HUE_TOKEN/lights/1/state" -d '{"on":false}' --max-time 2
curl -s -X PUT "http://$HUE_BRIDGE/api/$HUE_TOKEN/lights/2/state" -d '{"on":false}' --max-time 2

echo "[hue-shutdown] lights off"
