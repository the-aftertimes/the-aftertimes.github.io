"""Build archive.html - every past dispatch, newest first, plus a future-timeline
bar plotting each by its dateline. Pure functions; run separately or from run.py."""
from __future__ import annotations

import glob
import html
import math
import os

from common import hyphenate, load_settings, read_json, rel
from dates import format_dateline

_MINOR = {"a", "an", "and", "the", "of", "to", "in", "on", "for", "at", "by", "or", "with"}


def _title_case(s: str) -> str:
    words = s.split()
    return " ".join(w if (w.lower() in _MINOR and i) else w[:1].upper() + w[1:]
                    for i, w in enumerate(words))


def _dom_key(domain: str) -> str:
    """Normalised filter key for a domain (casing/whitespace-insensitive)."""
    return " ".join((domain or "").strip().lower().split())


def _domain_chips(records: list[dict]) -> str:
    """A row of filter chips: 'All' plus every distinct domain observed in the
    records (label is first-seen title-case; key is the normalised form)."""
    labels: dict[str, str] = {}
    for r in records:
        raw = r["dispatch"].get("domain", "")
        key = _dom_key(raw)
        if key and key not in labels:
            labels[key] = _title_case(hyphenate(raw.strip()))
    if not labels:
        return ""
    chips = ('<button type="button" class="chip is-active" '
             'data-filter="all" aria-pressed="true">All</button>')
    for key in sorted(labels, key=lambda k: labels[k].lower()):
        chips += (f'<button type="button" class="chip" '
                  f'data-filter="{html.escape(key, quote=True)}" '
                  f'aria-pressed="false">{html.escape(labels[key])}</button>')
    return f'<div class="chips" role="group" aria-label="Filter by domain">{chips}</div>'

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
.timeline{position:relative;height:60px;margin:0 0 2rem;}
.timeline::before{content:"";position:absolute;left:0;right:0;top:22px;height:1px;
  background:var(--rule);}
.ttoday,.tmark{position:absolute;top:0;text-align:center;transform:translateX(-50%);}
.ttoday-dot{display:block;width:9px;height:9px;margin:17.5px auto 0;box-sizing:border-box;
  border:1.5px solid var(--muted);border-radius:50%;background:var(--bg);}
.tdot{display:block;width:9px;height:9px;margin:17.5px auto 0;border-radius:50%;
  background:var(--accent);opacity:0.85;}
.ttoday-label,.tyear{display:block;margin-top:0.35rem;white-space:nowrap;
  font-family:-apple-system,system-ui,sans-serif;font-size:0.6rem;letter-spacing:0.06em;
  color:var(--muted);}
.ttoday-label{text-transform:uppercase;}
.chips{display:flex;flex-wrap:wrap;gap:0.4rem;margin:0 0 0.4rem;
  font-family:-apple-system,system-ui,sans-serif;}
.chip{cursor:pointer;font:inherit;font-size:0.68rem;letter-spacing:0.08em;
  text-transform:uppercase;padding:0.32rem 0.7rem;border:1px solid var(--rule);
  border-radius:1rem;background:transparent;color:var(--muted);}
.chip:hover{border-color:var(--accent);color:var(--accent);}
.chip.is-active{background:var(--accent);border-color:var(--accent);color:var(--bg);}
ul.disp{list-style:none;margin:0;padding:0;}
ul.disp li.is-hidden,.timeline .tmark.is-hidden{display:none;}
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
.hublink{margin:0.45rem 0 0;}
"""


_FILTER_JS = """
(function(){
  var chips=document.querySelectorAll('.chip');
  var items=document.querySelectorAll('ul.disp li, .timeline .tmark');
  if(!chips.length)return;
  function apply(key){
    items.forEach(function(el){
      var show=(key==='all'||el.getAttribute('data-domain')===key);
      el.classList.toggle('is-hidden',!show);
    });
    chips.forEach(function(c){
      var on=c.getAttribute('data-filter')===key;
      c.classList.toggle('is-active',on);
      c.setAttribute('aria-pressed',on?'true':'false');
    });
  }
  chips.forEach(function(c){
    c.addEventListener('click',function(){apply(c.getAttribute('data-filter'));});
  });
})();
"""


def _timeline(records: list[dict]) -> str:
    if not records:
        return ""
    yrs = [max(1, r["dispatch"]["dateline"]["years_from_now"]) for r in records]
    log_max = math.log(max(yrs)) if max(yrs) > 1 else 1.0
    marks = (f'<div class="ttoday"><span class="ttoday-dot"></span>'
             f'<span class="ttoday-label">today</span></div>')
    for r in records:
        d = r["dispatch"]
        y = max(1, d["dateline"]["years_from_now"])
        logy = math.log(y) if y > 1 else 0.0
        pct = max(4.0, 100 * logy / log_max) if log_max else 4.0
        headline = html.escape(hyphenate(d["headline"]))
        year = html.escape(str(d["dateline"]["year"]))
        dk = html.escape(_dom_key(d.get("domain", "")), quote=True)
        marks += (f'<div class="tmark" data-domain="{dk}" style="left:{pct:.1f}%" '
                  f'title="{headline}">'
                  f'<span class="tdot"></span><span class="tyear">{year}</span></div>')
    return f'<div class="timeline">{marks}</div>'


def render_archive(records: list[dict], meta: dict) -> str:
    recs = sorted(records, key=lambda r: r["run_date"], reverse=True)
    rows = ""
    for r in recs:
        d = r["dispatch"]
        dl = html.escape(hyphenate(format_dateline(d["dateline"])))
        head = html.escape(hyphenate(d["headline"]))
        dom = html.escape(hyphenate(_title_case(d.get("domain", ""))))
        dk = html.escape(_dom_key(d.get("domain", "")), quote=True)
        rows += (f'<li data-domain="{dk}"><div class="dl">{dl}</div>'
                 f'<a href="d/{r["run_date"]}.html">{head}</a>'
                 f'<div class="dom">{dom}</div></li>')
    chips = _domain_chips(recs)
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
    <p class="hublink"><a class="home" href="https://charlie-tren.github.io/">Other
      projects &rarr;</a></p>
    <h2>Futures visited</h2>
    {_timeline(recs)}
    <h2>All dispatches</h2>
    {chips}
    <ul class="disp">{rows}</ul>
    <footer>Every dispatch is fiction, written by a machine. None of it has happened. Yet.
    </footer>
  </div>
  <script>{_FILTER_JS}</script>
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
