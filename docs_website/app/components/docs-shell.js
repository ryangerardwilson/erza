import Link from "next/link";

import { getDocPageData, getDocsTabs } from "@/lib/readme-docs";

const REPO_URL = "https://github.com/ryangerardwilson/erza";
const REPO_LABEL = "github.com/ryangerardwilson/erza";

export default function DocsShell({ activeSlug = "readme" }) {
  const { content, fileName } = getDocPageData(activeSlug);
  const tabs = getDocsTabs();
  const normalizedContent = content.replace(/\r\n?/g, "\n").replace(/\n$/, "");

  return (
    <main className="docs-scene">
      <section className="docs-shell">
        <header className="docs-topbar">
          <nav className="docs-tabs" aria-label="Documentation files">
            {tabs.map((tab) => {
              const isActive = tab.slug === activeSlug;
              return (
                <Link
                  key={tab.slug}
                  href={tab.href}
                  className={isActive ? "docs-tab docs-tab-active" : "docs-tab"}
                  aria-current={isActive ? "page" : undefined}
                >
                  <span className="docs-tab-label">{tab.label}</span>
                </Link>
              );
            })}
          </nav>

          <a
            className="docs-repo-link"
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            aria-label="Open the erza GitHub repository"
          >
            {REPO_LABEL}
          </a>
        </header>

        <section className="docs-panel" aria-label={`${fileName} source`}>
          <h1 className="sr-only">{fileName}</h1>
          <div className="docs-code-scroll">
            <pre className="docs-code-block">
              <code>{normalizedContent}</code>
            </pre>
          </div>
        </section>
      </section>
    </main>
  );
}
