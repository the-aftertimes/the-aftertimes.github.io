# The Aftertimes - working notes for Claude

## `main` has a SECOND writer: the bot

`daily-dispatch` commits and pushes to `main` **twice a day** (20:13 and 22:13
UTC), writing `index.html`, `archive.html`, `d/`, `data/` and `assets/img/`. So
your local clone goes stale on its own, with nobody touching it.

**Always `git pull` before you commit or push.** A push that has worked all
session will be rejected the moment a cron lands, and on 17/08/2026 it was
rejected after the bot filed two days of dispatches mid-session.

`pull.rebase` and `rebase.autoStash` are set locally in this repo, so a plain
`git pull` rebases and stashes work-in-progress for you. That fixes the second
failure mode too: `git pull --rebase` with unstaged changes used to abort with
*"cannot pull with rebase: You have unstaged changes"*.

**Do not** rewrite pushed history or force-push. The bot will push again on the
next cron regardless, so a force-push only loses dispatches.

Watch for conflicts in `data/` specifically - it is the one tree both you and
the bot write to (`data/dispatches/`, `data/last_email.json`,
`data/send_hold.json`, `data/trials/`).

## The newsletter is HELD, not broken (as at 17/08/2026)

Brevo put the shared account under validation on 10/08. `send_email.py` latches
`data/send_hold.json` on a 402 and stops calling the API - that is deliberate, to
avoid hammering an account under manual review. Clear it only once the account is
resolved:

```bash
python send_email.py --clear-hold
```

Publishing is unaffected and has continued throughout. See `docs/TODO.md` for the
full diagnosis, including the separate and larger finding that campaigns have
been delivering to an effectively empty list.

## Before changing anything about prose quality

Read `config/funny_lines.yaml` and the `quality` block in `config/settings.yaml`
first. The critic's thresholds are evidence-derived and one of them was wrong in
the dangerous direction (a rhythm floor that penalised the only dispatch Charlie
found funny). Do not reintroduce a threshold set by taste rather than by a
verdict.
