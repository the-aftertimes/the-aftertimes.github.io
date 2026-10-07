"""Record Charlie's good/bad call on a dispatch. This is the quality signal the
loop cannot compute for itself.

    python verdict.py 2026-08-06 good "the kicker lands"
    python verdict.py 2026-08-06 bad  "no satirical target"
    python verdict.py                      # list dispatches awaiting a verdict
    python verdict.py --pull               # fetch the taps made on the page

The page route (07/10/2026): in a browser holding the vote key, each edition
shows two buttons. They post to a Worker (worker/src/index.js), and the daily
job runs --pull before the pipeline, so a tap made at breakfast steers that
night's edition. In 72 editions before this, the CLI above was used zero times.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import urllib.request

from common import read_json, rel, write_json

_PATH = "data/verdicts.json"
_ALLOWED = ("good", "bad")
_URL = "https://verdict.charlietrenorden.com/v"


def load() -> dict:
    return read_json(_PATH, default={}) or {}


def record(run_date: str, call: str, note: str = "", reason: str = "") -> dict:
    if call not in _ALLOWED:
        raise ValueError(f"verdict must be one of {_ALLOWED}, got {call!r}")
    data = load()
    row = {"verdict": call, "note": note.strip()}
    if reason:
        row["reason"] = reason
    data[run_date] = row
    write_json(_PATH, data)
    return data


def sync(remote: dict, known_dates: set[str]) -> list[tuple[str, str, str]]:
    """Fold the page's taps into data/verdicts.json. Returns what changed.

    Only dates that are real editions are taken, and a tap only replaces a
    stored verdict when it says something different, so re-pulling the same
    taps every day writes nothing and promotes nothing twice. A note typed at
    the CLI is kept when a tap agrees with it."""
    stored = load()
    changed = []
    for run_date, row in sorted((remote or {}).items()):
        call = (row or {}).get("verdict")
        reason = (row or {}).get("reason") or ""
        if run_date not in known_dates or call not in _ALLOWED:
            continue
        old = stored.get(run_date) or {}
        if old.get("verdict") == call and (old.get("reason") or "") == reason:
            continue
        note = old.get("note", "") if old.get("verdict") == call else ""
        record(run_date, call, note, reason)
        changed.append((run_date, call, reason))
    return changed


def fetch(url: str, key: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {key}", "User-Agent": "aftertimes-daily"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def pull() -> int:
    """Best-effort: a failed pull must never stop an edition, so this reports
    and returns 0. The taps stay in the Worker and come in on the next run."""
    key = os.environ.get("VERDICT_KEY", "").strip()
    if not key:
        print("verdict pull: no VERDICT_KEY, skipped")
        return 0
    try:
        remote = fetch(os.environ.get("VERDICT_URL", _URL), key)
    except Exception as exc:  # noqa: BLE001 - see docstring
        print(f"verdict pull: FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 0
    known = {os.path.basename(f)[:-5]
             for f in glob.glob(rel("data/dispatches/*.json"))}
    changed = sync(remote, known)
    print(f"verdict pull: {len(remote)} on the page, {len(changed)} new")
    for run_date, call, reason in changed:
        print(f"  {run_date}: {call}" + (f" ({reason})" if reason else ""))
        status = _promote_if_good(run_date, call)
        if status:
            print(f"    {status}")
    return 0


def pending() -> list[str]:
    """Dispatch dates with no verdict yet, newest first."""
    judged = set(load())
    dates = [os.path.basename(f)[:-5]
             for f in sorted(glob.glob(rel("data/dispatches/*.json")))]
    return [d for d in reversed(dates) if d not in judged]


def _promote_if_good(run_date: str, call: str) -> str:
    """A good verdict promotes the dispatch's premise into the few-shot pool.
    Returns a short status line for the CLI."""
    if call != "good":
        return ""
    rec = read_json(f"data/dispatches/{run_date}.json")
    premise = ((rec or {}).get("dispatch") or {}).get("premise", "").strip()
    if not premise:
        return "no premise recorded, nothing promoted"
    import yaml
    import exemplars
    from common import load_settings
    cap = load_settings().get("learning", {}).get("exemplar_cap", 24)
    path = rel("config/exemplars.yaml")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    pool = doc.get("exemplars") or []
    out = exemplars.promote(pool, premise, cap)
    if out == pool:
        return "not promoted (already present, or it would unbalance the register)"
    doc["exemplars"] = out
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, allow_unicode=True, sort_keys=False)
    return f"promoted to the exemplar pool ({len(out)} total)"


def main(argv: list[str]) -> int:
    if argv[:1] == ["--pull"]:
        return pull()
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
    status = _promote_if_good(run_date, call)
    if status:
        print(f"  {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
