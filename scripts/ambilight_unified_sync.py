#!/usr/bin/env python3
"""
ambilight_unified_sync.py — sync unique : Ambilight → Hue + OpenRGB.

Un seul fetch TV, pousse simultanément vers Hue bridge et OpenRGB LEDs PC.
Sélection de la couleur la plus saturée de l'écran (pas de moyenne).
Reconnexion auto TV (backoff exponentiel) et OpenRGB.
"""

from __future__ import annotations

import signal
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

import requests
import urllib3
import yaml
from requests.auth import HTTPDigestAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_PATH = Path(__file__).parent.parent / "ambisync_config" / "config.yml"

# Night mode: 22h-6h → reduced brightness
NIGHT_START = 22
NIGHT_END = 6
NIGHT_HUE_BRI = 20
NIGHT_LED_SCALE = 0.05  # 5% brightness for OpenRGB LEDs at night

# Couleur par défaut quand TV éteinte (bleu doux)
IDLE_COLOR = (0, 40, 255)

# Delta filter — seuil pour éviter micro-tremblements
DELTA_THRESHOLD_ORGB = 25
DELTA_THRESHOLD_HUE = 25

_night_cache: bool = False
_night_cache_ts: float = 0.0


def is_night() -> bool:
    global _night_cache, _night_cache_ts
    now = time.monotonic()
    if now - _night_cache_ts > 60.0:
        h = datetime.now().hour
        _night_cache = h >= NIGHT_START or h < NIGHT_END
        _night_cache_ts = now
    return _night_cache

# OpenRGB import (optional)
try:
    from openrgb import OpenRGBClient
    from openrgb.utils import RGBColor, DeviceType
    HAS_OPENRGB = True
except ImportError:
    HAS_OPENRGB = False


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def rgb_to_xy(r: int, g: int, b: int) -> tuple[float, float]:
    def gamma(c: float) -> float:
        c /= 255.0
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
    rl, gl, bl = gamma(r), gamma(g), gamma(b)
    X = rl * 0.4124 + gl * 0.3576 + bl * 0.1805
    Y = rl * 0.2126 + gl * 0.7152 + bl * 0.0722
    Z = rl * 0.0193 + gl * 0.1192 + bl * 0.9505
    s = X + Y + Z
    if s == 0:
        return 0.3127, 0.3290
    return X / s, Y / s


API_MAX = 160  # plafond observé de l'API Ambilight (valeurs brutes)


