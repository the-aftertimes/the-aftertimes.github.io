# Learning Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the paper improve itself day to day - automatically where a trustworthy signal exists (repetition), and driven by Charlie's verdicts where it does not (funny).

**Architecture:** A deterministic `trends.py` mines the archive for staleness and writes a capped, decaying `data/dynamic_avoid.json`, which is injected into the ideate and write prompts as data. `verdict.py` records Charlie's good/bad calls; good premises are promoted into a few-shot exemplar pool that steers generation far harder than instructions do. Weekly, `proposals.py` drafts changes to the hand-written rules for Charlie to approve - it never edits them.

**Tech Stack:** Python 3.13, pytest, PyYAML. No new dependencies (scikit-learn is already present for the novelty gate).

**Spec:** `docs/superpowers/specs/2026-08-04-learning-loop-design.md`

**Working directory:** `~/dev/the-aftertimes`. Run python as `.venv/Scripts/python.exe`. Baseline: 125 tests pass.

**House rules:** NO em/en dashes anywhere (plain hyphens). The Write/Edit tool silently converts a U+2014 escape sequence into a literal em dash, so where a dash codepoint is genuinely needed write `chr(0x2014)`. Verify byte-level after each edit:
`.venv/Scripts/python.exe -c "s=open('FILE',encoding='utf-8').read(); print(sum(s.count(chr(c)) for c in (0x2014,0x2013,0x2011,0x2012)))"` must print 0. Australian spelling in prose and comments.

---

## Why the automation is split

Rhythm and repetition are measurable in code. **Funny is not.** An unattended nightly loop that optimises only what it can measure will drift toward prose that scores well and reads bland, unobserved for days. So: repetition is automated, Charlie's taste is the quality signal, and **the hand-written prompt is never machine-edited** - only proposed against.

## File Structure

| File | Responsibility |
|---|---|
| `trends.py` (new) | Deterministic staleness detection over the archive. Pure, no API. |
| `avoid.py` (new) | Build, decay, cap and render the dynamic avoid block. |
| `verdict.py` (new) | CLI recording Charlie's good/bad calls. |
| `exemplars.py` (new) | Promote good premises into the few-shot pool, register-balanced. |
| `proposals.py` (new) | Weekly human-gated proposal document. |
| `ideate.py`, `write.py` (modify) | Accept an optional `avoid_block`. |
| `run.py` (modify) | Refresh trends, inject the block, honour the kill switch. |
| `config/settings.yaml` (modify) | `learning` block. |
| `config/exemplars.yaml` (new) | Charlie-endorsed premises. Starts empty. |
| `data/dynamic_avoid.json`, `data/verdicts.json` | Generated state, committed daily. |

---

### Task 1: learning config block and the kill switch

**Files:** Modify `config/settings.yaml`; create `tests/test_learning_config.py`

- [ ] **Step 1: Write the failing test**

```python
"""The learning loop's configuration, including its kill switch."""
import yaml

from common import rel


def _cfg():
    with open(rel("config/settings.yaml"), encoding="utf-8") as fh:
        return yaml.safe_load(fh)["learning"]


def test_learning_block_present_and_complete():
    c = _cfg()
    assert c["enabled"] is True
    assert c["window"] >= 10           # dispatches considered for staleness
    assert c["min_count"] >= 2         # occurrences before something is stale
    assert c["avoid_char_cap"] > 0
    assert c["exemplar_cap"] > 0
    assert 0 <= c["proposals_weekday"] <= 6


def test_avoid_cap_is_small_enough_not_to_bloat_the_prompt():
    # The whole risk of this feature is re-creating the verbosity we just fixed
    # by growing the prompt without limit.
    assert _cfg()["avoid_char_cap"] <= 2000
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_learning_config.py -v`
Expected: FAIL with `KeyError: 'learning'`

- [ ] **Step 3: Add the config block**

Append to `config/settings.yaml` as a new top-level block:

```yaml
# Daily self-improvement. Only REPETITION is automated: it is measurable, whereas
# "funny" is not, and a loop optimising only what it can measure drifts toward
# bland-but-compliant prose. Charlie's verdicts supply the quality signal, and the
# hand-written prompts are never machine-edited - see proposals.py.
learning:
  enabled: true           # kill switch: false restores the fixed prompts exactly
  window: 30              # dispatches considered when judging staleness
  min_count: 3            # occurrences before something counts as over-used
  avoid_char_cap: 1200    # hard cap on the injected block, guards prompt bloat
  exemplar_cap: 24        # maximum Charlie-endorsed premises in the few-shot pool
  proposals_weekday: 0    # Monday
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_learning_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add config/settings.yaml tests/test_learning_config.py
git commit -m "feat: learning-loop config block with kill switch and caps"
```

