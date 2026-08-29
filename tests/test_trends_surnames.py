"""A surname that recurs under different forenames is the repeat a reader sees.

`repeated_names` keyed on the full name, which caught "Kaelen Voss" three times and
missed "Chen" six times - Priya Chen, Haruki Chen, Jori Chen and three more read as six
distinct names, none reaching min_count. Measured over the first 31 published dispatches
on 29/08/2026: 17 of the 31 used one of Chen, Osei, Voss or Thorne, and the avoid block
the writer received named exactly one of them.

Also guards the thing that made the fix take three attempts: a scripted edit can put a
literal control character where a regex escape was meant. It compiles, imports, runs on
every record and matches nothing, and looks exactly like working detection.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import trends  # noqa: E402


def _rec(date, body):
    return {"run_date": date, "dispatch": {"headline": "H", "body": body}}


def test_surname_repeating_under_different_forenames_is_caught():
    recs = [
        _rec("2026-01-01", 'Priya Chen said the vents were fine.'),
        _rec("2026-01-02", 'Haruki Chen told the board otherwise.'),
        _rec("2026-01-03", 'Jori Chen refused to comment further.'),
    ]
    items = {h["item"] for h in trends.repeated_names(recs, min_count=3)}
    assert "Chen" in items, items


def test_a_full_name_repeating_is_reported_as_the_full_name():
    recs = [_rec(f"2026-01-0{i}", "Kaelen Voss objected loudly.") for i in (1, 2, 3)]
    hits = trends.repeated_names(recs, min_count=3)
    items = {h["item"] for h in hits}
    assert "Kaelen Voss" in items
    # and not ALSO the bare surname at the same strength, which would say it twice
    assert "Voss" not in items, items


def test_a_surname_under_the_threshold_is_not_reported():
    recs = [_rec("2026-01-01", "Priya Chen spoke."), _rec("2026-01-02", "Ada Chen spoke.")]
    assert trends.repeated_names(recs, min_count=3) == []


def test_number_words_are_not_treated_as_surnames():
    recs = [_rec(f"2026-01-0{i}", "Sister Four opened the hatch on Deck Four.")
            for i in (1, 2, 3)]
    items = {h["item"] for h in trends.repeated_names(recs, min_count=3)}
    assert "Four" not in items, items


def test_no_source_file_carries_a_control_character():
    """0x07 bell, 0x08 backspace, 0x0b vertical tab, 0x0c form feed. None belongs in
    Python source and each is invisible in a diff, so a regex escape written as a
    literal control byte silently matches nothing forever."""
    bad = {7: "bell", 8: "backspace", 11: "vertical tab", 12: "form feed"}
    offenders = []
    files = sorted(list(ROOT.glob("*.py")) + list((ROOT / "tools").glob("*.py"))
                   + list((ROOT / "tests").glob("*.py")))
    for f in files:
        hits = {bad[b] for b in f.read_bytes() if b in bad}
        if hits:
            offenders.append(f"{f.name}: {', '.join(sorted(hits))}")
    assert not offenders, offenders
    assert len(files) > 20, f"only scanned {len(files)} files, expected the whole repo"
