# Installation Mesh WiFi - TP-Link Deco

## Architecture cible

```
Internet ← Livebox W7 (WiFi OFF, mode modem)
                │ Ethernet
                ├── Deco Node 1 (salon, à côté Livebox)  ← routeur principal
                │       └── Bridge Hue (Ethernet sur Deco)
                │
                └── Deco Node 2 (chambre/couloir)  ← satellite
                        └── Tous appareils chambre en WiFi optimal
```

## Etape 1 : Setup Deco via app mobile

1. Brancher Node 1 en Ethernet sur la Livebox (port LAN → WAN du Deco)
2. Installer app TP-Link Deco sur iPhone
3. Suivre le setup : créer réseau WiFi (SSID + mot de passe)
4. Ajouter Node 2 comme satellite (l'app guide automatiquement)
5. Placer Node 2 dans le couloir ou la chambre

## Etape 2 : Désactiver WiFi Livebox

Via http://192.168.1.1 :
1. Connexion admin (admin / votre mot de passe Livebox)
2. Menu WiFi → décocher "Activer le WiFi 2.4GHz"
3. Menu WiFi → décocher "Activer le WiFi 5GHz"
4. Sauvegarder

Le Deco prend le relais pour tout le WiFi.

## Etape 3 : Config réseau Deco

Dans l'app Deco :
- **Mode routeur** : le Deco gère le DHCP (sous-réseau 192.168.0.x par défaut)
- **OU Mode Access Point (AP)** : la Livebox garde le DHCP (même réseau 192.168.1.x)

### Mode recommandé : Access Point (AP)
- Avantage : tous les appareils restent sur 192.168.1.x
- Nos scripts, IPs fixes, configs HA ne changent pas
- La Livebox gère toujours le DHCP
- Le Deco ne fait QUE le WiFi

Pour activer : App Deco → Plus → Mode de fonctionnement → Mode Point d'accès

## Etape 4 : DNS Pi-hole sur tous les appareils

En mode AP, configurer le DNS dans la Livebox :
- Normalement verrouillé par l'API, mais via l'interface web :
  Menu Réseau → DHCP → DNS primaire : IP de la tour GPU
- Si impossible : configurer DNS par appareil (comme fait pour la TV)

Alternative : dans le Deco en mode routeur, le DNS est configurable :
- App Deco → Plus → Paramètres avancés → DNS → personnalisé → IP tour GPU

## Etape 5 : Reconnecter les appareils

Tous les appareils doivent se connecter au nouveau SSID Deco :
- TV Philips (paramètres réseau)
- Firestick HD
- Firestick 4K
- Phones, PC, etc.

Si mode AP avec même SSID/mot de passe que la Livebox : rien à faire, migration transparente.

## Etape 6 : Vérifier

- [ ] Tous appareils connectés au mesh
- [ ] TV accessible en JointSPACE (port 1926)
- [ ] Firesticks accessibles en ADB
- [ ] Pi-hole reçoit les requêtes DNS
- [ ] HA fonctionne normalement
- [ ] Ambilight sync fonctionne
- [ ] Bridge Hue toujours accessible

## Notes

- Le Bridge Hue peut rester branché en Ethernet sur la Livebox OU sur un port Deco
- En mode AP tout est sur le même réseau, donc pas de problème de routage
- Le mesh améliore surtout : stabilité WiFi chambre, débit Firesticks, latence sync
