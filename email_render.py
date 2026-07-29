"""Daily email body for Brevo. Light bone theme, table + inline styles so it
survives Outlook. Kept close to the One Story email but broadsheet-styled.
No em/en dashes. Delivery is a separate step, activated later."""
from __future__ import annotations

import html

from common import hyphenate
from dates import format_date, format_dateline


def build_email(dispatch: dict, meta: dict) -> tuple[str, str]:
    dl = dispatch["dateline"]
    subject = hyphenate(f"The Aftertimes: {dispatch['headline']}")
    headline = html.escape(hyphenate(dispatch["headline"]))
    dateline = html.escape(hyphenate(format_dateline(dl)))
    date_txt = html.escape(hyphenate(format_date(dl)))
    paras = "".join(
        f'<p style="margin:0 0 14px;font-size:16px;line-height:1.55;color:#1a1611;">'
        f'{html.escape(hyphenate(p.strip()))}</p>'
        for p in dispatch["body"].split("\n") if p.strip())
    url = html.escape(meta["base_url"], quote=True)
    body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light only"></head>
<body style="margin:0;padding:0;background:#e7e1d3;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#e7e1d3">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" bgcolor="#f4efe3"
  style="max-width:600px;background:#f4efe3;border:1px solid #cdc3ad;">
<tr><td style="padding:28px 32px;font-family:Georgia,serif;">
  <div style="text-align:center;border-bottom:3px double #1a1611;padding-bottom:10px;margin-bottom:20px;">
    <div style="font-size:30px;font-weight:700;color:#1a1611;">The Aftertimes</div>
    <div style="font-size:10px;letter-spacing:0.24em;text-transform:uppercase;color:#6b5f4d;margin-top:6px;font-family:Arial,sans-serif;">Dispatches from years that have not yet happened</div>
  </div>
  <div style="font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#7a2b2b;margin-bottom:10px;font-family:Arial,sans-serif;">{dateline}</div>
  <h1 style="font-size:26px;line-height:1.15;color:#1a1611;margin:0 0 16px;">{headline}</h1>
  {paras}
  <p style="font-size:13px;font-style:italic;color:#6b5f4d;margin:6px 0 20px;">{date_txt}</p>
  <p style="margin:0 0 20px;"><a href="{url}" style="color:#7a2b2b;font-weight:700;font-family:Arial,sans-serif;font-size:14px;">Read it on the site and browse the archive &rarr;</a></p>
  <p style="font-size:12px;font-style:italic;color:#6b5f4d;border-top:1px solid #cdc3ad;padding-top:14px;margin:0;font-family:Arial,sans-serif;">Every dispatch is fiction, written by a machine each morning. None of it has happened. Yet.</p>
</td></tr></table>
</td></tr></table>
</body></html>"""
    return subject, body


if __name__ == "__main__":
    import sys
    from common import read_json
    rec = read_json(f"data/dispatches/{sys.argv[1]}.json")
    subj, html_body = build_email(rec["dispatch"], rec["meta"])
    print(subj)
    with open("email.html", "w", encoding="utf-8") as fh:
        fh.write(html_body)
