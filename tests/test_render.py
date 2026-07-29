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
    assert "365 years from today" in html
    assert "Nordwire" in html
    assert "Tide &amp; Wren" in html or "Tide & Wren" in html
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
    d = {**DISPATCH, "image": "assets/engravings/x.png"}
    html = render_dispatch(d, META)
    assert "figcaption" not in html
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


def test_archive_lists_dispatches_newest_first():
    records = [
        {"run_date": "2026-07-27", "dispatch": {
            "headline": "Older story", "domain": "sport",
            "dateline": {"place": "Luna", "year": 2200, "month": 1, "day": 1,
                         "years_from_now": 174}}},
        {"run_date": "2026-07-28", "dispatch": {
            "headline": "Newer story", "domain": "law",
            "dateline": {"place": "Mars", "year": 2400, "month": 2, "day": 2,
                         "years_from_now": 374}}},
    ]
    meta = {"site_name": "The Aftertimes",
            "tagline": "Dispatches from years that have not yet happened"}
    html = render_archive(records, meta)
    assert html.index("Newer story") < html.index("Older story")
    assert "d/2026-07-28.html" in html
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
    assert "\u2014" not in body
    assert "the-aftertimes.github.io" in body