---

### Task 2: trends.py detectors

**Files:** Create `trends.py`; create `tests/test_trends.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Staleness detection over the archive."""
import trends


def _d(headline, body, place="Somewhere", domain="law"):
    return {"dispatch": {"headline": headline, "body": body, "domain": domain,
                         "dateline": {"place": place, "year": 2500,
                                      "years_from_now": 474}}}


def test_repeated_phrases_are_detected_and_singletons_are_not():
    recs = [_d("H", "The council sealed the shaft again today."),
            _d("H", "The council sealed the door quietly."),
            _d("H", "The council sealed the vault at dawn."),
            _d("H", "A goalkeeper retired to the moon.")]
    hits = trends.repeated_phrases(recs, min_count=3)
    assert any("the council sealed" in h["item"] for h in hits)
    assert not any("goalkeeper" in h["item"] for h in hits)


def test_sentence_openers_are_detected():
    recs = [_d("H", "Municipal logs reveal a fault. More text here."),
            _d("H", "Municipal logs reveal a leak. More text here."),
            _d("H", "Municipal logs reveal a gap. More text here."),
            _d("H", "Rain fell on the dome all week.")]
    hits = trends.repeated_openers(recs, min_count=3)
    assert any(h["item"].startswith("municipal logs reveal") for h in hits)


def test_place_formulas_catch_the_pattern_not_the_literal():
    recs = [_d("H", "b", place="New Wollongong"), _d("H", "b", place="New Cairo"),
            _d("H", "b", place="New Perth"), _d("H", "b", place="Tycho South Rim")]
    hits = trends.place_formulas(recs, min_count=3)
    assert any(h["item"] == "New <place>" for h in hits)


def test_repeated_names_are_detected():
    recs = [_d("H", '"Yes," said Kaelen Varma, an engineer.'),
            _d("H", '"No," said Kaelen Varma, a pilot.'),
            _d("H", '"Maybe," said Kaelen Varma, a cook.'),
            _d("H", '"Never," said Tenzin Norbu, a clerk.')]
    hits = trends.repeated_names(recs, min_count=3)
    assert any("kaelen" in h["item"].lower() for h in hits)
    assert not any("tenzin" in h["item"].lower() for h in hits)


def test_every_hit_carries_a_count_and_the_dates_involved():
    recs = [_d("H", "The council sealed the shaft.") for _ in range(3)]
    for r in recs:
        r["run_date"] = "2026-08-01"
    hits = trends.repeated_phrases(recs, min_count=3)
    assert hits and hits[0]["count"] >= 3
    assert "kind" in hits[0]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trends.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trends'`

- [ ] **Step 3: Create trends.py**

