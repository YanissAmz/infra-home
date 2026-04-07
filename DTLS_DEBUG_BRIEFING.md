# Briefing debug DTLS Entertainment API — Ambilight Sync

## Contexte

Le projet `infra-home` synchronise les couleurs Ambilight de la TV Philips 55OLED708 vers :
- **Hue lamps** (2x Hue Color Lamp, bridge v2 BSB002, API 1.59)
- **OpenRGB LEDs PC** (MSI X670E + Corsair RAM, via SDK port 6742)

Le script principal est `scripts/ambilight_unified_sync.py`.

## Problème

L'Entertainment API (DTLS streaming, ~20ms latence) a été implémentée pour remplacer le REST API (~200-400ms). Le DTLS handshake **réussit**, les paquets **sont envoyés et chiffrés** (vérifié par tcpdump), mais les **lampes Hue ne réagissent pas** aux paquets du service sync.

## Ce qui a été trouvé et corrigé

1. **Cipher suite** : `python-mbedtls` négociait `CHACHA20-POLY1305` par défaut. Le bridge Hue accepte le handshake mais **ne traite pas les données applicatives** avec ce cipher. Fix : forcer `TLS-PSK-WITH-AES-128-GCM-SHA256` via le paramètre `ciphers=` de `DTLSConfiguration`. **Ce fix est appliqué.**

2. **Lampe 2 absente du groupe Entertainment** : seule la lampe 1 était dans le groupe 200. Lampe 2 a été ajoutée. **Ce fix est appliqué.** (Note: lampe 2 = `reachable=False`, problème Zigbee physique séparé.)

3. **Lampes OFF au démarrage du stream** : quand le streaming DTLS prend le contrôle, les lampes doivent être ON. Le code appelle `ensure_lights_on()` avant et après activation. **Ce fix est appliqué.**

4. **Stream résiduel bloquant les REST PUTs** : ajouté `_deactivate_stream()` avant les PUTs de `ensure_lights_on`. **Ce fix est appliqué.**

5. **boost_color v2 trop sombre** : l'algo v2 multipliait par `mx/160` (brightness proportionnelle). Revenu au v1 (toujours max=255, sat_boost 1.5). **Ce fix est appliqué.**

6. **TV power detection flaky** : `is_on()` timeout → idle blue. Remplacé par compteur d'échecs `fetch_ambilight()` (3 échecs consécutifs = TV off). **Ce fix est appliqué.**

7. **Delta threshold** : revenu de 25 à 15. **Appliqué.**

## Ce qui reste à débugger

### Le bug principal : DTLS fonctionne en standalone mais PAS dans le service

**Test standalone qui MARCHE** (`scripts/test_dtls6.py`) :
```python
# Séquence exacte :
requests.put(groups/200, {"stream":{"active":False}})  # deactivate
sleep(1)
requests.put(lights/1/state, {"on":True,"bri":254})     # lights on
sleep(1)
requests.put(groups/200, {"stream":{"active":True}})     # activate
sleep(0.5)
# DTLS handshake (AES-128-GCM) → OK
# Send V2 packets (channel 0+1, full red) → LAMPES CHANGENT DE COULEUR ✓
```

**Service sync qui NE MARCHE PAS** (même cipher, même format de paquets) :
```python
# Dans connect() → _activate_stream() :
_deactivate_stream()         # deactivate
sleep(0.5)                   # ← plus court que le test
ensure_lights_on()           # {"on":True} seulement, pas bri=254
sleep(0.5)                   # ← plus court
activate stream              # PUT groups/200
# _dtls_connect() :
# DTLS handshake (AES-128-GCM) → OK
# ensure_lights_on() APRES handshake (stream actif)
# Send RED test 3s → LAMPES NE CHANGENT PAS ✗
```

### Hypothèses non testées

1. **Timing trop court** : le test a 1s entre chaque étape, le service 0.5s. Le bridge Hue a peut-être besoin de plus de temps pour libérer/activer le stream.

2. **Brightness non settée** : `ensure_lights_on()` envoie `{"on":True}` sans `bri`. Le test envoie `{"on":True,"bri":254}`. Peut-être que la lampe est ON mais à `bri=0` ?

3. **Automations HA qui interfèrent** : certaines automations contrôlent `light.hue_color_lamp_1` directement (lignes 54-58, 86-91, 127-131, 140-144 de `ha_config/automations.yaml`). Elles pourraient éteindre/modifier la lampe entre les étapes du service.

4. **Second `ensure_lights_on()` après handshake** : envoyer un REST PUT pendant que le streaming DTLS est actif pourrait perturber la session. À tester en le retirant.

5. **Epoch/session DTLS** : le bridge pourrait invalider la session DTLS si un REST PUT arrive pendant le streaming. La deuxième `ensure_lights_on()` post-handshake est suspecte.

### Prochaines étapes recommandées

1. **Aligner le timing du service sur le test** : augmenter les sleeps à 1s dans `_activate_stream()`.
2. **Ajouter `bri=254`** à `ensure_lights_on()`.
3. **Retirer le second `ensure_lights_on()`** après le handshake DTLS (celui dans `connect()`).
4. **Désactiver temporairement les automations HA** qui touchent aux lampes Hue pour isoler le problème.
5. Si rien ne marche, **comparer le trafic tcpdump** entre le test standalone et le service pour trouver la différence au niveau réseau.

## Config réseau

| Device | IP | Port |
|--------|-----|------|
| Hue Bridge v2 (BSB002) | 192.168.1.59 | REST: 80, DTLS: 2100 |
| TV Philips 55OLED708 | 192.168.1.26 | JointSPACE: 1926 (HTTPS) |
| GPU Tower | 192.168.1.32 | OpenRGB: 6742 |

## Credentials (dans `ambisync_config/config.yml`)

- Hue token: `SHHCgK8UE4-rUhIZk2wZS2fZvKmW2RMcHWzv9MEu`
- Client key DTLS: `39646E355A54B5976BD62E5817314374`
- Entertainment group: `200` (V2 config ID: `21ce5a7d-4de1-4582-984f-f64e4b56127f`)
- Channel map: light 1 → channel 0, light 2 → channel 1

## Fichiers clés

- `scripts/ambilight_unified_sync.py` — script principal (modifié)
- `scripts/test_dtls6.py` — test standalone qui **fonctionne**
- `scripts/test_dtls4.py` — test avec tcpdump (confirme encryption OK)
- `ambisync_config/config.yml` — config (client_key actif)
- `ha_config/automations.yaml` — automations potentiellement interférentes
- Service systemd: `ambilight-sync.service`

## État actuel

- `client_key` est actif dans config → Entertainment API est activé
- Le code a un test RED de 3s au démarrage dans `connect()` (à retirer une fois debuggé)
- Le service tourne actuellement en mode Entertainment mais les lampes ne répondent pas
- Le REST fallback (thread-per-push) fonctionne comme backup
