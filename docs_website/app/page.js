import SiteFrame from "@/ui/site-frame";
import TypewriterHero from "@/ui/typewriter-hero";
import {
  installCommand,
  landingMarkup,
  landingVideo,
  starterScript,
  storyPhrases,
  terminalDocsCommand,
  terminalDocsSequence,
  whyUseCases
} from "@/lib/site-data";

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
          <code>erza</code> is for docs, tools, and product surfaces that should open in the
          terminal instead of inside another browser tab.
        </p>
      </section>

      <section className="section section-first">
        <div className="page-grid home-grid">
          <div>
            <div className="section-heading section-heading-compact">
              <p className="eyebrow">why erza</p>
              <h2>Use erza when the browser is the wrong container.</h2>
            </div>
            <div className="statement-list">
              {whyUseCases.map((item) => (
                <p key={item}>{item}</p>
              ))}
            </div>
          </div>

          <div>
            <div className="section-heading section-heading-compact">
              <p className="eyebrow">start in terminal</p>
              <h2>Install it, then open the real docs in erza.</h2>
            </div>
            <div className="terminal-jump">
              <pre className="code-block">
                <code>{starterScript}</code>
              </pre>
              <p className="protocol-link">
                In the terminal, start with{" "}
                {terminalDocsSequence.map((item, index) => (
                  <span key={item}>
                    <code>{item}</code>
                    {index < terminalDocsSequence.length - 1 ? ", " : "."}
                  </span>
                ))}
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section home-proof">
        <div className="page-grid demo-grid">
          <div className="demo-column">
            <div className="section-heading section-heading-compact">
              <p className="eyebrow">input</p>
              <h2>
                A landing page in <code>.erza</code>
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
              <h2>The terminal stays the primary surface.</h2>
            </div>
            <div className="terminal-window video-placeholder">
              <div className="terminal-window-bar">
                <span>captured hero demo</span>
                <span>app/examples/landing</span>
              </div>
              <video className="hero-video" autoPlay controls loop muted playsInline src={landingVideo} />
            </div>
            <p className="protocol-link">The detailed documentation lives in the terminal version of this site.</p>
          </div>
        </div>
      </section>

      <section className="section" id="full-docs">
        <div className="section-heading">
          <p className="eyebrow">full docs</p>
          <h2>Read the full docs in erza, not in the browser.</h2>
        </div>
        <div className="terminal-jump">
          <p className="protocol-link">
            Install the CLI first, then open the full docs in the terminal.
          </p>
          <pre className="code-block">
            <code>{installCommand}</code>
          </pre>
          <pre className="code-block">
            <code>{terminalDocsCommand}</code>
          </pre>
          <p className="protocol-link">
            The browser site is the quick pitch. The terminal site carries the full getting-started
            path, component rules, backend notes, remote model, examples, and reference material.
          </p>
        </div>
      </section>
    </SiteFrame>
  );
}
