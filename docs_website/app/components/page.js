import SiteFrame from "@/ui/site-frame";
import { remoteCommandForPage } from "@/lib/erza-pages";
import { componentFamilies } from "@/lib/site-data";

export const metadata = {
  title: "Components",
  description: "Light browser preview of erza components."
};

export default function ComponentsPage() {
  return (
    <SiteFrame footer="back">
      <section className="hero hero-small">
        <p className="eyebrow">components</p>
        <h1>A small component surface, with the full rules in the terminal docs.</h1>
        <p className="lede">
          erza keeps the public vocabulary intentionally small. The browser page only previews the
          current groups. The detailed walkthrough, nesting rules, and usage notes live in the
          terminal docs.
        </p>
      </section>

      <section className="section">
        <div className="section-heading">
          <p className="eyebrow">preview</p>
          <h2>Current component groups</h2>
        </div>
        <div className="family-list">
          {componentFamilies.map((family) => (
            <article className="family-row" key={family.name}>
              <h3>{family.name}</h3>
              <p>{family.summary}</p>
              <p className="family-items">
                {family.items.map((item, index) => (
                  <span key={item}>
                    <code>{item}</code>
                    {index < family.items.length - 1 ? "  " : ""}
                  </span>
                ))}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="section section-first">
        <div className="section-heading">
          <p className="eyebrow">open in terminal</p>
          <h2>The detailed component docs are in erza.</h2>
        </div>
        <div className="terminal-jump">
          <pre className="code-block">
            <code>{remoteCommandForPage("/components")}</code>
          </pre>
          <p className="protocol-link">
            The terminal page covers what each component is for, which ones own layout, and how
            links, actions, and animation should be used.
          </p>
        </div>
      </section>
    </SiteFrame>
  );
}
