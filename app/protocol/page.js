import SiteFrame from "@/ui/site-frame";
import { protocolSteps, protocolWireFormat, safetyPoints } from "@/lib/site-data";

export const metadata = {
  title: "Protocol",
  description: "Remote-mode notes for a future erza transport over HTTPS."
};

export default function ProtocolPage() {
  return (
    <SiteFrame footer="back" narrow>
      <section className="hero hero-small">
        <p className="eyebrow">protocol sketch</p>
        <h1>
          <code>erza example.com</code>
        </h1>
        <p className="lede">
          Assume HTTPS, fetch a terminal-native erza app from a domain, and render the result as a
          terminal session. The transport is the new piece. The authoring model remains{" "}
          <code>.erza</code>, but the wire format should eventually speak in safe component state,
          not browser documents.
        </p>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">flow</p>
          <h2>Minimal request model</h2>
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
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">guardrails</p>
          <h2>Keep the product boundary intact</h2>
        </div>
        <div className="card-grid">
          {safetyPoints.map((point) => (
            <article className="card" key={point}>
              <p>{point}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section section-accent">
        <div className="section-heading">
          <p className="eyebrow">rough shape</p>
          <h2>Potential wire-format outline</h2>
        </div>
        <pre className="code-block">
          <code>{protocolWireFormat}</code>
        </pre>
      </section>
    </SiteFrame>
  );
}
