import send_email


REC = {
    "run_date": "2026-07-29",
    "dispatch": {
        "headline": "Test Headline",
        "body": "A paragraph.\nAnother paragraph.",
        "dateline": {"place": "Somewhere", "year": 2400, "month": 1, "day": 1,
                     "years_from_now": 374},
        "wire": {"name": "", "gloss": ""},
        "domain": "law",
        "glossary": [],
    },
    "meta": {"site_name": "The Aftertimes",
             "base_url": "https://the-aftertimes.github.io"},
}


def test_dry_run_without_key_never_hits_api(monkeypatch, capsys):
    monkeypatch.setattr(send_email, "_latest_dispatch", lambda: REC)
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    # If _post is ever called in a dry-run, that is a bug (it would send).
    def _boom(*a, **k):
        raise AssertionError("_post must not be called during a dry-run")
    monkeypatch.setattr(send_email, "_post", _boom)
    monkeypatch.setattr(send_email, "read_json", lambda *a, **k: {})  # no prior guard
    assert send_email.main() == 0
    assert "DRY-RUN" in capsys.readouterr().out


def test_no_dispatch_returns_error(monkeypatch):
    monkeypatch.setattr(send_email, "_latest_dispatch", lambda: None)
    assert send_email.main() == 1
