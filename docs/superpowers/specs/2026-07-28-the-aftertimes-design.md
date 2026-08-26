# The Aftertimes - design spec

- **Status:** approved (brainstorm complete), pending implementation plan
- **Date:** 28/07/2026
- **Author:** Charlie Trenorden (with Claude)
- **Backup name:** The Anachronist

## 1. Concept

The Aftertimes is a public website that publishes **one AI-generated news dispatch per day, datelined from a random date in the future.** It is a sibling to One Story (`the-one-story.github.io`) and reuses its infrastructure almost wholesale, but inverts the core: where One Story *aggregates real news deterministically with no LLM*, The Aftertimes *generates fiction with an LLM and no real-news input*.

**Register:** wild, imaginative science fiction with a knowing satirical edge. Dispatches from a genuinely strange future, written straight-faced (Black-Mirror-meets-The-Onion, played as a real newswire). Plausibility is not a constraint; wit and surprise are the goals.

**The hook:** the same appeal as One Story (one thing a day, read in under a minute, a legible machine behind it), pointed at an imagined future instead of the real present.

## 2. Goals and non-goals

**Goals**
- A single, arresting daily dispatch that reads like a real wire story from the future.
- Zero running cost (free-tier LLM, free hosting). This is a hard constraint.
- A look that is distinctive and clearly *not* One Story: a printed broadsheet from a future that never arrived.
- An accumulating, browsable archive that rewards return visits (the future "world" builds up over time).
- Newsletter delivery infrastructure built in from the start (activated web-first).

**Non-goals**
- No hard future canon / timeline consistency (loose motifs only - see 5).
- No real-news input, no fact-checking, no plausibility guarantee.
- No user accounts, comments, or interactivity beyond newsletter signup.
- No paid APIs or paid hosting, ever.

## 3. Architecture

The pipeline mirrors One Story's four stages, renamed:

| One Story | The Aftertimes | Purpose |
|-----------|----------------|---------|
| `fetch`   | `ideate`  | Gemini brainstorms ~8 candidate premises for a random future date + domain, avoiding recent motifs/eras. |
| `cluster` + `rank` | `select` | Choose the most surprising premise; reject anything too close to a recent dispatch (novelty guard). |
| `render` (data prep) | `write` | Gemini writes the full dispatch (headline, dateline, body, filed-by, metadata + coined glossary terms). |
| `render` (HTML) | `render` | Emit static `index.html` in the bone-broadsheet look. |

Orchestrated by a single `run.py` that holds data in memory across stages and runs once per invocation, exactly like One Story. Top-level guard never crash-publishes: on failure it keeps the previous `index.html` and injects a stale banner ("Showing yesterday's dispatch").

### 3.1 The date mechanism
- **Weighted-random** future date. Mode a few decades to a few centuries out; long right tail to the deep future (year 40,000, post-human epochs, a heat-death-of-the-universe wildcard as the rare unhinged one).
- Implementation: sample years-from-now from a heavy-tailed distribution (e.g. log-normal or a mixture: ~70% within 10-300 yrs, ~25% 300-3000 yrs, ~5% 3000+ up to a configurable ceiling). Exact parameters live in `settings.yaml`.
- **Light anti-clustering:** avoid re-using an era within N recent days (checked against the ledger), so you are not datelined the same century two days running.
- The chosen dateline (invented place + date) is the **hero element** on the page.

### 3.2 Generation (Gemini, free tier)
- **Model:** Gemini 2.5 Flash (or Flash-Lite) via Google AI Studio free tier. One `GEMINI_API_KEY` GitHub secret.
- **Volume:** 1 dispatch/day = ~2 calls/day (ideate batch + write). Trivially inside free limits.
- **Two-stage prompting:**
  - *Ideate prompt* is seeded with: the random date + years-from-now, a randomly chosen domain, a slice of the vibe bible (a few motifs it may reuse), and a "do not repeat these recent premises/domains/eras" list from the ledger. Returns ~8 one-line premises as JSON.
  - *Write prompt* takes the selected premise and produces structured JSON: `headline`, `dateline_place`, `body` (250-350 words, shorter end), `wire_name`, `wire_gloss`, `domain`, and `glossary` (list of coined terms + one-line definitions).
