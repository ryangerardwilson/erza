# erza

`erza` is a terminal-native UI language and runtime for docs, tools, and small
product surfaces.

If you are an AI agent, do not use this file as your primary guide. Read
`SKILLS.md` instead:

`https://erza.ryangerardwilson.com/skills`

The hosted docs shell also includes a worked example at:

`https://erza.ryangerardwilson.com/example`

The repo also contains that same guide directly at [SKILLS.md](./SKILLS.md).

## What erza Is

`erza` moves small interactive surfaces out of the browser and into the
terminal.

The project currently includes:

- the `.erza` language surface
- the Python template/parser/runtime prototype for local in-process apps
- a language-agnostic remote protocol that backends like Node.js can implement
- local and remote app support
- example apps
- `koinonia`, a larger social-app prototype built in `erza`

The long-term direction is `erzanet`: apps and documents that can be opened as
`erza example.com` instead of “open a browser tab and hunt around.”

## Why erza

Use `erza` when the browser is the wrong container.

- docs should open without tab sprawl, cookie banners, or popover junk
- a tool should feel local, keyboard-first, and terminal-native
- a workflow should survive slow links, large monitors, and minimal machines
- a remote product surface should be reachable as `erza example.com`

## Current Product Model

The current design direction is intentionally opinionated.

- A typical app should be a single `index.erza` file.
- Top-level `<Section>` blocks act like tabs.
- Selecting a tab changes the active page within the same screen.
- Tabs can be conditional, so login state can change which tabs exist.
- Tabs can declare `tab-order` and `default-tab`.
- Forms are modal-only.
- A modal is either:
  - a single-form modal
  - a view modal whose actions may only open form-only modals
- `ButtonRow` is the standard action surface inside pages and forms.
- Direct-action tabs are allowed for flows like `Logout`.
- Splash screens and splash animations are first-class.

In other words: `erza` apps are moving closer to a terminal-native React-like
single-surface model than to a folder of loosely connected pages.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/erza/main/app/install.sh | bash
```

If `~/.local/bin` is not already on your `PATH`, add it once and reload:

```bash
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc
```

## Quick Start

Open the hosted docs:

```bash
erza run erza.ryangerardwilson.com
```

Open local examples from a checkout:

```bash
python app/main.py run app/examples/docs
python app/main.py run app/examples/forms
python app/main.py run app/examples/animation
python app/main.py run app/examples/tasks/app.erza
python app/main.py run app/examples/greetings
```

Open the `koinonia` prototype locally:

```bash
python app/main.py run koinonia
```

Canonical CLI surface:

```bash
python app/main.py -h
python app/main.py -v
python app/main.py run <source> [--backend <path>] [-u <username> -p <password>]
```

`source` may be:

- a single `.erza` file
- a directory, in which case `erza` resolves `index.erza`
- an `http(s)` URL
- a bare domain like `erza.ryangerardwilson.com`
- omitted entirely, in which case `erza run` uses the current directory

`erza` automatically loads `backend.py` from the same directory as the entry
file unless `--backend` is provided explicitly. That local auto-loading is
Python-only today. Non-Python backends, including Node.js, fit through the
remote protocol instead of a local `backend.py` hook.

For remote apps that implement standardized auth, you can sign in before the
first render:

```bash
python app/main.py run koinonia-singapore.onrender.com -u ryan -p secret
```

## A Minimal App

```erza
<Screen title="Town Square">
  <? status = backend("ui.status") ?>

  <Section title="Feed" tab-order="1" default-tab="true">
    <Header>Town Square</Header>
    <Text><?= status ?></Text>
    <ButtonRow align="right">
      <Action on:press="ui.open_modal" modal:id="new-post">New post</Action>
    </ButtonRow>
  </Section>

  <Section title="Profile" tab-order="0">
    <Header>@ryan</Header>
    <Text>No description set yet.</Text>
  </Section>

  <Modal id="new-post" title="New Post">
    <Form action="/posts">
      <Input name="body" type="text" label="Post" required="mandatory" />
      <ButtonRow align="right">
        <Submit>Publish</Submit>
      </ButtonRow>
    </Form>
  </Modal>
</Screen>
```

Matching local `backend.py` in Python:

```python
from erza.backend import handler, redirect, route, session


@handler("ui.status")
def ui_status() -> str:
    return session().get("status", "Welcome to erza.")


@route("/posts")
def create_post(body: str = ""):
    session()["status"] = f"Posted: {body.strip()}"
    return redirect("index.erza")
```

Equivalent remote backend example in Node.js using the protocol:

```js
import express from "express";

const app = express();
app.use(express.json());

let status = "Welcome to erza.";

