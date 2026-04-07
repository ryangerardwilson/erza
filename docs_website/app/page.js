import SiteFrame from "@/ui/site-frame";
import TypewriterHero from "@/ui/typewriter-hero";
import { erzaDocsPages } from "@/lib/erza-pages";
import { landingMarkup, landingVideo, storyPhrases } from "@/lib/site-data";

export default function HomePage() {
  return (
    <SiteFrame footer="home">
      <section className="hero hero-home">
        <div className="hero-poster">
          <div className="brand-lockup" aria-label="ERZA">
            <div className="brand-mark" aria-hidden="true">
              <span className="terminal-prompt">&gt;</span>
              <span className="terminal-cursor" />
            </div>
            <h1 className="brand-word">ERZA</h1>
          </div>
          <TypewriterHero phrases={storyPhrases} />
        </div>
        <p className="lede story-lede">
          <code>erza</code> is the wager that websites, product surfaces, and documentation can be
          designed CLI and TUI first, then opened over HTTPS without leaving the terminal.
        </p>
      </section>

      <section className="section section-first home-proof">
        <div className="page-grid demo-grid">
          <div className="demo-column">
            <div className="section-heading section-heading-compact">
              <p className="eyebrow">input</p>
              <h2>
                Landing page in <code>.erza</code>
              </h2>
            </div>
            <div className="hero-code">
              <pre className="code-block">
                <code>{landingMarkup}</code>
              </pre>
            </div>
          </div>

          <div className="demo-column">
            <div className="section-heading section-heading-compact">
              <p className="eyebrow">output</p>
              <h2>Latest terminal capture</h2>
            </div>
            <div className="terminal-window video-placeholder">
              <div className="terminal-window-bar">
                <span>captured hero demo</span>
                <span>app/examples/landing</span>
              </div>
              <video className="hero-video" autoPlay controls loop muted playsInline src={landingVideo} />
            </div>
            <p className="protocol-link">
              The current demo uses the latest local recording of the centered 79-column runtime.
            </p>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">same host</p>
          <h2>The browser docs and the erza site ship together.</h2>
        </div>
        <div className="page-directory">
          {erzaDocsPages.map((page) => (
            <article className="page-row" key={page.href}>
              <div className="page-row-copy">
                <h3>{page.label}</h3>
                <p>{page.summary}</p>
                <p className="page-row-links">
                  <a href={page.href}>Open in browser</a>
                  <span>Source: <code>{page.localPath}</code></span>
                </p>
              </div>
              <pre className="page-row-command">
                <code>{page.remoteCommand}</code>
              </pre>
            </article>
          ))}
        </div>
      </section>
    </SiteFrame>
  );
}
