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
        "site_name": "The Aftertimes", "signup_form_url": "",
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


def test_render_escapes_html():
    d = {**DISPATCH, "headline": "Robots <script>alert(1)</script> revolt"}
    html = render_dispatch(d, META)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_no_dashes_in_output():
    html = render_dispatch(DISPATCH, META)
    assert "—" not in html and "–" not in html


def test_stale_banner_toggles():
    assert "Showing yesterday" not in render_dispatch(DISPATCH, META, stale=False)
    assert "Showing yesterday" in render_dispatch(DISPATCH, META, stale=True)


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
    assert "—" not in html
