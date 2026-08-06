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


def _stub_dispatch(tmp_path, run_date):
    d = tmp_path / "data" / "dispatches"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{run_date}.json").write_text("{}", encoding="utf-8")


def test_already_filed_is_false_when_no_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    assert run_mod.already_filed("2026-08-06") is False


def test_already_filed_is_true_once_the_day_is_filed(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    _stub_dispatch(tmp_path, "2026-08-06")
    assert run_mod.already_filed("2026-08-06") is True
    assert run_mod.already_filed("2026-08-07") is False


def test_main_skips_when_the_day_is_already_filed(tmp_path, monkeypatch, capsys):
    """The backup cron must NEVER republish over an edition already emailed."""
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(run_mod, "_load_dotenv", lambda: None)
    today = run_mod.datetime.now(run_mod.timezone.utc).date().isoformat()
    _stub_dispatch(tmp_path, today)

    def _boom():
        raise AssertionError("run_pipeline must not be called on an already-filed day")

    monkeypatch.setattr(run_mod, "run_pipeline", _boom)
    assert run_mod.main([]) == 0
    assert "already filed" in capsys.readouterr().out


def test_main_force_regenerates_an_already_filed_day(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(run_mod, "_load_dotenv", lambda: None)
    today = run_mod.datetime.now(run_mod.timezone.utc).date().isoformat()
    _stub_dispatch(tmp_path, today)
    calls = []
    monkeypatch.setattr(run_mod, "run_pipeline", lambda: calls.append(1))
    assert run_mod.main(["--force"]) == 0
    assert calls == [1]


def test_main_runs_the_pipeline_when_the_day_is_unfiled(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(run_mod, "_load_dotenv", lambda: None)
    calls = []
    monkeypatch.setattr(run_mod, "run_pipeline", lambda: calls.append(1))
    assert run_mod.main([]) == 0
    assert calls == [1]
