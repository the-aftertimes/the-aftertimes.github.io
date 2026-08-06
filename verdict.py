"""Record Charlie's good/bad call on a dispatch. This is the quality signal the
loop cannot compute for itself.

    python verdict.py 2026-08-06 good "the kicker lands"
    python verdict.py 2026-08-06 bad  "no satirical target"
    python verdict.py                      # list dispatches awaiting a verdict
"""
from __future__ import annotations

import glob
import os
import sys

from common import read_json, rel, write_json

_PATH = "data/verdicts.json"
_ALLOWED = ("good", "bad")


def load() -> dict:
    return read_json(_PATH, default={}) or {}


def record(run_date: str, call: str, note: str = "") -> dict:
    if call not in _ALLOWED:
        raise ValueError(f"verdict must be one of {_ALLOWED}, got {call!r}")
    data = load()
    data[run_date] = {"verdict": call, "note": note.strip()}
    write_json(_PATH, data)
    return data


def pending() -> list[str]:
    """Dispatch dates with no verdict yet, newest first."""
    judged = set(load())
    dates = [os.path.basename(f)[:-5]
             for f in sorted(glob.glob(rel("data/dispatches/*.json")))]
    return [d for d in reversed(dates) if d not in judged]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        todo = pending()
        print("Awaiting a verdict:" if todo else "Every dispatch has a verdict.")
        for d in todo[:20]:
            print(f"  {d}")
        return 0
    run_date, call = argv[0], argv[1]
    note = " ".join(argv[2:])
    try:
        record(run_date, call, note)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Recorded {run_date}: {call} {note}".strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
