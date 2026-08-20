"""Turn a finished dispatch into a structured VISUAL BRIEF for the illustrator.

Ported from ~/dev/photocopy's `describe` stage on 17/08/2026, because Photocopy's
images are markedly better on the *same* free-tier model
(`@cf/black-forest-labs/flux-1-schnell`, same Cloudflare account). The generator
was never the difference.

The difference is what flux is handed. Until now `illustrate.build_prompt` pasted
the writer's single free-text `scene` line into the prompt - and that line was
written for a READER. It carries the joke and the mood, and almost never the
things a renderer needs: where the light comes from, what the surfaces are made
of, which single detail makes this image not a stock image. Free prose also
drifts toward the evocative-generic ("a haunting, atmospheric scene"), which
draws a generic picture.

Six fixed slots make that drift impossible to express. `anomaly` is the
load-bearing one: it forces the most specific thing in the scene to survive into
the prompt, where prose would have smoothed it away.

Costs one extra Gemini call per dispatch (~6 -> 7/day). Every failure path
returns None so `illustrate` falls back to the old scene-line prompt: a missing
brief must cost us a better picture, never the picture.
"""
from __future__ import annotations

import re

import gemini

#: The brief IS the data model. Order matters - it is also the order the fields
#: are assembled into the image prompt in illustrate.build_prompt.
FIELDS = ("subject", "action", "setting", "light", "materials", "anomaly")

_GUIDE = {
    "subject": "the person or object at the centre, and what it is made of, in one clause",
    "action": ("what they are plainly DOING - working, waiting, walking, watching. "
               "An ordinary action caught mid-way, not a dramatic pose"),
    "setting": "the ordinary working place around them, in concrete nouns",
    "light": "direction, hardness and source of the light",
    "materials": "the three or four materials actually visible, named plainly",
    "anomaly": ("one mundane, specific detail that proves this is a real place "
                "someone works in - wear, clutter, a tool set down, a repair. "
                "Something dull and true, NOT something strange"),
}

#: flux renders any text it is told about, and the engraving is meant to be
#: purely pictorial - the existing prompt spends a whole sentence forbidding
#: lettering. A brief that says "a sign reading CLOSED" hands that instruction
#: straight back, so strip the vocabulary before it can reach the prompt.
#: `signs?` and `notices?` are here and are NOT in photocopy's version, which
#: only blocked `signage`/`signature`. "a sign reading CLOSED" sailed through and
#: is the single likeliest way a brief asks for lettering.
_TEXT_ARTEFACT = re.compile(
    r"\b(text|lettering|letters|words?|writing|written|caption|watermark|"
    r"signs?|signage|signature|notices?|logo|label|placard|banner|poster|"
    r"plaque|inscription|inscribed|typeface|font|printed|imprint|numerals?)\b",
    re.I)

_SENTENCE = re.compile(r"(?<=[.;])\s+")


def strip_text_artefacts(value: str) -> str:
    """Drop any clause that asks for rendered lettering.

    Trailing separators are stripped from the surviving clauses: the split keeps
    the delimiter on the left-hand part, so dropping the second half of
    "a brass valve; a label reading 40 PSI" would otherwise leave a dangling
    "a brass valve;" to be pasted straight into the prompt."""
    kept = [s.strip().rstrip(";,.").strip()
            for s in _SENTENCE.split(value or "")
            if not _TEXT_ARTEFACT.search(s)]
    return " ".join(k for k in kept if k).strip()


