"""Batch-generate trial dispatches for Charlie to mark up, then harvest the
sentences he says are funny into a few-shot pool.

    python trial.py 10                # generate 10 trials
    python trial.py 10 --drafts 3     # ...with the full multi-draft pipeline
    python trial.py --render          # rebuild the mark-up page from what exists

Why this is not just `run.py` in a loop: run.py PUBLISHES. It writes index.html,
the permalink, the ledger, the bible and data/dispatches/<date>.json, and both it
and verdict.py key on the run DATE - so ten runs in one day would collide on one
key, trip already_filed(), and republish the live page ten times over an edition
subscribers already received. Trials therefore live in data/trials/, keyed by
slug, and touch nothing the site reads.

Illustration is skipped deliberately: the verdicts are about prose, and skipping
it saves a Cloudflare call per trial.

QUOTA: the binding constraint is the Gemini free tier, which 429s under heavy
same-day use and still has to serve the real cron. At the default --drafts 1
that is 2 calls per trial (ideate + write). At --drafts 3 it is 6. Progress is
saved after EACH trial, so a 429 half way costs you the rest of the batch, not
the batch - rerun and it tops up to the target rather than starting over.
"""
from __future__ import annotations

import glob
import html
import json
import os
import random
import re
import sys
import traceback
from datetime import date, datetime, timezone

from common import load_settings, load_yaml, read_json, rel, write_json
import bible as bible_mod
import critic
import ideate as ideate_stage
import ledger as ledger_mod
import selection as select_stage
import write as write_stage
from dates import sample_future_dateline
from run import _load_dotenv

TRIAL_DIR = "data/trials"
MARKUP_PAGE = "trials.html"

# Splits a body into sentences for numbering. Mirrors write.prose_report's
# closing-quote handling - a sentence ending inside quotes ("...bricks." he said)
# must not be merged with the next, or the numbering Charlie marks against will
# not line up with the sentences he can see.
# \s+ not " +" - bodies carry paragraph breaks, and splitting on spaces alone
# merged the last sentence of a paragraph with the first of the next, which
# would have thrown out the numbering Charlie marks against.
_SENT = re.compile(r'(?<=[.!?][")’\'])\s+|(?<=[.!?])\s+')


def split_sentences(body: str) -> list[str]:
    parts = [s.strip() for s in _SENT.split(body or "") if s and s.strip()]
    return parts


def existing() -> list[dict]:
    """Every trial on disk, oldest first."""
    out = []
    for path in sorted(glob.glob(rel(f"{TRIAL_DIR}/*.json"))):
        rec = read_json(f"{TRIAL_DIR}/{os.path.basename(path)}")
        if rec:
            out.append(rec)
    return out


def _slug(n: int) -> str:
    return f"t{n:03d}"


def _next_index() -> int:
    used = [int(os.path.basename(p)[1:4])
            for p in glob.glob(rel(f"{TRIAL_DIR}/t*.json"))
            if os.path.basename(p)[1:4].isdigit()]
    return (max(used) + 1) if used else 1


def generate_one(cfg: dict, rng: random.Random, n_drafts: int) -> dict:
    """One trial dispatch. Reads the live ledger/bible for anti-repeat context
    but never writes to them."""
    settings = cfg["settings"]
    ledger = cfg["ledger"]

    dateline = sample_future_dateline(date.today(), settings["dates"], set(), rng)
    domain = rng.choice(cfg["domains"])
    style = rng.choice(cfg["styles"])
    place_kind = rng.choice(cfg["place_kinds"])
    engine = rng.choice([e for e in cfg["engines"] if e["key"] != "bureaucratic"])

    motifs = bible_mod.random_slice(cfg["bible"],
                                    settings["ideate"]["bible_slice_size"], rng)
    avoid_headlines = ledger_mod.recent_headlines(
        ledger, settings["ideate"]["recent_premise_window"])
    premises = ideate_stage.ideate(
        dateline, domain, motifs, cfg["seeds"], avoid_headlines, settings,
        style["guidance"], engine["guidance"], place_kind["guidance"])

    chosen = select_stage.select_many(premises, ledger, settings, n_drafts)
    drafts = []
    for premise in chosen:
        try:
            drafts.append(write_stage.write(
                premise, dateline, domain, settings,
                style["guidance"], place_kind["guidance"]))
        except Exception as exc:  # noqa: BLE001 - one bad draft must not stop the batch
            print(f"      WARN draft failed: {exc}", file=sys.stderr)
    if not drafts:
        raise RuntimeError("every draft failed")

    context = {"years_from_now": dateline["years_from_now"],
               "engine": engine["key"]}
    scored = [(critic.score(d, context, settings["quality"]), d) for d in drafts]
    scored.sort(key=lambda pair: pair[0]["score"], reverse=True)
    best_score, best = scored[0]

    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "dispatch": best,
        "meta": {"dateline": dateline, "domain": domain,
                 "style": style["key"], "place_kind": place_kind["key"],
                 "engine": engine["key"], "n_drafts": len(drafts)},
        "critic": {"score": best_score["score"],
                   "violations": best_score["violations"]},
        "prose": write_stage.prose_report(best["body"]),
        "sentences": split_sentences(best["body"]),
        "funny": [],   # indices Charlie marks, filled in by mark.py
    }


