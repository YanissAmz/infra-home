#!/usr/bin/env python3
"""
hue_entertainment_setup.py — one-time setup for Hue Entertainment API.

Steps:
1. Register new API user with generateclientkey (requires bridge button press)
2. Create an Entertainment group with target lights
3. Save client_key + entertainment_group_id to config.yml
"""

import sys
import time
from pathlib import Path

import requests
import yaml

CONFIG_PATH = Path(__file__).parent.parent / "ambisync_config" / "config.yml"


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def save_config(cfg: dict):
    CONFIG_PATH.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
    print(f"[setup] config saved to {CONFIG_PATH}")


def register_user_with_clientkey(bridge: str) -> tuple[str, str]:
    """Register a new Hue API user with generateclientkey.
    Returns (username, clientkey)."""
    url = f"http://{bridge}/api"
    payload = {
        "devicetype": "ambisync#entertainment",
        "generateclientkey": True,
    }

    print("\n>>> Press the button on your Hue Bridge, then press Enter here...")
    input()

    resp = requests.post(url, json=payload, timeout=5)
    data = resp.json()

    if isinstance(data, list) and len(data) > 0:
        if "error" in data[0]:
            print(f"[setup] Error: {data[0]['error']['description']}")
            print("[setup] Make sure you pressed the bridge button first!")
            sys.exit(1)
        if "success" in data[0]:
            username = data[0]["success"]["username"]
            clientkey = data[0]["success"]["clientkey"]
            print(f"[setup] Registered: username={username}")
            print(f"[setup] Client key: {clientkey}")
            return username, clientkey

    print(f"[setup] Unexpected response: {data}")
    sys.exit(1)


def create_entertainment_group(bridge: str, token: str, light_ids: list[int]) -> str:
    """Create an Entertainment group. Returns group ID."""
    url = f"http://{bridge}/api/{token}/groups"
    payload = {
        "name": "AmbiSync Entertainment",
        "type": "Entertainment",
        "class": "TV",
        "lights": [str(lid) for lid in light_ids],
    }

    resp = requests.post(url, json=payload, timeout=5)
    data = resp.json()

    if isinstance(data, list) and len(data) > 0:
        if "error" in data[0]:
            print(f"[setup] Error creating group: {data[0]['error']['description']}")
            sys.exit(1)
        if "success" in data[0]:
            group_id = data[0]["success"]["id"]
            print(f"[setup] Entertainment group created: ID={group_id}")
            return group_id

    print(f"[setup] Unexpected response: {data}")
    sys.exit(1)


def check_existing_entertainment(bridge: str, token: str) -> str | None:
    """Check if an entertainment group already exists."""
    url = f"http://{bridge}/api/{token}/groups"
    resp = requests.get(url, timeout=5)
    groups = resp.json()
    for gid, group in groups.items():
        if group.get("type") == "Entertainment":
            print(f"[setup] Found existing entertainment group: ID={gid} name={group['name']}")
            return gid
    return None


def main():
    cfg = load_config()
    bridge = cfg["hue"]["bridge_host"]
    existing_token = cfg["hue"]["token"]

    # Check if already configured
    if cfg["hue"].get("client_key") and cfg["hue"].get("entertainment_group_id"):
        print("[setup] Entertainment API already configured in config.yml")
        print(f"  client_key: {cfg['hue']['client_key'][:8]}...")
        print(f"  group_id:   {cfg['hue']['entertainment_group_id']}")
        resp = input("Re-run setup? (y/N): ").strip().lower()
        if resp != "y":
            return

    # Step 1: Register new user with client key
    print("\n=== Step 1: Register API user with client key ===")
    print(f"Bridge: {bridge}")
    token, client_key = register_user_with_clientkey(bridge)

    # Update token in config
    cfg["hue"]["token"] = token
    cfg["hue"]["client_key"] = client_key

    # Step 2: Get light IDs from mapping
    light_ids = [m["light_id"] for m in cfg["mapping"]]
    # Filter to only reachable lights
    reachable = []
    for lid in light_ids:
        try:
            r = requests.get(f"http://{bridge}/api/{token}/lights/{lid}", timeout=3)
            info = r.json()
            if info.get("state", {}).get("reachable", False):
                reachable.append(lid)
                print(f"  Light {lid} ({info.get('name', '?')}): reachable")
            else:
                print(f"  Light {lid} ({info.get('name', '?')}): NOT reachable, skipping")
        except Exception:
            print(f"  Light {lid}: error checking, skipping")

    if not reachable:
        print("[setup] No reachable lights! At least one light must be on.")
        sys.exit(1)

    # Step 3: Create entertainment group
    print(f"\n=== Step 2: Create Entertainment group with lights {reachable} ===")

    # Check for existing group first
    existing = check_existing_entertainment(bridge, token)
    if existing:
        cfg["hue"]["entertainment_group_id"] = existing
    else:
        group_id = create_entertainment_group(bridge, token, reachable)
        cfg["hue"]["entertainment_group_id"] = group_id

    # Save config
    save_config(cfg)

    print("\n=== Setup complete ===")
    print("Entertainment API is ready. Restart ambilight-sync.service to use it.")


if __name__ == "__main__":
    main()
