// Cloudflare Pages Function: does the same job as serve.py's /proxy route.
// A file at functions/proxy.js is served at /proxy automatically.
const UA = "Mozilla/5.0 (compatible; CadenceHosted/1.0; +podcast cadence analysis)";

const headers = (extra = {}) => ({
  "Access-Control-Allow-Origin": "*",
  "Cache-Control": "no-store",
  ...extra,
});
const fail = (code, msg) =>
  new Response(msg, { status: code, headers: headers({ "Content-Type": "text/plain; charset=utf-8" }) });

export async function onRequestGet({ request }) {
  const target = new URL(request.url).searchParams.get("url");
  if (!target) return fail(400, "No url parameter given.");

  let parsed;
  try { parsed = new URL(target); } catch { return fail(400, "Not a valid URL."); }
  if (!["http:", "https:"].includes(parsed.protocol))
    return fail(400, `Only http and https are proxied, not '${parsed.protocol.replace(":", "")}'.`);

  let r;
  try {
    r = await fetch(parsed.toString(), {
      redirect: "follow",
      headers: { "User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*" },
    });
  } catch (e) {
    return fail(502, `Could not reach the feed host: ${e.message}.`);
  }
  if (!r.ok) return fail(502, `The feed host returned HTTP ${r.status} ${r.statusText}.`);

  // Stream the feed straight through, so even very large feeds work.
  return new Response(r.body, {
    status: 200,
    headers: headers({ "Content-Type": r.headers.get("Content-Type") || "application/xml" }),
  });
}