```python
"""Deterministic staleness detection over the archive.

Finds what the paper has started REPEATING - phrasing, sentence openers, names,
place-name formulas. This half is automated precisely because repetition is
measurable; humour is not, and is handled by Charlie's verdicts instead.

Pure functions over already-loaded records. No file IO, no API calls.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

#: Ordinary news phrasing that is not evidence of staleness.
_STOP_PHRASES = {
    "of the", "in the", "on the", "to the", "for the", "at the", "and the",
    "it is", "there is", "there are", "this is", "that the", "with the",
}

_WORD = re.compile(r"[A-Za-z']+")
#: A capitalised forename followed by a capitalised surname, as the writer names
#: characters. Deliberately conservative: two capitalised words in a row.
_NAME = re.compile(r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b")


def _bodies(records):
    return [(r.get("run_date", ""), r["dispatch"].get("body", "") or "")
            for r in records]


def _hit(kind, item, count, dates):
    return {"kind": kind, "item": item, "count": count,
            "dates": sorted(set(d for d in dates if d))[:6]}


def repeated_phrases(records, min_count=3, n_range=(2, 4)):
    """Word n-grams appearing in min_count or more DISPATCHES (not occurrences,
    so one dispatch repeating a phrase does not flag it)."""
    seen = defaultdict(set)
    for date, body in _bodies(records):
        words = [w.lower() for w in _WORD.findall(body)]
        grams = set()
        for n in range(n_range[0], n_range[1] + 1):
            for i in range(len(words) - n + 1):
                g = " ".join(words[i:i + n])
                if g not in _STOP_PHRASES:
                    grams.add(g)
        for g in grams:
            seen[g].add(date or id(body))
    out = [_hit("phrase", g, len(ds), ds) for g, ds in seen.items()
           if len(ds) >= min_count]
    # keep the longest phrase when one contains another, so the report is not
    # three overlapping versions of the same tic
    out.sort(key=lambda h: (-len(h["item"]), -h["count"]))
    kept = []
    for h in out:
        if not any(h["item"] in k["item"] for k in kept):
            kept.append(h)
    return sorted(kept, key=lambda h: -h["count"])


def repeated_openers(records, min_count=3, words=3):
    """The first few words of each paragraph, which is where formulaic openings
    show up ("Municipal logs reveal", "Station files show")."""
    seen = defaultdict(set)
    for date, body in _bodies(records):
        for para in body.split("\n"):
            ws = [w.lower() for w in _WORD.findall(para)][:words]
            if len(ws) == words:
                seen[" ".join(ws)].add(date or id(para))
    return sorted([_hit("opener", k, len(ds), ds) for k, ds in seen.items()
                   if len(ds) >= min_count], key=lambda h: -h["count"])


def repeated_names(records, min_count=3):
    """Character names reused across dispatches."""
    seen = defaultdict(set)
    for date, body in _bodies(records):
        for first, last in _NAME.findall(body):
            seen[f"{first} {last}"].add(date or id(body))
    return sorted([_hit("name", k, len(ds), ds) for k, ds in seen.items()
                   if len(ds) >= min_count], key=lambda h: -h["count"])


def place_formulas(records, min_count=3):
    """Dateline PATTERNS rather than literal names, so 'New Wollongong' and
    'New Cairo' count as the same tired formula."""
    pats = [(re.compile(r"^New\s+\w+"), "New <place>"),
            (re.compile(r"^Port\s+\w+"), "Port <place>"),
            (re.compile(r"\w+-on-\w+"), "<place>-on-<place>"),
            (re.compile(r"\w+\s+Ring\b"), "<place> Ring"),
            (re.compile(r"\w+\s+Deck\b"), "<place> Deck"),
            (re.compile(r"\w+\s+Station\b"), "<place> Station")]
    seen = defaultdict(set)
    for r in records:
        place = (r["dispatch"].get("dateline") or {}).get("place") or ""
        for rx, label in pats:
            if rx.search(place):
                seen[label].add(r.get("run_date", "") or place)
    return sorted([_hit("place_formula", k, len(ds), ds) for k, ds in seen.items()
                   if len(ds) >= min_count], key=lambda h: -h["count"])


def detect(records, min_count=3):
    """Every detector, strongest first."""
    hits = (repeated_phrases(records, min_count)
            + repeated_openers(records, min_count)
            + repeated_names(records, min_count)
            + place_formulas(records, min_count))
    return sorted(hits, key=lambda h: -h["count"])
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trends.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Sanity-check against the REAL archive**

Run:
```bash
.venv/Scripts/python.exe -c "import glob,json,trends; recs=[json.load(open(f,encoding='utf-8')) for f in sorted(glob.glob('data/dispatches/*.json'))]; [print(h['kind'], h['count'], repr(h['item'])) for h in trends.detect(recs, 2)[:15]]"
```
Read the output. Hits must look like genuine tics, not ordinary English. If half of them are phrases like "on the platform", raise `min_count` or extend `_STOP_PHRASES` and say so in your report. Do NOT skip this step - a detector that flags ordinary language would poison every future prompt.

- [ ] **Step 6: Commit**

```bash
git add trends.py tests/test_trends.py
git commit -m "feat: deterministic staleness detectors over the archive"
```

---

### Task 3: avoid.py - build, decay, cap, render

**Files:** Create `avoid.py`; create `tests/test_avoid.py`

- [ ] **Step 1: Write the failing tests**

```python
import avoid

CFG = {"enabled": True, "window": 30, "min_count": 3, "avoid_char_cap": 200,
       "exemplar_cap": 24, "proposals_weekday": 0}

HITS = [{"kind": "phrase", "item": "the council sealed", "count": 5,
         "dates": ["2026-08-01"]},
        {"kind": "opener", "item": "municipal logs reveal", "count": 4,
         "dates": ["2026-08-02"]},
        {"kind": "name", "item": "Kaelen Varma", "count": 3,
         "dates": ["2026-08-03"]}]


def test_render_lists_items_strongest_first():
    text = avoid.render(HITS, CFG)
    assert "the council sealed" in text
    assert text.index("the council sealed") < text.index("Kaelen Varma")


def test_render_respects_the_character_cap():
    many = [{"kind": "phrase", "item": f"stale phrase number {i}", "count": 9,
             "dates": []} for i in range(200)]
    text = avoid.render(many, CFG)
    assert len(text) <= CFG["avoid_char_cap"]


def test_render_is_empty_when_there_is_nothing_stale():
    assert avoid.render([], CFG) == ""


def test_render_is_empty_when_learning_is_disabled():
    assert avoid.render(HITS, dict(CFG, enabled=False)) == ""


