"""Stage 4 - render. Turn a dispatch record into the bone-broadsheet HTML.
All model/feed text is HTML-escaped and hyphenated. Pure function; run.py owns IO."""
from __future__ import annotations

import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import locator
from common import hyphenate
from dates import format_date, format_dateline

_CSS = """
:root{--bg:#f4efe3;--fg:#1a1611;--muted:#6b5f4d;--accent:#7a2b2b;--rule:#cdc3ad;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:Georgia,'Times New Roman',serif;line-height:1.55;
  -webkit-font-smoothing:antialiased;}
.wrap{max-width:52rem;margin:0 auto;padding:clamp(2rem,7vw,4.5rem) 1.5rem 4rem;
  min-height:100vh;display:flex;flex-direction:column;}
.masthead{text-align:center;border-bottom:3px double var(--fg);padding-bottom:0.9rem;
  margin-bottom:2rem;}
.masthead .edition{font-family:-apple-system,system-ui,sans-serif;font-size:0.62rem;
  letter-spacing:0.22em;text-transform:uppercase;color:var(--muted);margin-bottom:0.6rem;}
.masthead .name{font-family:'Aftertimes Flag','UnifrakturCook',serif;font-weight:700;
  font-size:clamp(2.7rem,10vw,4.6rem);line-height:1;letter-spacing:0.01em;}
.masthead .tag{font-family:-apple-system,system-ui,sans-serif;font-size:0.62rem;
  letter-spacing:0.3em;text-transform:uppercase;color:var(--muted);margin-top:0.7rem;}
.dateline{font-family:-apple-system,system-ui,sans-serif;font-size:0.92rem;
  font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:var(--accent);
  margin:0 0 0.8rem;}
.engraving{margin:1.2rem 0 1.8rem;}
.engraving img{width:100%;height:auto;display:block;mix-blend-mode:multiply;}
.meta-locrow{display:flex;align-items:stretch;margin-top:0.7rem;}
.meta-loctext{flex:1 1 0;text-align:right;padding-right:1.5rem;
  display:flex;flex-direction:column;justify-content:center;}
figure.locator{flex:1 1 0;margin:0;text-align:left;
  border-left:1px solid var(--rule);padding-left:1.5rem;}
figure.locator svg{width:230px;max-width:100%;height:auto;mix-blend-mode:multiply;}
.meta-location{font-family:Georgia,'Times New Roman',serif;font-size:1.6rem;
  font-weight:700;color:var(--fg);line-height:1.1;margin-bottom:0.2rem;}
.meta-far{font-size:0.66rem;letter-spacing:0.2em;text-transform:uppercase;
  color:var(--muted);margin-bottom:0.9rem;}
@media (max-width:36rem){
  .meta-locrow{flex-direction:column;}
  .meta-loctext{text-align:center;padding-right:0;}
  figure.locator{border-left:none;padding-left:0;margin-top:1.1rem;}
}
h1{font-size:clamp(1.9rem,6vw,2.5rem);line-height:1.12;font-weight:700;
  margin:0 0 1.1rem;letter-spacing:-0.01em;}
.body p{font-size:clamp(1.02rem,2.6vw,1.16rem);margin:0 0 1rem;}
.meta{font-family:-apple-system,system-ui,sans-serif;margin-top:1.8rem;}
.meta-title{margin:0;color:var(--accent);font-weight:600;font-size:0.72rem;
  letter-spacing:0.16em;text-transform:uppercase;padding-top:0.6rem;
  border-top:1px solid var(--rule);}
.meta-body{color:var(--muted);font-size:0.9rem;padding-top:0.6rem;}
.meta-facts{line-height:1.6;}
.meta-facts b{color:var(--fg);}
.stale{font-family:-apple-system,system-ui,sans-serif;font-size:0.85rem;
  background:var(--accent);color:var(--bg);padding:0.6rem 1rem;border-radius:0.3rem;
  margin-bottom:1.8rem;}
.signup{margin:2.5rem 0 0;padding:1.5rem 0 0;border-top:1px solid var(--rule);
  font-family:-apple-system,system-ui,sans-serif;}
.signup-lead{margin:0 0 0.9rem;color:var(--fg);font-weight:600;}
.signup-form{display:flex;flex-wrap:wrap;gap:0.5rem;}
.signup-form input{flex:1 1 12rem;min-width:0;padding:0.6rem 0.8rem;font-size:0.95rem;
  color:var(--fg);background:#fff;border:1px solid var(--rule);border-radius:0.3rem;
  font-family:inherit;}
.signup-form button{padding:0.6rem 1.2rem;font-weight:600;cursor:pointer;
  color:var(--bg);background:var(--accent);border:none;border-radius:0.3rem;
  font-family:inherit;}
.signup-note{margin:0.7rem 0 0;color:var(--muted);font-size:0.78rem;}
footer{padding-top:2rem;font-family:-apple-system,system-ui,sans-serif;
  font-size:0.78rem;color:var(--muted);}
footer .fiction{font-style:italic;margin:0 0 0.6rem;}
footer .byline{margin:0.7rem 0 0;}
a.arc{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent);}
"""


