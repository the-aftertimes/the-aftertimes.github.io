"""Generate a monochrome wood-engraving illustration for a dispatch via Cloudflare
Workers AI (free tier). Story-specific (scene derived from the headline) and text-free
(the model's caption band is cropped off). Best-effort: returns a repo-relative image
path, or None on ANY failure - the page then simply renders with no illustration."""
from __future__ import annotations

import base64
import io
import json
import os
import urllib.request

from PIL import Image

from common import rel


def build_prompt(dispatch: dict) -> str:
    return (
        "A masterful wood engraving in the style of Gustave Dore. Fine black ink linework "
        "and dense cross-hatching on aged paper, dramatic chiaroscuro lighting, a clear "
        "central scene with figures in a believable environment, rich background detail. "
        f"It depicts the scene of this news story: \"{dispatch['headline']}\". No colour. "
        "Absolutely no text, no letters, no words, no captions, no titles, no numbers, no "
        "signatures and no watermark anywhere in the image - purely pictorial."
    )


def _cf_image(prompt: str, settings: dict) -> bytes | None:
    acct = os.environ.get("CF_ACCOUNT_ID", "").strip()
    tok = os.environ.get("CF_API_TOKEN", "").strip()
    if not acct or not tok:
        return None
    cfg = settings["image"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{cfg['model']}"
    body = json.dumps({"prompt": prompt, "steps": cfg["steps"]}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=cfg.get("timeout", 120)) as resp:
        data = json.load(resp)
    if not data.get("success") or "result" not in data:
        return None
    return base64.b64decode(data["result"]["image"])


def _crop(raw: bytes, frac: list) -> bytes:
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    left, top, right, bottom = frac
    im = im.crop((int(w * left), int(h * top), int(w * right), int(h * bottom)))
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=88)
    return out.getvalue()


def generate(dispatch: dict, run_date: str, settings: dict) -> str | None:
    """Return a repo-relative path like 'assets/img/2026-07-28.jpg', or None."""
    if not settings.get("image", {}).get("enabled"):
        return None
    try:
        raw = _cf_image(build_prompt(dispatch), settings)
        if not raw:
            return None
        cropped = _crop(raw, settings["image"]["crop"])
        relpath = f"{settings['image']['dir']}/{run_date}.jpg"
        path = rel(relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(cropped)
        return relpath
    except Exception:
        return None
