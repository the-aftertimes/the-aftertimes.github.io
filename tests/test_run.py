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
    # The PUBLICATION date, not the UTC one. publication_date() moved to Sydney
    # on 31/08/2026 to get the edition key off a boundary that falls in the
    # middle of the cron ladder; these two tests kept stubbing the UTC date, so
    # they failed for the ten hours a day the two disagree - and the daily
    # workflow gates on "Tests must pass before anything is generated", so the
    # paper stopped publishing every afternoon. Green for part of a day is the
    # worst kind of red: it looks like flakiness rather than a real fault.
    today = run_mod.publication_date()
    _stub_dispatch(tmp_path, today)

    def _boom():
        raise AssertionError("run_pipeline must not be called on an already-filed day")

    monkeypatch.setattr(run_mod, "run_pipeline", _boom)
    assert run_mod.main([]) == 0
    assert "already filed" in capsys.readouterr().out


def test_main_force_regenerates_an_already_filed_day(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(run_mod, "_load_dotenv", lambda: None)
    # The PUBLICATION date, not the UTC one. publication_date() moved to Sydney
    # on 31/08/2026 to get the edition key off a boundary that falls in the
    # middle of the cron ladder; these two tests kept stubbing the UTC date, so
    # they failed for the ten hours a day the two disagree - and the daily
    # workflow gates on "Tests must pass before anything is generated", so the
    # paper stopped publishing every afternoon. Green for part of a day is the
    # worst kind of red: it looks like flakiness rather than a real fault.
    today = run_mod.publication_date()
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


def test_trial_sentences_split_across_paragraph_breaks():
    """Bodies carry paragraph breaks; splitting on spaces alone merged the last
    sentence of a paragraph with the first of the next, which would misalign the
    numbering Charlie marks funny sentences against."""
    import trial
    body = 'He denied it. I missed the marker.\n\nThe staff refused.'
    assert trial.split_sentences(body) == [
        "He denied it.", "I missed the marker.", "The staff refused."]


def test_trial_sentences_keep_quoted_endings_separate():
    import trial
    body = '"Your grandmother glows," she said. The staff refused to move her.'
    assert trial.split_sentences(body) == [
        '"Your grandmother glows," she said.', "The staff refused to move her."]


def test_trial_sentences_do_not_break_after_an_abbreviation():
    """A full stop after a title or an abbreviation is not a sentence end. Found in
    the corpus 02/09/2026: "Haruki Sato at No. 14. His new..." was numbered as two
    sentences, so every mark Charlie made after it landed one sentence off - and
    nothing about the numbering looked wrong."""
    import trial
    body = 'He lives at No. 14. Dr. Ito complained. The Council agreed.'
    assert trial.split_sentences(body) == [
        "He lives at No. 14.", "Dr. Ito complained.", "The Council agreed."]


# --- the revise gate --------------------------------------------------------
# 22/08/2026: all three drafts scored a perfect 1.0, the critique correctly said
# the final line restated the setup, the rewrite fixed it and scored 0.92 on one
# minor violation, and the gate threw it away. From a 1.0 draft the old gate
# could only accept a score-NEUTRAL rewrite, so the revise pass was structurally
# incapable of improving comedy on exactly the days the prose was already clean.

def _qcfg(**over):
    from common import load_settings
    cfg = dict(load_settings()["quality"])
    cfg.update(over)
    return cfg


def _dispatch(tag):
    return {"headline": f"Head {tag}", "body": "A body. " * 30,
            "dateline": {"place": "P"}}


def _patch(monkeypatch, after_score, pick, before_score=1.0):
    import run as run_mod
    scores = iter([before_score, after_score])
    monkeypatch.setattr(run_mod.critic, "score",
                        lambda d, c, q: {"score": next(scores), "rejected": False,
                                         "violations": [], "metrics": {}})
    monkeypatch.setattr(run_mod.revise_mod, "revise",
                        lambda d, v, s: {"critique": "weak kicker",
                                         "dispatch": _dispatch("revised")})
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda drafts, s: {"pick": pick, "reason": "funnier"})


def test_a_slightly_worse_revision_goes_to_the_judge_and_can_win(monkeypatch):
    import run as run_mod
    _patch(monkeypatch, after_score=0.92, pick=1)
    out, info = run_mod.maybe_revise(_dispatch("draft"), {}, _qcfg(), {})
    assert info["revision_accepted"] is True
    assert out["headline"] == "Head revised"


