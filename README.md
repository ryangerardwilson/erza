# erza

`erza` is a terminal-native UI language project for building component-driven
interfaces and exploring an in-terminal networked experience for software and
documents.

The basic bet is simple: a lot of browser experiences are bloated, fragile, and
hostile to focused work. `erza` aims at a different path. Instead of opening a
tab jungle just to read docs, inspect a tool, or work through a workflow, the
same experience can be rendered as a terminal-native interface with predictable
keyboard movement, restrained layout, and no browser chrome.

That future direction is the `erzanet`: terminal-addressed apps and documents
that can be opened without leaving the terminal.

This repository includes a runnable Python prototype with:

- `.erza` files as the primary authoring surface
- HTML-like tags with PHP-style template blocks
- component-oriented screen composition rendered as bordered terminal panels
- terminal-native rendering through `curses`
- keyboard-first navigation with `Ctrl+N`, `Ctrl+P`, `j`, `k`, `h`, and `l`
- transparent/default terminal backgrounds and host terminal typography

## Direction

The language is moving toward a component-first model, even though the current
prototype still renders many screens as sectional panels.

- A screen is composed from terminal components rather than browser pages.
- The current runtime uses titled panels as a neat default presentation.
- `Ctrl+N` and `Ctrl+P` move between top-level components.
- `gg` jumps to the first component and `G` jumps to the last.
- `j` and `k` move through the active component's items.
- `h` goes back one page.
- `l` opens the selected link or fires the selected action.

This keeps the runtime closer to navigating a clean terminal workspace than to
steering through arbitrary browser chrome or a floating cursor over random
widgets.

## Why This Exists

`erza` is for situations where the browser is the wrong container.

- docs that should be readable without tabs, popovers, and cookie banners
- tools that should feel local and keyboard-native
- workflows that should survive slow networks, large monitors, and minimal
  environments
- remote experiences that should be reachable as `erza example.com` instead of
  “open another browser tab”

If the browser made the experience worse, `erza` is the attempt to move that
experience back into a terminal-shaped environment.

See [`PRODUCT_SPEC.md`](PRODUCT_SPEC.md) for the current product definition.

## Quick Start

```bash
python -m erza run app/examples/docs
python -m erza run app/examples/tasks/app.erza
python -m erza run app/examples/greetings
python -m erza run app/examples/animation
python -m erza run https://erza.ryangerardwilson.com
python -m erza run erza.ryangerardwilson.com
```

If you prefer, `PYTHONPATH=app/src python -m erza ...` also works. An installed
CLI is available through `cd app && python -m pip install -e .` when `pip` is
present.

`erza` automatically loads `backend.py` from the same directory as the `.erza`
entry file unless `--backend` is provided explicitly. If you pass a directory,
`erza` looks for `index.erza` inside it. If you omit the source entirely,
`erza run` defaults to the current directory. If you pass an `http(s)` URL or a
bare domain, `erza` now first looks for a same-host `.erza` endpoint and falls
back to HTML rendering only when the host does not expose terminal-native
pages.

## V0 Surface Area

Primary components:

- `<Screen title="...">`
- `<Section title="...">`
- `<Text>`
- `<Link href="...">`
- `<Action on:press="handler.name">`
- `<AsciiAnimation fps="...">`

Support layout components:

- `<Column gap="...">`
- `<Row gap="...">`

Compatibility component:

- `<Button on:press="handler.name">`

`<Button>` still works, but the intended public vocabulary is `<Action>` inside
sections.

Supported template features:

- `<?= expr ?>` output tags
- `<? name = expr ?>` assignments
- `<? if expr ?> ... <? else ?> ... <? endif ?>`
- `<? for item in items ?> ... <? endfor ?>`
- `backend("handler.name", **kwargs)` calls inside expressions

The v0 expression engine is intentionally constrained. It supports plain values,
dot access such as `task.title`, simple comparisons, boolean logic, list/dict
literals, and `backend(...)` calls.

## Authoring Shape

```erza
<Screen title="Tasks">
  <? tasks = backend("tasks.list") ?>

  <Section title="Open Tasks">
    <Text>Ctrl+N/Ctrl+P switch sections. j/k move inside the active section.</Text>

    <? if tasks ?>
      <? for task in tasks ?>
        <Text><?= task.title ?></Text>
        <Action on:press="tasks.complete" task:id="<?= task.id ?>">
          Complete task
        </Action>
      <? endfor ?>
    <? else ?>
      <Text>All tasks complete.</Text>
    <? endif ?>
  </Section>

  <Section title="Explore">
    <Link href="https://erza.ryangerardwilson.com">Open hosted docs</Link>
  </Section>
</Screen>
```

The bundled examples in [`app/examples/tasks/app.erza`](app/examples/tasks/app.erza)
[`app/examples/greetings/index.erza`](app/examples/greetings/index.erza), and
[`app/examples/animation/index.erza`](app/examples/animation/index.erza) demonstrate
the full loop:

- load backend data during template expansion
- render named sections as the primary screen structure
- move across top-level components with `Ctrl+N` and `Ctrl+P`
- jump directly to the bounds with `gg` and `G`
- move through the active component's actions with `j` and `k`
- play declarative ASCII frame animations inside the runtime
- use `h` for page history and `l` for opening links or dispatching actions

## Docs Site

The public docs site now lives in `docs_website/` and is intended to be
iterated on like a normal web app while the terminal runtime evolves beside it.

Local docs workflow:

```bash
cd docs_website
npm install
npm run dev
```

Then open `http://localhost:3000`.

Production build:

```bash
cd docs_website
npm run build
```

Relevant paths:

- `app/`: runtime package, examples, tests, and packaging metadata
- `docs_website/app/`: Next.js routes
- `docs_website/ui/`: shared React UI pieces for the docs site
- `docs_website/lib/erza-pages.js`: shared route map for same-host browser and `.erza` pages
- `docs_website/lib/site-data.js`: docs content data
- `docs_website/public/assets/landing-demo.mp4`: homepage demo capture
- `docs_website/website/`: archived static `.erza` docs source
- `docs_website/update_docs.sh`: archived legacy docs builder entrypoint
- `.github/workflows/ci.yml`: Python + Next build verification

## Repo Layout

- `app/src/erza/template.py`: constrained `.erza` template engine
- `app/src/erza/parser.py`: rendered-markup to component-tree compiler
- `app/src/erza/runtime.py`: terminal renderer, section navigation, and event loop
- `app/src/erza/backend.py`: Python backend bridge
- `app/src/erza/remote.py`: remote fetch and read-only remote viewer
- `app/examples/animation/`: local AsciiAnimation lab
- `app/examples/docs/`: minimal `.erza` twins for the public docs routes
- `app/examples/`: runnable terminal examples
- `app/tests/`: unit coverage for templates, parsing, runtime behavior, and docs build

## Status

This is still intentionally small. The current prototype proves:

- `.erza` can serve as a readable TUI authoring language
- a neat boxed terminal layout can be enforced consistently in the runtime
- motion can be added as a declarative terminal component instead of browser media
- backend actions and local/remote links can share one navigation model
- the hosted docs site can act as a capability lab for a future `erzanet`
