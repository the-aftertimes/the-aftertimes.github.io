"""Redraw the picture for an already-published dispatch, leaving the words alone.

    python reillustrate.py                        # the most recent dispatch
    python reillustrate.py 2026-08-19             # a specific one
    python reillustrate.py 2026-08-19 --scene "..."   # ...with a corrected scene

Written 19/08/2026, when a published engraving came back lewd - a brief that
named a jumper and boots and nothing in between, which flux completed with bare
legs and a reclining pose. Charlie asked for it to be changed for that day, and
there was no way to do it: the picture path needs CF_ACCOUNT_ID and CF_API_TOKEN,
which live only in Actions, and re-running the daily job cannot help because
run.already_filed() correctly refuses to refile a date that has already published.

So this is deliberately NOT a rerun of the day. It re-runs the two picture stages
only - depict, then illustrate - against the stored dispatch, and rewrites the
image, the record's brief, the permalink, the archive and (only if this is the
current front page) index.html. The prose, the dateline, the ledger and the
bible are never touched, so a redraw cannot quietly rewrite the paper.

Costs one Gemini call and one Cloudflare call. Both stages already print what
they produced, and the old and new briefs are printed side by side so the run log
shows exactly what changed.
"""
from __future__ import annotations

import glob
import json
import os
import sys

from common import (load_settings, read_json, refresh_render_meta, rel,
                    write_json)
import archive as archive_mod
import depict
import card
import illustrate as illustrate_mod
import render as render_mod
from run import _load_dotenv


def _latest_date() -> str | None:
    files = sorted(glob.glob(rel("data/dispatches/*.json")))
    return os.path.basename(files[-1])[:-5] if files else None


def reillustrate(run_date: str, scene: str = "") -> int:
    settings = load_settings()
    record = read_json(f"data/dispatches/{run_date}.json")
    if not record:
        print(f"No dispatch for {run_date}.", file=sys.stderr)
        return 1
    dispatch, meta = record["dispatch"], record["meta"]
    # An already-filed record carries the presentation config it was filed
    # under; re-rendering without this reproduces the old page faithfully.
    refresh_render_meta(meta, settings)
    print(f">>> REILLUSTRATE {run_date}: {dispatch.get('headline', '')[:70]}")

    # A redraw alone cannot fix a bad SCENE LINE, because depict is handed that
    # line and told to draw it rather than choose. 22/08/2026: the scene named
    # the mayor's coach as the subject for an obituary of the mayor, so the first
    # redraw faithfully produced the same wrong picture. The override edits the
    # picture brief only - never the headline, body or dateline - and is stored,
    # so a record always says what its illustration was actually drawn from.
    if scene:
        print(f"    scene overridden\n      was: {dispatch.get('scene', '')}"
              f"\n      now: {scene}")
        dispatch["scene"] = scene

    old_brief = dispatch.get("brief") or {}
    print("    old brief:")
    for f in depict.FIELDS:
        print(f"      {f:9} {old_brief.get(f, '')}")

    brief = depict.depict(dispatch, settings)
    if brief:
        print("    new brief:")
        for f in depict.FIELDS:
            print(f"      {f:9} {brief.get(f, '')}")
    else:
        # Not fatal: illustrate falls back to the writer's scene line. Worth
        # shouting about though, because the brief is where the subject and the
        # clothing rules are enforced.
        print("    WARN depict returned nothing; falling back to the scene line",
              file=sys.stderr)

    image = illustrate_mod.generate(dispatch, run_date, settings, brief)
    if not image:
        print("    FAILED: no image produced; nothing written", file=sys.stderr)
        return 1

    dispatch["brief"] = brief
    dispatch["image"] = image
    # The share card is cut from the engraving, so a redraw makes the old card
    # stale. Rebuilt here rather than left for the next daily run, or the card
    # would show the picture this redraw exists to replace.
    try:
        print(f"    card: {card.write(run_date, image)}")
    except Exception as exc:  # noqa: BLE001 - a card never blocks a redraw
        print(f"    card: FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
    write_json(f"data/dispatches/{run_date}.json", record)

    perma = f"d/{run_date}.html"
    with open(rel(perma), "w", encoding="utf-8") as fh:
        fh.write(render_mod.render_dispatch(dispatch, meta, is_permalink=True))
    written = [image, f"data/dispatches/{run_date}.json", perma]

    # index.html shows ONE dispatch. Rewriting it from an older record would
    # silently roll the front page back to that day, so only the current front
    # page is touched.
    if run_date == _latest_date():
        with open(rel(settings["output_html"]), "w", encoding="utf-8") as fh:
            fh.write(render_mod.render_dispatch(dispatch, meta, stale=False))
        written.append(settings["output_html"])
    else:
        print(f"    {run_date} is not the current front page; index.html untouched")

    archive_mod.build()          # the row's thumbnail and figure come from here
    written.append("archive.html")
    print("    wrote " + ", ".join(written))
    return 0


if __name__ == "__main__":
    _load_dotenv()
    args = [a for a in sys.argv[1:] if a]
    date = args[0] if args and not args[0].startswith("--") else _latest_date()
    scene = ""
    for i, a in enumerate(args):
        if a == "--scene" and i + 1 < len(args):
            scene = args[i + 1]
        elif a.startswith("--scene="):
            scene = a.split("=", 1)[1]
    if not date:
        print("No dispatches to reillustrate.", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(reillustrate(date, scene))