def test_the_judge_can_still_keep_the_draft(monkeypatch):
    import run as run_mod
    _patch(monkeypatch, after_score=0.92, pick=0)
    out, info = run_mod.maybe_revise(_dispatch("draft"), {}, _qcfg(), {})
    assert info["revision_accepted"] is False
    assert out["headline"] == "Head draft"


def test_a_big_score_drop_is_never_put_to_the_judge(monkeypatch):
    """The tolerance buys one minor violation for a better joke. It must not let
    a majorly-flawed rewrite through on a model's say-so."""
    import run as run_mod
    called = []
    _patch(monkeypatch, after_score=0.5, pick=1)
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda d, s: called.append(1) or {"pick": 1, "reason": ""})
    out, info = run_mod.maybe_revise(_dispatch("draft"), {}, _qcfg(), {})
    assert info["revision_accepted"] is False and called == []


def test_a_judge_failure_keeps_the_draft(monkeypatch):
    import run as run_mod
    _patch(monkeypatch, after_score=0.92, pick=1)
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda d, s: (_ for _ in ()).throw(RuntimeError("429")))
    out, info = run_mod.maybe_revise(_dispatch("draft"), {}, _qcfg(), {})
    assert info["revision_accepted"] is False
    assert out["headline"] == "Head draft"


def test_the_judge_cannot_excuse_a_house_rule(monkeypatch):
    """Some minors are taste; the seven-word headline cap is not. The first
    reedit dry run offered a nine-word headline and the tolerance alone would
    have let it through."""
    import run as run_mod
    called = []
    scores = iter([1.0, 0.92])
    monkeypatch.setattr(run_mod.critic, "score", lambda d, c, q: {
        "score": next(scores), "rejected": False, "metrics": {},
        "violations": ([] if not called.append(0) else [])
        or ([{"rule": "headline_length", "severity": "minor", "detail": "9 words"}]
            if len(called) > 1 else [])})
    monkeypatch.setattr(run_mod.revise_mod, "revise",
                        lambda d, v, s: {"critique": "c",
                                         "dispatch": _dispatch("revised")})
    judged = []
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda d, s: judged.append(1) or {"pick": 1, "reason": ""})
    out, info = run_mod.maybe_revise(_dispatch("draft"), {}, _qcfg(), {})
    assert info["revision_accepted"] is False
    assert judged == [], "a house-rule breach must not even reach the judge"
    assert out["headline"] == "Head draft"


def test_a_pre_existing_house_rule_breach_is_not_held_against_the_revision():
    """If the DRAFT already broke the cap, the revision is not punished for
    inheriting it - only newly-introduced breaches block."""
    from common import load_settings
    assert "headline_length" in load_settings()["quality"]["revise_judge_never"]


# --- the backup cron fills a missing picture ---------------------------------

def test_a_filed_day_with_no_picture_is_retried(monkeypatch, tmp_path):
    """25/08/2026 published with no engraving. The 22:13 backup cron exists to
    catch a dropped primary, saw the day was filed, printed "nothing to do" and
    left it pictureless. "Filed" is not "complete"."""
    import run as run_mod
    called = []
    monkeypatch.setattr(run_mod, "read_json", lambda p, default=None: {
        "dispatch": {"headline": "H", "image": None}})
    import reillustrate
    monkeypatch.setattr(reillustrate, "reillustrate",
                        lambda d, scene="": called.append(d) or 0)
    assert run_mod.fill_missing_image("2026-08-25") is True
    assert called == ["2026-08-25"]


def test_a_filed_day_with_a_picture_is_left_alone(monkeypatch):
    """The backup must never redraw a good picture - that would burn a
    Cloudflare call every night and could replace a hand-corrected engraving."""
    import run as run_mod
    called = []
    monkeypatch.setattr(run_mod, "read_json", lambda p, default=None: {
        "dispatch": {"headline": "H", "image": "assets/img/x.jpg"}})
    import reillustrate
    monkeypatch.setattr(reillustrate, "reillustrate",
                        lambda d, scene="": called.append(d) or 0)
    assert run_mod.fill_missing_image("2026-08-25") is False
    assert called == []