def test_window_limits_which_records_are_considered():
    recs = [{"run_date": f"2026-07-{d:02d}", "dispatch": {}} for d in range(1, 20)]
    assert len(avoid.recent(recs, 5)) == 5
    assert avoid.recent(recs, 5)[-1]["run_date"] == "2026-07-19"
```

- [ ] **Step 2: Run to verify it fails**

Expected: FAIL with `ModuleNotFoundError: No module named 'avoid'`

- [ ] **Step 3: Create avoid.py**

```python
"""Turn staleness hits into the prompt's 'recently over-used' block.

Three properties matter more than the detection itself:
- DECAY: only the last `window` dispatches count, so a tic stops being nagged
  about once the paper has actually moved on.
- CAP: the rendered block is hard-limited, because the whole risk of this feature
  is quietly re-growing the prompt into the verbosity that was just fixed.
- KILL SWITCH: `learning.enabled: false` yields an empty block, which restores
  today's prompts byte for byte.
"""
from __future__ import annotations

_HEADER = ("RECENTLY OVER-USED - the paper has leaned on these lately, so find "
           "something else:")

_LABELS = {"phrase": "phrasing", "opener": "opening", "name": "name",
           "place_formula": "place-name formula"}


def recent(records, window):
    """The last `window` records by run date."""
    return sorted(records, key=lambda r: r.get("run_date", ""))[-window:]


def render(hits, cfg) -> str:
    """A compact block, strongest first, never exceeding the configured cap."""
    if not cfg.get("enabled") or not hits:
        return ""
    lines, out = [], _HEADER
    for h in sorted(hits, key=lambda x: -x["count"]):
        label = _LABELS.get(h["kind"], h["kind"])
        line = f"\n- {label}: \"{h['item']}\" (used in {h['count']} dispatches)"
        if len(out) + len(line) > cfg["avoid_char_cap"]:
            break
        out += line
        lines.append(line)
    return out if lines else ""
```

- [ ] **Step 4: Run to verify it passes**

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add avoid.py tests/test_avoid.py
git commit -m "feat: avoid block with decay, hard cap and kill switch"
```

---

### Task 4: inject into the prompts

**Files:** Modify `ideate.py`, `write.py`; create `tests/test_avoid_injection.py`

- [ ] **Step 1: Write the failing tests**

```python
import ideate
import write as write_stage

BLOCK = 'RECENTLY OVER-USED - the paper has leaned on these lately:\n- name: "Kaelen Varma"'


def test_ideate_prompt_carries_the_block_when_given_one():
    p = ideate.build_prompt(
        dateline={"year": 2500, "years_from_now": 474}, domain="food",
        bible_motifs=[], seed_premises=[], avoid_headlines=[], n=8,
        style_guidance="A wire report.", engine_guidance="etiquette",
        place_guidance="a moon", avoid_block=BLOCK)
    assert "Kaelen Varma" in p


def test_write_prompt_carries_the_block_when_given_one():
    p = write_stage.build_prompt(
        premise="p", dateline={"year": 2500, "years_from_now": 474},
        domain="food", style_guidance="A wire report.",
        place_guidance="a moon", avoid_block=BLOCK)
    assert "Kaelen Varma" in p


def test_prompts_are_byte_identical_without_a_block():
    """The kill switch must restore the previous prompts EXACTLY, so turning the
    feature off is a genuine rollback rather than a different prompt."""
    args = dict(premise="p", dateline={"year": 2500, "years_from_now": 474},
                domain="food", style_guidance="A wire report.",
                place_guidance="a moon")
    assert write_stage.build_prompt(**args) == write_stage.build_prompt(
        **args, avoid_block="")
```

- [ ] **Step 2: Run to verify it fails**

Expected: FAIL with `TypeError: build_prompt() got an unexpected keyword argument 'avoid_block'`

- [ ] **Step 3: Add the parameter to both prompts**

In `ideate.build_prompt`, add `avoid_block: str = ""` as the last parameter, and immediately before the `Return JSON only:` line insert:

```python
    avoid_extra = f"\n{avoid_block}\n" if avoid_block else ""
```

then interpolate `{avoid_extra}` just above `Return JSON only:`. Thread the argument through `ideate.ideate` the same way `place_guidance` already is.

In `write.build_prompt`, add `avoid_block: str = ""` as the last parameter, build the same `avoid_extra`, and interpolate it immediately before the `Return JSON only:` line. Thread it through `write.write`.

IMPORTANT: when `avoid_block` is empty the prompt string must be byte-identical to before - the test above enforces this, so use the empty-string guard rather than always inserting a newline.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_avoid_injection.py tests/test_registers.py -v`
Expected: PASS, and the existing register/prompt guards still green

- [ ] **Step 5: Commit**

```bash
git add ideate.py write.py tests/test_avoid_injection.py
git commit -m "feat: inject the dynamic avoid block into both prompts"
```

---

### Task 5: verdict.py

**Files:** Create `verdict.py`; create `tests/test_verdict.py`

- [ ] **Step 1: Write the failing tests**

```python
import json

