import SiteFrame from "@/ui/site-frame";
import { remoteCommandForPage } from "@/lib/erza-pages";
import { animationFrames, capabilityMatrix, labTracks } from "@/lib/site-data";

export const metadata = {
  title: "Labs",
  description: "Capability lab for the current erza runtime, docs output, and remote viewer."
};

export default function LabsPage() {
  return (
    <SiteFrame footer="back">
      <section className="hero hero-small">
        <p className="eyebrow">labs</p>
        <h1>Use the hosted site as a capability checklist.</h1>
        <p className="lede">
          This page is where the browser build, the local runtime, the remote HTML viewer, and the
          future erzanet transport stop pretending to be the same thing. Each row below is a prompt
          for what to add next.
        </p>
        <p className="terminal-twin">
          In erza: <code>{remoteCommandForPage("/labs")}</code>
        </p>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">matrix</p>
          <h2>What works where</h2>
        </div>
        <div className="matrix-grid">
          {capabilityMatrix.map((item) => (
            <article className="card" key={item.feature}>
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
      </section>

      <section className="section section-accent">
        <div className="section-heading">
          <p className="eyebrow">animation</p>
          <h2>Poster fallback for AsciiAnimation</h2>
        </div>
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
        <p className="protocol-link">
          Run <code>python app/main.py run app/examples/animation</code> locally for the live runtime
          version.
        </p>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">next steps</p>
          <h2>Pressure points worth chasing next</h2>
        </div>
        <div className="card-grid">
          {labTracks.map((item) => (
            <article className="step-card" key={item.title}>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </section>
    </SiteFrame>
  );
}
