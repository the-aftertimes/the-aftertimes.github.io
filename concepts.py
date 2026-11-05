"""Find which CONCEPTS are funny, before any sentence is written.

    python concepts.py                 # build concepts.html and open it
    python concepts.py --apply "funny C3 C17; flat C9"

Charlie, 06/11/2026: "I think we need to start even broader. like find the funny
concepts". Every complaint since August - "contrived", "not funny", the airlock
brunch - was about the idea, not the prose, and the premise layer had never had
any human signal at all.

The page mixes the archive's own premises (published AND the ones that lost)
with concepts written from territories the ideate prompt never reaches, shuffled
so he judges blind. Each is recorded with its source and angle, so --apply can
report which TERRITORIES land, not only which lines.

Marks go to config/exemplars.yaml (funny) and config/flat_concepts.yaml (flat).
The overtuning guard is in run.sample_premises: ideate sees a handful of each,
drawn fresh daily, never the whole pool.
"""
from __future__ import annotations

import collections
import glob
import html
import os
import random
import re
import subprocess
import sys

import yaml

from common import append_yaml_list, read_json, rel, write_json

_INDEX = "data/concepts/index.json"
_PAGE = "concepts.html"
_FLAT = "config/flat_concepts.yaml"

#: The archive's crutch, recorded 06/11/2026: roughly half its premises turn on
#: an old rule, record or translation error ("bar" became "bear"). Tagged so a
#: round can show whether Charlie finds that device funny or tired.
_OLD_RULE = re.compile(r"\b(\d+-year-old|centur|ancient|mistransl|transcription|"
                       r"typo|clerical error|old (rule|law|order|record)|"
                       r"founding|charter|decree)", re.I)


def archive(n: int, seed: str) -> list[dict]:
    seen: dict[str, dict] = {}
    for f in sorted(glob.glob(rel("data/dispatches/*.json"))):
        r = read_json(f"data/dispatches/{os.path.basename(f)}") or {}
        pub = ((r.get("dispatch") or {}).get("premise") or "").strip()
        for d in ((r.get("quality") or {}).get("drafts") or []):
            p = (d.get("premise") or "").strip()
            if p and p not in seen:
                seen[p] = {"text": p, "date": r.get("run_date", ""),
                           "source": "published" if p == pub else "lost",
                           "angle": "old-rule" if _OLD_RULE.search(p) else "archive"}
    rng = random.Random(seed)
    pubs = [c for c in seen.values() if c["source"] == "published"]
    lost = [c for c in seen.values() if c["source"] == "lost"]
    half = n // 2
    return (rng.sample(pubs, min(half, len(pubs)))
            + rng.sample(lost, min(n - half, len(lost))))


def fresh() -> list[dict]:
    out = []
    for f in sorted(glob.glob(rel("data/concepts/fresh-*.yaml"))):
        doc = yaml.safe_load(open(f, encoding="utf-8")) or {}
        for c in doc.get("concepts") or []:
            out.append({"text": c["text"].strip(), "source": "fresh",
                        "angle": c.get("angle", "fresh"), "date": ""})
    return out


def render(items: list[dict]) -> str:
    rows = "".join(f'<li><span class="n">C{i}</span>{html.escape(c["text"])}</li>'
                   for i, c in enumerate(items, start=1))
    return f"""<meta charset="utf-8"><title>Aftertimes concepts</title>
<style>
body{{background:#eeece5;color:#1a1611;font:17px/1.55 Georgia,serif;max-width:46rem;
margin:0 auto;padding:2rem 1.25rem 5rem}}
h1{{font-size:1.4rem;margin:0 0 .3rem}} .lede{{color:#5c5347;margin:0 0 1.6rem}}
ol{{list-style:none;padding:0;margin:0}}
li{{margin:0 0 .9rem;padding-left:3rem;text-indent:-3rem}}
.n{{display:inline-block;width:2.6rem;text-indent:0;font:12px ui-monospace,monospace;
color:#9a8f7a}}
</style>
<h1>The Aftertimes - which ideas are funny?</h1>
<p class="lede">{len(items)} concepts, shuffled. Reply with numbers:
<code>funny C3 C17; flat C9</code>. Mark only what stands out.</p>
<ol>{rows}</ol>
"""


def apply(spec: str) -> int:
    index = read_json(_INDEX)
    if not index:
        raise SystemExit("no concepts index - run `python concepts.py` first")
    items = index["items"]
    marks = {"funny": [], "flat": []}
    for part in spec.split(";"):
        part = part.strip()
        if not part:
            continue
        kind = "flat" if part.lower().startswith("flat") else "funny"
        for tok in re.findall(r"C(\d+)", part, re.I):
            k = int(tok)
            if 1 <= k <= len(items):
                marks[kind].append(items[k - 1])
    append_yaml_list("config/exemplars.yaml", "exemplars",
                     [c["text"] for c in marks["funny"]])
    append_yaml_list(_FLAT, "concepts", [c["text"] for c in marks["flat"]])
    print(f"recorded {len(marks['funny'])} funny, {len(marks['flat'])} flat")
    shown = collections.Counter((c["source"], c["angle"]) for c in items)
    for kind in ("funny", "flat"):
        got = collections.Counter((c["source"], c["angle"]) for c in marks[kind])
        if got:
            print(f"\n{kind}, by where it came from:")
            for key, n in got.most_common():
                print(f"  {n} of {shown[key]:>2}  {key[0]:<10} {key[1]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--apply" in argv:
        return apply(" ".join(argv[argv.index("--apply") + 1:]))
    seed = "2026-11-06"
    items = archive(30, seed) + fresh()
    random.Random(seed).shuffle(items)
    os.makedirs(rel("data/concepts"), exist_ok=True)
    write_json(_INDEX, {"items": items})
    path = rel(_PAGE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render(items))
    by = collections.Counter(c["source"] for c in items)
    print(f"wrote {path}: {len(items)} concepts {dict(by)}")
    if "--no-open" not in argv:
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome):
            subprocess.Popen([chrome, path])
    return 0


if __name__ == "__main__":
    sys.exit(main())
