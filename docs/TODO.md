# The Aftertimes - launch checklist

## Open
- [ ] **Turn on the daily send:** add `BREVO_API_KEY` (reuse the One Story Brevo key) as a GitHub Actions secret on this repo. Until it's set the send safely dry-runs. Optional: add `BREVO_TEST_EMAIL` (your address) too.
- [ ] **Test the email before the first live cron:** Actions -> daily-dispatch -> Run workflow -> tick "Send a one-off test email..." -> Run. Check your inbox renders well, then the daily cron sends live automatically.
- [ ] Quick self-test: subscribe with your own email on the live site and confirm the contact lands in the Brevo "The Aftertimes" list.
- [ ] Minor: the workflow uses `actions/checkout@v4` + `actions/setup-python@v5` (Node 20 deprecation warning) - bump when convenient.
- [ ] The launch-day live edition was a near-duplicate; the daily cron should replace it with a fresh, non-duplicate edition on the next run (ledger remembers it). Sanity-check the next edition.

## Done
- [x] **Deployed + live** at https://the-aftertimes.github.io/ (org `the-aftertimes`, Pages from main root, daily Actions cron 20:00 UTC). `.nojekyll` in place.
- [x] **Subscribe box wired** - Brevo "The Aftertimes signup" form (single opt-in, no confirmation) -> "The Aftertimes" list (#3); `signup_form_url` set in settings.yaml; box live at the bottom of every dispatch.
- [x] **Daily send built** - `send_email.py` (ported from One Story) + `newsletter` config (list_id 3, verified sender) + a send step in the workflow with a `test_send` toggle. Dry-runs until `BREVO_API_KEY` is set; per-day guard prevents double-sends.
- [x] **Linked from the personal hub** (charlie-tren.github.io) with a screenshot thumbnail.
- [x] Pictures - Cloudflare Workers AI engravings (greyscale, story-scene-derived, caption cropped, graceful fallback).
- [x] Tagline "Tomorrow's headlines, a little early"; NYT-blackletter masthead; edition line; day-to-day style rotation; actual-date dateline; Title-Case domain; glossary removed from the page.
- [x] Actions secrets set: `GEMINI_API_KEY`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`.

## Later (v2 ideas)
- [ ] **Try a Pro model for the write stage.** If prompt-tuning plateaus on story quality, switch the `write` stage from `gemini-3.6-flash` to a Gemini Pro model (e.g. `gemini-3-pro-preview`) for sharper prose. Pro's free-tier quota is tighter, so wire a graceful fallback to flash on 429/quota. Keep ideate on flash. Zero-cost constraint still applies.
- [ ] **Locator map.** A small star-map / solar-system map on each dispatch showing where in the galaxy the story is set (the dateline location), the way One Story plots covering countries on a world map.
- [ ] **Filter the archive by tag.** Let readers filter the archive/timeline by domain tag (e.g. show only "Space Law" dispatches).
