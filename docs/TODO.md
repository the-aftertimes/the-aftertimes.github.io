# The Aftertimes - launch checklist

## Open
- [ ] **Daily newsletter SEND (fast-follow).** The signup box now collects subscribers into the Brevo "The Aftertimes" list, but nothing emails them yet. To wire the daily send: add `BREVO_API_KEY` as a GitHub Actions secret, add the Brevo list_id + verified sender to config, and add a send step to `.github/workflows/daily.yml` that calls Brevo's campaign/transactional API with `email_render.build_email(...)`. Mirror One Story's send job. Mind the HTML-email gotchas (real-send test, free-tier badge, Gmail rendering).
- [ ] Quick self-test: subscribe with your own email on the live site and confirm the contact lands in the Brevo "The Aftertimes" list.
- [ ] Minor: the workflow uses `actions/checkout@v4` + `actions/setup-python@v5` (Node 20 deprecation warning) - bump when convenient.
- [ ] The launch-day live edition was a near-duplicate; the daily cron should replace it with a fresh, non-duplicate edition on the next run (ledger remembers it). Sanity-check the next edition.

## Done
- [x] **Deployed + live** at https://the-aftertimes.github.io/ (org `the-aftertimes`, Pages from main root, daily Actions cron 20:00 UTC). `.nojekyll` in place.
- [x] **Subscribe box wired** - Brevo "The Aftertimes signup" form (single opt-in, no confirmation) -> "The Aftertimes" list; `signup_form_url` set in settings.yaml; box live at the bottom of every dispatch.
- [x] **Linked from the personal hub** (charlie-tren.github.io) with a screenshot thumbnail.
- [x] Pictures - Cloudflare Workers AI engravings (greyscale, story-scene-derived, caption cropped, graceful fallback).
- [x] Tagline "Tomorrow's headlines, a little early"; NYT-blackletter masthead; edition line; day-to-day style rotation; actual-date dateline; Title-Case domain; glossary removed from the page.
- [x] Actions secrets set: `GEMINI_API_KEY`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`.

## Later (v2 ideas)
- [ ] **Locator map.** A small star-map / solar-system map on each dispatch showing where in the galaxy the story is set (the dateline location), the way One Story plots covering countries on a world map.
- [ ] **Filter the archive by tag.** Let readers filter the archive/timeline by domain tag (e.g. show only "Space Law" dispatches).
