import yaml

import common
import eyetest


def test_chosen_keeps_picks_and_drops_neither():
    picks = [
        {"at": "2", "a": "A2", "b": "B2", "choice": "neither"},
        {"at": "1", "a": "A1", "b": "B1", "choice": "b"},
        {"at": "3", "a": "A3", "b": "B3", "choice": "both"},
        {"at": "4", "a": "A3", "b": "B4", "choice": "a"},
    ]
    assert eyetest.chosen(picks) == ["B1", "A3", "B3"]


def test_chosen_reads_lineups():
    six = [{"text": f"T{i}"} for i in range(6)]
    picks = [{"at": "1", "mode": "lineup", "items": six, "choice": 4},
             {"at": "2", "mode": "lineup", "items": six, "choice": -1}]
    assert eyetest.chosen(picks) == ["T4"]


def test_append_keeps_comments_and_skips_duplicates(tmp_path, monkeypatch):
    path = tmp_path / "ex.yaml"
    path.write_text("# keep me\nexemplars:\n- old one\n", encoding="utf-8")
    monkeypatch.setattr(common, "_path", lambda p: str(path))
    added = common.append_yaml_list("ex.yaml", "exemplars", ["old one", "new one"])
    text = path.read_text(encoding="utf-8")
    assert added == ["new one"]
    assert text.startswith("# keep me")
    assert yaml.safe_load(text)["exemplars"] == ["old one", "new one"]