def _fmt_local(iso: str, tzname: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone(ZoneInfo(tzname))
    return f"{dt.strftime('%d/%m/%Y %H:%M')} {dt.tzname() or ''}".strip()


def _fmt_publish(iso: str, tzname: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone(ZoneInfo(tzname))
    return dt.strftime("%a %d %B %Y")


def _roman(n: int) -> str:
    if n <= 0 or n > 3999:
        return str(n)  # roman is absurd for deep-future years; fall back to arabic
    table = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
             (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = []
    for v, s in table:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


_MINOR = {"a", "an", "and", "the", "of", "to", "in", "on", "for", "at", "by", "or", "with"}


def _headline_case(s: str) -> str:
    words = s.split()
    out = []
    for i, w in enumerate(words):
        out.append(w if (w.lower() in _MINOR and i != 0) else w[:1].upper() + w[1:])
    return " ".join(out)


def _signup(form_url: str) -> str:
    if not form_url:
        return ""
    action = html.escape(form_url, quote=True)
    return f"""<section class="signup">
  <p class="signup-lead">Get one dispatch from the future in your inbox each morning.</p>
  <form action="{action}" method="post" target="at-sink" class="signup-form"
        onsubmit="return atSignup(this)">
    <input type="email" name="EMAIL" placeholder="you@example.com"
           aria-label="Email address" required>
    <input type="text" name="email_address_check" value="" tabindex="-1"
           autocomplete="off" aria-hidden="true" style="position:absolute;left:-5000px;">
    <input type="hidden" name="locale" value="en">
    <input type="hidden" name="html_type" value="simple">
    <button type="submit">Subscribe</button>
  </form>
  <p class="signup-note" id="at-note">One email a day. No tracking. Unsubscribe anytime.</p>
  <iframe name="at-sink" title="subscription" aria-hidden="true" tabindex="-1"
          style="position:absolute;width:0;height:0;border:0;"></iframe>
  <script>function atSignup(f){{setTimeout(function(){{f.style.display='none';
    var n=document.getElementById('at-note');if(n){{n.textContent=
    "Thanks - your first dispatch arrives tomorrow morning.";n.style.color='var(--accent)';}}}},150);
    return true;}}</script>
</section>"""


def render_dispatch(dispatch: dict, meta: dict, stale: bool = False,
                    is_permalink: bool = False) -> str:
    dl = dict(dispatch["dateline"])
    dl["place"] = re.sub(r"\s*\(\d{2,}\)\s*$", "", (dl.get("place") or ""))
    headline = html.escape(hyphenate(dispatch["headline"]))
    dateline_txt = html.escape(hyphenate(format_dateline(dl)))
    date_txt = html.escape(hyphenate(format_date(dl)))
    body_paras = "".join(
        f"<p>{html.escape(hyphenate(p.strip()))}</p>"
        for p in dispatch["body"].split("\n") if p.strip())
    domain = html.escape(hyphenate(_headline_case(dispatch["domain"])))
    stamp = _fmt_local(meta["run_time"], meta["timezone"])
    stale_banner = ("<div class='stale'>Showing yesterday's dispatch - today's "
                    "edition did not file.</div>" if stale else "")
    signup = "" if is_permalink else _signup(meta.get("signup_form_url", ""))
    archive_link = ('<p><a class="arc" href="archive.html">Browse the archive '
                    '&rarr;</a></p>') if not is_permalink else (
                    '<p><a class="arc" href="../index.html">Today\'s dispatch '
                    '&rarr;</a> &middot; <a class="arc" href="../archive.html">Archive</a></p>')
    title = html.escape(hyphenate(f"{dispatch['headline']} - {meta['site_name']}"))
    desc = html.escape("Fiction. A daily news dispatch from a random date in the future.")
    asset_prefix = "../" if is_permalink else ""
    font_face = (
        f"<style>@font-face{{font-family:'Aftertimes Flag';"
        f"src:url('{asset_prefix}assets/fonts/unifrakturcook-700.woff2') "
        f"format('woff2');font-weight:700;font-display:swap;}}</style>")
    edition = meta.get("edition", 1)
    publish_date = html.escape(_fmt_publish(meta["run_time"], meta["timezone"]))
    edition_line = (f'<div class="edition">VOL. {_roman(dl["year"])} &middot; '
                    f'No. {html.escape(str(edition))} &middot; {publish_date}</div>')
    image = dispatch.get("image")
    figure = ""
    if image:
        img_src = f"{asset_prefix}{html.escape(str(image), quote=True)}"
        figure = (f'<figure class="engraving"><img src="{img_src}" alt="{headline}" '
                  f'loading="lazy"></figure>')
    # Locator chart: deterministic, inline SVG, keyed off the already-scrubbed
    # place so label and seed agree. Guarded - a chart error must never blank
    # the page.
    # The location itself is named in the Dispatch metadata panel below (loc_meta);
    # here we render just the chart, which leads into that panel.
    locator_fig = ""
    loc_meta = ""
    try:
        svg = locator.render_locator_svg(
            dl, int(meta.get("locator_deep_max", 40000)), "plate")
        loc_place, loc_far = locator.caption_text(dl)
        locator_fig = f'<figure class="locator">{svg}</figure>'
        loc_meta = (f'<div class="meta-location">{html.escape(hyphenate(loc_place))}</div>'
                    f'<div class="meta-far">{html.escape(loc_far)}</div>')
    except Exception:  # noqa: BLE001 - decorative; never block the dispatch
        locator_fig = ""
        loc_meta = ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f4efe3">
<link rel="icon" type="image/svg+xml" href="{'../' if is_permalink else ''}assets/favicon.svg">
<title>{title}</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="{html.escape(meta['site_name'])}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta name="twitter:card" content="summary_large_image">
<style>{_CSS}</style>
{font_face}
</head>
<body>
  <div class="wrap">
    {stale_banner}
    <header class="masthead">
      {edition_line}
      <div class="name">{html.escape(meta['site_name'])}</div>
      <div class="tag">{html.escape(hyphenate(meta['tagline']))}</div>
    </header>
    <p class="dateline">{dateline_txt}</p>
    <h1>{headline}</h1>
    {figure}
    <div class="body">{body_paras}</div>
    <section class="meta">
      <h2 class="meta-title">Dispatch metadata</h2>
      <div class="meta-body">
        <div class="meta-locrow">
          <div class="meta-loctext">
            {loc_meta}
            <div class="meta-facts">
              <b>{date_txt}</b><br>Domain: <b>{domain}</b>
            </div>
          </div>
          {locator_fig}
        </div>
      </div>
    </section>
    {signup}
    {archive_link}
    <footer>
      <p class="fiction">Every dispatch is fiction, written by a machine each
        morning. None of it has happened. Yet.</p>
      Filed {stamp}.
      <p class="byline">A <a class="arc" href="https://charlie-tren.github.io/">Charlie
        Trenorden</a> project.</p>
    </footer>
  </div>
</body>
</html>
"""
