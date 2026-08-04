# Multi-draft pipeline - design

Date: 04/08/2026
Status: approved in conversation, pending spec review

## Problem

The paper generates one draft and publishes it unseen. Every quality failure
Charlie has caught (a non-news council complaint, a story about nothing, prose at
30 words per sentence, a Boston fern in the year 37562) shipped because there was
no step between generation and publication. Prompt rules can only ever bias the
first attempt; they cannot detect that a specific draft came back bad.

## Goal

Insert selection and revision between generation and publication, so a weak draft
is caught and either replaced or repaired before anyone reads it.

## Non-goals

- Judging humour in code. Funny is not measurable; only the model can rank it.
- Any change to the daily publish guarantee. The site must still file every day.
- Any spend. Stays on the Gemini free tier.
- Learning across days. That is spec 2 (the learning loop), which consumes the
  scored records this spec emits.

## Shape

```
ideate            1 call    8 premises, strongest first        (unchanged)
select_many(3)    0 calls   top 3 distinct premises via the existing TF-IDF gate
write x3          3 calls   one draft per premise
critic.score      0 calls   measure + hard-reject rule-breakers, rank the rest
judge             1 call    model picks the funniest survivor  (skipped if 1 left)
revise            1 call    critique + rewrite the winner
accept-or-keep    0 calls   publish the revision only if it measures no worse
illustrate        1 CF call ONLY the winner, after selection
```

Six Gemini calls per day, up from two. Free tier, no billing relationship.

## Components

### `critic.py` (new, pure functions, no API)

The deterministic half. Everything measurable lives here so model calls are spent
only on judgement.

```python
def score(dispatch: dict, context: dict, cfg: dict) -> dict
# -> {"score": float, "violations": [{"rule","detail","severity"}], "metrics": {...}}
```

`context` carries `years_from_now` and `engine` (some checks are conditional on
them). `cfg` is the `quality` block from settings, so every threshold is tunable
without editing code.

Checks:

| Rule | Detail | Severity |
|---|---|---|
| `rhythm_mean` | mean sentence outside 14-20 words | major outside 12-24, else minor |
| `rhythm_longest` | any sentence over 35 words | major |
| `rhythm_short` | fewer than 2 sentences of <=6 words | minor |
| `length` | outside 200-280 words | minor; major outside 160-340 |
| `machine_phrases` | any of `write._MACHINE_PHRASES` | major |
| `present_day_props` | prop regex; threshold tightens as `years_from_now` grows | minor under 400 years, major beyond |
| `legal_register` | legal/financial regex, SKIPPED when `engine == "bureaucratic"` | major |
| `stated_joke` | opening 2 sentences match "realised/realized", "too ... to notice", "little did" | minor (heuristic, deliberately soft) |
| `dash_residue` | any codepoint in `common._DASH_CODEPOINTS` survives | major - signals a fixer gap |
| `us_spelling` | any key of `write._AU_SPELLING` survives | major - signals a fixer gap |

`score` starts at 1.0, subtracts a configured weight per violation by severity, and
floors at 0. A draft with any `hard_reject` rule (configurable list, default
`machine_phrases`, `legal_register`, `dash_residue`, `us_spelling`) is marked
`rejected: True` but still returned - the orchestrator needs it as a last resort.

Reasoning for the soft `stated_joke` heuristic: the real fault is semantic and not
reliably detectable by regex. It is scored as a nudge, never a rejection, so a
false positive cannot bin a good draft.

### `selection.py` (extended)

```python
def select_many(premises: list[str], ledger: list[dict], settings: dict,
                n: int) -> list[str]
```

Walks the premises in order (ideate already sorts strongest first), keeping any
that pass the existing novelty gate against the ledger AND are not near-duplicates
of one another, until `n` are collected. Falls back to the head of the list if
fewer than `n` survive. The existing single `select()` stays for callers that want
one.

### `judge.py` (new, 1 call)

Given the surviving drafts (headline plus body), returns the index of the funniest
and a one-line reason. The prompt asks specifically which is funniest and most
pointed, restates the house voice briefly, and is told to ignore polish. Returns
`{"pick": int, "reason": str}`.

