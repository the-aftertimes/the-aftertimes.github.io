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
