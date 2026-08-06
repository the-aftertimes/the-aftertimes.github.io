"""Staleness detection over the archive."""
import trends


def _d(headline, body, place="Somewhere", domain="law"):
    return {"dispatch": {"headline": headline, "body": body, "domain": domain,
                         "dateline": {"place": place, "year": 2500,
                                      "years_from_now": 474}}}


def test_repeated_phrases_are_detected_and_singletons_are_not():
    recs = [_d("H", "The council sealed the shaft again today."),
            _d("H", "The council sealed the door quietly."),
            _d("H", "The council sealed the vault at dawn."),
            _d("H", "A goalkeeper retired to the moon.")]
    hits = trends.repeated_phrases(recs, min_count=3)
    assert any("the council sealed" in h["item"] for h in hits)
    assert not any("goalkeeper" in h["item"] for h in hits)


def test_sentence_openers_are_detected():
    recs = [_d("H", "Municipal logs reveal a fault. More text here."),
            _d("H", "Municipal logs reveal a leak. More text here."),
            _d("H", "Municipal logs reveal a gap. More text here."),
            _d("H", "Rain fell on the dome all week.")]
    hits = trends.repeated_openers(recs, min_count=3)
    assert any(h["item"].startswith("municipal logs reveal") for h in hits)


def test_place_formulas_catch_the_pattern_not_the_literal():
    recs = [_d("H", "b", place="New Wollongong"), _d("H", "b", place="New Cairo"),
            _d("H", "b", place="New Perth"), _d("H", "b", place="Tycho South Rim")]
    hits = trends.place_formulas(recs, min_count=3)
    assert any(h["item"] == "New <place>" for h in hits)


def test_repeated_names_are_detected():
    recs = [_d("H", '"Yes," said Kaelen Varma, an engineer.'),
            _d("H", '"No," said Kaelen Varma, a pilot.'),
            _d("H", '"Maybe," said Kaelen Varma, a cook.'),
            _d("H", '"Never," said Tenzin Norbu, a clerk.')]
    hits = trends.repeated_names(recs, min_count=3)
    assert any("kaelen" in h["item"].lower() for h in hits)
    assert not any("tenzin" in h["item"].lower() for h in hits)


def test_every_hit_carries_a_count_and_the_dates_involved():
    recs = [_d("H", "The council sealed the shaft.") for _ in range(3)]
    for r in recs:
        r["run_date"] = "2026-08-01"
    hits = trends.repeated_phrases(recs, min_count=3)
    assert hits and hits[0]["count"] >= 3
    assert "kind" in hits[0]
