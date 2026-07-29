# The Aftertimes - launch checklist

## Done (launched 29/07/2026)
- [x] **Deployed + live** at https://the-aftertimes.github.io/ (org `the-aftertimes`, Pages from main root, daily Actions cron 20:00 UTC). `.nojekyll` required and in place.
- [x] Pictures - Cloudflare Workers AI engravings (greyscale, story-scene-derived, caption cropped, graceful fallback).
- [x] Tagline "Tomorrow's headlines, a little early".
- [x] Reset generated artefacts before launch (started at Edition No. 1).
- [x] Actions secrets set: `GEMINI_API_KEY`, `CF_ACCOUNT_ID`, `CF_API_TOKEN`.

## Open
- [ ] **Link card on the personal hub site** (`charlie-tren/charlie-tren.github.io`) pointing at the live URL, matching the existing One Story / Crowdwise / Chronoscape cards (ideally a real screenshot thumbnail).
- [ ] **Subscribe box (Brevo).** The signup form is built into `render.py`; dormant until `signup_form_url` is set in `config/settings.yaml`. Create a new Brevo list/form for The Aftertimes, wire the URL. Later: add a daily send step to the workflow using `email_render.build_email`. See HTML-email gotchas.
- [ ] Minor: the workflow uses `actions/checkout@v4` + `actions/setup-python@v5` (Node 20 deprecation warning) - bump when convenient.

## Later (v2 ideas)
- [ ] **Locator map.** A small star-map / solar-system map on each dispatch showing where in the galaxy the story is set (the dateline location), the way One Story plots covering countries on a world map.
- [ ] **Filter the archive by tag.** Let readers filter the archive/timeline by domain tag (e.g. show only "Space Law" dispatches).
