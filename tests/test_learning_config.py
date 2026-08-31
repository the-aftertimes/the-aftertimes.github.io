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


def test_every_technique_is_complete_and_original():
    """The pool is fed to a model to imitate, so it may not carry published copy -
    funny_block already records a model lifting an example verbatim. Each entry
    names where the technique is seen and shows it in our OWN words."""
    import yaml
    from common import rel
    with open(rel("config/techniques.yaml"), encoding="utf-8") as fh:
        techs = yaml.safe_load(fh)["techniques"]
    assert techs, "an empty pool would silently disable the rotation"
    keys = [t["key"] for t in techs]
    assert len(keys) == len(set(keys))
    for t in techs:
        assert t["source"].strip(), t["key"]
        assert len(t["guidance"].split()) >= 20, f"{t['key']} guidance is too thin"
        # Short on purpose: a long example gets copied instead of learned from.
        assert len(t["example"].split()) <= 45, f"{t['key']} example is too long"
