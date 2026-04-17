import Link from "next/link";

import { getDocPageData, getDocsTabs } from "@/lib/readme-docs";

export default function DocsShell({ activeSlug = "readme" }) {
  const doc = getDocPageData(activeSlug);
  const tabs = getDocsTabs();
  const lines = doc.content.replace(/\r\n?/g, "\n").replace(/\n$/, "").split("\n");

  return (
    <main className="docs-scene">
      <div className="docs-ambient docs-ambient-one" aria-hidden="true" />
      <div className="docs-ambient docs-ambient-two" aria-hidden="true" />
      <section className="docs-shell">
        <header className="docs-hero">
          <div className="docs-hero-copy">
            <span className="docs-overline">erza docs</span>
            <h1>Canonical markdown, presented as a live code surface.</h1>
            <p>
              The repo stays source-first. The docs site now gives those sources an HTML shell so browser users land on a
              proper page, not a raw file download.
            </p>
          </div>
          <div className="docs-callout">
            <span>{doc.eyebrow}</span>
            <p>{doc.summary}</p>
            <a href={doc.repoHref} target="_blank" rel="noreferrer">
              Open source file
            </a>
          </div>
        </header>

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
                <span className="docs-tab-meta">{tab.eyebrow}</span>
              </Link>
            );
          })}
        </nav>

        <section className="docs-panel" aria-label={`${doc.fileName} source viewer`}>
          <div className="docs-panel-bar">
            <div className="docs-panel-title-group">
              <span className="docs-panel-pill">{doc.fileName}</span>
              <p>{doc.summary}</p>
            </div>
            <a href={doc.repoHref} target="_blank" rel="noreferrer" className="docs-panel-link">
              View in GitHub
            </a>
          </div>

          <div className="docs-code-scroll">
            <pre className="docs-code-block">
              <code>
                {lines.map((line, index) => (
                  <span className="docs-code-line" key={`${doc.slug}-${index + 1}`}>
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
