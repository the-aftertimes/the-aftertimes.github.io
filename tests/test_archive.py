"""Archive page: domain-filter chips + data-domain tagging on list and timeline."""
import archive


def _dl(y, yfn):
    return {"year": y, "years_from_now": yfn, "month": 9, "day": 4, "place": "Port X"}


def _recs(domains):
    return [{"run_date": f"2026-07-{29 - i:02d}",
             "dispatch": {"headline": f"H{i}", "domain": dom,
                          "dateline": _dl(2200 + i * 400, 174 + i * 400)}}
            for i, dom in enumerate(domains)]


META = {"site_name": "The Aftertimes", "tagline": "x"}


def test_dom_key_normalises_case_and_space():
    assert archive._dom_key("  Space   Law ") == "space law"
    assert archive._dom_key("") == ""


def test_chips_dedupe_on_key_keep_first_label():
    # "Space Law" and "space law" collapse to one chip; label is first-seen title-case.
    out = archive.render_archive(_recs(["Space Law", "space law", "crime"]), META)
    assert out.count('data-filter="space law"') == 1
    assert ">Space Law<" in out
    assert 'data-filter="all"' in out and ">All<" in out


def test_list_and_timeline_carry_matching_domain_keys():
    out = archive.render_archive(_recs(["crime", "space law", "death and mourning"]), META)
    for key in ("crime", "space law", "death and mourning"):
        assert f'<li data-domain="{key}"' in out
        assert f'class="tmark" data-domain="{key}"' in out


def test_default_is_all_visible_when_js_off():
    # No element ships with the is-hidden class, so the page works without JS.
    out = archive.render_archive(_recs(["crime", "space law"]), META)
    import re
    assert not re.findall(r'class="[^"]*is-hidden[^"]*"', out)


def test_no_em_or_en_dashes():
    out = archive.render_archive(_recs(["crime", "space law"]), META)
    assert chr(0x2014) not in out and chr(0x2013) not in out
