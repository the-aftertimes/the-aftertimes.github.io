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


def test_hold_short_circuits_the_send(tmp_path, monkeypatch, capsys):
    """Brevo held the account on 10/08/2026 and both projects kept calling
    campaign creation twice a day - retry abuse against an account already under
    manual review. A latched hold must stop the API call entirely."""
    import common
    import send_email as se
    # read_json/write_json resolve through common._path, NOT rel, so patching
    # only the module-local rel leaves the hold file unfindable.
    _orig = common._path
    monkeypatch.setattr(common, "_path", lambda *p: str(tmp_path.joinpath(*p))
                        if p and p[0].startswith("data") else _orig(*p))
    monkeypatch.setattr(se, "rel", lambda p: str(tmp_path / p))
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "send_hold.json").write_text(
        '{"code": "account_under_validation", "message": "under review",'
        ' "first_seen": "2026-08-10"}', encoding="utf-8")

    def _boom(*a, **k):
        raise AssertionError("must not call Brevo while a hold is latched")

    monkeypatch.setattr(se, "_post", _boom)
    monkeypatch.setattr(se, "_latest_dispatch", lambda: {
        "run_date": "2026-08-13",
        "dispatch": {"headline": "H", "body": "B", "dateline": {"place": "P"}},
        "meta": {}})
    monkeypatch.setattr(se, "build_email", lambda d, m: ("subj", "<p>body</p>"))
    monkeypatch.setenv("BREVO_API_KEY", "key")
    monkeypatch.setattr(se.sys, 'argv', ['send_email.py'])
    # The newsletter was retired on 13/08/2026 (newsletter.enabled: false), which
    # makes the live config dry-run before it ever reaches the hold check. Force
    # the enabled config here so this still exercises the hold logic rather than
    # passing for the wrong reason - the module is retired, not deleted.
    _live = se.load_settings()
    monkeypatch.setattr(se, "load_settings", lambda: {
        **_live, "newsletter": {**_live["newsletter"], "enabled": True}})
    assert se.main() == 2
    assert "SEND HELD" in capsys.readouterr().out


def test_hold_records_only_the_latching_codes():
    import send_email as se
    assert "account_under_validation" in se._HOLD_CODES
    assert "rate_limit" not in se._HOLD_CODES
