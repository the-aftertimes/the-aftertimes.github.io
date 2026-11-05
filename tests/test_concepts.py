"""The concept loop: concepts.py shows, run.sample_premises limits."""
import run


SEEDS = [f"seed {i}" for i in range(19)]


def test_ideate_no_longer_sees_every_seed():
    got = run.sample_premises(SEEDS, [], "2026-11-07")
    assert len(got) == run._SEEDS_PER_RUN


def test_picks_steer_but_cannot_take_over():
    """Charlie: "dont overtune it". Forty picks must still mean four a day,
    sitting beside four seeds - not forty few-shots in one prompt."""
    picks = [f"pick {i}" for i in range(40)]
    got = run.sample_premises(SEEDS, picks, "2026-11-07")
    assert sum(g.startswith("pick") for g in got) == run._PICKED_PER_RUN
    assert sum(g.startswith("seed") for g in got) == run._SEEDS_PER_RUN


def test_every_pick_gets_a_turn_over_time():
    picks = [f"pick {i}" for i in range(12)]
    seen = set()
    for d in range(60):
        seen |= {g for g in run.sample_premises(SEEDS, picks, f"day{d}")
                 if g.startswith("pick")}
    assert seen == set(picks)


def test_the_same_day_gives_the_same_prompt():
    picks = [f"pick {i}" for i in range(12)]
    assert run.sample_premises(SEEDS, picks, "2026-11-07") == \
        run.sample_premises(SEEDS, picks, "2026-11-07")


def test_no_picks_is_just_seeds():
    assert all(g.startswith("seed") for g in run.sample_premises(SEEDS, [], "d"))


def test_concepts_page_builds_from_the_archive_and_the_fresh_set():
    import concepts
    items = concepts.archive(30, "s") + concepts.fresh()
    sources = {c["source"] for c in items}
    assert {"published", "lost", "fresh"} <= sources
    assert all(c["text"] for c in items)
