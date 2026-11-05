"""Bring the Eye Test's picks into the paper.

    python eyetest.py

Export first: ArtifactData, action "list", collection "picks", out_dir
data/eyetest, on https://claude.ai/artifact/BXuctDY8THVSFDmrGCALcB.

Every premise Charlie chose goes to config/exemplars.yaml, where ideate sees
four a day (run.sample_premises). "Neither" goes nowhere: it came back on four
pairs in five, so it says the pair was weak, not which idea was. Losing
territories go to config/flat_concepts.yaml by hand, once a pattern repeats.
"""
from __future__ import annotations

import glob
import json

from common import append_yaml_list, rel

_PICKS = "data/eyetest/picks/*.json"


def chosen(picks: list[dict]) -> list[str]:
    out = []
    for p in sorted(picks, key=lambda p: p["at"]):
        c = p.get("choice") or ""
        out += {"a": [p["a"]], "b": [p["b"]], "both": [p["a"], p["b"]]}.get(c, [])
    return list(dict.fromkeys(out))


def main() -> int:
    picks = [json.load(open(f, encoding="utf-8")) for f in glob.glob(rel(_PICKS))]
    if not picks:
        raise SystemExit("no picks exported - see the docstring")
    wins = chosen(picks)
    added = append_yaml_list("config/exemplars.yaml", "exemplars", wins)
    print(f"{len(picks)} readings, {len(wins)} chosen, {len(added)} new to exemplars")
    for t in added:
        print(f"  + {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
