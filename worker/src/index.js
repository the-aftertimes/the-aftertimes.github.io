/* Charlie's verdicts on each edition, one tap from the page.

     POST /v   {date, verdict: "good" | "bad", reason?}   store one verdict
     GET  /v                                              every verdict, for the daily job

   Both need `Authorization: Bearer <VOTE_KEY>`. The page only shows its buttons
   in a browser that holds the key, so a reader never sees them, and a verdict is
   only ever Charlie's.

   Why this exists (07/10/2026): the paper has had a learning loop since August -
   verdict.py records good/bad, a good verdict promotes the premise into the
   few-shot pool that steers every later edition - and in 72 editions it had
   received zero verdicts, because recording one meant running a script. The
   signal it waits for is Charlie's taste, which nothing automated can stand in
   for: the model judge and the comedy panel score almost every draft 7 or 8.
   So the fix is the cost of the signal, not the loop.

   KV, one key per edition date. A second tap on the same day overwrites the
   first, which is the behaviour wanted: a change of mind. */

const ORIGIN = "https://aftertimes.charlietrenorden.com";
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const VERDICTS = ["good", "bad"];
// Kept short and fixed so the daily job can tally them. Free text would be
// richer and would not be tapped.
const REASONS = ["", "not funny", "doesn't make sense", "too weird", "picture"];

function cors(extra = {}) {
  return {
    "Access-Control-Allow-Origin": ORIGIN,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "86400",
    ...extra,
  };
}

function reply(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: cors({ "Content-Type": "application/json" }),
  });
}

function authorised(request, env) {
  const got = request.headers.get("Authorization") || "";
  return Boolean(env.VOTE_KEY) && got === `Bearer ${env.VOTE_KEY}`;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { headers: cors() });
    if (url.pathname !== "/v") return reply(404, { error: "not found" });
    if (!authorised(request, env)) return reply(401, { error: "unauthorised" });

    if (request.method === "GET") {
      const out = {};
      let cursor;
      do {
        const page = await env.VERDICTS.list({ cursor });
        for (const k of page.keys) out[k.name] = JSON.parse(await env.VERDICTS.get(k.name));
        cursor = page.list_complete ? undefined : page.cursor;
      } while (cursor);
      return reply(200, out);
    }

    if (request.method === "POST") {
      let body;
      try { body = await request.json(); } catch { return reply(400, { error: "bad json" }); }
      const { date, verdict } = body || {};
      const reason = (body && body.reason) || "";
      if (!DATE.test(date || "")) return reply(400, { error: "bad date" });
      if (!VERDICTS.includes(verdict)) return reply(400, { error: "bad verdict" });
      if (!REASONS.includes(reason)) return reply(400, { error: "bad reason" });
      const row = { verdict, reason, at: new Date().toISOString() };
      await env.VERDICTS.put(date, JSON.stringify(row));
      return reply(200, { date, ...row });
    }

    return reply(405, { error: "method not allowed" });
  },
};
