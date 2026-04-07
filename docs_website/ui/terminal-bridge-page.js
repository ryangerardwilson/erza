import SiteFrame from "@/ui/site-frame";

export default function TerminalBridgePage({ eyebrow, title, description, command, points = [] }) {
  return (
    <SiteFrame footer="back" narrow>
      <section className="hero hero-small">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="lede">{description}</p>
      </section>

      <section className="section section-first">
        <div className="section-heading">
          <p className="eyebrow">open in terminal</p>
          <h2>The detailed version of this page lives in erza.</h2>
        </div>
        <div className="terminal-jump">
          <pre className="code-block">
            <code>{command}</code>
          </pre>
          <p className="protocol-link">
            The browser site is only the on-ramp. The terminal page carries the full documentation.
          </p>
        </div>
      </section>

      {points.length ? (
        <section className="section">
          <div className="section-heading">
            <p className="eyebrow">covers</p>
            <h2>What you will find there</h2>
          </div>
          <div className="statement-list">
            {points.map((point) => (
              <p key={point}>{point}</p>
            ))}
          </div>
        </section>
      ) : null}
    </SiteFrame>
  );
}
