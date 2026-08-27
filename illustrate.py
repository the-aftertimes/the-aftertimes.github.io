"""Generate a monochrome wood-engraving illustration for a dispatch via Cloudflare
Workers AI (free tier). Story-specific (uses the dispatch's concrete scene, falling
back to the headline) and text-free (the model's caption band is cropped off).
Best-effort: returns a repo-relative image path, or None on ANY failure - the page
then simply renders with no illustration."""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

from PIL import Image

from common import rel


#: "documentary" and the anti-surrealism clause matter as much as the Dore
#: reference. Charlie, 17/08/2026, on the first brief-built image: "still really
#: Dali-esque and absurd, it doesn't look real". A structured brief gives flux
#: enough specificity to compose an ALLEGORY, and a surreal picture explains the
#: joke - the same failure the prose had before "report the facts, never state
#: the joke". The events are absurd; the picture reports them deadpan.
_STYLE = ("A documentary wood engraving in the style of Gustave Dore, as a "
          "newspaper illustration of a real event that was actually witnessed. "
          "Fine black ink linework and dense cross-hatching on aged paper, a "
          "single clear focal subject, figures in a believable environment, rich "
          "background detail. Plain eye-level view, natural gravity, everything "
          "resting on solid ground - nothing floating or suspended, no symbolic "
          "or dreamlike composition.")
#: "no border, no frame" is ported from photocopy and is NOT cosmetic: the first
#: brief-built image came back with a drawn white margin ruled around it, because
#: a richly specified scene reads to flux as a plate in a book. The engraving must
#: bleed to the edge - the page supplies its own framing.
#: The hatching clause is here for the same reason: the structured brief pulled
#: the sky toward a smooth grey wash, away from the linework the house style is.
#: The clothing clause is not prudishness, it is a gap-filling failure. On
#: 19/08/2026 a brief read "a woman in a red knitted fleece sweater... with both
#: feet encased in bulky heat-foam boots" - a top and boots, and nothing said
#: about anything between them. flux completed the gap with bare legs and put her
#: in a reclining pin-up pose on the bunk. Charlie: "today's image was a bit
#: lewd." Any body part the brief leaves unspecified is a part flux will decide
#: about, so the prompt states the default explicitly and the negative closes it.
#: KEEP THIS TIGHT. It shares a 2048-character budget with everything else, and
#: on 21/08/2026 it was what blew that budget - see MAX_PROMPT below. Every rule
#: here is load-bearing, so compress the wording, never drop a rule.
_NEGATIVE = ("Everyone fully and modestly dressed for work, whole body covered, "
             "sleeves, long trousers or skirts, proper boots. No nudity, no bare "
             "legs or chest, no underwear, no exposed skin beyond hands and "
             "face. Nobody reclining, draped or posed for the viewer: upright "
             "and working. Every tone engraved lines and cross-hatching, never "
             "smooth grey. Full bleed: no border, frame, margin or plate mark. "
             "One or two clear focal figures in front, larger and sharper than "
             "anyone else; a few plainer figures may stand behind. No dense "
             "crowd or sea of faces. No colour. Absolutely no text, letters, "
             "words, captions, numbers, signatures or watermark - purely "
             "pictorial.")


#: Cloudflare's flux endpoint rejects a prompt over 2048 characters with a bare
#: HTTP 400. This bit on 21/08/2026 and cost that day its picture: the prompt had
#: been running at 1978-2039 characters for a week - nine characters of headroom
#: at its worst - and two rules added to _NEGATIVE on the 19th and 20th pushed it
#: to 2132. Nothing warned, because the length lived nowhere; it was an emergent
#: property of a style constant, a negative constant and six model-written slots.
#: 1900 leaves room for a long brief without going near the wall.
MAX_PROMPT = 1900


