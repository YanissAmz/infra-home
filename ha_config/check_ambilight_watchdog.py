#!/usr/bin/env python3

from __future__ import annotations

import json
import time
from pathlib import Path


STATUS_DIR = Path("/config/status")
MAX_AGE_S = 180


def _read_status(name: str) -> tuple[str | None, int | None]:
    path = STATUS_DIR / f"{name}.txt"
    if not path.exists():
        return None, None
    try:
        age_s = int(time.time() - path.stat().st_mtime)
        value = path.read_text().strip()
    except OSError:
        return None, None
    return value, age_s


def main() -> int:
    mode, mode_age = _read_status("ambilight_mode")
    transport, transport_age = _read_status("ambilight_transport")
    tv_power, _tv_age = _read_status("tv")
    _color, color_age = _read_status("ambilight_color")
    govee_target, govee_age = _read_status("govee_target_brightness")
    hue_target, hue_age = _read_status("hue_target_brightness")

    issues: list[str] = []
    state = "ok"

    if mode is None or transport is None:
        state = "starting"
    else:
        if mode_age is None or mode_age > MAX_AGE_S:
            issues.append("mode_status_stale")
        if transport_age is None or transport_age > MAX_AGE_S:
            issues.append("transport_status_stale")
        if govee_age is None or govee_age > MAX_AGE_S:
            issues.append("govee_target_stale")
        if hue_age is None or hue_age > MAX_AGE_S:
            issues.append("hue_target_stale")
        if mode != "tv_off" and tv_power != "OFF":
            if color_age is None or color_age > MAX_AGE_S:
                issues.append("ambilight_color_stale")
        if issues:
            state = "stale"

    print(
        json.dumps(
            {
                "state": state,
                "issues": issues,
                "mode_age_s": mode_age,
                "ambilight_color_age_s": color_age,
                "transport_age_s": transport_age,
                "govee_target_age_s": govee_age,
                "hue_target_age_s": hue_age,
                "tv_power": tv_power or "unknown",
                "mode": mode or "starting",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
