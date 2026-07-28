# The Aftertimes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily AI-generated "news from the future" static site (The Aftertimes) that generates one dispatch/day with Gemini, renders a bone-broadsheet page + growing archive, and publishes free via GitHub Actions + Pages.

**Architecture:** A four-stage Python pipeline (`ideate -> select -> write -> render`) orchestrated by `run.py`, mirroring the sibling project One Story's shape but inverting its core from deterministic real-news aggregation to LLM fiction generation. Deterministic helpers (date sampler, anti-repetition ledger, vibe bible, JSON repair, renderer) are unit-tested; the two Gemini-calling stages are tested against a mocked client and validated once against the live free tier before the first cron. State (past dispatches, coined motifs, recent-era ledger) is committed to the repo so the archive and anti-repetition accumulate over time.

**Tech Stack:** Python 3.13, Gemini 2.5 Flash via the REST API (`requests`, free AI Studio tier), scikit-learn (TF-IDF novelty, ported from One Story), PyYAML, pytest. GitHub Actions (daily cron) + GitHub Pages (org page). Brevo (newsletter, no backend).

**Reference:** the design spec at `docs/superpowers/specs/2026-07-28-the-aftertimes-design.md`. The sibling codebase to port idioms from is at `C:\Users\CharlieTrenorden\dev\one-story` (read-only reference - do not modify it).

---

## Key conventions (read before starting)

- **House style:** Australian English. **No em/en dashes anywhere** in code, comments, or generated/rendered text - plain hyphens only. A `_hyphenate()` helper enforces this on all rendered/model text.
- **Deep-future dates break `datetime.date`** (its max year is 9999). The future dateline is therefore represented as plain ints `(year, month, day)`, never a `date` object. Only "today" is a real `date`.
- **Zero cost is a hard constraint.** Never introduce a paid API or paid host. Gemini calls are ~2/day, inside the free tier.
- **TDD:** write the failing test, watch it fail, implement minimally, watch it pass, commit. One logical change per commit.
- **Run tests from the repo root** with `python -m pytest`. All paths below are relative to the repo root `C:\Users\CharlieTrenorden\dev\the-aftertimes`.

## File structure (created across the tasks below)

```
the-aftertimes/
  common.py            # config/paths/json + _hyphenate (ported from one-story)
  dates.py             # weighted future-date sampler + anti-clustering
  ledger.py            # anti-repetition ledger + TF-IDF novelty gate
  bible.py             # vibe-bible load / random slice / dedup-append
  gemini.py            # Gemini REST client + defensive JSON extraction
  ideate.py            # stage 1: brainstorm ~8 premises
  select.py            # stage 2: novelty gate + pick
  write.py             # stage 3: write the full dispatch record
  render.py            # stage 4: render index.html + a single-dispatch permalink
  archive.py           # build archive.html (list + future timeline)
  email_render.py      # Brevo email body (ported from one-story)
  run.py               # orchestrator + stale-fallback + archive/ledger/bible writes
  replay.py            # offline re-render from a saved dispatch (no API call)
  config/
    settings.yaml
    domains.yaml
    seed_premises.yaml
  data/
    dispatches/        # YYYY-MM-DD.json (one committed record per day)
    bible.json
    ledger.json
  assets/
    favicon.svg
  d/                   # rendered permalinks: YYYY-MM-DD.html
  tests/
    conftest.py
    test_dates.py
    test_ledger.py
    test_bible.py
    test_gemini.py
    test_stages.py
    test_render.py
    test_run.py
  requirements.txt
  .gitignore
  .github/workflows/daily.yml
```

---

## Phase 0: Scaffold and shared helpers

### Task 0: Repo, deps, gitignore

**Files:**
- Create: `requirements.txt`, `.gitignore`

- [ ] **Step 1: Write `requirements.txt`**

```
requests>=2.31
PyYAML>=6.0
scikit-learn>=1.3
python-dateutil>=2.8
tzdata>=2024.1
pytest>=8.0
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
.superpowers/
.env
```

- [ ] **Step 3: Create a virtualenv and install**

Run:
```bash
cd "C:/Users/CharlieTrenorden/dev/the-aftertimes"
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```
Expected: installs cleanly. Use `.venv/Scripts/python` for all subsequent `python`/`pytest` runs.

- [ ] **Step 4: Commit**

```bash
git init
git add requirements.txt .gitignore
git commit -m "chore: scaffold repo and dependencies"
```

### Task 1: `common.py` (ported helpers)

**Files:**
- Create: `common.py`

- [ ] **Step 1: Write `common.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add common.py
git commit -m "feat: add common helpers (config, json, hyphenate)"
```

### Task 2: Config files (settings, domains, seed premises)

**Files:**
- Create: `config/settings.yaml`, `config/domains.yaml`, `config/seed_premises.yaml`

- [ ] **Step 1: Write `config/settings.yaml`**

```yaml
site:
  name: "The Aftertimes"
  tagline: "Dispatches from years that have not yet happened"
  base_url: "https://the-aftertimes.github.io"
timezone: "Australia/Sydney"
update_hour_utc: 20
output_html: "index.html"
signup_form_url: ""   # Brevo form action; filled in when the newsletter is activated

dates:
  min_years: 8
  band_weights: [0.70, 0.25, 0.05]   # near, mid, deep
  bands:
    near: [8, 300]
    mid: [300, 3000]
    deep: [3000, 40000]
  anti_cluster:
    era_bucket_years: 50    # two dates in the same 50-year bucket count as the same era
    avoid_recent_days: 5    # do not reuse an era used within the last N dispatches
    max_attempts: 12        # resample attempts before giving up

ideate:
  n_premises: 8
  bible_slice_size: 6       # how many bible motifs to offer the model as optional colour
  recent_premise_window: 20 # how many recent headlines/premises to show as "avoid"

novelty:
  match_threshold: 0.45     # cosine >= this vs a recent dispatch = too similar, reject
  recent_window: 30         # compare against the last N dispatches

gemini:
  model: "gemini-2.5-flash"
  endpoint: "https://generativelanguage.googleapis.com/v1beta/models"
  timeout_seconds: 60
  max_retries: 2
  temperature_ideate: 1.1
  temperature_write: 0.9
```

- [ ] **Step 2: Write `config/domains.yaml`**

```yaml
# Domain axes the ideate stage samples from. Steer the *space*, not the idea.
domains:
  - biotech
  - space law
  - artificial intelligence rights
  - sport
  - religion
  - food
  - love and marriage
  - crime
  - money and finance
  - art
  - death and mourning
  - weather and climate
  - governance and elections
  - language and slang
  - family
  - medicine
  - ecology and wildlife
  - entertainment
  - transport
  - labour and work
```

- [ ] **Step 3: Write `config/seed_premises.yaml`** (first-pass taste-setters; Charlie edits later)

```yaml
# Few-shot examples that teach the ideate stage the house sense of humour:
# straight-faced, absurd, satirical sci-fi. NOT a consumable queue.
seed_premises:
  - "A moon of Saturn votes to secede, citing irreconcilable time zones."
  - "The last human accountant is legally declared a protected cultural site."
  - "A floating capital city sues the sea for breach of contract."
  - "Two artificial intelligences file for divorce; custody of a shared API is contested."
  - "A man sues his own clone for defamation and loses the case to himself."
  - "A nation abolishes money on a Tuesday and forgets to tell the vending machines."
  - "A generation ship arrives to find its destination already settled by a later, faster ship."
  - "Mars introduces daylight saving; three towns are lost to the paperwork."
  - "A museum of extinct jobs opens, its star exhibit a live working dentist."
  - "The heat death of the universe is postponed for budget reasons."
  - "An ancient AI is found still running a loyalty-points scheme for a supermarket that closed centuries ago."
  - "A city elects a river as mayor; it governs by flooding selectively."
```

- [ ] **Step 4: Commit**

```bash
git add config/
git commit -m "feat: add settings, domain axes and seed premises"
```

---

## Phase 1: Date sampler

### Task 3: `dates.py` - weighted future-date sampler with anti-clustering

**Files:**
- Create: `dates.py`
- Test: `tests/test_dates.py`, `tests/conftest.py`

- [ ] **Step 1: Write `tests/conftest.py`** (shared fixtures)

