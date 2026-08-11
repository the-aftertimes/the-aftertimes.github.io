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


#: Words the model shouts that stay lowercase inside a place name.
_PLACE_MINOR = {"of", "the", "on", "at", "in", "and", "upon", "under", "by",
                "de", "del", "la", "le", "der", "van", "von"}


def _place_word(word: str, first: bool) -> str:
    """Title-case one word, keeping hyphenated compounds sensible:
    ZURICH-ON-STILTS -> Zurich-on-Stilts, SILT-REACH -> Silt-Reach."""
    parts = word.split("-")
    out = []
    for i, p in enumerate(parts):
        if not p:
            out.append(p)
        elif p.lower() in _PLACE_MINOR and not (first and i == 0):
            out.append(p.lower())
        else:
            out.append(p[:1].upper() + p[1:].lower())
    return "-".join(out)


def normalise_place(place: str) -> str:
    """Even out the case of a dateline place.

    The model shouts some of them and not others - the archive held
    'THE AETHELGARD RING' and 'SHACKLETON DOME, THE MOON' next to
    'Port Low-G, Vesta', which read as a mistake in a list.

    ONLY all-caps names are touched, and each comma-separated segment is
    capitalised from its own first word. Anything already mixed-case is returned
    verbatim, because the model's own casing carries meaning this cannot infer:
    'Epsilon Eridani b' is a planet designation and 'Epsilon Eridani B' would be
    a companion star, and 'Port Low-G' is not 'Port Low-g'.
    """
    s = (place or "").strip()
    if not s or not any(c.isalpha() for c in s) or s != s.upper():
        return s
    segments = []
    for seg in s.split(","):
        words = seg.split()
        segments.append(" ".join(_place_word(w, i == 0)
                                 for i, w in enumerate(words)))
    return ", ".join(seg for seg in segments if seg)


# Cloudflare Web Analytics. Feeds the private stats dashboard, which runs ONE
# account-wide GraphQL query and splits the results by `requestHost` - so this is
# deliberately the same token used across every site in the estate, not a per-site
# one. Cookieless, no personal data, ~10KB deferred so it costs nothing visible.
#
# It lives here because render.py and archive.py both emit a <head> and a beacon
# on only one of them would silently under-count. It is a plain constant rather
# than inline HTML because both call sites are f-strings, where the token's braces
# would otherwise need escaping and would eventually get it wrong.
BEACON = (
    '<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
    '''data-cf-beacon='{"token": "32b821209b5441a08df42ccf61c9e6c2"}'></script>'''
)
