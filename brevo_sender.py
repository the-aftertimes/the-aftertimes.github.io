"""Brevo sender/domain admin, run from GitHub Actions where BREVO_API_KEY lives.

    python brevo_sender.py list
    python brevo_sender.py create

Exists because Brevo cannot authenticate a freemail From address: it rewrites the
From to its own SHARED `<id>.brevosend.com` domain, and you inherit that shared
domain's cold reputation, so a new subscriber's FIRST edition reliably lands in
spam. Sending from an authenticated domain fixes it.

The authenticated domain alone is NOT enough - the address must also exist as a
Sender, or the campaign API returns 400 "Sender is invalid / inactive". That is
what `create` does. It is idempotent: an existing sender is reported, not
duplicated.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from common import load_settings

API = "https://api.brevo.com/v3"


def _key() -> str:
    k = os.environ.get("BREVO_API_KEY", "").strip()
    if not k:
        print("BREVO_API_KEY not set", file=sys.stderr)
        raise SystemExit(1)
    return k


#: Cloudflare sits in front of parts of the Brevo API and rejects urllib's default
#: "Python-urllib/3.x" agent with 403 error 1010 browser_signature_banned. The
#: /senders endpoints refuse it even though /emailCampaigns (used by send_email.py)
#: does not, so a plain UA is required here.
_UA = "the-aftertimes/1.0 (+https://aftertimes.charlietrenorden.com)"


def _call(path: str, payload: dict | None = None):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"api-key": _key(), "accept": "application/json",
                 "content-type": "application/json", "user-agent": _UA},
        method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode()
            return resp.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode()[:400]}


def diagnose() -> None:
    """Evidence for WHY Brevo put this account under validation (13/08/2026).

    The 402 says the account is under review but not what triggered it. The
    usual triggers are visible through the API, so gather them before anyone
    guesses or clicks through the dashboard: list growth (a sudden spike of
    signups is the list-bombing pattern their anti-abuse team looks for),
    contact provenance, and the bounce/complaint rates on the campaigns that
    were actually delivered. Read-only."""
    status, acct = _call("/account")
    print(f"== account (HTTP {status})")
    if status == 200:
        plan = (acct.get("plan") or [{}])
        print(f"  email      : {acct.get('email')}")
        print(f"  company    : {(acct.get('companyName') or '?')}")
        for p in plan:
            print(f"  plan       : {p.get('type')} credits={p.get('credits')} "
                  f"({p.get('creditsType')})")
    else:
        print(f"  {acct}", file=sys.stderr)

    status, lists = _call("/contacts/lists?limit=50")
    print(f"\n== lists (HTTP {status})")
    for l in lists.get("lists", []):
        print(f"  id={l.get('id'):<4} {str(l.get('name'))[:34]:<34} "
              f"subscribers={l.get('totalSubscribers')} "
              f"blacklisted={l.get('totalBlacklisted')}")

    # Newest contacts first: a burst of addresses created within minutes of each
    # other, or obvious junk domains, is the signal that a single-opt-in form was
    # abused. Modified-desc is the only ordering the endpoint offers.
    status, contacts = _call("/contacts?limit=50&sort=desc")
    print(f"\n== newest contacts (HTTP {status}) "
          f"total={contacts.get('count')}")
    for c in contacts.get("contacts", [])[:25]:
        print(f"  {str(c.get('createdAt'))[:19]}  {c.get('email')}  "
              f"blacklisted={c.get('emailBlacklisted')}")

    # Deliverability on what DID go out. High hard-bounce or complaint rates are
    # the other common trigger and would point somewhere different entirely.
    status, camps = _call("/emailCampaigns?limit=8&sort=desc")
    print(f"\n== recent campaigns (HTTP {status})")
    for c in camps.get("campaigns", []):
        g = ((c.get("statistics") or {}).get("globalStats") or {})
        print(f"  {str(c.get('sentDate'))[:10]}  id={c.get('id'):<4} "
              f"{c.get('status'):<10} sent={g.get('sent', 0)} "
              f"deliv={g.get('delivered', 0)} hardB={g.get('hardBounces', 0)} "
              f"softB={g.get('softBounces', 0)} spam={g.get('complaints', 0)} "
              f"unsub={g.get('unsubscriptions', 0)}")


def show() -> None:
    status, data = _call("/senders")
    print(f"senders HTTP {status}")
    for s in data.get("senders", []):
        print(f"  id={s.get('id')}  {s.get('email')}  active={s.get('active')}")
    status, data = _call("/senders/domains")
    print(f"domains HTTP {status}")
    for d in data.get("domains", []):
        print(f"  {d.get('domain_name')}  authenticated={d.get('authenticated')}"
              f"  verified={d.get('verified')}")


def whoami() -> None:
    """Which Brevo account is this key actually for, and what state is it in?

    Added 12/08/2026, when campaign creation started returning HTTP 402
    account_under_validation and the login address for the account was not
    known. The key identifies the account even when nobody can sign in, so
    /account is the cheapest way to recover the owner email. Read-only.
    """
    status, data = _call("/account")
    print(f"account HTTP {status}")
    if status != 200:
        print(f"  {data}", file=sys.stderr)
        raise SystemExit(1)
    print(f"  login email : {data.get('email')}")
    print(f"  name        : {data.get('firstName')} {data.get('lastName')}")
    print(f"  company     : {data.get('companyName')}")
    plan = data.get("plan")
    if isinstance(plan, list):
        for p in plan:
            print(f"  plan        : {p.get('type')} credits={p.get('credits')}")
    rel_ = data.get("relay") or {}
    if rel_:
        print(f"  relay       : enabled={rel_.get('enable')}")
    # Anything the API volunteers about a hold is worth seeing verbatim, since
    # the 402 body itself says nothing beyond "under validation".
    for k in ("marketingAutomation", "status", "state", "validation"):
        if k in data:
            print(f"  {k}: {data[k]}")


def create() -> None:
    """Create the configured sender if it is missing. The address and name come
    from config/settings.yaml, so the config stays the single source of truth."""
    nl = load_settings()["newsletter"]
    email, name = nl["sender_email"], nl["sender_name"]
    domain = email.split("@")[-1]

    status, data = _call("/senders/domains")
    match = next((d for d in data.get("domains", [])
                  if d.get("domain_name") == domain), None)
    if not match:
        print(f"WARN {domain} is not in this Brevo account's domain list; "
              f"Brevo will rewrite the From address", file=sys.stderr)
    elif not match.get("authenticated"):
        print(f"WARN {domain} exists but is NOT authenticated; Brevo will "
              f"rewrite the From address", file=sys.stderr)
    else:
        print(f"OK {domain} is authenticated")

    status, data = _call("/senders")
    existing = next((s for s in data.get("senders", [])
                     if (s.get("email") or "").lower() == email.lower()), None)
    if existing:
        print(f"OK sender already exists: id={existing.get('id')} {email} "
              f"active={existing.get('active')}")
        return
    status, data = _call("/senders", {"name": name, "email": email})
    if status in (201, 200):
        print(f"CREATED sender {email} -> {data}")
    else:
        print(f"FAILED to create sender ({status}): {data}", file=sys.stderr)
        raise SystemExit(1)


def campaign() -> None:
    """Print the sender actually recorded on the most recent campaign. This is the
    load-bearing check: an authenticated domain and an existing Sender only matter
    if the campaign really went out under that From address."""
    status, data = _call("/emailCampaigns?limit=1&sort=desc")
    print(f"campaigns HTTP {status}")
    for c in data.get("campaigns", []):
        s = c.get("sender") or {}
        email = s.get("email", "")
        print(f"  id={c.get('id')}  status={c.get('status')}")
        print(f"  subject={c.get('subject', '')[:60]}")
        print(f"  FROM: {s.get('name')} <{email}>")
        if "brevosend.com" in email:
            print("  BAD: still going out on Brevo's shared domain",
                  file=sys.stderr)
        elif email:
            print("  GOOD: sending from an authenticated domain")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    {"list": show, "create": create, "campaign": campaign,
     "whoami": whoami, "diagnose": diagnose}.get(action, show)()
