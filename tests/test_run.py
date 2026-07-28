import os

import run as run_mod


def test_inject_stale_banner_returns_false_when_no_page(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    assert run_mod.inject_stale_banner("index.html") is False


def test_inject_stale_banner_marks_existing_page(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    page = tmp_path / "index.html"
    page.write_text("<body><div class=\"wrap\">hi</div></body>", encoding="utf-8")
    assert run_mod.inject_stale_banner("index.html") is True
    assert "Showing yesterday" in page.read_text(encoding="utf-8")


def test_inject_stale_banner_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    page = tmp_path / "index.html"
    page.write_text("<body><div class=\"wrap\">hi</div></body>", encoding="utf-8")
    run_mod.inject_stale_banner("index.html")
    run_mod.inject_stale_banner("index.html")
    assert page.read_text(encoding="utf-8").count("Showing yesterday") == 1
