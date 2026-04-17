# erza

`erza` is a terminal-native UI language, runtime, and thin app protocol for
docs, tools, and small product surfaces.

This `SKILLS.md` file is the AI-agent guide for `erza`.

Browser URL:
`https://erza.ryangerardwilson.com/skills`

Worked example URL:
`https://erza.ryangerardwilson.com/example`

The human-facing overview lives in `README.md`.

## Read This First

If you are an AI agent with no prior context, treat this file as the operating
manual.

`erza` is:

- a frontend-first application framework for the terminal
- a `.erza` authoring language
- a curses runtime
- a thin backend protocol for actions, forms, auth, and remote app loading

`erza` is not:

- a browser UI framework
- a generic CLI scaffolding tool
- a full backend framework with opinions about databases, jobs, or infra

The standard app shape is:

```text
my_app/
  index.erza
  backend.py        # Python local prototype backend, optional today
```

## If You Only Remember 12 Things

1. Build a single `index.erza`, not a folder of pages.
2. Top-level `<Section>` blocks are tabs.
3. Tabs render within one screen, not as separate documents.
4. Forms are modal-only.
5. A modal is either a single-form modal or a view modal that only opens form modals.
6. `ButtonRow` is the standard action surface.
7. `ui.*` actions are runtime-local. They do not call the backend.
8. Non-`ui.*` actions are backend actions.
9. `<Form action="/path">` is for backend writes with explicit route paths.
10. `<Link href="...">` is for navigation.
11. Use `hjkl` as the primary interaction model. Arrow keys are secondary aliases.
12. Default visual direction is terminal-native, keyboard-first, and low-chrome.

## Mental Model

An `erza` app is usually one terminal surface with these layers:

- `<Screen>`: the root container
- `<Splash>`: optional startup screen shown before the main app
- top-level `<Section>`: tabs across the app
- top-level `<Modal>`: overlays opened from tabs or page actions
- `<Form>`: write flows inside modals
- `backend(...)`: read-side template access
- actions and routes: write-side interaction contract

Think of it like this:

- `Screen` is the app shell
- `Section` is a tab/page inside that shell
- `Modal` is the overlay system
- `Form` is the write surface
- `ButtonRow` is the canonical action strip

Directionally, `erza` is closer to a terminal-native single-surface React app than
to a multi-page website.

## Build Rules

When authoring an app, follow these rules.

- Prefer one `index.erza` file per app.
- Put app-level tabs at the top level with `<Section>`.
- Use `tab-order` to set tab order.
- Use `default-tab="true"` to choose the first selected tab.
- Use direct-action tabs only for things like `Logout`.
- Put read-only context in pages or view modals.
- Put write flows in form-only modals.
- Use `ButtonRow` instead of scattering ad-hoc actions through content.
- Keep nested boxes meaningful. Use them to show hierarchy, not decoration.
- Keep backgrounds transparent or terminal-default.
- Do not assume a custom font.
- Keep the UI usable with `hjkl` alone.
- Use `<!-- ... -->` for source comments when you need to annotate a real `.erza` file.

## Action Contract

This is the most important thing to understand if `erza` feels unusual.

`on:press` is an action name, not always a URL.

There are four different write/navigation paths:

### 1. Runtime-local UI actions

Example:

```erza
<Action on:press="ui.open_modal" modal:id="new-post">New post</Action>
```

This does not call the backend. The runtime intercepts `ui.open_modal` and opens
a modal locally.

The `ui.*` namespace is reserved for runtime behavior.

### 2. Backend actions

Example:

```erza
<Action on:press="feed.like" post:id="42">Like</Action>
```

This is a backend action.

- in local apps, the runtime dispatches it directly through the backend bridge
- in remote apps, the runtime sends it to the standardized action endpoint

You do not see a route path inline because backend actions are command-based, not
route-based.

### 3. Form routes

Example:

```erza
<Form action="/posts">
```

This is route-based. Forms always submit to explicit paths.

### 4. Links

Example:

```erza
<Link href="docs.erza">Docs</Link>
```

Links are explicit navigation targets.

## Remote Protocol

A remote `erza` app is opened by host or URL. The current protocol is:

- `GET /.well-known/erza?path=/requested/path`
- `POST /.well-known/erza/action?path=/requested/path`
- `POST /.well-known/erza/auth`

