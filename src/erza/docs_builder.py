from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import shutil

from erza.template import render_template


DEFAULT_DOMAIN = "erza.ryangerardwilson.com"
DEFAULT_REPO_URL = "https://github.com/ryangerardwilson/erza"


def build_docs(
    source_dir: Path,
    output_dir: Path,
    *,
    domain: str = DEFAULT_DOMAIN,
    repo_url: str = DEFAULT_REPO_URL,
) -> list[Path]:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    context = _build_context(domain=domain, repo_url=repo_url)
    written: list[Path] = []

    for path in sorted(source_dir.rglob("*")):
        if path.is_dir():
            continue

        relative = path.relative_to(source_dir)
        if path.suffix == ".erza":
            target = output_dir / relative.with_suffix(".html")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                render_template(path.read_text(encoding="utf-8"), context=context),
                encoding="utf-8",
            )
            written.append(target)
            continue

        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        written.append(target)

    cname = output_dir / "CNAME"
    cname.write_text(f"{domain}\n", encoding="utf-8")
    written.append(cname)

    nojekyll = output_dir / ".nojekyll"
    nojekyll.write_text("\n", encoding="utf-8")
    written.append(nojekyll)

    return written


def _build_context(*, domain: str, repo_url: str) -> dict[str, object]:
    return {
        "site": {
            "domain": domain,
            "url": f"https://{domain}",
            "repo_url": repo_url,
            "build_stamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        },
        "nav": [
            {"href": "#model", "label": "Model"},
            {"href": "#components", "label": "Components"},
            {"href": "#run", "label": "Run"},
            {"href": "#examples", "label": "Examples"},
            {"href": "/protocol/", "label": "Protocol"},
            {"href": repo_url, "label": "GitHub"},
        ],
        "commands": [
            {"label": "Local example", "command": "python -m erza run examples/greetings"},
            {"label": "Remote docs", "command": "python -m erza run erza.ryangerardwilson.com"},
            {"label": "Docs build", "command": "./update_docs.sh"},
        ],
        "pillars": [
            {
                "title": "Section is the primary unit",
                "body": "A screen should read as a stack of named regions, each with one job and a small number of active items.",
            },
            {
                "title": "Navigation starts with regions",
                "body": "Ctrl+N and Ctrl+P move between sections, gg and G jump to the ends, then j and k move inside the currently active section while h and l handle back and open.",
            },
            {
                "title": "Remote transport stays separate",
                "body": "The future networked model should fetch terminal-native app state over HTTPS without inheriting browser compatibility scope.",
            },
        ],
        "components": [
            {
                "tag": "<Screen>",
                "summary": "Root shell for one terminal page.",
            },
            {
                "tag": "<Section title=\"...\">",
                "summary": "Primary navigable region and the main unit of composition.",
            },
            {
                "tag": "<Text>",
                "summary": "Plain copy, status, or values inside a section.",
            },
            {
                "tag": "<Action on:press=\"...\">",
                "summary": "A backend-triggering affordance selected with j/k and fired with l.",
            },
            {
                "tag": "<Link href=\"...\">",
                "summary": "A local or remote page hop that opens with l.",
            },
        ],
        "examples": [
            {
                "name": "Tasks",
                "path": "examples/tasks/app.erza",
                "summary": "A section-first task board with backend actions, links, and page history.",
            },
            {
                "name": "Greetings",
                "path": "examples/greetings/index.erza",
                "summary": "A directory-based entrypoint that shows how sections become the default screen rhythm.",
            },
        ],
        "protocol_steps": [
            {
                "step": "1",
                "title": "Resolve a domain",
                "body": "`erza example.com` assumes HTTPS and asks the server for an erza app, not a browser document.",
            },
            {
                "step": "2",
                "title": "Fetch a screen tree",
                "body": "The server returns a safe section-first screen tree the client can render locally.",
            },
            {
                "step": "3",
                "title": "Send actions back",
                "body": "Links and actions post structured events back to the server while client-side history stays local.",
            },
            {
                "step": "4",
                "title": "Rerender in place",
                "body": "The client receives the next screen or a diff and updates the local terminal session.",
            },
        ],
        "safety_points": [
            "Do not ship arbitrary backend code to the client.",
            "Keep the wire format declarative and terminal-native.",
            "Preserve normal backend integration over HTTPS.",
            "Avoid inheriting browser compatibility scope by accident.",
        ],
    }
