"""The vibe bible: a growing store of coined motifs (wires, orgs, places, slang,
tech) that may resurface for texture. Consistency is not enforced."""
from __future__ import annotations

import random as _random

from common import read_json, write_json


def load_bible() -> dict:
    return read_json("data/bible.json", default={"motifs": []}) or {"motifs": []}


def save_bible(bible: dict) -> str:
    return write_json("data/bible.json", bible)


def random_slice(bible: dict, n: int, rng: _random.Random) -> list[dict]:
    motifs = bible.get("motifs", [])
    if n >= len(motifs):
        return list(motifs)
    return rng.sample(motifs, n)


def merge_glossary(bible: dict, glossary: list[dict], run_date: str) -> dict:
    """Append new glossary terms, deduped case-insensitively on `term`."""
    existing = {m["term"].strip().lower() for m in bible.get("motifs", [])}
    for g in glossary or []:
        term = (g.get("term") or "").strip()
        if not term or term.lower() in existing:
            continue
        bible.setdefault("motifs", []).append({
            "term": term,
            "gloss": (g.get("gloss") or "").strip(),
            "kind": g.get("kind", "term"),
            "first_seen": run_date,
        })
        existing.add(term.lower())
    return bible
