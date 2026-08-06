import exemplars

LEGALISH = "A tribunal issues a writ over unpaid taxes and a lien on a debt."
CLEAN = "A colony holds a state funeral for its last surviving houseplant."


def test_promote_adds_a_good_premise():
    pool = exemplars.promote([], CLEAN, cap=5)
    assert CLEAN in pool


def test_promotion_is_idempotent():
    pool = exemplars.promote([CLEAN], CLEAN, cap=5)
    assert pool.count(CLEAN) == 1


def test_cap_evicts_the_oldest():
    pool = [f"premise {i}" for i in range(5)]
    out = exemplars.promote(pool, CLEAN, cap=5)
    assert len(out) == 5
    assert CLEAN in out
    assert "premise 0" not in out


def test_register_guard_refuses_to_unbalance_the_pool():
    """Few-shot examples dominate output, so letting the pool fill with legal or
    financial premises would re-create the 'why is it always unpaid debts'
    collapse."""
    pool = [LEGALISH, LEGALISH.replace("tribunal", "court")]
    out = exemplars.promote(pool, LEGALISH.replace("writ", "summons"), cap=10)
    assert len(out) == 2      # refused
    assert exemplars.legal_share(out) <= 1.0


def test_a_clean_premise_is_still_accepted_into_a_legal_heavy_pool():
    pool = [LEGALISH, LEGALISH.replace("tribunal", "court")]
    out = exemplars.promote(pool, CLEAN, cap=10)
    assert CLEAN in out
