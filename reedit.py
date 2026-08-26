"""Re-run the EDITOR over an already-published dispatch. The picture is untouched.

    python reedit.py                  # the most recent dispatch
    python reedit.py 2026-08-22       # a specific one
    python reedit.py 2026-08-22 --dry # print the rewrite, change nothing

Sibling of reillustrate.py, written 22/08/2026. Charlie read that day's dispatch,
said the premise was very good, and listed three faults the deterministic critic
cannot see: a covert recording quoted as though someone had been interviewed, a
punchline that inverted the story's own logic, and an unexplained coinage. The
revise prompt now looks for exactly those, and the acceptance gate no longer
discards a rewrite for measuring fractionally worse - but both changes only reach
dispatches written after them, and the flawed piece was already live.

REWRITING A PUBLISHED PAPER IS AN EDITORIAL ACT, so two things are deliberate:

1. **Every superseded version is kept**, appended to `record["revisions"]` with
   the reason and a timestamp. A dated newspaper that silently changes its own
   back numbers is doing something worse than publishing a flat joke. Nothing is
   ever overwritten without the previous text surviving in the record.
2. **The dateline, domain, date and ledger entry are never touched** - only the
   headline and body. A re-edit cannot turn one dispatch into a different one,
   and `--dry` shows the rewrite without writing anything at all.

The illustration is left exactly as it is even when the body changes: the picture
is expensive, often hand-corrected, and a re-edit is a prose pass. Redraw
separately with reillustrate.py if the rewrite genuinely moves the scene.
"""
from __future__ import annotations

import glob
import os
import sys
from datetime import datetime, timezone

from common import (load_settings, read_json, refresh_render_meta, rel,
                    write_json)
import archive as archive_mod
import critic
import render as render_mod
import revise as revise_mod
from run import _load_dotenv, maybe_revise

#: Fields a re-edit is allowed to change. Everything else in the dispatch - the
#: dateline, the domain, the glossary, the image - is identity, not prose.
#: `scene` is deliberately NOT here: it is the picture brief, revise.py now
#: carries it through untouched, and a 22/08 dry run showed why - the editor
#: returned the word "OBITUARIES" for it.
EDITABLE = ("headline", "body")


def _latest_date() -> str | None:
    files = sorted(glob.glob(rel("data/dispatches/*.json")))
    return os.path.basename(files[-1])[:-5] if files else None


#: The daily cron fires at 20:13 UTC. A batch of re-edits before it competes for
#: the same free Gemini tier, and a trial batch run early on 10/08/2026 exhausted
#: the allowance and degraded that night's dispatch. The gate is enforced here
#: rather than left to whoever presses the button, because "run it after 20:13"
#: is exactly the kind of instruction that survives in a TODO and nowhere else.
_CRON_UTC_HOUR, _CRON_UTC_MINUTE = 20, 13


def quota_window_open(now: datetime | None = None) -> tuple[bool, str]:
    """Is it safe to spend a batch of model calls? Returns (ok, why)."""
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    if read_json(f"data/dispatches/{today}.json"):
        return True, f"{today} has filed"
    cron = now.replace(hour=_CRON_UTC_HOUR, minute=_CRON_UTC_MINUTE,
                       second=0, microsecond=0)
    if now >= cron:
        return True, f"past {_CRON_UTC_HOUR:02d}:{_CRON_UTC_MINUTE:02d} UTC"
    return False, (f"{today} has not filed and it is "
                   f"{now:%H:%M} UTC, before {_CRON_UTC_HOUR:02d}:"
                   f"{_CRON_UTC_MINUTE:02d} - a batch now competes with the "
                   f"day's dispatch for the same free tier")


def archaic_dates() -> list[str]:
    """Published dispatches whose prose still measures as a plainness fault.

    Selected by MEASUREMENT, not by the date range anyone remembers: the
    docs/TODO.md note said "the six pre-04/08 pieces" and the real six are
    30/07, 31/07, 01/08, 03/08, 08/08 and 14/08.
    """
    from common import load_common_words
    cfg = load_settings()["quality"]
    words = load_common_words()
    out = []
    for path in sorted(glob.glob(rel("data/dispatches/*.json"))):
        date = os.path.basename(path)[:-5]
        rec = read_json(f"data/dispatches/{date}.json") or {}
        body = (rec.get("dispatch") or {}).get("body", "")
        if body and critic.check_plainness(body, words, cfg):
            out.append(date)
    return out