def _fit(core: list[str], optional: list[str], negative: str) -> str:
    """Join the prompt, dropping the least important slots if it will not fit.

    The style, the subject-and-action and the negative block are never dropped:
    the first two are the picture and the third carries the clothing and no-text
    rules, so losing it is how an unusable image gets published. Everything else
    is detail, and detail is what goes. Dropped from the end backwards, because
    the slots are already ordered by how much they matter - setting, light,
    materials, then the anomaly, which is the most expendable.

    A single enormous subject clause is truncated rather than dropped, since a
    prompt with no subject draws nothing.
    """
    budget = MAX_PROMPT - len(negative) - 1
    kept = list(optional)
    while kept and len(" ".join(core + kept)) > budget:
        dropped = kept.pop()
        print(f"    illustrate: prompt over {MAX_PROMPT} chars, dropped a slot "
              f"({dropped[:40]}...)", file=sys.stderr)
    head = " ".join(core + kept)
    if len(head) > budget:
        print(f"    illustrate: subject clause alone is {len(head)} chars, "
              f"truncating", file=sys.stderr)
        head = head[:budget].rsplit(" ", 1)[0].rstrip(",;") + "."
    return f"{head} {negative}"


def build_prompt(dispatch: dict, brief: dict | None = None) -> str:
    """Assemble the flux prompt, preferring a structured brief from depict.py.

    Ported from ~/dev/photocopy 17/08/2026. Two details there are load-bearing
    and are the reason this is not just string concatenation:
      - EMPTY SLOTS ARE SKIPPED, not emitted blank. flux reads a dangling
        "Light: ." as an instruction about punctuation and it shows in the image.
      - THE NEGATIVE GOES LAST. flux weights the tail of a prompt most heavily,
        and the slots are exactly what tempts it to render lettering, so a
        no-text clause placed in front of them loses the argument.
    """
    if brief:
        lead = ", ".join(p for p in ((brief.get("subject") or "").strip(),
                                     (brief.get("action") or "").strip()) if p)
        core = [_STYLE, (lead or "a figure").rstrip(".") + "."]
        optional = []
        for field, prefix in (("setting", ""), ("light", "Light: "),
                              ("materials", "Materials: "), ("anomaly", "")):
            value = (brief.get(field) or "").strip()
            if value:
                optional.append(f"{prefix}{value}".rstrip(".") + ".")
        return _fit(core, optional, _NEGATIVE)

    # Fallback: the writer's scene line, which is prose written for a reader.
    subject = (dispatch.get("scene") or "").strip() or dispatch["headline"]
    return _fit([_STYLE], [f'It depicts this scene: "{subject}".'], _NEGATIVE)


#: Waits between Cloudflare attempts, in seconds. Three tries over roughly a
#: minute and a half. Added 20/08/2026, after a redraw died on a bare 429 that a
#: single retry would very likely have survived - the free image tier is a short
#: rolling window rather than a daily allowance, so the fix is to wait, not to
#: give up for the day. Deliberately short: the daily cron has a backup run two
#: hours later, and a job that sits blocked for ten minutes is worse than one
#: that fails fast and lets the backup take it.
_RETRY_WAITS = (20, 45)