import verdict


def test_record_and_read_back(tmp_path, monkeypatch):
    store = tmp_path / "verdicts.json"
    monkeypatch.setattr(verdict, "_PATH", str(store))
    verdict.record("2026-08-04", "good", "kicker lands")
    verdict.record("2026-08-05", "bad", "no target")
    data = json.loads(store.read_text(encoding="utf-8"))
    assert data["2026-08-04"]["verdict"] == "good"
    assert data["2026-08-05"]["note"] == "no target"


def test_recording_the_same_date_twice_overwrites(tmp_path, monkeypatch):
    store = tmp_path / "verdicts.json"
    monkeypatch.setattr(verdict, "_PATH", str(store))
    verdict.record("2026-08-04", "bad", "first call")
    verdict.record("2026-08-04", "good", "changed my mind")
    data = json.loads(store.read_text(encoding="utf-8"))
    assert data["2026-08-04"]["verdict"] == "good"
    assert len(data) == 1


def test_an_unknown_verdict_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(verdict, "_PATH", str(tmp_path / "v.json"))
    try:
        verdict.record("2026-08-04", "brilliant", "")
    except ValueError:
        return
    raise AssertionError("expected ValueError for an unknown verdict")
```

- [ ] **Step 2: Run to verify it fails**

Expected: FAIL with `ModuleNotFoundError: No module named 'verdict'`

- [ ] **Step 3: Create verdict.py**

```python
"""Record Charlie's good/bad call on a dispatch. This is the quality signal the
loop cannot compute for itself.

    python verdict.py 2026-08-06 good "the kicker lands"
    python verdict.py 2026-08-06 bad  "no satirical target"
    python verdict.py                      # list dispatches awaiting a verdict
"""
from __future__ import annotations

import glob
import json
import os
import sys

from common import read_json, rel, write_json

_PATH = "data/verdicts.json"
_ALLOWED = ("good", "bad")


def load() -> dict:
    return read_json(_PATH, default={}) or {}


def record(run_date: str, call: str, note: str = "") -> dict:
    if call not in _ALLOWED:
        raise ValueError(f"verdict must be one of {_ALLOWED}, got {call!r}")
    data = load()
    data[run_date] = {"verdict": call, "note": note.strip()}
    write_json(_PATH, data)
    return data


def pending() -> list[str]:
    """Dispatch dates with no verdict yet, newest first."""
    judged = set(load())
    dates = [os.path.basename(f)[:-5]
             for f in sorted(glob.glob(rel("data/dispatches/*.json")))]
    return [d for d in reversed(dates) if d not in judged]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        todo = pending()
        print("Awaiting a verdict:" if todo else "Every dispatch has a verdict.")
        for d in todo[:20]:
            print(f"  {d}")
        return 0
    run_date, call = argv[0], argv[1]
    note = " ".join(argv[2:])
    try:
        record(run_date, call, note)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Recorded {run_date}: {call} {note}".strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Note `_PATH` is a module-level string so tests can point it at a temp file.
`read_json`/`write_json` from `common` resolve paths relative to the repo, so a
monkeypatched absolute path works because `common.write_json` calls
`os.path.join(ROOT, path)` - an absolute second argument wins. Verify this
behaviour holds when you run the tests; if it does not, change `_PATH` handling to
call the raw `open()` directly and say so in your report.

- [ ] **Step 4: Run to verify it passes**

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add verdict.py tests/test_verdict.py
git commit -m "feat: verdict CLI recording Charlie's good/bad calls"
```

---

### Task 6: exemplar promotion, register-balanced

**Files:** Create `exemplars.py`, `config/exemplars.yaml`; create `tests/test_exemplars.py`

- [ ] **Step 1: Write the failing tests**

```python
import exemplars

LEGALISH = "A tribunal issues a writ over unpaid taxes and a lien on a debt."
CLEAN = "A colony holds a state funeral for its last surviving houseplant."


def test_promote_adds_a_good_premise():
    pool = exemplars.promote([], CLEAN, cap=5)
    assert CLEAN in pool


def test_promotion_is_idempotent():
    pool = exemplars.promote([CLEAN], CLEAN, cap=5)
    assert pool.count(CLEAN) == 1


def test_cap_evicts_the_oldest():
    pool = [f"premise {i}" for i in range(5)]
    out = exemplars.promote(pool, CLEAN, cap=5)
    assert len(out) == 5
    assert CLEAN in out
    assert "premise 0" not in out