Remote form submits post JSON directly to the form `action` URL.

### Remote action request

```json
{
  "action": "feed.like",
  "params": {"post_id": 42}
}
```

### Remote auth request

```json
{
  "username": "ryan",
  "password": "secret"
}
```

### Standard result contract

Forms and auth use the same result shape:

```json
{
  "type": "refresh"
}
```

```json
{
  "type": "redirect",
  "href": "index.erza"
}
```

```json
{
  "type": "error",
  "message": "Something went wrong"
}
```

This is the key portability boundary. A backend can be written in any language if
it speaks this contract.

## Backend Model

Today, the built-in local backend path is Python, but the product boundary is
still language-agnostic. Node.js and other languages fit through the remote
protocol cleanly.

Read side:

- `@handler("name")` exposes a function to templates through `backend("name")`

Write side:

- `@route("/path")` handles form submissions
- backend actions handle `on:press="some.action"`
- `session()` exposes per-user session state

Use Python first if you want the fastest local path. Use Node.js or another
language when you are building a remote host that implements the protocol.

## Start Building

### 1. Create the app shell

Start with one `index.erza`.

```erza
<Screen title="Town Square">
  <Section title="Profile" tab-order="0">
    <Header>@ryan</Header>
    <Text>No description yet.</Text>
  </Section>

  <Section title="Feed" tab-order="1" default-tab="true">
    <Header>Town Square</Header>
    <Text>Welcome to erza.</Text>
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
</Screen>
```

### 2. Add a backend

Python local example using `backend.py`:

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

Node.js remote-host example using the protocol:

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

### 3. Read backend state in the template

```erza
<? status = backend("ui.status") ?>
<Text><?= status ?></Text>
```

### 4. Run it

```bash
python app/main.py run path/to/app
```

If `path/to/app` is a directory, `erza` resolves `index.erza` automatically.

### 5. Read a real app

If you want a realistic reference instead of a toy example, read `koinonia/index.erza`.
It is currently `268` lines and shows that `erza` can express a small social-media
app in under `300` lines, including:

- auth-gated tabs
- post compose flows
- profile editing
- reply/view-replies modal flows
- thread viewing

### 6. Keep the backend distinction straight

Do not confuse these two backend paths:

- `backend.py` is the built-in Python local prototype path in this repo
- Node.js is supported by implementing the remote `erza` protocol on your host

## Core Authoring Rules

### Screen

`<Screen title="...">` is the root.

Supported root structure today:

- zero or one `<Splash>`
- top-level `<Section>` tabs
- top-level `<Modal>` overlays

### Sections

Top-level sections are tabs.

- use `tab-order="N"` for ordering
- use `default-tab="true"` for default activation
- use conditional template logic to change tabs by login state
- use a direct action section for flows like `Logout`

### Modals

There are only two valid modal types.

#### Form modal

A form modal contains exactly one `<Form>`.

Use it for:

- login
- signup
- compose
- edit profile
- reply
- any other write flow

#### View modal

A view modal contains no form.

It may only contain actions that open form-only modals.

Use it for:

- viewing replies
- viewing context
- choosing a next write action without mixing reading and writing

### Forms

Forms are modal-only.

Current form behavior:

- opening a form modal auto-focuses the first input
- `Enter` commits the current input and moves into the next input when possible
- submit buttons live in a `ButtonRow`
- multi-submit forms are supported with multiple `<Submit>` buttons
- `ascii-art` inputs enforce a frontend width limit of `72` columns

### ButtonRow

`ButtonRow` is the standard action strip.

- it is full-width
- it is horizontally scrollable
- alignment can be `left`, `center`, or `right`
- inside a form, it should contain `<Submit>` buttons
- outside a form, it may contain actions or links

### Splash

Use `<Splash>` for startup screens and `<SplashAnimation>` for ASCII logo motion.

```erza
<Splash duration-ms="1400">
  <SplashAnimation fps="7">
    <Frame>...</Frame>
    <Frame>...</Frame>
  </SplashAnimation>
</Splash>
```

## Template Model

`.erza` files use HTML-like tags plus PHP-style template blocks.

Supported template features:

- `<?= expr ?>`
- `<? name = expr ?>`
- `<? if expr ?> ... <? else ?> ... <? endif ?>`
- `<? for item in items ?> ... <? endfor ?>`
- `backend("handler.name", **kwargs)` inside expressions

