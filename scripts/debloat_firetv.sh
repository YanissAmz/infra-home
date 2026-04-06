#!/usr/bin/env bash
# debloat_firetv.sh — désactive packages Amazon pubs/télémétrie/carrousel
# Usage: ./debloat_firetv.sh <IP_firestick>
# Prérequis côté Firestick:
#   Settings → My Fire TV → About → 7 clics sur Build
#   → Developer Options → ADB Debugging ON + Apps from Unknown Sources ON
# Rollback: remplacer disable-user par enable, relancer le script.
set -euo pipefail

IP="${1:-}"
if [[ -z "$IP" ]]; then
    echo "Usage: $0 <IP_firestick>"
    exit 1
fi

ACTION="${ACTION:-disable-user}"   # ACTION=enable ./debloat_firetv.sh <IP> pour rollback

# Packages à désactiver (pubs, carrousel Prime imposé, télémétrie, bloat)
PACKAGES=(
    # Pubs et recommandations forcées
    com.amazon.bueller.notification
    com.amazon.hedwig
    com.amazon.pandahouse
    com.amazon.ftv.glances
    com.amazon.ftv.screensaver.inhome.feature
    com.amazon.avod.thirdpartyclient
    com.amazon.recess
    com.amazon.katmaioobe

    # Auto-updates agressifs
    com.amazon.kindleautoupdate
    com.amazon.device.software.ota.override

    # Alexa et assistants (décommenter si pas utilisé)
    # com.amazon.alexashopping
    # com.amazon.bit.wakeword
    # com.amazon.alexa.externalmediaplayer.fireos

    # Launcher Amazon (remplacé par Projectivy, voir firetv_sideload.sh)
    com.amazon.tv.launcher

    # Telemetry / analytics
    com.amazon.device.metrics
    com.amazon.device.logmanager
)

echo "[adb] connecting $IP:5555"
adb connect "$IP:5555" >/dev/null

echo "[adb] wait-for-device"
adb -s "$IP:5555" wait-for-device

echo "[adb] Firestick info:"
adb -s "$IP:5555" shell getprop ro.build.fingerprint
adb -s "$IP:5555" shell getprop ro.product.model

echo ""
echo "[adb] action=$ACTION on ${#PACKAGES[@]} packages"
for pkg in "${PACKAGES[@]}"; do
    if adb -s "$IP:5555" shell "pm $ACTION --user 0 $pkg" 2>&1 | grep -qE "new state|Unknown package"; then
        echo "  ✓ $pkg"
    else
        echo "  ✗ $pkg (skipped or error)"
    fi
done

echo ""
echo "[done] Reboot recommended: adb -s $IP:5555 reboot"
echo "[info] To rollback: ACTION=enable $0 $IP"
