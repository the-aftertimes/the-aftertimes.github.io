"""The weekly, human-gated proposal document."""
import proposals


def _rec(date, premise, headline="H"):
    return {"run_date": date,
            "dispatch": {"headline": headline, "premise": premise,
                         "body": "b", "domain": "law",
                         "dateline": {"place": "P", "year": 2500,
                                      "years_from_now": 474}}}


def test_document_lists_stale_items_and_the_verdict_tally():
    recs = [_rec(f"2026-08-{i + 1:02d}", "a premise") for i in range(4)]
    verdicts = {"2026-08-01": {"verdict": "good", "note": "kicker"},
                "2026-08-02": {"verdict": "bad", "note": "no target"}}
    doc = proposals.build(recs, verdicts,
                          [{"kind": "phrase", "item": "the council sealed",
                            "count": 4, "dates": []}])
    assert "the council sealed" in doc
    assert "good: 1" in doc and "bad: 1" in doc
    assert "no target" in doc          # the notes are the evidence


def test_document_states_plainly_that_nothing_is_auto_applied():
    doc = proposals.build([], {}, [])
    assert "applied automatically" in doc.lower()


def test_no_em_or_en_dashes():
    doc = proposals.build([], {}, [])
    assert chr(0x2014) not in doc and chr(0x2013) not in doc
