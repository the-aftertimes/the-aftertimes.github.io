"""Anti-repetition ledger + TF-IDF novelty gate (novelty approach ported from
One Story). The ledger is a JSON list committed to the repo; it grows one entry
per successful dispatch."""
from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from common import read_json, write_json


def load_ledger() -> list[dict]:
    return read_json("data/ledger.json", default=[]) or []


def save_ledger(ledger: list[dict]) -> str:
    return write_json("data/ledger.json", ledger)


def recent_eras(ledger: list[dict], last_n: int) -> set[int]:
    return {e["era_bucket"] for e in ledger[-last_n:] if "era_bucket" in e}


def recent_domains(ledger: list[dict], last_n: int) -> list[str]:
    return [e["domain"] for e in ledger[-last_n:] if e.get("domain")]


def recent_headlines(ledger: list[dict], window: int) -> list[str]:
    return [e["headline"] for e in ledger[-window:] if e.get("headline")]


def is_novel(candidate: str, ledger: list[dict], threshold: float,
             window: int) -> bool:
    """True if `candidate` is not too close to any recent headline."""
    past = recent_headlines(ledger, window)
    if not past:
        return True
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                          sublinear_tf=True)
    tfidf = vec.fit_transform(past + [candidate])
    sims = linear_kernel(tfidf[-1:], tfidf[:-1]).ravel()
    return float(sims.max()) < threshold


def append_entry(ledger: list[dict], run_date: str, dateline: dict, domain: str,
                 headline: str, era_bucket_years: int, style: str) -> list[dict]:
    ledger.append({
        "run_date": run_date,
        "year": dateline["year"],
        "era_bucket": dateline["years_from_now"] // era_bucket_years,
        "domain": domain,
        "headline": headline,
        "style": style,
    })
    return ledger