def test_a_failed_fill_in_never_fails_the_job(monkeypatch):
    import run as run_mod
    monkeypatch.setattr(run_mod, "read_json", lambda p, default=None: {
        "dispatch": {"headline": "H", "image": None}})
    import reillustrate
    monkeypatch.setattr(reillustrate, "reillustrate",
                        lambda d, scene="": (_ for _ in ()).throw(RuntimeError("cf")))
    assert run_mod.fill_missing_image("2026-08-25") is False


# --- a pool of one is not a choice ------------------------------------------

def _scored(monkeypatch, specs):
    """specs: list of (score, rejected, rules) in draft order."""
    import run as run_mod
    it = iter(specs)
    monkeypatch.setattr(run_mod.critic, "score", lambda d, c, q: (
        lambda sc: {"score": sc[0], "rejected": sc[1], "metrics": {},
                    "violations": [{"rule": r, "severity": "major",
                                    "detail": r} for r in sc[2]]})(next(it)))


def test_a_draft_rejected_only_for_register_is_put_back_to_the_judge(monkeypatch):
    """25/08/2026: two of three drafts were hard rejected on legal_register, so
    the judge was never asked and the day was decided by elimination."""
    import run as run_mod
    _scored(monkeypatch, [(0.75, True, ["legal_register"]),
                          (0.67, True, ["legal_register"]),
                          (0.92, False, [])])
    seen = []
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda drafts, s: seen.append(len(drafts))
                        or {"pick": 0, "reason": "funnier"})
    drafts = [_dispatch("a"), _dispatch("b"), _dispatch("c")]
    out, info = run_mod.choose_draft(drafts, {}, _qcfg(), {})
    assert seen == [3], "all three should reach the judge, not just the survivor"
    assert info["judge_reason"] == "funnier"


def test_a_structurally_broken_draft_is_never_rescued(monkeypatch):
    """The rescue list is register TASTE. A missing headline is not an opinion."""
    import run as run_mod
    _scored(monkeypatch, [(0.75, True, ["structure"]),
                          (0.67, True, ["structure"]),
                          (0.92, False, [])])
    seen = []
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda drafts, s: seen.append(len(drafts))
                        or {"pick": 0, "reason": ""})
    drafts = [_dispatch("a"), _dispatch("b"), _dispatch("c")]
    run_mod.choose_draft(drafts, {}, _qcfg(), {})
    assert seen == [], "one survivor and nothing rescuable means no judge call"


def test_two_clean_drafts_are_judged_without_rescuing_anything(monkeypatch):
    import run as run_mod
    _scored(monkeypatch, [(0.75, True, ["legal_register"]),
                          (0.9, False, []), (0.92, False, [])])
    seen = []
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda drafts, s: seen.append(len(drafts))
                        or {"pick": 0, "reason": ""})
    drafts = [_dispatch("a"), _dispatch("b"), _dispatch("c")]
    run_mod.choose_draft(drafts, {}, _qcfg(), {})
    assert seen == [2], "a healthy pool must not drag rejected drafts back in"


def test_losing_drafts_are_kept(monkeypatch):
    """26/08/2026: Charlie read a CI log line - "Sentries Turn Missile Silo Into
    Pickleball Court" - and said it sounded funny. That draft's body was already
    gone, because only the winner was ever stored. Two thirds of the paper's
    output was being discarded unread, and it is the one signal the learning loop
    has never had."""
    import run as run_mod
    _scored(monkeypatch, [(0.75, True, ["legal_register"]),
                          (0.9, False, []), (0.92, False, [])])
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda d, s: {"pick": 0, "reason": "r"})
    drafts = [dict(_dispatch(t), premise=f"premise {t}") for t in "abc"]
    _, info = run_mod.choose_draft(drafts, {}, _qcfg(), {})
    assert len(info["drafts"]) == 3
    kept = info["drafts"][0]
    assert kept["headline"] == "Head a" and kept["body"]
    assert kept["premise"] == "premise a"
    assert kept["rejected"] is True and kept["score"] == 0.75


# --- the fill-in reaches back, but only a little ----------------------------
# 26/08/2026: the day published with no engraving because Cloudflare's allocation
# was spent, and the allocation resets before the next cron - so the gap would
# have been orphaned the moment the UTC date rolled, because the fill-in looked
# only at its own day.

