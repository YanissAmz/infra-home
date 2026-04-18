# infra-home

**Bypass the removed Ambilight+Hue feature, sync your PC LEDs to your TV, debloat Fire TV Sticks, and block ads network-wide — all orchestrated from a single Home Assistant dashboard.**

> TP Vision removed Ambilight+Hue from 2023 Philips TVs, pushing a ~250 EUR Hue Sync Box.
> This project brings it back for free, and goes much further.

<!-- TODO: Replace with actual demo video -->
<!-- https://github.com/user-attachments/assets/your-video-id -->

https://github.com/user-attachments/assets/PLACEHOLDER_DEMO_VIDEO

---

## What it does

| Feature | Description | Savings |
|---------|-------------|---------|
| **Ambilight &rarr; Hue sync** | TV colors push to Hue lamps in real-time via JointSPACE API | ~250 EUR (no Sync Box) |
| **Ambilight &rarr; PC LEDs** | Same TV colors sync to motherboard/RAM RGB via OpenRGB | Free immersion |
| **Fire TV debloat** | Remove Amazon ads, telemetry, replace launcher | No more ads |
| **Pi-hole DNS** | Network-wide ad/tracking blocker (38+ custom domains) | All devices protected |
| **Home Assistant** | Central dashboard, automations, scenes, remote control | One app rules all |

---

## Demo

### Dashboard

<!-- TODO: Screenshot of the main dashboard -->
![Dashboard - Chambre](docs/screenshots/dashboard_chambre.png)

<!-- TODO: Screenshot of the services view -->
![Dashboard - Services](docs/screenshots/dashboard_services.png)

<!-- TODO: Screenshot of the network view -->
![Dashboard - Reseau](docs/screenshots/dashboard_reseau.png)

### Ambilight Sync in action

<!-- TODO: Photo/video of TV + Hue lamps + PC LEDs all synced -->
![Ambilight Sync](docs/screenshots/ambilight_sync_demo.gif)

### Before / After Fire TV

<!-- TODO: Side by side screenshots -->
| Before (stock) | After (debloated) |
|:-:|:-:|
| ![Before](docs/screenshots/firetv_before.png) | ![After](docs/screenshots/firetv_after.png) |

---

## Architecture

```
                    Internet
                       |
                   Livebox W7
                    /     \
              Pi-hole      Mesh WiFi (Deco)
             (DNS block)      |
                |         --------------------
             GPU Tower    |    |    |    |
           (RTX 3090)    TV  Stick Stick Phones
              |          OLED  HD   4K
         -----------
         |    |    |
         HA  MQTT  OpenRGB
         |
    ---------------------
    |         |         |
  Hue API  JointSPACE  ADB
    |         |         |
  Lamps    Ambilight  Firesticks
```

### How the sync works

```
TV Ambilight (JointSPACE /6/ambilight/measured)
       |
       v
  [Dominant color extraction + boost]
       |
       +----> Hue Bridge REST API -----> Hue Lamps (color sync)
       |
       +----> OpenRGB SDK (port 6742) -> Motherboard + RAM LEDs
```

The sync script polls the TV's Ambilight API, picks the most saturated zone, boosts the color (API returns 0~120, we normalize to 0~255 with 1.5x saturation), and pushes the same unified color to both Hue and OpenRGB simultaneously.

---

## Hardware

| Device | Role |
|--------|------|
| Philips 55OLED708 | Ambilight source (JointSPACE API) |
| Hue Bridge + 2x E27 Color + Smart Plug + Dimmer Switch | Ambient lighting |
| Fire TV Stick HD | Streaming (debloated) |
| Fire TV Stick 4K | Streaming (debloated) |
| GPU Tower (RTX 3090) | Runs HA, Pi-hole, OpenRGB, sync scripts |
| TP-Link Deco (mesh) | Stable WiFi coverage |

---

## Quick start

### 1. Clone & configure

```bash
git clone https://github.com/YanissAmz/infra-home.git
cd infra-home

# Secrets
cp .env.example .env                              # Pi-hole password
cp ambisync_config/config.example.yml ambisync_config/config.yml  # TV + Hue credentials
cp ha_config/secrets.example.yaml ha_config/secrets.yaml          # HA shell commands / local hosts
# Edit both files with your values
```

### 2. Pair your TV (JointSPACE)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install requests pyyaml urllib3

python scripts/philips_jointspace.py --pair --host <TV_IP>
# Enter the PIN shown on TV
```

### 3. Pair Hue Bridge

```bash
# Press the bridge button, then within 30 seconds:
curl -X POST http://<BRIDGE_IP>/api \
  -H 'Content-Type: application/json' \
  -d '{"devicetype":"ambisync#home"}'
# Save the returned token in ambisync_config/config.yml
```

### 4. Launch the stack

```bash
# Free port 53 for Pi-hole
sudo sed -i 's/#DNSStubListener=yes/DNSStubListener=no/' /etc/systemd/resolved.conf
sudo systemctl restart systemd-resolved

