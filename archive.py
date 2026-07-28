"""Build archive.html - every past dispatch, newest first, plus a future-timeline
bar plotting each by its dateline. Pure functions; run separately or from run.py."""
from __future__ import annotations

import glob
import html
import math
import os

from common import hyphenate, load_settings, read_json, rel
from dates import format_dateline

_CSS = """
:root{--bg:#f4efe3;--fg:#1a1611;--muted:#6b5f4d;--accent:#7a2b2b;--rule:#cdc3ad;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:Georgia,'Times New Roman',serif;line-height:1.5;}
.wrap{max-width:46rem;margin:0 auto;padding:clamp(2rem,7vw,4rem) 1.5rem 4rem;}
.masthead{text-align:center;border-bottom:3px double var(--fg);padding-bottom:0.9rem;
  margin-bottom:1.4rem;}
.masthead .name{font-size:clamp(2rem,8vw,3rem);font-weight:700;line-height:1;}
.masthead .tag{font-family:-apple-system,system-ui,sans-serif;font-size:0.6rem;
  letter-spacing:0.3em;text-transform:uppercase;color:var(--muted);margin-top:0.6rem;}
h2{font-family:-apple-system,system-ui,sans-serif;font-size:0.72rem;
  letter-spacing:0.18em;text-transform:uppercase;color:var(--accent);margin:1.4rem 0 0.8rem;}
.timeline{position:relative;height:52px;border-top:1px solid var(--rule);
  border-bottom:1px solid var(--rule);margin:0 0 2rem;}
.tick{position:absolute;top:8px;width:2px;height:22px;background:var(--accent);opacity:0.75;}
.tlabel{position:absolute;bottom:2px;font-family:-apple-system,system-ui,sans-serif;
  font-size:0.6rem;color:var(--muted);transform:translateX(-50%);}
ul.disp{list-style:none;margin:0;padding:0;}
ul.disp li{padding:0.9rem 0;border-top:1px solid var(--rule);}
.disp .dl{font-family:-apple-system,system-ui,sans-serif;font-size:0.68rem;
  font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:var(--accent);}
.disp a{color:var(--fg);text-decoration:none;font-size:1.15rem;font-weight:700;
  border-bottom:1px solid var(--accent);}
.disp .dom{font-family:-apple-system,system-ui,sans-serif;font-size:0.72rem;
  color:var(--muted);margin-top:0.2rem;}
a.home{font-family:-apple-system,system-ui,sans-serif;color:var(--accent);
  text-decoration:none;border-bottom:1px solid var(--accent);font-size:0.85rem;}
footer{margin-top:3rem;font-family:-apple-system,system-ui,sans-serif;
  font-size:0.78rem;color:var(--muted);}
"""


def _timeline(records: list[dict]) -> str:
    yrs = [max(1, r["dispatch"]["dateline"]["years_from_now"]) for r in records]
    if not yrs:
        return ""
    lo, hi = math.log(min(yrs)), math.log(max(yrs) + 1)
    span = (hi - lo) or 1.0
    ticks = ""
    for r in records:
        y = max(1, r["dispatch"]["dateline"]["years_from_now"])
        pct = 100 * (math.log(y) - lo) / span
        ticks += f'<div class="tick" style="left:{pct:.1f}%"></div>'
    ends = (f'<div class="tlabel" style="left:2%">{min(yrs):,} yrs</div>'
            f'<div class="tlabel" style="left:98%">{max(yrs):,} yrs</div>')
    return f'<div class="timeline">{ticks}{ends}</div>'


def render_archive(records: list[dict], meta: dict) -> str:
    recs = sorted(records, key=lambda r: r["run_date"], reverse=True)
    rows = ""
    for r in recs:
        d = r["dispatch"]
        dl = html.escape(hyphenate(format_dateline(d["dateline"])))
        head = html.escape(hyphenate(d["headline"]))
        dom = html.escape(hyphenate(d.get("domain", "")))
        rows += (f'<li><div class="dl">{dl}</div>'
                 f'<a href="d/{r["run_date"]}.html">{head}</a>'
                 f'<div class="dom">{dom}</div></li>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f4efe3">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<title>Archive - {html.escape(meta['site_name'])}</title>
<style>{_CSS}</style>
</head>
<body>
  <div class="wrap">
    <header class="masthead">
      <div class="name">{html.escape(meta['site_name'])}</div>
      <div class="tag">{html.escape(hyphenate(meta['tagline']))}</div>
    </header>
    <p><a class="home" href="index.html">&larr; Today's dispatch</a></p>
    <h2>Futures visited</h2>
    {_timeline(recs)}
    <h2>All dispatches</h2>
    <ul class="disp">{rows}</ul>
    <footer>Every dispatch is fiction, written by a machine. None of it has happened. Yet.</footer>
  </div>
</body>
</html>
"""


def build() -> str:
    settings = load_settings()
    files = sorted(glob.glob(rel("data/dispatches/*.json")))
    records = [read_json(f"data/dispatches/{os.path.basename(f)}") for f in files]
    records = [r for r in records if r]
    meta = {"site_name": settings["site"]["name"], "tagline": settings["site"]["tagline"]}
    out = render_archive(records, meta)
    with open(rel("archive.html"), "w", encoding="utf-8") as fh:
        fh.write(out)
    return rel("archive.html")


if __name__ == "__main__":
    print(f"Wrote {build()}")
