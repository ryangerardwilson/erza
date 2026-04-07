import SiteFrame from "@/ui/site-frame";

export default function NotFound() {
  return (
    <SiteFrame footer="back">
      <section className="hero hero-small">
        <p className="eyebrow">404</p>
        <h1>That route is not part of the current erza docs surface.</h1>
        <p className="lede">
          Head back to the overview and continue from the current component, pattern, lab, or
          protocol pages.
        </p>
      </section>
    </SiteFrame>
  );
}
