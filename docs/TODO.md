# The Aftertimes - launch checklist

## Open
- [ ] **Ongoing: story-quality tuning.** Keep flagging flat/bland dispatches; the free levers are the ideate prompt (comedic engine), the write prompt (kicker, shape variety, banned names), the seed premises, and the idiom-fixer map in `write.py`. Now also: the Pro write-model (below) - watch the cron log's "write: served by ..." line to see how often Pro actually wins vs falls back to flash.
- [ ] Optional self-test: subscribe with your own email on the live site and confirm the contact lands in the Brevo "The Aftertimes" list (#3).

## Done
- [x] **Deployed + live** at https://the-aftertimes.github.io/ (org `the-aftertimes`, Pages from main root, daily Actions cron 20:00 UTC, `.nojekyll`).
- [x] **Daily newsletter LIVE** - subscribe box (Brevo form -> list #3, single opt-in) + `send_email.py` daily send (per-day guard, `test_send` toggle); `BREVO_API_KEY` + `BREVO_TEST_EMAIL` secrets set and a test verified to both inboxes. Cron sends live each morning.
- [x] **Linked from the personal hub** (charlie-tren.github.io) with a screenshot thumbnail.
- [x] **Pictures** - Cloudflare Workers AI engravings (greyscale, story-scene-derived, caption cropped, graceful fallback).
- [x] **Look** - tagline "Tomorrow's headlines, a little early"; NYT-blackletter masthead; edition line; actual-date dateline; Title-Case domain; glossary removed from the page.
- [x] **Email polished** - blackletter-image masthead, correct tagline, embedded engraving, single-tone background, bottom padding.
- [x] **Writing tuned** - comedic-engine premises (best-first), kicker + no forced metaphors, banned recurring names, 11 distinct style shapes (only court/notice are "ruling"-shaped), permanent idiom-slip fixer.
- [x] Secrets set: `GEMINI_API_KEY`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `BREVO_API_KEY`, `BREVO_TEST_EMAIL`.
- [x] Launch-day duplicate edition self-healed (cron regenerates fresh, non-duplicate editions via the ledger).
- [x] **Pro write-model + flash fallback** (30/07/2026). Write stage tries `gemini-3.1-pro-preview` (verified callable via ListModels), falls back to `gemini-3.6-flash` on any failure; Pro attempt fast-fails (retries=0) so a quota 429 drops to flash immediately. One flippable key `gemini.write_model` (blank to disable). Logs which model served. NOTE: free-tier Pro quota is tight - it 429'd on the first live call and fell back; how often Pro actually serves depends on daily quota at cron time, so treat the prose upgrade as best-effort.
- [x] **Locator chart** (30/07/2026). Per-dispatch ink-on-bone SVG (circular celestial plate): centre = now, marker = the story's dateline, radius log-scaled by years-from-now. Deterministic (sha256(scrubbed place + year) -> splitmix64), so index/permalink/replay match byte-for-byte. Inline SVG, web only (not email). Charlie picked the plate from 3 labelled options.
- [x] **Archive domain filter** (30/07/2026). Chips built from the observed domain set (deduped on a normalised key), filtering both the list and the future-timeline together; defaults to all-visible so it works with JS off.

## Later (v3 ideas)
- [ ] **Style-transfer the locator into an engraving.** The chart is clean vector; a future pass could render it as a hand-engraved star plate to sit even closer to the Dore illustrations.
