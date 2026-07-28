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