```python
import random
import pytest


@pytest.fixture
def rng():
    return random.Random(12345)


@pytest.fixture
def date_cfg():
    return {
        "min_years": 8,
        "band_weights": [0.70, 0.25, 0.05],
        "bands": {"near": [8, 300], "mid": [300, 3000], "deep": [3000, 40000]},
        "anti_cluster": {"era_bucket_years": 50, "avoid_recent_days": 5,
                         "max_attempts": 12},
    }
```

- [ ] **Step 2: Write the failing tests `tests/test_dates.py`**

```python
from datetime import date
import random

from dates import sample_future_dateline, era_bucket, format_dateline


def test_sample_is_in_the_future(rng, date_cfg):
    dl = sample_future_dateline(date(2026, 7, 28), date_cfg, set(), rng)
    assert dl["year"] > 2026
    assert dl["years_from_now"] >= date_cfg["min_years"]
    assert 1 <= dl["month"] <= 12
    assert 1 <= dl["day"] <= 28


def test_deep_future_year_does_not_crash(date_cfg):
    # Force the deep band; year can exceed 9999 (datetime.date would raise).
    rng = random.Random(2)
    date_cfg = {**date_cfg, "band_weights": [0.0, 0.0, 1.0]}
    dl = sample_future_dateline(date(2026, 1, 1), date_cfg, set(), rng)
    assert dl["year"] >= 2026 + 3000
    assert isinstance(dl["year"], int)


def test_anti_clustering_avoids_recent_eras(date_cfg):
    # If every near/mid era is "recent", the sampler still returns something
    # (falls through after max_attempts) but tries to avoid the blocked set.
    rng = random.Random(7)
    dl = sample_future_dateline(date(2026, 1, 1), date_cfg, set(), rng)
    blocked = {era_bucket(dl["years_from_now"], 50)}
    dl2 = sample_future_dateline(date(2026, 1, 1), date_cfg, blocked, random.Random(7))
    assert era_bucket(dl2["years_from_now"], 50) not in blocked or dl2["years_from_now"] != dl["years_from_now"]


def test_format_dateline_no_dashes_and_grouped_years():
    txt = format_dateline({"place": "Port Kobenhavn-2", "year": 40312,
                           "month": 9, "day": 4, "years_from_now": 38286})
    assert "September" in txt
    assert "40312" in txt or "40,312" in txt
    assert "\u2014" not in txt and "\u2013" not in txt
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_dates.py -v`
Expected: FAIL (ImportError: cannot import name from `dates`).

- [ ] **Step 4: Implement `dates.py`**

```python
"""Weighted-random future-date sampler.

The future dateline is plain ints (year, month, day) - NOT a datetime.date,
because deep-future years exceed date's max of 9999. Only 'today' is a date.
"""
from __future__ import annotations

import math
import random as _random
from datetime import date

_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def era_bucket(years_from_now: int, bucket_years: int) -> int:
    return years_from_now // bucket_years


def _sample_years(rng: _random.Random, cfg: dict) -> int:
    band = rng.choices(["near", "mid", "deep"], weights=cfg["band_weights"], k=1)[0]
    lo, hi = cfg["bands"][band]
    lo = max(lo, cfg["min_years"])
    # log-uniform within the band favours the nearer end.
    u = rng.random()
    years = int(round(math.exp(math.log(lo) + u * (math.log(hi) - math.log(lo)))))
    return max(lo, min(hi, years))


def sample_future_dateline(today: date, cfg: dict, recent_eras: set[int],
                           rng: _random.Random | None = None) -> dict:
    """Return a dateline dict: place is filled later by the writer stage."""
    rng = rng or _random.Random()
    ac = cfg["anti_cluster"]
    years = _sample_years(rng, cfg)
    for _ in range(ac["max_attempts"]):
        if era_bucket(years, ac["era_bucket_years"]) not in recent_eras:
            break
        years = _sample_years(rng, cfg)
    return {
        "place": "",                       # set by write stage
        "year": today.year + years,
        "month": rng.randint(1, 12),
        "day": rng.randint(1, 28),         # 28 keeps every month valid
        "years_from_now": years,
    }


def format_dateline(dl: dict) -> str:
    """e.g. 'Port Kobenhavn-2 . 4 September 40,312'. No dashes in the date."""
    place = (dl.get("place") or "").strip()
    ymd = f"{dl['day']} {_MONTHS[dl['month'] - 1]} {dl['year']:,}"
    return f"{place} . {ymd}".strip(" .") if place else ymd


def years_phrase(years_from_now: int) -> str:
    return f"{years_from_now:,} years from today"
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_dates.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add dates.py tests/conftest.py tests/test_dates.py
git commit -m "feat: weighted future-date sampler with anti-clustering"
```

---

## Phase 2: Anti-repetition ledger and novelty gate

### Task 4: `ledger.py`

The ledger records, per past dispatch: run date, dateline year, era bucket, domain, and headline text (for TF-IDF novelty). It answers two questions: "which eras/domains are recent?" (for the sampler and ideate prompt) and "is this candidate too similar to a recent dispatch?" (novelty gate).

**Files:**
- Create: `ledger.py`
- Test: `tests/test_ledger.py`

- [ ] **Step 1: Write failing tests `tests/test_ledger.py`**

```python
from ledger import recent_eras, recent_domains, is_novel, append_entry


LEDGER = [
    {"run_date": "2026-07-20", "era_bucket": 2, "domain": "sport",
     "headline": "Robot umpire defects to the other team"},
    {"run_date": "2026-07-21", "era_bucket": 40, "domain": "money and finance",
     "headline": "Nation abolishes money on a Tuesday"},
]


def test_recent_eras_collects_buckets():
    assert recent_eras(LEDGER, last_n=5) == {2, 40}


def test_recent_domains_collects_domains():
    assert "sport" in recent_domains(LEDGER, last_n=5)


def test_is_novel_rejects_near_duplicate():
    cand = "A nation abolishes money on a Tuesday and tells no one"
    assert is_novel(cand, LEDGER, threshold=0.45, window=30) is False


def test_is_novel_accepts_fresh_headline():
    cand = "Saturn's moon secedes over irreconcilable time zones"
    assert is_novel(cand, LEDGER, threshold=0.45, window=30) is True


def test_is_novel_true_on_empty_ledger():
    assert is_novel("anything at all", [], threshold=0.45, window=30) is True


def test_append_entry_shape():
    entry = append_entry([], run_date="2026-07-28",
                         dateline={"year": 2391, "years_from_now": 365},
                         domain="crime", headline="Someone sues their own clone",
                         era_bucket_years=50)
    assert entry[-1]["era_bucket"] == 365 // 50
    assert entry[-1]["domain"] == "crime"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_ledger.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement `ledger.py`**

```python
"""Anti-repetition ledger + TF-IDF novelty gate (novelty approach ported from
One Story). The ledger is a JSON list committed to the repo; it grows one entry
per successful dispatch."""
from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from common import read_json, write_json


def load_ledger() -> list[dict]:
    return read_json("data/ledger.json", default=[]) or []


def save_ledger(ledger: list[dict]) -> str:
    return write_json("data/ledger.json", ledger)


def recent_eras(ledger: list[dict], last_n: int) -> set[int]:
    return {e["era_bucket"] for e in ledger[-last_n:] if "era_bucket" in e}


def recent_domains(ledger: list[dict], last_n: int) -> list[str]:
    return [e["domain"] for e in ledger[-last_n:] if e.get("domain")]


def recent_headlines(ledger: list[dict], window: int) -> list[str]:
    return [e["headline"] for e in ledger[-window:] if e.get("headline")]


def is_novel(candidate: str, ledger: list[dict], threshold: float,
             window: int) -> bool:
    """True if `candidate` is not too close to any recent headline."""
    past = recent_headlines(ledger, window)
    if not past:
        return True
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                          sublinear_tf=True)
    tfidf = vec.fit_transform(past + [candidate])
    sims = linear_kernel(tfidf[-1:], tfidf[:-1]).ravel()
    return float(sims.max()) < threshold


