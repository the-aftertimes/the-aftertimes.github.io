import random
import pytest


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