def test_register_guard_refuses_to_unbalance_the_pool():
    """Few-shot examples dominate output, so letting the pool fill with legal or
    financial premises would re-create the 'why is it always unpaid debts'
    collapse."""
    pool = [LEGALISH, LEGALISH.replace("tribunal", "court")]
    out = exemplars.promote(pool, LEGALISH.replace("writ", "summons"), cap=10)
    assert len(out) == 2      # refused
    assert exemplars.legal_share(out) <= 1.0


def test_a_clean_premise_is_still_accepted_into_a_legal_heavy_pool():
    pool = [LEGALISH, LEGALISH.replace("tribunal", "court")]
    out = exemplars.promote(pool, CLEAN, cap=10)
    assert CLEAN in out
```

- [ ] **Step 2: Run to verify it fails**

Expected: FAIL with `ModuleNotFoundError: No module named 'exemplars'`

- [ ] **Step 3: Create `config/exemplars.yaml`**

```yaml
# Premises Charlie marked "good", promoted here automatically by exemplars.py.
# These are FEW-SHOT examples, which steer the model far harder than instructions
# do - so the register balance is guarded (see exemplars.legal_share). Starts
# empty and grows one verdict at a time.
exemplars: []
```

- [ ] **Step 4: Create exemplars.py**

```python
"""Promote Charlie-endorsed premises into the few-shot pool.

This is the mechanism by which the paper actually gets funnier: few-shot examples
dominate model output far more than instructions do, so a growing pool of premises
Charlie personally liked steers every future generation.

For exactly that reason the pool's REGISTER is guarded. Letting it fill with legal
and financial premises would re-create the collapse where every dispatch became a
story about debt, tax and injunctions.
"""
from __future__ import annotations

import re

_LEGAL = re.compile(
    r"\b(sue[sd]?|suing|lawsuit|court|magistrate|tribunal|injunction|lien|liens"
    r"|repossess\w*|bailiff\w*|writ|statute|ordinance|tax|taxes|levy|levies"
    r"|debt|debts|money|budget|paperwork|accountant)\b", re.I)

#: Maximum share of the pool that may be legal or financial in register.
_MAX_LEGAL_SHARE = 0.25


def is_legal(premise: str) -> bool:
    return bool(_LEGAL.search(premise or ""))


def legal_share(pool: list[str]) -> float:
    return (sum(1 for p in pool if is_legal(p)) / len(pool)) if pool else 0.0


def promote(pool: list[str], premise: str, cap: int) -> list[str]:
    """Add `premise` unless it would unbalance the register. Returns the new pool;
    the caller decides whether anything changed."""
    premise = (premise or "").strip()
    if not premise or premise in pool:
        return list(pool)
    if is_legal(premise):
        would_be = list(pool) + [premise]
        if legal_share(would_be) > _MAX_LEGAL_SHARE:
            return list(pool)          # refused, deliberately silent to callers
    out = list(pool) + [premise]
    return out[-cap:] if len(out) > cap else out
```

- [ ] **Step 5: Run to verify it passes**

Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add exemplars.py config/exemplars.yaml tests/test_exemplars.py
git commit -m "feat: register-guarded exemplar promotion from Charlie's verdicts"
```

---

### Task 7: wire the loop into run.py

**Files:** Modify `run.py`; create `tests/test_learning_wiring.py`

- [ ] **Step 1: Write the failing tests**

```python
import run as run_mod

CFG_ON = {"enabled": True, "window": 30, "min_count": 3, "avoid_char_cap": 1200,
          "exemplar_cap": 24, "proposals_weekday": 0}


def _recs(n, phrase):
    return [{"run_date": f"2026-08-{i + 1:02d}",
             "dispatch": {"headline": "H", "body": f"{phrase} number {i}.",
                          "domain": "law",
                          "dateline": {"place": "P", "year": 2500,
                                       "years_from_now": 474}}}
            for i in range(n)]


def test_build_avoid_block_finds_a_repeated_phrase():
    block = run_mod.build_avoid_block(_recs(5, "the council sealed the shaft"),
                                      CFG_ON)
    assert "council sealed" in block


def test_build_avoid_block_is_empty_when_disabled():
    recs = _recs(5, "the council sealed the shaft")
    assert run_mod.build_avoid_block(recs, dict(CFG_ON, enabled=False)) == ""


def test_build_avoid_block_never_raises_on_bad_input():
    """A trend-spotting fault must never take the daily publish down with it."""
    assert run_mod.build_avoid_block([{"broken": True}], CFG_ON) == ""
```

- [ ] **Step 2: Run to verify it fails**

Expected: FAIL with `AttributeError: module 'run' has no attribute 'build_avoid_block'`

