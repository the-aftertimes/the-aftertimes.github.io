"""Redraw the picture for an already-published dispatch, leaving the words alone.

    python reillustrate.py             # the most recent dispatch
    python reillustrate.py 2026-08-19  # a specific one

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

from common import load_settings, read_json, rel, write_json
import archive as archive_mod
import depict
import illustrate as illustrate_mod
import render as render_mod
from run import _load_dotenv


def _latest_date() -> str | None:
    files = sorted(glob.glob(rel("data/dispatches/*.json")))
    return os.path.basename(files[-1])[:-5] if files else None


def reillustrate(run_date: str) -> int:
    settings = load_settings()
    record = read_json(f"data/dispatches/{run_date}.json")
    if not record:
        print(f"No dispatch for {run_date}.", file=sys.stderr)
        return 1
    dispatch, meta = record["dispatch"], record["meta"]
    print(f">>> REILLUSTRATE {run_date}: {dispatch.get('headline', '')[:70]}")

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
    date = sys.argv[1] if len(sys.argv) > 1 else _latest_date()
    if not date:
        print("No dispatches to reillustrate.", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(reillustrate(date))
