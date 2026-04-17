import Link from "next/link";

import { getDocPageData, getDocsTabs } from "@/lib/readme-docs";

export default function DocsShell({ activeSlug = "readme" }) {
  const { content } = getDocPageData(activeSlug);
  const tabs = getDocsTabs();
  const lines = content.replace(/\r\n?/g, "\n").replace(/\n$/, "").split("\n");

  return (
    <main className="docs-scene">
      <div className="docs-ambient docs-ambient-one" aria-hidden="true" />
      <div className="docs-ambient docs-ambient-two" aria-hidden="true" />
      <section className="docs-shell">
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

        <section className="docs-panel" aria-label="source viewer">
          <div className="docs-code-scroll">
            <pre className="docs-code-block">
              <code>
                {lines.map((line, index) => (
                  <span className="docs-code-line" key={`${activeSlug}-${index + 1}`}>
                    <span className="docs-code-number">{String(index + 1).padStart(3, "0")}</span>
                    <span className="docs-code-text">{line || " "}</span>
                  </span>
                ))}
              </code>
            </pre>
          </div>
        </section>
      </section>
    </main>
  );
}
