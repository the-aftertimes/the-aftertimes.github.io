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
