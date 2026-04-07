import SiteFrame from "@/ui/site-frame";
import { remoteCommandForPage } from "@/lib/erza-pages";
import { labTracks, patterns } from "@/lib/site-data";

export const metadata = {
  title: "Patterns",
  description: "Pattern library for terminal-native erza layouts."
};

export default function PatternsPage() {
  return (
    <SiteFrame footer="back">
      <section className="hero hero-small">
        <p className="eyebrow">pattern library</p>
        <h1>Reference surfaces the runtime should handle cleanly.</h1>
        <p className="lede">
          These are not all first-class components yet. They are durable screen shapes to
          pressure-test layout, density, hierarchy, and navigation.
        </p>
        <p className="terminal-twin">
          In erza: <code>{remoteCommandForPage("/patterns")}</code>
        </p>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">patterns</p>
          <h2>Six shapes worth building against</h2>
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
      </section>

      <section className="section section-accent">
        <div className="section-heading">
          <p className="eyebrow">checks</p>
          <h2>Questions each pattern should answer</h2>
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
