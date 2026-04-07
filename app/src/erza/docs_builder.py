from __future__ import annotations

from datetime import UTC, datetime
import inspect
import json
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
            {"href": "/", "label": "Overview"},
            {"href": "/components/", "label": "Components"},
            {"href": "/patterns/", "label": "Patterns"},
            {"href": "/labs/", "label": "Labs"},
            {"href": "/protocol/", "label": "Protocol"},
            {"href": repo_url, "label": "GitHub"},
        ],
        "commands": [
            {"label": "Landing demo", "command": "python app/main.py run app/examples/landing"},
            {"label": "Local example", "command": "python app/main.py run app/examples/greetings"},
            {"label": "Animation lab", "command": "python app/main.py run app/examples/animation"},
            {"label": "Remote docs", "command": "erza run erza.ryangerardwilson.com"},
            {"label": "Docs build", "command": "./docs_website/update_docs.sh"},
        ],
        "story_questions": [
            "What if the internet did not need a web browser or Android/iOS gatekeepers?",
            "What if websites could open and be navigated directly from the terminal?",
            "What if frontend was redesigned to be CLI and TUI first?",
        ],
        "story_phrases_json": json.dumps(
            [
                "the internet did not need a web browser or Android/iOS gatekeepers?",
                "websites could open and be navigated directly from the terminal?",
                "frontend was redesigned to be CLI and TUI first?",
            ]
        ),
        "landing_command": "python app/main.py run app/examples/landing",
        "landing_video": "/assets/landing-demo.mp4",
        "landing_markup": _block(
            """
<Screen title="Erzanet">
  <Section title="What If">
    <Text>What if websites opened directly in the terminal?</Text>
    <Text>What if the network felt calmer than the browser?</Text>
  </Section>

  <Section title="Navigate">
    <Link href="/components/">Inspect components</Link>
    <Link href="/labs/">Inspect the capability matrix</Link>
  </Section>

  <Section title="Signal">
    <AsciiAnimation label="Pulse" fps="6">
      <Frame>+---+\n|*  |\n+---+</Frame>
      <Frame>+---+\n| * |\n+---+</Frame>
      <Frame>+---+\n|  *|\n+---+</Frame>
    </AsciiAnimation>
  </Section>
</Screen>
            """
        ),
        "pillars": [
            {
                "title": "Component-first, not browser-first",
                "body": "The long-term shape is a component system for terminal interfaces, with titled panels as the current house style rather than browser pages re-skinned in a shell.",
            },
            {
                "title": "The terminal stays in charge",
                "body": "The runtime owns layout, focus, history, and motion so the user stays in one keyboard-native environment instead of bouncing through browser chrome.",
            },
            {
                "title": "Erzanet is the next container",
                "body": "The hosted docs site is a proving ground for a future where remote apps and documents can be opened as `erza example.com` without leaving the terminal.",
            },
        ],
        "component_families": [
            {
                "name": "Shell",
                "summary": "Top-level structure and page rhythm.",
                "items": [
                    "<Screen title=\"...\">",
                    "<Section title=\"...\">",
                    "<Column gap=\"...\">",
                    "<Row gap=\"...\">",
                ],
            },
            {
                "name": "Content",
                "summary": "Readable surfaces and document structure.",
                "items": [
                    "<Header>",
                    "<Text>",
                    "<Link href=\"...\">",
                ],
            },
            {
                "name": "Action",
                "summary": "Intentional affordances instead of browser chrome.",
                "items": [
                    "<Action on:press=\"...\">",
                    "<Button on:press=\"...\">",
                ],
            },
            {
                "name": "Motion",
                "summary": "Terminal-safe movement without video or canvas baggage.",
                "items": [
                    "<AsciiAnimation fps=\"...\">",
                    "<Frame>...</Frame>",
                ],
            },
        ],
        "nesting_rules": [
            {
                "parent": "<Screen>",
                "allows": "top-level panels, layout containers, and other shell-level components",
                "body": "Screens should read like a small number of strong regions rather than a pile of loose widgets.",
            },
            {
                "parent": "<Section>",
                "allows": "text, links, actions, animations, and nested layout",
                "body": "A section should hold one idea or one workflow step and expose only the items needed inside that region.",
            },
            {
                "parent": "<AsciiAnimation>",
                "allows": "only <Frame> children",
                "body": "Animation stays declarative and transport-safe by carrying frame data and playback metadata instead of executable logic.",
            },
            {
                "parent": "<Row>",
                "allows": "small leaf components or compact nested panels",
                "body": "Rows are for tightly coupled items. Wide prose and large boxes should usually stay in columns.",
            },
        ],
        "examples": [
            {
                "name": "Landing",
                "path": "app/examples/landing/index.erza",
                "summary": "A terminal-native splash surface meant for recording and homepage storytelling.",
            },
            {
                "name": "Tasks",
                "path": "app/examples/tasks/app.erza",
                "summary": "Backend-fed task workflow with page history and remote docs links.",
            },
            {
                "name": "Greetings",
                "path": "app/examples/greetings/index.erza",
                "summary": "A small directory entrypoint with stateful backend changes.",
            },
            {
                "name": "Animation",
                "path": "app/examples/animation/index.erza",
                "summary": "A local lab for the new AsciiAnimation component and runtime tick loop.",
            },
        ],
        "patterns": [
            {
                "name": "Operator Dashboard",
                "summary": "A boxed overview with status strips, urgent queues, and a detail rail.",
                "regions": "Hero metrics, active queue, alerts, audit trail",
            },
            {
                "name": "Docs Reader",
                "summary": "Dense reference content with navigation, code samples, and capability notes.",
                "regions": "Overview, topic panels, code windows, appendix",
            },
            {
                "name": "Inbox + Inspector",
                "summary": "A list-first workflow with one active document and a side channel for metadata.",
                "regions": "Folder rail, message list, reading pane, inspector",
            },
            {
                "name": "Settings Surface",
                "summary": "Low-drama forms, toggles, and state explanations without browser settings sludge.",
                "regions": "Category nav, fields, confirmation area, recent changes",
            },
            {
                "name": "Launch Pad",
                "summary": "Command surfaces, recent destinations, and quick open flows for remote apps.",
                "regions": "Primary actions, saved endpoints, help, session status",
            },
            {
                "name": "Animation Lab",
                "summary": "A place for motion components, playback controls, and frame fallbacks.",
                "regions": "Poster frame, live runtime note, frame strip, open questions",
            },
        ],
        "capability_matrix": [
            {
                "feature": "Boxed panel layout",
                "runtime": "works",
                "docs": "works",
                "remote": "works",
                "erzanet": "ready",
            },
            {
                "feature": "Multi-page information architecture",
                "runtime": "works",
                "docs": "works",
                "remote": "works",
                "erzanet": "ready",
            },
            {
                "feature": "AsciiAnimation playback",
                "runtime": "works",
                "docs": "poster fallback",
                "remote": "poster fallback",
                "erzanet": "needs transport shape",
            },
            {
                "feature": "Complex nested composition",
                "runtime": "partial",
                "docs": "works",
                "remote": "partial",
                "erzanet": "needs component schema",
            },
            {
                "feature": "Stateful remote interaction",
                "runtime": "local only",
                "docs": "n/a",
                "remote": "read only",
                "erzanet": "core future work",
            },
        ],
        "lab_tracks": [
            {
                "title": "Remote Viewer Gaps",
                "body": "Use the hosted site as a checklist for what the HTML scraper still flattens, loses, or over-groups.",
            },
            {
                "title": "Component System Pressure",
                "body": "Use the richer pages to discover which panels should become first-class components instead of staying ad hoc markup patterns.",
            },
            {
                "title": "Motion Without Browser Baggage",
                "body": "Use AsciiAnimation to define how much motion can live in a TUI without turning into terminal abuse.",
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
        "animation_frames": [
            {
                "title": "Frame 1",
                "art": _block(
                    """
                    +---------+
                    |*        |
                    |  erza   |
                    +---------+
                    """
                ),
            },
            {
                "title": "Frame 2",
                "art": _block(
                    """
                    +---------+
                    |   *     |
                    |  erza   |
                    +---------+
                    """
                ),
            },
            {
                "title": "Frame 3",
                "art": _block(
                    """
                    +---------+
                    |      *  |
                    |  erza   |
                    +---------+
                    """
                ),
            },
        ],
        "animation_markup": _block(
            """
            <AsciiAnimation label="Signal" fps="6">
              <Frame>
              +---------+
              |*        |
              |  erza   |
              +---------+
              </Frame>
              <Frame>
              +---------+
              |   *     |
              |  erza   |
              +---------+
              </Frame>
              <Frame>
              +---------+
              |      *  |
              |  erza   |
              +---------+
              </Frame>
            </AsciiAnimation>
            """
        ),
    }


def _block(text: str) -> str:
    return inspect.cleandoc(text).strip()
