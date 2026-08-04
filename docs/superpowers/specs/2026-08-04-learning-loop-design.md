# Learning loop - design

Date: 04/08/2026
Status: approved in conversation, pending spec review
Depends on: `2026-08-04-multi-draft-pipeline-design.md` (consumes its scored records)

## Problem

Charlie: "I want it to spot recurring trends and update the generic prompt every
day as well so we iterate every day and it gets better and funnier over time."

Every quality gain so far has come from Charlie reading a dispatch, spotting a
pattern, and me changing a prompt by hand. That does not scale and it stops the
moment he stops reading.

## The constraint that shapes the whole design

Rhythm, repetition, registers and props are measurable in code. **Funny is not.**
An unattended nightly loop that optimises what it can measure will optimise exactly
those things and drift toward prose that scores well and reads bland - Goodhart's
law, unobserved for days. And a model editing its own core house-voice rules is the
highest-blast-radius change available: one bad edit degrades every dispatch after
it, silently.

So automation is allocated by whether a trustworthy signal exists:

| Layer | Signal | Automated? |
|---|---|---|
| Repetition and staleness | measurable from the archive | yes, daily |
| What is actually funny | Charlie's verdicts | yes, but he supplies the signal |
| Core house-voice rules | none | no - proposals only, he approves |

## Component 1 - daily trend spotter (`trends.py`, deterministic, 0 calls)

Reads `data/dispatches/*.json` (last N, default 30) and detects what has become
repetitive:

- **Phrase and n-gram overuse** - 2 to 4-grams appearing in 3+ dispatches, minus a
  stopword-ish baseline of ordinary news phrasing.
- **Sentence-opener formulas** - the opening 3 words of each paragraph; flags
  repeats such as "Municipal logs reveal", "Station files show".
- **Name reuse** - given names and surnames of quoted people, and invented org
  names, appearing more than once.
- **Place-name formulas** - patterns rather than literals: "New X", "X-on-Y",
  "X Ring", "Port X", so the formula is caught even when the name differs.
- **Register concentration** - keyword clusters (legal, medical, military,
  culinary...) with a share above a threshold across recent dispatches.
- **Kicker shapes** - the final sentence's grammatical pattern, to catch every
  dispatch ending on the same beat.
- **Structural repeats** - e.g. how often a quote is followed immediately by an
  official denial.

Output: `data/dynamic_avoid.json`, a compact, ranked, size-capped list of
"over-used lately" items with the count and the dates involved.

Decay and cap are essential. Only the last 30 dispatches count, entries below a
count threshold drop out, and the block injected into the prompt is hard-capped
(default 1200 characters). Without the cap this feature slowly re-creates the
verbosity problem we just fixed by bloating the prompt.

## Component 2 - injection

`ideate` and `write` each gain an optional `avoid_block` argument, rendered from
`dynamic_avoid.json` as a short "recently over-used, find something else" section.
It is passed as data, appended at a fixed point in the prompt - it never rewrites
the hand-written prompt text.

This is deliberately the same mechanism as the existing `avoid_headlines`, which
already works; it just widens what counts as repetition.

## Component 3 - Charlie's verdicts (the actual quality engine)

Few-shot examples dominate model output far more than instructions do - that is the
lesson from the "why is it always unpaid debts" investigation. So the highest-
leverage lever available is a growing pool of exemplars that Charlie has personally
endorsed.

CLI:

```
python verdict.py 2026-08-04 good "the kicker lands"
python verdict.py 2026-08-04 bad  "no satirical target"
python verdict.py                     # lists recent dispatches lacking a verdict
```

Writes `data/verdicts.json`. Then:

- **good** - the dispatch's premise is promoted into the exemplar pool
  (`config/exemplars.yaml`), subject to the register-balance guard already enforced
  by `tests/test_registers.py`. If promoting it would push legal/financial share
  over the cap, it is held back and the run says so rather than silently breaking
  the balance.
- **bad** - its distinguishing patterns are added to `dynamic_avoid.json` with a
  longer decay than ordinary staleness entries, and the note is retained as
  evidence for the weekly proposal.

Exemplars are capped (default 24) and the pool is pruned oldest-first among
same-engine entries, so it stays balanced and the prompt stays bounded.

## Component 4 - weekly proposals, human-gated

Once a week the loop writes `docs/prompt-proposals/YYYY-WW.md`: what the trend
spotter and the verdicts suggest about the hand-written rules, each proposal
carrying the evidence (counts, dates, example sentences) and a concrete suggested
diff. One model call may be used to draft the prose.

It is **never applied automatically.** Charlie reads it and says yes or no. This is
the only path by which core prompt text changes, and it stays a human decision.

The weekly nudge reaches him by the same route as the other scheduled work: a
self-addressed Outlook email, since notifications do not reach him.

## Guardrails

- The hand-written prompt is **never** machine-edited. Machine output only ever
  enters through the `avoid_block` and the exemplar pool.
- `dynamic_avoid.json` and `config/exemplars.yaml` are committed daily, so every
  mutation is a readable git diff and revertable with one command.
- Both injected blocks are size-capped; a test asserts the caps.
- Kill switch: `learning.enabled: false` in settings disables injection entirely
  and the paper reverts to today's fixed prompts.
- Entries decay. Nothing accumulates forever.
- The trend spotter is deterministic and free, so it cannot fail the daily run in
  a way that costs anything; on any exception the run proceeds with no avoid block.

## Config

```yaml
learning:
  enabled: true
  window: 30              # dispatches considered for staleness
  min_count: 3            # occurrences before something counts as over-used
  avoid_char_cap: 1200
  exemplar_cap: 24
  proposals_weekday: 0    # Monday
```

## Testing

- `trends.py` against a hand-built fixture archive: each detector fires on a
  planted repetition and stays silent on varied text.
- Decay: an item outside the window stops appearing.
- Caps: the rendered avoid block never exceeds the character cap; the exemplar pool
  never exceeds its cap.
- Register guard: promoting a legal/financial exemplar past the cap is refused.
- `verdict.py`: writes and updates verdicts, lists un-judged dispatches, rejects an
  unknown date.
- Injection: prompts contain the block when enabled and are byte-identical to
  today's when `learning.enabled` is false.
- Prompt-bloat guard: a test asserting total prompt length stays under a ceiling,
  because the whole risk of this feature is re-introducing verbosity.

## How we will know it worked

The pipeline records from spec 1 give a baseline: mean draft score, rejection rate,
revision-acceptance rate, and the distribution of violations. If after a month the
scores have not improved and Charlie's good/bad ratio has not shifted, the loop is
not earning its complexity and should be cut back to the trend spotter alone.

That check is the point of storing the records. It is deliberately falsifiable.
