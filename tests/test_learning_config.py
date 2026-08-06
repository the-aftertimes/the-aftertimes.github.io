"""The learning loop's configuration, including its kill switch."""
import yaml

from common import rel


def _cfg():
    with open(rel("config/settings.yaml"), encoding="utf-8") as fh:
        return yaml.safe_load(fh)["learning"]


def test_learning_block_present_and_complete():
    c = _cfg()
    assert c["enabled"] is True
    assert c["window"] >= 10           # dispatches considered for staleness
    assert c["min_count"] >= 2         # occurrences before something is stale
    assert c["avoid_char_cap"] > 0
    assert c["exemplar_cap"] > 0
    assert 0 <= c["proposals_weekday"] <= 6


def test_avoid_cap_is_small_enough_not_to_bloat_the_prompt():
    # The whole risk of this feature is re-creating the verbosity we just fixed
    # by growing the prompt without limit.
    assert _cfg()["avoid_char_cap"] <= 2000
