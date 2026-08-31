"""Record which sentences Charlie found funny, into config/funny_lines.yaml.

    python mark.py --show 2026-08-31   # number the sentences of a published edition
    python mark.py 2026-08-31 4 7      # these ones landed
    python mark.py t002 1 2 3 6        # same, on a trial
    python mark.py --list              # show the pool

PUBLISHED EDITIONS ARE MARKABLE, added 31/08/2026, and the reason is the whole
point of this file. On that date the pool held FOUR lines, all from one trial
(t002), marked once on 10/08. config/exemplars.yaml held ONE premise, added by
hand. Everything else the pipeline measures - critic.py's rhythm, length,
plainness and five hard-reject rules - is mechanics, and mechanics only stop a
dispatch being bad. So Charlie's verdict that the paper "is never that funny"
was a description of a starved loop, not of a broken one: the taste channel
existed and had been fed twice in three weeks.

It had been fed twice because feeding it meant running a trial and reading
numbered sentences in a terminal. He reads the published edition every morning
anyway. Pointing the same marker at that is the difference between a habit and
an errand.

The pool is injected into the write prompt as few-shot evidence of what actually
lands (see write.build_prompt). It is the ONLY taste signal in the project -
everything else the loop measures is repetition or mechanics.

Deliberately capped and deduped: a lopsided few-shot pool collapses the register,
which is exactly how every dispatch ended up being about unpaid debts.
"""
from __future__ import annotations

import re
import sys

import yaml

from common import read_json, rel
from trial import split_sentences

_PATH = "config/funny_lines.yaml"
_CAP = 30
# Sentences of setup carried with each marked line, so the pool preserves the
# sequence the comedy actually lives in.
_CONTEXT = 2


def load() -> list[dict]:
    with open(rel(_PATH), encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("lines") or []


def save(lines: list[dict]) -> None:
    """Rewrites the pool. Note this drops the file's hand-written header comment,
    so keep the guidance for future sessions in mark.py and write.py, not there."""
    with open(rel(_PATH), "w", encoding="utf-8") as fh:
        yaml.safe_dump({"lines": lines}, fh, allow_unicode=True, sort_keys=False,
                       default_flow_style=False, width=100)


#: A published edition is addressed by its date; a trial by its slug.
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def resolve(slug: str) -> tuple[list[str], str | None]:
    """Sentences for `slug`, and the trial path to write a `funny` list back to.

    A published edition has no such path - the dispatch record is the archive and
    is not rewritten here - so the second element is None for one.
    """
    if _DATE.match(slug):
        rec = read_json(f"data/dispatches/{slug}.json")
        if not rec:
            raise SystemExit(f"no edition for {slug!r} - see data/dispatches/")
        body = (rec.get("dispatch") or {}).get("body") or ""
        return split_sentences(body), None
    rec = read_json(f"data/trials/{slug}.json")
    if not rec:
        raise SystemExit(f"no trial {slug!r} - run `python trial.py --render` to list")
    return rec.get("sentences") or [], f"data/trials/{slug}.json"


def show(slug: str) -> int:
    sents, _ = resolve(slug)
    for i, line in enumerate(sents, start=1):
        print(f"{i:3d}  {line}")
    return 0


def add(slug: str, numbers: list[int], why: str = "") -> tuple[int, int]:
    """Returns (added, skipped)."""
    sents, trial_path = resolve(slug)
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
        # Store the SETUP with the payoff. Charlie's note on 10/08/2026: "the
        # lines are funny in the context they're in, not just by themself" -
        # "Most messages address minor domestic disputes." is nothing without
        # the magnetosphere sentence before it. A pool of orphaned one-liners
        # teaches the model that flat sentences are inherently funny, which is
        # the opposite of the lesson.
        setup = [s for s in sents[max(0, n - 1 - _CONTEXT):n - 1]]
        pool.append({"line": line, "setup": setup, "source": slug, "why": why})
        seen.add(line)
        added += 1
    # Keep the freshest, so the pool tracks current taste rather than ossifying.
    if len(pool) > _CAP:
        pool = pool[-_CAP:]
    save(pool)
    if trial_path:
        rec = read_json(trial_path) or {}
        rec["funny"] = sorted(set(rec.get("funny") or []) | set(numbers))
        from common import write_json
        write_json(trial_path, rec)
    return added, skipped


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    pool = load()
    if not argv or "--list" in argv:
        print(f"{len(pool)} line(s) in the pool:")
        for e in pool:
            print(f"  [{e.get('source', '?')}] {e['line']}")
        return 0
    if argv[0] == "--show":
        if len(argv) < 2:
            raise SystemExit("give an edition date or trial slug, e.g. mark.py --show 2026-08-31")
        return show(argv[1])
    slug, nums = argv[0], [int(a) for a in argv[1:] if a.isdigit()]
    if not nums:
        raise SystemExit("give at least one sentence number, e.g. mark.py 2026-08-31 4 7")
    added, skipped = add(slug, nums)
    print(f"added {added}, skipped {skipped}; pool now {len(load())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