def build_prompt(dispatch: dict) -> str:
    slots = ",\n".join(f'  "{f}": "{_GUIDE[f]}"' for f in FIELDS)
    headline = (dispatch.get("headline") or "").strip()
    scene = (dispatch.get("scene") or "").strip()
    body = (dispatch.get("body") or "").strip()
    return (
        "You are the picture editor for a newspaper. Below is a news dispatch "
        "and THE SCENE THAT HAS ALREADY BEEN CHOSEN for it.\n"
        "Your job is to say HOW THAT SCENE IS DRAWN, not to pick a different "
        "one. Describe it as a PRESS PHOTOGRAPH - the plain, unstaged record a "
        "reporter would file - by filling in what the scene line does not carry: "
        "the light, the materials, the clothing, the small true detail. Keep its "
        "subject, its action and its place exactly as given. Do not substitute a "
        "different person, a different moment, an earlier moment or a later "
        "one.\n\n"
        "This is the most important instruction: THE PICTURE MUST LOOK REAL. "
        "The events in these stories are absurd, and the picture must report "
        "them completely straight, exactly as the writing does. A surreal or "
        "symbolic image explains the joke and kills it.\n"
        "So: everything obeys gravity and rests on something. Nothing floats, "
        "hovers or is suspended in mid-air. No object is impossibly large. "
        "People stand and work normally - nobody is falling, flailing, "
        "reaching skyward or arranged into a tableau. No allegory, no dreamlike "
        "composition, no swirling sky. Ordinary eye-level view.\n"
        "Photograph it undramatically - the plain working moment rather than the "
        "instant of peak action. That is about the FRAMING, never about swapping "
        "in a calmer subject.\n"
        "**Three consecutive pictures were wrong because this stage re-chose the "
        "scene instead of specifying it**, so it no longer gets to choose. "
        "17-19/08/2026: a dispatch about six nuns guarding a burst pipe came back "
        "as a bystanding fitter at a cart, and one about a woman marching her "
        "family onto a hull for a photograph came back as that woman alone in a "
        "recovery bunk afterwards. Every one of those was a true, plain, "
        "correctly-composed moment from the story, and unrecognisable AS the "
        "story. The scene line above already names the person the headline is "
        "about, doing the headline's action. Use them.\n"
        "The `subject` is the scene's subject and the `action` is the scene's "
        "action. If the scene line names other people behind or around them, "
        "they belong in `setting` as background, never in `subject`.\n"
        "DESCRIBE THE WHOLE OF WHAT THE SUBJECT IS WEARING, head to foot, in the "
        "`subject` clause - the garment on the body AND the legs AND the feet. "
        "Naming only a top and boots leaves the renderer to invent the rest, and "
        "on 19/08/2026 it invented bare legs and a reclining pose. Everyone in "
        "these pictures is dressed for work.\n"
        "ONE person, or at most two. A crowd has no focal subject and the "
        "engraving turns every extra face into mush.\n\n"
        # "SUGGESTED SCENE" is what this line used to say, and one word was
        # doing real damage: a suggestion is a thing you may decline. The
        # dispatch stays in the prompt because the brief needs the era's
        # materials and clothing, which the scene line does not carry - but it
        # is labelled as reference so it does not read as a menu of moments.
        f"HEADLINE: {headline}\n"
        f"THE SCENE TO DRAW (not a suggestion - draw this): {scene}\n"
        f"THE DISPATCH, for context only - do not pick a moment from it:\n"
        f"{body[:1500]}\n\n"
        "Return a single JSON object with exactly these keys:\n"
        f"{{\n{slots}\n}}\n\n"
        "Each value is one plain clause. Describe only what is VISIBLE. Do not "
        "interpret the story, do not explain the joke, and do not use the words "
        "atmospheric, moody, ethereal, haunting, striking or surreal.\n"
        "Name things rather than qualifying them: 'a brass hinge where the mouth "
        "would be', not 'an unsettling facial feature'.\n"
        "The picture must contain NO lettering of any kind. Never describe a "
        "sign, label, screen of text or written notice - describe the object it "
        "sits on instead, or choose a different detail.\n"
        "This is a scene from the future: the objects, clothing and machinery "
        "should not be present-day."
    )


def parse(raw) -> dict:
    """Coerce a model response into a complete brief.

    Missing keys become empty strings rather than raising - a brief with five of
    six slots still draws well, and losing the illustration because the model
    omitted `materials` once would be a poor trade."""
    if not isinstance(raw, dict):
        raise ValueError(f"brief must be an object, got {type(raw).__name__}")
    return {f: strip_text_artefacts(str(raw.get(f, "") or "").strip())
            for f in FIELDS}


def is_usable(brief: dict) -> bool:
    """Needs a subject and at least three filled slots. Below that the assembled
    prompt is thinner than the scene line it replaced, so the fallback is
    genuinely the better picture."""
    if not brief.get("subject"):
        return False
    return sum(1 for f in FIELDS if brief.get(f)) >= 3


def depict(dispatch: dict, settings: dict) -> dict | None:
    """Return a usable visual brief, or None to fall back to the scene line."""
    try:
        raw = gemini.generate(build_prompt(dispatch), settings,
                              settings["gemini"].get("temperature_depict", 0.7))
        brief = parse(gemini.extract_json(raw))
    except Exception as exc:  # noqa: BLE001 - never cost the dispatch its picture
        print(f"    depict failed, using the scene line: "
              f"{type(exc).__name__}: {exc}")
        return None
    if not is_usable(brief):
        print("    depict returned too few slots, using the scene line")
        return None
    return brief
