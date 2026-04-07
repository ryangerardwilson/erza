import SiteFrame from "@/ui/site-frame";
import { remoteCommandForPage } from "@/lib/erza-pages";
import { animationFrames, animationMarkup, componentFamilies, nestingRules } from "@/lib/site-data";

export const metadata = {
  title: "Components",
  description: "Component gallery and nesting rules for erza."
};

export default function ComponentsPage() {
  return (
    <SiteFrame footer="back">
      <section className="hero hero-small">
        <p className="eyebrow">component gallery</p>
        <h1>A small component set with hard boundaries.</h1>
        <p className="lede">
          The goal is not widget sprawl. It is a compact set of primitives with clear nesting
          rules, reliable motion, and enough structure to make remote terminal documents feel
          deliberate.
        </p>
        <p className="terminal-twin">
          In erza: <code>{remoteCommandForPage("/components")}</code>
        </p>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">families</p>
          <h2>Current component groups</h2>
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
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">nesting</p>
          <h2>Rules worth enforcing in the language</h2>
        </div>
        <div className="card-grid">
          {nestingRules.map((rule) => (
            <article className="card" key={rule.parent}>
              <h3>
                <code>{rule.parent}</code>
              </h3>
              <p>
                <strong>Allows:</strong> {rule.allows}
              </p>
              <p>{rule.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section section-accent">
        <div className="section-heading">
          <p className="eyebrow">motion</p>
          <h2>The new AsciiAnimation component</h2>
        </div>
        <div className="page-grid">
          <div>
            <p>
              The runtime component is declarative: a label, an FPS value, and a sequence of raw
              ASCII frames. The docs site cannot play it natively, so this page shows the poster
              and the source shape instead.
            </p>
            <pre className="code-block">
              <code>{animationMarkup}</code>
            </pre>
          </div>
          <div>
            <div className="ascii-gallery">
              {animationFrames.map((frame) => (
                <article className="ascii-frame-card" key={frame.title}>
                  <p className="command-label">{frame.title}</p>
                  <pre className="ascii-stage">
                    <code>{frame.art}</code>
                  </pre>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>
    </SiteFrame>
  );
}
