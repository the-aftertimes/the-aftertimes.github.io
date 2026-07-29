# The Aftertimes - launch checklist

Open items, in rough order. Tick as done.

## Deferred (do not forget - flagged by Charlie 29/07/2026)
- [ ] **Push to GitHub.** Currently a local-only git repo (17+ commits) on branch `build/initial-implementation`. Needs the GitHub org `the-aftertimes` created, then push + merge. (Deploy step.)
- [ ] **Website + link from personal site.** Deploy via GitHub org `the-aftertimes` -> Pages (`the-aftertimes.github.io`), then add a one-line card linking to it from `charlie-tren.github.io` (repo `charlie-tren/charlie-tren.github.io`).
- [ ] **Subscribe box (Brevo).** The signup form is already built into `render.py`; it is dormant until `signup_form_url` is set in `config/settings.yaml`. Create a new Brevo list/form for The Aftertimes (Charlie already runs Brevo for One Story) and wire the form URL.

## In flight
- [ ] **Pictures** - Cloudflare Workers AI engraving per dispatch (CF creds now in `.env`); validating quality, then build `illustrate.py` + wire in with graceful fallback.
- [ ] **Tagline** - replacing "Dispatches from years that have not yet happened"; Charlie choosing from options.

## Before first live edition
- [ ] **Reset generated artefacts** so day 1 starts clean: `data/ledger.json` -> `[]`, `data/bible.json` -> the 3 seed motifs, delete test `data/dispatches/*.json`, `d/*.html`, and the placeholder `index.html`/`archive.html`. (These got swept into git during local tone-testing.)
- [ ] Set the `GEMINI_API_KEY` (and CF token) as GitHub Actions secrets for the daily cron.