def boost_color(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Boost fidèle à l'Ambilight : couleurs renforcées + luminosité proportionnelle.
    Scène sombre → LEDs sombres. Scène lumineuse → LEDs lumineuses."""
    mx = max(r, g, b)
    if mx < 5:
        return 0, 0, 0
    # Luminosité relative : à quel point la scène est lumineuse (0.0-1.0)
    brightness = min(1.0, mx / API_MAX)
    # Normaliser les proportions entre canaux (teinte + saturation relative)
    scale = 255.0 / mx
    r2 = r * scale
    g2 = g * scale
    b2 = b * scale
    # Boost saturation modéré (×1.4) — garde les blancs blancs
    avg = (r2 + g2 + b2) / 3
    sat_boost = 1.4
    r2 = avg + (r2 - avg) * sat_boost
    g2 = avg + (g2 - avg) * sat_boost
    b2 = avg + (b2 - avg) * sat_boost
    # Appliquer la luminosité de la scène
    r2 = min(255, max(0, int(r2 * brightness)))
    g2 = min(255, max(0, int(g2 * brightness)))
    b2 = min(255, max(0, int(b2 * brightness)))
    return r2, g2, b2


class TVConnection:
    def __init__(self, host: str, device_id: str, auth_key: str):
        self.host = host
        self.auth = HTTPDigestAuth(device_id, auth_key)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.verify = False
        self._backoff = 0.3
        self._max_backoff = 15.0

    def fetch_ambilight(self) -> dict | None:
        try:
            r = self.session.get(
                f"https://{self.host}:1926/6/ambilight/measured", timeout=0.8
            )
            r.raise_for_status()
            self._backoff = 0.3  # reset on success
            return r.json()
        except Exception:
            self._reconnect()
            return None

    def get_backoff(self) -> float:
        """Retourne le délai actuel et l'augmente pour le prochain appel."""
        delay = self._backoff
        self._backoff = min(self._backoff * 2, self._max_backoff)
        return delay

    def is_on(self) -> bool:
        try:
            r = self.session.get(
                f"https://{self.host}:1926/6/powerstate", timeout=1.5
            )
            return r.json().get("powerstate") == "On"
        except Exception:
            return False

    def _reconnect(self):
        try:
            self.session.close()
        except Exception:
            pass
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.verify = False


class HueSink:
    def __init__(self, bridge_host: str, token: str, mapping: list, transition_ds: int = 2):
        self.bridge = bridge_host
        self.token = token
        self.mapping = mapping
        self.transition_ds = transition_ds
        self.last = {}

    def push(self, colors: dict[str, tuple[int, int, int]]):
        for m in self.mapping:
            side = m["side"]
            if side not in colors:
                continue
            r, g, b = colors[side]
            lid = m["light_id"]

            # Delta filter
            prev = self.last.get(lid, (0, 0, 0))
            if abs(r - prev[0]) + abs(g - prev[1]) + abs(b - prev[2]) < DELTA_THRESHOLD_HUE:
                continue
            self.last[lid] = (r, g, b)

            if r + g + b < 30:
                # Scène noire → brightness minimum
                try:
                    requests.put(
                        f"http://{self.bridge}/api/{self.token}/lights/{lid}/state",
                        json={"bri": 1, "transitiontime": self.transition_ds},
                        timeout=1.0,
                    )
                except Exception:
                    pass
                continue

            x, y = rgb_to_xy(r, g, b)
            max_bri = NIGHT_HUE_BRI if is_night() else m.get("brightness", 200)
            # Brightness proportionnelle à la luminosité de la couleur boostée
            scene_bri = max(r, g, b) * max_bri // 255
            bri = min(254, max(1, scene_bri))
            try:
                requests.put(
                    f"http://{self.bridge}/api/{self.token}/lights/{lid}/state",
                    json={"on": True, "xy": [x, y], "bri": bri, "transitiontime": self.transition_ds},
                    timeout=1.0,
                )
            except Exception:
                pass


class OpenRGBSink:
    def __init__(self):
        self.client = None
        self.mapping = None
        self.last = {}
        self._last_connect_attempt = 0.0

    def connect(self) -> bool:
        if not HAS_OPENRGB:
            print("[openrgb] openrgb-python not installed, skipping")
            return False
        try:
            self.client = OpenRGBClient("127.0.0.1", 6742)
            for dev in self.client.devices:
                try:
                    dev.set_mode("Direct")
                except Exception:
                    pass
            self.mapping = self._build_mapping()
            print(f"[openrgb] connected, {len(self.client.devices)} devices")
            self._last_connect_attempt = time.monotonic()
            return True
        except Exception as e:
            print(f"[openrgb] connect failed: {e}")
            self._last_connect_attempt = time.monotonic()
            return False

    def reconnect_if_needed(self) -> bool:
        """Tente une reconnexion si déconnecté (max 1 tentative / 30s)."""
        if self.client is not None:
            return True
        now = time.monotonic()
        if now - self._last_connect_attempt < 30.0:
            return False
        print("[openrgb] attempting reconnect...")
        return self.connect()

    def _build_mapping(self) -> dict:
        ram_indices = []
        zone_map = {}
        for i, dev in enumerate(self.client.devices):
            if dev.type == DeviceType.DRAM:
                ram_indices.append(i)
            elif dev.type == DeviceType.MOTHERBOARD:
                for zi, zone in enumerate(dev.zones):
                    zname = zone.name.upper()
                    if "JRAINBOW1" in zname:
                        zone_map["left"] = (i, zi)
                    elif "JRAINBOW2" in zname:
                        zone_map["right"] = (i, zi)
                    elif "PIPE" in zname:
                        zone_map["top"] = (i, zi)
                    elif "JRGB" in zname:
                        zone_map["jrgb"] = (i, zi)
        return {"ram_indices": ram_indices, "zone_map": zone_map}

    def set_static(self, r: int, g: int, b: int):
        """Set une couleur statique sur tous les devices."""
        if not self.client:
            return
        color = RGBColor(r, g, b)
        for i in range(len(self.client.devices)):
            try:
                self.client.devices[i].set_color(color)
            except Exception:
                self._mark_disconnected()
                return
        self.last = {"dom": (r, g, b)}

    def push(self, colors: dict[str, tuple[int, int, int]]):
        if not self.client or not self.mapping:
            return

        r, g, b = next(iter(colors.values()))

        # Delta check
        prev = self.last.get("dom", (0, 0, 0))
        if abs(r - prev[0]) + abs(g - prev[1]) + abs(b - prev[2]) < DELTA_THRESHOLD_ORGB:
            return
        self.last["dom"] = (r, g, b)

        if is_night():
            r = int(r * NIGHT_LED_SCALE)
            g = int(g * NIGHT_LED_SCALE)
            b = int(b * NIGHT_LED_SCALE)

        color = RGBColor(r, g, b)

        # Carte mère : set_color sur le device entier
        mobo_idx = next(
            (i for i, d in enumerate(self.client.devices) if d.type == DeviceType.MOTHERBOARD),
            None
        )
        if mobo_idx is not None:
            try:
                self.client.devices[mobo_idx].set_color(color)
            except Exception:
                self._mark_disconnected()
                return

        # RAM : toutes les barrettes
        for ri in self.mapping["ram_indices"]:
            try:
                self.client.devices[ri].set_color(color)
            except Exception:
                self._mark_disconnected()
                return

    def _mark_disconnected(self):
        """Marque la connexion comme perdue pour trigger un reconnect."""
        print("[openrgb] connection lost, will reconnect")
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.client = None
        self.mapping = None
        self.last = {}


def run():
    cfg = load_config()
    tv_cfg = cfg["tv"]
    hue_cfg = cfg["hue"]

    tv = TVConnection(tv_cfg["host"], tv_cfg["device_id"], tv_cfg["auth_key"])

    hue = HueSink(
        hue_cfg["bridge_host"], hue_cfg["token"],
        cfg["mapping"], cfg.get("transition_ds", 2)
    )

    orgb = OpenRGBSink()
    orgb_ok = orgb.connect()

    stop = False
    def _sig(_s, _f):
        nonlocal stop
        stop = True
        print("\n[unified-sync] stopping")

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    last_tv_check = 0.0
    tv_on = False
    idle_color_set = False

    print(f"[unified-sync] started — Hue: {hue_cfg['bridge_host']}, OpenRGB: {'yes' if orgb_ok else 'no'}")

    while not stop:
        t0 = time.monotonic()

        # OpenRGB reconnect auto si déconnecté
        if not orgb_ok:
            orgb_ok = orgb.reconnect_if_needed()

        # TV power check every 15s
        if t0 - last_tv_check > 15.0:
            tv_on = tv.is_on()
            last_tv_check = t0
            if not tv_on and not idle_color_set and orgb_ok:
                orgb.set_static(*IDLE_COLOR)
                idle_color_set = True
                print(f"[unified-sync] TV off → idle blue")

        if not tv_on:
            time.sleep(15.0)
            continue

        idle_color_set = False

        data = tv.fetch_ambilight()
        if data is None:
            delay = tv.get_backoff()
            time.sleep(delay)
            continue

        layer = data.get("layer1", {})

        if not layer.get("left") or not layer.get("right"):
            continue

        # Prolongation mode : pixels du bas gauche + droit, moyenne
        left_zone = layer["left"]
        right_zone = layer["right"]
        bottom_left_key = str(max(int(k) for k in left_zone.keys()))
        bottom_right_key = str(max(int(k) for k in right_zone.keys()))

        bl = left_zone[bottom_left_key]
        br = right_zone[bottom_right_key]

        # Moyenne brute AVANT boost (pour garder la fidélité)
        avg_r = (bl["r"] + br["r"]) // 2
        avg_g = (bl["g"] + br["g"]) // 2
        avg_b = (bl["b"] + br["b"]) // 2

        dominant = boost_color(avg_r, avg_g, avg_b)

        unified = {"left": dominant, "right": dominant, "top": dominant}

        # Push OpenRGB d'abord (local, instantané)
        if orgb_ok:
            orgb.push(unified)

        # Push Hue en parallèle (réseau, plus lent mais non-bloquant)
        threading.Thread(target=hue.push, args=(unified,), daemon=True).start()

        # No sleep — fire next request as soon as possible


def main():
    run()


if __name__ == "__main__":
    main()
