"""Turn staleness hits into the prompt's 'recently over-used' block.

Three properties matter more than the detection itself:
- DECAY: only the last `window` dispatches count, so a tic stops being nagged
  about once the paper has actually moved on.
- CAP: the rendered block is hard-limited, because the whole risk of this feature
  is quietly re-growing the prompt into the verbosity that was just fixed.
- KILL SWITCH: `learning.enabled: false` yields an empty block, which restores
  today's prompts byte for byte.
"""
from __future__ import annotations

#: Kept short deliberately: the char cap is meant to bound a handful of real
#: hits, not just one, so the fixed header/line overhead has to be compact -
#: see test_render_lists_items_strongest_first, which needs three hits to fit
#: inside a 200-char cap.
_HEADER = "RECENTLY OVER-USED - avoid these lately:"

_LABELS = {"phrase": "phrasing", "opener": "opening", "name": "name",
           "place_formula": "place-name formula"}


def recent(records, window):
    """The last `window` records by run date."""
    return sorted(records, key=lambda r: r.get("run_date", ""))[-window:]


def render(hits, cfg) -> str:
    """A compact block, strongest first, never exceeding the configured cap."""
    if not cfg.get("enabled") or not hits:
        return ""
    lines, out = [], _HEADER
    for h in sorted(hits, key=lambda x: -x["count"]):
        label = _LABELS.get(h["kind"], h["kind"])
        line = f"\n- {label}: \"{h['item']}\" (x{h['count']})"
        if len(out) + len(line) > cfg["avoid_char_cap"]:
            break
        out += line
        lines.append(line)
    return out if lines else ""
