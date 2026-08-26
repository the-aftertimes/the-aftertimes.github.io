"""Full pipeline orchestrator + stale fallback.

    python run.py

Sequence: pick a future date + domain -> ideate -> select -> write -> render,
then commit the dispatch to the archive, ledger and bible. Never crash-publishes:
on any failure it keeps the previous index.html and flags it stale."""
from __future__ import annotations

import glob
import os
import random
import sys
import traceback
from datetime import date, datetime, timedelta, timezone

from common import (load_common_words, load_settings, load_yaml,
                    locator_ceiling, read_json,
                    rel, write_json)
import archive as archive_mod
import avoid
import bible as bible_mod
import critic
import depict
import exemplars
import ideate as ideate_stage
import illustrate as illustrate_mod
import judge as judge_mod
import ledger as ledger_mod
import proposals
import render as render_mod
import revise as revise_mod
import selection as select_stage
import trends
import write as write_stage
from dates import sample_future_dateline

_STALE_MARKER = "Showing yesterday's dispatch"


def inject_stale_banner(output_html: str) -> bool:
    path = rel(output_html)
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as fh:
        doc = fh.read()
    if _STALE_MARKER in doc:
        return True
    banner = ("<div class='stale'>Showing yesterday's dispatch - today's edition "
              "did not file.</div>")
    marker = '<div class="wrap">'
    if marker in doc:
        doc = doc.replace(marker, marker + "\n    " + banner, 1)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(doc)
    return True


def choose_draft(drafts: list[dict], context: dict, qcfg: dict,
                 settings: dict) -> tuple[dict, dict]:
    """Score every draft, then let the model pick the funniest survivor. Returns
    (chosen dispatch, info) where info records the scores and how the choice was
    made. Never raises: a judge failure falls back to the top score, and if every
    draft is rejected the best of them is published anyway - a flawed dispatch
    beats no dispatch."""
    scored = [(d, critic.score(d, context, qcfg)) for d in drafts]
    for i, (d, s) in enumerate(scored, start=1):
        rules = ", ".join(v["rule"] for v in s["violations"]) or "clean"
        print(f"    draft {i}: score {s['score']} "
              f"{'REJECTED ' if s['rejected'] else ''}[{rules}]")
    survivors = [(d, s) for d, s in scored if not s["rejected"]]
    all_rejected = not survivors
    # A pool of ONE is not a choice - it is an election with a single candidate,
    # and the judge is never asked. 25/08/2026: two of three drafts were hard
    # rejected on legal_register, one of them for the word "court" in
    # "pickleball court", so the day's dispatch was decided by elimination and
    # Charlie said the article was not funny.
    #
    # So a draft rejected ONLY for a rule listed in judge_can_rescue is put back
    # in front of the judge when the pool is thin. Those rules are register
    # TASTE, and taste is exactly what the judge is for. Rules not listed -
    # structure, dash residue, US spelling - stay fatal, because they are
    # mechanical faults rather than opinions.
    rescuable = set(qcfg.get("judge_can_rescue") or ())
    if len(survivors) < 2 and rescuable:
        rescued = [(d, s) for d, s in scored
                   if s["rejected"] and s not in [x[1] for x in survivors]
                   and {v["rule"] for v in s["violations"] if v["rule"]
                        in set(qcfg["hard_reject"])} <= rescuable]
        if rescued:
            print(f"    only {len(survivors)} clean draft(s); putting "
                  f"{len(rescued)} rescuable one(s) back to the judge")
            survivors = survivors + rescued
    pool = sorted(survivors or scored, key=lambda pair: pair[1]["score"],
                  reverse=True)
    # Keep the FULL violation dicts and record which draft actually won, indexed
    # against the original `drafts` order. `pool` is re-sorted by score, so a bare
    # judge index would be meaningless to anything reading the record later (the
    # learning loop needs to know which premise and draft was published).
    info = {"scores": [s["score"] for _, s in scored],
            "violations": [s["violations"] for _, s in scored],
            # KEEP THE LOSING DRAFTS. Two thirds of what this paper writes was
            # being discarded unread, surviving only as a headline in a CI log
            # that expires. On 26/08/2026 Charlie read one of those log lines -
            # "Sentries Turn Missile Silo Into Pickleball Court" - and said it
            # sounded funny; the body was already gone. That is the single
            # signal the learning loop has never had, thrown away daily for
            # nothing. Costs a few kilobytes of JSON and no API calls.
            "drafts": [{"headline": d.get("headline", ""),
                        "body": d.get("body", ""),
                        "premise": d.get("premise", ""),
                        "score": s["score"], "rejected": s["rejected"]}
                       for d, s in scored],
            "all_rejected": all_rejected, "judge_reason": "", "judge_pick": None}

    def _finish(dispatch):
        for idx, (d, _) in enumerate(scored):
            if d is dispatch:
                info["chosen_index"] = idx
                break
        return dispatch, info

    if all_rejected:
        print("    WARN every draft was rejected; publishing the best of them",
              file=sys.stderr)
    # Do not spend a judge call on a pool where nothing passed - the spec calls
    # for a deterministic best-of-the-bad pick in that case.
    if qcfg.get("judge") and not all_rejected and len(pool) > 1:
        try:
            verdict = judge_mod.judge([d for d, _ in pool], settings)
            info["judge_reason"] = verdict["reason"]
            info["judge_pick"] = verdict["pick"]
            print(f"    judge picked {verdict['pick'] + 1}: {verdict['reason']}")
            return _finish(pool[verdict["pick"]][0])
        except Exception as exc:  # noqa: BLE001 - best effort
            print(f"    WARN judge failed ({exc}); using the top score",
                  file=sys.stderr)
    return _finish(pool[0][0])


