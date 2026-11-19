// Browsers that explicitly prefer HTML keep the rendered error page.
// Other clients receive a small JSON document with a concrete discovery URL.
export function notFoundResponse(request, response, indexUrl = "https://sopops.dev/llms.txt") {
  if (response.status !== 404) return response;
  const accepts = new Map((request.headers.get("accept") ?? "").split(",").map((part) => {
    const [type, ...params] = part.trim().toLowerCase().split(";");
    const quality = params.find((p) => p.trim().startsWith("q="));
    const q = quality ? Number(quality.trim().slice(2)) : 1;
    return [type.trim(), Number.isFinite(q) && q >= 0 && q <= 1 ? q : 0];
  }));
  const html = accepts.get("text/html") ?? 0;
  const json = accepts.get("application/json") ?? 0;
  const headers = new Headers(response.headers);
  if (headers.get("vary") !== "*") {
    const vary = (headers.get("vary") ?? "").split(",").map((v) => v.trim()).filter(Boolean);
    if (!vary.some((v) => v.toLowerCase() === "accept")) vary.push("Accept");
    headers.set("Vary", vary.join(", "));
  }
  if (html > 0 && html >= json) return new Response(response.body, { status: 404, headers });

  // The asset body's metadata (length, encoding, ETag) does not describe this JSON.
  const body = JSON.stringify({
    error: "not_found",
    how_to_fix: "Read the content index and use a listed URL instead of guessing a path.",
    docs_url: "https://sopops.dev/docs/",
    index_url: indexUrl,
  });
  return new Response(request.method === "HEAD" ? null : body, {
    status: 404,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "Vary": headers.get("Vary"),
      "X-Content-Type-Options": "nosniff",
    },
  });
}
