"""The taste loop: review.py shows, mark.py records, write.taste_sample limits."""
import write


def _pool(n_sources, per_source):
    return [{"line": f"line {s}.{i}", "setup": [], "source": f"2026-10-{s:02d}"}
            for s in range(1, n_sources + 1) for i in range(per_source)]


def test_sample_never_exceeds_its_cap():
    assert len(write.taste_sample(_pool(10, 3), 5, seed="x")) == 5


def test_one_loved_edition_cannot_dominate():
    """Charlie: "dont overtune it". Ten marks from one piece must not become ten
    of the five lines the prompt sees."""
    pool = _pool(1, 10) + _pool(3, 1)[0:0] + [
        {"line": "other", "setup": [], "source": "2026-11-01"}]
    got = write.taste_sample(pool, 5, seed="x")
    by_source = {}
    for e in got:
        by_source[e["source"]] = by_source.get(e["source"], 0) + 1
    assert max(by_source.values()) <= 2


def test_sample_draws_from_the_whole_pool_not_the_tail():
    """Showing the newest N each day is what overtunes - last week's marks would
    be in every prompt. Over many days, old entries must still appear."""
    pool = _pool(20, 1)
    oldest = pool[0]["line"]
    seen = any(oldest in [e["line"] for e in write.taste_sample(pool, 5, seed=f"d{k}")]
               for k in range(40))
    assert seen


def test_sample_is_stable_for_one_day():
    pool = _pool(20, 1)
    assert write.taste_sample(pool, 5, seed="2026-11-06") == \
        write.taste_sample(pool, 5, seed="2026-11-06")


def test_sample_keeps_pool_order_so_excerpts_still_merge():
    got = write.taste_sample(_pool(6, 2), 5, seed="y")
    pool = _pool(6, 2)
    positions = [pool.index(e) for e in got]
    assert positions == sorted(positions)


def test_empty_pool_is_silent():
    assert write.taste_sample([], 5) == []
    assert write.funny_block([]) == ""


def test_review_parses_a_reply(tmp_path, monkeypatch):
    import common
    import mark
    import review
    _orig = common._path
    monkeypatch.setattr(common, "_path", lambda *p: str(tmp_path.joinpath(*p))
                        if p and p[0].startswith("data") else _orig(*p))
    (tmp_path / "data").mkdir()
    common.write_json(review._INDEX, {
        "editions": ["2026-11-06"],
        "losers": [{"date": "2026-11-06", "headline": "Wail Shortened By Decree"}]})
    calls, saved = [], []
    monkeypatch.setattr(mark, "add", lambda d, nums, flat=False: (calls.append((d, nums, flat)), (1, 0))[1])
    monkeypatch.setattr(mark, "load", lambda path=None: [])
    monkeypatch.setattr(mark, "save", lambda pool, path=None: saved.append(pool))
    review.apply("funny 1.3 H1; flat 1.5")
    assert ("2026-11-06", [3], False) in calls
    assert ("2026-11-06", [5], True) in calls
    assert saved and saved[-1][0]["line"] == "Wail Shortened By Decree"
    assert saved[-1][0]["kind"] == "headline"
