"""Wiring of the learning loop into run.py: build_avoid_block must never raise."""
import run as run_mod

CFG_ON = {"enabled": True, "window": 30, "min_count": 3, "avoid_char_cap": 1200,
          "exemplar_cap": 24, "proposals_weekday": 0}


def _recs(n, phrase):
    return [{"run_date": f"2026-08-{i + 1:02d}",
             "dispatch": {"headline": "H", "body": f"{phrase} number {i}.",
                          "domain": "law",
                          "dateline": {"place": "P", "year": 2500,
                                       "years_from_now": 474}}}
            for i in range(n)]


def test_build_avoid_block_finds_a_repeated_phrase():
    block = run_mod.build_avoid_block(_recs(5, "the council sealed the shaft"),
                                      CFG_ON)
    assert "council sealed" in block


def test_build_avoid_block_is_empty_when_disabled():
    recs = _recs(5, "the council sealed the shaft")
    assert run_mod.build_avoid_block(recs, dict(CFG_ON, enabled=False)) == ""


def test_build_avoid_block_never_raises_on_bad_input():
    """A trend-spotting fault must never take the daily publish down with it."""
    assert run_mod.build_avoid_block([{"broken": True}], CFG_ON) == ""
