"""Send the daily dispatch to the mailing list (Brevo). Ported from One Story.

Runs in the daily CI job after the page is built. Safe by default:
- Dry-run unless BREVO_API_KEY is set AND the newsletter is fully configured
  (enabled, a verified sender_email, and a list_id) in settings, so it never
  sends from a local run or a half-configured repo.
- A per-day guard (data/last_email.json) means re-running the job the same day
  will NOT send a second email.

Brevo has no single "send this HTML to a list" call, so the flow is two steps:
create the campaign as a draft (POST /v3/emailCampaigns) then send it
(POST /v3/emailCampaigns/{id}/sendNow). --test uses sendTest to a single address
(BREVO_TEST_EMAIL) so it never touches the live list, and leaves the daily guard
untouched.

Usage:
    python send_email.py            # sends if configured, else dry-run
    python send_email.py --dry-run  # force dry-run (build + print, never send)
    python send_email.py --test     # create + send a test to BREVO_TEST_EMAIL only
"""
from __future__ import annotations

import glob
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

from common import load_settings, read_json, rel, write_json
from email_render import build_email

_STATE = "data/last_email.json"
# Set when Brevo refuses to create campaigns at all (account under manual
# review). While it exists, we do not call the API - see _hold_reason().
_HOLD = "data/send_hold.json"
# Brevo error codes that mean "stop asking", not "try again later".
_HOLD_CODES = {"account_under_validation", "account_blocked", "account_disabled"}


def _hold_reason() -> dict | None:
    return read_json(_HOLD, default=None) or None


def _record_hold(code: str, message: str, run_date: str) -> None:
    """Latch a hold so the next run short-circuits.

    Brevo put this account under validation on 10/08/2026 and BOTH projects kept
    calling campaign creation every day, twice daily counting the backup cron -
    roughly a dozen rejected attempts against an account already under manual
    review, which is exactly what retry abuse looks like to whoever is assessing
    it. Persisted under data/, which the daily workflow commits, because the CI
    runner itself is ephemeral."""
    existing = _hold_reason()
    if existing:
        return
    write_json(_HOLD, {"code": code, "message": message[:300],
                       "first_seen": run_date, "attempts_stopped_after": run_date})
    print(f"HOLD RECORDED ({code}) - further sends will be skipped until this is "
          f"cleared with: python send_email.py --clear-hold", file=sys.stderr)


def _latest_dispatch() -> dict | None:
    files = sorted(glob.glob(rel("data/dispatches/*.json")))
    if not files:
        return None
    return read_json(f"data/dispatches/{os.path.basename(files[-1])}")


def _post(url: str, key: str, payload: dict | None) -> tuple[int, dict]:
    """POST JSON to Brevo. payload=None sends an empty-body POST (sendNow)."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"api-key": key,
                 "content-type": "application/json",
                 "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", "replace")
        return resp.status, (json.loads(raw) if raw.strip() else {})


def main() -> int:
    force_dry = "--dry-run" in sys.argv
    force_test = "--test" in sys.argv   # send a test to BREVO_TEST_EMAIL, no guard
    if "--clear-hold" in sys.argv:
        held = _hold_reason()
        if not held:
            print("No hold in place.")
            return 0
        os.remove(rel(_HOLD))
        print(f"Cleared hold ({held.get('code')}, first seen "
              f"{held.get('first_seen')}). The next run will attempt a send.")
        return 0
    settings = load_settings()
    record = _latest_dispatch()
    if not record:
        print("No dispatch to send - run the pipeline first.")
        return 1

    subject, body = build_email(record["dispatch"], record["meta"])
    if force_test:
        # Make each test subject unique so Gmail doesn't thread/de-dupe repeated
        # tests of the same day's edition (which hid earlier template changes).
        subject = f"{subject} [test {datetime.now().strftime('%H:%M:%S')}]"
    run_date = record["run_date"]
    nl = settings.get("newsletter") or {}
    key = os.environ.get("BREVO_API_KEY", "").strip()
    sender_email = str(nl.get("sender_email") or "").strip()
    list_id = nl.get("list_id")

    # Already sent today? (the one-off test ignores this)
    last = (read_json(_STATE, default={}) or {}).get("date")
    if last == run_date and not force_dry and not force_test:
        print(f"Already emailed for {run_date}; skipping.")
        return 0

    if force_dry or not (key and nl.get("enabled") and sender_email and list_id):
        why = ("--dry-run" if force_dry else
               "no BREVO_API_KEY" if not key else
               "newsletter disabled" if not nl.get("enabled") else
               "no sender_email in settings" if not sender_email else
               "no list_id in settings")
        print(f"DRY-RUN ({why}) - not sending.")
        print(f"Subject: {subject}")
        print(f"Body: {len(body)} bytes")
        return 0

    held = _hold_reason()
    if held and not force_dry:
        print(f"SEND HELD since {held.get('first_seen')}: {held.get('code')} - "
              f"{held.get('message', '')[:160]}")
        print("Not calling Brevo. Resolve the account, then: "
              "python send_email.py --clear-hold")
        return 2

    api = str(nl.get("api_base") or "https://api.brevo.com/v3").rstrip("/")
    name = f"The Aftertimes {run_date}" + (" [test]" if force_test else "")
    campaign = {
        "name": name,
        "subject": subject,
        "sender": {"name": nl.get("sender_name", "The Aftertimes"), "email": sender_email},
        "htmlContent": body,
        "recipients": {"listIds": [int(list_id)]},
    }
    try:
        status, data = _post(f"{api}/emailCampaigns", key, campaign)
        campaign_id = data.get("id")
        if not campaign_id:
            print(f"Create returned HTTP {status} but no campaign id: {data}",
                  file=sys.stderr)
            return 1

        if force_test:
            recipients = [e.strip() for e in
                          os.environ.get("BREVO_TEST_EMAIL", "").split(",") if e.strip()]
            if not recipients:
                print("--test needs BREVO_TEST_EMAIL set (comma-separated ok).",
                      file=sys.stderr)
                return 1
            _post(f"{api}/emailCampaigns/{campaign_id}/sendTest", key,
                  {"emailTo": recipients})
            print(f"Test of '{subject[:60]}' sent to {recipients} "
                  f"(campaign {campaign_id}; live list untouched, guard left alone).")
            return 0

        _post(f"{api}/emailCampaigns/{campaign_id}/sendNow", key, None)
        print(f"Sent '{subject[:60]}' -> campaign {campaign_id}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        print(f"Send FAILED: HTTP {e.code} {raw[:400]}", file=sys.stderr)
        try:
            code = (json.loads(raw) or {}).get("code", "")
        except ValueError:
            code = ""
        if code in _HOLD_CODES:
            _record_hold(code, raw, run_date)
            return 2
        return 1

    write_json(_STATE, {"date": run_date, "subject": subject})
    print(f"Recorded send for {run_date}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
