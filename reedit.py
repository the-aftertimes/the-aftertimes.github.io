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
    date = positional[0] if positional else _latest_date()
    if not date:
        print("No dispatches to re-edit.", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(reedit(date, dry))
