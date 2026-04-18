#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8070/api/ambilight/controller"


def _post(path: str, payload: dict) -> int:
    request = Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=4.0) as response:
        body = response.read().decode().strip()
    if body:
        print(body)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(
            "usage: ambilight_control_api.py apply|bootstrap|mode|profile|power|hyte|pc|sync-service ..."
        )
    command = sys.argv[1]
    if command == "apply":
        reason = sys.argv[2] if len(sys.argv) > 2 else "ha"
        return _post("/apply", {"reason": reason})
    if command == "bootstrap":
        return _post("/bootstrap", {})
    if command == "mode":
        if len(sys.argv) != 3:
            raise SystemExit("usage: ambilight_control_api.py mode auto|day|night")
        return _post("/mode", {"mode": sys.argv[2]})
    if command == "profile":
        if len(sys.argv) != 3:
            raise SystemExit("usage: ambilight_control_api.py profile movie|gaming|reading|sleep|off")
        return _post("/profile", {"profile": sys.argv[2]})
    if command == "power":
        if len(sys.argv) != 3:
            raise SystemExit("usage: ambilight_control_api.py power on|off")
        return _post("/power", {"power": sys.argv[2]})
    if command == "hyte":
        if len(sys.argv) < 3:
            raise SystemExit("usage: ambilight_control_api.py hyte auto|manual [profile]")
        mode = sys.argv[2]
        payload = {"mode": mode}
        if len(sys.argv) > 3:
            payload["profile"] = sys.argv[3]
        return _post("/hyte", payload)
    if command == "hyte-sync":
        if len(sys.argv) != 4:
            raise SystemExit("usage: ambilight_control_api.py hyte-sync 0|1 manual_profile")
        return _post(
            "/hyte",
            {
                "auto_sync": bool(int(sys.argv[2])),
                "manual_profile": sys.argv[3],
            },
        )
    if command == "pc":
        if len(sys.argv) < 3:
            raise SystemExit("usage: ambilight_control_api.py pc auto|manual_high [auto_led_scale_pct]")
        payload = {"mode": sys.argv[2]}
        if len(sys.argv) > 3:
            payload["auto_led_scale_pct"] = int(sys.argv[3])
        return _post("/pc", payload)
    if command == "pc-sync":
        if len(sys.argv) != 4:
            raise SystemExit("usage: ambilight_control_api.py pc-sync 0|1 auto_led_scale_pct")
        return _post(
            "/pc",
            {
                "auto_sync": bool(int(sys.argv[2])),
                "auto_led_scale_pct": int(sys.argv[3]),
            },
        )
    if command == "sync-service":
        if len(sys.argv) != 3:
            raise SystemExit("usage: ambilight_control_api.py sync-service start|stop|restart")
        return _post("/sync-service", {"action": sys.argv[2]})
    raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    raise SystemExit(main())