def append_entry(ledger: list[dict], run_date: str, dateline: dict, domain: str,
                 headline: str, era_bucket_years: int) -> list[dict]:
    ledger.append({
        "run_date": run_date,
        "year": dateline["year"],
        "era_bucket": dateline["years_from_now"] // era_bucket_years,
        "domain": domain,
        "headline": headline,
    })
    return ledger
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_ledger.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add ledger.py tests/test_ledger.py
git commit -m "feat: anti-repetition ledger and TF-IDF novelty gate"
```

---

## Phase 3: Vibe bible

### Task 5: `bible.py`

**Files:**
- Create: `bible.py`, `data/bible.json` (seed)
- Test: `tests/test_bible.py`

- [ ] **Step 1: Write seed `data/bible.json`**

```json
{
  "motifs": [
    {"term": "Nordwire", "gloss": "pan-Baltic newswire, est. 2334", "kind": "wire", "first_seen": "seed"},
    {"term": "Tide & Wren", "gloss": "first law firm to represent a non-human client", "kind": "org", "first_seen": "seed"},
    {"term": "Solar Wire", "gloss": "pan-system newswire of record", "kind": "wire", "first_seen": "seed"}
  ]
}
```

- [ ] **Step 2: Write failing tests `tests/test_bible.py`**

```python
from bible import random_slice, merge_glossary


BIBLE = {"motifs": [
    {"term": "Nordwire", "gloss": "pan-Baltic newswire", "kind": "wire", "first_seen": "seed"},
    {"term": "Solar Wire", "gloss": "pan-system newswire", "kind": "wire", "first_seen": "seed"},
    {"term": "Tide & Wren", "gloss": "non-human law firm", "kind": "org", "first_seen": "seed"},
]}


def test_random_slice_size_and_membership(rng):
    sl = random_slice(BIBLE, 2, rng)
    assert len(sl) == 2
    assert all(m in BIBLE["motifs"] for m in sl)


def test_random_slice_caps_at_available(rng):
    sl = random_slice(BIBLE, 99, rng)
    assert len(sl) == 3


def test_merge_glossary_dedups_case_insensitively():
    glossary = [{"term": "nordwire", "gloss": "dup"},
                {"term": "Chrono Bureau", "gloss": "time regulator"}]
    merged = merge_glossary(BIBLE, glossary, run_date="2026-07-28")
    terms = [m["term"].lower() for m in merged["motifs"]]
    assert terms.count("nordwire") == 1
    assert "chrono bureau" in terms
    added = [m for m in merged["motifs"] if m["term"] == "Chrono Bureau"][0]
    assert added["first_seen"] == "2026-07-28"
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_bible.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 4: Implement `bible.py`**

```python
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
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_bible.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add bible.py data/bible.json tests/test_bible.py
git commit -m "feat: vibe-bible slice and dedup-merge"
```

---

## Phase 4: Gemini client

### Task 6: `gemini.py` - REST client + defensive JSON extraction

**Files:**
- Create: `gemini.py`
- Test: `tests/test_gemini.py`

- [ ] **Step 1: Write failing tests `tests/test_gemini.py`**

