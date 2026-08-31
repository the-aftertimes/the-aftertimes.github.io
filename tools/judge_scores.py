"""The distribution of judge scores, so the floor can be set from data.

    python tools/judge_scores.py

config/settings.yaml's `judge_floor` was set to 5 on 31/08/2026 as a bound
chosen to fire rarely, because no score had ever been recorded. This is the
command that replaces that guess. Run it once a fortnight's worth of dispatches
carry a judge_score and move the floor to roughly the 20th percentile - low
enough that a normal night is untouched, high enough that a genuinely weak pool
buys a second batch.

It also reports how often the floor WOULD have fired, which is the number that
actually matters: a floor firing most nights is not a floor, it is a doubled
draft budget.
"""
from __future__ import annotations

import glob
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import load_settings, rel  # noqa: E402


def main() -> int:
    scores = []
    for path in sorted(glob.glob(rel("data/dispatches/*.json"))):
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh) or {}
        s = (rec.get("quality") or {}).get("judge_score")
        if isinstance(s, (int, float)):
            scores.append((os.path.basename(path)[:-5], float(s)))
    if not scores:
        print("No judge scores recorded yet. They start with the first dispatch "
              "after 31/08/2026; come back in a fortnight.")
        return 0

    vals = sorted(v for _, v in scores)
    floor = load_settings()["quality"].get("judge_floor") or 0
    print(f"{len(vals)} scored dispatch(es)")
    print(f"  min {vals[0]:.1f}  p20 {vals[int(0.2 * len(vals))]:.1f}  "
          f"median {st.median(vals):.1f}  "
          f"p80 {vals[min(len(vals) - 1, int(0.8 * len(vals)))]:.1f}  max {vals[-1]:.1f}")
    if floor:
        under = sum(1 for v in vals if v < floor)
        print(f"  floor {floor}: would have fired on {under}/{len(vals)} "
              f"({100 * under / len(vals):.0f}%)")
        if under > len(vals) * 0.4:
            print("  -> that is not a floor, it is a doubled draft budget. Lower it.")
        elif under == 0 and len(vals) >= 10:
            print("  -> never fires. Raise it toward the 20th percentile above.")
    print()
    for date, v in sorted(scores):
        print(f"  {date}  {v:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