def maybe_revise(dispatch: dict, context: dict, qcfg: dict,
                 settings: dict) -> tuple[dict, dict]:
    """Critique and rewrite, publishing the revision ONLY if it measures no worse
    than the draft. This makes the pass non-regressive: a rewrite that sands off
    the voice to satisfy the rules is discarded."""
    before = critic.score(dispatch, context, qcfg)
    info = {"revision_accepted": False, "score_before": before["score"],
            "score_after": None, "critique": ""}
    if not qcfg.get("revise"):
        return dispatch, info
    try:
        # Unwrapping and scoring stay INSIDE the try: if revise ever changes its
        # contract, a recoverable fault must not become a lost day.
        out = revise_mod.revise(dispatch, before["violations"], settings)
        after = critic.score(out["dispatch"], context, qcfg)
    except Exception as exc:  # noqa: BLE001 - best effort
        print(f"    WARN revise failed ({exc}); keeping the draft",
              file=sys.stderr)
        return dispatch, info
    info["critique"] = out["critique"]
    info["score_after"] = after["score"]
    # ABSOLUTE gate first: a structurally broken revision is never publishable,
    # whatever it scores. Relative comparison cannot protect us here - because the
    # score floors at 0.0, a three-word stub actually scores HIGHER (0.17) than a
    # badly flawed full draft (0.0) and would otherwise be "an improvement".
    structural = [v for v in after["violations"] if v["rule"] == "structure"]
    if structural:
        print("    revision discarded, structurally unusable: "
              + "; ".join(v["detail"] for v in structural), file=sys.stderr)
        return dispatch, info
    # Never trade a clean draft for a rejected revision, whatever the scores say.
    if after["rejected"] and not before["rejected"]:
        print("    revision discarded, it breaks a hard rule the draft did not")
        return dispatch, info
    improved = (after["score"] > before["score"] if before["score"] == 0.0
                else after["score"] >= before["score"])
    if improved:
        info["revision_accepted"] = True
        print(f"    revision accepted ({before['score']} -> {after['score']})")
        return out["dispatch"], info

    # The revision measures worse - but the deterministic score cannot see the
    # thing the revision was written to fix.
    #
    # 22/08/2026 is the case that forced this. All three drafts scored a perfect
    # 1.0, the critique correctly said "the final line restated the setup instead
    # of escalating the joke", the rewrite fixed it and scored 0.92 on ONE minor
    # violation, and the gate threw it away. Charlie then read the published
    # piece and said the final line was not funny. From a 1.0 draft the old gate
    # could only ever accept a score-neutral rewrite, so the revise pass was
    # structurally incapable of improving the comedy on exactly the days the
    # prose was already clean.
    #
    # So the score now VETOES the unpublishable rather than arbitrating the
    # funny: structural faults and new hard rejects are still absolute (above),
    # a large drop still auto-rejects, and inside the tolerance the judge - which
    # already picks the funniest of the drafts - is asked to compare the two.
    # Some minor faults are taste the judge may trade for a better joke; others
    # are house rules that a joke does not buy. The first reedit dry run on
    # 22/08/2026 produced "Tycho Mayor Dies At 84, Exposed As Secretly Capable" -
    # nine words against a seven-word cap Charlie has stated repeatedly and given
    # worked examples for - and the tolerance would have let it through, because
    # headline_length is only a minor.
    never = set(qcfg.get("revise_judge_never") or ())
    blocking = sorted({v["rule"] for v in after["violations"]
                       if v["rule"] in never}
                      - {v["rule"] for v in before["violations"]})
    if blocking:
        print(f"    revision discarded, breaks a rule a joke cannot buy: "
              f"{', '.join(blocking)}")
        return dispatch, info

    drop = before["score"] - after["score"]
    tolerance = qcfg.get("revise_judge_tolerance", 0.0)
    if not qcfg.get("judge") or drop > tolerance:
        print(f"    revision discarded, measures worse "
              f"({before['score']} -> {after['score']})")
        return dispatch, info
    try:
        # Order is fixed at [draft, revision], so any positional bias in the
        # model favours KEEPING the draft. That is the conservative direction and
        # is preferred to shuffling, which would make a run harder to read back.
        verdict = judge_mod.judge([dispatch, out["dispatch"]], settings)
    except Exception as exc:  # noqa: BLE001 - best effort; the draft is fine
        print(f"    WARN revise-judge failed ({exc}); keeping the draft",
              file=sys.stderr)
        return dispatch, info
    info["revise_judge_reason"] = verdict["reason"]
    if verdict["pick"] == 1:
        info["revision_accepted"] = True
        print(f"    revision accepted on the judge's call despite "
              f"{before['score']} -> {after['score']}: {verdict['reason'][:80]}")
        return out["dispatch"], info
    print(f"    revision discarded, judge preferred the draft: "
          f"{verdict['reason'][:80]}")
    return dispatch, info


