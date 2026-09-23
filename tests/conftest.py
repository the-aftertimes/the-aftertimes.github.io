import os
import random

import pytest

import common


#: NO TEST MAY WRITE TO THE LIVE SITE.
#:
#: Twice now a test has published over the real paper. 09/09/2026 a fixture
#: patched `common.rel` on eight modules but not `_path`, and overwrote the
#: 2026-09-09 dispatch and the ledger. 23/09/2026 a `monkeypatch.undo()` meant
#: to disarm one mock also undid the temp-root patch, and the REAL run_pipeline
#: wrote index.html, a permalink, a dispatch record and a ledger entry - caught
#: only by `git status` afterwards, which is not a guard, it is luck.
#:
#: Both times the test still PASSED or failed for an unrelated reason. So the
#: check belongs here, where no individual test can forget it: the files the
#: site is made of are fingerprinted before every test and compared after. A
#: test that legitimately writes them is one that patched `common._path` to a
#: temp root, in which case the real ones never move.
_WATCHED = ("index.html", "archive.html", "data/ledger.json", "data/bible.json",
            "data/wip.json")


#: Captured at import, before any test can patch it - so the fingerprint always
#: reads the REAL files even while a test has _path pointed at a temp root.
_REAL_PATH = common._path


def _fingerprint() -> dict:
    out = {}
    for name in _WATCHED:
        path = _REAL_PATH(*name.split("/"))
        try:
            out[name] = os.path.getmtime(path), os.path.getsize(path)
        except OSError:
            out[name] = None
    try:
        out["dispatches"] = sorted(os.listdir(_REAL_PATH("data", "dispatches")))
    except OSError:
        out["dispatches"] = None
    return out


@pytest.fixture(autouse=True)
def _no_writes_to_the_live_site(request):
    before = _fingerprint()
    yield
    # Take the fingerprint with the ORIGINAL _path: a test that patched it has
    # had its patch undone by now, so this compares the real files either way.
    after = _fingerprint()
    changed = [k for k in before if before[k] != after[k]]
    assert not changed, (
        f"{request.node.name} wrote to the live site: {changed}. A test must "
        f"patch common._path to a temp root before running anything that "
        f"writes - see tests/test_haiku_pipeline.py's `repo` fixture.")


@pytest.fixture
def rng():
    return random.Random(12345)


@pytest.fixture
def date_cfg():
    return {
        "min_years": 8,
        "band_weights": [0.70, 0.25, 0.05],
        "bands": {"near": [8, 300], "mid": [300, 3000], "deep": [3000, 40000]},
        "anti_cluster": {"era_bucket_years": 50, "avoid_recent_days": 5,
                         "max_attempts": 12},
    }


@pytest.fixture
def quality_cfg():
    return {
        "n_drafts": 3, "judge": True, "revise": True,
        "hard_reject": ["structure", "machine_phrases", "legal_register",
                        "dash_residue", "us_spelling"],
        "weights": {"major": 0.25, "minor": 0.08},
        "rhythm": {"mean_min": 14, "mean_max": 20, "mean_hard_min": 12,
                   "mean_hard_max": 24, "longest_max": 35, "min_short": 2},
        "length": {"min": 200, "max": 280, "hard_min": 160, "hard_max": 340},
        "plainness": {"rate_max": 5.0, "rate_major": 7.0},
    }
