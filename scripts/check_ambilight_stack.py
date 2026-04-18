#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


class HALoader(yaml.SafeLoader):
    pass


def _construct_tag(loader: HALoader, node: yaml.Node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


HALoader.add_multi_constructor("!", lambda loader, suffix, node: _construct_tag(loader, node))


def parse_yaml(path: Path) -> None:
    with path.open() as fh:
        yaml.load(fh, Loader=HALoader)


def main() -> None:
    tracked = [
        REPO_ROOT / "ha_config" / "configuration.yaml",
        REPO_ROOT / "ha_config" / "automations.yaml",
        REPO_ROOT / "ha_config" / "scripts.yaml",
        REPO_ROOT / "ha_config" / "ui-lovelace.yaml",
        REPO_ROOT / "ambisync_config" / "config.example.yml",
        REPO_ROOT / "ha_config" / "secrets.example.yaml",
    ]
    optional = [
        REPO_ROOT / "ambisync_config" / "config.yml",
        REPO_ROOT / "ha_config" / "secrets.yaml",
    ]

    for path in tracked:
        parse_yaml(path)
        print(f"[check] ok yaml: {path.relative_to(REPO_ROOT)}")

    for path in optional:
        if path.exists():
            parse_yaml(path)
            print(f"[check] ok local: {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
