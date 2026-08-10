"""Record which trial sentences Charlie found funny, into config/funny_lines.yaml.

    python mark.py t002 1 2 3 6      # these sentence numbers landed
    python mark.py --list            # show the pool

The pool is injected into the write prompt as few-shot evidence of what actually
lands (see write.build_prompt). It is the ONLY taste signal in the project -
everything else the loop measures is repetition or mechanics.

Deliberately capped and deduped: a lopsided few-shot pool collapses the register,
which is exactly how every dispatch ended up being about unpaid debts.
"""
from __future__ import annotations

import sys

import yaml

from common import read_json, rel

_PATH = "config/funny_lines.yaml"
_CAP = 30


def load() -> list[dict]:
    with open(rel(_PATH), encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("lines") or []


def save(lines: list[dict]) -> None:
    """Rewrites the pool. Note this drops the file's hand-written header comment,
    so keep the guidance for future sessions in mark.py and write.py, not there."""
    with open(rel(_PATH), "w", encoding="utf-8") as fh:
        yaml.safe_dump({"lines": lines}, fh, allow_unicode=True, sort_keys=False,
                       default_flow_style=False, width=100)


def add(slug: str, numbers: list[int], why: str = "") -> tuple[int, int]:
    """Returns (added, skipped)."""
    rec = read_json(f"data/trials/{slug}.json")
    if not rec:
        raise SystemExit(f"no trial {slug!r} - run `python trial.py --render` to list")
    sents = rec.get("sentences") or []
    pool = load()
    seen = {entry["line"] for entry in pool}
    added = skipped = 0
    for n in numbers:
        if not 1 <= n <= len(sents):
            print(f"  skip {slug}.{n}: out of range (1-{len(sents)})", file=sys.stderr)
            skipped += 1
            continue
        line = sents[n - 1]
        if line in seen:
            skipped += 1
            continue
        pool.append({"line": line, "source": slug, "why": why})
        seen.add(line)
        added += 1
    # Keep the freshest, so the pool tracks current taste rather than ossifying.
    if len(pool) > _CAP:
        pool = pool[-_CAP:]
    save(pool)
    rec.setdefault("funny", [])
    rec["funny"] = sorted(set(rec["funny"]) | set(numbers))
    from common import write_json
    write_json(f"data/trials/{slug}.json", rec)
    return added, skipped


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    pool = load()
    if not argv or "--list" in argv:
        print(f"{len(pool)} line(s) in the pool:")
        for e in pool:
            print(f"  [{e.get('source', '?')}] {e['line']}")
        return 0
    slug, nums = argv[0], [int(a) for a in argv[1:] if a.isdigit()]
    if not nums:
        raise SystemExit("give at least one sentence number, e.g. mark.py t002 1 2 3")
    added, skipped = add(slug, nums)
    print(f"added {added}, skipped {skipped}; pool now {len(load())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
