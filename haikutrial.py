"""Throwaway harness for the haiku pivot: generate poems, and compare picture styles.

    python haikutrial.py poems 24     # one Gemini call, 24 haiku, sieved
    python haikutrial.py styles       # one scene drawn in every candidate style

Writes only into data/trials/haiku/ and never touches anything the site reads,
for the same reason trial.py does not: run.py keys on the run DATE and publishes.

Both halves need credentials that live only in GitHub secrets, so this is driven
by .github/workflows/haikutrial.yml rather than from the laptop.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import datetime, timezone

import dates as dates_mod
import depict
import gemini
import haiku as haiku_mod
import illustrate
import run as run_mod
import urllib.request
from common import load_settings, rel

OUT = "data/trials/haiku"

#: 40, not 24. THIS IS THE POINT OF THE FORM, so use it: the batch is ONE call
#: whatever the count, and the sieve throws most of it away by design. The
#: 09/09/2026 register fix cut the scan rate from 17/24 to 7/24 because a longer
#: prompt buries the syllable rule - worth fixing at the prompt (it now ends on
#: that rule) AND worth out-running, because forty candidates at a 30% scan rate
#: still leaves twelve to judge, which is three times what the prose pipeline
#: ever managed on four whole Gemini calls.
DEFAULT_COUNT = 40


# --------------------------------------------------------------------------
# Picture styles
#
# Charlie, 07/09/2026: "we also need to make the images either more absurd or
# more realistic. either way less ai sloppy."
#
# The diagnosis first, because it decides the options. The live style asks
# flux-1-schnell for "fine black ink linework and dense cross-hatching... rich
# background detail" in the manner of Gustave Dore. That is close to the most
# demanding thing you can ask a FOUR-STEP distilled model for: fine repeated
# high-frequency line, over a whole frame, plus faces. It has nowhere near
# enough steps to resolve it, so it approximates hatching with a smooth grey
# mush and approximates faces with the waxy averages Charlie is reading as "AI
# sloppy". The sloppiness is not a prompt-wording problem, it is a request the
# model cannot fill.
#
# So every candidate below asks for LESS resolution rather than more, in a
# different direction:
#   - woodcut and stencil remove the fine line entirely and work in flat black
#     shapes, which four steps CAN hold.
#   - ligne-claire keeps line but makes it uniform and sparse.
#   - blueprint and plate avoid the human face, which is where the uncanny
#     lives, and lean the "more absurd" way by making the object the subject.
#   - photo is the "more realistic" pole, honestly represented so the choice is
#     informed rather than assumed away.
#
# A haiku is one image, so a quieter picture also fights the poem less than a
# dense engraving does.
STYLES = {
    "dore": (
        "A documentary wood engraving in the style of Gustave Dore, as a "
        "newspaper illustration of a real event that was actually witnessed. "
        "Fine black ink linework and dense cross-hatching on aged paper, a "
        "single clear focal subject, figures in a believable environment, rich "
        "background detail."),
    "woodcut": (
        "A bold black and white woodcut print. Large flat areas of solid black "
        "against bare white paper, thick confident carved edges, almost no fine "
        "detail, high contrast, a single simple silhouette reading clearly at "
        "arm's length. Rough hand-cut texture where the blade left the block."),
    "ligne-claire": (
        "A clean line drawing in uniform thin black ink on white, ligne claire: "
        "every edge one steady line of the same weight, no hatching, no shading, "
        "no texture, large areas of plain white, calm and precise, like a "
        "technical illustrator drawing an ordinary scene."),
    "stencil": (
        "A two-tone stencil print in solid black on bare paper. Shapes reduced to "
        "flat cut-out masses with hard edges and no interior detail, strong "
        "negative space, the whole image readable as a silhouette."),
    "blueprint": (
        "A plain engineering elevation drawing of a single object, white line on "
        "deep blue ground, orthographic, no perspective, no people, thin uniform "
        "line weight, construction lines and section marks, the object drawn "
        "flatly as a thing that was manufactured."),
    # KEPT, AND THE HOUSE STYLE STAYS THIS, 09/09/2026. Charlie: "why can't we
    # stick with current picture style?" - and the answer is that we can. The
    # measured gap is real (29.5% smooth grey against woodcut's 2.8%) but it
    # describes a LOOK, not the fault he reported: the hairdryer-hood head and
    # the mirrored space helmet were both failures of the FIGURE, and both were
    # drawn in this style. Forty published dispatches carry it, so switching
    # makes the back catalogue a different paper, and the engraving is the half
    # of the design nobody has ever complained about.
    #
    # The two below are the actual lever - ask this style to draw LESS. The
    # haiku pivot hands that over for nothing, because the picture is now one
    # object rather than a person doing something inside a 230-word story, and
    # a face is where the sloppiness lived.
    "dore-object": (
        "A documentary wood engraving in the style of Gustave Dore, as a "
        "newspaper illustration. Fine black ink linework and cross-hatching on "
        "bare paper. ONE object, alone, filling the frame, resting on a plain "
        "surface. No people, no faces, no hands, no figures of any kind. Plain "
        "empty background, no scenery, no clutter."),
    "dore-object-plate": (
        "A single object drawn as a plate in a nineteenth-century catalogue: "
        "wood-engraved black ink linework and cross-hatching on bare paper, the "
        "object isolated dead centre against blank paper, drawn straight on, "
        "described exactly and without drama. No people, no faces, no hands, no "
        "background, no shadow, no setting."),
    "photo": (
        "A black and white documentary photograph on 35mm film, available light, "
        "slight grain, shallow depth of field, an ordinary unposed working "
        "moment caught by a press photographer. Plain, undramatic, real."),
}

#: One fixed scene for the comparison, so STYLE is the only thing that varies.
#: Derived from a haiku rather than from a dispatch, because that is what these
#: pictures will have to be drawn from.
#: Now an OBJECT, not a scene with a worker in it - drawn from a real haiku
#: ("the cloud licence clerk / stamps the thunderstorm for noon / dry rain takes
#: two weeks"), because that is what these pictures have to be drawn from once
#: the paper is poems.
STYLE_SCENE = ("A heavy desk stamp for approving weather, cast in dull metal "
               "with a thick handle and a wide flat die, set down on a bare "
               "counter beside a shallow tray of ink.")

_NO_TEXT = ("Absolutely no text, letters, words, captions, numbers, signatures "
            "or watermark - purely pictorial. No border, frame, margin or plate "
            "mark. Everyone fully dressed for work, upright, whole body covered.")


def models() -> None:
    """Print every model this key can actually see, and what it supports.

    ENUMERATE, DO NOT GUESS. 09/09/2026: needing a model with its own daily
    quota, the obvious sibling name was tried from memory and came back 404
    "models/gemini-2.5-flash is no longer available to new users". A guessed
    model name costs a whole CI round trip to disprove; the list endpoint costs
    one read and settles it."""
    settings = load_settings()
    url = f"{settings['gemini']['endpoint'].rsplit('/', 1)[0]}/models"
    with urllib.request.urlopen(
            f"{url}?key={gemini._api_key()}&pageSize=200", timeout=30) as resp:
        data = json.load(resp)
    rows = []
    for m in data.get("models", []):
        methods = m.get("supportedGenerationMethods") or []
        if "generateContent" in methods:
            rows.append(m.get("name", "").replace("models/", ""))
    print(f">>> {len(rows)} models support generateContent on this key")
    for name in sorted(rows):
        print(f"      {name}")


#: The two register faults measured in the first batch (09/09/2026): 64% of the
#: seventeen surviving haiku carried a bleak word and 64% a pre-industrial prop.
#: Counted on every batch from now on, because "it feels grim" is not something a
#: prompt change can be judged against and a percentage is.
_BLEAK = re.compile(
    r"\b(dead|death|dies|dying|corpse|bone|teeth|rot|rots|lime|grave|hunger|"
    r"hungry|ration\w*|scrap\w*|dust|grey|gray|cold|frost|starv\w*|disease|"
    r"sick|wound|ache|weary|exhaust\w*|mourn\w*|grief|ash|ruin\w*)\b", re.I)
_PREINDUSTRIAL = re.compile(
    r"\b(shovel\w*|rake\w*|spade|cart|carts|quilt\w*|kelp|cabbage|barge|"
    r"boiler|grease|knife|knives|salt|brine|soot|alley|pier|crate|vat|vats|"
    r"wick|lamp|lantern|rope|sack\w*|timber|coal|cinder|anvil|forge|loom)\b",
    re.I)


def _register(kept: list[dict]) -> dict:
    """How much of a batch is bleak, and how much of it reads as the past."""
    n = max(1, len(kept))
    bleak = sum(1 for h in kept if _BLEAK.search(" ".join(h["lines"])))
    old = sum(1 for h in kept if _PREINDUSTRIAL.search(" ".join(h["lines"])))
    return {"n": len(kept), "bleak": bleak, "preindustrial": old,
            "bleak_pct": round(100 * bleak / n), "preindustrial_pct": round(100 * old / n)}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


#: Trials MUST NOT draw on the model the paper publishes with. Settled
#: 09/09/2026: the free-tier quota is
#: `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, value 20 - twenty calls
#: a DAY, and crucially per MODEL. The prose pipeline spends 8 to 13 of those on
#: a generating run, so every trial run this session was competing with the
#: paper for the same twenty and losing. A sibling model gives trials their own
#: twenty and makes it impossible for a trial to cost the paper an edition,
#: which trial.py's docstring has warned about since August without being able
#: to prevent it.
#:
#: A LIST, NOT A NAME, because being listed is not being usable. `gemini-2.5-flash`
#: appears in this key's own models listing and still answers 404 "no longer
#: available to new users" - so enumerating was necessary and not sufficient.
#: Each dead name now costs exactly one call (a non-429 4xx is not retried), so
#: walking a short list is cheaper than another round trip per guess. Ordered
#: newest-first: these are siblings of the published model, not the Pro tier,
#: which settings.yaml records as having zero free quota.
TRIAL_MODELS = ("gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite",
                "gemini-flash-latest")


def _generate_on_a_spare_model(prompt: str, settings: dict, temperature: float,
                               model: str | None = None):
    """Return (raw, model), trying each candidate until one answers."""
    tried = []
    for name in ((model,) if model else TRIAL_MODELS):
        try:
            return gemini.generate(prompt, settings, temperature,
                                   model=name), name
        except gemini.GeminiError as exc:
            tried.append(name)
            print(f"    {name}: {str(exc)[:120]}", file=sys.stderr)
    raise gemini.GeminiError(f"no trial model answered; tried {tried}")


def poems(count: int, model: str | None = None) -> None:
    settings = load_settings()
    model = (model or "").strip() or None
    dateline = dates_mod.sample_future_dateline(
        datetime.now(timezone.utc).date(), settings["dates"], set())
    prompt = haiku_mod.build_prompt(dateline, "", count)
    print(f">>> HAIKU {count} datelined {dateline['year']} "
          f"({dateline['years_from_now']} years out)")
    raw, model = _generate_on_a_spare_model(
        prompt, settings, settings["gemini"].get("temperature_ideate", 1.1),
        model)
    print(f"    served by {model}")
    data = gemini.extract_json(raw)
    if isinstance(data, dict) and data.get("place"):
        dateline["place"] = str(data["place"]).strip()
    got = haiku_mod.parse(data)
    print(f"    parsed {len(got)} of {count}, place {dateline['place']!r}")

    # Report the DENOMINATOR at every stage. A sieve that reports only what
    # survived cannot tell "the model wrote badly" from "the counter is wrong",
    # and the syllable counter here is a measured heuristic, not an oracle.
    kept, failed = [], []
    for h in got:
        counts = [haiku_mod.line_syllables(l) for l in h["lines"]]
        (kept if counts == list(haiku_mod.PATTERN) else failed).append(
            {**h, "counts": counts})
    print(f"    {len(kept)} scan 5-7-5, {len(failed)} do not")
    reg = _register(kept)
    print(f"    register: {reg['bleak']}/{reg['n']} bleak ({reg['bleak_pct']}%), "
          f"{reg['preindustrial']}/{reg['n']} pre-industrial "
          f"({reg['preindustrial_pct']}%)  [first batch: 64% and 64%]")

    os.makedirs(rel(OUT), exist_ok=True)
    stamp = _stamp()
    record = {"generated": stamp, "dateline": dateline, "asked": count,
              "model": model, "register": reg, "asked_count": count,
              "parsed": len(got), "kept": kept, "failed": failed}
    with open(rel(f"{OUT}/{stamp}.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, ensure_ascii=False)
    _render_poems(record, stamp)
    for h in kept:
        print("      " + " / ".join(h["lines"]))


def _render_poems(record: dict, stamp: str) -> None:
    d = record["dateline"]

    def block(h, dim=False):
        lines = "<br>".join(html.escape(l) for l in h["lines"])
        note = ("<span class=n>" + "-".join(str(c) for c in h["counts"]) +
                "</span>") if dim else ""
        return (f"<li><b>{html.escape(h.get('title') or '')}</b>{note}"
                f"<p>{lines}</p></li>")

    body = (f"<h2>Scans 5-7-5 ({len(record['kept'])})</h2><ol>"
            + "".join(block(h) for h in record["kept"]) + "</ol>"
            + f"<h2>Did not scan ({len(record['failed'])})</h2><ol>"
            + "".join(block(h, True) for h in record["failed"]) + "</ol>")
    page = f"""<!doctype html><meta charset=utf-8>
