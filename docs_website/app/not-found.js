export default function NotFound() {
  return (
    <main className="readme-shell">
      <div className="readme-meta">
        <span>Canonical docs from README.md</span>
      </div>
      <article className="readme-docs">
        <h1>That docs route does not exist.</h1>
        <p>The documentation site is a single README-driven surface now.</p>
        <p>
          Go back to <a href="/">the root docs page</a>.
        </p>
      </article>
    </main>
  );
}