def _post_with_retry(req, cfg: dict):
    """POST, retrying only what is worth retrying.

    429 (rate limited) and 5xx (Cloudflare having a moment) are transient and get
    another go. A 401/403 is a bad token and a 400 is a bad prompt - retrying
    either just burns quota and delays the honest failure, so they return
    immediately.
    """
    for attempt in range(len(_RETRY_WAITS) + 1):
        try:
            with urllib.request.urlopen(
                    req, timeout=cfg.get("timeout", 120)) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            # Cloudflare returns 429 for BOTH "too fast, slow down" and "your
            # 10,000-neuron daily free allocation is gone" (error code 4006).
            # Only the first is worth waiting for; the second cannot clear until
            # the UTC day rolls, so retrying it just burns a minute and hammers
            # an endpoint that has already said no. 25/08/2026 spent 65 seconds
            # doing exactly that before publishing without a picture.
            body = ""
            try:
                body = exc.read().decode()[:400]
            except Exception:  # noqa: BLE001 - a body is a nicety
                pass
            exhausted = "4006" in body or "daily free allocation" in body
            transient = (exc.code == 429 or 500 <= exc.code < 600) and not exhausted
            last = attempt >= len(_RETRY_WAITS)
            if exhausted:
                # The note here used to blame the photocopy project for sharing
                # this allocation. It does NOT: on 27/08/2026 photocopy drew
                # successfully at 22:06 UTC while this repo was refused at 21:42
                # AND again at 22:09, on the identical model
                # (@cf/black-forest-labs/flux-1-schnell). Cloudflare's free
                # neuron budget is per ACCOUNT, so two projects cannot see
                # different answers from one exhausted budget - they are on
                # different accounts. Pointing at photocopy sent a whole
                # diagnosis down the wrong path; the spend is all inside THIS
                # account, so look at trial/reedit/reillustrate runs earlier in
                # the same UTC day.
                print("    illustrate: Cloudflare's daily free allocation for "
                      "THIS account is used up - not retryable until the UTC "
                      "day rolls (00:00 UTC / 10:00 AEST). The spend is this "
                      "repo's own: check today's trial, reedit and reillustrate "
                      "runs, which draw on the same budget as the dispatch.",
                      file=sys.stderr)
                return None
            if not transient or last:
                # Print what Cloudflare actually SAID - `body`, read once above.
                # An HTTPError body is a stream and the second read comes back
                # empty, so this must NOT call exc.read() again. The first
                # version of this function swallowed the body entirely and the
                # 21/08 failure logged a bare "CF HTTP 400", leaving the reason
                # (prompt too long) to be reconstructed from character counts.
                detail = body or "<no body>"
                print(f"    illustrate: CF HTTP {exc.code}"
                      f"{'' if transient else ' (not retryable)'}"
                      f"{' after ' + str(attempt + 1) + ' attempts' if transient else ''}"
                      f": {detail}", file=sys.stderr)
                return None
            wait = _RETRY_WAITS[attempt]
            print(f"    illustrate: CF HTTP {exc.code}, retrying in {wait}s "
                  f"({attempt + 1}/{len(_RETRY_WAITS)})", file=sys.stderr)
            time.sleep(wait)
    return None


def _cf_image(prompt: str, settings: dict) -> bytes | None:
    acct = os.environ.get("CF_ACCOUNT_ID", "").strip()
    tok = os.environ.get("CF_API_TOKEN", "").strip()
    if not acct or not tok:
        print(f"    illustrate: CF creds missing (acct set={bool(acct)}, "
              f"token set={bool(tok)})", file=sys.stderr)
        return None
    cfg = settings["image"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{cfg['model']}"
    body = json.dumps({"prompt": prompt, "steps": cfg["steps"]}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    data = _post_with_retry(req, cfg)
    if data is None:
        return None
    if not data.get("success") or "result" not in data:
        print(f"    illustrate: CF returned no image ({str(data.get('errors'))[:200]})",
              file=sys.stderr)
        return None
    return base64.b64decode(data["result"]["image"])


def _crop(raw: bytes, frac: list) -> bytes:
    # Convert to greyscale so the engraving is always monochrome ink, even if the
    # model sneaks in colour (it sometimes does). The bone-paper blend is done in CSS.
    im = Image.open(io.BytesIO(raw)).convert("L")
    w, h = im.size
    left, top, right, bottom = frac
    im = im.crop((int(w * left), int(h * top), int(w * right), int(h * bottom)))
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=88)
    return out.getvalue()


def generate(dispatch: dict, run_date: str, settings: dict,
             brief: dict | None = None) -> str | None:
    """Return a repo-relative path like 'assets/img/2026-07-28.jpg', or None."""
    if not settings.get("image", {}).get("enabled"):
        return None
    try:
        raw = _cf_image(build_prompt(dispatch, brief), settings)
        if not raw:
            return None
        cropped = _crop(raw, settings["image"]["crop"])
        relpath = f"{settings['image']['dir']}/{run_date}.jpg"
        path = rel(relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(cropped)
        return relpath
    except Exception as exc:
        print(f"    illustrate failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None