- [ ] **Step 3: Add the helper to run.py**

Add imports `import avoid`, `import trends`, and `import exemplars` beside the
existing ones, then add above `run_pipeline()`:

```python
def build_avoid_block(records: list[dict], lcfg: dict) -> str:
    """The 'recently over-used' block, or an empty string. Never raises: a
    staleness-detection fault must not be able to stop the paper publishing."""
    if not lcfg.get("enabled"):
        return ""
    try:
        window = avoid.recent(records, lcfg["window"])
        return avoid.render(trends.detect(window, lcfg["min_count"]), lcfg)
    except Exception as exc:  # noqa: BLE001 - decorative, never fatal
        print(f"    WARN trend spotting failed ({exc}); no avoid block",
              file=sys.stderr)
        return ""
```

- [ ] **Step 4: Run to verify it passes**

Expected: PASS (3 tests)

- [ ] **Step 5: Wire it into run_pipeline**

In `run_pipeline()`, after the ledger and bible are loaded and before `>>> IDEATE`,
add:

```python
    lcfg = settings.get("learning", {"enabled": False})
    past = [read_json(f"data/dispatches/{os.path.basename(f)}")
            for f in sorted(glob.glob(rel("data/dispatches/*.json")))]
    avoid_block = build_avoid_block([p for p in past if p], lcfg)
    if avoid_block:
        print(f"    avoid block: {len(avoid_block)} chars")
```

Add `import glob` to the imports if it is not already there. Pass
`avoid_block=avoid_block` to both `ideate_stage.ideate(...)` and each
`write_stage.write(...)` call.

Also load the exemplar pool and append it to the seed premises passed to ideate:

```python
    pool = load_yaml("config/exemplars.yaml").get("exemplars") or []
    seeds_plus = seeds + [p for p in pool if p not in seeds]
```

and pass `seeds_plus` to `ideate_stage.ideate` in place of `seeds`.

- [ ] **Step 6: Run the FULL suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass, no regressions.

- [ ] **Step 7: Commit**

```bash
git add run.py tests/test_learning_wiring.py
git commit -m "feat: wire trend spotting and exemplars into the daily run"
```

---

### Task 8: promote verdicts, and the weekly proposal document

**Files:** Create `proposals.py`; modify `verdict.py`; create `tests/test_proposals.py`

- [ ] **Step 1: Write the failing tests**

```python
import proposals


def _rec(date, premise, headline="H"):
    return {"run_date": date,
            "dispatch": {"headline": headline, "premise": premise,
                         "body": "b", "domain": "law",
                         "dateline": {"place": "P", "year": 2500,
                                      "years_from_now": 474}}}


def test_document_lists_stale_items_and_the_verdict_tally():
    recs = [_rec(f"2026-08-{i + 1:02d}", "a premise") for i in range(4)]
    verdicts = {"2026-08-01": {"verdict": "good", "note": "kicker"},
                "2026-08-02": {"verdict": "bad", "note": "no target"}}
    doc = proposals.build(recs, verdicts,
                          [{"kind": "phrase", "item": "the council sealed",
                            "count": 4, "dates": []}])
    assert "the council sealed" in doc
    assert "good: 1" in doc and "bad: 1" in doc
    assert "no target" in doc          # the notes are the evidence


def test_document_states_plainly_that_nothing_is_auto_applied():
    doc = proposals.build([], {}, [])
    assert "never applied automatically" in doc.lower()


def test_no_em_or_en_dashes():
    doc = proposals.build([], {}, [])
    assert chr(0x2014) not in doc and chr(0x2013) not in doc
```

- [ ] **Step 2: Run to verify it fails**

Expected: FAIL with `ModuleNotFoundError: No module named 'proposals'`

- [ ] **Step 3: Create proposals.py**

```python
"""The weekly, human-gated half of the learning loop.

Writes a document proposing changes to the HAND-WRITTEN prompts, with the evidence
behind each. It is never applied automatically: an unattended process editing the
core house voice is the highest-blast-radius change available, and one bad edit
would degrade every dispatch after it, silently.
"""
from __future__ import annotations

from collections import Counter


def build(records: list[dict], verdicts: dict, hits: list[dict]) -> str:
    tally = Counter(v.get("verdict") for v in verdicts.values())
    lines = [
        "# Prompt proposals",
        "",
        "Generated from the archive and Charlie's verdicts. These are SUGGESTIONS.",
        "Nothing here is never applied automatically; the hand-written prompts",
        "change only when Charlie says so.",
        "",
        f"## Verdicts so far: good: {tally.get('good', 0)}, "
        f"bad: {tally.get('bad', 0)}",
        "",
    ]
    bad_notes = [v.get("note", "") for v in verdicts.values()
                 if v.get("verdict") == "bad" and v.get("note")]
    if bad_notes:
        lines += ["### What Charlie disliked, in his words", ""]
        lines += [f"- {n}" for n in bad_notes] + [""]
    if hits:
        lines += ["### Over-used lately", ""]
        lines += [f"- {h['kind']}: \"{h['item']}\" in {h['count']} dispatches"
                  for h in hits[:20]] + [""]
    lines += [
        "### Suggested next step",
        "",
        "Read the items above. If a pattern here reflects a rule that should",
        "change, edit the prompt yourself or ask for the change - the loop will",
        "not touch it.",
        "",
    ]
    return "\n".join(lines)
```