def maybe_write_proposals(records: list[dict], lcfg: dict,
                          today: date) -> str | None:
    """On the configured weekday, write the weekly prompt-proposal document.

    Wired 26/08/2026. `proposals.py` had been written, documented and tested for
    a month and NOTHING called it - `learning.proposals_weekday: 0` pointed at a
    Monday run that did not exist. The choice was wire it or delete it, and
    wiring won on cost: it is a pure function over records already in memory, so
    it spends no API call and adds no failure mode to the publish path.

    It proposes; it never applies. That is the whole design - an unattended
    process editing the house voice is the highest-blast-radius change available.
    Returns the path written, or None.
    """
    if not lcfg.get("enabled") or today.weekday() != lcfg.get("proposals_weekday", 0):
        return None
    try:
        window = avoid.recent(records, lcfg["window"])
        hits = trends.detect(window, lcfg["min_count"])
        doc = proposals.build(records, read_json("data/verdicts.json", {}) or {},
                              hits)
    except Exception as exc:  # noqa: BLE001 - a weekly nicety must never take
        print(f"    WARN proposals failed ({exc}); skipping",  # down the publish
              file=sys.stderr)
        return None
    path = "docs/proposals.md"
    os.makedirs(os.path.dirname(rel(path)), exist_ok=True)
    with open(rel(path), "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"    wrote {path} ({len(hits)} over-used items)")
    return path


def build_avoid_block(records: list[dict], lcfg: dict) -> str:
    """The 'recently over-used' block, or an empty string. Never raises: a
    staleness-detection fault must not be able to stop the paper publishing."""
    if not lcfg.get("enabled"):
        return ""
    try:
        window = avoid.recent(records, lcfg["window"])
        return avoid.render(trends.detect(window, lcfg["min_count"]), lcfg)
    except Exception as exc:  # noqa: BLE001 - decorative, never fatal
        print(f"    WARN trend spotting failed ({exc}); no avoid block",
              file=sys.stderr)
        return ""


def run_pipeline() -> dict:
    settings = load_settings()
    domains = load_yaml("config/domains.yaml")["domains"]
    seeds = load_yaml("config/seed_premises.yaml")["seed_premises"]
    styles = load_yaml("config/styles.yaml")["styles"]
    place_kinds = load_yaml("config/places.yaml")["place_kinds"]
    engines = load_yaml("config/engines.yaml")["engines"]
    ledger = ledger_mod.load_ledger()
    bible = bible_mod.load_bible()
    rng = random.Random()

    run_dt = datetime.now(timezone.utc)
    run_date = run_dt.date().isoformat()
    today = date.today()

    ac = settings["dates"]["anti_cluster"]
    eras = ledger_mod.recent_eras(ledger, ac["avoid_recent_days"])
    dateline = sample_future_dateline(today, settings["dates"], eras, rng)
    recent_doms = set(ledger_mod.recent_domains(ledger, ac["avoid_recent_days"]))
    domain = rng.choice([d for d in domains if d not in recent_doms] or domains)
    recent_styles = {e.get("style") for e in ledger[-ac["avoid_recent_days"]:]}
    style = rng.choice([s for s in styles if s["key"] not in recent_styles] or styles)
    recent_places = {e.get("place_kind") for e in ledger[-ac["avoid_recent_days"]:]}
    place_kind = rng.choice(
        [p for p in place_kinds if p["key"] not in recent_places] or place_kinds)
    recent_engines = {e.get("engine") for e in ledger[-ac["avoid_recent_days"]:]}
    # The bureaucratic engine is the over-used register (see config/engines.yaml),
    # so cap how often it can be drawn at all rather than relying on anti-repeat.
    pool = [e for e in engines
            if e["key"] not in recent_engines
            and not (e["key"] == "bureaucratic" and rng.random() > 0.25)]
    engine = rng.choice(pool or [e for e in engines if e["key"] != "bureaucratic"]
                        or engines)
    print(f">>> DATE {dateline['year']} ({dateline['years_from_now']} yrs) / "
          f"{domain} / {style['key']} / {place_kind['key']} / {engine['key']}")

    lcfg = settings.get("learning", {"enabled": False})
    past = [read_json(f"data/dispatches/{os.path.basename(f)}")
            for f in sorted(glob.glob(rel("data/dispatches/*.json")))]
    records = [p for p in past if p]
    avoid_block = build_avoid_block(records, lcfg)
    maybe_write_proposals(records, lcfg, date.today())
    if avoid_block:
        print(f"    avoid block: {len(avoid_block)} chars")

    pool = load_yaml("config/exemplars.yaml").get("exemplars") or []
    seeds_plus = seeds + [p for p in pool if p not in seeds]
    # Sentences Charlie marked funny - the project's only taste memory between
    # days. Injected as few-shot evidence of a TECHNIQUE, not material to copy.
    funny_lines = load_yaml("config/funny_lines.yaml").get("lines") or []
    if funny_lines:
        print(f"    funny-line pool: {len(funny_lines)} line(s)")

    print(">>> IDEATE")
    motifs = bible_mod.random_slice(bible, settings["ideate"]["bible_slice_size"], rng)
    avoid_headlines = ledger_mod.recent_headlines(
        ledger, settings["ideate"]["recent_premise_window"])
    premises = ideate_stage.ideate(dateline, domain, motifs, seeds_plus,
                                    avoid_headlines, settings,
                                    style["guidance"], engine["guidance"],
                                    place_kind["guidance"], avoid_block=avoid_block)
    print(f"    {len(premises)} premises")

    qcfg = settings["quality"]
    context = {"years_from_now": dateline["years_from_now"],
               "engine": engine["key"],
               "common_words": load_common_words()}

    print(">>> SELECT")
    chosen_premises = select_stage.select_many(
        premises, ledger, settings, qcfg["n_drafts"])
    print(f"    {len(chosen_premises)} premises chosen")

    print(">>> WRITE")
    drafts = []
    for i, premise in enumerate(chosen_premises, start=1):
        try:
            drafts.append(write_stage.write(
                premise, dateline, domain, settings,
                style["guidance"], place_kind["guidance"],
                avoid_block=avoid_block, funny_lines=funny_lines))
            print(f"    draft {i}: {drafts[-1]['headline'][:56]}")
        except Exception as exc:  # noqa: BLE001 - one bad draft must not stop us
            print(f"    WARN draft {i} failed: {exc}", file=sys.stderr)
    if not drafts:
        raise RuntimeError("every draft failed")

    print(">>> CHOOSE")
    dispatch, choose_info = choose_draft(drafts, context, qcfg, settings)

    print(">>> REVISE")
    dispatch, revise_info = maybe_revise(dispatch, context, qcfg, settings)
    pr = write_stage.prose_report(dispatch["body"])
    # The decode rate is logged even when it is clean, unlike the violation,
    # which only speaks up past the threshold. Charlie's complaint on 17/08/2026
    # was that the paper had drifted archaic over WEEKS - a number that appears
    # only once it is already too high cannot show a trend.
    rare = critic.rare_words(dispatch["body"], context["common_words"])
    pr["rare_words"] = len(rare)
    pr["rare_rate"] = round(100.0 * len(rare) / max(1, pr["words"]), 1)
    print(f"    final: {dispatch['headline'][:60]}")
    print(f"    prose: {pr['words']}w / mean {pr['mean_sentence']}w / "
          f"longest {pr['longest']}w / {pr['short_sentences']} short / "
          f"{pr['rare_rate']}% to decode")

    print(">>> ILLUSTRATE")
    # A structured visual brief beats the writer's scene line, which is prose
    # written for a reader rather than a renderer. Returns None on any failure
    # and illustrate falls back, so this can cost a better picture but never the
    # picture. One extra Gemini call.
    brief = depict.depict(dispatch, settings)
    if brief:
        print(f"    brief: {', '.join(f for f in depict.FIELDS if brief.get(f))}")
    dispatch["brief"] = brief
    dispatch["image"] = illustrate_mod.generate(dispatch, run_date, settings, brief)
    print(f"    image: {dispatch['image'] or 'none (fallback)'}")

    print(">>> RENDER")
    meta = {
        "run_time": run_dt.isoformat(),
        "timezone": settings["timezone"],
        "tagline": settings["site"]["tagline"],
        "site_name": settings["site"]["name"],
        "base_url": settings["site"]["base_url"],
        "signup_form_url": settings.get("signup_form_url", ""),
        "edition": len(ledger) + 1,
        "locator_deep_max": locator_ceiling(settings),
    }
    with open(rel(settings["output_html"]), "w", encoding="utf-8") as fh:
        fh.write(render_mod.render_dispatch(dispatch, meta, stale=False))
    perma = f"d/{run_date}.html"
    os.makedirs(rel("d"), exist_ok=True)
    with open(rel(perma), "w", encoding="utf-8") as fh:
        fh.write(render_mod.render_dispatch(dispatch, meta, is_permalink=True))
    print(f"    wrote {settings['output_html']} + {perma}")

    print(">>> RECORD")
    record = {"run_date": run_date, "run_time": run_dt.isoformat(),
              "dispatch": dispatch, "meta": meta,
              # `prose` was printed but never stored, so "has the paper drifted
              # archaic or long-winded?" could only be answered by re-measuring
              # every body. It is stored now, decode rate included, because that
              # is the question Charlie actually asked on 17/08/2026.
              "quality": {"n_drafts": len(drafts), **choose_info,
                          **revise_info, "prose": pr}}
    write_json(f"data/dispatches/{run_date}.json", record)
    ledger_mod.save_ledger(ledger_mod.append_entry(
        ledger, run_date, dateline, domain, dispatch["headline"],
        settings["dates"]["anti_cluster"]["era_bucket_years"], style["key"],
        place_kind["key"], engine["key"]))
    bible_mod.save_bible(bible_mod.merge_glossary(bible, dispatch["glossary"], run_date))
    print(f"    archived {run_date}; ledger={len(ledger)}; motifs={len(bible['motifs'])}")

    archive_mod.build()
    print("    rebuilt archive.html")
    return record


def _load_dotenv() -> None:
    """Best-effort: load KEY=VALUE lines from a gitignored .env for local runs.
    CI supplies GEMINI_API_KEY via the environment instead, so this is a no-op there."""
    path = rel(".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def already_filed(run_date: str) -> bool:
    """True if a dispatch has already been filed for this UTC date.

    GitHub silently DROPS scheduled runs (it dropped 06/08/2026 entirely), so
    daily.yml carries a backup cron later the same UTC day. Without this guard
    that backup would file a SECOND, different dispatch over the top of the one
    subscribers were already emailed - send_email.py's own per-date guard would
    suppress the email, leaving the live page and the edition in their inbox
    telling different stories."""
    return os.path.exists(rel(f"data/dispatches/{run_date}.json"))


#: How far back the picture fill-in will look. Bounded on purpose: this runs on
#: the publish path and draws at most ONE image per run, so it cannot turn a
#: backlog into a quota stampede that starves the day's own dispatch.
_FILL_LOOKBACK_DAYS = 4


def _newest_pictureless(run_date: str) -> str | None:
    """The dispatch most in need of a picture: today if it lacks one, else the
    oldest gap within the lookback window. Returns None when all are fine."""
    start = date.fromisoformat(run_date)
    candidates = [(start - timedelta(days=n)).isoformat()
                  for n in range(_FILL_LOOKBACK_DAYS)]
    gaps = []
    for d in candidates:
        rec = read_json(f"data/dispatches/{d}.json")
        if rec and not (rec.get("dispatch") or {}).get("image"):
            gaps.append(d)
    if not gaps:
        return None
    # Today first if it is one of them - the front page is what a reader sees.
    return run_date if run_date in gaps else min(gaps)


def fill_missing_image(run_date: str) -> bool:
    """Draw the picture for a day that published without one. Returns True if it
    actually drew something.

    Deliberately narrow. It touches the image, the record's brief and the
    rendered pages - never the prose - so the backup cron cannot rewrite an
    edition that has already gone out. Everything about it is best-effort: a
    second failure just leaves the day as it already was.
    """
    target = _newest_pictureless(run_date)
    if not target:
        print("    picture present; nothing to do.")
        return False
    if target != run_date:
        # A dispatch that misses its picture and then rolls over the UTC date is
        # orphaned: the next run looks only at ITS own day and never comes back.
        # 26/08/2026 was minutes from exactly that - the day published with no
        # engraving because Cloudflare's allocation was spent, and the allocation
        # resets before the next cron. Look back a few days, oldest gap first.
        print(f"    filling an OLDER gap: {target}")
    print("    NO PICTURE on a filed dispatch - attempting the illustration only")
    try:
        import reillustrate
        return reillustrate.reillustrate(target) == 0
    except Exception as exc:  # noqa: BLE001 - a failed retry must not fail the job
        print(f"    fill-in failed ({type(exc).__name__}: {exc}); leaving as is",
              file=sys.stderr)
        return False


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    _load_dotenv()
    print("=" * 70)
    print("THE AFTERTIMES - daily dispatch")
    print("=" * 70)
    run_date = datetime.now(timezone.utc).date().isoformat()
    if already_filed(run_date) and "--force" not in argv:
        print(f"Dispatch for {run_date} is already filed.")
        # ...but "filed" is not the same as "complete". The picture can fail on
        # its own while the words publish fine, and until 26/08/2026 the 22:13
        # backup cron - which exists precisely to catch a dropped primary - would
        # print "nothing to do" and leave the day pictureless. 25/08 published
        # with no engraving and nobody found out until Charlie looked.
        #
        # The illustration is the ONLY thing retried here. Re-running the whole
        # pipeline would rewrite a published edition, which is what already_filed
        # is there to prevent.
        if fill_missing_image(run_date):
            return 0
        print("(Pass --force to regenerate and overwrite it.)")
        return 0
    try:
        run_pipeline()
        print("\nOK - fresh dispatch filed.")
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level guard, never crash-publish
        print(f"\nPIPELINE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        settings = load_settings()
        if inject_stale_banner(settings["output_html"]):
            print("FALLBACK - kept previous page, flagged stale.", file=sys.stderr)
            return 0
        print("FALLBACK - no previous page; nothing to publish.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