The expression language is intentionally small.

It supports:

- literals
- lists and dictionaries
- attribute access like `post.title`
- boolean logic
- simple comparisons
- `backend(...)` calls

## Component Reference

Common authoring components:

- `<Screen title="...">`
- `<Section title="...">`
- `<Header>`
- `<Text>`
- `<AsciiArt>`
- `<Link href="...">`
- `<Action on:press="..."></Action>`
- `<ButtonRow align="left|center|right">`
- `<Modal id="..." title="...">`
- `<Form action="/path">`
- `<Input name="..." type="text|password|ascii-art|hidden">`
- `<Submit>`
- `<Splash duration-ms="...">`
- `<SplashAnimation fps="...">`
- `<AsciiAnimation fps="...">`
- `<Column gap="...">`
- `<Row gap="...">`

## Runtime Controls

Global movement:

- `h` / left: previous tab or previous button in a row
- `l` / right: next tab or next button in a row
- `j` / down: move down inside a page or modal
- `k` / up: move up inside a page or modal
- arrow keys work as aliases
- `Enter`: activate current target or enter the active page
- `Esc`: leave page/edit mode or close a modal
- `Backspace`: go back
- `gg`: jump to the first top-level section
- `G`: jump to the last top-level section
- `Ctrl+D` / `Ctrl+U`: half-page movement
- `?`: shortcuts/help

## Commands

Install:

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/erza/main/app/install.sh | bash
```

CLI:

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
- omitted, in which case the current directory is used

Examples:

```bash
python app/main.py run erza.ryangerardwilson.com
python app/main.py run app/examples/docs
python app/main.py run app/examples/forms
python app/main.py run app/examples/animation
python app/main.py run app/examples/tasks/app.erza
python app/main.py run app/examples/greetings
python app/main.py run koinonia
python app/main.py run koinonia-singapore.onrender.com -u ryan -p secret
```

## Common Mistakes

Avoid these.

- Do not spread one app across many `.erza` pages unless there is a real need.
- Do not put `<Form>` directly inside a page section.
- Do not mix read-only context and form editing in the same modal.
- Do not treat `ui.open_modal` like a backend route.
- Do not assume `on:press` always means a URL.
- Do not default to mouse-first or arrow-only interaction.
- Do not force backgrounds or fonts.
- Do not model `erza` as a browser-first framework.

## Examples Worth Reading

- `app/examples/docs/`: docs-shaped app
- `app/examples/forms/`: local form flow and routes
- `app/examples/animation/`: ASCII animation and splash direction
- `app/examples/tasks/`: task-oriented app flow
- `koinonia/index.erza`: a `268`-line social-media app example that shows how far a single `index.erza` file can go
- `koinonia/`: larger social app using auth, tabs, modals, replies, profile editing, remote deploy, and Supabase-backed state

## Repo Map

- `README.md`: canonical docs source
- `AGENTS.md`: repo guardrails for coding agents
- `PRODUCT_SPEC.md`: current product direction
- `FORMS_SPEC.md`: older form notes
- `app/main.py`: canonical CLI entrypoint
- `app/install.sh`: install and upgrade path
- `app/src/erza/template.py`: template engine
- `app/src/erza/parser.py`: markup compiler
- `app/src/erza/runtime.py`: curses runtime and renderer
- `app/src/erza/backend.py`: backend bridge, routes, sessions
- `app/src/erza/remote.py`: remote fetch, remote forms, remote actions, auth
- `app/examples/`: runnable examples
- `app/tests/`: unit tests
- `koinonia/`: larger end-to-end example app
- `docs_website/`: browser shell for serving this README and terminal docs

## Development

Run the app tests:

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

## Current Status

This repo is intentionally small and still fluid.

What it already proves:

- `.erza` is readable as a TUI authoring language
- single-file app surfaces are practical
- tabbed section navigation works well in the terminal
- modal-only forms simplify write flows
- runtime-local UI actions and backend actions can coexist cleanly
- remote apps can be opened directly by domain
- splash screens and ASCII motion can be first-class

What is still fluid:

- the final long-term language surface
- the full `erzanet` capability model
- how broad the component vocabulary should become
- how much browser fallback should exist beside true terminal-native hosts