Note the deliberate wording "Nothing here is never applied automatically" is
GRAMMATICALLY WRONG. Fix it to "Nothing here is applied automatically" and make
the test assert `"applied automatically" in doc.lower()` instead. Flag in your
report that you corrected it.

- [ ] **Step 4: Add promotion to verdict.py**

Extend `verdict.record` so a "good" verdict also promotes that dispatch's premise
into `config/exemplars.yaml`:

```python
def _promote_if_good(run_date: str, call: str) -> str:
    """A good verdict promotes the dispatch's premise into the few-shot pool.
    Returns a short status line for the CLI."""
    if call != "good":
        return ""
    rec = read_json(f"data/dispatches/{run_date}.json")
    premise = ((rec or {}).get("dispatch") or {}).get("premise", "").strip()
    if not premise:
        return "no premise recorded, nothing promoted"
    import yaml
    import exemplars
    from common import load_settings
    cap = load_settings().get("learning", {}).get("exemplar_cap", 24)
    path = rel("config/exemplars.yaml")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    pool = doc.get("exemplars") or []
    out = exemplars.promote(pool, premise, cap)
    if out == pool:
        return "not promoted (already present, or it would unbalance the register)"
    doc["exemplars"] = out
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, allow_unicode=True, sort_keys=False)
    return f"promoted to the exemplar pool ({len(out)} total)"
```

Call it from `main` after `record(...)` and print whatever it returns.

- [ ] **Step 5: Run the FULL suite**

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add proposals.py verdict.py tests/test_proposals.py config/exemplars.yaml
git commit -m "feat: verdict promotion into the exemplar pool, weekly proposal doc"
```

---

### Task 9: end-to-end verification on real data

Green tests are not evidence for a generation pipeline.

- [ ] **Step 1: Trend spotting on the real archive**

```bash
.venv/Scripts/python.exe -c "import glob,json,run,avoid,trends; from common import load_settings; recs=[json.load(open(f,encoding='utf-8')) for f in sorted(glob.glob('data/dispatches/*.json'))]; print(run.build_avoid_block(recs, load_settings()['learning']))"
```
READ the block. Every line must be a genuine tic. If ordinary English appears,
raise `min_count` or extend `_STOP_PHRASES` and re-run.

- [ ] **Step 2: The kill switch really is a rollback**

```bash
.venv/Scripts/python.exe -c "
import write
a=write.build_prompt('p',{'year':2500,'years_from_now':474},'food','S','P')
b=write.build_prompt('p',{'year':2500,'years_from_now':474},'food','S','P',avoid_block='')
print('identical with no block:', a==b)"
```
Expected: `True`

- [ ] **Step 3: A verdict promotes a premise**

```bash
.venv/Scripts/python.exe verdict.py
.venv/Scripts/python.exe verdict.py <a real dispatch date> good "test promotion"
cat config/exemplars.yaml
```
Confirm the premise appears. Then revert the test verdict and the pool entry
before committing, unless the verdict is one Charlie actually holds.

- [ ] **Step 4: Report to Charlie** with the real avoid block, so he can judge
whether the detectors are finding genuine tics before this steers live generation.

---

## Self-Review

**Spec coverage:** trend spotter - Task 2; dynamic avoid file with decay/cap -
Task 3; injection - Task 4; verdicts - Task 5; exemplar promotion with the
register guard - Tasks 6 and 8; weekly proposals - Task 8; config and kill switch
- Task 1; wiring plus never-fatal guarantee - Task 7; verification - Task 9.

**Deliberately deferred:** register-concentration and kicker-shape detectors, and
the Outlook nudge for the weekly proposal. The four detectors built here cover the
tics actually observed; the rest can follow once there is evidence they are
needed.

**Type consistency:** every detector returns `{kind, item, count, dates}`;
`avoid.render` consumes exactly that; `run.build_avoid_block` returns a plain
string that both prompts accept as `avoid_block`. `exemplars.promote(pool,
premise, cap)` returns a new list and is the only writer of the pool.