- **Select:** deterministic pick of the "most surprising" premise. Default heuristic: Gemini ranks its own premises in the ideate call *and* a novelty check (TF-IDF cosine vs recent dispatch headlines, reusing One Story's approach) vetoes any premise too similar to a recent one. Fallback: first premise that passes the novelty gate.
- **Robustness:** JSON parsing is defensive (strip code fences, retry once on malformed output). Zero valid output after retry -> pipeline failure -> stale fallback.

## 4. Article anatomy
- **Length:** 250-350 words (shorter end of 250-400).
- **Headline:** the hook. One line.
- **Dateline:** `INVENTED-PLACE · DD MONTH YYYY` - a real-but-changed or fully invented place from the vibe bible, plus the random future date. Shown large.
- **Filed by:** an invented future wire/outlet (e.g. *Nordwire*, *Solar Wire*). Each coined wire is added to the vibe bible and can recur.
- **Dispatch metadata panel** (collapsible, the analogue of One Story's "Why this story?"): the date + years-from-now ("366 years from today"), the domain, and a short glossary of the invented terms/motifs used in the piece. Rewards curiosity and shows off the accumulating canon.

## 5. Continuity - loose motifs
- A **`vibe bible`** (`data/bible.json`): a growing store of coined elements - wires/outlets, megacorps, nations/places, slang, technologies - each with a one-line definition and first-seen date.
- Motifs *may* resurface for texture but consistency is **not enforced**. The ideate/write prompts are fed a small random slice of the bible as optional colour.
- New coined terms from each day's `glossary` are appended to the bible (deduped) after a successful run.

## 6. Look and feel

**Direction: "Broadsheet 2200" - light bone paper.** A grand newspaper printed in a future that never arrived.

- **Palette:** bone paper `#eeece5` (was `#f4efe3` until 26/08/2026 - the yellow was pulled out for a greyer stone), ink `#1a1611`, muted `#6b5f4d`, oxblood accent `#7a2b2b`, hairline rule `#cdc3ad`. (Accent is a single-token swap; oxblood is the default.)
- **Type:** Georgia / Times serif for masthead, headline, body. System sans for labels/datelines/metadata (small uppercase, letter-spaced).
- **Masthead:** centred "The Aftertimes" in large serif, double-rule (`3px double`) underline, tagline "Dispatches from years that have not yet happened".
- **Body layout** (single column, ~44rem, like One Story): masthead -> dateline (oxblood, uppercase, letter-spaced) -> big serif headline -> lede/body -> "Filed by [wire]" -> collapsible Dispatch metadata panel -> footer.
- Committed single theme (light). No dark mode (mirrors One Story's "committed by design" stance, opposite polarity).
- House style: **no em/en dashes anywhere** - plain hyphens only (reuse One Story's `_hyphenate`).

## 7. Pages
- **`index.html`** - today's dispatch (above).
- **`/archive`** (build from the start) - every past dispatch, reverse-chronological by *publish* date, and plotted on a **future timeline** by their *dateline* date (so you see the spread of futures visited). Each entry links to a permalink render of that day's dispatch.
- **Permalinks:** each dispatch is rendered/retained so archive entries resolve (e.g. `/d/YYYY-MM-DD.html` or a data-driven archive render).

## 8. Infrastructure (ports from One Story)
- **Hosting:** dedicated GitHub **org** page, `the-aftertimes.github.io` (room for a custom domain later, matches One Story).
- **Schedule:** daily GitHub Actions cron -> `run.py` (Gemini generate) -> commit `index.html` + data + archive -> GitHub Pages serves.
- **Secrets:** `GEMINI_API_KEY`. (Brevo form URL is public, as in One Story.)
- **Committed data:** `data/dispatches/YYYY-MM-DD.json` (full record per day), `data/bible.json`, `data/ledger.json` (recent dates/eras/domains/headline vectors for anti-repetition), `config/settings.yaml`, `config/domains.yaml`, `config/seed_premises.yaml`.
- **Fallback:** never crash-publish; keep prior page + stale banner on failure (One Story's `_inject_stale_banner`).
- **Newsletter:** Brevo signup form embedded from launch (reuse One Story's no-backend hidden-iframe single-opt-in form + `email_render.py`). Daily send wired but web-first; activation is a fast-follow. Heed the HTML-email gotchas already logged (Gmail dark-mode greying, forced branding badge, table+inline+bgcolor for Outlook, real-send self-test).

## 9. Fiction framing (approved)
The AI/fiction nature is explicit but tasteful, so nobody mistakes it for real news while the straight-faced conceit survives:
- Permanent masthead tagline: "Dispatches from years that have not yet happened".
- Footer line: *"Every dispatch is fiction, written by a machine each morning. None of it has happened. Yet."*
- `<meta name="robots">` and Open Graph copy make the fiction explicit in previews/unfurls.

## 10. Seeds (authored at build time, not now)
- `config/domains.yaml` - starter domain axes (biotech, space law, AI rights, sport, religion, food, love, crime, money, art, death, weather, ...).
- `config/seed_premises.yaml` - ~10-15 example premises in Charlie's sense of humour, to set tone for the ideate stage. Claude drafts a first pass; Charlie edits. These are few-shot taste-setters, not a consumable queue.

## 11. Testing
- **`replay.py`** analogue: re-run write/render over an existing dispatch record offline (no API call) to iterate on the look and on prompt output shape.
- **Deterministic units** tested directly: date sampler (distribution + anti-clustering), novelty gate, bible dedup/append, JSON parsing/repair, renderer (golden-file HTML from a fixed record).
- **Generation** validated against real Gemini output on a handful of manual runs before first cron (per the "validate on real data before shipping" rule), checking: tone, length bounds, JSON validity, glossary quality.
- Fixed-record golden render so CSS/layout changes are reviewable without burning API calls.

## 12. Reuse map (from One Story)
Direct or near-direct ports: `common.py` (config/paths/json), `_hyphenate`, stale-fallback logic in `run.py`, the Brevo signup form + `email_render.py`, the TF-IDF novelty approach, GitHub Actions workflow shape, GitHub Pages/org-page setup, OG/meta scaffolding. Net-new: `ideate.py`, `write.py` (Gemini), the date sampler, `bible.json` handling, the archive/timeline page, the broadsheet render theme.

## 13. Open items / v2
- Custom domain (`aftertimes.news` or similar) - later, as with One Story.
- Newsletter daily-send activation - fast-follow after web launch.
- Possible "on this day, from the future" or reader-submitted-premise ideas - out of scope for v1.
