"""Show Charlie the recent writing, numbered, so he can say what is funny.

    python review.py            # last 5 editions -> review.html, opened in Chrome
    python review.py 8          # last 8
    python review.py --apply "funny 2.3 2.4 H5; flat 1.2"

Every line of every recent edition gets a number (edition.sentence), and the
headlines that LOST the judge's vote get H-numbers - the losing headlines are
often the funniest thing the paper writes and nobody ever sees them. He replies
with numbers; --apply records them through mark.py, which keeps each line's setup
with it.

This is the only taste signal the paper has. Since the verdict step was removed
every quality check is a model grading a model, which is how it scored 7 out of
10 for weeks while Charlie called the writing "still bad" (06/11/2026). He asked
for this loop with one condition: "dont overtune it". The guard against that
lives where the pools are READ (write.funny_block / write.flat_block), not here:
the prompt sees a small rotating sample, never the whole pool.
"""
from __future__ import annotations

import glob
import html
import os
import re
import subprocess
import sys

from common import read_json, rel, write_json
import mark

_INDEX = "data/review_index.json"
_PAGE = "review.html"


def collect(days: int) -> tuple[list[dict], list[dict]]:
    """(editions, losing headlines), newest edition first."""
    files = sorted(glob.glob(rel("data/dispatches/*.json")))[-days:][::-1]
    editions, losers = [], []
    for f in files:
        rec = read_json(f"data/dispatches/{os.path.basename(f)}") or {}
        d = rec.get("dispatch") or {}
        date = rec.get("run_date") or os.path.basename(f)[:-5]
        sents, _ = mark.resolve(date)
        editions.append({"date": date, "headline": d.get("headline", ""),
                         "sentences": sents})
        published = (d.get("headline") or "").strip()
        for dr in ((rec.get("quality") or {}).get("drafts") or []):
            h = (dr.get("headline") or "").strip()
            if h and h != published:
                losers.append({"date": date, "headline": h})
    return editions, losers


def render(editions: list[dict], losers: list[dict]) -> str:
    blocks = []
    for k, ed in enumerate(editions, start=1):
        rows = "".join(
            f'<li><span class="n">{k}.{i}</span>{html.escape(s)}</li>'
            for i, s in enumerate(ed["sentences"], start=1))
        blocks.append(
            f'<article><div class="tag">{k} &middot; {ed["date"]}</div>'
            f'<h2>{html.escape(ed["headline"])}</h2><ol>{rows}</ol></article>')
    heads = "".join(
        f'<li><span class="n">H{j}</span>{html.escape(h["headline"])}'
        f' <span class="d">{h["date"]}</span></li>'
        for j, h in enumerate(losers, start=1))
    return f"""<meta charset="utf-8"><title>Aftertimes review</title>
<style>
body{{background:#eeece5;color:#1a1611;font:17px/1.6 Georgia,serif;max-width:46rem;
margin:0 auto;padding:2rem 1.25rem 5rem}}
h1{{font-size:1.4rem;margin:0 0 .3rem}} .lede{{color:#5c5347;margin:0 0 2rem}}
article{{margin:0 0 2.4rem;padding-top:1.2rem;border-top:1px solid #d6cdb9}}
h2{{font-size:1.15rem;margin:.3rem 0 .8rem}}
.tag,.d{{font:12px ui-monospace,monospace;color:#7a2b2b}} .d{{color:#9a8f7a}}
ol{{list-style:none;padding:0;margin:0}}
li{{margin:.4rem 0;padding-left:3.4rem;text-indent:-3.4rem}}
.n{{display:inline-block;width:3rem;text-indent:0;font:12px ui-monospace,monospace;
color:#9a8f7a}}
</style>
<h1>The Aftertimes - what's funny?</h1>
<p class="lede">Reply with numbers: <code>funny 2.3 2.4 H5; flat 1.2</code>.
Only mark the ones that stand out either way.</p>
{''.join(blocks)}
<article><div class="tag">Headlines that lost the vote</div><ol>{heads}</ol></article>
"""


_TOKEN = re.compile(r"H\d+|\d+\.\d+")


def apply(spec: str) -> int:
    """Record a reply like 'funny 2.3 H5; flat 1.2' against the saved index."""
    index = read_json(_INDEX)
    if not index:
        raise SystemExit("no review_index.json - run `python review.py` first")
    editions, losers = index["editions"], index["losers"]
    done = 0
    for part in spec.split(";"):
        part = part.strip()
        if not part:
            continue
        flat = part.lower().startswith("flat")
        for tok in _TOKEN.findall(part):
            if tok.startswith("H"):
                j = int(tok[1:])
                if not 1 <= j <= len(losers) or flat:
                    print(f"  skip {tok}", file=sys.stderr)
                    continue
                h = losers[j - 1]
                pool = mark.load()
                if all(e["line"] != h["headline"] for e in pool):
                    pool.append({"line": h["headline"], "setup": [],
                                 "source": h["date"], "kind": "headline",
                                 "why": "a headline that lost the vote"})
                    mark.save(pool)
                    done += 1
                continue
            k, i = (int(x) for x in tok.split("."))
            if not 1 <= k <= len(editions):
                print(f"  skip {tok}", file=sys.stderr)
                continue
            added, _ = mark.add(editions[k - 1], [i], flat=flat)
            done += added
    print(f"recorded {done} mark(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--apply" in argv:
        i = argv.index("--apply")
        return apply(" ".join(argv[i + 1:]))
    days = int(argv[0]) if argv and argv[0].isdigit() else 5
    editions, losers = collect(days)
    write_json(_INDEX, {"editions": [e["date"] for e in editions],
                        "losers": losers})
    path = rel(_PAGE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render(editions, losers))
    print(f"wrote {path}: {len(editions)} editions, {len(losers)} losing headlines")
    if "--no-open" not in argv:
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome):
            subprocess.Popen([chrome, path])
    return 0


if __name__ == "__main__":
    sys.exit(main())
