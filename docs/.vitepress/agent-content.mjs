import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, posix } from "node:path";

const SITE = "https://sopops.dev";
const REPO = "https://github.com/sopops-dev/sopops";

export const pageRoute = (page) => page.replace(/(^|\/)index\.md$/, "$1").replace(/\.md$/, "");

// Resolve prose links against the source page, including repo files outside docs.
// Fenced examples remain byte-for-byte intact.
export function markdownLinks(source, page, base) {
  let fence;
  return source.split("\n").map((line) => {
    const marker = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (marker) {
      if (!fence) fence = marker[1];
      else if (marker[1][0] === fence[0] && marker[1].length >= fence.length) fence = undefined;
      return line;
    }
    if (fence) return line;
    return line.replace(/(\]\()([^\s)]+)([^)]*\))/g, (_all, before, href, after) => {
      if (/^(?:[a-z][\w+.-]*:|#|\/\/)/i.test(href)) return `${before}${href}${after}`;
      const split = href.search(/[?#]/);
      const path = split < 0 ? href : href.slice(0, split);
      const suffix = split < 0 ? "" : href.slice(split);
      const target = path.startsWith("/")
        ? `docs/${path.slice(1)}`
        : posix.normalize(posix.join("docs", posix.dirname(page), path));
      const url = target === "API.md" ? `${SITE}${base}api/index.md`
        : target.startsWith("docs/") ? `${SITE}${base}${target.slice(5)}`
        : `${REPO}/blob/main/${target}`;
      return `${before}${url}${suffix}${after}`;
    });
  }).join("\n");
}

export async function exportAgentContent(config, base) {
  const pages = config.pages.filter((page) => page.endsWith(".md") && page !== "404.md").sort();
  const documents = [];
  for (const page of pages) {
    const raw = await readFile(join(config.srcDir, page), "utf8");
    const body = raw.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, "").trim();
    const title = body.match(/^#\s+(.+)$/m)?.[1] ?? "sopops docs";
    const canonical = `${SITE}${base}${pageRoute(page)}`;
    const markdown = `${/^#\s/m.test(body) ? "" : `# ${title}\n\n`}Source: ${canonical}\n\n${markdownLinks(body, page, base)}\n`;
    const dest = join(config.outDir, page);
    await mkdir(dirname(dest), { recursive: true });
    await writeFile(dest, markdown);
    documents.push({ title, page, markdown });
  }
  const index = `# sopops documentation

> Set up sopops, connect voice agents, and check calls against their procedures.

These Markdown files are generated from the same sources as the HTML documentation. Code blocks include both Python and TypeScript examples. No JavaScript or authentication is needed to read them.

## Start here

- [Run the local demo](${SITE}${base}first-agent.md)
- [Self-hosting quickstart](${SITE}${base}quickstart.md)
- [Connect your agent](${SITE}${base}connect.md)
- [SDK reference](${SITE}${base}sdk.md)
- [API reference](${SITE}${base}api/index.md)
- [All documentation in one file](${SITE}${base}llms-full.txt)

## All pages

${documents.map(({ title, page }) => `- [${title}](${SITE}${base}${page})`).join("\n")}

## Other content

- [Product and blog index](${SITE}/llms.txt)
- [Source code](${REPO})
`;
  await writeFile(join(config.outDir, "llms.txt"), index);
  await writeFile(join(config.outDir, "llms-full.txt"), [index, ...documents.map((d) => d.markdown)].join("\n\n---\n\n"));
}
