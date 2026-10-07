"""Two pictures a day, the clearer one published, and drawing notes that learn.

Charlie, 07/10/2026, after the house-notes loop shipped for the prose: "does a
similar thing happen for the image?" It did not - one picture a day, drawn from
the scene line, compared against nothing. Then: "yes build it".

HOW IT WORKS
- Every edition draws TWO candidates. With a challenger running, one is drawn
  with the champion DRAWING NOTES and one with the challenger's; otherwise both
  use the champion's, and the day is simply best of two. flux takes no seed, so
  the same prompt twice is already two different pictures.
- One Gemini call with both images picks the one that shows the story more
  clearly. If Gemini is down, the lower share of smooth mid-grey wins instead:
  the measured mush number, 30.6% median for the archive's good pictures against
  37.2% for its bad ones (07/10/2026). A mush pick publishes but never counts for
  the loop - only a judged day between two different sets of notes does.
- After `trials` judged days the challenger is kept on `promote_at` wins, else
  retired, and one call proposes the next edit from the judge's stored reasons.
  The shared bookkeeping is tune.py's; only the judge and the proposal are here.

The Dore engraving style is SETTLED and is not the loop's to change: a note may
only steer what is drawn and how it is framed, and any note naming another style
or a colour is refused. The judge is an AI deciding what "clear" means. That is
a narrower question than "funny", which is why it is trusted more here.

Cost per edition: one extra Cloudflare image and one Gemini call, plus a
proposal every couple of weeks. Cloudflare's free tier has only ever refused
after 31 images in fifteen minutes.
"""
from __future__ import annotations

import io
import os
import re
import sys

from PIL import Image

import gemini
import illustrate
import tune
from common import rel

STATE_PATH = "config/drawing_notes.yaml"

#: A note may not change the settled style, add colour, or push toward the
#: surreal - each a direction Charlie has already rejected for this paper.
_FORBIDDEN = re.compile(
    r"\b(colou?r\w*|red|blue|green|yellow|orange|purple|pink|gold\w*|"
    r"photo\w*|watercolou?r|woodcut|anime|manga|cartoon\w*|comic|oil paint\w*|"
    r"pixel\w*|3d|render\w*|surreal\w*|dreamlike|fantas\w*|whimsical|"
    r"abstract)\b|—|–", re.I)


def mush(jpeg: bytes) -> float:
    """Percent of pixels in the smooth mid-grey band (64-191). An engraving that
    reads as ink on paper sits low; a dissolved one runs high."""
    h = Image.open(io.BytesIO(jpeg)).convert("L").histogram()
    return round(100.0 * sum(h[64:192]) / max(1, sum(h)), 1)


def judge_prompt(dispatch: dict) -> str:
    return f"""Two candidate wood engravings for one news story. Pick the one a
reader who has just read the headline would recognise as THIS story.

Headline: {dispatch.get('headline', '')}
The scene it should show: {dispatch.get('scene', '')}

Prefer, in this order: the subject and what they are doing are clearly visible
and match the scene; nothing important cut off by the edges; no lettering,
garbled signs or signatures; crisp ink lines rather than smudged grey.

Return JSON only: {{"pick": 1 or 2, "reason": "one sentence naming what the
loser got wrong", "winner_faults": "one sentence on what is still wrong with
the winner, or empty if nothing"}}"""


def judge(dispatch: dict, a: bytes, b: bytes, settings: dict) -> dict | None:
    try:
        raw = gemini.generate(judge_prompt(dispatch), settings,
                              settings["gemini"].get("temperature_judge", 0.2),
                              images=[a, b])
        got = gemini.extract_json(raw)
        pick = int(got.get("pick"))
        if pick not in (1, 2):
            return None
        return {"pick": pick - 1, "reason": str(got.get("reason", "")).strip(),
                # The winner's own faults are what the next drawing note should
                # fix. 07/10/2026: the first live judgement picked a picture
                # covered in nonsense lettering over one with severed bodies, and
                # a loser-only reason would never have mentioned the lettering.
                "winner_faults": str(got.get("winner_faults", "")).strip()}
    except Exception as exc:  # noqa: BLE001 - a judge failure falls back to mush
        print(f"    picture judge failed ({str(exc)[:120]})", file=sys.stderr)
        return None