docker compose up -d
```

### 5. Start the sync

```bash
# Test manually first
python scripts/ambilight_unified_sync.py

# Then install as systemd service (see docs)
# Daily workflow:
make check
make deploy-ambilight
```

Runtime day/night tuning is exposed directly in Home Assistant under `Services > Ambilight Sync > Reglages runtime`.
Those helpers write `/config/runtime/overrides.json`, which the sync reloads live without a service restart.

**Access:**
- Home Assistant: `http://localhost:8123`
- Pi-hole admin: `http://localhost:8081/admin`

---

## Fire TV debloat

```bash
# Enable Developer Options on Firestick (7 taps on Build Number)
# Enable ADB debugging, note the IP

./scripts/debloat_firetv.sh <FIRESTICK_IP>
# Disables 23+ Amazon bloatware packages (ads, telemetry, appstore promos)

# Rollback anytime:
ACTION=enable ./scripts/debloat_firetv.sh <FIRESTICK_IP>
```

---

## Dashboard

The Lovelace dashboard includes 5 views:

| View | Features |
|------|----------|
| **Chambre** | TV media control, Ambilight, Hue lamps, 5 scenes (Cinema/Gaming/Lecture/Nuit/OFF), automations |
| **Firesticks** | Launch apps (Stremio/YouTube/IPTV) via ADB, online status |
| **Services** | Ambilight sync status + restart, Pi-hole stats, OpenRGB status |
| **Reseau** | Device ping status, Zigbee mesh health, weather |
| **Systeme** | HACS updates |

### Scenes

| Scene | Lamps | Use case |
|-------|-------|----------|
| Cinema | Warm white, very dim | Movie night |
| Gaming | Blue + Pink, vivid | Gaming session |
| Lecture | Full brightness, neutral | Reading |
| Nuit | Minimal, warmest | Bedtime |

### Hue Dimmer Switch mapping

| Button | Short press | Long press |
|--------|------------|------------|
| 1 (top) | Lights ON | Gaming scene |
| 2 | Brightness + | Lecture scene |
| 3 | Brightness - | Cinema scene |
| 4 (bottom) | Lights OFF | Nuit scene |

---

## Pi-hole blocklist

Custom blocklist targeting:
- Amazon Fire TV telemetry & ads (device-metrics-us, mads-eu, unagi-na...)
- Philips TV analytics (smarttv.philips.com)
- Google TV ads
- Samsung & LG bonus domains

See [`pihole/custom-blocklist.txt`](pihole/custom-blocklist.txt) for the full list.

---

## File structure

```
infra-home/
|-- docker-compose.yml              # HA + Pi-hole + Mosquitto
|-- .env.example                    # Secrets template
|-- ambisync_config/
|   |-- config.example.yml          # Sync config template
|-- ha_config/
|   |-- configuration.yaml          # HA config (sensors, shell commands)
|   |-- automations.yaml            # 13 automations (TV + remote)
|   |-- scenes.yaml                 # 5 scenes
|   |-- ui-lovelace.yaml            # Dashboard (5 views)
|-- scripts/
|   |-- ambilight_unified_sync.py   # TV -> Hue + OpenRGB sync
|   |-- philips_jointspace.py       # JointSPACE API CLI (pair, control)
|   |-- philips_hue_ambisync.py     # Hue-only sync (legacy)
|   |-- ambilight_to_openrgb.py     # OpenRGB-only sync (legacy)
|   |-- debloat_firetv.sh           # Fire TV debloat/restore
|   |-- ha_command_bridge.sh        # Host systemctl bridge for HA
|   |-- update_status.sh            # Cron status updater for HA sensors
|-- pihole/
|   |-- custom-blocklist.txt        # 38+ blocked domains
|-- PROGRESS.md                     # Detailed build log
|-- MESH_SETUP.md                   # Mesh WiFi install guide
```

---

## Tested on

- Philips 55OLED708/12 (firmware 2023-2024, JointSPACE v6)
- Fire TV Stick HD & 4K (FireOS 2025-2026)
- Hue Bridge v2 + E27 Color A60 + Smart Plug LOM008 + Dimmer Switch RWL022
- Ubuntu 24.04+ with Docker, RTX 3090
- Home Assistant 2026.4+

---

## Known limitations

- **PC must be on** for sync and Pi-hole to work. Future: dedicated RPi Zero 2 W (~20 EUR).
- **JointSPACE** may be locked on future Philips firmware. Fallback: ADB screen capture + Hyperion.
- **Hue lamp latency** ~200-500ms depending on Zigbee mesh quality. Smart plug as mesh relay helps.
- **`/6/ambilight/processed` returns zeroes** on 55OLED708. Use `/measured` instead.

---

## Contributing

This started as a personal setup but might help others with Philips Ambilight TVs.
Feel free to open issues or PRs if you adapt it to your own hardware.

---

## License

MIT