Skipped entirely when only one draft survives, saving a call.

### `revise.py` (new, 1 call)

Receives the winning draft AND its measured violations rendered as plain
instructions ("mean sentence is 29 words, cut it"; "you used 'took an unexpected
turn'"; "you named a Boston fern in the year 37562"). Returns
`{"critique": str, "revised": {...}}` - the critique is requested in the same
response so the reasoning benefit arrives without a second call.

The revised object is validated exactly like a fresh write (same JSON shape, same
`_fix_slips` and `hyphenate` treatment).

### Acceptance gate

The revision is scored by `critic.score`. It is published only if its score is
`>=` the draft's. This makes the pass non-regressive by construction and defuses
the main risk of critique-revise loops, which is a compliant but blander rewrite.

### `run.py` (orchestration)

Sequence, with each step's failure behaviour:

1. `ideate` - on failure, existing stale fallback. Unchanged.
2. `select_many(n_drafts)` - pure; cannot fail meaningfully.
3. Write N drafts. Each wrapped: a failed draft is skipped. If ALL fail, stale
   fallback.
4. Score all drafts. Partition into survivors (not rejected) and rejected.
5. If no survivors, proceed with the highest-scoring rejected draft rather than
   failing - publishing beats not publishing, and the log records it loudly.
6. `judge` among survivors; on failure or an out-of-range index, take the highest
   deterministic score.
7. `revise` the winner; on failure, or if the revision scores worse, keep the draft.
8. `illustrate` the final dispatch only.
9. Render, record, ledger, bible, archive - unchanged. Only the FINAL dispatch's
   glossary is merged into the motif bible; discarded drafts contribute nothing,
   or the bible would fill with coinages from stories nobody ever read.

### Config: new `quality` block in `settings.yaml`

```yaml
quality:
  n_drafts: 3
  judge: true
  revise: true
  hard_reject: [machine_phrases, legal_register, dash_residue, us_spelling]
  weights: {major: 0.25, minor: 0.08}
  rhythm: {mean_min: 14, mean_max: 20, longest_max: 35, min_short: 2}
  length: {min: 200, max: 280, hard_min: 160, hard_max: 340}
```

`judge` and `revise` are independently switchable so either half can be disabled
without a code change if it turns out to hurt.

### Record additions

The per-dispatch JSON gains a `quality` object: draft count, every draft's score
and violations, the judge's pick and reason, whether the revision was accepted,
and the before/after scores. Without this we cannot later tell whether any of this
machinery helped - and spec 2 learns from exactly these records.

## Failure matrix

| Failure | Behaviour |
|---|---|
| ideate fails | stale fallback (unchanged) |
| some writes fail | proceed with the drafts that returned |
| all writes fail | stale fallback |
| no draft passes scoring | publish the best rejected draft, log loudly |
| judge fails / bad index | take the top deterministic score |
| revise fails | keep the draft |
| revision scores worse | keep the draft |
| illustrate fails | existing no-image fallback |

## Testing

- `critic.py`: one test per rule, each asserting detection and severity; a test
  that `engine == bureaucratic` suppresses `legal_register`; a test that the
  present-day-prop severity escalates with `years_from_now`; a test that a clean
  dispatch scores 1.0 and is not rejected.
- `select_many`: returns n distinct, dedupes near-identical premises, falls back
  when too few survive.
- `judge`: parses a valid pick; out-of-range and malformed responses fall back.
- `revise`: accepted when the revision scores better, discarded when worse
  (both with mocked model calls).
- Orchestration with all model calls mocked: the happy path, one-survivor (judge
  skipped), zero-survivor, judge failure, revise failure, revise-worse.
- Existing register and prompt guards stay green.

## Verification before calling it done

Run the real pipeline once end to end with live calls, print every draft with its
score, the judge's reason and the accept/reject decision, and read them. Per the
codified lesson, green tests are not evidence that a generation pipeline works -
the actual output has to be inspected.
