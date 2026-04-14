import { readFile } from "node:fs/promises";
import { join } from "node:path";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const REPO_URL = "https://github.com/ryangerardwilson/erza";

export const metadata = {
  title: "Docs",
  description: "Canonical erza documentation rendered directly from the repo README."
};

function resolveMarkdownHref(href = "") {
  if (!href || href.startsWith("#") || href.startsWith("http://") || href.startsWith("https://")) {
    return href;
  }
  const cleaned = href.replace(/^\.\//, "");
  const mode = cleaned.endsWith("/") ? "tree" : "blob";
  return `${REPO_URL}/${mode}/main/${cleaned}`;
}

export default async function HomePage() {
  const readme = await readFile(join(process.cwd(), "..", "README.md"), "utf-8");

  return (
    <main className="readme-shell">
      <div className="readme-meta">
        <span>Canonical docs from README.md</span>
        <a href={`${REPO_URL}/blob/main/README.md`} rel="noreferrer" target="_blank">
          View source
        </a>
      </div>

      <article className="readme-docs">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a({ href, children, ...props }) {
              const resolved = resolveMarkdownHref(href);
              const external = Boolean(resolved) && !String(resolved).startsWith("#");
              return (
                <a
                  {...props}
                  href={resolved}
                  rel={external ? "noreferrer" : undefined}
                  target={external ? "_blank" : undefined}
                >
                  {children}
                </a>
              );
            }
          }}
        >
          {readme}
        </ReactMarkdown>
      </article>
    </main>
  );
}