def reedit(run_date: str, dry: bool = False) -> int:
    settings = load_settings()
    record = read_json(f"data/dispatches/{run_date}.json")
    if not record:
        print(f"No dispatch for {run_date}.", file=sys.stderr)
        return 1
    dispatch, meta = record["dispatch"], record["meta"]
    # An already-filed record carries the presentation config it was filed
    # under; re-rendering without this reproduces the old page faithfully.
    refresh_render_meta(meta, settings)
    qcfg = settings["quality"]
    print(f">>> REEDIT {run_date}: {dispatch.get('headline', '')[:70]}")

    context = {"years_from_now": dispatch["dateline"].get("years_from_now", 0),
               "engine": "", "common_words": _common_words()}
    before = critic.score(dispatch, context, qcfg)
    print(f"    before: score {before['score']}")

    revised, info = maybe_revise(dict(dispatch), context, qcfg, settings)
    if not info.get("revision_accepted"):
        print("    no change: the editor did not improve it "
              f"({info.get('critique', '')[:100]})")
        return 0

    print(f"    critique: {info['critique']}")
    for field in EDITABLE:
        if (revised.get(field) or "") != (dispatch.get(field) or ""):
            print(f"    --- {field} ---")
            print(f"    was: {(dispatch.get(field) or '')[:400]}")
            print(f"    now: {(revised.get(field) or '')[:400]}")
    if dry:
        print("    --dry: nothing written")
        return 0

    # Keep what is being replaced, before replacing it.
    record.setdefault("revisions", []).append({
        "replaced_at": datetime.now(timezone.utc).isoformat(),
        "reason": info.get("critique", ""),
        **{f: dispatch.get(f) for f in EDITABLE},
    })
    for field in EDITABLE:
        dispatch[field] = revised.get(field, dispatch.get(field))
    write_json(f"data/dispatches/{run_date}.json", record)

    perma = f"d/{run_date}.html"
    with open(rel(perma), "w", encoding="utf-8") as fh:
        fh.write(render_mod.render_dispatch(dispatch, meta, is_permalink=True))
    written = [f"data/dispatches/{run_date}.json", perma]
    # index.html shows ONE dispatch; re-rendering it from an older record would
    # roll the front page back to that day. Same guard as reillustrate.
    if run_date == _latest_date():
        with open(rel(settings["output_html"]), "w", encoding="utf-8") as fh:
            fh.write(render_mod.render_dispatch(dispatch, meta, stale=False))
        written.append(settings["output_html"])
    else:
        print(f"    {run_date} is not the current front page; index.html untouched")
    archive_mod.build()
    written.append("archive.html")
    print("    wrote " + ", ".join(written))
    return 0


def _common_words():
    from common import load_common_words
    return load_common_words()


if __name__ == "__main__":
    _load_dotenv()
    args = [a for a in sys.argv[1:] if a]
    dry = "--dry" in args
    positional = [a for a in args if not a.startswith("--")]

    if "--archaic" in args:
        dates = archaic_dates()
        if not dates:
            print("No published dispatch measures as a plainness fault.")
            raise SystemExit(0)
        ok, why = quota_window_open()
        if not ok and "--force" not in args:
            print(f"REFUSING: {why}.", file=sys.stderr)
            print(f"({len(dates)} would be re-edited: {', '.join(dates)}.) "
                  f"Pass --force to override.", file=sys.stderr)
            raise SystemExit(2)
        print(f">>> ARCHAIC BATCH - {len(dates)} dispatch(es); quota ok: {why}")
        rc = 0
        for d in dates:
            rc |= reedit(d, dry)
        raise SystemExit(rc)

    date = positional[0] if positional else _latest_date()
    if not date:
        print("No dispatches to re-edit.", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(reedit(date, dry))
