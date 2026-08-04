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


#: Every dash-like codepoint collapses to a plain hyphen. Covers the WHOLE family,
#: not just em/en: 04/08/2026 a model emitted U+2011 non-breaking hyphens
#: ("grief\u2011counselling") and nine of them sailed through the old two-character
#: version straight towards the page.
#: Built from codepoints so this file stays free of literal dash characters.
_DASH_CODEPOINTS = (
    0x2010,  # hyphen
    0x2011,  # non-breaking hyphen
    0x2012,  # figure dash
    0x2013,  # en dash
    0x2014,  # em dash
    0x2015,  # horizontal bar
    0x2043,  # hyphen bullet
    0x2212,  # minus sign
    0xFE58,  # small em dash
    0xFE63,  # small hyphen-minus
    0xFF0D,  # fullwidth hyphen-minus
)
_DASH_MAP = {cp: "-" for cp in _DASH_CODEPOINTS}


def hyphenate(text: str) -> str:
    """House style: no em/en dashes or any other dash variant - all become '-'."""
    return (text or "").translate(_DASH_MAP)
