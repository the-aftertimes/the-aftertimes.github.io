"""Deterministic dispatch scoring - the measurable half of quality control.

Everything checkable in code lives here so the two model calls in the pipeline
(judge, revise) are spent only on the genuinely subjective question of whether a
dispatch is funny. Pure functions: no API calls, no file IO, no globals.

Severity is either "major" or "minor"; the weights and thresholds all come from
the `quality` block in config/settings.yaml so tuning never means editing code.
"""
from __future__ import annotations

from write import prose_report


def metrics_for(body: str) -> dict:
    """Prose measurements for a body. Thin alias so callers do not reach into
    write.py, and so tests read clearly."""
    return prose_report(body)


def _v(rule: str, detail: str, severity: str) -> dict:
    return {"rule": rule, "detail": detail, "severity": severity}


def check_rhythm(metrics: dict, cfg: dict) -> list[dict]:
    r = cfg["rhythm"]
    out = []
    mean = metrics["mean_sentence"]
    if not (r["mean_min"] <= mean <= r["mean_max"]):
        hard = mean < r["mean_hard_min"] or mean > r["mean_hard_max"]
        out.append(_v("rhythm_mean",
                      f"mean sentence is {mean} words, wanted "
                      f"{r['mean_min']}-{r['mean_max']}",
                      "major" if hard else "minor"))
    if metrics["longest"] > r["longest_max"]:
        out.append(_v("rhythm_longest",
                      f"longest sentence is {metrics['longest']} words, "
                      f"maximum {r['longest_max']}", "major"))
    if metrics["short_sentences"] < r["min_short"]:
        out.append(_v("rhythm_short",
                      f"only {metrics['short_sentences']} sentences of six words "
                      f"or fewer, wanted at least {r['min_short']}", "minor"))
    return out


def check_length(metrics: dict, cfg: dict) -> list[dict]:
    ln = cfg["length"]
    words = metrics["words"]
    if ln["min"] <= words <= ln["max"]:
        return []
    hard = words < ln["hard_min"] or words > ln["hard_max"]
    return [_v("length",
               f"{words} words, wanted {ln['min']}-{ln['max']}",
               "major" if hard else "minor")]
