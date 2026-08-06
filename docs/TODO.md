# The Aftertimes - launch checklist

## Open
- [ ] **Ongoing: story-quality tuning.** Keep flagging flat/bland dispatches. Levers are ALL prompt-side (there is no better model available at zero cost - see the disabled Pro entry below): the ideate prompt (comedic engine + news-event-only rule), the write prompt (headline-carries-the-joke, comedy-is-structure block, banned names), `config/styles.yaml` (news-shapes only), `config/places.yaml` (dateline settings), the seed premises, and the fixer maps in `write.py`.
  - 31/07/2026 pass addressed Charlie's four complaints (Australian-sounding places, clunky/unfunny headline, non-news "council complaint" shape, flat writing). Verified improvement on a live sample: "Atmospheric Bailiffs Tow Repossessed Hurricane Over Unpaid Debts", datelined Verdigris Promenade, Saturn Envelope - with a mid-piece competing-lien turn and a municipal-parking-fine kicker.
  - Watch for the NEXT failure modes: over-reliance on the legal/bureaucratic register (bailiffs, injunctions, liens are becoming a crutch), and quotes that all sound like the same deadpan official.
- [ ] **Archive "Futures visited" timeline is clunky** (Charlie, 04/08/2026). Observed defects on the live page: adjacent year labels COLLIDE and render as mush ("231[]2356" where 2311 and 2356 overlap); the log scale bunches every dot into the right-hand half leaving a large dead gap after the TODO dot; visually it is a thin bare line with dots and reads unfinished; and with only a handful of dispatches it looks sparse. Note the date ceiling is now ~4000 years (deep band dropped), so the log scale matters less than it did and a linear or banded axis may now be viable. Options to weigh: collision-aware label placement (alternate above/below, or drop labels and show on hover); replace the continuous axis with era buckets ("next century / 2100s-2400s / beyond") as columns with counts, which also scales as the archive grows; merge it into the dispatch list below (currently redundant - the list already shows every date); or cut it. Charlie should pick from rendered options per the labelled-visual-options rule. Code: `_timeline()` and `_CSS` in `archive.py`.
- [x] Custom domain LIVE and verified 06/08/2026: `https://aftertimes.charlietrenorden.com` returns 200 over HTTPS (cert provisioned, DNS on the GitHub Pages IPs, `CNAME` file committed), and `/assets/email-masthead.png` resolves - which matters because the newsletter builds its links and masthead URL from `site.base_url`.
- [x] **DONE 06/08/2026 - now sending from the authenticated domain.** `sender_email` is `aftertimes@mail.charlietrenorden.com`; the Brevo sender was created via API (id=3, no SPF/DKIM errors, auto-verified instantly as predicted) and **verified end to end**: campaign 38 went out as `The Aftertimes <aftertimes@mail.charlietrenorden.com>`, not `brevosend.com`.
  Built along the way: `brevo_sender.py` + a manual-only `brevo-admin` workflow (`list` / `campaign` / `create`) so sender admin runs where `BREVO_API_KEY` already lives instead of the key being copied to a laptop; `campaign` re-checks the actual From on the latest campaign.
  **Two gotchas hit that are NOT in the original note:** (1) the Brevo `/senders` endpoints sit behind Cloudflare bot rules that reject urllib's default agent with `403 error 1010 browser_signature_banned` - a real User-Agent header is required, and without it the domain lookup returns empty, which looks exactly like "the domain is not authenticated" (a false negative that briefly sent me the wrong way). `/emailCampaigns`, which `send_email.py` uses, is not blocked. (2) `test_send=true` used to run the WHOLE daily job, so testing the newsletter would burn a day of model quota and republish over the live page; the generate and commit steps are now skipped for a test send.
  Also added a `test_email` workflow input overriding the `BREVO_TEST_EMAIL` secret, per the One Story pattern.
  <details><summary>Original note (kept for the reasoning)</summary>
  **Problem:** `config/settings.yaml` has `newsletter.sender_email: charlie.rochfordgroup@gmail.com`. Brevo cannot authenticate a freemail address, so it rewrites the From to its own **shared** domain `<id>.brevosend.com`. SPF/DKIM/DMARC all pass - it is not an auth failure - but you inherit that shared domain's cold reputation, and the result is that a new subscriber's **first** edition reliably lands in spam. One Story had exactly this for weeks.
  **Why it is cheap:** `mail.charlietrenorden.com` is **already authenticated in Brevo** (done 06/08/2026 for One Story) in the **same Brevo account** and on the **same root domain** this site already uses (`aftertimes.charlietrenorden.com`). So the DNS work is done - do NOT add any DNS records, and do NOT touch the branded subdomain (see gotcha 2).
  **Steps:**
    1. Brevo -> Senders, Domains & IPs -> **Senders** -> *Add sender*: From Name `The Aftertimes`, From Email `aftertimes@mail.charlietrenorden.com`. It auto-verifies **instantly with no confirmation email**, because the domain is authenticated. Confirm the row shows *Verified* with DKIM signature `mail.charlietrenorden.com` and "DMARC is configured".
    2. Set `newsletter.sender_email: "aftertimes@mail.charlietrenorden.com"` in `config/settings.yaml` (leave `sender_name` and `list_id: 3` alone). Commit + push - the daily job sends from `main`.
    3. Test: `gh workflow run <daily workflow> -f test_send=true`, which sends to the `BREVO_TEST_EMAIL` secret. **Note:** unlike One Story, this repo's `workflow_dispatch` has no `test_email` input, so you cannot target an arbitrary address without adding one (One Story's `daily.yml` has the pattern to copy - a `test_email` string input that overrides the secret). Verify the received email's **From** reads `@mail.charlietrenorden.com`, NOT `brevosend.com`, and that it landed in the inbox.
  **Two gotchas that cost real time on One Story:**
    1. **An authenticated domain is NOT sufficient to send.** The address must ALSO exist as a Sender or the campaign API returns `400 invalid_parameter "Sender is invalid / inactive"`. Step 1 is not optional.
    2. **Do not opt into a branded subdomain.** Brevo refuses to mark a domain authenticated while the *optional* branding records mismatch, so it turns a nice-to-have into a hard blocker - and its record values are unreadable programmatically (truncated in the UI, absent from the accessibility tree, page JS blocked). Irrelevant if you leave it alone, which you should.
  **Expected result:** One Story's very first send from this authenticated domain **landed in the inbox with no warm-up period**, so expect the same rather than a slow reputation build.
  </details>
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
- [x] **Pro write-model + flash fallback** (30/07/2026), then **DISABLED 31/07/2026**. The fallback machinery works and is retained, but `write_model` is now blank: **every Pro-tier model (`gemini-3.1-pro-preview`, `gemini-3-pro-preview`, `gemini-pro-latest`, `gemini-2.5-pro`) returns HTTP 429 on this free key - the free tier has ZERO Pro quota, exactly like image generation.** It never once served (every dispatch to date was flash) and leaving it on burned a wasted call + ~1.5s each run. **Do not re-enable without a paid key.** Prose quality therefore rests entirely on the prompts.
- [x] **Locator chart** (30/07/2026). Per-dispatch ink-on-bone SVG (circular celestial plate): centre = now, marker = the story's dateline, radius log-scaled by years-from-now. Deterministic (sha256(scrubbed place + year) -> splitmix64), so index/permalink/replay match byte-for-byte. Inline SVG, web only (not email). Charlie picked the plate from 3 labelled options.
- [x] **Archive domain filter** (30/07/2026). Chips built from the observed domain set (deduped on a normalised key), filtering both the list and the future-timeline together; defaults to all-visible so it works with JS off.

