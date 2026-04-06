# infra-home — Libération TV Philips 55OLED708 + Firesticks + Hue

Stack Docker (HA + Pi-hole + Mosquitto + Ambisync) pour piloter ma chambre, bypasser la suppression Ambilight+hue TP Vision, et virer pubs/télémétrie Amazon/Philips/Google.

## Runbook par phase

### Phase 0 — Prérequis tour GPU

```bash
# Docker déjà installé normalement. Sinon:
sudo apt install docker.io docker-compose-plugin -y
sudo usermod -aG docker $USER
# reconnecter shell

# Libérer port 53 pour Pi-hole (désactive stub resolver systemd):
sudo sed -i 's/#DNSStubListener=yes/DNSStubListener=no/' /etc/systemd/resolved.conf
sudo systemctl restart systemd-resolved
# DNS système: pointer /etc/resolv.conf vers 127.0.0.1 après Pi-hole up
```

---

### Phase 1 — TV + Hue + Bypass (actions manuelles + scripts)

**Actions manuelles TV** :
1. TV allumée → Settings → À propos → 7 clics sur Build → Developer Options activé
2. Activer ADB debugging + noter IP TV
3. HDMI Ultra HD → Optimal (Game) sur ports utilisés
4. Activer JointSPACE si besoin : télécommande `5646877223` en regardant TV
5. Menu service panel OLED (bonus) : `1 2 3 6 5 4` rapide ou `062596`

**Pairing Hue** :
1. Brancher bridge Hue Ethernet sur box
2. App Hue mobile → pairer 2× E27 + prise + switch
3. Créer token API local :
   ```bash
   # Récupère IP bridge:
   curl https://discovery.meethue.com/
   # Appuyer bouton physique bridge puis dans 30s:
   curl -X POST http://<IP_BRIDGE>/api -H 'Content-Type: application/json' \
     -d '{"devicetype":"ambisync#yaniss"}'
   # → retourne {"success":{"username":"TOKEN"}}, garde TOKEN
   ```
4. Lister lampes pour récupérer IDs :
   ```bash
   curl http://<IP_BRIDGE>/api/<TOKEN>/lights | jq
   ```

**Pairing JointSPACE TV** :
```bash
cd /home/yaniss/infra-home
python3 -m venv .venv && source .venv/bin/activate
pip install requests pyyaml urllib3
python scripts/philips_jointspace.py --pair --host <IP_TV>
# PIN s'affiche sur TV → l'entrer dans le prompt
# → credentials sauvegardés dans scripts/.env.jointspace
```

**Test API** :
```bash
python scripts/philips_jointspace.py --powerstate
python scripts/philips_jointspace.py --ambilight-processed | head -50
```

**Configurer bypass Ambilight→Hue** :
```bash
# Éditer ambisync_config/config.yml:
# - tv.host, tv.device_id, tv.auth_key (depuis scripts/.env.jointspace)
# - hue.bridge_host, hue.token
# - mapping: adapter light_id aux vraies IDs retournées par /api/<token>/lights
nano ambisync_config/config.yml

# Test one-shot:
python scripts/philips_hue_ambisync.py --once
```

---

### Phase 2 — Stack Docker

```bash
cd /home/yaniss/infra-home

# Copier .env.example vers .env et remplir le mot de passe Pi-hole

docker compose up -d
docker compose ps
docker compose logs -f ambisync   # vérifier que sync tourne
```

**Accès** :
- Home Assistant : http://<IP_TOUR>:8123
- Pi-hole admin : http://<IP_TOUR>:8081/admin

**Pi-hole — importer blocklist custom** :
- Admin → Adlists → Add : colle URL d'un gist si tu veux l'héberger
- Ou : Group Management → Domains → Import → coller contenu de `pihole/custom-blocklist.txt`

**Box FAI — forcer DNS** :
- Admin box → DHCP → DNS primaire = IP tour GPU
- **DNS secondaire = 1.1.1.1** ← CRITIQUE, fallback si container down
- Reboot box

**Home Assistant — intégrations** :
1. First setup HA (compte local)
2. Install HACS : https://hacs.xyz/docs/setup/download
3. HACS → Integrations → ajouter :
   - `jomwells/ambilights` (custom repo)
   - `mrjackyliang/ha-philips-tv` (ou équivalent maintenu)
4. Settings → Devices → Add : Philips Hue (auto-discovery), Philips TV (JointSPACE)

---

### Phase 3 — Firesticks

**Sur chaque Firestick (HD cuisine + 4K chambre sœur)** :
1. Settings → My Fire TV → About → 7 clics sur Build
2. Developer Options → ADB Debugging ON + Apps from Unknown Sources ON
3. Noter IP (Settings → My Fire TV → About → Network)

**Debloat** :
```bash
cd /home/yaniss/infra-home
./scripts/debloat_firetv.sh <IP_FIRESTICK_4K>
./scripts/debloat_firetv.sh <IP_FIRESTICK_HD>
# accepter prompt ADB sur chaque Firestick (écran "Allow USB debugging?")
```

**Sideload APKs** :
1. Éditer `docs/apks/urls.txt` avec les URLs à jour des dernières releases
2. Lancer :
   ```bash
   ./scripts/firetv_sideload.sh <IP_FIRESTICK>
   ```
3. Set Projectivy default launcher :
   ```bash
   adb -s <IP>:5555 shell cmd package set-home-activity \
     com.spocky.projengmenu/.ui.launcher.MainActivity
   ```

**Rollback Firestick** :
```bash
ACTION=enable ./scripts/debloat_firetv.sh <IP>
# + reset launcher via Settings → Applications → Manage → Clear defaults
```

---

## Vérification end-to-end

- [ ] `curl http://<IP_TOUR>/admin/api.php` → Pi-hole répond
- [ ] `nslookup amazon-adsystem.com <IP_TOUR>` → `0.0.0.0`
- [ ] `python scripts/philips_jointspace.py --ambilight-processed` → JSON couleurs
- [ ] Container `ambisync` logs : "polling ... at 5 Hz"
- [ ] Jouer vidéo colorée sur TV → ampoules Hue suivent les couleurs (<500ms lag)
- [ ] Firestick : Projectivy au boot, zéro carrousel Amazon
- [ ] Pi-hole query log montre domaines Amazon bloqués depuis IP Firestick
- [ ] HA détecte Hue bridge + TV Philips automatiquement

---

## Compromis et notes

- **Tour PAS H24** → sync Ambilight→Hue actif uniquement quand PC allumé. Fallback futur = RPi Zero 2 W dédié (~20€).
- **JointSPACE** peut être fermé sur firmware Philips 2024+ → fallback ADB Android TV.
- **Root Firestick 4K 2023+** : bootloader probablement signé, root pas garanti. Le debloat ADB couvre 95% des besoins.
- **OLED burn-in** : éviter HDR peak max permanent sur contenu statique.
