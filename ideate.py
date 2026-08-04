"""Stage 1 - ideate. Ask Gemini for ~N candidate premises for a given future
date + domain, primed with optional bible motifs and seed-premise examples, and
told to avoid recent headlines."""
from __future__ import annotations

import gemini


def build_prompt(dateline: dict, domain: str, bible_motifs: list[dict],
                 seed_premises: list[str], avoid_headlines: list[str],
                 n: int, style_guidance: str, engine_guidance: str = "") -> str:
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

TODAY'S COMIC ENGINE - the source of the humour must be: {engine_guidance}

Every premise must run on THAT engine. This constraint exists because the paper
developed a bad habit of making every story about debt, tax, liens, lawsuits,
injunctions, permits and repossession. Unless today's engine above is explicitly
the bureaucratic one, do NOT reach for money, courts, contracts, fines, unpaid
bills, licences or legal process as the source of the joke. They are a crutch.
Find the comedy where today's engine says it lives.

EVERY PREMISE MUST SATIRISE SOMETHING REAL. This is the most important rule and
the one most often missed. A premise that is merely a whimsical impossibility -
"a giant organ rolls through a city", "a cloud is towed away" - is a failure, no
matter how absurd, because it is ABOUT nothing. Each premise must take aim at a
recognisably true human or institutional behaviour that a reader today would
recognise instantly and wince at: status-signalling, box-ticking that defeats its
own purpose, nostalgia weaponised, professional self-importance, the way people
adapt instantly to the monstrous, sentimentality about the wrong things, the
gap between an organisation's stated reason and its real one. The future setting
exists to make that familiar behaviour visible in a new light. If you cannot name
what a premise is mocking about people or institutions NOW, discard it.

Each premise also needs a real comedic engine - not merely "a futuristic version
of a present-day thing", but a genuine twist. A reader should smile at the premise
alone. Make each surprising,
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
           settings: dict, style_guidance: str,
           engine_guidance: str = "") -> list[str]:
    prompt = build_prompt(dateline, domain, bible_motifs, seed_premises,
                          avoid_headlines, settings["ideate"]["n_premises"],
                          style_guidance, engine_guidance)
    raw = gemini.generate(prompt, settings,
                          settings["gemini"]["temperature_ideate"])
    data = gemini.extract_json(raw)
    premises = [p.strip() for p in data.get("premises", []) if p and p.strip()]
    if not premises:
        raise gemini.GeminiError("ideate returned no premises")
    return premises
