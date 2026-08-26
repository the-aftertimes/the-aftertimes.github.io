"""What is actually consuming this account's Cloudflare Workers AI allocation?

    python cfusage.py            # last 7 days, per day and per model
    python cfusage.py --days 30

Written 26/08/2026. Two days that month published with no engraving because the
account's 10,000-neuron daily free allocation was exhausted, and every response to
that so far has been a guess: stagger the crons, split the accounts, pay for
Workers AI. Those are three different answers and the right one depends on a
number nobody has looked at.

What IS known: the photocopy project draws one flux image a day on the same
CF_ACCOUNT_ID. What is not known is whether two images a day can plausibly reach
10,000 neurons, or whether something else on the account is doing it.

The endpoint is deliberately discovered rather than assumed. docs/TODO.md
confidently named `GET /accounts/{id}/ai/usage`, which this script's own probe is
there to confirm or refute - Cloudflare's usage numbers live behind the GraphQL
analytics API (`aiInferenceAdaptiveGroups`), and the REST route may not exist at
all. Both are tried and whatever answers is reported, so the output is evidence
rather than a second guess.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.cloudflare.com/client/v4"
UA = "the-aftertimes/1.0 (+https://aftertimes.charlietrenorden.com)"


def _creds() -> tuple[str, str]:
    acct = os.environ.get("CF_ACCOUNT_ID", "").strip()
    tok = os.environ.get("CF_API_TOKEN", "").strip()
    if not acct or not tok:
        print("CF_ACCOUNT_ID / CF_API_TOKEN not set", file=sys.stderr)
        raise SystemExit(1)
    return acct, tok


def _call(url: str, tok: str, payload: dict | None = None):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"Bearer {tok}", "User-Agent": UA,
                 "Content-Type": "application/json"},
        method="POST" if payload else "GET")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode()[:400]
        except Exception:  # noqa: BLE001
            pass
        return exc.code, {"error": body}


def probe_rest(acct: str, tok: str) -> None:
    """Does a REST usage route exist? docs/TODO.md asserted one; find out."""
    print(">>> REST probe")
    for path in (f"/accounts/{acct}/ai/usage",
                 f"/accounts/{acct}/ai/models/search?per_page=1"):
        status, data = _call(f"{API}{path}", tok)
        ok = data.get("success") if isinstance(data, dict) else None
        print(f"    {status:3}  success={ok}  {path}")
        if status == 200 and path.endswith("usage"):
            print("    " + json.dumps(data.get("result"), indent=2)[:800])


def graphql_usage(acct: str, tok: str, days: int) -> None:
    """The number that actually answers the question: neurons per day, by model.

    aiInferenceAdaptiveGroups is the Workers AI dataset. If the token lacks the
    Account Analytics read permission this returns an errors block rather than
    data, which is itself the finding - say so instead of reporting zero.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    until = datetime.now(timezone.utc).date().isoformat()
    query = """
    query Usage($acct: String!, $since: Date!, $until: Date!) {
      viewer { accounts(filter: {accountTag: $acct}) {
        aiInferenceAdaptiveGroups(
          limit: 1000,
          filter: {date_geq: $since, date_leq: $until},
          orderBy: [date_DESC]
        ) {
          count
          sum { totalNeurons }
          dimensions { date modelId }
        }
      } }
    }"""
    print(f">>> GraphQL usage, {since} to {until}")
    status, data = _call("https://api.cloudflare.com/client/v4/graphql", tok,
                         {"query": query,
                          "variables": {"acct": acct, "since": since,
                                        "until": until}})
    if status != 200 or data.get("errors"):
        print(f"    HTTP {status}; errors: "
              f"{json.dumps(data.get('errors') or data)[:400]}", file=sys.stderr)
        print("    NOTE a permissions error here is a finding, not a zero - the "
              "token needs Account Analytics: Read.", file=sys.stderr)
        return
    accounts = (data.get("data") or {}).get("viewer", {}).get("accounts") or []
    rows = accounts[0].get("aiInferenceAdaptiveGroups", []) if accounts else []
    if not rows:
        print("    no rows returned for that window")
        return
    per_day: dict[str, int] = {}
    per_model: dict[str, int] = {}
    for r in rows:
        d = r["dimensions"]["date"]
        m = r["dimensions"]["modelId"]
        n = int((r.get("sum") or {}).get("totalNeurons") or 0)
        per_day[d] = per_day.get(d, 0) + n
        per_model[m] = per_model.get(m, 0) + n
    print(f"    {'date':12} {'neurons':>10}  (free allocation is 10,000/day)")
    for d in sorted(per_day, reverse=True):
        flag = "  <-- AT OR OVER CAP" if per_day[d] >= 10000 else ""
        print(f"    {d:12} {per_day[d]:>10,}{flag}")
    print(f"\n    {'model':52} {'neurons':>10}")
    for m in sorted(per_model, key=per_model.get, reverse=True):
        print(f"    {m[:52]:52} {per_model[m]:>10,}")


def main() -> int:
    acct, tok = _creds()
    days = 7
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    print(f"account {acct[:6]}...{acct[-4:]}")
    probe_rest(acct, tok)
    print()
    graphql_usage(acct, tok, days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
