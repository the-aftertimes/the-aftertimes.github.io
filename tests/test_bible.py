from bible import random_slice, merge_glossary


BIBLE = {"motifs": [
    {"term": "Nordwire", "gloss": "pan-Baltic newswire", "kind": "wire", "first_seen": "seed"},
    {"term": "Solar Wire", "gloss": "pan-system newswire", "kind": "wire", "first_seen": "seed"},
    {"term": "Tide & Wren", "gloss": "non-human law firm", "kind": "org", "first_seen": "seed"},
]}


def test_random_slice_size_and_membership(rng):
    sl = random_slice(BIBLE, 2, rng)
    assert len(sl) == 2
    assert all(m in BIBLE["motifs"] for m in sl)


def test_random_slice_caps_at_available(rng):
    sl = random_slice(BIBLE, 99, rng)
    assert len(sl) == 3


def test_merge_glossary_dedups_case_insensitively():
    glossary = [{"term": "nordwire", "gloss": "dup"},
                {"term": "Chrono Bureau", "gloss": "time regulator"}]
    merged = merge_glossary(BIBLE, glossary, run_date="2026-07-28")
    terms = [m["term"].lower() for m in merged["motifs"]]
    assert terms.count("nordwire") == 1
    assert "chrono bureau" in terms
    added = [m for m in merged["motifs"] if m["term"] == "Chrono Bureau"][0]
    assert added["first_seen"] == "2026-07-28"
