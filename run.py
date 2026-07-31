"""Full pipeline orchestrator + stale fallback.

    python run.py

Sequence: pick a future date + domain -> ideate -> select -> write -> render,
then commit the dispatch to the archive, ledger and bible. Never crash-publishes:
on any failure it keeps the previous index.html and flags it stale."""
from __future__ import annotations

import os
import random
import sys
import traceback
from datetime import date, datetime, timezone

from common import load_settings, load_yaml, read_json, rel, write_json
import archive as archive_mod
import bible as bible_mod
import ideate as ideate_stage
import illustrate as illustrate_mod
import ledger as ledger_mod
import render as render_mod
import selection as select_stage
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
    engine = rng.choice(
        [e for e in engines if e["key"] not in recent_engines] or engines)
    print(f">>> DATE {dateline['year']} ({dateline['years_from_now']} yrs) / "
          f"{domain} / {style['key']} / {place_kind['key']} / {engine['key']}")

    print(">>> IDEATE")
    motifs = bible_mod.random_slice(bible, settings["ideate"]["bible_slice_size"], rng)
    avoid = ledger_mod.recent_headlines(ledger, settings["ideate"]["recent_premise_window"])
    premises = ideate_stage.ideate(dateline, domain, motifs, seeds, avoid, settings,
                                    style["guidance"], engine["guidance"])
    print(f"    {len(premises)} premises")

    print(">>> SELECT")
    premise = select_stage.select(premises, ledger, settings)
    print(f"    chosen: {premise[:70]}")

    print(">>> WRITE")
    dispatch = write_stage.write(premise, dateline, domain, settings,
                                 style["guidance"], place_kind["guidance"])
    print(f"    headline: {dispatch['headline'][:60]}")

    print(">>> ILLUSTRATE")
    dispatch["image"] = illustrate_mod.generate(dispatch, run_date, settings)
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
        "locator_deep_max": settings["dates"]["bands"]["deep"][1],
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
              "dispatch": dispatch, "meta": meta}
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


def main() -> int:
    _load_dotenv()
    print("=" * 70)
    print("THE AFTERTIMES - daily dispatch")
    print("=" * 70)
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
