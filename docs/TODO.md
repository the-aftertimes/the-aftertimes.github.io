# The Aftertimes - launch checklist

## >>> DO NEXT
- [ ] **Wire the Brevo subscribe box.** The signup form is built into `render.py` but dormant until `signup_form_url` is set in `config/settings.yaml`. Steps: create a new Brevo list + signup form for The Aftertimes, paste its form action URL into `settings.yaml` `signup_form_url`, redeploy (form then appears at the bottom of every dispatch). Then (optional, fast-follow) add a daily send step to `.github/workflows/daily.yml` using `email_render.build_email`. Mind the logged HTML-email gotchas (real-send test, free-tier badge, Gmail rendering).

## Other open
- [ ] Minor: the workflow uses `actions/checkout@v4` + `actions/setup-python@v5` (Node 20 deprecation warning) - bump when convenient.
- [ ] The launch-day live edition was a near-duplicate (marital-tech review); the daily cron should replace it with a fresh, non-duplicate edition on the next run (the ledger remembers it). Sanity-check the next edition when convenient.

## Done (launched 29/07/2026)
- [x] **Deployed + live** at https://the-aftertimes.github.io/ (org `the-aftertimes`, Pages from main root, daily Actions cron 20:00 UTC). `.nojekyll` in place.
- [x] **Linked from the personal hub** (charlie-tren.github.io) with a screenshot thumbnail.
- [x] Pictures - Cloudflare Workers AI engravings (greyscale, story-scene-derived, caption cropped, graceful fallback).
- [x] Tagline "Tomorrow's headlines, a little early"; NYT-blackletter masthead; edition line; day-to-day style rotation; actual-date dateline; Title-Case domain; glossary removed from the page.
- [x] Actions secrets set: `GEMINI_API_KEY`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`.

## Later (v2 ideas)
- [ ] **Locator map.** A small star-map / solar-system map on each dispatch showing where in the galaxy the story is set (the dateline location), the way One Story plots covering countries on a world map.
- [ ] **Filter the archive by tag.** Let readers filter the archive/timeline by domain tag (e.g. show only "Space Law" dispatches).