```python
import pytest

from gemini import extract_json, GeminiError


def test_extract_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    raw = "```json\n{\"headline\": \"hi\"}\n```"
    assert extract_json(raw) == {"headline": "hi"}


def test_extract_json_with_prose_around_it():
    raw = "Sure! Here is your object:\n{\"x\": [1, 2, 3]}\nHope that helps."
    assert extract_json(raw) == {"x": [1, 2, 3]}


def test_extract_json_raises_on_garbage():
    with pytest.raises(GeminiError):
        extract_json("no json here at all")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_gemini.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement `gemini.py`**

```python
"""Thin Gemini REST client (free AI Studio tier) + defensive JSON extraction.
Uses the API key from the GEMINI_API_KEY environment variable."""
from __future__ import annotations

import json
import os
import re
import time

import requests


class GeminiError(RuntimeError):
    pass


def extract_json(raw: str):
    """Pull the first JSON object/array out of a model response.
    Handles code fences and surrounding prose."""
    if raw is None:
        raise GeminiError("empty response")
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the first {...} or [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = text.find(opener), text.rfind(closer)
        if 0 <= i < j:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                continue
    raise GeminiError(f"no parseable JSON in response: {raw[:200]!r}")


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiError("GEMINI_API_KEY not set")
    return key


def generate(prompt: str, settings: dict, temperature: float) -> str:
    """Call generateContent and return the model's raw text. Retries on
    transient HTTP errors with linear backoff."""
    g = settings["gemini"]
    url = f"{g['endpoint']}/{g['model']}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature,
                             "responseMimeType": "application/json"},
    }
    last = None
    for attempt in range(g["max_retries"] + 1):
        try:
            resp = requests.post(
                url, params={"key": _api_key()}, json=payload,
                timeout=g["timeout_seconds"],
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            last = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except (requests.RequestException, KeyError, IndexError) as exc:
            last = str(exc)
        time.sleep(1.5 * (attempt + 1))
    raise GeminiError(f"generate failed after retries: {last}")
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_gemini.py -v`
Expected: PASS (4 passed). (Only `extract_json` is unit-tested; `generate` is exercised via mocks in Task 7 and live in Task 12.)

- [ ] **Step 5: Commit**

```bash
git add gemini.py tests/test_gemini.py
git commit -m "feat: Gemini REST client and defensive JSON extraction"
```

---

## Phase 5: The three generation stages

### Task 7: `ideate.py`, `select.py`, `write.py`

These call Gemini through `gemini.generate`. Tests inject a fake `generate` via monkeypatch so no network/API key is needed. The prompt builders are pure and separately asserted.

**Files:**
- Create: `ideate.py`, `select.py`, `write.py`
- Test: `tests/test_stages.py`

- [ ] **Step 1: Write failing tests `tests/test_stages.py`**

```python
import json
import random

import gemini
import ideate
import select as select_stage
import write as write_stage


SETTINGS = {
    "ideate": {"n_premises": 8, "bible_slice_size": 2, "recent_premise_window": 20},
    "novelty": {"match_threshold": 0.45, "recent_window": 30},
    "gemini": {"model": "gemini-2.5-flash", "endpoint": "x", "timeout_seconds": 1,
               "max_retries": 0, "temperature_ideate": 1.1, "temperature_write": 0.9},
}


def test_ideate_prompt_mentions_date_domain_and_avoids(rng):
    prompt = ideate.build_prompt(
        dateline={"year": 2391, "years_from_now": 365, "month": 9, "day": 4},
        domain="crime", bible_motifs=[{"term": "Nordwire", "gloss": "wire"}],
        seed_premises=["a clone sues itself"], avoid_headlines=["old headline"],
        n=8)
    assert "2391" in prompt and "crime" in prompt
    assert "Nordwire" in prompt
    assert "old headline" in prompt
    assert "8" in prompt


def test_ideate_returns_premise_list(monkeypatch, rng):
    monkeypatch.setattr(gemini, "generate",
                        lambda *a, **k: json.dumps({"premises": ["a", "b", "c"]}))
    out = ideate.ideate(
        dateline={"year": 2391, "years_from_now": 365, "month": 9, "day": 4},
        domain="crime", bible_motifs=[], seed_premises=[], avoid_headlines=[],
        settings=SETTINGS)
    assert out == ["a", "b", "c"]


def test_select_skips_non_novel(monkeypatch):
    ledger = [{"headline": "a nation abolishes money on a tuesday",
               "domain": "money", "era_bucket": 1}]
    premises = ["A nation abolishes money on a Tuesday",   # dup -> reject
                "Saturn's moon secedes over time zones"]   # novel -> keep
    chosen = select_stage.select(premises, ledger, SETTINGS)
    assert chosen == "Saturn's moon secedes over time zones"


def test_select_falls_back_to_first_when_all_stale(monkeypatch):
    monkeypatch.setattr(select_stage, "is_novel", lambda *a, **k: False)
    premises = ["one", "two"]
    assert select_stage.select(premises, [], SETTINGS) == "one"


def test_write_parses_and_hyphenates(monkeypatch):
    payload = {
        "headline": "Floating Capital Sues the Sea",
        "dateline_place": "Port Kobenhavn-2",
        "body": "An em dash sneaks in \u2014 like this.",
        "wire_name": "Nordwire", "wire_gloss": "pan-Baltic newswire",
        "domain": "law",
        "glossary": [{"term": "Tide & Wren", "gloss": "non-human law firm"}],
    }
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: json.dumps(payload))
    dispatch = write_stage.write(
        premise="a city sues the sea",
        dateline={"place": "", "year": 2391, "years_from_now": 365, "month": 9, "day": 4},
        domain="law", settings=SETTINGS)
    assert dispatch["dateline"]["place"] == "Port Kobenhavn-2"
    assert "\u2014" not in dispatch["body"]      # hyphenated
    assert dispatch["headline"] == "Floating Capital Sues the Sea"
    assert dispatch["glossary"][0]["term"] == "Tide & Wren"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_stages.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement `ideate.py`**

```python
"""Stage 1 - ideate. Ask Gemini for ~N candidate premises for a given future
date + domain, primed with optional bible motifs and seed-premise examples, and
told to avoid recent headlines."""
from __future__ import annotations

import gemini


def build_prompt(dateline: dict, domain: str, bible_motifs: list[dict],
                 seed_premises: list[str], avoid_headlines: list[str],
                 n: int) -> str:
    motif_lines = "\n".join(f"- {m['term']}: {m.get('gloss', '')}"
                            for m in bible_motifs) or "(none yet)"
    seed_lines = "\n".join(f"- {p}" for p in seed_premises) or "(none)"
    avoid_lines = "\n".join(f"- {h}" for h in avoid_headlines) or "(none)"
    return f"""You are the wire desk of The Aftertimes, a newspaper filing real
news dispatches from the future. The register is imaginative science fiction with
a knowing satirical edge: strange, funny, but written completely straight-faced,
as a real newswire would.

Brainstorm {n} one-sentence story premises datelined the year {dateline['year']}
({dateline['years_from_now']} years from now), in the domain: {domain}.

Each premise must be surprising, specific, and self-contained. Vary them widely.
Do NOT explain them. Straight-faced, never winking.

Example premises for tone (do not reuse these):
{seed_lines}

You may (optionally) reuse any of these established motifs for texture:
{motif_lines}

Avoid anything close to these recently-used stories:
{avoid_lines}

Return JSON only: {{"premises": ["...", "...", ...]}} with exactly {n} items."""


def ideate(dateline: dict, domain: str, bible_motifs: list[dict],
           seed_premises: list[str], avoid_headlines: list[str],
           settings: dict) -> list[str]:
    prompt = build_prompt(dateline, domain, bible_motifs, seed_premises,
                          avoid_headlines, settings["ideate"]["n_premises"])
    raw = gemini.generate(prompt, settings,
                          settings["gemini"]["temperature_ideate"])
    data = gemini.extract_json(raw)
    premises = [p.strip() for p in data.get("premises", []) if p and p.strip()]
    if not premises:
        raise gemini.GeminiError("ideate returned no premises")
    return premises
```

- [ ] **Step 4: Implement `select.py`**

```python
"""Stage 2 - select. Pick the first premise that passes the novelty gate;
fall back to the first premise if every candidate is too close to a recent one."""
from __future__ import annotations

from ledger import is_novel


def select(premises: list[str], ledger: list[dict], settings: dict) -> str:
    nov = settings["novelty"]
    for premise in premises:
        if is_novel(premise, ledger, nov["match_threshold"], nov["recent_window"]):
            return premise
    return premises[0]
```

- [ ] **Step 5: Implement `write.py`**

```python
"""Stage 3 - write. Turn the chosen premise into a full dispatch record."""
from __future__ import annotations

import gemini
from common import hyphenate


def build_prompt(premise: str, dateline: dict, domain: str) -> str:
    return f"""You are a correspondent for The Aftertimes. Write a single news
dispatch, datelined the year {dateline['year']}
({dateline['years_from_now']} years from now), in the domain: {domain}.

The premise: {premise}

Rules:
- 250 to 350 words. Straight-faced, as a real wire story. Dry wit, never winking.
- Invent a plausible future place for the dateline.
- File it under an invented future newswire.
- Coin 1 to 3 world-specific terms and define each in one line for the glossary.
- Do not use em dashes or en dashes. Use plain hyphens.

Return JSON only:
{{"headline": "...", "dateline_place": "...", "body": "...",
  "wire_name": "...", "wire_gloss": "...", "domain": "{domain}",
  "glossary": [{{"term": "...", "gloss": "..."}}]}}"""


def write(premise: str, dateline: dict, domain: str, settings: dict) -> dict:
    prompt = build_prompt(premise, dateline, domain)
    raw = gemini.generate(prompt, settings,
                          settings["gemini"]["temperature_write"])
    d = gemini.extract_json(raw)
    dl = dict(dateline)
    dl["place"] = hyphenate((d.get("dateline_place") or "").strip())
    return {
        "headline": hyphenate((d.get("headline") or "").strip()),
        "body": hyphenate((d.get("body") or "").strip()),
        "dateline": dl,
        "wire": {"name": hyphenate((d.get("wire_name") or "").strip()),
                 "gloss": hyphenate((d.get("wire_gloss") or "").strip())},
        "domain": (d.get("domain") or domain).strip(),
        "glossary": [{"term": hyphenate(g.get("term", "").strip()),
                      "gloss": hyphenate(g.get("gloss", "").strip())}
                     for g in d.get("glossary", []) if g.get("term")],
        "premise": premise,
    }
```

- [ ] **Step 6: Run to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_stages.py -v`
Expected: PASS (6 passed).

- [ ] **Step 7: Commit**

```bash
git add ideate.py select.py write.py tests/test_stages.py
git commit -m "feat: ideate, select and write generation stages"
```

---

## Phase 6: Renderer

### Task 8: `render.py` - the bone-broadsheet page + permalink

The renderer is pure: `render_dispatch(dispatch, meta, stale=False) -> str`. `run.py` writes both `index.html` (today) and `d/YYYY-MM-DD.html` (permalink) from it. A golden test pins the structure so CSS edits are reviewable without API calls.

**Files:**
- Create: `render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write failing tests `tests/test_render.py`**

```python
from render import render_dispatch


DISPATCH = {
    "headline": "Floating Capital Sues the Sea for Breach of Contract",
    "body": "The North Atlantic declined to comment. Lawyers for the ocean called it terrestrial.",
    "dateline": {"place": "Port Kobenhavn-2", "year": 2391, "month": 9, "day": 4,
                 "years_from_now": 365},
    "wire": {"name": "Nordwire", "gloss": "pan-Baltic newswire, est. 2334"},
    "domain": "law",
    "glossary": [{"term": "Tide & Wren", "gloss": "non-human law firm"}],
    "premise": "a city sues the sea",
}
META = {"run_time": "2026-07-28T20:00:00+00:00", "timezone": "Australia/Sydney",
        "tagline": "Dispatches from years that have not yet happened",
        "site_name": "The Aftertimes", "signup_form_url": "",
        "base_url": "https://the-aftertimes.github.io"}


def test_render_contains_core_elements():
    html = render_dispatch(DISPATCH, META)
    assert "The Aftertimes" in html
    assert "Floating Capital Sues the Sea" in html
    assert "September" in html and "2,391".replace(",", "") in html.replace(",", "")
    assert "365 years from today" in html
    assert "Nordwire" in html
    assert "Tide &amp; Wren" in html or "Tide & Wren" in html
    assert "fiction" in html.lower()          # framing footer present


def test_render_escapes_html():
    d = {**DISPATCH, "headline": "Robots <script>alert(1)</script> revolt"}
    html = render_dispatch(d, META)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_no_dashes_in_output():
    html = render_dispatch(DISPATCH, META)
    assert "\u2014" not in html and "\u2013" not in html


def test_stale_banner_toggles():
    assert "Showing yesterday" not in render_dispatch(DISPATCH, META, stale=False)
    assert "Showing yesterday" in render_dispatch(DISPATCH, META, stale=True)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_render.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement `render.py`**

```python
"""Stage 4 - render. Turn a dispatch record into the bone-broadsheet HTML.
All model/feed text is HTML-escaped and hyphenated. Pure function; run.py owns IO."""
from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

from common import hyphenate
from dates import format_dateline, years_phrase

_CSS = """
:root{--bg:#f4efe3;--fg:#1a1611;--muted:#6b5f4d;--accent:#7a2b2b;--rule:#cdc3ad;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:Georgia,'Times New Roman',serif;line-height:1.55;
  -webkit-font-smoothing:antialiased;}
.wrap{max-width:44rem;margin:0 auto;padding:clamp(2rem,7vw,4.5rem) 1.5rem 4rem;
  min-height:100vh;display:flex;flex-direction:column;}
.masthead{text-align:center;border-bottom:3px double var(--fg);padding-bottom:0.9rem;
  margin-bottom:2rem;}
.masthead .name{font-size:clamp(2.4rem,9vw,3.6rem);font-weight:700;line-height:1;
  letter-spacing:0.01em;}
.masthead .tag{font-family:-apple-system,system-ui,sans-serif;font-size:0.62rem;
  letter-spacing:0.3em;text-transform:uppercase;color:var(--muted);margin-top:0.7rem;}
.dateline{font-family:-apple-system,system-ui,sans-serif;font-size:0.72rem;
  font-weight:600;letter-spacing:0.14em;text-transform:uppercase;color:var(--accent);
  margin:0 0 0.8rem;}
h1{font-size:clamp(1.9rem,6vw,2.9rem);line-height:1.12;font-weight:700;
  margin:0 0 1.1rem;letter-spacing:-0.01em;}
.body p{font-size:clamp(1.02rem,2.6vw,1.16rem);margin:0 0 1rem;}
.filed{font-family:-apple-system,system-ui,sans-serif;font-size:0.82rem;
  font-style:italic;color:var(--muted);margin:0.5rem 0 0;}
.meta{font-family:-apple-system,system-ui,sans-serif;margin-top:1.8rem;}
.meta summary{cursor:pointer;color:var(--accent);font-weight:600;font-size:0.82rem;
  letter-spacing:0.16em;text-transform:uppercase;padding:0.5rem 0;
  border-top:1px solid var(--rule);}
.meta-body{color:var(--muted);font-size:0.9rem;padding-top:0.6rem;}
.meta-facts{display:flex;gap:1.2rem;flex-wrap:wrap;margin-bottom:0.7rem;}
.meta-facts b{color:var(--fg);}
.gloss{list-style:none;margin:0;padding:0;}
.gloss li{padding:0.35rem 0;border-top:1px solid var(--rule);}
.gloss b{color:var(--fg);}
.stale{font-family:-apple-system,system-ui,sans-serif;font-size:0.85rem;
  background:var(--accent);color:var(--bg);padding:0.6rem 1rem;border-radius:0.3rem;
  margin-bottom:1.8rem;}
.signup{margin:2.5rem 0 0;padding:1.5rem 0 0;border-top:1px solid var(--rule);
  font-family:-apple-system,system-ui,sans-serif;}
.signup-lead{margin:0 0 0.9rem;color:var(--fg);font-weight:600;}
.signup-form{display:flex;flex-wrap:wrap;gap:0.5rem;}
.signup-form input{flex:1 1 12rem;min-width:0;padding:0.6rem 0.8rem;font-size:0.95rem;
  color:var(--fg);background:#fff;border:1px solid var(--rule);border-radius:0.3rem;
  font-family:inherit;}
.signup-form button{padding:0.6rem 1.2rem;font-weight:600;cursor:pointer;
  color:var(--bg);background:var(--accent);border:none;border-radius:0.3rem;
  font-family:inherit;}
.signup-note{margin:0.7rem 0 0;color:var(--muted);font-size:0.78rem;}
footer{margin-top:auto;padding-top:3rem;font-family:-apple-system,system-ui,sans-serif;
  font-size:0.78rem;color:var(--muted);}
footer .fiction{font-style:italic;margin:0 0 0.6rem;}
a.arc{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent);}
"""


def _fmt_local(iso: str, tzname: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone(ZoneInfo(tzname))
    return f"{dt.strftime('%d/%m/%Y %H:%M')} {dt.tzname() or ''}".strip()


def _signup(form_url: str) -> str:
    if not form_url:
        return ""
    action = html.escape(form_url, quote=True)
    return f"""<section class="signup">
  <p class="signup-lead">Get one dispatch from the future in your inbox each morning.</p>
  <form action="{action}" method="post" target="at-sink" class="signup-form"
        onsubmit="return atSignup(this)">
    <input type="email" name="EMAIL" placeholder="you@example.com"
           aria-label="Email address" required>
    <input type="text" name="email_address_check" value="" tabindex="-1"
           autocomplete="off" aria-hidden="true" style="position:absolute;left:-5000px;">
    <input type="hidden" name="locale" value="en">
    <input type="hidden" name="html_type" value="simple">
    <button type="submit">Subscribe</button>
  </form>
  <p class="signup-note" id="at-note">One email a day. No tracking. Unsubscribe anytime.</p>
  <iframe name="at-sink" title="subscription" aria-hidden="true" tabindex="-1"
          style="position:absolute;width:0;height:0;border:0;"></iframe>
  <script>function atSignup(f){{setTimeout(function(){{f.style.display='none';
    var n=document.getElementById('at-note');if(n){{n.textContent=
    "Thanks - your first dispatch arrives tomorrow morning.";n.style.color='var(--accent)';}}}},150);
    return true;}}</script>
</section>"""


def render_dispatch(dispatch: dict, meta: dict, stale: bool = False,
                    is_permalink: bool = False) -> str:
    dl = dispatch["dateline"]
    headline = html.escape(hyphenate(dispatch["headline"]))
    dateline_txt = html.escape(hyphenate(format_dateline(dl)))
    years_txt = html.escape(years_phrase(dl["years_from_now"]))
    body_paras = "".join(
        f"<p>{html.escape(hyphenate(p.strip()))}</p>"
        for p in dispatch["body"].split("\n") if p.strip())
    wire = dispatch["wire"]
    filed = html.escape(hyphenate(wire["name"]))
    domain = html.escape(hyphenate(dispatch["domain"]))
    gloss_items = "".join(
        f"<li><b>{html.escape(hyphenate(g['term']))}</b> - "
        f"{html.escape(hyphenate(g['gloss']))}</li>"
        for g in dispatch.get("glossary", []))
    wire_gloss = (f"<li><b>{filed}</b> - {html.escape(hyphenate(wire['gloss']))}</li>"
                  if wire.get("gloss") else "")
    stamp = _fmt_local(meta["run_time"], meta["timezone"])
    stale_banner = ("<div class='stale'>Showing yesterday's dispatch - today's "
                    "edition did not file.</div>" if stale else "")
    signup = "" if is_permalink else _signup(meta.get("signup_form_url", ""))
    archive_link = ('<p><a class="arc" href="archive.html">Browse the archive '
                    '&rarr;</a></p>') if not is_permalink else (
                    '<p><a class="arc" href="../index.html">Today\'s dispatch '
                    '&rarr;</a> &middot; <a class="arc" href="../archive.html">Archive</a></p>')
    title = html.escape(f"{dispatch['headline']} - {meta['site_name']}")
    desc = html.escape("Fiction. A daily news dispatch from a random date in the future.")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f4efe3">
<link rel="icon" type="image/svg+xml" href="{'../' if is_permalink else ''}assets/favicon.svg">
<title>{title}</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="{html.escape(meta['site_name'])}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta name="twitter:card" content="summary_large_image">
<style>{_CSS}</style>
</head>
<body>
  <div class="wrap">
    {stale_banner}
    <header class="masthead">
      <div class="name">{html.escape(meta['site_name'])}</div>
      <div class="tag">{html.escape(hyphenate(meta['tagline']))}</div>
    </header>
    <p class="dateline">{dateline_txt} &middot; {years_txt}</p>
    <h1>{headline}</h1>
    <div class="body">{body_paras}</div>
    <p class="filed">Filed by {filed}</p>
    <details class="meta">
      <summary>Dispatch metadata</summary>
      <div class="meta-body">
        <div class="meta-facts">
          <span><b>{html.escape(str(dl['year']))}</b> &middot; {years_txt}</span>
          <span>Domain: <b>{domain}</b></span>
        </div>
        <ul class="gloss">{wire_gloss}{gloss_items}</ul>
      </div>
    </details>
    {signup}
    {archive_link}
    <footer>
      <p class="fiction">Every dispatch is fiction, written by a machine each
        morning. None of it has happened. Yet.</p>
      Filed {stamp}.
    </footer>
  </div>
</body>
</html>
"""
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_render.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add render.py tests/test_render.py
git commit -m "feat: bone-broadsheet dispatch renderer"
```

---

## Phase 7: Orchestrator + fallback

### Task 9: `run.py`

**Files:**
- Create: `run.py`
- Test: `tests/test_run.py`

- [ ] **Step 1: Write failing tests `tests/test_run.py`** (fallback logic is the testable unit; generation is covered by stage tests + the live run in Task 12)

```python
import os

import run as run_mod


def test_inject_stale_banner_returns_false_when_no_page(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    assert run_mod.inject_stale_banner("index.html") is False


def test_inject_stale_banner_marks_existing_page(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    page = tmp_path / "index.html"
    page.write_text("<body><div class=\"wrap\">hi</div></body>", encoding="utf-8")
    assert run_mod.inject_stale_banner("index.html") is True
    assert "Showing yesterday" in page.read_text(encoding="utf-8")


def test_inject_stale_banner_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    page = tmp_path / "index.html"
    page.write_text("<body><div class=\"wrap\">hi</div></body>", encoding="utf-8")
    run_mod.inject_stale_banner("index.html")
    run_mod.inject_stale_banner("index.html")
    assert page.read_text(encoding="utf-8").count("Showing yesterday") == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_run.py -v`
Expected: FAIL (ImportError / AttributeError).

- [ ] **Step 3: Implement `run.py`**

```python
"""Full pipeline orchestrator + stale fallback.

    python run.py

Sequence: pick a future date + domain -> ideate -> select -> write -> render,
then commit the dispatch to the archive, ledger and bible. Never crash-publishes:
on any failure it keeps the previous index.html and flags it stale."""
from __future__ import annotations

import os
import random
import sys
import traceback
from datetime import date, datetime, timezone

from common import load_settings, load_yaml, read_json, rel, write_json
import bible as bible_mod
import ideate as ideate_stage
import ledger as ledger_mod
import render as render_mod
import select as select_stage
import write as write_stage
from dates import sample_future_dateline

_STALE_MARKER = "Showing yesterday's dispatch"


def inject_stale_banner(output_html: str) -> bool:
    path = rel(output_html)
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as fh:
        doc = fh.read()
    if _STALE_MARKER in doc:
        return True
    banner = ("<div class='stale'>Showing yesterday's dispatch - today's edition "
              "did not file.</div>")
    marker = '<div class="wrap">'
    if marker in doc:
        doc = doc.replace(marker, marker + "\n    " + banner, 1)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(doc)
    return True


def run_pipeline() -> dict:
    settings = load_settings()
    domains = load_yaml("config/domains.yaml")["domains"]
    seeds = load_yaml("config/seed_premises.yaml")["seed_premises"]
    ledger = ledger_mod.load_ledger()
    bible = bible_mod.load_bible()
    rng = random.Random()

    run_dt = datetime.now(timezone.utc)
    run_date = run_dt.date().isoformat()
    today = date.today()

    ac = settings["dates"]["anti_cluster"]
    eras = ledger_mod.recent_eras(ledger, ac["avoid_recent_days"])
    dateline = sample_future_dateline(today, settings["dates"], eras, rng)
    domain = rng.choice(domains)
    print(f">>> DATE {dateline['year']} ({dateline['years_from_now']} yrs) / {domain}")

    print(">>> IDEATE")
    motifs = bible_mod.random_slice(bible, settings["ideate"]["bible_slice_size"], rng)
    avoid = ledger_mod.recent_headlines(ledger, settings["ideate"]["recent_premise_window"])
    premises = ideate_stage.ideate(dateline, domain, motifs, seeds, avoid, settings)
    print(f"    {len(premises)} premises")

    print(">>> SELECT")
    premise = select_stage.select(premises, ledger, settings)
    print(f"    chosen: {premise[:70]}")

    print(">>> WRITE")
    dispatch = write_stage.write(premise, dateline, domain, settings)
    print(f"    headline: {dispatch['headline'][:60]}")

    print(">>> RENDER")
    meta = {
        "run_time": run_dt.isoformat(),
        "timezone": settings["timezone"],
        "tagline": settings["site"]["tagline"],
        "site_name": settings["site"]["name"],
        "base_url": settings["site"]["base_url"],
        "signup_form_url": settings.get("signup_form_url", ""),
    }
    with open(rel(settings["output_html"]), "w", encoding="utf-8") as fh:
        fh.write(render_mod.render_dispatch(dispatch, meta, stale=False))
    perma = f"d/{run_date}.html"
    os.makedirs(rel("d"), exist_ok=True)
    with open(rel(perma), "w", encoding="utf-8") as fh:
        fh.write(render_mod.render_dispatch(dispatch, meta, is_permalink=True))
    print(f"    wrote {settings['output_html']} + {perma}")

    print(">>> RECORD")
    record = {"run_date": run_date, "run_time": run_dt.isoformat(),
              "dispatch": dispatch, "meta": meta}
    write_json(f"data/dispatches/{run_date}.json", record)
    ledger_mod.save_ledger(ledger_mod.append_entry(
        ledger, run_date, dateline, domain, dispatch["headline"],
        settings["dates"]["anti_cluster"]["era_bucket_years"]))
    bible_mod.save_bible(bible_mod.merge_glossary(bible, dispatch["glossary"], run_date))
    print(f"    archived {run_date}; ledger={len(ledger)}; motifs={len(bible['motifs'])}")
    return record


def main() -> int:
    print("=" * 70)
    print("THE AFTERTIMES - daily dispatch")
    print("=" * 70)
    try:
        run_pipeline()
        print("\nOK - fresh dispatch filed.")
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level guard, never crash-publish
        print(f"\nPIPELINE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        settings = load_settings()
        if inject_stale_banner(settings["output_html"]):
            print("FALLBACK - kept previous page, flagged stale.", file=sys.stderr)
            return 0
        print("FALLBACK - no previous page; nothing to publish.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_run.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest -v`
Expected: PASS (all tests green).

- [ ] **Step 6: Commit**

```bash
git add run.py tests/test_run.py
git commit -m "feat: pipeline orchestrator with stale fallback"
```

---

## Phase 8: Offline replay

### Task 10: `replay.py` - re-render a saved dispatch without an API call

**Files:**
- Create: `replay.py`

- [ ] **Step 1: Implement `replay.py`**

```python
"""Re-render a saved dispatch to index.html WITHOUT calling Gemini.
Use to iterate on the look/CSS for free.

    python replay.py 2026-07-28    # a specific archived dispatch
    python replay.py               # the most recent archived dispatch
"""
from __future__ import annotations

import glob
import os
import sys

from common import load_settings, read_json, rel
import render as render_mod


def main() -> int:
    settings = load_settings()
    if len(sys.argv) > 1:
        run_date = sys.argv[1]
    else:
        files = sorted(glob.glob(rel("data/dispatches/*.json")))
        if not files:
            print("No archived dispatches to replay.")
            return 1
        run_date = os.path.basename(files[-1])[:-5]
    record = read_json(f"data/dispatches/{run_date}.json")
    if not record:
        print(f"No dispatch for {run_date}.")
        return 1
    html = render_mod.render_dispatch(record["dispatch"], record["meta"], stale=False)
    with open(rel(settings["output_html"]), "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Replayed {run_date} -> {settings['output_html']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add replay.py
git commit -m "feat: offline replay renderer"
```

---

## Phase 9: Archive / timeline page

### Task 11: `archive.py`

Builds `archive.html`: every dispatch, newest first by publish date, each showing its future dateline, headline (linking to the permalink), and domain. A lightweight "future timeline" bar plots each dispatch by its dateline year on a log scale of years-from-now, so the spread of futures visited is visible.

**Files:**
- Create: `archive.py`
- Test: extend `tests/test_render.py` with an archive test (kept in the same file to avoid a near-empty module)

- [ ] **Step 1: Add failing test to `tests/test_render.py`**

```python
from archive import render_archive


def test_archive_lists_dispatches_newest_first():
    records = [
        {"run_date": "2026-07-27", "dispatch": {
            "headline": "Older story", "domain": "sport",
            "dateline": {"place": "Luna", "year": 2200, "month": 1, "day": 1,
                         "years_from_now": 174}}},
        {"run_date": "2026-07-28", "dispatch": {
            "headline": "Newer story", "domain": "law",
            "dateline": {"place": "Mars", "year": 2400, "month": 2, "day": 2,
                         "years_from_now": 374}}},
    ]
    meta = {"site_name": "The Aftertimes",
            "tagline": "Dispatches from years that have not yet happened"}
    html = render_archive(records, meta)
    assert html.index("Newer story") < html.index("Older story")
    assert "d/2026-07-28.html" in html
    assert "\u2014" not in html
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_render.py::test_archive_lists_dispatches_newest_first -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement `archive.py`**

```python
"""Build archive.html - every past dispatch, newest first, plus a future-timeline
bar plotting each by its dateline. Pure functions; run separately or from run.py."""
from __future__ import annotations

import glob
import html
import math
import os

from common import hyphenate, load_settings, read_json, rel
from dates import format_dateline

_CSS = """
:root{--bg:#f4efe3;--fg:#1a1611;--muted:#6b5f4d;--accent:#7a2b2b;--rule:#cdc3ad;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:Georgia,'Times New Roman',serif;line-height:1.5;}
.wrap{max-width:46rem;margin:0 auto;padding:clamp(2rem,7vw,4rem) 1.5rem 4rem;}
.masthead{text-align:center;border-bottom:3px double var(--fg);padding-bottom:0.9rem;
  margin-bottom:1.4rem;}
.masthead .name{font-size:clamp(2rem,8vw,3rem);font-weight:700;line-height:1;}
.masthead .tag{font-family:-apple-system,system-ui,sans-serif;font-size:0.6rem;
  letter-spacing:0.3em;text-transform:uppercase;color:var(--muted);margin-top:0.6rem;}
h2{font-family:-apple-system,system-ui,sans-serif;font-size:0.72rem;
  letter-spacing:0.18em;text-transform:uppercase;color:var(--accent);margin:1.4rem 0 0.8rem;}
.timeline{position:relative;height:52px;border-top:1px solid var(--rule);
  border-bottom:1px solid var(--rule);margin:0 0 2rem;}
.tick{position:absolute;top:8px;width:2px;height:22px;background:var(--accent);opacity:0.75;}
.tlabel{position:absolute;bottom:2px;font-family:-apple-system,system-ui,sans-serif;
  font-size:0.6rem;color:var(--muted);transform:translateX(-50%);}
ul.disp{list-style:none;margin:0;padding:0;}
ul.disp li{padding:0.9rem 0;border-top:1px solid var(--rule);}
.disp .dl{font-family:-apple-system,system-ui,sans-serif;font-size:0.68rem;
  font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:var(--accent);}
.disp a{color:var(--fg);text-decoration:none;font-size:1.15rem;font-weight:700;
  border-bottom:1px solid var(--accent);}
.disp .dom{font-family:-apple-system,system-ui,sans-serif;font-size:0.72rem;
  color:var(--muted);margin-top:0.2rem;}
a.home{font-family:-apple-system,system-ui,sans-serif;color:var(--accent);
  text-decoration:none;border-bottom:1px solid var(--accent);font-size:0.85rem;}
footer{margin-top:3rem;font-family:-apple-system,system-ui,sans-serif;
  font-size:0.78rem;color:var(--muted);}
"""


def _timeline(records: list[dict]) -> str:
    yrs = [max(1, r["dispatch"]["dateline"]["years_from_now"]) for r in records]
    if not yrs:
        return ""
    lo, hi = math.log(min(yrs)), math.log(max(yrs) + 1)
    span = (hi - lo) or 1.0
    ticks = ""
    for r in records:
        y = max(1, r["dispatch"]["dateline"]["years_from_now"])
        pct = 100 * (math.log(y) - lo) / span
        ticks += f'<div class="tick" style="left:{pct:.1f}%"></div>'
    ends = (f'<div class="tlabel" style="left:2%">{min(yrs):,} yrs</div>'
            f'<div class="tlabel" style="left:98%">{max(yrs):,} yrs</div>')
    return f'<div class="timeline">{ticks}{ends}</div>'


def render_archive(records: list[dict], meta: dict) -> str:
    recs = sorted(records, key=lambda r: r["run_date"], reverse=True)
    rows = ""
    for r in recs:
        d = r["dispatch"]
        dl = html.escape(hyphenate(format_dateline(d["dateline"])))
        head = html.escape(hyphenate(d["headline"]))
        dom = html.escape(hyphenate(d.get("domain", "")))
        rows += (f'<li><div class="dl">{dl}</div>'
                 f'<a href="d/{r["run_date"]}.html">{head}</a>'
                 f'<div class="dom">{dom}</div></li>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f4efe3">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<title>Archive - {html.escape(meta['site_name'])}</title>
<style>{_CSS}</style>
</head>
<body>
  <div class="wrap">
    <header class="masthead">
      <div class="name">{html.escape(meta['site_name'])}</div>
      <div class="tag">{html.escape(hyphenate(meta['tagline']))}</div>
    </header>
    <p><a class="home" href="index.html">&larr; Today's dispatch</a></p>
    <h2>Futures visited</h2>
    {_timeline(recs)}
    <h2>All dispatches</h2>
    <ul class="disp">{rows}</ul>
    <footer>Every dispatch is fiction, written by a machine. None of it has happened. Yet.</footer>
  </div>
</body>
</html>
"""


def build() -> str:
    settings = load_settings()
    files = sorted(glob.glob(rel("data/dispatches/*.json")))
    records = [read_json(f"data/dispatches/{os.path.basename(f)}") for f in files]
    records = [r for r in records if r]
    meta = {"site_name": settings["site"]["name"], "tagline": settings["site"]["tagline"]}
    out = render_archive(records, meta)
    with open(rel("archive.html"), "w", encoding="utf-8") as fh:
        fh.write(out)
    return rel("archive.html")


if __name__ == "__main__":
    print(f"Wrote {build()}")
```

- [ ] **Step 4: Wire archive build into `run.py`** (rebuild the archive after each successful record)

Modify `run.py`: add `import archive as archive_mod` at the top with the other imports, and at the end of `run_pipeline()`, immediately before `return record`, add:

```python
    archive_mod.build()
    print("    rebuilt archive.html")
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_render.py -v`
Expected: PASS (archive test + render tests green).

- [ ] **Step 6: Commit**

```bash
git add archive.py run.py tests/test_render.py
git commit -m "feat: archive/timeline page, rebuilt each run"
```

---

## Phase 10: Assets

### Task 12: favicon + first live generation (real Gemini validation)

**Files:**
- Create: `assets/favicon.svg`

- [ ] **Step 1: Write `assets/favicon.svg`** (a simple bone-on-oxblood "A")

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="10" fill="#7a2b2b"/>
  <text x="32" y="46" font-family="Georgia, serif" font-size="42" font-weight="700"
        text-anchor="middle" fill="#f4efe3">A</text>
</svg>
```

- [ ] **Step 2: Get a Gemini API key and set it locally**

Get a free key from Google AI Studio (aistudio.google.com, "Get API key"). Then:
```bash
export GEMINI_API_KEY="your-key-here"    # Git Bash / macOS / Linux
```
(On Windows PowerShell: `$env:GEMINI_API_KEY="your-key-here"`.)

- [ ] **Step 3: Run the real pipeline once and inspect**

Run: `.venv/Scripts/python run.py`
Expected: prints each stage, writes `index.html`, `d/<today>.html`, `data/dispatches/<today>.json`, updates `data/ledger.json` and `data/bible.json`, rebuilds `archive.html`, exits 0.

Then open `index.html` in a browser and **validate against the design (per the "validate on real output before shipping" rule):**
  - Tone is straight-faced sci-fi satire, not winking or generic.
  - Body is 250-350 words.
  - Dateline, years-from-now, filed-by wire, and glossary all render.
  - No em/en dashes anywhere on the page.
  - The metadata panel expands; the fiction footer is present.

If the tone/length is off, iterate on the prompts in `write.py` / `ideate.py` and re-run `python replay.py` (free) for layout tweaks or `python run.py` (one API call) for content. Do 3-5 runs to confirm variety and that anti-clustering/novelty are behaving.

- [ ] **Step 4: Commit the assets and the first few generated artefacts**

```bash
git add assets/favicon.svg index.html archive.html d/ data/
git commit -m "feat: favicon; first validated live dispatches"
```

---

## Phase 11: Deployment

### Task 13: GitHub Actions daily workflow + Pages

**Files:**
- Create: `.github/workflows/daily.yml`

- [ ] **Step 1: Create the GitHub org + repo**

Create a GitHub organisation `the-aftertimes` and a repo named `the-aftertimes.github.io` under it (org page). Push this repo to it:
```bash
git remote add origin https://github.com/the-aftertimes/the-aftertimes.github.io.git
git branch -M main
git push -u origin main
```

- [ ] **Step 2: Add the secret**

In the repo: Settings -> Secrets and variables -> Actions -> New repository secret. Name `GEMINI_API_KEY`, value = your key.

- [ ] **Step 3: Enable Pages**

Settings -> Pages -> Source = "Deploy from a branch", branch `main`, folder `/ (root)`. (The org page serves `index.html` from the repo root.)

- [ ] **Step 4: Write `.github/workflows/daily.yml`**

```yaml
name: daily-dispatch
on:
  schedule:
    - cron: "0 20 * * *"   # 20:00 UTC daily (matches One Story)
  workflow_dispatch: {}

permissions:
  contents: write

concurrency:
  group: daily-dispatch
  cancel-in-progress: false

jobs:
  file:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install deps
        run: pip install -r requirements.txt
      - name: Generate today's dispatch
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python run.py
      - name: Commit and push
        run: |
          git config user.name "aftertimes-bot"
          git config user.email "bot@the-aftertimes.github.io"
          git add index.html archive.html d/ data/
          git commit -m "dispatch: $(date -u +%Y-%m-%d)" || echo "no changes"
          git push
```

- [ ] **Step 5: Trigger a manual run and verify**

In the repo: Actions -> daily-dispatch -> Run workflow. Confirm it goes green, commits a new dispatch, and the site updates at `https://the-aftertimes.github.io`.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/daily.yml
git commit -m "ci: daily dispatch workflow + Pages deploy"
git push
```

---

## Phase 12: Newsletter (infra ready, activation deferred)

### Task 14: Brevo email body + form wiring

The signup form is already rendered by `render.py` (Task 8) and appears whenever `signup_form_url` is set. This task adds the daily email body builder (ported from One Story) so delivery is one config + one CI step away when Charlie is ready.

**Files:**
- Create: `email_render.py`
- Test: extend `tests/test_render.py`

- [ ] **Step 1: Add failing test to `tests/test_render.py`**

```python
from email_render import build_email


def test_build_email_has_subject_and_body():
    dispatch = {
        "headline": "Floating Capital Sues the Sea",
        "body": "One paragraph.\nAnother paragraph.",
        "dateline": {"place": "Port Kobenhavn-2", "year": 2391, "month": 9, "day": 4,
                     "years_from_now": 365},
        "wire": {"name": "Nordwire", "gloss": ""}, "domain": "law", "glossary": [],
    }
    meta = {"site_name": "The Aftertimes", "base_url": "https://the-aftertimes.github.io"}
    subject, body = build_email(dispatch, meta)
    assert "Floating Capital" in subject
    assert "2391" in body or "2,391" in body
    assert "\u2014" not in body
    assert "the-aftertimes.github.io" in body
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_render.py::test_build_email_has_subject_and_body -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement `email_render.py`** (table + inline styles + bgcolor for Outlook, per the HTML-email gotchas already logged)

```python
"""Daily email body for Brevo. Light bone theme, table + inline styles so it
survives Outlook. Kept close to the One Story email but broadsheet-styled.
No em/en dashes. Delivery is a separate step, activated later."""
from __future__ import annotations

import html

from common import hyphenate
from dates import format_dateline, years_phrase


def build_email(dispatch: dict, meta: dict) -> tuple[str, str]:
    dl = dispatch["dateline"]
    subject = hyphenate(f"The Aftertimes: {dispatch['headline']}")
    headline = html.escape(hyphenate(dispatch["headline"]))
    dateline = html.escape(hyphenate(format_dateline(dl)))
    years = html.escape(years_phrase(dl["years_from_now"]))
    paras = "".join(
        f'<p style="margin:0 0 14px;font-size:16px;line-height:1.55;color:#1a1611;">'
        f'{html.escape(hyphenate(p.strip()))}</p>'
        for p in dispatch["body"].split("\n") if p.strip())
    filed = html.escape(hyphenate(dispatch["wire"]["name"]))
    url = html.escape(meta["base_url"], quote=True)
    body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light only"></head>
<body style="margin:0;padding:0;background:#e7e1d3;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#e7e1d3">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" bgcolor="#f4efe3"
  style="max-width:600px;background:#f4efe3;border:1px solid #cdc3ad;">
<tr><td style="padding:28px 32px;font-family:Georgia,serif;">
  <div style="text-align:center;border-bottom:3px double #1a1611;padding-bottom:10px;margin-bottom:20px;">
    <div style="font-size:30px;font-weight:700;color:#1a1611;">The Aftertimes</div>
    <div style="font-size:10px;letter-spacing:0.24em;text-transform:uppercase;color:#6b5f4d;margin-top:6px;font-family:Arial,sans-serif;">Dispatches from years that have not yet happened</div>
  </div>
  <div style="font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#7a2b2b;margin-bottom:10px;font-family:Arial,sans-serif;">{dateline} &middot; {years}</div>
  <h1 style="font-size:26px;line-height:1.15;color:#1a1611;margin:0 0 16px;">{headline}</h1>
  {paras}
  <p style="font-size:13px;font-style:italic;color:#6b5f4d;margin:6px 0 20px;">Filed by {filed}</p>
  <p style="margin:0 0 20px;"><a href="{url}" style="color:#7a2b2b;font-weight:700;font-family:Arial,sans-serif;font-size:14px;">Read it on the site and browse the archive &rarr;</a></p>
  <p style="font-size:12px;font-style:italic;color:#6b5f4d;border-top:1px solid #cdc3ad;padding-top:14px;margin:0;font-family:Arial,sans-serif;">Every dispatch is fiction, written by a machine each morning. None of it has happened. Yet.</p>
</td></tr></table>
</td></tr></table>
</body></html>"""
    return subject, body


if __name__ == "__main__":
    import sys
    from common import read_json
    rec = read_json(f"data/dispatches/{sys.argv[1]}.json")
    subj, html_body = build_email(rec["dispatch"], rec["meta"])
    print(subj)
    with open("email.html", "w", encoding="utf-8") as fh:
        fh.write(html_body)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_render.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite green**

Run: `.venv/Scripts/python -m pytest -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add email_render.py tests/test_render.py
git commit -m "feat: Brevo daily email body (delivery activated later)"
git push
```

**Newsletter activation (deferred, do when ready):** create a Brevo account + list, make a single-opt-in signup form, put its POST action URL into `settings.yaml` `signup_form_url`, redeploy (the form then appears on the page). For sending, add a Brevo transactional/campaign step to the workflow after `run.py` using `email_render.build_email`. Follow the logged HTML-email gotchas: real-send test to yourself first, expect the free-tier branding badge, watch Gmail rendering. This is out of scope for the initial launch.

---

## Self-review (completed against the spec)

- **Spec coverage:** register/tone -> ideate+write prompts (Task 7) & live validation (Task 12); pipeline `ideate/select/write/render` -> Tasks 7-9; weighted date + deep tail + anti-clustering -> Task 3; loose-motif bible -> Task 5, wired in Task 9; article anatomy + metadata panel -> Tasks 7-8; bone-broadsheet look -> Task 8; index + archive/timeline + permalinks -> Tasks 8-9; free Gemini -> Task 6; GitHub org/Pages/cron + stale fallback -> Tasks 9,13; committed data -> Task 9; fiction framing -> Task 8 (footer + tagline + meta); newsletter infra from start -> Tasks 8,14; seeds -> Task 2; testing/replay -> throughout + Task 10. All spec sections map to a task.
- **Placeholder scan:** no TBD/TODO; every code step has complete code; the only deferred item (newsletter *send activation*) is explicitly out of v1 scope per the spec, with concrete steps recorded.
- **Type consistency:** the `dispatch` dict shape (`headline`, `body`, `dateline{place,year,month,day,years_from_now}`, `wire{name,gloss}`, `domain`, `glossary[{term,gloss}]`, `premise`) is produced by `write.write` (Task 7) and consumed identically by `render.render_dispatch` (Task 8), `archive.render_archive` (Task 11), `email_render.build_email` (Task 14) and `replay.py` (Task 10). The `meta` dict and the `dateline` helpers (`format_dateline`, `years_phrase`) are used consistently. Ledger entry shape is written and read by the same module (Task 4).

## Notes for the executor

- Do not modify the One Story project at `C:\dev\one-story`; it is read-only reference.
- Keep every generated/rendered string free of em/en dashes; `hyphenate()` is applied at write time and again at render time as a belt-and-braces guard.
- The live-API steps (Task 12 Step 3, Task 13 Step 5) are the only ones that spend a Gemini call. Everything else runs offline and free; use `replay.py` for all layout iteration.