<title>Haiku trial {stamp}</title>
<style>
body{{background:#eeece5;color:#1b1a17;font:16px/1.5 Iowan Old Style,Palatino,Georgia,serif;
margin:0;padding:2rem 1.2rem;}}
.wrap{{max-width:44rem;margin:0 auto;}}
h1{{font-size:1.4rem;margin:0 0 .2rem;}}
.sub{{color:#6b6659;font-size:.85rem;margin:0 0 2rem;}}
h2{{font-size:.8rem;text-transform:uppercase;letter-spacing:.12em;color:#6b6659;
margin:2.4rem 0 1rem;}}
ol{{list-style:none;padding:0;margin:0;
display:grid;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));gap:1.6rem;}}
li{{border-top:1px solid #d5d1c4;padding-top:.7rem;}}
b{{font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;color:#6b6659;
font-weight:600;}}
p{{margin:.5rem 0 0;font-size:1.08rem;}}
.n{{float:right;font-size:.7rem;color:#a09a8c;letter-spacing:0;}}
</style><div class=wrap>
<h1>Haiku trial</h1>
<p class=sub>{html.escape(str(d['place']))}, {d['year']} &middot;
{d['years_from_now']} years from now &middot; asked {record['asked']},
parsed {record['parsed']}, scanned {len(record['kept'])}</p>
{body}</div>"""
    with open(rel(f"{OUT}/{stamp}.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"    wrote {OUT}/{stamp}.html")


def styles(only: list[str] | None = None) -> None:
    settings = load_settings()
    chosen = {k: v for k, v in STYLES.items() if not only or k in only}
    os.makedirs(rel(f"{OUT}/img"), exist_ok=True)
    stamp = _stamp()
    drawn = []
    for name, style in chosen.items():
        prompt = f"{style} {STYLE_SCENE} {_NO_TEXT}"
        print(f">>> {name} ({len(prompt)} chars)")
        raw = illustrate._cf_image(prompt, settings)
        if not raw:
            print(f"    {name}: no image")
            continue
        path = f"{OUT}/img/{stamp}-{name}.jpg"
        with open(rel(path), "wb") as fh:
            fh.write(illustrate._crop(raw, settings["image"]["crop"]))
        drawn.append((name, os.path.basename(path)))
        print(f"    wrote {path}")
    if drawn:
        _render_styles(drawn, stamp)


def draw() -> None:
    """The real picture path for a real haiku: depict_haiku then illustrate.

    The unit tests prove the plumbing with the model calls mocked, so the ONE
    thing they cannot answer is whether flux still prints a caption on an
    isolated object - which it did on 09/09/2026 ("APPROVING WEATHER"). This
    runs the actual two calls the edition will make and writes the actual image,
    without publishing anything."""
    settings = load_settings()
    dispatch = haiku_mod.to_dispatch(
        {"lines": ["the cloud licence clerk",
                   "stamps the thunderstorm for noon",
                   "dry rain takes two weeks"],
         "title": "Cloud Licence"},
        {"place": "Carrow Shelf", "year": 2877, "years_from_now": 851}, "weather")
    print(">>> DEPICT")
    # Pass the SAME model list the live pipeline uses. Without it this
    # defaults to settings.gemini.model alone, and on 09/09/2026 that
    # made the trial report a dead end that production would have walked
    # straight past - a harness that is weaker than the thing it tests
    # produces false negatives, which are worse than no test.
    brief = depict.depict_haiku(dispatch, settings, run_mod.HAIKU_MODELS)
    if not brief:
        print("    no brief; aborting rather than drawing from the scene line")
        return
    for k, v in brief.items():
        if v:
            print(f"      {k:10} {v}")
    prompt = illustrate.build_prompt(dispatch, brief)
    print(f">>> ILLUSTRATE ({len(prompt)} chars)")
    print(f"    no-caption clause last: {prompt.rstrip().endswith('empty margins.')}")
    raw = illustrate._cf_image(prompt, settings)
    if not raw:
        print("    no image")
        return
    stamp = _stamp()
    os.makedirs(rel(f"{OUT}/img"), exist_ok=True)
    path = f"{OUT}/img/{stamp}-live-object.jpg"
    with open(rel(path), "wb") as fh:
        fh.write(illustrate._crop(raw, settings["image"]["crop"]))
    print(f"    wrote {path}")


def _render_styles(drawn, stamp: str) -> None:
    cards = "".join(
        f"<figure><img src='img/{f}' alt=''><figcaption>{html.escape(n)}"
        f"</figcaption></figure>" for n, f in drawn)
    page = f"""<!doctype html><meta charset=utf-8>
<title>Picture styles {stamp}</title>
<style>
body{{background:#eeece5;color:#1b1a17;font:15px/1.5 Iowan Old Style,Palatino,Georgia,serif;
margin:0;padding:2rem 1.2rem;}}
.wrap{{max-width:60rem;margin:0 auto;}}
h1{{font-size:1.4rem;margin:0 0 .2rem;}}
.sub{{color:#6b6659;font-size:.85rem;margin:0 0 2rem;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:1.6rem;}}
figure{{margin:0;}}
img{{width:100%;display:block;border:1px solid #d5d1c4;}}
figcaption{{font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;
color:#6b6659;margin-top:.5rem;}}
</style><div class=wrap>
<h1>Picture styles</h1>
<p class=sub>One scene, {len(drawn)} styles, everything else held constant.</p>
<div class=grid>{cards}</div></div>"""
    with open(rel(f"{OUT}/{stamp}-styles.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"    wrote {OUT}/{stamp}-styles.html")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "poems"
    if cmd == "styles":
        styles(sys.argv[2:] or None)
    elif cmd == "models":
        models()
    elif cmd == "draw":
        draw()
    else:
        poems(int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_COUNT,
              sys.argv[3] if len(sys.argv) > 3 else None)
