#!/usr/bin/env python3
"""
philips_jointspace.py — wrapper API JointSPACE (Philips TVs 2016+).

Usage:
    # Pairing (one-time, interactive):
    python philips_jointspace.py --pair --host 192.168.1.XX

    # Ambilight snapshot:
    python philips_jointspace.py --ambilight-processed
    python philips_jointspace.py --ambilight-power on
    python philips_jointspace.py --ambilight-mode internal

    # TV power / apps / keys:
    python philips_jointspace.py --powerstate
    python philips_jointspace.py --key Standby
    python philips_jointspace.py --apps
    python philips_jointspace.py --launch com.netflix.ninja

Credentials stored in .env next to this script after pairing.
Reference: https://github.com/eslavnov/pylips, JointSPACE API v6.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import random
import string
import sys
import time
from pathlib import Path
from typing import Any

import requests
from requests.auth import HTTPDigestAuth

ENV_PATH = Path(__file__).parent / ".env.jointspace"
SECRET_KEY = base64.b64decode(
    "ZmVheDVsMmhnMjBzZ2wyaDJoOXMyNWgwczFoNDc4ZDgyamQ3ODJ5ZDgyamQ3ODJkZGg4MmQ="
    # Standard JointSPACE pairing secret used by all Android TVs. Public.
)


def _load_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    data = {}
    for line in ENV_PATH.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def _save_env(data: dict[str, str]) -> None:
    ENV_PATH.write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n")
    ENV_PATH.chmod(0o600)


def _rand_str(n: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def _create_signature(secret: bytes, to_sign: str) -> str:
    sig = hmac.new(secret, to_sign.encode(), hashlib.sha256).digest()
    return base64.b64encode(sig).decode()


def pair(host: str) -> None:
    """Interactive pairing. TV must be ON. User enters PIN displayed on TV."""
    device_id = _rand_str(16)
    payload = {
        "device": {
            "device_name": "ambisync",
            "device_os": "Linux",
            "app_name": "ambisync",
            "type": "native",
            "app_id": "app.id",
            "id": device_id,
        },
        "scope": ["read", "write", "control"],
    }
    url = f"https://{host}:1926/6/pair/request"
    print(f"[pair] POST {url}")
    r = requests.post(url, json=payload, verify=False, timeout=10)
    r.raise_for_status()
    resp = r.json()
    auth_timestamp = resp["timestamp"]
    auth_key = resp["auth_key"]
    print(f"[pair] got auth_key, PIN should now be visible on TV screen")

    pin = input("Enter PIN shown on TV: ").strip()

    auth = {
        "auth_AppId": "1",
        "pin": pin,
        "auth_timestamp": auth_timestamp,
        "auth_signature": _create_signature(
            SECRET_KEY, str(auth_timestamp) + pin
        ),
    }
    grant_payload = {"auth": auth, "device": payload["device"]}
    url = f"https://{host}:1926/6/pair/grant"
    r = requests.post(
        url,
        json=grant_payload,
        verify=False,
        auth=HTTPDigestAuth(device_id, auth_key),
        timeout=10,
    )
    r.raise_for_status()
    print("[pair] SUCCESS")
    _save_env(
        {
            "TV_HOST": host,
            "TV_DEVICE_ID": device_id,
            "TV_AUTH_KEY": auth_key,
        }
    )
    print(f"[pair] credentials saved to {ENV_PATH}")


class PhilipsTV:
    def __init__(self, host: str, device_id: str, auth_key: str, timeout: float = 5.0):
        self.host = host
        self.auth = HTTPDigestAuth(device_id, auth_key)
        self.timeout = timeout
        self.base = f"https://{host}:1926/6"

    @classmethod
    def from_env(cls) -> "PhilipsTV":
        env = _load_env()
        missing = [k for k in ("TV_HOST", "TV_DEVICE_ID", "TV_AUTH_KEY") if k not in env]
        if missing:
            sys.exit(f"Missing env vars {missing}. Run --pair first.")
        return cls(env["TV_HOST"], env["TV_DEVICE_ID"], env["TV_AUTH_KEY"])

    def _get(self, path: str) -> Any:
        r = requests.get(
            f"{self.base}/{path}", auth=self.auth, verify=False, timeout=self.timeout
        )
        r.raise_for_status()
        return r.json() if r.text else None

    def _post(self, path: str, body: dict) -> Any:
        r = requests.post(
            f"{self.base}/{path}",
            json=body,
            auth=self.auth,
            verify=False,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json() if r.text else None

    # Ambilight
    def ambilight_processed(self) -> dict:
        return self._get("ambilight/processed")

    def ambilight_measured(self) -> dict:
        return self._get("ambilight/measured")

    def ambilight_config(self) -> dict:
        return self._get("ambilight/currentconfiguration")

    def ambilight_power(self, on: bool) -> None:
        self._post("ambilight/power", {"power": "On" if on else "Off"})

    def ambilight_mode(self, mode: str) -> None:
        # modes: internal, manual, expert, lounge
        self._post("ambilight/mode", {"current": mode})

    def ambilight_lounge_rgb(self, r: int, g: int, b: int) -> None:
        self._post(
            "ambilight/lounge",
            {"color": {"hue": 0, "saturation": 0, "brightness": 255},
             "colordelta": {"hue": 0, "saturation": 0, "brightness": 0},
             "speed": 255},
        )
        self._post(
            "ambilight/cached",
            {
                "r": r, "g": g, "b": b,
            },
        )

    # Power
    def powerstate(self) -> dict:
        return self._get("powerstate")

    def power_on(self) -> None:
        self._post("powerstate", {"powerstate": "On"})

    def power_standby(self) -> None:
        self._post("powerstate", {"powerstate": "Standby"})

    # Input keys
    def send_key(self, key: str) -> None:
        # keys: Standby, VolumeUp, VolumeDown, Mute, Home, Back, Confirm,
        # CursorUp/Down/Left/Right, Play, Pause, ChannelStepUp, Source, etc.
        self._post("input/key", {"key": key})

    # Applications
    def list_apps(self) -> dict:
        return self._get("applications")

    def launch_app(self, package: str, class_name: str | None = None) -> None:
        apps = self.list_apps().get("applications", [])
        target = next(
            (a for a in apps if a.get("intent", {}).get("component", {}).get("packageName") == package),
            None,
        )
        if not target:
            sys.exit(f"App {package} not found. Use --apps to list.")
        self._post("activities/launch", {"intent": target["intent"]})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", action="store_true")
    ap.add_argument("--host", help="TV IP for --pair")
    ap.add_argument("--ambilight-processed", action="store_true")
    ap.add_argument("--ambilight-config", action="store_true")
    ap.add_argument("--ambilight-power", choices=["on", "off"])
    ap.add_argument("--ambilight-mode", choices=["internal", "manual", "expert", "lounge"])
    ap.add_argument("--powerstate", action="store_true")
    ap.add_argument("--power-on", action="store_true")
    ap.add_argument("--standby", action="store_true")
    ap.add_argument("--key", help="Send remote key (e.g. Home, VolumeUp)")
    ap.add_argument("--apps", action="store_true")
    ap.add_argument("--launch", help="Launch app by package name")
    args = ap.parse_args()

    # Silence self-signed cert warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if args.pair:
        if not args.host:
            sys.exit("--host required with --pair")
        pair(args.host)
        return

    tv = PhilipsTV.from_env()

    if args.ambilight_processed:
        print(json.dumps(tv.ambilight_processed(), indent=2))
    elif args.ambilight_config:
        print(json.dumps(tv.ambilight_config(), indent=2))
    elif args.ambilight_power:
        tv.ambilight_power(args.ambilight_power == "on")
        print(f"Ambilight {args.ambilight_power}")
    elif args.ambilight_mode:
        tv.ambilight_mode(args.ambilight_mode)
        print(f"Ambilight mode → {args.ambilight_mode}")
    elif args.powerstate:
        print(json.dumps(tv.powerstate(), indent=2))
    elif args.power_on:
        tv.power_on()
    elif args.standby:
        tv.power_standby()
    elif args.key:
        tv.send_key(args.key)
        print(f"Key {args.key} sent")
    elif args.apps:
        print(json.dumps(tv.list_apps(), indent=2))
    elif args.launch:
        tv.launch_app(args.launch)
        print(f"Launched {args.launch}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
