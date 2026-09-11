"""The committee of comedians - ranking, Borda, and every degradation path."""
import pytest

import panel


def _members(n=3):
    return [{"name": f"m{i}", "persona": "p", "looks_for": "l"} for i in range(n)]


def test_borda_prefers_the_broadly_liked_over_the_divisive():
    """The whole reason to combine rankings rather than take a favourite: a
    candidate everyone puts second beats one that is first for a single member
    and last for the others. Right bias for a daily paper."""
    # 3 candidates. 0 is loved by one and hated by two; 1 is second for all.
    rankings = [[0, 1, 2], [2, 1, 0], [2, 1, 0]]
    pts = panel.borda(rankings, 3)
    assert pts[1] == 3.0
    assert pts[0] == 2.0
    assert max(range(3), key=lambda i: pts[i]) == 2


def test_parse_ranking_tolerates_a_preamble():
    assert panel.parse_ranking("Sure! My order: 3, 1, 4, 2", 4) == [2, 0, 3, 1]


def test_parse_ranking_drops_duplicates_and_out_of_range():
    assert panel.parse_ranking("2,2,9,1,0", 3) == [1, 0]


def test_parse_ranking_keeps_a_partial_answer():
    """A member who ranks two of four has still said something; discarding the
    reply would quietly turn a short panel back into a single judge."""
    assert panel.parse_ranking("3,1", 4) == [2, 0]


def test_parse_ranking_rejects_a_reply_with_no_numbers():
    with pytest.raises(ValueError):
        panel.parse_ranking("they are all equally good", 4)


def test_an_omitted_item_scores_as_last_not_as_missing():
    pts = panel.borda([[0]], 3)
    assert pts == [2.0, 0.0, 0.0]


def test_convene_returns_none_below_two_candidates():
    assert panel.convene(["only one"], _members(), {}) is None


def test_convene_returns_none_with_no_members():
    assert panel.convene(["a", "b"], [], {}) is None


def test_convene_survives_a_member_failing(monkeypatch):
    calls = []

    def flaky(prompt, settings, temperature, **kw):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("429")
        return "2,1"

    monkeypatch.setattr(panel.gemini, "generate", flaky)
    out = panel.convene(["a", "b"], _members(3), {"gemini": {}})
    assert out is not None
    assert out["voted"] == ["m0", "m2"]
    assert out["winner"] == 1


def test_convene_returns_none_when_every_member_fails(monkeypatch):
    """No votes must leave the caller's existing choice untouched, not crash and
    not pick arbitrarily."""
    monkeypatch.setattr(panel.gemini, "generate",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("429")))
    assert panel.convene(["a", "b"], _members(), {"gemini": {}}) is None


def test_prompt_demands_an_order_and_forbids_a_tie():
    p = panel.build_prompt(_members(1)[0], ["one", "two"], "story ideas")
    assert "Rank ALL 2" in p
    assert "equally good" in p
    assert "story ideas" in p


def test_settings_and_config_agree_on_the_members():
    from common import load_settings, load_yaml
    cfg = load_yaml("config/comedians.yaml")
    cap = load_settings()["panel"]["max_members"]
    for key in ("premise_panel", "draft_panel"):
        members = cfg[key]
        assert len(members) >= 2, "a panel of one is just a judge"
        assert len(members) <= cap
        assert len({m["name"] for m in members}) == len(members)
        for m in members:
            assert m["persona"].strip() and m["looks_for"].strip()
