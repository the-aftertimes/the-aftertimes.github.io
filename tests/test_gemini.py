import pytest

from gemini import extract_json, GeminiError


def test_extract_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    raw = "```json\n{\"headline\": \"hi\"}\n```"
    assert extract_json(raw) == {"headline": "hi"}


def test_extract_json_with_prose_around_it():
    raw = "Sure! Here is your object:\n{\"x\": [1, 2, 3]}\nHope that helps."
    assert extract_json(raw) == {"x": [1, 2, 3]}


def test_extract_json_raises_on_garbage():
    with pytest.raises(GeminiError):
        extract_json("no json here at all")
