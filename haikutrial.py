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
import sys
from datetime import datetime, timezone

import dates as dates_mod
import gemini
import haiku as haiku_mod
import illustrate
from common import load_settings, rel

OUT = "data/trials/haiku"


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
    "photo": (
        "A black and white documentary photograph on 35mm film, available light, "
        "slight grain, shallow depth of field, an ordinary unposed working "
        "moment caught by a press photographer. Plain, undramatic, real."),
}

#: One fixed scene for the comparison, so STYLE is the only thing that varies.
#: Derived from a haiku rather than from a dispatch, because that is what these
#: pictures will have to be drawn from.
STYLE_SCENE = ("A dock worker in a heavy sealed one-piece suit and hard boots "
               "stands beside a low mound of grey calcified crust welded to a "
               "metal deck, holding a flat handheld reader. Overhead ducting, "
               "riveted panel walls.")

_NO_TEXT = ("Absolutely no text, letters, words, captions, numbers, signatures "
            "or watermark - purely pictorial. No border, frame, margin or plate "
            "mark. Everyone fully dressed for work, upright, whole body covered.")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def poems(count: int) -> None:
    settings = load_settings()
    dateline = dates_mod.sample_future_dateline(
        datetime.now(timezone.utc).date(), settings["dates"], set())
    prompt = haiku_mod.build_prompt(dateline, "", count)
    print(f">>> HAIKU {count} datelined {dateline['year']} "
          f"({dateline['years_from_now']} years out)")
    raw = gemini.generate(prompt, settings,
                          settings["gemini"].get("temperature_ideate", 1.1))
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

    os.makedirs(rel(OUT), exist_ok=True)
    stamp = _stamp()
    record = {"generated": stamp, "dateline": dateline, "asked": count,
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


def styles() -> None:
    settings = load_settings()
    os.makedirs(rel(f"{OUT}/img"), exist_ok=True)
    stamp = _stamp()
    drawn = []
    for name, style in STYLES.items():
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
        styles()
    else:
        poems(int(sys.argv[2]) if len(sys.argv) > 2 else 24)
