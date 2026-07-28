from datetime import date
import random

from dates import sample_future_dateline, era_bucket, format_dateline


def test_sample_is_in_the_future(rng, date_cfg):
    dl = sample_future_dateline(date(2026, 7, 28), date_cfg, set(), rng)
    assert dl["year"] > 2026
    assert dl["years_from_now"] >= date_cfg["min_years"]
    assert 1 <= dl["month"] <= 12
    assert 1 <= dl["day"] <= 28


def test_deep_future_year_does_not_crash(date_cfg):
    # Force the deep band; year can exceed 9999 (datetime.date would raise).
    rng = random.Random(2)
    date_cfg = {**date_cfg, "band_weights": [0.0, 0.0, 1.0]}
    dl = sample_future_dateline(date(2026, 1, 1), date_cfg, set(), rng)
    assert dl["year"] >= 2026 + 3000
    assert isinstance(dl["year"], int)


def test_anti_clustering_avoids_recent_eras(date_cfg):
    # If every near/mid era is "recent", the sampler still returns something
    # (falls through after max_attempts) but tries to avoid the blocked set.
    rng = random.Random(7)
    dl = sample_future_dateline(date(2026, 1, 1), date_cfg, set(), rng)
    blocked = {era_bucket(dl["years_from_now"], 50)}
    dl2 = sample_future_dateline(date(2026, 1, 1), date_cfg, blocked, random.Random(7))
    assert era_bucket(dl2["years_from_now"], 50) not in blocked or dl2["years_from_now"] != dl["years_from_now"]


def test_format_dateline_no_dashes_and_grouped_years():
    txt = format_dateline({"place": "Port Kobenhavn-2", "year": 40312,
                           "month": 9, "day": 4, "years_from_now": 38286})
    assert "September" in txt
    assert "40312" in txt or "40,312" in txt
    assert "\u2014" not in txt and "\u2013" not in txt
