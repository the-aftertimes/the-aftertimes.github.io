import avoid

CFG = {"enabled": True, "window": 30, "min_count": 3, "avoid_char_cap": 200,
       "exemplar_cap": 24, "proposals_weekday": 0}

HITS = [{"kind": "phrase", "item": "the council sealed", "count": 5,
         "dates": ["2026-08-01"]},
        {"kind": "opener", "item": "municipal logs reveal", "count": 4,
         "dates": ["2026-08-02"]},
        {"kind": "name", "item": "Kaelen Varma", "count": 3,
         "dates": ["2026-08-03"]}]


def test_render_lists_items_strongest_first():
    text = avoid.render(HITS, CFG)
    assert "the council sealed" in text
    assert text.index("the council sealed") < text.index("Kaelen Varma")


def test_render_respects_the_character_cap():
    many = [{"kind": "phrase", "item": f"stale phrase number {i}", "count": 9,
             "dates": []} for i in range(200)]
    text = avoid.render(many, CFG)
    assert len(text) <= CFG["avoid_char_cap"]


def test_render_is_empty_when_there_is_nothing_stale():
    assert avoid.render([], CFG) == ""


def test_render_is_empty_when_learning_is_disabled():
    assert avoid.render(HITS, dict(CFG, enabled=False)) == ""


def test_window_limits_which_records_are_considered():
    recs = [{"run_date": f"2026-07-{d:02d}", "dispatch": {}} for d in range(1, 20)]
    assert len(avoid.recent(recs, 5)) == 5
    assert avoid.recent(recs, 5)[-1]["run_date"] == "2026-07-19"
