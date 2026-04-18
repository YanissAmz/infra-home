#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


API_URL = "http://127.0.0.1:8070/api/ambilight/profile"
VALID_PROFILES = {"soft", "normal", "punchy"}


def _fetch_json(req: Request | str) -> dict:
    with urlopen(req, timeout=2.0) as response:
        raw = response.read().decode().strip()
    return json.loads(raw) if raw else {}


def get_profile() -> int:
    try:
        data = _fetch_json(API_URL)
    except (OSError, URLError, json.JSONDecodeError):
        return 1
    profile = data.get("profile")
    if profile in VALID_PROFILES:
        print(profile)
        return 0
    print("unknown")
    return 0


def set_profile(profile: str) -> int:
    if profile not in VALID_PROFILES:
        raise SystemExit(f"invalid profile: {profile}")
    payload = json.dumps({"profile": profile}).encode()
    request = Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        data = _fetch_json(request)
    except (OSError, URLError, json.JSONDecodeError):
        return 1
    print(data.get("profile", profile))
    return 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in {"get", "set"}:
        raise SystemExit("usage: hyte_ambilight_profile.py get|set [soft|normal|punchy]")
    if sys.argv[1] == "get":
        return get_profile()
    if len(sys.argv) != 3:
        raise SystemExit("usage: hyte_ambilight_profile.py set soft|normal|punchy")
    return set_profile(sys.argv[2])


if __name__ == "__main__":
    raise SystemExit(main())