app.get("/.well-known/erza", (req, res) => {
  res.type("application/erza").send(`
<Screen title="Town Square">
  <Section title="Feed" default-tab="true">
    <Header>Town Square</Header>
    <Text>${status}</Text>
    <ButtonRow align="right">
      <Action on:press="ui.open_modal" modal:id="new-post">New post</Action>
    </ButtonRow>
  </Section>

  <Modal id="new-post" title="New Post">
    <Form action="/posts">
      <Input name="body" type="text" label="Post" required="mandatory" />
      <ButtonRow align="right">
        <Submit>Publish</Submit>
      </ButtonRow>
    </Form>
  </Modal>
</Screen>`);
});

app.post("/posts", (req, res) => {
  status = `Posted: ${String(req.body.body || "").trim()}`;
  res.json({ type: "redirect", href: "index.erza" });
});

app.post("/.well-known/erza/action", (req, res) => {
  res.json({ type: "refresh" });
});

app.listen(3000);
```

## Local and Remote Model

Locally, `erza` can run a file or directory with an optional Python backend.
Remotely, `erza` can open a host directly by domain or URL, which is where
Node.js and other backend languages fit cleanly today.

The current remote protocol is:

- `GET /.well-known/erza?path=/requested/path`
- `POST /.well-known/erza/action?path=/requested/path`
- `POST /.well-known/erza/auth`

Remote form submits post JSON directly to the form `action` URL.

The key design point is that `erza` is frontend-first, but not frontend-only:
there is a small backend contract for reads, writes, auth, and action dispatch.

## Language Surface

Supported root-level structure today:

- `<Screen title="...">`
- zero or one `<Splash duration-ms="...">`
- top-level `<Section>` tabs
- top-level `<Modal>` overlays

Common components:

- `<Section title="...">`
- `<Header>`
- `<Text>`
- `<AsciiArt>`
- `<Link href="...">`
- `<Action on:press="handler.name">`
- `<Button on:press="handler.name">`
- `<ButtonRow align="left|center|right">`
- `<Modal id="..." title="...">`
- `<Form action="/path">`
- `<Input name="field" type="text|password|ascii-art|hidden">`
- `<Submit>`
- `<AsciiAnimation fps="...">`
- `<Splash duration-ms="...">`
- `<SplashAnimation fps="...">`
- `<Column gap="...">`
- `<Row gap="...">`

## Runtime Controls

Global movement:

- `h` / left: previous tab or previous button in a row
- `l` / right: next tab or next button in a row
- `j` / down: move down inside a page
- `k` / up: move up inside a page
- arrow keys work as alternatives to `hjkl`
- `Enter`: activate current target or enter the active page
- `Esc`: leave page/edit mode or close modal focus back toward the page
- `Backspace`: go back
- `gg`: jump to the first top-level section
- `G`: jump to the last top-level section
- `Ctrl+D` / `Ctrl+U`: half-page movement
- `?`: shortcuts/help

## Where to Go Next

Humans should continue from:

- [SKILLS.md](./SKILLS.md) if you want the agent-style operating manual
- `app/examples/` for small runnable examples
- `koinonia/` for a larger end-to-end app
- `app/tests/` if you want to see what the runtime actually guarantees

## Repo Layout

- `README.md`: human-facing introduction and overview
- `SKILLS.md`: AI-agent guide to building with `erza`
- `AGENTS.md`: repo guardrails for coding agents
- `PRODUCT_SPEC.md`: current product direction
- `FORMS_SPEC.md`: older form-focused notes
- `app/main.py`: canonical CLI entrypoint
- `app/install.sh`: installer and upgrade path
- `app/src/erza/template.py`: template engine
- `app/src/erza/parser.py`: markup-to-component compiler
- `app/src/erza/runtime.py`: curses runtime and renderer
- `app/src/erza/backend.py`: backend bridge and route/session primitives
- `app/src/erza/remote.py`: remote fetch and remote app client
- `app/examples/`: runnable examples
- `app/tests/`: unit tests
- `koinonia/`: larger end-to-end example app
- `docs_website/`: browser shell that serves `README.md` and `SKILLS.md`

## Development

Run the app test suite:

```bash
cd app/tests
python -m unittest
```

Run the Koinonia tests:

```bash
cd koinonia
python -m unittest
```

Run the browser docs locally:

```bash
cd docs_website
npm install
npm run dev
```

## Status

This is still an intentionally small, opinionated prototype.

What the current repo already proves:

- `.erza` can serve as a readable TUI authoring language
- one-file app surfaces are practical
- tabbed section navigation works well in the terminal
- modal-only forms keep write flows cleaner
- backend reads and writes can share the same runtime surface
- remote apps can be opened directly by domain
- animated splash screens and ASCII motion can be first-class terminal UI

What is still fluid:

- the exact long-term language surface
- the remote transport and capability model for `erzanet`
- how much browser fallback should exist beside true terminal-native hosts
- how much more structure should be added to the app/layout vocabulary
