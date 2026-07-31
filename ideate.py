"""Stage 1 - ideate. Ask Gemini for ~N candidate premises for a given future
date + domain, primed with optional bible motifs and seed-premise examples, and
told to avoid recent headlines."""
from __future__ import annotations

import gemini


def build_prompt(dateline: dict, domain: str, bible_motifs: list[dict],
                 seed_premises: list[str], avoid_headlines: list[str],
                 n: int, style_guidance: str) -> str:
    motif_lines = "\n".join(f"- {m['term']}: {m.get('gloss', '')}"
                            for m in bible_motifs) or "(none yet)"
    seed_lines = "\n".join(f"- {p}" for p in seed_premises) or "(none)"
    avoid_lines = "\n".join(f"- {h}" for h in avoid_headlines) or "(none)"
    return f"""You are the wire desk of The Aftertimes, a newspaper filing real
news dispatches from the future. The register is imaginative science fiction with
a knowing satirical edge: strange, funny, but written completely straight-faced,
as a real newswire would.

Today's dispatch format: {style_guidance}

Brainstorm {n} one-sentence story premises datelined the year {dateline['year']}
({dateline['years_from_now']} years from now), in the domain: {domain}.

Each premise needs a real comedic engine - not merely "a futuristic version of a
present-day thing", but a genuine twist: an ironic reversal, petty bureaucracy or
mundane human smallness colliding with something cosmic or profound, a category
error taken completely seriously, or a strange consequence nobody would think to
legislate for. A reader should smile at the premise alone. Avoid dry, generic
finance/policy framings unless there is a real joke in them. Make each surprising,
specific and self-contained, and vary them widely across genuinely different ideas.
Do NOT explain them. Order them strongest first - put the sharpest, funniest, most
surprising premise as item 1.

Every premise must be a NEWS EVENT that a correspondent could report on - something
that HAPPENED, involving other people, that a newspaper would cover. Do NOT propose
a premise whose form is a private document: no "a resident files a complaint",
no "a reader writes in", no "someone submits a form". Those are not news stories.
The bureaucratic absurdity should be reported ABOUT, not performed.

Also: the joke must live in the SITUATION, not in the invented product name. A
premise that is just "branded futuristic gadget malfunctions and annoys someone"
has no engine. Ask what is genuinely, structurally ridiculous about the world it
implies, and put THAT in the premise.

Example premises for tone (do not reuse these):
{seed_lines}

You may reuse one of these established motifs ONLY if it fits the story
naturally; otherwise ignore them entirely:
{motif_lines}

Avoid anything close to these recently-used stories:
{avoid_lines}

Return JSON only: {{"premises": ["...", "...", ...]}} with exactly {n} items."""


def ideate(dateline: dict, domain: str, bible_motifs: list[dict],
           seed_premises: list[str], avoid_headlines: list[str],
           settings: dict, style_guidance: str) -> list[str]:
    prompt = build_prompt(dateline, domain, bible_motifs, seed_premises,
                          avoid_headlines, settings["ideate"]["n_premises"],
                          style_guidance)
    raw = gemini.generate(prompt, settings,
                          settings["gemini"]["temperature_ideate"])
    data = gemini.extract_json(raw)
    premises = [p.strip() for p in data.get("premises", []) if p and p.strip()]
    if not premises:
        raise gemini.GeminiError("ideate returned no premises")
    return premises
