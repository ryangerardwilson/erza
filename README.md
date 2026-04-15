# erza

`erza` is a terminal-native UI language for docs, tools, and small product
surfaces.

The core bet is simple: many browser experiences get worse once they are buried
under tabs, banners, popovers, and unstable page chrome. `erza` moves those
surfaces back into the terminal, where layout is constrained, keyboard movement
is explicit, and the interface can stay focused on the work.

The long-term direction is `erzanet`: apps and documents that can be opened as
`erza example.com` instead of "open a browser tab and hunt around."

This repository contains:

- the `.erza` language surface
- the Python template/parser/runtime prototype
- local and remote app support
- example apps
- `koinonia`, a larger social-app prototype built in `erza`

## Canonical Docs

This `README.md` is the canonical documentation source.

The browser docs at `https://erza.ryangerardwilson.com` now serve this
`README.md` directly as markdown, and the hosted terminal docs at
`erza run erza.ryangerardwilson.com` are derived from the same file.

That deploy path is automated directly by Vercel's Git integration. Pushes
to `main` that change `README.md` or `docs_website/` should redeploy the docs
site automatically.

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
file unless `--backend` is provided explicitly.

For remote apps that implement standardized auth, you can sign in before the
first render:

```bash
python app/main.py run koinonia-9xr5.onrender.com -u ryan -p ainiwmn
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

Matching `backend.py`:

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

## Language Surface

### Root structure

Supported root-level structure today:

- `<Screen title="...">`
- zero or one `<Splash duration-ms="...">`
- top-level `<Section>` tabs
- top-level `<Modal>` overlays

### Core components

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

### Sections as tabs

Top-level sections are treated as tabs.

- `tab-order="N"` controls tab ordering
- `default-tab="true"` selects the default active tab
- top-level actions like logout can live in a section with a direct `<Action>`
- apps commonly swap tab sets based on login state

### Button rows

`ButtonRow` is the standard action strip.

- it renders as a full-width action panel
- items are horizontally scrollable like tabs
- alignment can be `left`, `center`, or `right`
- inside a form, a `ButtonRow` may only contain `<Submit>` children
- outside a form, a `ButtonRow` may contain actions or links

### Modals

`erza` currently enforces two modal shapes:

1. Form modal
   - contains exactly one `<Form>`
   - used for login, compose, edit-profile, and other write flows
2. View modal
   - contains no form
   - may only contain actions that open form-only modals

This keeps reading and writing flows separate and reduces cognitive load.

### Forms

Forms are modal-only. A `<Form>` may not appear directly inside a page section.

Current form behavior:

- the first input is focused automatically when the modal opens
- `Enter` commits the current input and moves into the next input when possible
- submit buttons live in a `ButtonRow`
- multi-submit forms are supported through multiple `<Submit>` controls
- modal form action rows are typically right-aligned in app code
- form validation runs in the frontend before submit
- `ascii-art` inputs default to a `72` column limit in the frontend

### Splash screens

A screen can define a startup splash:

```erza
<Splash duration-ms="1400">
  <SplashAnimation fps="7">
    <Frame>...</Frame>
    <Frame>...</Frame>
  </SplashAnimation>
</Splash>
```

Use this for logo reveals, launch atmosphere, or short terminal-native intro
animations before the main app loads.

## Template Model

`.erza` files use HTML-like tags plus PHP-style template blocks.

Supported template features:

- `<?= expr ?>` output
- `<? name = expr ?>` assignment
- `<? if expr ?> ... <? else ?> ... <? endif ?>`
- `<? for item in items ?> ... <? endfor ?>`
- `backend("handler.name", **kwargs)` calls inside expressions

The expression engine is intentionally small. It supports:

- literals
- lists and dictionaries
- attribute access like `post.title`
- boolean logic
- simple comparisons
- function-style `backend(...)` calls

## Backend Model

Backends are currently Python prototypes.

Read side:

- `@handler("name")` exposes a function to templates through `backend("name")`

Write side:

- `@route("/path")` handles `<Form action="/path">` submissions
- action buttons can also call backend handlers through `on:press`
- `session()` exposes per-user UI state
- routes generally return `redirect("index.erza")` or an error result

This keeps the authoring surface language-neutral while using Python as the
current prototype backend.

## Remote Apps

Remote `erza` apps can be opened as a domain or URL.

`erza` first tries a terminal-native endpoint on the same host. The current
remote protocol is:

- `GET /.well-known/erza?path=/requested/path`
- `POST /.well-known/erza/action?path=/requested/path`
- `POST /.well-known/erza/auth`

The standardized auth endpoint accepts JSON credentials shaped as
`{"username": "...", "password": "..."}` and returns the same JSON result
contract as form submits: `refresh`, `redirect`, or `error`.

If a host does not expose a terminal-native `erza` surface, the client can fall
back to HTML rendering.

Current remote client behavior includes:

- persistent cookies for remote sessions
- remote form submits and remote action dispatch
- same-host path navigation
- loading overlays while a remote screen or form submit is in flight

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

Form behavior:

- opening a form modal enters the first field automatically
- `Enter` inside a field commits that field and advances to the next field
- on the last field, `Enter` advances to the next actionable target

## Examples

Useful examples in this repo:

- `app/examples/docs/`: docs-shaped example app
- `app/examples/forms/`: local form flow and backend routes
- `app/examples/animation/`: ASCII animation and splash direction
- `app/examples/tasks/`: task-oriented app flow
- `koinonia/`: larger social-app prototype using auth, profile editing, tabs, modals, remote deploy, and Supabase-backed state

## Repo Layout

- `README.md`: canonical documentation source
- `PRODUCT_SPEC.md`: current product direction
- `FORMS_SPEC.md`: older form-focused notes
- `AGENTS.md`: repo instructions for coding agents
- `app/main.py`: canonical CLI entrypoint
- `app/install.sh`: installer and upgrade path
- `app/src/erza/template.py`: template engine
- `app/src/erza/parser.py`: markup-to-component compiler
- `app/src/erza/runtime.py`: curses runtime and renderer
- `app/src/erza/backend.py`: backend bridge and route/session primitives
- `app/src/erza/remote.py`: remote fetch and remote app client
- `app/src/erza/docs_builder.py`: legacy docs build helper
- `app/examples/`: runnable examples
- `app/tests/`: unit tests
- `koinonia/`: larger end-to-end example app
- `docs_website/`: browser shell that should render this README rather than maintain separate docs content

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

## Current Status

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
