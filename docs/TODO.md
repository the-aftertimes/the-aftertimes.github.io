# The Aftertimes - launch checklist

## Open
- [ ] **Ongoing: story-quality tuning.** Keep flagging flat/bland dispatches; the free levers are the ideate prompt (comedic engine), the write prompt (kicker, shape variety, banned names), the seed premises, and the idiom-fixer map in `write.py`. Bigger lever if prompts plateau: the Pro write-model (see Later).
- [ ] Optional self-test: subscribe with your own email on the live site and confirm the contact lands in the Brevo "The Aftertimes" list (#3).
- [ ] Minor: bump the Node 20-deprecated `actions/checkout@v4` + `actions/setup-python@v5` when convenient.

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

## Later (v2 ideas)
- [ ] **Try a Pro model for the write stage.** If prompt-tuning plateaus on story quality, switch the `write` stage from `gemini-3.6-flash` to a Gemini Pro model (e.g. `gemini-3-pro-preview`) for sharper prose. Pro's free-tier quota is tighter, so wire a graceful fallback to flash on 429/quota. Keep ideate on flash. Zero-cost constraint still applies.
- [ ] **Locator map.** A small star-map / solar-system map on each dispatch showing where in the galaxy the story is set (the dateline location), the way One Story plots covering countries on a world map.
- [ ] **Filter the archive by tag.** Let readers filter the archive/timeline by domain tag (e.g. show only "Space Law" dispatches).