## Free-model survey (04/08/2026) - read this before shopping for a better model

Gemini free tier is **flash only** (every Pro model 429s - zero Pro quota).
So the other free option already wired to this project is **Cloudflare Workers AI**,
on the SAME `CF_ACCOUNT_ID` / `CF_API_TOKEN` already used for the engravings.
It exposes **26 text-generation models**. Tested on an identical write prompt:

| Model | Result |
|---|---|
| `@cf/openai/gpt-oss-120b` | **The only real contender.** 3/3 reliable, but ONLY with `max_tokens>=4000` - it is a reasoning model and burns 3k-9k chars of thinking first; at 2000 it returns null content. Metrics were fine (225w, mean 15.0, longest 23). Prose was competent but noticeably LESS FUNNY than flash - more worldbuilding, weaker jokes. Emits U+2011 non-breaking hyphens (which is how the `hyphenate()` gap was found). |
| `@cf/nvidia/nemotron-3-120b-a12b` | Empty response - reasoning consumed the budget. |
| `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Catastrophically over-applies the rhythm rule: mean sentence 5.0 words, 17 short sentences, 104 words total - reads like a children's book. Also **lifted a prompt example verbatim** into the story. |
| `@cf/mistralai/mistral-small-3.1-24b-instruct` | Returned no usable JSON. |
| `@cf/moonshotai/kimi-k2.6`, `@cf/zai-org/glm-5.2` | HTTP 403 - not available on this plan. |

**Conclusion: stay on gemini-3.6-flash.** It is currently the funniest of the free
options and the most reliable at returning clean JSON. `gpt-oss-120b` is the
documented fallback if flash quota ever disappears - all CF models are
OpenAI-shaped (`result.choices[0].message.content`), unlike Gemini.
Untested elsewhere (would need a new key): Groq, GitHub Models, OpenRouter free tier.

## Later (v3 ideas)
- [ ] **Style-transfer the locator into an engraving.** The chart is clean vector; a future pass could render it as a hand-engraved star plate to sit even closer to the Dore illustrations.