def generate(target: int, n_drafts: int) -> int:
    settings = load_settings()
    cfg = {
        "settings": settings,
        "domains": load_yaml("config/domains.yaml")["domains"],
        "seeds": load_yaml("config/seed_premises.yaml")["seed_premises"],
        "styles": load_yaml("config/styles.yaml")["styles"],
        "place_kinds": load_yaml("config/places.yaml")["place_kinds"],
        "engines": load_yaml("config/engines.yaml")["engines"],
        "ledger": ledger_mod.load_ledger(),
        "bible": bible_mod.load_bible(),
    }
    rng = random.Random()
    made = 0
    idx = _next_index()
    for i in range(target):
        slug = _slug(idx)
        print(f">>> TRIAL {slug} ({i + 1}/{target})")
        try:
            rec = generate_one(cfg, rng, n_drafts)
        except Exception as exc:  # noqa: BLE001 - a 429 must not lose the batch
            print(f"    STOPPED: {type(exc).__name__}: {exc}", file=sys.stderr)
            print(f"    {made} trial(s) saved; rerun to top up.", file=sys.stderr)
            break
        rec["slug"] = slug
        write_json(f"{TRIAL_DIR}/{slug}.json", rec)
        m, p = rec["meta"], rec["prose"]
        print(f"    {rec['dispatch']['headline'][:64]}")
        print(f"    {m['dateline']['year']} / {m['domain']} / {m['style']} / "
              f"{m['engine']} | {p['words']}w mean {p['mean_sentence']}w | "
              f"critic {rec['critic']['score']}")
        made += 1
        idx += 1
    return made


def render() -> str:
    """A mark-up page: every sentence numbered so Charlie can say which landed."""
    trials = existing()
    rows = []
    for rec in trials:
        m = rec["meta"]
        sents = "".join(
            f'<li><span class="n">{rec["slug"]}.{i}</span> {html.escape(s)}</li>'
            for i, s in enumerate(rec["sentences"], start=1))
        rows.append(f"""
<article>
  <div class="tag">{html.escape(rec['slug'])} &middot; {m['dateline']['year']}
    ({m['dateline']['years_from_now']} yrs) &middot; {html.escape(m['domain'])}
    &middot; {html.escape(m['style'])} &middot; {html.escape(m['engine'])}
    &middot; critic {rec['critic']['score']}</div>
  <h2>{html.escape(rec['dispatch'].get('headline', ''))}</h2>
  <ol>{sents}</ol>
</article>""")
    page = f"""<meta charset="utf-8"><title>Aftertimes trials</title>
<style>
body{{background:#f4efe3;color:#1a1611;font:16px/1.6 Georgia,serif;
max-width:46rem;margin:0 auto;padding:2rem 1.25rem 6rem}}
h1{{font-size:1.5rem;border-bottom:2px solid #1a1611;padding-bottom:.4rem}}
.lede{{color:#5c5347;font-size:.95rem}}
article{{margin:2.5rem 0;padding-top:1.25rem;border-top:1px solid #d6cdb9}}
h2{{font-size:1.2rem;margin:.35rem 0 .75rem}}
.tag{{font:11px/1.4 ui-monospace,monospace;letter-spacing:.06em;
text-transform:uppercase;color:#7a2b2b}}
ol{{list-style:none;padding:0;margin:0}}
li{{margin:.45rem 0;padding-left:3.6rem;text-indent:-3.6rem}}
.n{{display:inline-block;width:3.2rem;text-indent:0;
font:11px ui-monospace,monospace;color:#9a8f7a}}
</style>
<h1>The Aftertimes &mdash; trial dispatches</h1>
<p class="lede">{len(trials)} trial(s). Tell me the sentence numbers that are
actually funny (e.g. <code>t001.4, t003.9</code>). Nothing here is published.</p>
{''.join(rows)}
"""
    path = rel(MARKUP_PAGE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return path


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    _load_dotenv()
    if "--render" in argv:
        print(f"wrote {render()} ({len(existing())} trials)")
        return 0
    nums = [a for a in argv if a.isdigit()]
    target = int(nums[0]) if nums else 5
    n_drafts = 1
    if "--drafts" in argv:
        n_drafts = int(argv[argv.index("--drafts") + 1])
    print("=" * 70)
    print(f"TRIAL BATCH - {target} dispatch(es), {n_drafts} draft(s) each")
    print(f"~{target * (1 + n_drafts)} Gemini calls; nothing published")
    print("=" * 70)
    made = generate(target, n_drafts)
    print(f"\n{made} trial(s) generated.")
    print(f"wrote {render()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
