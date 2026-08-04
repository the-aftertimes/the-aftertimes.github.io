# Multi-draft Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate three dispatch drafts from three different premises, score them deterministically, have the model pick the funniest, then critique-and-rewrite the winner - publishing the rewrite only if it measures no worse.

**Architecture:** A new pure-Python `critic.py` does everything measurable (rhythm, banned phrases, registers, props, residue) so the two new model calls (`judge.py`, `revise.py`) are spent only on judgement. `run.py` orchestrates with a defined fallback at every step so the daily publish can never break.

**Tech Stack:** Python 3.13, pytest, PyYAML, Gemini REST via the existing `gemini.py`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-04-multi-draft-pipeline-design.md`

**Working directory:** `~/dev/the-aftertimes`. Run python as `.venv/Scripts/python.exe`.

---

## File Structure

| File | Responsibility |
|---|---|
| `critic.py` (new) | Deterministic scoring. Pure functions, no API, no IO. |
| `judge.py` (new) | One model call: pick the funniest of N drafts. |
| `revise.py` (new) | One model call: critique + rewrite a draft. |
| `selection.py` (modify) | Add `select_many()` beside the existing `select()`. |
| `write.py` (modify) | Extract `normalise()` so `revise.py` reuses the same cleanup. |
| `run.py` (modify) | Orchestrate drafts, scoring, judge, revise, record. |
| `config/settings.yaml` (modify) | New `quality` block holding every threshold. |
| `tests/conftest.py` (modify) | Add a `quality_cfg` fixture. |
| `tests/test_critic.py` (new) | One test per rule. |
| `tests/test_judge.py` (new) | Parsing and fallback. |
| `tests/test_revise.py` (new) | Accept-when-better, discard-when-worse. |
| `tests/test_pipeline.py` (new) | Orchestration paths with mocked calls. |
| `tests/test_stages.py` (modify) | `select_many` tests. |

---

### Task 1: Quality config block

**Files:**
- Modify: `config/settings.yaml`
- Modify: `tests/conftest.py`
- Test: `tests/test_critic.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_critic.py`:

```python
"""Deterministic dispatch scoring."""
import yaml

from common import rel


