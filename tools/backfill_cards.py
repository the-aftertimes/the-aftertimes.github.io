"""Build the share card for every archived dispatch, then re-render the pages.

    python tools/backfill_cards.py

One-off, 29/08/2026. `card.py` and the `og:image` tags were added that day, but a
generator only fixes what it makes NEXT - every dispatch already published still
carried `twitter:card=summary_large_image` and no image, which is the bug. This
walks the archive so the back catalogue is fixed too, then re-renders each
permalink, the front page and the archive index so the new meta tags appear.

Safe to re-run: building a card is deterministic from the engraving, and
re-rendering a dispatch reproduces the same page from the same stored record.
"""
from __future__ import annotations

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import card                                    # noqa: E402
from common import load_settings, read_json, refresh_render_meta, rel  # noqa: E402
import archive as archive_mod                  # noqa: E402
import render as render_mod                    # noqa: E402


def main() -> int:
    settings = load_settings()
    dates = [os.path.basename(p)[:-5]
             for p in sorted(glob.glob(rel("data/dispatches/*.json")))]
    if not dates:
        print("no dispatches found", file=sys.stderr)
        return 1

    made = skipped = 0
    for d in dates:
        rec = read_json(f"data/dispatches/{d}.json") or {}
        art = (rec.get("dispatch") or {}).get("image")
        if not art or not os.path.exists(rel(art)):
            print(f"  {d}  no engraving - card skipped (page will say 'summary')")
            skipped += 1
            continue
        card.write(d, art)
        made += 1

    # Re-render AFTER every card exists: render_dispatch only emits the og:image
    # tags when it can see the file, so rendering as we went would have left the
    # earliest pages without them.
    for d in dates:
        rec = read_json(f"data/dispatches/{d}.json") or {}
        dispatch, meta = rec.get("dispatch"), rec.get("meta")
        if not dispatch or not meta:
            continue
        refresh_render_meta(meta, settings)
        with open(rel(f"d/{d}.html"), "w", encoding="utf-8") as fh:
            fh.write(render_mod.render_dispatch(dispatch, meta, is_permalink=True))

    newest = dates[-1]
    rec = read_json(f"data/dispatches/{newest}.json")
    meta = rec["meta"]
    refresh_render_meta(meta, settings)
    with open(rel(settings["output_html"]), "w", encoding="utf-8") as fh:
        fh.write(render_mod.render_dispatch(rec["dispatch"], meta))
    archive_mod.build()

    print(f"\n{made} cards built, {skipped} skipped (no engraving), "
          f"{len(dates)} pages re-rendered, front page = {newest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
