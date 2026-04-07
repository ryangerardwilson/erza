import SiteFrame from "@/ui/site-frame";
import TypewriterHero from "@/ui/typewriter-hero";
import {
  capabilityMatrix,
  commands,
  componentFamilies,
  examples,
  landingMarkup,
  landingVideo,
  patterns,
  pillars,
  protocolSteps,
  storyPhrases
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
          <p className="eyebrow">thesis</p>
          <h2>Why this site exists</h2>
        </div>
        <div className="card-grid">
          {pillars.map((pillar) => (
            <article className="card" key={pillar.title}>
              <h3>{pillar.title}</h3>
              <p>{pillar.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">component map</p>
          <h2>What exists today</h2>
        </div>
        <div className="card-grid">
          {componentFamilies.map((family) => (
            <article className="card" key={family.name}>
              <h3>{family.name}</h3>
              <p>{family.summary}</p>
              <ul className="bullet-list">
                {family.items.map((item) => (
                  <li key={item}>
                    <code>{item}</code>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
        <p className="protocol-link">
          <a href="/components">Open the component gallery</a>
        </p>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">patterns</p>
          <h2>Reference surfaces</h2>
        </div>
        <div className="card-grid">
          {patterns.map((pattern) => (
            <article className="card" key={pattern.name}>
              <h3>{pattern.name}</h3>
              <p>{pattern.summary}</p>
              <p>
                <strong>Regions:</strong> {pattern.regions}
              </p>
            </article>
          ))}
        </div>
        <p className="protocol-link">
          <a href="/patterns">Open the pattern library</a>
        </p>
      </section>

      <section className="section section-accent">
        <div className="section-heading">
          <p className="eyebrow">labs</p>
          <h2>What works where</h2>
        </div>
        <div className="matrix-grid">
          {capabilityMatrix.map((item) => (
            <article className="step-card" key={item.feature}>
              <h3>{item.feature}</h3>
              <p>
                <strong>Runtime:</strong> {item.runtime}
              </p>
              <p>
                <strong>Docs HTML:</strong> {item.docs}
              </p>
              <p>
                <strong>Remote Viewer:</strong> {item.remote}
              </p>
              <p>
                <strong>Erzanet:</strong> {item.erzanet}
              </p>
            </article>
          ))}
        </div>
        <p className="protocol-link">
          <a href="/labs">Open the labs page</a>
        </p>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">examples</p>
          <h2>Runnable local surfaces</h2>
        </div>
        <div className="card-grid">
          {examples.map((example) => (
            <article className="card" key={example.name}>
              <h3>{example.name}</h3>
              <p>{example.summary}</p>
              <p>
                <code>{example.path}</code>
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">commands</p>
          <h2>Open the current surfaces</h2>
        </div>
        <div className="command-list command-list-tight">
          {commands.map((command) => (
            <div className="command-card" key={command.label}>
              <p className="command-label">{command.label}</p>
              <pre>
                <code>{command.command}</code>
              </pre>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">next hop</p>
          <h2>Remote mode over HTTPS</h2>
        </div>
        <div className="flow-grid">
          {protocolSteps.map((item) => (
            <article className="step-card" key={item.step}>
              <p className="step-number">{item.step}</p>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
        <p className="protocol-link">
          <a href="/protocol">Read the remote-mode notes</a>
        </p>
      </section>
    </SiteFrame>
  );
}
