"""Build archive.html - every past dispatch, newest first, plus a future-timeline
bar plotting each by its dateline. Pure functions; run separately or from run.py."""
from __future__ import annotations

import glob
import html
import math
import os

from common import BEACON, hyphenate, load_settings, read_json, rel

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
.timeline{position:relative;margin:0 0 2.6rem;}
.taxis{position:absolute;left:0;right:0;top:10px;height:1px;background:var(--rule);}
.tmark{position:absolute;top:0;text-align:center;transform:translateX(-50%);}
.tdot{display:block;width:9px;height:9px;margin:6px auto 0;border-radius:50%;
  background:var(--accent);opacity:0.85;}
.tdot.hollow{box-sizing:border-box;border:1.5px solid var(--muted);
  background:var(--bg);opacity:1;}
.tyear{display:block;margin-top:0.35rem;white-space:nowrap;
  font-family:-apple-system,system-ui,sans-serif;font-size:0.6rem;letter-spacing:0.06em;
  color:var(--muted);}
.ttoday .tyear{text-transform:uppercase;letter-spacing:0.12em;}
/* Lower tiers: a label that would collide drops down behind a leader line. One
   tier per level of crowding, so a cluster of four fans out instead of two of
   them landing back on the same row. */
.tmark.t1 .tyear{margin-top:1.5rem;}
.tmark.t2 .tyear{margin-top:2.65rem;}
.tmark.t3 .tyear{margin-top:3.8rem;}
.tmark.t1::after,.tmark.t2::after,.tmark.t3::after{content:"";position:absolute;
  left:50%;top:15px;width:1px;background:var(--rule);transform:translateX(-50%);}
.tmark.t1::after{height:18px;}
.tmark.t2::after{height:36px;}
.tmark.t3::after{height:55px;}
.chips{display:flex;flex-wrap:wrap;gap:0.4rem;margin:0 0 0.4rem;
  font-family:-apple-system,system-ui,sans-serif;}
.chip{cursor:pointer;font:inherit;font-size:0.68rem;letter-spacing:0.08em;
  text-transform:uppercase;padding:0.32rem 0.7rem;border:1px solid var(--rule);
  border-radius:1rem;background:transparent;color:var(--muted);}
.chip:hover{border-color:var(--accent);color:var(--accent);}
.chip.is-active{background:var(--accent);border-color:var(--accent);color:var(--bg);}
ul.disp{list-style:none;margin:0;padding:0;}
ul.disp li.is-hidden,.timeline .tmark.is-hidden{display:none;}
/* The list is itself a timeline: year on a rail, ordered by distance from now. */
ul.disp li{display:flex;gap:1.2rem;padding:0.8rem 0;
  border-top:1px solid var(--rule);}
.disp .rail{flex:0 0 5.5rem;text-align:right;position:relative;}
.disp .rail::after{content:"";position:absolute;right:-0.63rem;top:0.4rem;
  width:7px;height:7px;border-radius:50%;background:var(--accent);}
.disp .ryear{display:block;font-size:1.15rem;font-weight:700;color:var(--fg);
  line-height:1.1;}
.disp .rago{display:block;font-family:-apple-system,system-ui,sans-serif;
  font-size:0.56rem;letter-spacing:0.1em;text-transform:uppercase;
  color:var(--muted);margin-top:0.15rem;}
.disp .rbody{flex:1 1 auto;border-left:1px solid var(--rule);padding-left:1.2rem;}
.disp a{color:var(--fg);text-decoration:none;font-size:1.05rem;font-weight:700;
  border-bottom:1px solid var(--accent);}
.disp .dom{font-family:-apple-system,system-ui,sans-serif;font-size:0.7rem;
  color:var(--muted);margin-top:0.25rem;}
@media (max-width:30rem){
  /* Tiering works in percent, but label width does not shrink with the
     viewport. Trim the year type so the gap stays real on a phone. */
  .tyear{font-size:0.55rem;letter-spacing:0.02em;}
  ul.disp li{flex-direction:column;gap:0.3rem;}
  .disp .rail{text-align:left;}
  .disp .rail::after{display:none;}
  .disp .rbody{border-left:none;padding-left:0;}
}
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


#: Top of the sampled range (config dates.bands deep max). Fixing the axis to the
#: configured ceiling rather than to whatever the archive happens to hold keeps
#: the scale stable as dispatches accumulate.
_AXIS_MAX_YEARS = 4000

#: Minimum horizontal gap, in percent, before two year labels are treated as
#: colliding and the later one drops to a lower tier.
#: 8% is ~26px at the 327px mobile width, against a 23px four-digit label, so
#: even the narrowest viewport keeps real air between neighbours.
_LABEL_GAP_PCT = 8.0

