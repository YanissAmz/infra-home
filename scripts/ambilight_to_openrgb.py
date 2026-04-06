#!/usr/bin/env python3
"""
ambilight_to_openrgb.py — sync LEDs boîtier PC avec Ambilight TV.

Lit les couleurs Ambilight via JointSPACE API (endpoint /measured),
pousse vers OpenRGB SDK pour colorer RAM, carte mère, bandes LED.

Mapping zones:
  - Ambilight gauche  → JRAINBOW1 (bande LED gauche boîtier)
  - Ambilight droite  → JRAINBOW2 (bande LED droite boîtier)
  - Ambilight haut    → PIPE1 (LEDs haut carte mère)
  - Couleur dominante → RAM Corsair Dominator (les 2 barrettes)

Usage:
    python ambilight_to_openrgb.py           # run forever
    python ambilight_to_openrgb.py --once    # single sync (debug)
    python ambilight_to_openrgb.py --test    # cycle rouge/vert/bleu sur tous devices
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
import threading
from pathlib import Path

import requests
import urllib3
import yaml
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor, DeviceType
from requests.auth import HTTPDigestAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_PATH = Path(__file__).parent.parent / "ambisync_config" / "config.yml"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"Missing config: {CONFIG_PATH}")
    return yaml.safe_load(CONFIG_PATH.read_text())


def avg_zone(zone_data: dict) -> tuple[int, int, int]:
    rs, gs, bs, n = 0, 0, 0, 0
    for _key, rgb in zone_data.items():
        rs += rgb.get("r", 0)
        gs += rgb.get("g", 0)
        bs += rgb.get("b", 0)
        n += 1
    if n == 0:
        return 0, 0, 0
    return rs // n, gs // n, bs // n


_session = None

def _get_session(auth: HTTPDigestAuth) -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.auth = auth
        _session.verify = False
    return _session


def fetch_ambilight(tv_host: str, auth: HTTPDigestAuth) -> dict:
    s = _get_session(auth)
    r = s.get(f"https://{tv_host}:1926/6/ambilight/measured", timeout=0.5)
    r.raise_for_status()
    return r.json()


def tv_is_on(tv_host: str, auth: HTTPDigestAuth) -> bool:
    try:
        s = _get_session(auth)
        r = s.get(f"https://{tv_host}:1926/6/powerstate", timeout=1.5)
        return r.json().get("powerstate") == "On"
    except Exception:
        return False


def set_zone_color(client: OpenRGBClient, device_idx: int, zone_idx: int, r: int, g: int, b: int) -> None:
    try:
        device = client.devices[device_idx]
        device.zones[zone_idx].set_color(RGBColor(r, g, b))
    except Exception:
        pass


def set_device_color(client: OpenRGBClient, device_idx: int, r: int, g: int, b: int) -> None:
    try:
        device = client.devices[device_idx]
        device.set_color(RGBColor(r, g, b))
    except Exception:
        pass


def test_cycle(client: OpenRGBClient) -> None:
    """Cycle rouge/vert/bleu sur tous les devices pour vérifier le setup."""
    colors = [("ROUGE", 255, 0, 0), ("VERT", 0, 255, 0), ("BLEU", 0, 0, 255)]
    for name, r, g, b in colors:
        print(f"[test] {name}")
        for i, dev in enumerate(client.devices):
            set_device_color(client, i, r, g, b)
        time.sleep(1.5)
    # Reset blanc
    for i in range(len(client.devices)):
        set_device_color(client, i, 50, 50, 50)
    print("[test] done")


def build_mapping(client: OpenRGBClient) -> dict:
    """
    Auto-detect devices and build mapping.
    Returns dict with keys: ram_indices, mobo_idx, zone_map
    """
    ram_indices = []
    mobo_idx = None

    for i, dev in enumerate(client.devices):
        if dev.type == DeviceType.DRAM:
            ram_indices.append(i)
        elif dev.type == DeviceType.MOTHERBOARD:
            mobo_idx = i

    # Build zone map for motherboard
    zone_map = {}
    if mobo_idx is not None:
        dev = client.devices[mobo_idx]
        for zi, zone in enumerate(dev.zones):
            zname = zone.name.upper()
            if "JRAINBOW1" in zname:
                zone_map["left"] = (mobo_idx, zi)
            elif "JRAINBOW2" in zname:
                zone_map["right"] = (mobo_idx, zi)
            elif "PIPE" in zname:
                zone_map["top"] = (mobo_idx, zi)
            elif "JRGB" in zname:
                zone_map["jrgb"] = (mobo_idx, zi)

    print(f"[openrgb] RAM sticks: {len(ram_indices)}, Mobo zones mapped: {list(zone_map.keys())}")
    return {"ram_indices": ram_indices, "mobo_idx": mobo_idx, "zone_map": zone_map}


def run(cfg: dict, once: bool = False) -> None:
    tv = cfg["tv"]
    poll_hz = cfg.get("openrgb_poll_hz", 0)
    period = 1.0 / poll_hz if poll_hz > 0 else 0  # 0 = no sleep, fire as fast as TV responds

    auth = HTTPDigestAuth(tv["device_id"], tv["auth_key"])

    # Connect OpenRGB
    client = OpenRGBClient("127.0.0.1", 6742)
    print(f"[openrgb] connected, {len(client.devices)} devices")

    # Set all devices to Direct mode
    for dev in client.devices:
        try:
            dev.set_mode("Direct")
        except Exception:
            pass

    mapping = build_mapping(client)

    stop = False
    def _sig(_s, _f):
        nonlocal stop
        stop = True
        print("\n[openrgb-sync] stopping")

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    last_tv_check = 0.0
    tv_on = False
    last_colors = {}

    print(f"[openrgb-sync] polling TV at {poll_hz} Hz")

    while not stop:
        t0 = time.monotonic()

        if t0 - last_tv_check > 15.0:
            tv_on = tv_is_on(tv["host"], auth)
            last_tv_check = t0
            if not tv_on:
                # TV off → set dim static color
                for i in range(len(client.devices)):
                    set_device_color(client, i, 20, 10, 30)
                print("[openrgb-sync] TV off, static dim")

        if not tv_on:
            time.sleep(15.0)
            continue

        try:
            data = fetch_ambilight(tv["host"], auth)
            layer = data.get("layer1", {})
        except Exception:
            # Reconnexion rapide au lieu d'attendre 2s
            global _session
            _session = None  # force nouvelle session TLS
            time.sleep(0.3)
            continue

        colors = {}
        for side in ("left", "top", "right"):
            if layer.get(side):
                colors[side] = avg_zone(layer[side])

        # Skip if no significant change (seuil bas pour réactivité)
        total_delta = 0
        for side, (r, g, b) in colors.items():
            pr, pg, pb = last_colors.get(side, (0, 0, 0))
            total_delta += abs(r - pr) + abs(g - pg) + abs(b - pb)
        if total_delta < 8 and not once:
            elapsed = time.monotonic() - t0
            if elapsed < period:
                time.sleep(period - elapsed)
            continue
        last_colors = colors.copy()

        # Push colors in background thread to not block polling
        def _push(colors_snap, mapping_ref, client_ref):
            zone_map = mapping_ref["zone_map"]
            for side, (r, g, b) in colors_snap.items():
                if r + g + b < 15:
                    continue
                if side in zone_map:
                    dev_idx, zone_idx = zone_map[side]
                    set_zone_color(client_ref, dev_idx, zone_idx, r, g, b)

            if colors_snap:
                all_r = sum(c[0] for c in colors_snap.values()) // len(colors_snap)
                all_g = sum(c[1] for c in colors_snap.values()) // len(colors_snap)
                all_b = sum(c[2] for c in colors_snap.values()) // len(colors_snap)
                if all_r + all_g + all_b >= 15:
                    for ri in mapping_ref["ram_indices"]:
                        set_device_color(client_ref, ri, all_r, all_g, all_b)

            if "top" in colors_snap and "jrgb" in zone_map:
                r, g, b = colors_snap["top"]
                if r + g + b >= 15:
                    dev_idx, zone_idx = zone_map["jrgb"]
                    set_zone_color(client_ref, dev_idx, zone_idx, r, g, b)

        threading.Thread(target=_push, args=(colors.copy(), mapping, client), daemon=True).start()

        if once:
            print(f"[openrgb-sync] --once done: {colors}")
            return

        elapsed = time.monotonic() - t0
        if elapsed < period:
            time.sleep(period - elapsed)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--test", action="store_true", help="Cycle RGB test on all devices")
    args = ap.parse_args()

    if args.test:
        client = OpenRGBClient("127.0.0.1", 6742)
        print(f"[openrgb] {len(client.devices)} devices detected")
        for i, dev in enumerate(client.devices):
            print(f"  [{i}] {dev.name} ({dev.type}) — {len(dev.zones)} zones, {len(dev.leds)} LEDs")
        test_cycle(client)
        return

    cfg = load_config()
    run(cfg, once=args.once)


if __name__ == "__main__":
    main()
