"""Re-render a saved dispatch to index.html WITHOUT calling Gemini.
Use to iterate on the look/CSS for free.

    python replay.py 2026-07-28    # a specific archived dispatch
    python replay.py               # the most recent archived dispatch
"""
from __future__ import annotations

import glob
import os
import sys

from common import load_settings, read_json, refresh_render_meta, rel
import render as render_mod


def main() -> int:
    settings = load_settings()
    if len(sys.argv) > 1:
        run_date = sys.argv[1]
    else:
        files = sorted(glob.glob(rel("data/dispatches/*.json")))
        if not files:
            print("No archived dispatches to replay.")
            return 1
        run_date = os.path.basename(files[-1])[:-5]
    record = read_json(f"data/dispatches/{run_date}.json")
    if not record:
        print(f"No dispatch for {run_date}.")
        return 1
    # Refresh the config-derived meta fields from current settings, so a replay
    # reflects the live look/config (e.g. a newly-wired signup form URL, tagline).
    meta = dict(record["meta"])
    meta["signup_form_url"] = settings.get("signup_form_url", "")
    meta["tagline"] = settings["site"]["tagline"]
    meta["site_name"] = settings["site"]["name"]
    meta["base_url"] = settings["site"]["base_url"]
    refresh_render_meta(meta, settings)
    html = render_mod.render_dispatch(record["dispatch"], meta, stale=False)
    with open(rel(settings["output_html"]), "w", encoding="utf-8") as fh:
        fh.write(html)
    perma = f"d/{run_date}.html"
    os.makedirs(rel("d"), exist_ok=True)
    with open(rel(perma), "w", encoding="utf-8") as fh:
        fh.write(render_mod.render_dispatch(record["dispatch"], meta, is_permalink=True))
    print(f"Replayed {run_date} -> {settings['output_html']} + {perma}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
