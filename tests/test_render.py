from render import render_dispatch


DISPATCH = {
    "headline": "Floating Capital Sues the Sea for Breach of Contract",
    "body": "The North Atlantic declined to comment. Lawyers for the ocean called it terrestrial.",
    "dateline": {"place": "Port Kobenhavn-2", "year": 2391, "month": 9, "day": 4,
                 "years_from_now": 365},
    "wire": {"name": "Nordwire", "gloss": "pan-Baltic newswire, est. 2334"},
    "domain": "law",
    "glossary": [{"term": "Tide & Wren", "gloss": "non-human law firm"}],
    "premise": "a city sues the sea",
}
META = {"run_time": "2026-07-28T20:00:00+00:00", "timezone": "Australia/Sydney",
        "tagline": "Dispatches from years that have not yet happened",
        "site_name": "The Aftertimes", "signup_form_url": "", "edition": 1,
        "base_url": "https://the-aftertimes.github.io"}


def test_render_contains_core_elements():
    html = render_dispatch(DISPATCH, META)
    assert "The Aftertimes" in html
    assert "Floating Capital Sues the Sea" in html
    assert "September" in html and "2,391".replace(",", "") in html.replace(",", "")
    assert "4 September 2,391" in html or "4 September 2391" in html
    assert "years from today" not in html
    assert "Filed by" not in html
    assert "Tide" not in html  # glossary removed from the page
    assert "fiction" in html.lower()          # framing footer present
    assert "VOL." in html and "No. 1" in html  # edition line renders


def test_render_escapes_html():
    d = {**DISPATCH, "headline": "Robots <script>alert(1)</script> revolt"}
    html = render_dispatch(d, META)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_no_dashes_in_output():
    html = render_dispatch(DISPATCH, META)
    assert "\u2014" not in html and "\u2013" not in html


def test_stale_banner_toggles():
    assert "Showing yesterday" not in render_dispatch(DISPATCH, META, stale=False)
    assert "Showing yesterday" in render_dispatch(DISPATCH, META, stale=True)


def test_font_path_relative_for_permalink():
    home = render_dispatch(DISPATCH, META)
    perma = render_dispatch(DISPATCH, META, is_permalink=True)
    assert "url('assets/fonts/unifrakturcook-700.woff2')" in home
    assert "url('../assets/fonts/unifrakturcook-700.woff2')" in perma


def test_dateline_strips_trailing_year_parenthetical():
    d = {**DISPATCH, "dateline": {**DISPATCH["dateline"],
                                   "place": "Gills Crater, Ganymede (2287)"}}
    html = render_dispatch(d, META)
    assert "(2287)" not in html
    assert "Gills Crater, Ganymede" in html
    # input dict not mutated
    assert d["dateline"]["place"] == "Gills Crater, Ganymede (2287)"


def test_metadata_always_visible_no_details_toggle():
    html = render_dispatch(DISPATCH, META)
    assert "<details" not in html
    assert "<summary" not in html
    assert 'class="meta"' in html
    assert "Dispatch metadata" in html


def test_engraving_has_no_figcaption():
    import re
    d = {**DISPATCH, "image": "assets/engravings/x.png"}
    html = render_dispatch(d, META)
    # The engraving figure itself carries no caption (flux can stamp garbled
    # text); the locator figure legitimately has one, so scope the check.
    engraving = re.search(r'<figure class="engraving">.*?</figure>', html, re.S).group(0)
    assert "figcaption" not in engraving
    assert "An imagined engraving" not in html


def test_domain_rendered_title_case():
    html = render_dispatch(DISPATCH, META)  # DISPATCH domain is "law"
    assert "Domain: <b>Law</b>" in html
    assert "Domain: <b>law</b>" not in html


def test_image_slot_optional():
    assert "figure class=\"engraving\"" not in render_dispatch(DISPATCH, META)
    d = {**DISPATCH, "image": "assets/engravings/x.png"}
    home = render_dispatch(d, META)
    assert 'figure class="engraving"' in home and "assets/engravings/x.png" in home
    perma = render_dispatch(d, META, is_permalink=True)
    assert "../assets/engravings/x.png" in perma


from archive import render_archive


def test_archive_lists_dispatches_by_distance_not_publication_date():
    """The list IS the timeline now (06/08/2026), so it is ordered by how far out
    each dispatch is set, NOT newest-published-first as it was before. Note the
    nearer future here was published LATER, so the two orderings disagree and the
    assertion is meaningful."""
    records = [
        {"run_date": "2026-07-27", "dispatch": {
            "headline": "Distant story", "domain": "law",
            "dateline": {"place": "Mars", "year": 2400, "month": 2, "day": 2,
                         "years_from_now": 374}}},
        {"run_date": "2026-07-28", "dispatch": {
            "headline": "Nearer story", "domain": "sport",
            "dateline": {"place": "Luna", "year": 2200, "month": 1, "day": 1,
                         "years_from_now": 174}}},
    ]
    meta = {"site_name": "The Aftertimes",
            "tagline": "Dispatches from years that have not yet happened"}
    html = render_archive(records, meta)
    assert html.index("Nearer story") < html.index("Distant story")
    assert "d/2026-07-28.html" in html
    assert "174 yrs" in html and "374 yrs" in html   # the year rail
    assert "\u2014" not in html