def test_quality_config_present_and_complete():
    with open(rel("config/settings.yaml"), encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)["quality"]
    assert cfg["n_drafts"] == 3
    assert cfg["judge"] is True
    assert cfg["revise"] is True
    assert set(cfg["hard_reject"]) == {
        "machine_phrases", "legal_register", "dash_residue", "us_spelling"}
    assert cfg["weights"]["major"] > cfg["weights"]["minor"] > 0
    r = cfg["rhythm"]
    assert r["mean_min"] == 14 and r["mean_max"] == 20
    assert r["longest_max"] == 35 and r["min_short"] == 2
    ln = cfg["length"]
    assert ln["hard_min"] < ln["min"] < ln["max"] < ln["hard_max"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_critic.py -v`
Expected: FAIL with `KeyError: 'quality'`

- [ ] **Step 3: Add the config block**

Append to `config/settings.yaml` (top level, after the `image:` block):

```yaml
# Multi-draft quality pipeline. Every threshold the critic uses lives here so
# tuning never means editing code. `judge` and `revise` are independently
# switchable so either half can be turned off if it proves unhelpful.
quality:
  n_drafts: 3
  judge: true
  revise: true
  hard_reject: [machine_phrases, legal_register, dash_residue, us_spelling]
  weights:
    major: 0.25
    minor: 0.08
  rhythm:
    mean_min: 14
    mean_max: 20
    mean_hard_min: 12
    mean_hard_max: 24
    longest_max: 35
    min_short: 2
  length:
    min: 200
    max: 280
    hard_min: 160
    hard_max: 340
```

- [ ] **Step 4: Add the test fixture**

Append to `tests/conftest.py`:

```python
@pytest.fixture
def quality_cfg():
    return {
        "n_drafts": 3, "judge": True, "revise": True,
        "hard_reject": ["machine_phrases", "legal_register",
                        "dash_residue", "us_spelling"],
        "weights": {"major": 0.25, "minor": 0.08},
        "rhythm": {"mean_min": 14, "mean_max": 20, "mean_hard_min": 12,
                   "mean_hard_max": 24, "longest_max": 35, "min_short": 2},
        "length": {"min": 200, "max": 280, "hard_min": 160, "hard_max": 340},
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_critic.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add config/settings.yaml tests/conftest.py tests/test_critic.py
git commit -m "feat: quality config block for the multi-draft pipeline"
```

---

### Task 2: critic.py - rhythm and length rules

**Files:**
- Create: `critic.py`
- Test: `tests/test_critic.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_critic.py`:

```python
import critic


def _body(sentences):
    return " ".join(sentences)


def test_rhythm_flags_long_uniform_prose(quality_cfg):
    # every sentence 25 words, no short ones
    long_s = " ".join(["word"] * 24) + " end."
    v = critic.check_rhythm(critic.metrics_for(_body([long_s] * 4)), quality_cfg)
    rules = {x["rule"] for x in v}
    assert "rhythm_mean" in rules
    assert "rhythm_short" in rules


def test_rhythm_flags_an_overlong_sentence(quality_cfg):
    body = ("Short one here now. " + " ".join(["word"] * 40) + ". "
            "Also short here now.")
    v = critic.check_rhythm(critic.metrics_for(body), quality_cfg)
    assert any(x["rule"] == "rhythm_longest" and x["severity"] == "major"
               for x in v)


def test_rhythm_clean_on_good_prose(quality_cfg):
    body = ("The council sealed the shaft on Tuesday. "
            "Nobody filed a query about the missing crew that week. "
            "She walked out. "
            "Three days of mourning had already been scheduled for the fern. "
            "It stayed sealed.")
    assert critic.check_rhythm(critic.metrics_for(body), quality_cfg) == []


def test_length_minor_and_major(quality_cfg):
    short = " ".join(["word"] * 180) + "."
    v = critic.check_length(critic.metrics_for(short), quality_cfg)
    assert any(x["rule"] == "length" and x["severity"] == "minor" for x in v)
    tiny = " ".join(["word"] * 100) + "."
    v = critic.check_length(critic.metrics_for(tiny), quality_cfg)
    assert any(x["rule"] == "length" and x["severity"] == "major" for x in v)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_critic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'critic'`

- [ ] **Step 3: Create critic.py with rhythm and length**

Create `critic.py`:

```python
"""Deterministic dispatch scoring - the measurable half of quality control.

Everything checkable in code lives here so the two model calls in the pipeline
(judge, revise) are spent only on the genuinely subjective question of whether a
dispatch is funny. Pure functions: no API calls, no file IO, no globals.

Severity is either "major" or "minor"; the weights and thresholds all come from
the `quality` block in config/settings.yaml so tuning never means editing code.
"""
from __future__ import annotations

from write import prose_report


def metrics_for(body: str) -> dict:
    """Prose measurements for a body. Thin alias so callers do not reach into
    write.py, and so tests read clearly."""
    return prose_report(body)


def _v(rule: str, detail: str, severity: str) -> dict:
    return {"rule": rule, "detail": detail, "severity": severity}


def check_rhythm(metrics: dict, cfg: dict) -> list[dict]:
    r = cfg["rhythm"]
    out = []
    mean = metrics["mean_sentence"]
    if not (r["mean_min"] <= mean <= r["mean_max"]):
        hard = mean < r["mean_hard_min"] or mean > r["mean_hard_max"]
        out.append(_v("rhythm_mean",
                      f"mean sentence is {mean} words, wanted "
                      f"{r['mean_min']}-{r['mean_max']}",
                      "major" if hard else "minor"))
    if metrics["longest"] > r["longest_max"]:
        out.append(_v("rhythm_longest",
                      f"longest sentence is {metrics['longest']} words, "
                      f"maximum {r['longest_max']}", "major"))
    if metrics["short_sentences"] < r["min_short"]:
        out.append(_v("rhythm_short",
                      f"only {metrics['short_sentences']} sentences of six words "
                      f"or fewer, wanted at least {r['min_short']}", "minor"))
    return out


def check_length(metrics: dict, cfg: dict) -> list[dict]:
    ln = cfg["length"]
    words = metrics["words"]
    if ln["min"] <= words <= ln["max"]:
        return []
    hard = words < ln["hard_min"] or words > ln["hard_max"]
    return [_v("length",
               f"{words} words, wanted {ln['min']}-{ln['max']}",
               "major" if hard else "minor")]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_critic.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add critic.py tests/test_critic.py
git commit -m "feat: critic rhythm and length rules"
```

---

### Task 3: critic.py - phrases, register, props

**Files:**
- Modify: `critic.py`
- Test: `tests/test_critic.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_critic.py`:

```python
def test_machine_phrases_are_major():
    v = critic.check_phrases("The proceedings took an unexpected turn today.")
    assert v and v[0]["rule"] == "machine_phrases"
    assert v[0]["severity"] == "major"
    assert "took an unexpected turn" in v[0]["detail"]


def test_legal_register_flagged_but_not_for_the_bureaucratic_engine():
    body = "The tribunal issued a writ and the bailiff served an injunction."
    assert critic.check_register(body, "logistics")
    assert critic.check_register(body, "bureaucratic") == []


def test_present_day_props_escalate_with_distance():
    body = "She lit a candle beside the bronze plaque and drank her coffee."
    near = critic.check_props(body, 120)
    far = critic.check_props(body, 3000)
    assert near and near[0]["severity"] == "minor"
    assert far and far[0]["severity"] == "major"


def test_props_clean_text_passes():
    assert critic.check_props("The sculptor whipped the cloud perimeter.", 3000) == []


def test_stated_joke_is_only_a_minor_nudge():
    body = ("They realised the settlement was too distraught over a fern to "
            "notice the missing crew. More text follows here to pad it out.")
    v = critic.check_stated_joke(body)
    assert v and v[0]["rule"] == "stated_joke"
    assert v[0]["severity"] == "minor"


def test_stated_joke_ignores_later_paragraphs():
    body = ("The shaft was sealed on Tuesday. Nobody filed a query. "
            "Weeks later the inspector realised the logs were missing.")
    assert critic.check_stated_joke(body) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_critic.py -v`
Expected: FAIL with `AttributeError: module 'critic' has no attribute 'check_phrases'`

- [ ] **Step 3: Add the checks**

Append to `critic.py`:

```python
import re

from write import _MACHINE_PHRASES

#: The legal/financial register the paper over-used (see config/engines.yaml).
#: Suppressed when the day's comic engine IS the bureaucratic one.
_LEGAL = re.compile(
    r"\b(sue[sd]?|suing|lawsuit|court|magistrate|tribunal|injunction|lien|liens"
    r"|repossess\w*|bailiff\w*|writ|statute|ordinance|permit|permits|licence"
    r"|tax|taxes|levy|levies|debt|debts|fine|fined|fines|insurance"
    r"|liability|liabilities)\b", re.I)

#: Present-day objects that should not furnish a far-future dispatch unless
#: their survival is the story. A dispatch set in 37562 mourned a Boston fern by
#: candlelight under a bronze plaque; another rolled a coffee press through
#: cobbled alleys.
_PROPS = re.compile(
    r"\b(candle\w*|bronze plaque\w*|handwritten|clipboard\w*|vellum|locker\w*"
    r"|apothecar\w*|cobblestone\w*|lard|typewriter\w*|fax|dollar\w*|euro\w*"
    r"|coffee|espresso|Boston fern\w*)\b", re.I)

#: The narrator or a character explaining the comic mechanism out loud. This is
#: a semantic fault that regex cannot detect reliably, so it is deliberately
#: only ever a minor nudge - a false positive must never bin a draft.
_STATED_JOKE = re.compile(
    r"(\brealis\w+\b|\brealiz\w+\b|too\s+\w+\s+to\s+notice|\blittle did\b)", re.I)

_STATED_JOKE_SENTENCES = 2


def check_phrases(body: str) -> list[dict]:
    hits = [p for p in _MACHINE_PHRASES if p in body.lower()]
    if not hits:
        return []
    return [_v("machine_phrases", "stock machine phrasing: " + ", ".join(hits),
               "major")]


def check_register(body: str, engine: str) -> list[dict]:
    if (engine or "") == "bureaucratic":
        return []
    hits = sorted({m.group(0).lower() for m in _LEGAL.finditer(body)})
    if not hits:
        return []
    return [_v("legal_register",
               "legal/financial crutch: " + ", ".join(hits), "major")]


def check_props(text: str, years_from_now: int) -> list[dict]:
    hits = sorted({m.group(0).lower() for m in _PROPS.finditer(text)})
    if not hits:
        return []
    severity = "major" if int(years_from_now) >= 400 else "minor"
    return [_v("present_day_props",
               "present-day props: " + ", ".join(hits), severity)]


def check_stated_joke(body: str) -> list[dict]:
    flat = re.sub(r"\s+", " ", body).strip()
    opening = " ".join(
        re.split(r"(?<=[.!?])[\"”’']*\s+", flat)[:_STATED_JOKE_SENTENCES])
    m = _STATED_JOKE.search(opening)
    if not m:
        return []
    return [_v("stated_joke",
               f"the opening states the conceit ({m.group(0)!r}) instead of "
               "reporting facts", "minor")]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_critic.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add critic.py tests/test_critic.py
git commit -m "feat: critic phrase, register and present-day-prop rules"
```

---

### Task 4: critic.py - residue checks and the score function

**Files:**
- Modify: `critic.py`
- Test: `tests/test_critic.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_critic.py`:

```python
def test_residue_checks_detect_fixer_gaps():
    v = critic.check_residue("a" + chr(0x2014) + "b")
    assert any(x["rule"] == "dash_residue" and x["severity"] == "major"
               for x in v)
    v = critic.check_residue("the neighbor complained")
    assert any(x["rule"] == "us_spelling" and x["severity"] == "major"
               for x in v)


def test_residue_clean_text_passes():
    assert critic.check_residue("the neighbour complained - loudly") == []


def _clean_dispatch():
    body = ("The council sealed the shaft on Tuesday. "
            "Nobody filed a query about the missing crew that week. "
            "She walked out. "
            "Three days of mourning had already been scheduled. "
            "It stayed sealed. "
            + " ".join(["settlement records show more detail here"] * 30) + ".")
    return {"headline": "Shaft Sealed Quietly", "body": body}


def test_clean_dispatch_scores_well_and_is_not_rejected(quality_cfg):
    r = critic.score(_clean_dispatch(),
                     {"years_from_now": 300, "engine": "logistics"}, quality_cfg)
    assert r["rejected"] is False
    assert r["score"] > 0.8
    assert r["metrics"]["words"] > 0


def test_hard_reject_rules_set_the_rejected_flag(quality_cfg):
    d = _clean_dispatch()
    d["body"] += " The tribunal served an injunction on the bailiff."
    r = critic.score(d, {"years_from_now": 300, "engine": "logistics"},
                     quality_cfg)
    assert r["rejected"] is True
    assert any(x["rule"] == "legal_register" for x in r["violations"])


def test_engine_bureaucratic_prevents_that_rejection(quality_cfg):
    d = _clean_dispatch()
    d["body"] += " The tribunal served an injunction on the bailiff."
    r = critic.score(d, {"years_from_now": 300, "engine": "bureaucratic"},
                     quality_cfg)
    assert r["rejected"] is False


def test_score_floors_at_zero(quality_cfg):
    d = {"headline": "Neighbor" + chr(0x2014) + "Dispute",
         "body": "The proceedings took an unexpected turn. "
                 "They realised it was too odd to notice. "
                 + " ".join(["word"] * 60) + ". A tribunal issued a writ."}
    r = critic.score(d, {"years_from_now": 3000, "engine": "logistics"},
                     quality_cfg)
    assert r["score"] == 0.0
    assert r["rejected"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_critic.py -v`
Expected: FAIL with `AttributeError: module 'critic' has no attribute 'check_residue'`

- [ ] **Step 3: Add residue checks and score**

Append to `critic.py`:

```python
from common import _DASH_CODEPOINTS
from write import _AU_SPELLING

_US_WORDS = re.compile(
    r"\b(" + "|".join(sorted(_AU_SPELLING, key=len, reverse=True)) + r")\b", re.I)


def check_residue(text: str) -> list[dict]:
    """A hit here means one of the deterministic fixers has a GAP - the text was
    supposed to be cleaned before it ever reached the critic. Treated as major
    for exactly that reason."""
    out = []
    dashes = sorted({hex(ord(c)) for c in text if ord(c) in _DASH_CODEPOINTS})
    if dashes:
        out.append(_v("dash_residue",
                      "dash characters survived hyphenate(): " + ", ".join(dashes),
                      "major"))
    us = sorted({m.group(0).lower() for m in _US_WORDS.finditer(text)})
    if us:
        out.append(_v("us_spelling",
                      "US spellings survived the normaliser: " + ", ".join(us),
                      "major"))
    return out


def score(dispatch: dict, context: dict, cfg: dict) -> dict:
    """Measure a dispatch. `context` carries years_from_now and engine, both of
    which make some checks conditional. Returns the score, the violations and the
    raw metrics; a draft breaking any cfg["hard_reject"] rule is flagged
    `rejected` but still returned, because the orchestrator may need it as a last
    resort rather than failing to publish."""
    body = dispatch.get("body", "") or ""
    text = f"{dispatch.get('headline', '')} {body}"
    metrics = metrics_for(body)
    violations = []
    violations += check_rhythm(metrics, cfg)
    violations += check_length(metrics, cfg)
    violations += check_phrases(body)
    violations += check_register(body, context.get("engine", ""))
    violations += check_props(text, context.get("years_from_now", 0))
    violations += check_stated_joke(body)
    violations += check_residue(text)
    weights = cfg["weights"]
    penalty = sum(weights.get(v["severity"], weights["minor"])
                  for v in violations)
    hard = set(cfg["hard_reject"])
    return {
        "score": round(max(0.0, 1.0 - penalty), 3),
        "rejected": any(v["rule"] in hard for v in violations),
        "violations": violations,
        "metrics": metrics,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_critic.py -v`
Expected: PASS (18 tests)

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass, no regressions

- [ ] **Step 6: Commit**

```bash
git add critic.py tests/test_critic.py
git commit -m "feat: critic residue checks and the composite score function"
```

---

### Task 5: selection.select_many

**Files:**
- Modify: `selection.py`
- Test: `tests/test_stages.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_stages.py`:

```python
def test_select_many_returns_n_distinct_premises():
    premises = ["a city sues the sea", "a moon secedes over time zones",
                "a fern is mourned by a whole colony",
                "an orbital cricket league refuses zero gravity"]
    out = select_stage.select_many(premises, [], SETTINGS, 3)
    assert len(out) == 3
    assert len(set(out)) == 3
    assert out[0] == premises[0]      # ideate orders strongest first


def test_select_many_drops_near_duplicate_candidates():
    premises = ["a fern is mourned by a whole colony",
                "a fern is mourned by an entire colony",
                "an orbital cricket league refuses zero gravity"]
    out = select_stage.select_many(premises, [], SETTINGS, 3)
    assert len(out) == 2
    assert "cricket" in out[1]


def test_select_many_falls_back_when_too_few_survive():
    premises = ["a fern is mourned by a whole colony",
                "a fern is mourned by an entire colony"]
    out = select_stage.select_many(premises, [], SETTINGS, 3)
    assert len(out) >= 1
    assert out[0] == premises[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stages.py -v -k select_many`
Expected: FAIL with `AttributeError: module 'selection' has no attribute 'select_many'`

- [ ] **Step 3: Implement select_many**

Replace the whole of `selection.py`:

```python
"""Stage 2 - select. Pick premises that pass the novelty gate against the ledger
AND are not near-duplicates of each other; fall back to the head of the list if
too few survive, because publishing beats not publishing."""
from __future__ import annotations

from ledger import is_novel


def select(premises: list[str], ledger: list[dict], settings: dict) -> str:
    nov = settings["novelty"]
    for premise in premises:
        if is_novel(premise, ledger, nov["match_threshold"], nov["recent_window"]):
            return premise
    return premises[0]


def select_many(premises: list[str], ledger: list[dict], settings: dict,
                n: int) -> list[str]:
    """Up to `n` premises, strongest first (ideate already sorts them), each novel
    against the ledger and against the ones already chosen."""
    nov = settings["novelty"]
    chosen: list[str] = []
    for premise in premises:
        if len(chosen) >= n:
            break
        if not is_novel(premise, ledger, nov["match_threshold"],
                        nov["recent_window"]):
            continue
        # compare against the picks so far by reusing the same gate, treating
        # each chosen premise as though it were a recent headline
        peers = [{"headline": c} for c in chosen]
        if chosen and not is_novel(premise, peers, nov["match_threshold"],
                                   nov["recent_window"]):
            continue
        chosen.append(premise)
    return chosen or premises[:1]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stages.py -v -k select_many`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add selection.py tests/test_stages.py
git commit -m "feat: select_many picks N mutually-distinct premises"
```

---

### Task 6: judge.py

**Files:**
- Create: `judge.py`
- Test: `tests/test_judge.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_judge.py`:

```python
import json

import gemini
import judge

SETTINGS = {"gemini": {"model": "gemini-3.6-flash", "endpoint": "x",
                       "timeout_seconds": 1, "max_retries": 0,
                       "temperature_ideate": 1.1, "temperature_write": 0.9}}

DRAFTS = [
    {"headline": "One", "body": "First body."},
    {"headline": "Two", "body": "Second body."},
]


def test_prompt_lists_every_draft_and_asks_for_the_funniest():
    p = judge.build_prompt(DRAFTS)
    assert "One" in p and "Two" in p
    assert "DRAFT 1" in p and "DRAFT 2" in p
    assert "funniest" in p.lower()


def test_judge_returns_pick_and_reason(monkeypatch):
    monkeypatch.setattr(gemini, "generate",
                        lambda *a, **k: json.dumps({"pick": 2, "reason": "kicker"}))
    out = judge.judge(DRAFTS, SETTINGS)
    assert out["pick"] == 1          # converted to a zero-based index
    assert out["reason"] == "kicker"


def test_judge_rejects_an_out_of_range_pick(monkeypatch):
    monkeypatch.setattr(gemini, "generate",
                        lambda *a, **k: json.dumps({"pick": 9, "reason": "x"}))
    try:
        judge.judge(DRAFTS, SETTINGS)
    except gemini.GeminiError:
        return
    raise AssertionError("expected GeminiError for an out-of-range pick")


def test_judge_rejects_a_malformed_response(monkeypatch):
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: "not json at all")
    try:
        judge.judge(DRAFTS, SETTINGS)
    except gemini.GeminiError:
        return
    raise AssertionError("expected GeminiError for a malformed response")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_judge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judge'`

- [ ] **Step 3: Create judge.py**

Create `judge.py`:

```python
"""Pick the funniest of several drafts - the one question the deterministic
critic cannot answer. One model call; raises GeminiError on anything unusable so
the orchestrator can fall back to the top deterministic score."""
from __future__ import annotations

import gemini


def build_prompt(drafts: list[dict]) -> str:
    blocks = []
    for i, d in enumerate(drafts, start=1):
        blocks.append(f"DRAFT {i}\nHeadline: {d['headline']}\n\n{d['body']}")
    joined = "\n\n" + ("\n\n" + "-" * 40 + "\n\n").join(blocks) + "\n\n"
    return f"""You are the editor of The Aftertimes, a satirical newspaper filing
dispatches from the future. Below are {len(drafts)} candidate dispatches for
today's edition. Choose the ONE to publish.

Judge on which is FUNNIEST and most pointed. Specifically:
- Does it satirise something recognisably true about people or institutions, or
  is it merely a whimsical impossibility that is about nothing?
- Does the headline land a joke rather than describe the premise?
- Does the final line work as a real kicker?
- Does a quoted character say something genuinely funny while treating an absurd
  world as completely normal?

Ignore polish, grammar and length - those are fixed separately. Pick on comedy
and point alone. Do not be swayed by whichever is longest or most elaborate.
{joined}
Return JSON only: {{"pick": <the draft number>, "reason": "<one short line>"}}"""


def judge(drafts: list[dict], settings: dict) -> dict:
    """Return {"pick": zero-based index, "reason": str}."""
    raw = gemini.generate(build_prompt(drafts), settings,
                          settings["gemini"]["temperature_write"])
    data = gemini.extract_json(raw)
    if isinstance(data, list):
        data = data[0] if data else {}
    try:
        pick = int(data.get("pick"))
    except (TypeError, ValueError):
        raise gemini.GeminiError(f"judge returned no usable pick: {data!r}")
    if not 1 <= pick <= len(drafts):
        raise gemini.GeminiError(
            f"judge pick {pick} out of range for {len(drafts)} drafts")
    return {"pick": pick - 1, "reason": str(data.get("reason", "")).strip()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_judge.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add judge.py tests/test_judge.py
git commit -m "feat: judge stage picks the funniest draft"
```

---

### Task 7: revise.py, plus extracting write.normalise

**Files:**
- Modify: `write.py`
- Create: `revise.py`
- Test: `tests/test_revise.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_revise.py`:

```python
import json

import gemini
import revise

SETTINGS = {"gemini": {"model": "gemini-3.6-flash", "endpoint": "x",
                       "timeout_seconds": 1, "max_retries": 0,
                       "temperature_ideate": 1.1, "temperature_write": 0.9}}

DISPATCH = {
    "headline": "Shaft Sealed Quietly",
    "body": "Original body text.",
    "scene": "workers stand at a sealed airlock",
    "dateline": {"place": "Oronko", "year": 2600, "years_from_now": 574,
                 "month": 4, "day": 9},
    "domain": "death and mourning",
    "glossary": [],
    "premise": "a colony hides a disaster",
}

VIOLATIONS = [
    {"rule": "rhythm_mean", "detail": "mean sentence is 29 words, wanted 14-20",
     "severity": "major"},
    {"rule": "machine_phrases", "detail": "stock machine phrasing: took an "
     "unexpected turn", "severity": "major"},
]


def test_violations_render_as_plain_instructions():
    text = revise.render_violations(VIOLATIONS)
    assert "mean sentence is 29 words" in text
    assert "took an unexpected turn" in text


def test_prompt_carries_the_draft_and_the_faults():
    p = revise.build_prompt(DISPATCH, VIOLATIONS)
    assert "Original body text." in p
    assert "Shaft Sealed Quietly" in p
    assert "mean sentence is 29 words" in p
    assert "critique" in p


def test_revise_returns_a_normalised_dispatch(monkeypatch):
    payload = {"critique": "too long", "revised": {
        "headline": "Neighbor Sealed" + chr(0x2014) + "Quietly",
        "dateline_place": "Oronko", "body": "Tighter body.",
        "scene": "a sealed airlock", "domain": "death and mourning",
        "glossary": []}}
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: json.dumps(payload))
    out = revise.revise(DISPATCH, VIOLATIONS, SETTINGS)
    assert out["critique"] == "too long"
    d = out["dispatch"]
    # the same normalisation as a fresh write: AU spelling and no em dashes
    assert "Neighbour" in d["headline"]
    assert chr(0x2014) not in d["headline"]
    assert d["body"] == "Tighter body."
    assert d["premise"] == DISPATCH["premise"]
    assert d["dateline"]["year"] == 2600


def test_revise_raises_on_a_missing_revised_object(monkeypatch):
    monkeypatch.setattr(gemini, "generate",
                        lambda *a, **k: json.dumps({"critique": "fine"}))
    try:
        revise.revise(DISPATCH, VIOLATIONS, SETTINGS)
    except gemini.GeminiError:
        return
    raise AssertionError("expected GeminiError when revised is missing")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_revise.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'revise'`

- [ ] **Step 3: Extract normalise() in write.py**

In `write.py`, find the `write()` function's return statement (the block starting
`dl = dict(dateline)` and ending with the returned dict) and replace that portion
with a call to a new shared helper. The new helper goes immediately above
`write()`:

```python
def normalise(d: dict, dateline: dict, domain: str, premise: str) -> dict:
    """Turn a raw parsed model object into a dispatch record, applying every
    deterministic fixer. Shared by the write and revise stages so a revision gets
    exactly the same cleanup as a fresh draft."""
    dl = dict(dateline)
    dl["place"] = hyphenate((d.get("dateline_place") or "").strip())
    return {
        "headline": hyphenate(_fix_slips((d.get("headline") or "").strip())),
        "body": hyphenate(_fix_slips((d.get("body") or "").strip())),
        "scene": hyphenate((d.get("scene") or "").strip()),
        "dateline": dl,
        "domain": (d.get("domain") or domain).strip(),
        "glossary": [{"term": hyphenate(g.get("term", "").strip()),
                      "gloss": hyphenate(g.get("gloss", "").strip())}
                     for g in d.get("glossary", []) if g.get("term")],
        "premise": premise,
    }
```

Then the tail of `write()` becomes:

```python
    print(f"    write: served by {served}", file=sys.stderr)
    return normalise(d, dateline, domain, premise)
```

- [ ] **Step 4: Verify no regression from the extraction**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stages.py -v`
Expected: PASS - the existing `test_write_parses_and_hyphenates` still passes

- [ ] **Step 5: Create revise.py**

Create `revise.py`:

```python
"""Critique and rewrite a winning draft. One model call that returns BOTH the
critique and the revision, so the reasoning benefit arrives without a second
call. The caller decides whether to keep the result - see the acceptance gate in
run.py, which discards a revision that measures worse than the draft."""
from __future__ import annotations

import gemini
from write import build_prompt as write_prompt
from write import normalise


def render_violations(violations: list[dict]) -> str:
    if not violations:
        return "- no measured faults; tighten the comedy only"
    return "\n".join(f"- [{v['severity']}] {v['detail']}" for v in violations)


def build_prompt(dispatch: dict, violations: list[dict]) -> str:
    return f"""You are the editor of The Aftertimes revising a dispatch before
publication. Below is today's draft, followed by faults measured mechanically.

CURRENT HEADLINE: {dispatch['headline']}

CURRENT BODY:
{dispatch['body']}

MEASURED FAULTS:
{render_violations(violations)}

Fix every fault above. At the same time make the piece FUNNIER and more pointed:
sharpen the headline so it lands a joke rather than describing the premise, make
sure a quoted character says something genuinely funny while treating the absurd
world as normal, and make the final line a real kicker that recontextualises
rather than restates.

Do NOT blandify. Keep the specific, concrete and strange details; cut the
explanatory and generic sentences instead. Keep the same story, dateline place
and domain. Australian spelling. Plain hyphens only, never em or en dashes.

Return JSON only:
{{"critique": "<two short lines on what was wrong>",
  "revised": {{"headline": "...", "dateline_place": "...", "body": "...",
               "scene": "...", "domain": "...",
               "glossary": [{{"term": "...", "gloss": "..."}}]}}}}"""


def revise(dispatch: dict, violations: list[dict], settings: dict) -> dict:
    """Return {"critique": str, "dispatch": <normalised dispatch>}.
    Raises GeminiError if the model returns nothing usable."""
    raw = gemini.generate(build_prompt(dispatch, violations), settings,
                          settings["gemini"]["temperature_write"])
    data = gemini.extract_json(raw)
    if isinstance(data, list):
        data = data[0] if data else {}
    revised = data.get("revised")
    if not isinstance(revised, dict) or not (revised.get("body") or "").strip():
        raise gemini.GeminiError(f"revise returned no usable revision: {data!r}")
    out = normalise(revised, dispatch["dateline"], dispatch["domain"],
                    dispatch.get("premise", ""))
    return {"critique": str(data.get("critique", "")).strip(), "dispatch": out}
```

Note: `write_prompt` is imported but unused; remove that import line if the
linter objects. It is listed here only because the revise prompt deliberately
does NOT re-send the full house-style prompt - the draft already embodies it, and
re-sending it doubles the token cost for no benefit.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_revise.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add write.py revise.py tests/test_revise.py
git commit -m "feat: revise stage with shared normalise() extracted from write"
```

---

### Task 8: run.py orchestration and record additions

**Files:**
- Modify: `run.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline.py`:

```python
"""Orchestration paths, with every model call mocked."""
import pytest

import critic
import judge as judge_mod
import revise as revise_mod
import run as run_mod


def _dispatch(headline, body, score_hint=""):
    return {"headline": headline, "body": body + " " + score_hint,
            "scene": "a scene", "domain": "law",
            "dateline": {"place": "P", "year": 2600, "years_from_now": 574,
                         "month": 4, "day": 9},
            "glossary": [], "premise": "p"}


CFG = {
    "n_drafts": 3, "judge": True, "revise": True,
    "hard_reject": ["machine_phrases"],
    "weights": {"major": 0.25, "minor": 0.08},
    "rhythm": {"mean_min": 14, "mean_max": 20, "mean_hard_min": 12,
               "mean_hard_max": 24, "longest_max": 35, "min_short": 2},
    "length": {"min": 200, "max": 280, "hard_min": 160, "hard_max": 340},
}
CTX = {"years_from_now": 574, "engine": "logistics"}


def test_choose_prefers_the_judge_pick(monkeypatch):
    drafts = [_dispatch("A", "body one"), _dispatch("B", "body two")]
    monkeypatch.setattr(judge_mod, "judge",
                        lambda d, s: {"pick": 1, "reason": "funnier"})
    chosen, info = run_mod.choose_draft(drafts, CTX, CFG, {})
    assert chosen["headline"] == "B"
    assert info["judge_reason"] == "funnier"


def test_choose_falls_back_to_top_score_when_judge_fails(monkeypatch):
    import gemini
    good = _dispatch("Good", "The council sealed the shaft on Tuesday. "
                     "Nobody filed a query about the crew that week. "
                     "She walked out. It stayed sealed. "
                     + " ".join(["records show more detail here"] * 40) + ".")
    bad = _dispatch("Bad", "The proceedings took an unexpected turn today.")
    monkeypatch.setattr(judge_mod, "judge",
                        lambda d, s: (_ for _ in ()).throw(
                            gemini.GeminiError("boom")))
    chosen, info = run_mod.choose_draft([bad, good], CTX, CFG, {})
    assert chosen["headline"] == "Good"
    assert info["judge_reason"] == ""


def test_choose_uses_best_rejected_when_all_are_rejected(monkeypatch):
    a = _dispatch("A", "The proceedings took an unexpected turn today.")
    b = _dispatch("B", "The scandal deepened and took an unexpected turn.")
    monkeypatch.setattr(judge_mod, "judge",
                        lambda d, s: {"pick": 0, "reason": "x"})
    chosen, info = run_mod.choose_draft([a, b], CTX, CFG, {})
    assert chosen["headline"] in ("A", "B")
    assert info["all_rejected"] is True


def test_maybe_revise_keeps_a_worse_revision_out(monkeypatch):
    good = _dispatch("Good", "The council sealed the shaft on Tuesday. "
                     "Nobody filed a query that week. She walked out. "
                     + " ".join(["records show more detail here"] * 40) + ".")
    worse = _dispatch("Worse", "The proceedings took an unexpected turn today.")
    monkeypatch.setattr(revise_mod, "revise",
                        lambda d, v, s: {"critique": "c", "dispatch": worse})
    out, info = run_mod.maybe_revise(good, CTX, CFG, {})
    assert out["headline"] == "Good"
    assert info["revision_accepted"] is False


def test_maybe_revise_accepts_a_better_revision(monkeypatch):
    bad = _dispatch("Bad", "The proceedings took an unexpected turn today.")
    better = _dispatch("Better", "The council sealed the shaft on Tuesday. "
                       "Nobody filed a query that week. She walked out. "
                       + " ".join(["records show more detail here"] * 40) + ".")
    monkeypatch.setattr(revise_mod, "revise",
                        lambda d, v, s: {"critique": "c", "dispatch": better})
    out, info = run_mod.maybe_revise(bad, CTX, CFG, {})
    assert out["headline"] == "Better"
    assert info["revision_accepted"] is True


def test_maybe_revise_survives_a_revise_failure(monkeypatch):
    import gemini
    d = _dispatch("Keep", "The proceedings took an unexpected turn today.")
    monkeypatch.setattr(revise_mod, "revise",
                        lambda a, b, c: (_ for _ in ()).throw(
                            gemini.GeminiError("boom")))
    out, info = run_mod.maybe_revise(d, CTX, CFG, {})
    assert out["headline"] == "Keep"
    assert info["revision_accepted"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: FAIL with `AttributeError: module 'run' has no attribute 'choose_draft'`

- [ ] **Step 3: Add the two orchestration helpers to run.py**

In `run.py`, add these imports beside the existing ones:

```python
import critic
import judge as judge_mod
import revise as revise_mod
```

Then add both functions above `run_pipeline()`:

```python
def choose_draft(drafts: list[dict], context: dict, qcfg: dict,
                 settings: dict) -> tuple[dict, dict]:
    """Score every draft, then let the model pick the funniest survivor. Returns
    (chosen dispatch, info) where info records the scores and how the choice was
    made. Never raises: a judge failure falls back to the top score, and if every
    draft is rejected the best of them is published anyway - a flawed dispatch
    beats no dispatch."""
    scored = [(d, critic.score(d, context, qcfg)) for d in drafts]
    for i, (d, s) in enumerate(scored, start=1):
        rules = ", ".join(v["rule"] for v in s["violations"]) or "clean"
        print(f"    draft {i}: score {s['score']} "
              f"{'REJECTED ' if s['rejected'] else ''}[{rules}]")
    survivors = [(d, s) for d, s in scored if not s["rejected"]]
    all_rejected = not survivors
    pool = survivors or scored
    pool = sorted(pool, key=lambda pair: pair[1]["score"], reverse=True)
    info = {"scores": [s["score"] for _, s in scored],
            "violations": [[v["rule"] for v in s["violations"]] for _, s in scored],
            "all_rejected": all_rejected, "judge_reason": ""}
    if all_rejected:
        print("    WARN every draft was rejected; publishing the best of them",
              file=sys.stderr)
    if qcfg.get("judge") and len(pool) > 1:
        try:
            verdict = judge_mod.judge([d for d, _ in pool], settings)
            info["judge_reason"] = verdict["reason"]
            print(f"    judge picked {verdict['pick'] + 1}: {verdict['reason']}")
            return pool[verdict["pick"]][0], info
        except Exception as exc:  # noqa: BLE001 - best effort
            print(f"    WARN judge failed ({exc}); using the top score",
                  file=sys.stderr)
    return pool[0][0], info


def maybe_revise(dispatch: dict, context: dict, qcfg: dict,
                 settings: dict) -> tuple[dict, dict]:
    """Critique and rewrite, publishing the revision ONLY if it measures no worse
    than the draft. This makes the pass non-regressive: a rewrite that sands off
    the voice to satisfy the rules is discarded."""
    before = critic.score(dispatch, context, qcfg)
    info = {"revision_accepted": False, "score_before": before["score"],
            "score_after": None, "critique": ""}
    if not qcfg.get("revise"):
        return dispatch, info
    try:
        out = revise_mod.revise(dispatch, before["violations"], settings)
    except Exception as exc:  # noqa: BLE001 - best effort
        print(f"    WARN revise failed ({exc}); keeping the draft",
              file=sys.stderr)
        return dispatch, info
    after = critic.score(out["dispatch"], context, qcfg)
    info["critique"] = out["critique"]
    info["score_after"] = after["score"]
    if after["score"] >= before["score"]:
        info["revision_accepted"] = True
        print(f"    revision accepted ({before['score']} -> {after['score']})")
        return out["dispatch"], info
    print(f"    revision discarded, measured worse "
          f"({before['score']} -> {after['score']})")
    return dispatch, info
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Wire the helpers into run_pipeline**

In `run_pipeline()`, replace the SELECT and WRITE sections (from
`print(">>> SELECT")` down to and including the existing prose-report warnings)
with:

```python
    qcfg = settings["quality"]
    context = {"years_from_now": dateline["years_from_now"],
               "engine": engine["key"]}

    print(">>> SELECT")
    chosen_premises = select_stage.select_many(
        premises, ledger, settings, qcfg["n_drafts"])
    print(f"    {len(chosen_premises)} premises chosen")

    print(">>> WRITE")
    drafts = []
    for i, premise in enumerate(chosen_premises, start=1):
        try:
            drafts.append(write_stage.write(
                premise, dateline, domain, settings,
                style["guidance"], place_kind["guidance"]))
            print(f"    draft {i}: {drafts[-1]['headline'][:56]}")
        except Exception as exc:  # noqa: BLE001 - one bad draft must not stop us
            print(f"    WARN draft {i} failed: {exc}", file=sys.stderr)
    if not drafts:
        raise RuntimeError("every draft failed")

    print(">>> CHOOSE")
    dispatch, choose_info = choose_draft(drafts, context, qcfg, settings)

    print(">>> REVISE")
    dispatch, revise_info = maybe_revise(dispatch, context, qcfg, settings)
    pr = write_stage.prose_report(dispatch["body"])
    print(f"    final: {dispatch['headline'][:60]}")
    print(f"    prose: {pr['words']}w / mean {pr['mean_sentence']}w / "
          f"longest {pr['longest']}w / {pr['short_sentences']} short")
```

- [ ] **Step 6: Record the quality data**

In the RECORD section of `run_pipeline()`, change the record construction to:

```python
    record = {"run_date": run_date, "run_time": run_dt.isoformat(),
              "dispatch": dispatch, "meta": meta,
              "quality": {"n_drafts": len(drafts), **choose_info,
                          **revise_info}}
```

- [ ] **Step 7: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add run.py tests/test_pipeline.py
git commit -m "feat: wire the multi-draft pipeline into run.py with quality records"
```

---

### Task 9: End-to-end verification on real output

Green tests are not evidence that a generation pipeline works. This task exists
because six real defects once shipped past a full green suite on a sibling
project.

**Files:** none modified unless a defect is found.

- [ ] **Step 1: Run the real pipeline once**

Run: `.venv/Scripts/python.exe run.py`

- [ ] **Step 2: Read the output and check each of these**

- Three drafts were written and each printed a score plus its violation rules.
- The judge printed a pick and a reason, OR the warning path is visible and
  explained.
- The revision was either accepted with the before/after scores shown, or
  discarded because it measured worse.
- The final prose line shows a mean sentence between 14 and 20 words.
- `index.html` and `d/<date>.html` were written and the dateline place matches the
  story's setting.

- [ ] **Step 3: Confirm the record captured the quality data**

Run:
```bash
.venv/Scripts/python.exe -c "import json,glob; d=json.load(open(sorted(glob.glob('data/dispatches/*.json'))[-1],encoding='utf-8')); print(json.dumps(d['quality'],indent=2))"
```
Expected: `n_drafts`, `scores`, `violations`, `all_rejected`, `judge_reason`,
`revision_accepted`, `score_before`, `score_after`, `critique` all populated.

- [ ] **Step 4: Verify the published page is dash-clean**

Run:
```bash
.venv/Scripts/python.exe -c "import common; s=open('index.html',encoding='utf-8').read(); print('dash-clean:', not [c for c in s if ord(c) in common._DASH_CODEPOINTS])"
```
Expected: `dash-clean: True`

- [ ] **Step 5: Commit the generated dispatch**

```bash
git add index.html archive.html d/ data/ assets/img/
git commit -m "dispatch: first edition from the multi-draft pipeline"
```

---

## Self-Review

**Spec coverage:** `critic.py` with all ten rules - Tasks 2-4. `select_many` -
Task 5. `judge.py` - Task 6. `revise.py` plus the acceptance gate - Tasks 7-8.
`quality` config - Task 1. Record additions - Task 8. Failure matrix - covered by
Task 8's helpers (judge failure, revise failure, revision-worse, all-rejected) and
the per-draft try/except in Step 5. Illustrate-only-the-winner - satisfied because
`illustrate` already runs after the chosen dispatch is final and is untouched.
Bible merges only the final glossary - satisfied for the same reason.

**Placeholder scan:** none. Every code step carries complete code; every command
carries expected output.

**Type consistency:** `critic.score` returns `score`/`rejected`/`violations`/
`metrics`, used with those names in Task 8. `judge.judge` returns a zero-based
`pick`, indexed into `pool` in Task 8. `revise.revise` returns
`critique`/`dispatch`, both consumed in `maybe_revise`. `write.normalise` has one
signature, called from `write()` and `revise.revise()` identically.
