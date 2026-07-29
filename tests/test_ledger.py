from ledger import recent_eras, recent_domains, is_novel, append_entry


LEDGER = [
    {"run_date": "2026-07-20", "era_bucket": 2, "domain": "sport",
     "headline": "Robot umpire defects to the other team"},
    {"run_date": "2026-07-21", "era_bucket": 40, "domain": "money and finance",
     "headline": "Nation abolishes money on a Tuesday"},
]


def test_recent_eras_collects_buckets():
    assert recent_eras(LEDGER, last_n=5) == {2, 40}


def test_recent_domains_collects_domains():
    assert "sport" in recent_domains(LEDGER, last_n=5)


def test_is_novel_rejects_near_duplicate():
    cand = "A nation abolishes money on a Tuesday and tells no one"
    assert is_novel(cand, LEDGER, threshold=0.45, window=30) is False


def test_is_novel_accepts_fresh_headline():
    cand = "Saturn's moon secedes over irreconcilable time zones"
    assert is_novel(cand, LEDGER, threshold=0.45, window=30) is True


def test_is_novel_true_on_empty_ledger():
    assert is_novel("anything at all", [], threshold=0.45, window=30) is True


def test_append_entry_shape():
    entry = append_entry([], run_date="2026-07-28",
                         dateline={"year": 2391, "years_from_now": 365},
                         domain="crime", headline="Someone sues their own clone",
                         era_bucket_years=50, style="wire")
    assert entry[-1]["era_bucket"] == 365 // 50
    assert entry[-1]["domain"] == "crime"
    assert entry[-1]["style"] == "wire"
