# Suivi projet — Home automation Philips + Firesticks + Hue + OpenRGB

Fichier de reprise. Dernière mise à jour : 2026-04-06 soir.

---

## Où on en est

**Phase 0 — Plan & Code** ✅ TERMINÉ
**Phase 1 — TV + Hue + Bypass** ✅ FONCTIONNEL (ampoule + LEDs PC sync Ambilight, Zigbee stable, Ambilight mode Vif)
**Phase 2 — Stack Docker** ✅ TERMINÉ (HA + Pi-hole + Mosquitto)
**Phase 2b — Home Assistant config** ✅ HACS + intégrations + 5 automations
**Phase 3 — Firesticks** 🔶 HD cuisine FAIT, 4K sœur À FAIRE
**Phase 4 — LEDs boîtier PC via OpenRGB** ✅ FONCTIONNEL (sync unifié Hue + OpenRGB, couleurs boostées, zone la plus saturée)
**Phase 5 — Calibrage image TV** ✅ FAIT via API JointSPACE (Filmmaker Mode)
**Phase 6 — Écosystème chambre** ⏳ Govee strip TV + 2 lampes boule à acheter
**Réseau — Mesh WiFi** ⏳ COMMANDÉ (amélioration réseau global + bridge Hue Ethernet chambre)

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
| pihole | pihole/pihole:latest | UP | DNS blocker, 38 domaines custom |
| mosquitto | eclipse-mosquitto:2 | UP | MQTT broker |
| ambisync | infra-home-ambisync | **STOPPÉ** | Remplacé par service systemd unifié |

### Services systemd
| Service | Statut | Rôle |
|---|---|---|
| `openrgb-server.service` | active, enabled | OpenRGB SDK server port 6742 |
| `ambilight-sync.service` | active, enabled | Sync unifié Ambilight → Hue + OpenRGB |
| ~~`openrgb-sync.service`~~ | disabled | Ancien sync séparé, remplacé |

---

## Credentials et IPs

| Device | IP | Port | Auth |
|---|---|---|---|
| TV Philips 55OLED708 | 192.168.1.26 | ADB:5555, JointSPACE:1925(HTTP)/1926(HTTPS) | voir `scripts/.env.jointspace` |
| Bridge Hue | 192.168.1.59 | 80 | voir `ambisync_config/config.yml` |
| Tour GPU (Pi-hole/HA) | 192.168.1.32 | HA:8123, Pi-hole:8081, MQTT:1883, OpenRGB:6742 | voir `.env` |
| Firestick HD cuisine | 192.168.1.13 | ADB:5555 | — |
| Firestick 4K sœur | ? | ? | — |
| Livebox W7 | 192.168.1.1 | 80/443 | voir admin Livebox |

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
│   ├── Dockerfile.ambisync                       # image Docker sync (plus utilisé)
│   └── .env.jointspace                           # credentials TV (chmod 600)
├── ambisync_config/
│   └── config.yml                                # config sync : IPs, tokens, mapping, poll_hz
├── pihole/
│   ├── custom-blocklist.txt                      # ~45 domaines Amazon/Philips/Google
│   └── etc-pihole/                               # data Pi-hole (auto-généré)
├── mosquitto_config/
│   └── mosquitto.conf                            # broker MQTT local
├── ha_config/
│   ├── configuration.yaml                        # config HA + shell_commands ADB
│   ├── automations.yaml                          # 5 automations (TV ON/OFF, mode nuit)
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

### Priorité 1 — Mesh WiFi (COMMANDÉ)
- [x] Mesh commandé (modèle à confirmer — Deco BE63 ou XE75 Pro)
- [ ] **À la réception** : nœud salon (Ethernet Livebox) + nœud chambre + nœud cuisine
- [ ] Désactiver WiFi Livebox via API
- [ ] Brancher bridge Hue en Ethernet sur nœud chambre
- [ ] Configurer Pi-hole comme DNS sur le mesh (si le mesh le permet, sinon par device)

### Priorité 2 — Écosystème lumière chambre
- [ ] Acheter **Govee WiFi LED strip TV** (~25-35€) — IMPORTANT : prendre version **WiFi** pas Bluetooth ! [Ce modèle](https://www.amazon.fr/Govee-Lumineuse-R%C3%A9tro%C3%A9clairage-Bluetooth-Fonctionne/dp/B0C3VF8ZP3) ou chercher "Govee WiFi LED strip" avec mention Alexa
- [ ] Acheter **2x lampe boule verre E27** (~25€) — IKEA FADO 15€/pièce ou équivalent Amazon
- [ ] Intégrer Govee dans HA via HACS (intégration Govee)
- [ ] Placer lampes de chaque côté TV, strip sous/derrière TV
- [ ] Brancher 2ème ampoule Hue dans la 2ème lampe boule

### Priorité 3 — Firestick 4K sœur
- [ ] Obtenir accord sœur
- [ ] Dev mode + ADB + debloat + Projectivy + DNS Pi-hole (même procédure que HD)

### Priorité 4 — Finitions HA
- [ ] Supprimer intégration HACS `philips_ambilight_hue` (ne marche pas)
- [ ] Dashboard Lovelace : cartes TV + Hue + Ambilight + Firesticks
- [ ] Mapper boutons télécommande Hue dimmer switch (4 boutons → actions custom)
- [ ] Automations avancées quand Zigbee stable : scènes "film", "coucher", réveil progressif

### Futur
- [ ] Jellyfin server sur tour GPU → Firesticks/TV consomment le média perso
- [ ] RPi en bridge DNS transparent (bypass verrouillage DNS Livebox pour tout le réseau)
- [ ] Hue Entertainment API (DTLS UDP streaming, latence <50ms vs REST 200ms actuel)
- [ ] Tester sync OpenRGB par zones séparées (quand mesh = latence basse)
- [ ] Acheter 2ème support E27 pour lampe 2

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
- Runbook : `/home/yaniss/infra-home/README.md`
- Mémoire projet : `/home/yaniss/.claude/projects/-home-yaniss/memory/project_home_automation.md`
- Doc réseau/Livebox API : `/home/yaniss/docs/reseaux-config.md`
- XDA System User exploit : https://xdaforums.com/t/system-user-fire-cube-stick-tv-tablet-ps7704-fireos7-rs8149-fireos8.4759215/
- AFTVnews exploit patché : https://www.aftvnews.com/amazon-patches-fire-tv-exploit-that-allows-custom-launchers-disabling-updates-and-more/
- TP-Link Deco BE63 : https://www.amazon.fr/TP-Link-Tri-Band-Deco-BE63-s6-Stream/dp/B0CN8QLS4K
- TP-Link Deco XE75 Pro : https://www.amazon.fr/TP-Link-Deco-XE75-Pro-3-pack/dp/B0BBV18ZD4
- Dong Knows Tech mesh reviews : https://dongknows.com/best-five-wi-fi-7-mesh-systems/
