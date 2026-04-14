import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { readCanonicalReadme, resolveReadmeHref } from "@/lib/readme-docs";

const REPO_URL = "https://github.com/ryangerardwilson/erza";

export const metadata = {
  title: "Docs",
  description: "Canonical erza documentation rendered directly from the repo README."
};

export default function HomePage() {
  const readme = readCanonicalReadme();

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
              const resolved = resolveReadmeHref(href);
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
