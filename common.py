"""Shared helpers: config loading, paths, JSON IO, house-style hyphenation.
Ported from the One Story sibling project; kept deliberately tiny."""
from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))


def _path(*parts: str) -> str:
    return os.path.join(ROOT, *parts)


def load_settings() -> dict:
    with open(_path("config", "settings.yaml"), "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_yaml(rel_path: str) -> dict:
    with open(_path(rel_path), "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def tz_now(settings: dict) -> datetime:
    return datetime.now(ZoneInfo(settings["timezone"]))


def read_json(rel_path: str, default=None):
    path = _path(rel_path)
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(rel_path: str, obj) -> str:
    path = _path(rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
    return path


def rel(path: str) -> str:
    return _path(path)


def hyphenate(text: str) -> str:
    """House style: no em/en dashes anywhere - collapse to a plain hyphen."""
    return (text or "").replace("\u2014", "-").replace("\u2013", "-")
