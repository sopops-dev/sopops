import assert from "node:assert/strict";
import { test } from "node:test";
import { notFoundResponse } from "./not-found.js";

const request = (accept, method = "GET") => new Request("https://sopops.dev/guessed", {
  method, headers: accept === undefined ? {} : { Accept: accept },
});
const missing = () => new Response("<h1>Missing</h1>", {
  status: 404, headers: { "Content-Type": "text/html", "Content-Length": "16", ETag: "old", Vary: "Origin" },
});

test("unknown URLs return actionable JSON for agents and default clients", async () => {
  for (const accept of [undefined, "*/*", "application/json", "text/markdown", "text/html;q=0", "text/html;q=.1,application/json;q=1"]) {
    const response = notFoundResponse(request(accept), missing());
    assert.equal(response.status, 404);
    assert.match(response.headers.get("Content-Type"), /application\/json/);
    assert.equal(response.headers.get("Vary"), "Origin, Accept");
    assert.equal(response.headers.get("Cache-Control"), "no-store");
    assert.equal(response.headers.get("ETag"), null);
    assert.equal(response.headers.get("Content-Length"), null);
    const body = await response.json();
    assert.equal(body.error, "not_found");
    assert.ok(body.how_to_fix);
    assert.equal(body.docs_url, "https://sopops.dev/docs/");
    assert.equal(body.index_url, "https://sopops.dev/llms.txt");
  }
});

test("explicit HTML preferences preserve the browser error page", async () => {
  for (const accept of ["text/html", "text/html,application/xhtml+xml,*/*;q=.8", "text/html;q=1,application/json;q=.5"]) {
    const response = notFoundResponse(request(accept), missing());
    assert.equal(response.status, 404);
    assert.equal(await response.text(), "<h1>Missing</h1>");
    assert.equal(response.headers.get("Vary"), "Origin, Accept");
  }
});

test("successful assets, redirects and other errors pass through unchanged", () => {
  for (const status of [200, 301, 403, 405, 500]) {
    const original = new Response("unchanged", { status });
    assert.equal(notFoundResponse(request("application/json"), original), original);
  }
});

test("HEAD sends no JSON body and docs responses link to their own index", async () => {
  const response = notFoundResponse(request("*/*", "HEAD"), missing(), "https://sopops.dev/docs/llms.txt");
  assert.equal(response.status, 404);
  assert.equal(await response.text(), "");
  const get = notFoundResponse(request("*/*"), missing(), "https://sopops.dev/docs/llms.txt");
  assert.equal((await get.json()).index_url, "https://sopops.dev/docs/llms.txt");
});
