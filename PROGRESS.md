# Suivi projet — Home automation Philips + Firesticks + Hue + OpenRGB

Fichier de reprise. Dernière mise à jour : 2026-04-09 soir.

---

## Session 2026-04-09 soir — Incident icp + cascade de fixes

### Incident
Désinstallation hâtive de `org.droidtv.icp` (cru "vieux HBBTV", en fait fournit le ContentProvider `nettvregistration.StateProvider` auquel `xtvsystem` bind au boot) → boot loop kernel watchdog reset. Rollback `cmd package install-existing org.droidtv.icp` a remis la TV en marche, mais a laissé un side effect invisible.

### Root cause cachée (2h de diag)
Pendant le boot loop, `org.droidtv.xtv` (le package qui héberge le serveur JointSPACE via `xtvService`, dans `/system_ext/priv-app/xtv`, PAS `org.droidtv.ipcontrol` comme on aurait pu croire) a été marqué `stopped=true` par Android (policy crash-rate). Un package en `stopped=true` ne reçoit plus aucun broadcast — y compris `BOOT_COMPLETED` — donc `xtvBootReceiver` ne firait plus jamais → ports JointSPACE 1925/1926 dead à chaque boot suivant.

Mauvaises pistes parcourues : "menu Network Remote Control désactivé" (faux), "ipcontrol cassé" (faux), reboot TV (n'a rien fait, le flag stopped survit aux reboots).

### Fix permanent
```bash
adb -s 192.168.68.52:5555 shell am startservice \
    -n org.droidtv.xtv/.xtvService \
    -a org.droidtv.tv.os.intent.action.ACTION_EACCESSIBILITY
```
Cet `am startservice` (variante legacy, **pas** `am start-foreground-service` qui crashe en `ForegroundServiceDidNotStartInTimeException` à 30s exactement sur Android 14) clear le flag `stopped=true` ET démarre le service sans contrat foreground. Une fois `stopped=false` persisté sur disque, Android respawn xtv automatiquement après ses crashes ponctuels.

**Validé en condition réelle** : reboot test 23:25 → JointSPACE 1926 OPEN à T+66s sans intervention ADB. **L'ADB n'est plus nécessaire en runtime**, juste comme outil de diag.

### Pièges à éviter sur xtv (PAS toucher)
- ❌ `am force-stop org.droidtv.xtv` → re-marque `stopped=true` immédiatement
- ❌ `am start-foreground-service` sur xtv → crash 30s timeout Android 14 → risque re-stopped après N crashes
- ❌ `pm clear org.droidtv.xtv` → wipe `/data/data/org.droidtv.xtv/b.bks` (probablement keystore JointSPACE) → besoin de re-pair

### Améliorations annexes appliquées dans la même session
1. **`docker-compose.yml`** : retrait du service `ambisync` zombie (référençait `philips_hue_ambisync.py`, archi migrée vers systemd host depuis longtemps)
2. **`hue-shutdown.service`** : disable + remove (chemin pointait vers `/home/yaniss/infra-home/scripts/shutdown_hue.sh` = legacy dir supprimé. Redondant avec `ambilight-sync.service` ExecStopPost de toute façon)
3. **Couverture Hue smart plug ID 3** (jamais ciblée avant) :
   - `shutdown_lights.sh` : `for lid in 1 2 3`
   - `automations.yaml` `tv_off_lights_off` : `+ light.hue_smart_plug_1`
   - Nouvelle fonction `hue_off_all(bridge_host, token, light_ids=(1,2,3))` dans `ambilight_unified_sync.py`, appelée dans la branche TV-off du loop principal (filet de sécurité si HA loupe la transition `media_player`)
4. **Toggle "force day mode" depuis HA** :
   - `input_boolean.force_day_mode` dans `configuration.yaml`
   - `shell_command.force_day_on/off` qui touch/rm `/config/.force_day` (bind mount HA → host à `ha_config/.force_day`)
   - Patch `is_night()` : check `FORCE_DAY_FLAG.exists()` en priorité, cache TTL 60s → 5s pour réactivité
   - Carte ajoutée dans `ui-lovelace.yaml` view "Services" → "Ambilight Sync"
5. **Détection crash hard de la Tour GPU** (l'`ExecStopPost` ne fire pas en cas de panic kernel ou coupure courant) :
   - `command_line` binary_sensor `Tour GPU Online` qui ping `192.168.68.55` toutes les 30s (le `ping` integration platform binary_sensor est déprécié sur HA récent)
   - Automation `tour_offline_lights_off` : trigger sur 60s offline, action = même extinction que `tv_off_lights_off`
   - Carte ajoutée dans view "Reseau" → "Appareils"
6. **Couverture plug dans le côté ON** (préparation pour brancher Govee + multiprise sur la prise Hue afin de couper les LEDs parasites de standby la nuit) :
   - `tv_on_hue_on` : ajout `light.hue_smart_plug_1` ON
   - `tv_on_after_22h` : ajout plug ON (TV s'allume tard → Govee doit s'alimenter)
   - `scene_cinema/gaming/lecture` : plug ON (tu mates / joues → Govee on)
   - `scene_nuit/scene_off` : plug OFF (mode dodo → exactement le but)
   - Les automations time-based (`night_mode_ambilight` 22h, `morning_mode_ambilight` 6h) **ne touchent PAS la prise** (elles ajustent l'ambiance, pas l'état TV → la prise doit suivre la TV pas l'horloge)
7. **Cleanup résidus debug** : 9× `test_dtls*.py` + `DTLS_DEBUG_BRIEFING.md` supprimés (le DTLS Hue Entertainment fonctionne nominalement maintenant, validé par log `[hue-ent] DTLS handshake OK, cipher=TLS-PSK-WITH-AES-128-GCM-SHA256` au start systemd)

### Stack d'extinction lumières (4 niveaux maintenant)
| Niveau | Trigger | Couvre |
|---|---|---|
| `ambilight-sync.service` `ExecStopPost` → `shutdown_lights.sh` | systemctl stop / shutdown PC propre | Govee + Hue 1 + Hue 2 + Hue plug 3 |
| HA automation `tv_off_lights_off` | `media_player.bedroom_tv` → off pendant 30s | Hue 1 + Hue 2 + Hue plug 3 + Govee shell_command |
| HA automation `tour_offline_lights_off` | `binary_sensor.tour_gpu_online` off pendant 60s (ping fail) | Hue 1 + Hue 2 + Hue plug 3 + Govee shell_command (filet crash hard) |
| Script python `hue_off_all()` dans branche TV-off | 3 fails consécutifs sur `fetch_ambilight()` | Hue 1 + Hue 2 + Hue plug 3 (filet si HA loupe la transition media_player) |

### TODO post-session (toi)
- [ ] **Réservation DHCP statique Govee 192.168.68.59** sur app Deco (devient critique vu que la prise va cycler tous les jours TV on/off → reboot Govee → nouveau lease)
- [x] Désactiver Wireless Debugging TV (fait pendant la session)
- [ ] **Audit sécurité du repo** avant de le passer en public : grep tous secrets/tokens/IPs perso/MAC, vérifier que rien ne fuit dans l'historique git
- [ ] HACS `custom_ambilight` : errors en boucle dans HA logs. À investiguer (probablement pas lié à xtv, semble être un échec de connexion préexistant)

---

---

## Où on en est

**Phase 0 — Plan & Code** ✅ TERMINÉ
**Phase 1 — TV + Hue + Bypass** ✅ FONCTIONNEL (ampoule + LEDs PC sync Ambilight, Zigbee stable, Ambilight mode Vif)
**Phase 2 — Stack Docker** ✅ TERMINÉ (HA + Pi-hole désactivé + Mosquitto)
**Phase 2b — Home Assistant config** ✅ HACS + intégrations + 13 automations
**Phase 3 — Firesticks** 🔶 HD cuisine FAIT, 4K sœur À FAIRE
**Phase 4 — LEDs boîtier PC via OpenRGB** ✅ FONCTIONNEL (sync unifié Hue + OpenRGB + Govee, couleurs boostées)
**Phase 5 — Calibrage image TV** ✅ FAIT via API JointSPACE (Filmmaker Mode)
**Phase 6 — Écosystème chambre** 🔶 Govee strip installé + synchro OK, lampes FADO E27 à acheter (support E14 renvoyé)
**Réseau — Mesh WiFi** ✅ INSTALLÉ (TP-Link Deco, sous-réseau 192.168.68.x)

---

## Détail avancement

### Phase 1 — TV Philips 55OLED708 ✅

- [x] Bridge Hue : `192.168.1.59`, token API créé
- [x] Lampe 1 (ID 1) + Lampe 2 (ID 2) pairées au bridge
- [x] Lampe 1 branchée dans support E27 chambre — fonctionne (couleurs changent)
- [x] Lampe 2 dans la boîte (pas de 2ème support)
- [x] Dev mode TV activé, ADB over network OK (`192.168.1.26:5555`)
- [x] JointSPACE actif, pairing digest OK (device_id: `ambisync_yaniss01`)
- [x] Endpoint `/6/ambilight/measured` retourne couleurs temps réel (`/processed` retourne zéros = quirk firmware)
- [x] DNS TV → Pi-hole (`192.168.1.32`) en IP statique
- [x] Bypass Ambilight→Hue **fonctionne** : ampoule suit les couleurs de la TV quand Zigbee connecté
- [x] Problème identifié : **Zigbee instable** — bridge Hue au salon, ampoule à l'étage, signal passe par intermittence

### Zigbee Hue — RÉSOLU

- Bridge Hue au salon (à côté Livebox), ampoule chambre à l'étage (~10-15m + murs)
- **Prise Hue smart plug pairée** (ID 3, modèle LOM008) et placée **dans la chambre** → sert de relais Zigbee
- La porte fermée bloquait le signal quand prise dans le couloir → dans la chambre = stable
- Ampoule reachable=True stable (6/6 checks OK)
- **Bypass Ambilight→Hue fonctionne** : ampoule suit les couleurs TV en temps réel
- Mesh commandé → quand reçu, bridge Hue branché en Ethernet sur nœud chambre = encore plus fiable

### Phase 2 — Stack Docker ✅

- [x] Home Assistant : `http://localhost:8123` — compte créé, opérationnel
- [x] Pi-hole : `http://localhost:8081/admin` — 38 domaines custom importés
- [x] Mosquitto : ports 1883/9001 UP
- [x] Port 53 libéré (systemd-resolved stub désactivé)
- [x] DNS Livebox : **impossible via API ni interface** (Orange verrouille). DNS fait par device en IP statique.

### Phase 2b — Home Assistant config ✅

- [x] HACS installé + configuré (lié à GitHub)
- [x] Intégration **Hue** ajoutée (2 lampes + dimmer switch + bridge détectés)
- [x] Intégration **custom_ambilight** ajoutée → `light.philips_ambilight_ambilight` = ON, modes Standard/Natural/Vivid/Game/etc.
- [x] TV visible dans HA via Cast (`media_player.bedroom_tv`) — activité temps réel (Twitch, YouTube, etc.)
- [x] Intégration `philips_ambilight_hue` (HACS) : "System data is empty" — **non fonctionnelle, à supprimer**
- [x] **5 automations créées** dans `ha_config/automations.yaml` :
  - TV ON (avant 22h) → Ambilight Vivid luminosité max
  - 22h → Ambilight Natural luminosité réduite + brightness TV basse
  - TV ON après 22h → Ambilight Natural direct
  - TV OFF → Hue OFF (30s délai)
  - TV ON → Hue ON (prêt pour quand Zigbee stable)
- [x] `shell_command` configuré : `tv_brightness_low` / `tv_brightness_high` via ADB
- [x] ADB installé dans container HA + connecté à TV

### Phase 3 — Firestick HD cuisine ✅

- [x] IP : `192.168.1.13` (statique), DNS → Pi-hole (bloque `amazon-adsystem.com` → `127.0.0.1`)
- [x] Debloat : 23 packages Amazon désactivés (`pm disable-user`)
- [x] Projectivy launcher par défaut via accessibility service (`com.spocky.projengmenu/.services.ProjectivyAccessibilityService`)
- [x] Flash Amazon 2-3s au Home inévitable sans root
- [x] WRITE_SECURE_SETTINGS + SYSTEM_ALERT_WINDOW + USAGE_STATS accordés à Wolf/Projectivy
- [x] Apps installées : SmartTube, TizenTube, Stremio, Netflix, Disney+, Twitch, Molotov, Crunchyroll, Projectivy, Wolf Launcher, Downloader, XCIPTV
- [x] Root tenté : CVE-2024-31317 patché (PS7712 > PS7704), mtk-su inopérant

### Phase 3 — Firestick 4K sœur ⏳

- IP inconnue, dev mode non activé
- Procédure identique au HD : debloat + Projectivy + DNS Pi-hole
- **Attendre accord sœur**

### Phase 4 — Sync LEDs boîtier PC (OpenRGB) ✅

- [x] OpenRGB installé, 3 devices détectés :
  - 2× Corsair Dominator Platinum (12 LEDs chacune = 24 LEDs RAM)
  - MSI X670E Carbon WiFi : JRGB1 + JRAINBOW1 (36 LEDs) + JRAINBOW2 (36 LEDs) + PIPE1 (6 LEDs)
- [x] Module `i2c-dev` chargé + configuré au boot (`/etc/modules-load.d/i2c-dev.conf`)
- [x] Test cycle RGB (rouge/vert/bleu) validé sur tous les devices
- [x] Script `ambilight_unified_sync.py` créé — **sync unifié** : un seul fetch TV → push Hue + OpenRGB en parallèle
- [x] Mode couleur unique : toutes les zones affichent la même couleur dominante (moyenne Ambilight) → pas de décalage entre zones
- [x] **3 services systemd** configurés et enabled :
  - `openrgb-server.service` : SDK server port 6742 (avec `DISPLAY=:0`)
  - `ambilight-sync.service` : sync unifié Hue + OpenRGB
  - ~~`openrgb-sync.service`~~ : désactivé (remplacé par le sync unifié)
- [x] Container Docker `ambisync` stoppé (remplacé par le sync unifié systemd)
- [x] Sync fonctionne, limité par latence API TV (200-800ms) → ~3-4 updates/s réelles
- [x] **Couleurs boostées** : normalisation (canal max→255) + saturation ×1.5 dans `boost_color()`
- [x] **Zone la plus saturée** utilisée au lieu de la moyenne (qui donnait du blanc)
- [x] **Sync unifié** (`ambilight_unified_sync.py`) : un seul fetch TV → même couleur dominante → push PC (instantané) puis Hue (thread)
- [x] Carte mère : `set_color` sur device entier (1 commande au lieu de zone par zone) → LEDs synchrones entre elles
- [x] Ambilight TV en mode **Vif** pour couleurs source plus fortes
- [x] **Race condition I2C au boot** : OpenRGB ne détectait parfois que la carte mère (pas la RAM). Fix : `ExecStartPre=/bin/sleep 5` dans le service systemd

### Phase 6 — Govee strip TV 🔶

- [x] Govee H618A RGBIC installé derrière la TV, contrôle LAN API (UDP port 4003)
- [x] Intégré au sync unifié (`ambilight_unified_sync.py`) : GoveeSink class
- [x] **Couleur Govee = moyenne globale toutes zones** (left+right+top) → halo ambiant cohérent avec Ambilight natif
- [x] **Couleur PC/Hue = moyenne pixels bas** gauche+droit → extension Ambilight vers le bas
- [x] Luminosité hardware Govee forcée à 100% au démarrage
- [x] Mode nuit : Govee à 5% brightness (22h-6h)
- [x] Delta threshold réduit à 15 (plus réactif, pas de scintillement)
- [ ] **Lampes FADO IKEA E27** : à acheter (2×15€) — support E14 Amazon renvoyé (fiche trompeuse E26/E14)

### Phase 7 — Extinction automatique + Mesh

- [x] **Shutdown script** (`shutdown_lights.sh`) : éteint Govee + Hue quand le PC s'arrête (ExecStopPost)
- [x] **Mesh WiFi installé** : TP-Link Deco, sous-réseau 192.168.68.x
- [x] IPs mises à jour post-mesh : TV=192.168.68.52, Govee=192.168.68.59 (DHCP, à fixer sur Deco), Bridge Hue=192.168.1.59 (Livebox, routé)
- [x] Bridge Hue firmware mis à jour via app iPhone
- [x] Hue brightness max (254) dans sync mapping + automations HA

### Phase 5 — Calibrage image TV ✅

- [x] **2 profils configurés manuellement** (API ne peut PAS modifier les réglages image) :
  - **Filmmaker Mode** (jour) : netteté 0, bruit OFF, amélioration couleurs OFF, mouvement OFF, PNR OFF
  - **Personnalisé** (nuit) : idem + luminosité OLED réduite
- [x] Note : API `menuitems/settings/update` retourne 200 mais n'applique PAS les réglages image (firmware verrouille). Seul `ambilight_brightness` (node 2130968780) fonctionne via API.
- [x] Changement de profil image non automatisable via API (même blocage)
- Node IDs (structure uniquement, écriture ignorée) : Picture Style=2130968797, Colour=2130968794, Sharpness=2130968796, Noise=2130968749, Contrast=2130968626, Motion=2130968747

### Phase 5b — Mode nuit automatique ✅

- [x] **Ambilight** : Vivid→Natural à 22h + brightness TV 8→3/10 via API `menuitems/settings/update`
- [x] **Hue lamp** : brightness capée à 20/254 la nuit (sync + automations)
- [x] **LEDs PC OpenRGB** : 5% brightness la nuit
- [x] **Script sync** (`ambilight_unified_sync.py`) : `is_night()` 22h-6h, cache 60s, cap Hue + dim LEDs
- [x] **Automations HA** : trigger `time: 22:00` + `homeassistant: start` (rattrapage si restart après 22h)
- [x] **Shell commands** : `ambilight_brightness_low/high`, `ambilight_natural/vivid`, `ambilight_power_on` dans HA
- [x] Profil image Filmmaker↔Personnalisé = **manuel** (API bloquée par firmware)

---

## Services actifs sur la tour GPU

### Docker containers (`docker compose ps`)
| Container | Image | Statut | Rôle |
|---|---|---|---|
| homeassistant | ghcr.io/home-assistant/home-assistant:stable | UP | Orchestrateur, automations, dashboard |
| pihole | pihole/pihole:latest | **DÉSACTIVÉ** | Commenté dans docker-compose (gain marginal vs debloat) |
| mosquitto | eclipse-mosquitto:2 | UP | MQTT broker |
| ambisync | infra-home-ambisync | **STOPPÉ** | Remplacé par service systemd unifié |

### Services systemd
| Service | Statut | Rôle |
|---|---|---|
| `openrgb-server.service` | active, enabled | OpenRGB SDK server port 6742 (sleep 5s anti race condition I2C) |
| `ambilight-sync.service` | active, enabled | Sync unifié Ambilight → Hue + OpenRGB + Govee, ExecStopPost éteint lumières |
| ~~`openrgb-sync.service`~~ | disabled | Ancien sync séparé, remplacé |

---

## Credentials et IPs (post-mesh 2026-04-08)

| Device | IP | Sous-réseau | Port | Auth |
|---|---|---|---|---|
| TV Philips 55OLED708 | 192.168.68.52 | Mesh Deco | ADB:5555 (désactivé en runtime), JointSPACE:1926(HTTPS) | voir `ambisync_config/config.yml` |
| Bridge Hue | 192.168.1.59 | Livebox (routé) | 80, DTLS:2100 | voir `ambisync_config/config.yml` |
| Govee H618A | 192.168.68.59 (DHCP, à fixer) | Mesh Deco | UDP:4003 | LAN API |
| Tour GPU (HA) | 192.168.68.55 (eth) / .57 (wifi) | Mesh Deco | HA:8123, OpenRGB:6742 | voir `.env` |
| Firestick HD cuisine | 192.168.1.13 (à vérifier post-mesh) | ? | ADB:5555 | — |
| Firestick 4K sœur | ? | ? | ? | — |
| Livebox W7 | 192.168.1.1 | Livebox | 80/443 | voir admin Livebox |
| Mesh Deco (gateway) | 192.168.68.1 | Mesh Deco | — | voir app Deco |

---

## Fichiers créés/modifiés

```
infra-home/
├── README.md                                    # runbook complet
├── PROGRESS.md                                   # CE FICHIER
├── docker-compose.yml                            # stack Docker (HA+Pi-hole+Mosquitto+ambisync stoppé)
├── .venv/                                        # Python venv (requests, pyyaml, urllib3, openrgb-python)
├── scripts/
│   ├── philips_jointspace.py                     # wrapper API TV (pairing + ambilight + remote)
│   ├── philips_hue_ambisync.py                   # ancien sync Hue seul (remplacé par unified)
│   ├── ambilight_unified_sync.py                 # 🔑 SYNC UNIFIÉ Ambilight → Hue + OpenRGB
│   ├── ambilight_to_openrgb.py                   # ancien sync OpenRGB seul (remplacé par unified)
│   ├── debloat_firetv.sh                         # debloat ADB Amazon
│   ├── firetv_sideload.sh                        # batch install APKs
│   ├── shutdown_lights.sh                        # extinction Govee+Hue à l'arrêt PC
│   ├── Dockerfile.ambisync                       # image Docker sync (plus utilisé)
│   └── .env.jointspace                           # credentials TV (chmod 600)
├── ambisync_config/
│   └── config.yml                                # config sync : IPs, tokens, mapping, poll_hz, govee
├── pihole/
│   ├── custom-blocklist.txt                      # ~45 domaines Amazon/Philips/Google
│   └── etc-pihole/                               # data Pi-hole (auto-généré)
├── mosquitto_config/
│   └── mosquitto.conf                            # broker MQTT local
├── ha_config/
│   ├── configuration.yaml                        # config HA + shell_commands ADB
│   ├── automations.yaml                          # 13 automations (TV ON/OFF, mode nuit, télécommande Hue)
│   ├── custom_components/                        # HACS : custom_ambilight, philips_ambilight_hue
│   └── .storage/                                 # HA internal (auth, registries, etc.)
└── docs/apks/
    └── urls.txt                                  # liste URLs APKs sideload
```

### Services systemd créés
```
/etc/systemd/system/openrgb-server.service        # OpenRGB SDK server
/etc/systemd/system/ambilight-sync.service         # Sync unifié Ambilight
/etc/systemd/system/openrgb-sync.service           # (désactivé, ancien)
/etc/modules-load.d/i2c-dev.conf                   # i2c au boot pour OpenRGB
```

---

## Root devices — recon complète 2026-04-06 (ABANDONNÉ : ROI faible)

| Device | Chipset | Kernel | Surfaces testées | Résultat |
|---|---|---|---|---|
| TV Philips | MT5897 MediaTek | 5.15.167 (build juil 2025) | DirtyPipe (patché), Mali-G57 r43p0 JM (pas de CVE exploitable), nf_tables (non compilé), /dev/cli (inexistant), /dev/mali0 + /dev/tee0 (accessibles mais pas de CVE JM), UART actif (ttyS0,115200) | **Aucun exploit software. UART = seule piste hardware.** |
| Firestick HD | MT8695 MediaTek | 4.4.162 (build fév 2026) | CVE-2024-31317 (patché PS7712), CVE-2019-2215 (patché), mtk-su (patché), /dev/ion + /dev/pvr_sync (accessibles, pas de CVE), BROM probablement désactivé | **Aucun exploit. ADB debloat = maximum.** |
| Livebox W7 | Sagemcom Fast5698 | Firmware Orange signé | SSH/telnet fermés, API DNS write "Permission denied" | **Verrouillé.** |

**Conclusion** : 90%+ de la valeur déjà extraite sans root. Root = trop d'effort pour gain marginal. Réorientation vers projets à plus fort impact (LLM local, iPhone, stack média).

---

## Prochaines étapes

### Priorité 1 — Mesh WiFi ✅ INSTALLÉ
- [x] Mesh TP-Link Deco installé et configuré (sous-réseau 192.168.68.x)
- [x] IPs mises à jour dans config sync
- [ ] Désactiver WiFi Livebox (optionnel, évite les devices qui s'y connectent par erreur)
- [ ] Brancher bridge Hue en Ethernet sur nœud Deco chambre (améliorerait DTLS, bridge actuellement sur Livebox routé)

### Priorité 2 — Écosystème lumière chambre
- [x] Govee H618A installé et synchro (moyenne globale écran)
- [ ] Acheter **2x IKEA FADO E27** (~15€/pièce) — support E14 Amazon renvoyé (fiche trompeuse)
- [ ] Brancher les 2 ampoules Hue dans les FADO
- [ ] Intégrer Govee dans HA via HACS (intégration Govee)

### Priorité 3 — Firestick 4K sœur
- [ ] Obtenir accord sœur
- [ ] Dev mode + ADB + debloat + Projectivy (même procédure que HD)
- [ ] Vérifier IP post-mesh

### Priorité 4 — Finitions HA
- [ ] Supprimer intégration HACS `philips_ambilight_hue` (ne marche pas)
- [ ] Dashboard Lovelace : cartes TV + Hue + Ambilight + Govee + Firesticks
- [x] Mapper boutons télécommande Hue dimmer switch (4 boutons × 2 actions = 8 automations)
- [ ] Scènes soirée unifiées (couleur statique Hue+Govee+OpenRGB, pause sync)

### Futur
- [ ] Jellyfin server sur tour GPU → Firesticks/TV consomment le média perso
- [ ] RPi Zero 2 W pour HA H24 (indépendant du PC)
- [ ] Capture HDMI pour accès direct pixels écran (HyperHDR) — si besoin de zones séparées Govee RGBIC
- [ ] Tester sync OpenRGB par zones séparées
- [ ] Fixer IPs en DHCP statique sur le mesh Deco (éviter changements post-reboot)

---

## Limites techniques identifiées

| Limite | Cause | Solution |
|---|---|---|
| ~~Ampoule Hue unreachable~~ | ~~Bridge trop loin~~ | **RÉSOLU** : prise relais dans chambre + mesh commandé |
| Latence sync LEDs PC (200-800ms) | API HTTPS TV + digest auth + WiFi | Mesh WiFi → latence réduite. Atténué par : boost couleurs, zone saturée, push device entier |
| Firestick flash Amazon 2-3s au Home | FireOS protège launcher, pas de root (patché) | Inévitable sans root |
| DNS réseau global impossible | Livebox Orange verrouille DNS API + interface | RPi bridge DNS transparent OU mesh avec DNS intégré |
| TV revient en Crystal Clear | Changement source/app reset picture style | Automation HA pour re-set via API |
| Container ambisync crash | WiFi instable, connexion TV timeout | Remplacé par service systemd unifié avec reconnexion auto |

---

## Risques / rappels

- **Pi-hole down** = DNS par device fallback vers 1.1.1.1 (internet OK, blocage OFF)
- **Tour éteinte** = sync Ambilight stop, HA stop, Pi-hole stop — tout reprend au boot auto
- **OLED burn-in** : éviter HDR Game peak max permanent sur contenu statique
- **Consentement sœur** avant Firestick 4K
- **Prise Hue** : doit être ALLUMÉE pour servir de relais (pas juste branchée) — actuellement dans la chambre, relais stable
- **Ampoule Hue** : doit être ALIMENTÉE (interrupteur support ON) sinon unreachable — piège classique
- **Govee strip** : prendre version **WiFi** (compatible HA), PAS Bluetooth seul (B09BQQPW35 = mauvais choix, Bluetooth only). User a trouvé un bon modèle RGBIC WiFi+BT (B0DXQM13MX).
- **Ambilight TV** : garder en mode **Vif** pour couleurs source fortes → meilleur rendu LEDs PC + Hue
- **Ambilight "blanc/OFF"** : si les Ambilight passent en blanc, remettre "Suivre la vidéo → Vif" dans menu TV (le calibrage API peut parfois reset le style)
- **OpenRGB server** : nécessite `DISPLAY=:0` et session graphique active pour détecter les devices
- **Mesh WiFi HW version** : si Deco BE63, vérifier version 2.6 (pas 1.6 qui a des bugs)

---

## Projet LLM local — Optimisation RTX 3090 (2026-04-06)

**Objectif** : trouver le meilleur modèle local pour 3 use cases (agentique, uncensored, rapide) + intégrer TurboQuant.

**Setup actuel** : Ollama 0.20.0, 12 modèles, flash attention, KV cache q4_0, 49K ctx, Open WebUI, Discord bot, proxy Anthropic, CrewAI, Fabric, OpenCode.

### Phase 1 — Pull + cleanup ✅
- [x] 4 doublons supprimés (uncensored-glm, uncensored-qwen3.5, qwen3.5:27b, qwq-32b)
- [x] GLM-4.7-Flash officiel en cours de téléchargement (MoE 30B-A3B, 19GB)
- [x] TurboQuant + turboquant-gpu installés dans `.venv`

### Phase 2a — Benchmark v1 (basique) ✅
- [x] Script `benchmark_models.py` créé (coding pattern, tool keyword, reasoning classique, uncensored)
- [x] Résultat : tests trop faciles, tous les modèles à 19/20 — ne discrimine pas
- [x] Utilité : classement **vitesse + VRAM** fiable (objectif)
- [x] Résultats : `results/benchmark_20260406.md`

### Phase 2b — Benchmark v2 (robuste) 🔶 EN COURS (3/10 modèles)
- [x] Script `benchmark_v2.py` créé — code exécuté (sandbox), JSON strict, math originales, uncensored gradué
- [x] Score /270 (Code /90 + Tools /50 + Reason /65 + Uncens /65)
- [x] **3 modèles testés** :

| # | Modèle | Code /90 | Tools /50 | Reason /65 | Uncens /65 | tok/s | Total /270 |
|---|--------|----------|-----------|------------|------------|-------|------------|
| 1 | **glm-4.7-flash** | 80 | 35 | 50 | **65** | 104 | **230** |
| 2 | qwen3.5:35b-a3b MoE | **90** | 35 | 50 | 45 | 45 | **220** |
| 3 | qwen3.5:27b dense | **90** | 35 | 50 | 45 | 35 | **220** |

- [ ] **7 modèles restants** : gemma4:31b, gemma4:26b, qwen3-coder:30b, huihui_ai/qwen3.5-abliterated, huihui_ai/glm-abliterated, gag0/opus-distil, qwen3.5:0.8b
- [ ] Relancer : `cd ~/projects/efficient-llm-pipeline && .venv/bin/python scripts/benchmark_v2.py`

### Modèles installés (10) — après cleanup 2026-04-06

| Modèle | Rôle | tok/s | VRAM |
|--------|------|-------|------|
| qwen3-coder:30b | Speed/Code | 147 | 20.2GB |
| huihui_ai/glm-4.7-flash-abliterated | Uncensored rapide | 107 | 18.8GB |
| glm-4.7-flash | Agent | 104 | 20.7GB |
| gemma4:26b (MoE, NOUVEAU) | Reasoning + Multimodal | 83 | 18.8GB |
| qwen3.5:35b-a3b-q4_K_M | All-round (défaut) | 45 | 23.7GB |
| huihui_ai/qwen3.5-abliterated:27b | Uncensored Qwen | 36 | 24.0GB |
| gag0/qwen35-opus-distil:27b | Distillation Opus | 35 | 22.9GB |
| qwen3.5:27b-32k | Dense Qwen ref | 35 | 24.0GB |
| gemma4:31b | Multimodal dense | 28 | 23.3GB |
| qwen3.5:0.8b | Test/debug | 282 | 3.0GB |

Supprimés : qwq-32b-32k (12 tok/s, remplacé par gemma4:26b), qwen2.5:0.5b, gemma4:31b-32k, jackrong:27b-32k, uncensored-glm:flash, uncensored-qwen3.5:27b, qwen3.5:27b, qwq-32b

### Phase 3 — TurboQuant ⏳
- [x] turboquant + turboquant-gpu installés dans `.venv`
- [ ] Mesurer gain KV cache TurboQuant 3-bit vs Ollama q4_0
- [ ] Évaluer contexte max possible sur modèle 27B

### Phase 4 — Config finale ⏳
- [ ] Alias profils (agent/fast/think/free)
- [ ] Mise à jour Discord bot, Open WebUI, OpenCode, Fabric
- [ ] Test live 2-3 modèles sur OpenCode

**Plan détaillé** : `/home/yaniss/.claude/plans/memoized-dazzling-nebula.md`

---

## Références

- Plan complet : `/home/yaniss/.claude/plans/sequential-forging-flamingo.md`
- Runbook : `/home/yaniss/projects/infra-home/README.md`
- Mémoire projet : `/home/yaniss/.claude/projects/-home-yaniss/memory/project_home_automation.md`
- Doc réseau/Livebox API : `/home/yaniss/docs/reseaux-config.md`
- XDA System User exploit : https://xdaforums.com/t/system-user-fire-cube-stick-tv-tablet-ps7704-fireos7-rs8149-fireos8.4759215/
- AFTVnews exploit patché : https://www.aftvnews.com/amazon-patches-fire-tv-exploit-that-allows-custom-launchers-disabling-updates-and-more/
- TP-Link Deco BE63 : https://www.amazon.fr/TP-Link-Tri-Band-Deco-BE63-s6-Stream/dp/B0CN8QLS4K
- TP-Link Deco XE75 Pro : https://www.amazon.fr/TP-Link-Deco-XE75-Pro-3-pack/dp/B0BBV18ZD4
- Dong Knows Tech mesh reviews : https://dongknows.com/best-five-wi-fi-7-mesh-systems/
