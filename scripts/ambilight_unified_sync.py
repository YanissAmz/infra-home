#!/usr/bin/env python3
"""
ambilight_unified_sync.py — sync unique : Ambilight → Hue + OpenRGB.

Un seul fetch TV, pousse simultanément vers Hue bridge et OpenRGB LEDs PC.
Évite que 2 scripts se battent pour la connexion TV.
"""

from __future__ import annotations

import signal
import sys
import time
import threading
from pathlib import Path

import requests
import urllib3
import yaml
from requests.auth import HTTPDigestAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_PATH = Path(__file__).parent.parent / "ambisync_config" / "config.yml"

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


def boost_color(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Amplifie et sature les couleurs faibles de l'API Ambilight.
    L'API retourne des valeurs 0-~120 au lieu de 0-255.
    On normalise au max du canal le plus fort puis on boost la saturation."""
    mx = max(r, g, b)
    if mx < 10:
        return 0, 0, 0
    # Normaliser pour que le canal max = 255
    scale = 255.0 / mx
    r2 = min(255, int(r * scale))
    g2 = min(255, int(g * scale))
    b2 = min(255, int(b * scale))
    # Boost saturation : éloigner les canaux faibles du max
    avg = (r2 + g2 + b2) / 3
    sat_boost = 1.5
    r2 = min(255, max(0, int(avg + (r2 - avg) * sat_boost)))
    g2 = min(255, max(0, int(avg + (g2 - avg) * sat_boost)))
    b2 = min(255, max(0, int(avg + (b2 - avg) * sat_boost)))
    return r2, g2, b2


def avg_zone(zone_data: dict) -> tuple[int, int, int]:
    rs, gs, bs, n = 0, 0, 0, 0
    for _key, rgb in zone_data.items():
        rs += rgb.get("r", 0)
        gs += rgb.get("g", 0)
        bs += rgb.get("b", 0)
        n += 1
    if n == 0:
        return 0, 0, 0
    return boost_color(rs // n, gs // n, bs // n)


class TVConnection:
    def __init__(self, host: str, device_id: str, auth_key: str):
        self.host = host
        self.auth = HTTPDigestAuth(device_id, auth_key)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.verify = False

    def fetch_ambilight(self) -> dict | None:
        try:
            r = self.session.get(
                f"https://{self.host}:1926/6/ambilight/measured", timeout=0.8
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            self._reconnect()
            return None

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
            if abs(r - prev[0]) + abs(g - prev[1]) + abs(b - prev[2]) < 15:
                continue
            self.last[lid] = (r, g, b)

            if r + g + b < 30:
                continue

            x, y = rgb_to_xy(r, g, b)
            bri = min(254, max(m.get("brightness", 200), (r + g + b) // 3))
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

    def connect(self):
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
            return True
        except Exception as e:
            print(f"[openrgb] connect failed: {e}")
            return False

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

    def push(self, colors: dict[str, tuple[int, int, int]]):
        if not self.client or not self.mapping:
            return

        # La couleur dominante est déjà calculée en amont (unified)
        r, g, b = next(iter(colors.values()))

        # Delta check
        prev = self.last.get("dom", (0, 0, 0))
        if abs(r - prev[0]) + abs(g - prev[1]) + abs(b - prev[2]) < 8:
            return
        self.last["dom"] = (r, g, b)

        if r + g + b < 15:
            return

        color = RGBColor(r, g, b)

        # Préparer TOUTES les commandes puis les envoyer le plus vite possible
        # 1. Carte mère : set_color sur le device entier (une seule commande = toutes zones d'un coup)
        mobo_idx = next(
            (i for i, d in enumerate(self.client.devices) if d.type == DeviceType.MOTHERBOARD),
            None
        )
        if mobo_idx is not None:
            try:
                self.client.devices[mobo_idx].set_color(color)
            except Exception:
                pass

        # 2. RAM : toutes les barrettes
        for ri in self.mapping["ram_indices"]:
            try:
                self.client.devices[ri].set_color(color)
            except Exception:
                pass


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

    print(f"[unified-sync] started — Hue: {hue_cfg['bridge_host']}, OpenRGB: {'yes' if orgb_ok else 'no'}")

    while not stop:
        t0 = time.monotonic()

        # TV power check every 15s
        if t0 - last_tv_check > 15.0:
            tv_on = tv.is_on()
            last_tv_check = t0
            if not tv_on:
                if orgb_ok:
                    for i in range(len(orgb.client.devices)):
                        try:
                            orgb.client.devices[i].set_color(RGBColor(20, 10, 30))
                        except Exception:
                            pass

        if not tv_on:
            time.sleep(15.0)
            continue

        data = tv.fetch_ambilight()
        if data is None:
            time.sleep(0.3)
            continue

        layer = data.get("layer1", {})

        if not layer.get("left") or not layer.get("right"):
            continue

        # Prolongation mode: prendre le pixel du BAS de chaque côté
        left_zone = layer["left"]
        right_zone = layer["right"]
        bottom_left_key = str(max(int(k) for k in left_zone.keys()))
        bottom_right_key = str(max(int(k) for k in right_zone.keys()))

        bl = left_zone[bottom_left_key]
        br = right_zone[bottom_right_key]

        color_left = boost_color(bl["r"], bl["g"], bl["b"])
        color_right = boost_color(br["r"], br["g"], br["b"])

        # PC LEDs: moyenne des deux bas
        pc_r = (color_left[0] + color_right[0]) // 2
        pc_g = (color_left[1] + color_right[1]) // 2
        pc_b = (color_left[2] + color_right[2]) // 2

        if color_left[0] + color_left[1] + color_left[2] < 15 and \
           color_right[0] + color_right[1] + color_right[2] < 15:
            continue

        # Moyenne des deux pixels bas → même couleur partout
        bottom_avg = (pc_r, pc_g, pc_b)
        unified = {"left": bottom_avg, "right": bottom_avg, "top": bottom_avg}

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