#: How many stacked label rows the timeline will use before it starts reusing
#: the least-recently-occupied one. Bounds the block's height.
_MAX_TIERS = 4


def _timeline(records: list[dict]) -> str:
    """A horizontal 'distance from now' axis.

    Three deliberate choices, all fixing observed defects:
    - SQUARE ROOT, not log. Log crushed everything into the right-hand half (the
      nearest dispatch sat at 48% with a dead gap before it); sqrt spreads the
      near centuries across the width, putting that same dispatch near 15%.
    - Colliding labels drop to a LOWER TIER with a leader line instead of
      overlapping. 2311 and 2356 sit about 5% apart and used to render as mush.
    - The tier is chosen by asking each row in turn whether its OWN last label
      has cleared, rather than alternating 0/1/0/1. Alternating only ever
      separates neighbours: a cluster of four (2114/2154/2163/2183) put the
      first and third back on the same row about 2% apart, which overlapped.
    """
    if not records:
        return ""
    ordered = sorted(records,
                     key=lambda r: r["dispatch"]["dateline"]["years_from_now"])
    span = math.sqrt(_AXIS_MAX_YEARS)
    marks = ('<div class="tmark ttoday" style="left:0%">'
             '<span class="tdot hollow"></span>'
             '<span class="tyear">today</span></div>')
    # Rightmost label position occupied on each tier; tier 0 starts as taken by
    # the "today" mark at 0%.
    last_on_tier = [0.0]
    max_tier = 0
    for r in ordered:
        d = r["dispatch"]
        y = max(1, min(int(d["dateline"]["years_from_now"]), _AXIS_MAX_YEARS))
        pct = 100.0 * math.sqrt(y) / span
        tier = next((t for t, last in enumerate(last_on_tier)
                     if pct - last >= _LABEL_GAP_PCT), len(last_on_tier))
        if tier == len(last_on_tier):
            if tier < _MAX_TIERS:
                last_on_tier.append(pct)
            else:
                # Everything is crowded: give it to whichever row has the most
                # room, so the unavoidable overlap is as small as possible.
                tier = min(range(_MAX_TIERS), key=lambda t: last_on_tier[t])
                last_on_tier[tier] = pct
        else:
            last_on_tier[tier] = pct
        max_tier = max(max_tier, tier)
        headline = html.escape(hyphenate(d["headline"]))
        year = html.escape(str(d["dateline"]["year"]))
        dk = html.escape(_dom_key(d.get("domain", "")), quote=True)
        marks += (f'<div class="tmark t{tier}" data-domain="{dk}" '
                  f'style="left:{pct:.2f}%" title="{headline}">'
                  f'<span class="tdot"></span>'
                  f'<span class="tyear">{year}</span></div>')
    # Height follows the deepest tier actually used, so a sparse archive keeps a
    # compact bar and a crowded one gets the room it needs.
    height = 56 + round(max_tier * 18.4)
    return (f'<div class="timeline" style="height:{height}px">'
            f'<div class="taxis"></div>{marks}</div>')


def render_archive(records: list[dict], meta: dict) -> str:
    recs = sorted(records, key=lambda r: r["run_date"], reverse=True)
    # The LIST IS THE TIMELINE: ordered by how far out each dispatch is set, with
    # the year on a rail. Previously it repeated every dateline that the bar above
    # had just shown, in publication order.
    by_distance = sorted(
        records, key=lambda r: r["dispatch"]["dateline"]["years_from_now"])
    rows = ""
    for r in by_distance:
        d = r["dispatch"]
        dl = d["dateline"]
        place = html.escape(hyphenate((dl.get("place") or "").strip()))
        head = html.escape(hyphenate(d["headline"]))
        dom = html.escape(hyphenate(_title_case(d.get("domain", ""))))
        dk = html.escape(_dom_key(d.get("domain", "")), quote=True)
        yfn = int(dl["years_from_now"])
        rows += (f'<li data-domain="{dk}">'
                 f'<div class="rail"><span class="ryear">'
                 f'{html.escape(str(dl["year"]))}</span>'
                 f'<span class="rago">{yfn:,} yrs</span></div>'
                 f'<div class="rbody">'
                 f'<a href="d/{r["run_date"]}.html">{head}</a>'
                 f'<div class="dom">{place + " &middot; " if place else ""}'
                 f'{dom}</div></div></li>')
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
{BEACON}
</head>
<body>
  <div class="wrap">
    <header class="masthead">
      <div class="name">{html.escape(meta['site_name'])}</div>
      <div class="tag">{html.escape(hyphenate(meta['tagline']))}</div>
    </header>
    <p><a class="home" href="index.html">&larr; Today's dispatch</a></p>
    <p class="hublink"><a class="home" href="https://charlietrenorden.com/">Other
      Projects &#8599;</a></p>
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
