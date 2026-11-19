# Documentation builds

Run `pnpm build` for the site root, or `pnpm build:cloudflare` for the production
`/docs/` prefix. The latter puts output in `.vitepress/dist/docs/`.

Every build generates a Markdown copy of every published documentation page at
its source path (for example, `/docs/sdk.md` and `/docs/api/index.md`), an index
at `/docs/llms.txt`, and the complete documentation at `/docs/llms-full.txt`.
Exports resolve prose links to absolute URLs and preserve fenced code examples.
HTML pages link to their Markdown copy, and the generated sitemap lists HTML pages.
The source README is excluded from the published pages and exports.

Edit the original Markdown pages to update both representations. The export hook
is `.vitepress/agent-content.mjs`. Run its focused checks with:

```sh
node --test .vitepress/agent-content.test.mjs
```

The Worker in `edge/worker.js` serves the built assets and gives unknown URLs
JSON recovery instructions unless the request explicitly prefers HTML. The
status remains 404, and errors vary by `Accept`. Check this behavior with
`node --test edge/not-found.test.mjs`.