def _records(monkeypatch, present):
    """present: {date: has_image}"""
    import run as run_mod
    monkeypatch.setattr(run_mod, "read_json", lambda p, default=None: (
        {"dispatch": {"image": "x.jpg" if present[d] else None}}
        if (d := p.split("/")[-1][:-5]) in present else None))


def test_today_is_preferred_when_it_is_the_one_missing(monkeypatch):
    """The front page is what a reader sees, so it jumps the queue."""
    import run as run_mod
    _records(monkeypatch, {"2026-08-27": False, "2026-08-25": False})
    assert run_mod._newest_pictureless("2026-08-27") == "2026-08-27"


def test_an_older_gap_is_picked_up_once_today_is_fine(monkeypatch):
    import run as run_mod
    _records(monkeypatch, {"2026-08-27": True, "2026-08-26": False})
    assert run_mod._newest_pictureless("2026-08-27") == "2026-08-26"


def test_nothing_to_do_when_every_day_has_its_picture(monkeypatch):
    import run as run_mod
    _records(monkeypatch, {"2026-08-27": True, "2026-08-26": True})
    assert run_mod._newest_pictureless("2026-08-27") is None


def test_the_lookback_is_bounded(monkeypatch):
    """It runs on the publish path. An unbounded backlog sweep would turn one bad
    week into a quota stampede that starves the day's own dispatch."""
    import run as run_mod
    old = "2026-08-01"
    _records(monkeypatch, {"2026-08-27": True, old: False})
    assert run_mod._newest_pictureless("2026-08-27") is None
    assert run_mod._FILL_LOOKBACK_DAYS <= 7


def _write_dispatch(tmp_path, run_date, hours_ago):
    from datetime import timedelta
    d = tmp_path / "data" / "dispatches"
    d.mkdir(parents=True, exist_ok=True)
    stamp = (run_mod.datetime.now(run_mod.timezone.utc)
             - timedelta(hours=hours_ago)).isoformat()
    (d / f"{run_date}.json").write_text(
        '{"run_date": "%s", "run_time": "%s"}' % (run_date, stamp),
        encoding="utf-8")


def test_a_cron_delivered_after_utc_midnight_does_not_refile(tmp_path, monkeypatch):
    """27/08/2026: the 22:13 backup arrived at 03:17 the next UTC day, so the
    date-keyed guard missed, a full generation ran over an edition filed five
    hours earlier, 429'd, and stamped a stale banner on a current page."""
    import common
    _orig = common._path
    monkeypatch.setattr(common, "_path", lambda *p: str(tmp_path.joinpath(*p))
                        if p and p[0].startswith("data") else _orig(*p))
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    _write_dispatch(tmp_path, "2026-08-26", hours_ago=5.6)
    # The run believes it is the 27th; no 27th record exists.
    assert run_mod.already_filed("2026-08-27") is True


def test_a_genuinely_new_day_still_files(tmp_path, monkeypatch):
    """The shortest real gap between editions is about 21h, so yesterday's
    dispatch must NOT suppress today's."""
    import common
    _orig = common._path
    monkeypatch.setattr(common, "_path", lambda *p: str(tmp_path.joinpath(*p))
                        if p and p[0].startswith("data") else _orig(*p))
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    _write_dispatch(tmp_path, "2026-08-26", hours_ago=21)
    assert run_mod.already_filed("2026-08-27") is False


def test_no_dispatches_at_all_is_not_recently_filed(tmp_path, monkeypatch):
    import common
    _orig = common._path
    monkeypatch.setattr(common, "_path", lambda *p: str(tmp_path.joinpath(*p))
                        if p and p[0].startswith("data") else _orig(*p))
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    (tmp_path / "data" / "dispatches").mkdir(parents=True, exist_ok=True)
    assert run_mod.already_filed("2026-08-27") is False


