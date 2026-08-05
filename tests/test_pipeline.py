"""Orchestration paths, with every model call mocked."""
import critic
import judge as judge_mod
import revise as revise_mod
import run as run_mod


def _dispatch(headline, body, score_hint=""):
    return {"headline": headline, "body": body + " " + score_hint,
            "scene": "a scene", "domain": "law",
            "dateline": {"place": "P", "year": 2600, "years_from_now": 574,
                         "month": 4, "day": 9},
            "glossary": [], "premise": "p"}


CFG = {
    "n_drafts": 3, "judge": True, "revise": True,
    "hard_reject": ["machine_phrases"],
    "weights": {"major": 0.25, "minor": 0.08},
    "rhythm": {"mean_min": 14, "mean_max": 20, "mean_hard_min": 12,
               "mean_hard_max": 24, "longest_max": 35, "min_short": 2},
    "length": {"min": 200, "max": 280, "hard_min": 160, "hard_max": 340},
}
CTX = {"years_from_now": 574, "engine": "logistics"}

# A body that scores well: mean sentence 15 words, longest 18, three short
# sentences, 225 words. Padded with whole SENTENCES on purpose - padding with a
# bare word list yields one enormous sentence and fails the rhythm rules.
_LONG_S = ("The council sealed the shaft on Tuesday and nobody filed a query "
           "about the missing crew that week. ")
_SHORT_S = "She walked out. "
GOOD_BODY = (_LONG_S * 12 + _SHORT_S * 3).strip()
BAD_BODY = "The proceedings took an unexpected turn today."


def test_choose_prefers_the_judge_pick(monkeypatch):
    drafts = [_dispatch("A", GOOD_BODY), _dispatch("B", GOOD_BODY)]
    monkeypatch.setattr(judge_mod, "judge",
                        lambda d, s: {"pick": 1, "reason": "funnier"})
    chosen, info = run_mod.choose_draft(drafts, CTX, CFG, {})
    assert chosen["headline"] == "B"
    assert info["judge_reason"] == "funnier"


def test_choose_falls_back_to_top_score_when_judge_fails(monkeypatch):
    import gemini
    good = _dispatch("Good", GOOD_BODY)
    bad = _dispatch("Bad", BAD_BODY)

    def boom(d, s):
        raise gemini.GeminiError("boom")

    monkeypatch.setattr(judge_mod, "judge", boom)
    chosen, info = run_mod.choose_draft([bad, good], CTX, CFG, {})
    assert chosen["headline"] == "Good"
    assert info["judge_reason"] == ""


def test_choose_uses_best_rejected_when_all_are_rejected(monkeypatch):
    a = _dispatch("A", BAD_BODY)
    b = _dispatch("B", "The scandal deepened and took an unexpected turn.")
    monkeypatch.setattr(judge_mod, "judge",
                        lambda d, s: {"pick": 0, "reason": "x"})
    chosen, info = run_mod.choose_draft([a, b], CTX, CFG, {})
    assert chosen["headline"] in ("A", "B")
    assert info["all_rejected"] is True


def test_choose_skips_the_judge_for_a_single_survivor(monkeypatch):
    called = []
    monkeypatch.setattr(judge_mod, "judge",
                        lambda d, s: called.append(1) or {"pick": 0, "reason": "x"})
    good = _dispatch("Only", GOOD_BODY)
    bad = _dispatch("Rejected", BAD_BODY)
    chosen, info = run_mod.choose_draft([good, bad], CTX, CFG, {})
    assert chosen["headline"] == "Only"
    assert called == []


def test_maybe_revise_keeps_a_worse_revision_out(monkeypatch):
    good = _dispatch("Good", GOOD_BODY)
    worse = _dispatch("Worse", BAD_BODY)
    monkeypatch.setattr(revise_mod, "revise",
                        lambda d, v, s: {"critique": "c", "dispatch": worse})
    out, info = run_mod.maybe_revise(good, CTX, CFG, {})
    assert out["headline"] == "Good"
    assert info["revision_accepted"] is False


def test_maybe_revise_accepts_a_better_revision(monkeypatch):
    bad = _dispatch("Bad", BAD_BODY)
    better = _dispatch("Better", GOOD_BODY)
    monkeypatch.setattr(revise_mod, "revise",
                        lambda d, v, s: {"critique": "c", "dispatch": better})
    out, info = run_mod.maybe_revise(bad, CTX, CFG, {})
    assert out["headline"] == "Better"
    assert info["revision_accepted"] is True
    assert info["score_after"] >= info["score_before"]


