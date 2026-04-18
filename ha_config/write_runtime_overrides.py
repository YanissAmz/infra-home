#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path


if len(sys.argv) != 8:
    raise SystemExit(
        "usage: write_runtime_overrides.py start end hue_pct govee_pct led_pct delta_day delta_night"
    )

start, end, hue_pct, govee_pct, led_pct, delta_day, delta_night = map(int, sys.argv[1:])

payload = {
    "night": {
        "start_hour": start,
        "end_hour": end,
        "hue_brightness_pct": hue_pct,
        "govee_brightness_pct": govee_pct,
        "led_scale_pct": led_pct,
    },
    "delta_threshold": {
        "day": delta_day,
        "night": delta_night,
    },
}

target = Path("/config/runtime/overrides.json")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(payload) + "\n")
