"""Archive page: the dispatch list, and what has been deliberately removed."""
import archive


def _dl(y, yfn):
    return {"year": y, "years_from_now": yfn, "month": 9, "day": 4, "place": "Port X"}


def _recs(domains):
    return [{"run_date": f"2026-07-{29 - i:02d}",
             "dispatch": {"headline": f"H{i}", "domain": dom,
                          "dateline": _dl(2200 + i * 400, 174 + i * 400)}}
            for i, dom in enumerate(domains)]


META = {"site_name": "The Aftertimes", "tagline": "x"}
def test_the_futures_visited_bar_is_gone():
    """Charlie cut it 18/08/2026 after two reworks. It duplicated the year rail
    the list already carries, so the filter has only one set of items to hide."""
    out = archive.render_archive(_recs(["crime", "space law"]), META)
    for dead in ("tmark", "tyear", "taxis", "Futures visited", "timeline"):
        assert dead not in out, dead
    # the filter script that used to hide marks alongside rows is gone too - see
    # test_the_domain_filter_is_gone


def test_archive_masthead_matches_the_front_page():
    """Same paper, same flag. It was plain Georgia here and blackletter there."""
    import render
    out = archive.render_archive(_recs(["crime"]), META)
    assert "'Aftertimes Flag','UnifrakturCook',serif" in out
    assert "unifrakturcook-700.woff2" in out
    for rule in ("font-size:clamp(2.7rem,10vw,4.6rem)",):
        assert rule in out and rule in render._CSS


def test_default_is_all_visible_when_js_off():
    # No element ships with the is-hidden class, so the page works without JS.
    out = archive.render_archive(_recs(["crime", "space law"]), META)
    import re
    assert not re.findall(r'class="[^"]*is-hidden[^"]*"', out)


def test_no_em_or_en_dashes():
    out = archive.render_archive(_recs(["crime", "space law"]), META)
    assert chr(0x2014) not in out and chr(0x2013) not in out


def test_the_domain_filter_is_gone():
    """Removed 26/08/2026. 17 of 22 chips returned exactly one dispatch and the
    largest returned three, so it was not a filter - it was the article list
    again, in pill form, costing 457px above the first story on a phone. The
    domain still prints on every row, so nothing is lost. Charlie delegated the
    call; this guard is here because the obvious "improvement" is to rebuild it."""
    out = archive.render_archive(_recs(["crime", "space law", "crime"]), META)
    for dead in ("chip", "data-filter", "data-domain", "is-hidden",
                 "querySelectorAll"):
        assert dead not in out, dead
    # the analytics beacon is a <script> and stays, so this checks for the
    # FILTER script rather than for scripts in general
    assert "beacon.min.js" in out
    # the domain must still be readable on each row - that is what makes the
    # filter redundant rather than merely absent
    assert "Crime" in out and "Space Law" in out


def test_the_heading_has_air_above_the_list():
    """Charlie asked twice, the second time with a screenshot. The first row
    carries a border-top, so a rule close under a small uppercase label reads as
    an underline on the label rather than the top of a list."""
    out = archive.render_archive(_recs(["crime"]), META)
    h2_rule = out.split("h2{")[1].split("}")[0]
    assert "margin:2.2rem 0 1.6rem" in h2_rule