def test_maybe_revise_survives_a_revise_failure(monkeypatch):
    import gemini
    d = _dispatch("Keep", BAD_BODY)

    def boom(a, b, c):
        raise gemini.GeminiError("boom")

    monkeypatch.setattr(revise_mod, "revise", boom)
    out, info = run_mod.maybe_revise(d, CTX, CFG, {})
    assert out["headline"] == "Keep"
    assert info["revision_accepted"] is False


def test_maybe_revise_is_skipped_when_disabled(monkeypatch):
    called = []
    monkeypatch.setattr(revise_mod, "revise",
                        lambda d, v, s: called.append(1) or {})
    cfg = dict(CFG, revise=False)
    d = _dispatch("Untouched", BAD_BODY)
    out, info = run_mod.maybe_revise(d, CTX, cfg, {})
    assert out["headline"] == "Untouched"
    assert called == []
    assert info["revision_accepted"] is False


# A body that scores below GOOD_BODY but is NOT rejected: 171 words trips the
# minor length rule only. Needed so sorting actually reorders the pool.
MEDIOCRE_BODY = (_LONG_S * 9 + _SHORT_S * 3).strip()


def test_judge_index_resolves_against_the_SORTED_pool(monkeypatch):
    """The judge is handed `pool` (re-sorted by score), so its index must be
    resolved against that same list. Two equal-scoring drafts cannot detect a
    mix-up, because sorted() is stable and input order survives - so this uses
    drafts with DIFFERENT scores, where sorting genuinely reorders."""
    mediocre = _dispatch("Mediocre", MEDIOCRE_BODY)
    good = _dispatch("Good", GOOD_BODY)
    seen = {}

    def fake_judge(drafts, settings):
        seen["headlines"] = [d["headline"] for d in drafts]
        return {"pick": 1, "reason": "second one"}

    monkeypatch.setattr(judge_mod, "judge", fake_judge)
    # input order puts Mediocre first; sorted pool must put Good first
    chosen, info = run_mod.choose_draft([mediocre, good], CTX, CFG, {})
    assert seen["headlines"] == ["Good", "Mediocre"]
    assert chosen["headline"] == "Mediocre"      # pool[1], not scored[1]
    assert info["judge_pick"] == 1
    assert info["chosen_index"] == 0             # index into the ORIGINAL drafts


def test_maybe_revise_accepts_an_exact_tie(monkeypatch):
    """The spec's gate is `>=`, so an equal-scoring revision is published. This
    is load-bearing and was previously untested."""
    draft = _dispatch("Draft", GOOD_BODY)
    twin = _dispatch("Twin", GOOD_BODY)
    monkeypatch.setattr(revise_mod, "revise",
                        lambda d, v, s: {"critique": "c", "dispatch": twin})
    out, info = run_mod.maybe_revise(draft, CTX, CFG, {})
    assert info["score_after"] == info["score_before"]
    assert info["revision_accepted"] is True
    assert out["headline"] == "Twin"


def test_maybe_revise_refuses_a_revision_that_breaks_a_hard_rule(monkeypatch):
    """Even a tie or an improvement must not admit a revision that trips a hard
    reject the draft did not."""
    cfg = dict(CFG, hard_reject=["structure"])
    draft = _dispatch("Draft", GOOD_BODY)
    headless = _dispatch("", GOOD_BODY)
    monkeypatch.setattr(revise_mod, "revise",
                        lambda d, v, s: {"critique": "c", "dispatch": headless})
    out, info = run_mod.maybe_revise(draft, CTX, cfg, {})
    assert out["headline"] == "Draft"
    assert info["revision_accepted"] is False


def test_maybe_revise_demands_strict_improvement_at_the_score_floor(monkeypatch):
    """The score floors at 0.0, so a draft already at the floor would TIE with
    any replacement at all - including a three-word stub. At the floor the gate
    must require a strict improvement."""
    cfg = dict(CFG, hard_reject=[])
    floored = _dispatch("Floored", BAD_BODY + " A tribunal issued a writ. "
                        + "They realised it was too odd to notice. "
                        + " ".join(["word"] * 60) + ".")
    before = critic.score(floored, CTX, cfg)
    assert before["score"] == 0.0, "fixture must actually sit at the floor"
    stub = _dispatch("Stub", "It stayed sealed.")
    monkeypatch.setattr(revise_mod, "revise",
                        lambda d, v, s: {"critique": "c", "dispatch": stub})
    out, info = run_mod.maybe_revise(floored, CTX, cfg, {})
    assert out["headline"] == "Floored"
    assert info["revision_accepted"] is False
