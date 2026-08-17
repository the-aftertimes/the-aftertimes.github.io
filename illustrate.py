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
_NEGATIVE = ("Every tone built from engraved lines and cross-hatching, never "
             "smooth grey shading. Full bleed to the edges: no border, no frame, "
             "no margin, no plate mark. No colour. Absolutely no text, no letters, "
             "no words, no captions, no titles, no numbers, no signatures and no "
             "watermark anywhere in the image - purely pictorial.")


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
        parts = [_STYLE]
        lead = ", ".join(p for p in ((brief.get("subject") or "").strip(),
                                     (brief.get("action") or "").strip()) if p)
        parts.append((lead or "a figure").rstrip(".") + ".")
        for field, prefix in (("setting", ""), ("light", "Light: "),
                              ("materials", "Materials: "), ("anomaly", "")):
            value = (brief.get(field) or "").strip()
            if value:
                parts.append(f"{prefix}{value}".rstrip(".") + ".")
        parts.append(_NEGATIVE)
        return " ".join(parts)

    # Fallback: the writer's scene line, which is prose written for a reader.
    subject = (dispatch.get("scene") or "").strip() or dispatch["headline"]
    return f"{_STYLE} It depicts this scene: \"{subject}\". {_NEGATIVE}"


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
    with urllib.request.urlopen(req, timeout=cfg.get("timeout", 120)) as resp:
        data = json.load(resp)
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
