import Link from "next/link";

import { nav, site } from "@/lib/site-data";

export default function SiteFrame({ children, narrow = false, footer = "home" }) {
  return (
    <div className={narrow ? "shell shell-narrow" : "shell"}>
      <header className="topbar">
        <Link className="brand" href="/">
          erza
        </Link>
        <nav className="nav">
          {nav.map((item) =>
            item.external ? (
              <a key={item.href} href={item.href} rel="noreferrer" target="_blank">
                {item.label}
              </a>
            ) : (
              <Link key={item.href} href={item.href}>
                {item.label}
              </Link>
            )
          )}
        </nav>
      </header>

      <main>{children}</main>

      <footer className="footer">
        {footer === "home" ? (
          <>
            <div>
              <p>
                Docs URL: <a href={site.url}>{site.domain}</a>
              </p>
              <p>
                Source: <a href={site.repoUrl}>{site.repoUrl}</a>
              </p>
            </div>
            <p>Built {site.buildStamp}</p>
          </>
        ) : (
          <>
            <p>
              <Link href="/">Back to overview</Link>
            </p>
            <p>Built {site.buildStamp}</p>
          </>
        )}
      </footer>
    </div>
  );
}
