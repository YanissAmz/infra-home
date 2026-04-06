#!/usr/bin/env bash
# firetv_sideload.sh — sideload batch APKs sur Firestick via ADB
# Usage: ./firetv_sideload.sh <IP_firestick> [apk_dir]
# Télécharge APKs depuis docs/apks/urls.txt si apk_dir non fourni.
set -euo pipefail

IP="${1:-}"
APK_DIR="${2:-$(dirname "$0")/../docs/apks/cache}"
URLS_FILE="$(dirname "$0")/../docs/apks/urls.txt"

if [[ -z "$IP" ]]; then
    echo "Usage: $0 <IP_firestick> [apk_dir]"
    exit 1
fi

mkdir -p "$APK_DIR"

# Download phase
if [[ -f "$URLS_FILE" ]]; then
    echo "[download] fetching APKs listed in $URLS_FILE"
    while IFS='|' read -r name url; do
        [[ "$name" =~ ^#.*$ || -z "$name" ]] && continue
        dest="$APK_DIR/${name}.apk"
        if [[ ! -f "$dest" ]]; then
            echo "  ↓ $name"
            curl -sL -o "$dest" "$url" || echo "    ✗ failed"
        else
            echo "  ✓ $name (cached)"
        fi
    done < "$URLS_FILE"
fi

echo "[adb] connecting $IP:5555"
adb connect "$IP:5555" >/dev/null
adb -s "$IP:5555" wait-for-device

echo "[adb] installing APKs from $APK_DIR"
shopt -s nullglob
for apk in "$APK_DIR"/*.apk; do
    name="$(basename "$apk")"
    echo "  → $name"
    adb -s "$IP:5555" install -r "$apk" 2>&1 | tail -1
done

echo ""
echo "[done] To set Projectivy as default launcher:"
echo "  adb -s $IP:5555 shell cmd package set-home-activity com.spocky.projengmenu/.ui.launcher.MainActivity"
