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
    "subject": "the single focal thing or figure, and what it is made of, in one clause",
    "action": "what it is doing at this exact instant, and which way it faces",
    "setting": "the place around it, in concrete nouns",
    "light": "direction, hardness and source of the light",
    "materials": "the three or four materials actually visible, named plainly",
    "anomaly": ("the single most specific detail in this scene - the one thing a "
                "generic illustration of this story would NOT have. Name it exactly."),
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
        "You are the picture editor for a newspaper. Below is a news dispatch. "
        "Choose the ONE moment in it that should be illustrated, and describe "
        "that moment as it would look to someone standing there.\n\n"
        f"HEADLINE: {headline}\n"
        f"SUGGESTED SCENE: {scene}\n"
        f"DISPATCH:\n{body[:1500]}\n\n"
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
