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
            {"href": "#why", "label": "Why"},
            {"href": "#run", "label": "Run"},
            {"href": "#examples", "label": "Examples"},
            {"href": "/protocol/", "label": "Protocol"},
            {"href": repo_url, "label": "GitHub"},
        ],
        "commands": [
            {"label": "Terminal app", "command": "python -m erza run examples/greetings"},
            {"label": "Docs build", "command": "./update_docs.sh"},
            {"label": "Future remote app", "command": "erza example.com"},
        ],
        "pillars": [
            {
                "title": "`.erza` is the authoring surface",
                "body": "The project stays centered on component files and readable templates instead of hand-rolled terminal paint loops.",
            },
            {
                "title": "Terminal-native first",
                "body": "The current runtime is for TUIs, with transparent defaults, keyboard-first focus movement, and `hjkl` as the primary navigation model.",
            },
            {
                "title": "Remote transport can come later",
                "body": "The website direction is best treated as domains serving terminal apps over HTTPS, not as a browser-compatibility project.",
            },
        ],
        "examples": [
            {
                "name": "Tasks",
                "path": "examples/tasks/app.erza",
                "summary": "Backend-fed task list with focused buttons and stateful rerendering.",
            },
            {
                "name": "Greetings",
                "path": "examples/greetings/index.erza",
                "summary": "A directory-based entrypoint with `index.erza` and live backend state changes.",
            },
        ],
        "protocol_steps": [
            {
                "step": "1",
                "title": "Resolve a domain",
                "body": "`erza example.com` assumes HTTPS and asks the server for an erza app, not HTML.",
            },
            {
                "step": "2",
                "title": "Fetch a screen tree",
                "body": "The server returns a safe terminal-focused document or compiled UI tree the client can render locally.",
            },
            {
                "step": "3",
                "title": "Send actions back",
                "body": "Button presses and navigation-triggered actions post structured events to the server.",
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
