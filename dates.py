"""Weighted-random future-date sampler.

The future dateline is plain ints (year, month, day) - NOT a datetime.date,
because deep-future years exceed date's max of 9999. Only 'today' is a date.
"""
from __future__ import annotations

import math
import random as _random
from datetime import date

_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def era_bucket(years_from_now: int, bucket_years: int) -> int:
    return years_from_now // bucket_years


def _sample_years(rng: _random.Random, cfg: dict) -> int:
    band = rng.choices(["near", "mid", "deep"], weights=cfg["band_weights"], k=1)[0]
    lo, hi = cfg["bands"][band]
    lo = max(lo, cfg["min_years"])
    # log-uniform within the band favours the nearer end.
    u = rng.random()
    years = int(round(math.exp(math.log(lo) + u * (math.log(hi) - math.log(lo)))))
    return max(lo, min(hi, years))


def sample_future_dateline(today: date, cfg: dict, recent_eras: set[int],
                           rng: _random.Random | None = None) -> dict:
    """Return a dateline dict: place is filled later by the writer stage."""
    rng = rng or _random.Random()
    ac = cfg["anti_cluster"]
    years = _sample_years(rng, cfg)
    for _ in range(ac["max_attempts"]):
        if era_bucket(years, ac["era_bucket_years"]) not in recent_eras:
            break
        years = _sample_years(rng, cfg)
    return {
        "place": "",                       # set by write stage
        "year": today.year + years,
        "month": rng.randint(1, 12),
        "day": rng.randint(1, 28),         # 28 keeps every month valid
        "years_from_now": years,
    }


def format_dateline(dl: dict) -> str:
    """e.g. 'Port Kobenhavn-2 . 4 September 40,312'. No dashes in the date."""
    place = (dl.get("place") or "").strip()
    ymd = f"{dl['day']} {_MONTHS[dl['month'] - 1]} {dl['year']:,}"
    return f"{place} . {ymd}".strip(" .") if place else ymd


def years_phrase(years_from_now: int) -> str:
    return f"{years_from_now:,} years from today"