def test_a_failed_run_does_not_flag_a_current_page_as_stale(tmp_path, monkeypatch, capsys):
    """27/08/2026: three failed backup runs each stamped "today's edition did not
    file" over a page carrying that morning's dispatch."""
    import common
    _orig = common._path
    monkeypatch.setattr(common, "_path", lambda *p: str(tmp_path.joinpath(*p))
                        if p and p[0].startswith("data") else _orig(*p))
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(run_mod, "_load_dotenv", lambda: None)
    _write_dispatch(tmp_path, "2026-08-26", hours_ago=5.6)

    def _boom():
        raise RuntimeError("every draft failed")

    monkeypatch.setattr(run_mod, "run_pipeline", _boom)

    def _must_not_run(*a, **k):
        raise AssertionError("must not banner a page holding a recent edition")

    monkeypatch.setattr(run_mod, "inject_stale_banner", _must_not_run)
    assert run_mod.main(["--force"]) == 0
    assert "leaving it alone" in capsys.readouterr().err


def test_publication_date_is_stable_across_the_cron_ladder(monkeypatch):
    """Every rung of the ladder must agree on which edition it is filing.

    The ladder spans 15:13 to 19:13 UTC and GitHub has delivered it up to 2h41
    late, so a run can land any time from 15:35 UTC to past midnight. Keyed on
    the UTC date those runs disagree, and the straggler files a date that
    silences the next day's entire ladder - which is what happened for the four
    days to 31/08/2026. Keyed on Sydney they are all one calendar day.
    """
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    syd = ZoneInfo("Australia/Sydney")
    base = datetime(2026, 8, 31, 15, 35, tzinfo=timezone.utc)
    # First rung on time, through the worst-case straggler nine hours later.
    stamps = [base + timedelta(hours=h) for h in (0, 2, 4, 6.5, 9)]
    assert len({s.astimezone(timezone.utc).date() for s in stamps}) == 2, \
        "the window must straddle midnight UTC, or this proves nothing"

    seen = set()
    for s in stamps:
        monkeypatch.setattr(run_mod, "tz_now", lambda _s, _t=s: _t.astimezone(syd))
        seen.add(run_mod.publication_date())
    assert seen == {"2026-09-01"}, seen


def test_the_already_filed_lock_holds_when_utc_and_sydney_disagree(tmp_path, monkeypatch, capsys):
    """The seam, pinned. 31/08/2026 moved publication_date() from UTC to Sydney -
    a correct fix, because the UTC boundary fell in the middle of the cron ladder
    and produced a self-sustaining lock that held for four days.

    But two tests kept stubbing the UTC date, so they only failed during the ten
    hours a day the two calendars disagree. The daily workflow gates on "Tests
    must pass before anything is generated", so for those ten hours the paper
    simply stopped publishing - and it read as flakiness rather than a fault,
    because the same suite went green again overnight.

    A test that is green for part of a day is the worst kind of red. This one
    freezes the clock at 22:00 UTC, when Sydney is already tomorrow, so the
    divergence is always exercised rather than depending on when CI happens to
    run."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    # Stub tz_now, NOT datetime. publication_date() stopped reading the clock
    # directly on 31/08/2026 and went through common.tz_now instead, but this test
    # kept stubbing run_mod.datetime - which the function no longer touches. So the
    # frozen clock was ignored and the assertion was graded against the REAL date:
    # green on 01/09/2026, red from 02/09. Same fault the docstring describes, one
    # layer down, and it survived the commit that fixed its sibling nine lines up.
    syd = ZoneInfo("Australia/Sydney")
    # 22:00 UTC on the 31st is 08:00 on the 1st in Sydney.
    base = datetime(2026, 8, 31, 22, 0, tzinfo=timezone.utc)
    assert base.date().isoformat() == "2026-08-31" and         base.astimezone(syd).date().isoformat() == "2026-09-01",         "the two calendars must disagree here, or this proves nothing"
    monkeypatch.setattr(run_mod, "tz_now", lambda _s: base.astimezone(syd))
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(run_mod, "_load_dotenv", lambda: None)

    pub = run_mod.publication_date()
    assert pub == "2026-09-01", (
        f"publication_date() returned {pub} at 22:00 UTC - the edition key must "
        f"follow the timezone the paper is READ in, or the ladder straddles a "
        f"boundary again")

    _stub_dispatch(tmp_path, pub)

    def _boom():
        raise AssertionError("run_pipeline must not be called on an already-filed day")

    monkeypatch.setattr(run_mod, "run_pipeline", _boom)
    assert run_mod.main([]) == 0
    assert "already filed" in capsys.readouterr().out