from email_render import build_email


def test_build_email_has_subject_and_body():
    dispatch = {
        "headline": "Floating Capital Sues the Sea",
        "body": "One paragraph.\nAnother paragraph.",
        "dateline": {"place": "Port Kobenhavn-2", "year": 2391, "month": 9, "day": 4,
                     "years_from_now": 365},
        "wire": {"name": "Nordwire", "gloss": ""}, "domain": "law", "glossary": [],
    }
    meta = {"site_name": "The Aftertimes", "base_url": "https://the-aftertimes.github.io"}
    subject, body = build_email(dispatch, meta)
    assert "Floating Capital" in subject
    assert "2391" in body or "2,391" in body
    assert "Filed by" not in body
    assert "\u2014" not in body
    assert "the-aftertimes.github.io" in body


def test_tab_title_leads_with_the_masthead_and_og_title_does_not():
    """A browser tab shows roughly 20 characters. Headline-first truncated to
    "Mantle Drillers Prom..." with nothing identifying the site, and because the
    headline changes daily the tab was never learnable. A shared link wants the
    opposite - og:title leads with the headline, which is the interesting part.
    The two must not be collapsed back into one string."""
    import re
    html_out = render_dispatch(DISPATCH, META)
    tab = re.search(r"<title>([^<]*)", html_out).group(1)
    og = re.search(r'og:title" content="([^"]*)', html_out).group(1)
    assert tab.startswith("The Aftertimes"), tab
    assert not og.startswith("The Aftertimes"), og
    assert og.endswith("The Aftertimes"), og


def test_end_links_share_one_row_at_the_foot():
    """Charlie 17/08/2026: put Other Projects in line with Browse the Archive.
    Nothing may sit above the masthead - this is a front page, and a link there
    competes with it."""
    out = render_dispatch(DISPATCH, META)
    row = out.split('<div class="endlinks">')[1].split("</div>")[0]
    assert "Other projects" in row and "Browse the archive" in row
    assert 'class="hublink"' not in out
    body = out.split("<body>")[1]
    assert body.index("masthead") < body.index("Other projects")


def test_permalink_end_links_pair_with_the_back_links():
    """The permalink's row carries 'Today's dispatch / Archive' instead, and must
    still hold the hub link - it is the only way off a permalink to the hub."""
    out = render_dispatch(DISPATCH, META, is_permalink=True)
    row = out.split('<div class="endlinks">')[1].split("</div>")[0]
    assert "Other projects" in row and "Archive" in row


def test_a_page_with_no_card_does_not_promise_a_large_image():
    """THE BUG, 29/08/2026. Every page declared `twitter:card=summary_large_image`
    and shipped no `og:image` from launch. That is worse than carrying no card
    tags at all: the tag tells X and Slack to reserve a large image slot, and they
    render it empty, so every share of the paper looked broken. It went unnoticed
    for months because a broken card is invisible from the site itself - it only
    appears in somebody else's timeline.

    A dispatch with no engraving is a real state (it is what happens when the
    Cloudflare allocation is spent), so the honest tag there is plain `summary`."""
    html = render_dispatch({**DISPATCH, "image": None}, META)
    assert 'content="summary"' in html
    assert "summary_large_image" not in html
    assert "og:image" not in html


def test_the_card_tags_are_absolute_and_complete_when_one_exists(tmp_path, monkeypatch):
    """og:image must be ABSOLUTE - a relative path is silently ignored by every
    platform, which looks exactly like having no card at all and is exactly as
    hard to notice. Width and height are declared so the platform reserves the
    right shape before the image loads."""
    import os
    import render as render_mod

    monkeypatch.setattr(render_mod.os.path, "exists", lambda p: True)
    html = render_dispatch({**DISPATCH, "image": "assets/img/2026-08-27.jpg"}, META)

    base = META["base_url"]
    assert f'content="{base}/assets/card/2026-08-27.jpg"' in html
    assert 'content="summary_large_image"' in html
    assert 'og:image:width" content="1200"' in html
    assert 'og:image:height" content="630"' in html
    assert f'<link rel="canonical" href="{base}/"' in html
    assert "og:image:alt" in html


def test_a_permalink_points_its_canonical_at_the_dated_page():
    """The front page and the dated permalink render the same dispatch. If both
    claimed the same canonical URL, the archive copy would tell crawlers it was
    the homepage - and the homepage changes daily."""
    import render as render_mod

    real = render_mod.os.path.exists
    render_mod.os.path.exists = lambda p: True
    try:
        html = render_dispatch({**DISPATCH, "image": "assets/img/2026-08-27.jpg"},
                               META, is_permalink=True)
    finally:
        render_mod.os.path.exists = real
    assert f'{META["base_url"]}/d/2026-08-27.html' in html
