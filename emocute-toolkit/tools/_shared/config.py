"""共有設定ローダ。~/.config/emocute/ を参照。

config.yaml / credentials.yaml / pj_map.yaml の 3 つ。
credentials.yaml は permission 600 を強制（警告のみ、auto-fix しない）。
"""
from __future__ import annotations
import os
import stat
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path.home() / ".config" / "emocute"
DEFAULT_PJ_MAP = {
    "Studio": str(Path.home() / "Downloads/Studio"),
    "Visual": str(Path.home() / "Downloads/Visual"),
    "Sale": str(Path.home() / "Downloads/Sale"),
    "Site": str(Path.home() / "Downloads/Site"),
    "HarmonyScope": str(Path.home() / "Downloads/HarmonyScope"),
    "Numbloom": str(Path.home() / "Downloads/Numbloom"),
    "Idiograph": str(Path.home() / "Downloads/Idiograph"),
    "Harmonizer": str(Path.home() / "Downloads/Harmonizer"),
    "Health": str(Path.home() / "Downloads/Health"),
    "Kagebu": str(Path.home() / "Downloads/Kagebu"),
    "Sketches": str(Path.home() / "Downloads/Sketches"),
}


def _load_yaml(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    with path.open() as f:
        return yaml.safe_load(f) or default


@lru_cache(maxsize=1)
def config() -> dict:
    return _load_yaml(CONFIG_DIR / "config.yaml", {
        "log_level": "info",
        "dashboard_port": 0,  # static file 配信、不要
        "default_dry_run": True,
    })


@lru_cache(maxsize=1)
def pj_map() -> dict:
    return _load_yaml(CONFIG_DIR / "pj_map.yaml", DEFAULT_PJ_MAP)


@lru_cache(maxsize=1)
def credentials() -> dict:
    path = CONFIG_DIR / "credentials.yaml"
    if path.exists():
        mode = path.stat().st_mode & 0o777
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            import sys
            print(f"[warn] {path} permissions {oct(mode)} too open (recommend 600)", file=sys.stderr)
    return _load_yaml(path, {})


def cred(key: str, default=None):
    """dotted-path 取得: cred('vercel.token')."""
    cur = credentials()
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def pj_path(name: str) -> Path:
    """PJ 名 → 絶対パス。"""
    p = pj_map().get(name)
    if not p:
        raise KeyError(f"unknown pj: {name}")
    return Path(p)
