"""Build archive.html - every past dispatch, newest first, ordered by how far out
it is set. Pure functions; run separately or from run.py.

There WAS a horizontal futures-visited bar above the list. Charlie cut it on
18/08/2026. It had been reworked twice - sqrt scale, then four-tier collision
avoidance - and it still read as a hairline rule with dots, while duplicating
the year rail the list already carries. Do not rebuild it."""
from __future__ import annotations

import glob
import html
import os

import locator
from common import (BEACON, hyphenate, load_settings, normalise_place,
                   read_json, rel)

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
/* Kept identical to render.py's masthead - Charlie, 18/08/2026: the logo on the
   archive must be the same as on the main page. It was plain bold Georgia here
   while the front page wore the blackletter flag, so the two pages did not look
   like the same paper. If one changes, change both. */
.masthead .name{font-family:'Aftertimes Flag','UnifrakturCook',serif;font-weight:700;
  font-size:clamp(2.7rem,10vw,4.6rem);line-height:1;letter-spacing:0.01em;}
.masthead .tag{font-family:-apple-system,system-ui,sans-serif;font-size:0.62rem;
  letter-spacing:0.3em;text-transform:uppercase;color:var(--muted);margin-top:0.7rem;}
h2{font-family:-apple-system,system-ui,sans-serif;font-size:0.72rem;
  letter-spacing:0.18em;text-transform:uppercase;color:var(--accent);margin:1.4rem 0 0.8rem;}
/* The three bands under "All dispatches" - heading, topic chips, then the list -
   were nearly touching, so the chips read as part of the heading and the first
   row read as part of the chips. Charlie, 26/08/2026: slight spacing between
   them. The gap BELOW the chips is the larger of the two because the first row
   carries a border-top, and a rule sitting tight under a row of pills looks like
   an underline on the pills rather than the start of a list. */
.chips{display:flex;flex-wrap:wrap;gap:0.45rem;margin:0.85rem 0 1.35rem;
  font-family:-apple-system,system-ui,sans-serif;}
.chip{cursor:pointer;font:inherit;font-size:0.68rem;letter-spacing:0.08em;
  text-transform:uppercase;padding:0.32rem 0.7rem;border:1px solid var(--rule);
  border-radius:1rem;background:transparent;color:var(--muted);}
.chip:hover{border-color:var(--accent);color:var(--accent);}
.chip.is-active{background:var(--accent);border-color:var(--accent);color:var(--bg);}
ul.disp{list-style:none;margin:0;padding:0;}
ul.disp li.is-hidden{display:none;}
/* Year on a rail, ordered by distance from now - this list does the job the
   futures-visited bar used to, without a second copy of every date. */
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
/* One locator thumbnail per row, drawn from the same seed as that dispatch's
   own chart, so the archive reads as a set of places rather than a list. */
.disp .rmap{flex:0 0 46px;align-self:center;line-height:0;}
.disp .rmap .thumb{display:block;width:46px;height:46px;opacity:0.72;}
.disp li:hover .rmap .thumb{opacity:1;}
.disp a{color:var(--fg);text-decoration:none;font-size:1.05rem;font-weight:700;
  border-bottom:1px solid var(--accent);}
.disp .dom{font-family:-apple-system,system-ui,sans-serif;font-size:0.7rem;
  color:var(--muted);margin-top:0.25rem;}
@media (max-width:30rem){
  /* Rail and body stack, but the thumbnail stays beside them rather than
     dropping to a third row of its own. */
  ul.disp li{display:grid;gap:0.3rem 0.8rem;align-items:center;
    grid-template-columns:1fr 54px;
    grid-template-areas:"rail map" "body map";}
  .disp .rail{grid-area:rail;text-align:left;}
  .disp .rail::after{display:none;}
  .disp .rbody{grid-area:body;border-left:none;padding-left:0;}
  /* Bigger on a phone than on the desktop, which looks wrong written down and
     is right on the page: the mobile row is a two-column grid where the map has
     its own full-height column beside two stacked text lines, so there is more
     room for it here than in the desktop flex row. Charlie, 19/08/2026. */
  .disp .rmap{grid-area:map;}
  .disp .rmap .thumb{width:54px;height:54px;}
}
a.home{font-family:-apple-system,system-ui,sans-serif;color:var(--accent);
  text-decoration:none;border-bottom:1px solid var(--accent);font-size:0.85rem;}
footer{margin-top:3rem;font-family:-apple-system,system-ui,sans-serif;
  font-size:0.78rem;color:var(--muted);}
"""


#: The masthead flag. archive.html is at the root, so the path needs no prefix
#: (render.py's permalinks do). Declared here rather than shared with render.py
#: because that module builds it per page depth.
_FONT_FACE = ("<style>@font-face{font-family:'Aftertimes Flag';"
              "src:url('assets/fonts/unifrakturcook-700.woff2') format('woff2');"
              "font-weight:700;font-display:swap;}</style>")


_FILTER_JS = """
(function(){
  var chips=document.querySelectorAll('.chip');
  var items=document.querySelectorAll('ul.disp li');
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


def render_archive(records: list[dict], meta: dict) -> str:
    recs = sorted(records, key=lambda r: r["run_date"], reverse=True)
    # The LIST IS THE TIMELINE: ordered by how far out each dispatch is set, with
    # the year on a rail. Previously it repeated every dateline that the bar above
    # had just shown, in publication order.
    by_distance = sorted(
        records, key=lambda r: r["dispatch"]["dateline"]["years_from_now"])
    deep_max = int(meta.get("locator_deep_max") or 4000)
    rows = ""
    for r in by_distance:
        d = r["dispatch"]
        dl = d["dateline"]
        place = html.escape(hyphenate(normalise_place(dl.get("place"))))
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
                 f'{dom}</div></div>'
                 f'<div class="rmap">{locator.thumbnail(dl, deep_max)}</div>'
                 f'</li>')
    chips = _domain_chips(recs)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f4efe3">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="icon" type="image/png" sizes="192x192" href="assets/favicon-192.png">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
<title>Archive - {html.escape(meta['site_name'])}</title>
<style>{_CSS}</style>
{_FONT_FACE}
{BEACON}
</head>
<body>
  <div class="wrap">
    <header class="masthead">
      <div class="name">{html.escape(meta['site_name'])}</div>
      <div class="tag">{html.escape(hyphenate(meta['tagline']))}</div>
    </header>
    <p><a class="home" href="index.html">&larr; Today's dispatch</a></p>
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
    # locator_deep_max must match render.py's, or a row's thumbnail would put
    # the same dispatch at a different radius from its own page.
    meta = {"site_name": settings["site"]["name"],
            "tagline": settings["site"]["tagline"],
            "locator_deep_max": settings["dates"]["bands"]["deep"][1]}
    out = render_archive(records, meta)
    with open(rel("archive.html"), "w", encoding="utf-8") as fh:
        fh.write(out)
    return rel("archive.html")


if __name__ == "__main__":
    print(f"Wrote {build()}")