def draw(dispatch: dict, run_date: str, settings: dict, brief: dict | None = None,
         state: dict | None = None) -> tuple[str | None, dict]:
    """Draw two, publish the clearer, return (relpath or None, info).
    Never raises: the worst case is the old single-picture behaviour or none."""
    icfg = settings.get("image") or {}
    if not icfg.get("enabled"):
        return None, {}
    state = state or tune.empty_state()
    variants = [tune.CHAMPION,
                tune.CHALLENGER if state.get("challenger") is not None else tune.CHAMPION]
    shots = []
    for v in variants:
        try:
            raw = illustrate._cf_image(illustrate.build_prompt(
                dispatch, brief, tune.notes_for(state, v)), settings)
            shots.append(illustrate._crop(raw, icfg["crop"]) if raw else None)
        except Exception as exc:  # noqa: BLE001
            print(f"    draw {v} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            shots.append(None)
    info = {"variants": variants,
            "mush": [mush(s) if s else None for s in shots],
            "pick": None, "decided_by": None, "reason": ""}
    alive = [i for i, s in enumerate(shots) if s]
    if not alive:
        return None, info
    if len(alive) == 1:
        info.update(pick=alive[0], decided_by="walkover")
    else:
        got = judge(dispatch, shots[0], shots[1], settings)
        if got:
            info.update(pick=got["pick"], decided_by="judge", reason=got["reason"],
                        winner_faults=got.get("winner_faults", ""))
        else:
            info.update(pick=min(alive, key=lambda i: info["mush"][i]),
                        decided_by="mush")
    relpath = f"{icfg['dir']}/{run_date}.jpg"
    path = rel(relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(shots[info["pick"]])
    print(f"    picture {info['pick'] + 1} of 2 by {info['decided_by']} "
          f"(mush {info['mush']}){': ' + info['reason'] if info['reason'] else ''}")
    return relpath, info


def outcome(info: dict) -> str | None:
    """'win' or 'loss' for the challenger. Only a JUDGED day between two
    different sets of notes counts; mush and walkovers publish but decide
    nothing."""
    if info.get("decided_by") != "judge":
        return None
    variants = info.get("variants") or []
    if set(variants) != {tune.CHAMPION, tune.CHALLENGER}:
        return None
    return "win" if variants[info["pick"]] == tune.CHALLENGER else "loss"


def proposal_prompt(champion: list[str], records: list[dict], history: list[dict],
                    cfg: dict) -> str:
    current = "\n".join(f"- {n}" for n in champion) or "(none yet)"
    seen = []
    for r in records[-12:]:
        pic = (r.get("quality") or {}).get("picture") or {}
        if pic.get("reason") or pic.get("winner_faults"):
            seen.append(f"- scene: {(r.get('dispatch') or {}).get('scene', '')} | "
                        f"losing picture: {pic.get('reason', '')} | "
                        f"still wrong with the published one: "
                        f"{pic.get('winner_faults') or 'nothing'}")
    tried = "\n".join(f"- {h['verdict']} ({h['wins']}/{h['of']}): {h.get('why', '')}"
                      for h in (history or [])[-6:]) or "(nothing tried yet)"
    return f"""You edit the drawing notes for a newspaper's daily illustration: a
monochrome wood engraving in the style of Gustave Dore, drawn by a fast image
model from a one-line scene. The notes are a few short lines appended to every
image prompt. The style is fixed and is not yours to change.

Current drawing notes:
{current}

What the picture judge has said recently, about the losing picture and about
what was still wrong with the one that was published:
{chr(10).join(seen) or '(nothing yet)'}

Recent changes already tried, and whether they won:
{tried}

Propose exactly ONE change: add one note, delete one note, or reword one note.
A note is a short, concrete instruction to the image model about what is drawn
or how it is framed - distance, what must be inside the frame, how many people,
what the subject is doing, what must not appear - under
{int(cfg.get('max_line_chars', 120))} characters. Aim at the fault the judge
keeps naming. Never mention colour, another art style, or anything surreal. At
most {int(cfg.get('max_lines', 4))} notes in total.

Return JSON only: {{"notes": ["...the full new list..."], "why": "one sentence"}}"""


def propose(state: dict, records: list[dict], settings: dict, today: str) -> bool:
    import write as write_stage
    cfg = settings.get("draw_tune") or {}
    prompt = proposal_prompt(state.get("champion") or [], records,
                             state.get("history") or [], cfg)
    for model in write_stage.models(settings):
        try:
            got = write_stage._generate_json(prompt, settings, model, retries=0)
        except Exception as exc:  # noqa: BLE001
            print(f"    drawtune: {model} failed ({str(exc)[:120]})")
            continue
        notes = [n.strip() for n in (got.get("notes") or [])
                 if isinstance(n, str)] if isinstance(got, dict) else None
        if notes is not None and tune.valid(notes, state.get("champion") or [],
                                            cfg, _FORBIDDEN):
            state.update(challenger=notes, why=str(got.get("why", "")).strip(),
                         since=today, results={})
            return True
        print(f"    drawtune: {model} proposed an invalid change; not taken")
        return False
    return False


def after_edition(settings: dict, run_date: str, info: dict,
                  records: list[dict]) -> dict:
    """Score the day, maybe promote or retire, maybe propose. Never raises."""
    cfg = settings.get("draw_tune") or {}
    if not cfg.get("enabled") or not info:
        return {}
    state = tune.load(STATE_PATH)
    result = outcome(info)
    tune.record(state, run_date, result)
    summary = {"result": result, "challenger_record": dict(state.get("results") or {})}
    verdict = tune.decide(state, cfg, run_date)
    if verdict:
        summary["decision"] = verdict
        print(f"    drawtune: challenger {verdict}")
    if state.get("challenger") is None and propose(state, records, settings, run_date):
        print(f"    drawtune: new challenger - {state['why']}")
        summary["new_challenger"] = state["why"]
    tune.save(state, STATE_PATH)
    return summary
