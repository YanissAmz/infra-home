#!/usr/bin/env python3
"""
philips_hue_ambisync.py — bypass Ambilight+hue retiré sur TVs Philips 2023+.

Polls TV JointSPACE API /6/ambilight/processed at ~5 Hz, averages zone colors,
pushes to Hue bulbs via bridge local API. Replaces the official Ambilight+hue
feature removed by TP Vision on 2023 models (55OLED708 etc.).

Config: ambisync_config/config.yml

Usage:
    python philips_hue_ambisync.py           # run forever
    python philips_hue_ambisync.py --once    # single poll+push (debug)
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Any

import requests
import urllib3
import yaml
from requests.auth import HTTPDigestAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_PATH = Path(__file__).parent.parent / "ambisync_config" / "config.yml"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        sys.exit(f"Missing config: {CONFIG_PATH}")
    return yaml.safe_load(CONFIG_PATH.read_text())


def rgb_to_xy(r: int, g: int, b: int) -> tuple[float, float]:
    """Convert sRGB → CIE xy (gamut B, Philips Hue approx)."""
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


def avg_zone(zone_data: dict[str, Any]) -> tuple[int, int, int]:
    """Average RGB across all pixels in a zone (left/right/top from API)."""
    rs, gs, bs, n = 0, 0, 0, 0
    for _pixel_key, rgb in zone_data.items():
        rs += rgb.get("r", 0)
        gs += rgb.get("g", 0)
        bs += rgb.get("b", 0)
        n += 1
    if n == 0:
        return 0, 0, 0
    return rs // n, gs // n, bs // n


def fetch_ambilight(tv_host: str, auth: HTTPDigestAuth, timeout: float = 2.0) -> dict:
    # 55OLED708 firmware quirk: /processed returns zeroes, /measured works
    url = f"https://{tv_host}:1926/6/ambilight/measured"
    r = requests.get(url, auth=auth, verify=False, timeout=timeout)
    r.raise_for_status()
    return r.json()


def tv_is_on(tv_host: str, auth: HTTPDigestAuth) -> bool:
    try:
        r = requests.get(
            f"https://{tv_host}:1926/6/powerstate",
            auth=auth, verify=False, timeout=2.0,
        )
        return r.json().get("powerstate") == "On"
    except Exception:
        return False


def push_hue(
    bridge_host: str, token: str, light_id: int, r: int, g: int, b: int, bri: int,
    transition_ds: int = 2,
    _last: dict = {},
) -> None:
    """transition_ds: deciseconds. 2 = 200ms fade for smooth transitions."""
    # Skip if color hasn't changed enough (reduces API spam + flicker)
    key = f"{light_id}"
    prev = _last.get(key, (0, 0, 0))
    delta = abs(r - prev[0]) + abs(g - prev[1]) + abs(b - prev[2])
    if delta < 15:
        return
    _last[key] = (r, g, b)

    # Don't turn off lamp for dark scenes — set minimum brightness
    total = r + g + b
    if total < 30:
        return  # Scene too dark, keep last color instead of flashing black

    x, y = rgb_to_xy(r, g, b)
    bri = max(bri, min(254, total // 3))
    url = f"http://{bridge_host}/api/{token}/lights/{light_id}/state"
    body = {"on": True, "xy": [x, y], "bri": bri, "transitiontime": transition_ds}
    try:
        requests.put(url, json=body, timeout=1.5)
    except requests.RequestException as e:
        print(f"[hue] push fail light {light_id}: {e}", file=sys.stderr)


def extract_zone_colors(data: dict) -> dict[str, tuple[int, int, int]]:
    """
    JointSPACE returns: {"layer1": {"left": {...}, "top": {...}, "right": {...}, "bottom": {...}}}
    Each side has numbered pixel entries with r/g/b keys.
    """
    layer = data.get("layer1", {})
    return {
        side: avg_zone(layer.get(side, {}))
        for side in ("left", "top", "right", "bottom")
        if layer.get(side)
    }


def run(cfg: dict, once: bool = False) -> None:
    tv = cfg["tv"]
    hue = cfg["hue"]
    mapping = cfg["mapping"]  # list of {side, light_id, brightness}
    poll_hz = cfg.get("poll_hz", 5)
    period = 1.0 / poll_hz
    transition_ds = cfg.get("transition_ds", 1)

    auth = HTTPDigestAuth(tv["device_id"], tv["auth_key"])

    # Graceful shutdown
    stop = False

    def _sig(_s, _f):
        nonlocal stop
        stop = True
        print("\n[ambisync] stopping")

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    last_tv_check = 0.0
    tv_on = False
    check_interval = 15.0

    print(f"[ambisync] polling {tv['host']} at {poll_hz} Hz → {hue['bridge_host']}")

    while not stop:
        t0 = time.monotonic()

        # Cheap TV on/off check every 15s to avoid hammering when off
        if t0 - last_tv_check > check_interval:
            tv_on = tv_is_on(tv["host"], auth)
            last_tv_check = t0
            if not tv_on:
                print("[ambisync] TV off, idling")

        if not tv_on:
            time.sleep(check_interval)
            continue

        try:
            data = fetch_ambilight(tv["host"], auth)
            colors = extract_zone_colors(data)
        except Exception as e:
            print(f"[ambisync] fetch fail: {e}", file=sys.stderr)
            time.sleep(2.0)
            last_tv_check = 0  # recheck TV state
            continue

        for m in mapping:
            side = m["side"]
            if side not in colors:
                continue
            r, g, b = colors[side]
            push_hue(
                hue["bridge_host"], hue["token"], m["light_id"],
                r, g, b, m.get("brightness", 200), transition_ds,
            )

        if once:
            print("[ambisync] --once done:", colors)
            return

        elapsed = time.monotonic() - t0
        if elapsed < period:
            time.sleep(period - elapsed)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    run(cfg, once=args.once)


if __name__ == "__main__":
    main()
