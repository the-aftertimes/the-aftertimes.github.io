"""Locator chart: determinism, place-scrub agreement, distance scaling, output."""
import locator


def _dl(place, year, yfn):
    return {"place": place, "year": year, "years_from_now": yfn, "month": 9, "day": 4}


def test_deterministic_same_dispatch_same_svg():
    dl = _dl("New Carthage", 4200, 2174)
    for v in ("plate", "survey", "rings"):
        assert locator.render_locator_svg(dl, 40000, v) == \
            locator.render_locator_svg(dl, 40000, v)


def test_seed_uses_scrubbed_place_matching_render():
    # A trailing (NNNN) disambiguation suffix is scrubbed (as render.py does),
    # so it must not change the drawn chart.
    a = locator.render_locator_svg(_dl("New Carthage", 4200, 2174), 40000)
    b = locator.render_locator_svg(_dl("New Carthage (2087)", 4200, 2174), 40000)
    assert a == b
    assert "New Carthage" in a and "(2087)" not in a


def test_distance_scales_with_years():
    near = locator._target_radius(8, 40000)
    mid = locator._target_radius(2000, 40000)
    deep = locator._target_radius(38000, 40000)
    assert near < mid < deep
    assert near >= locator._R_MIN and deep <= locator._R_MAX + 0.01


def test_deep_max_clamps_radius():
    # A dispatch further out than the configured deep max is clamped, not blown out.
    beyond = locator._target_radius(999999, 40000)
    assert beyond <= locator._R_MAX + 0.01


def test_unknown_variant_falls_back_to_plate():
    dl = _dl("Somewhere", 3000, 974)
    assert locator.render_locator_svg(dl, 40000, "nope") == \
        locator.render_locator_svg(dl, 40000, "plate")


def test_output_is_well_formed_and_dash_clean():
    for v in ("plate", "survey", "rings"):
        s = locator.render_locator_svg(_dl("Port X", 5000, 2974), 40000, v)
        assert s.startswith("<svg") and s.endswith("</svg>")
        assert "<title>" in s and "aria-label" in s
        assert chr(0x2014) not in s and chr(0x2013) not in s


# --- the locator ceiling has ONE owner --------------------------------------
# 26/08/2026: six permalinks drew their dispatch at a different radius from its
# own archive row, because archive.py computed the ceiling live for every row
# while render.py took whatever was stored on the record at filing time. Their
# fallback defaults disagreed too - 40000 against 4000 - which is why the one
# record with no stored ceiling was furthest wrong.

def test_re_rendering_a_stale_record_picks_up_todays_ceiling():
    """A record filed under an old config must not reproduce the old page."""
    from common import locator_ceiling, load_settings, refresh_render_meta
    settings = load_settings()
    meta = {"locator_deep_max": 40000}
    refresh_render_meta(meta, settings)
    assert meta["locator_deep_max"] == locator_ceiling(settings)
    assert meta["locator_deep_max"] != 40000


def test_a_record_with_no_ceiling_gets_one():
    from common import locator_ceiling, load_settings, refresh_render_meta
    settings = load_settings()
    meta = {}
    refresh_render_meta(meta, settings)
    assert meta["locator_deep_max"] == locator_ceiling(settings)


def test_only_the_ceiling_is_refreshed():
    """It is a presentation field. A re-render must not quietly restamp the
    dispatch's own identity."""
    from common import load_settings, refresh_render_meta
    meta = {"locator_deep_max": 40000, "run_time": "2026-07-29T20:00:00+00:00",
            "edition": 1, "site_name": "The Aftertimes"}
    refresh_render_meta(meta, load_settings())
    assert meta["run_time"] == "2026-07-29T20:00:00+00:00"
    assert meta["edition"] == 1 and meta["site_name"] == "The Aftertimes"


def test_nothing_reads_the_setting_directly_any_more():
    """The whole point is one owner. Five call sites used to read it and they
    disagreed; a sixth would reintroduce the divergence silently."""
    import glob, os, re
    offenders = []
    for path in glob.glob(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "*.py")):
        if os.path.basename(path) == "common.py":
            continue
        src = open(path, encoding="utf-8").read()
        if re.search(r'\["bands"\]\s*\[\s*"deep"\s*\]\s*\[\s*1\s*\]', src):
            offenders.append(os.path.basename(path))
    assert not offenders, f"read locator_ceiling() instead: {offenders}"
