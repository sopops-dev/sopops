import assert from "node:assert/strict";
import { test } from "node:test";
import { markdownLinks, pageRoute } from "./agent-content.mjs";

test("canonical routes preserve nested indexes", () => {
  assert.equal(pageRoute("index.md"), "");
  assert.equal(pageRoute("api/index.md"), "api/");
  assert.equal(pageRoute("api/sessions.md"), "api/sessions");
});

test("standalone exports resolve docs, repo, asset and API links under either base", () => {
  for (const base of ["/", "/docs/"]) {
    const source = "[SDK](../sdk.md#errors) [API](../../API.md) ![UI](../images/overview.png) [Code](../../sdks/python) [Local](#local)";
    assert.equal(markdownLinks(source, "api/sessions.md", base),
      `[SDK](https://sopops.dev${base}sdk.md#errors) [API](https://sopops.dev${base}api/index.md) ![UI](https://sopops.dev${base}images/overview.png) [Code](https://github.com/sopops-dev/sopops/blob/main/sdks/python) [Local](#local)`);
  }
});

test("export leaves fenced commands and external links intact", () => {
  const source = "[External](https://example.com/)\n```python\nprint('[link](relative.md)')\n```\n~~~sh\necho '[link](relative.md)'\n~~~";
  assert.equal(markdownLinks(source, "sdk.md", "/docs/"), source);
});
