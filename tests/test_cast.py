"""The writer is handed its people's names. See cast.py and config/names.yaml."""
import cast
import write
from common import load_yaml

POOL = load_yaml("config/names.yaml")
G, F = POOL["given"], POOL["family"]
DATELINE = {"year": 2300, "years_from_now": 274}


def test_a_cast_is_stable_for_a_draft_and_differs_between_drafts():
    a = cast.draw("2026-10-07:premise one", G, F)
    assert a == cast.draw("2026-10-07:premise one", G, F)   # a resume keeps it
    assert a != cast.draw("2026-10-07:premise two", G, F)
    assert a != cast.draw("2026-10-08:premise one", G, F)


def test_no_name_part_repeats_inside_one_cast():
    for i in range(200):
        names = cast.draw(f"seed {i}", G, F)
        firsts = [n.split()[0] for n in names]
        lasts = [n.split()[1] for n in names]
        assert len(set(firsts)) == len(firsts) and len(set(lasts)) == len(lasts)


def test_names_from_the_last_month_are_held_back():
    used = cast.recent_names(["Adaeze Abiodun said the moss had learnt to talk."])
    for i in range(200):
        for name in cast.draw(f"seed {i}", G, F, used):
            assert "Adaeze" not in name and "Abiodun" not in name


def test_an_avoid_set_that_empties_the_pool_still_gives_a_full_cast():
    assert len(cast.draw("x", G, F, set(G) | set(F))) == 3


def test_the_pool_holds_none_of_the_names_the_model_wore_out():
    worn = {"Chen", "Patel", "Al-Jamil", "Tariq", "Kenji", "Sunita", "Okoro",
            "Vance", "Elena", "Rostova", "Marcus", "Kovac"}
    assert not worn & (set(G) | set(F))
    assert len(set(G)) == len(G) and len(set(F)) == len(F)


def test_a_supplied_cast_replaces_the_invent_your_own_line():
    with_cast = write.build_prompt("p", DATELINE, "transport", "news",
                                   names=["Aino Laine", "Kofi Varga"])
    assert "Aino Laine, Kofi Varga" in with_cast
    assert "invent new ones" not in with_cast
    without = write.build_prompt("p", DATELINE, "transport", "news")
    assert "invent new ones" in without
