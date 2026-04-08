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
- keyboard-first navigation with `h`, `j`, `k`, `l`, `Enter`, `Esc`, `gg`, `G`, and `?`
- transparent/default terminal backgrounds and host terminal typography

## Direction

The language is moving toward a component-first model, even though the current
prototype still renders many screens as sectional panels.

- A screen is composed from terminal components rather than browser pages.
- The current runtime uses titled panels as a neat default presentation.
- Header mode uses `h`, `j`, `k`, and `l` to move across the section grid.
- `Enter` focuses the current section body.
- `gg` jumps to the first section and `G` jumps to the last.
- Section mode uses `j` and `k` line by line.
- Section mode uses `Ctrl+J` and `Ctrl+K` to move by half a page.
- `Esc` exits section mode and returns focus to the header grid.
- Section mode uses `Enter` to open the current link or fire the current action.
- `Backspace` goes back one page.
- `?` toggles the shortcuts modal.

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

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/erza/main/app/install.sh | bash
```

If `~/.local/bin` is not already on your `PATH`, add it once to `~/.bashrc`
and reload your shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc
```

## Quick Start

```bash
erza run erza.ryangerardwilson.com
erza run erza.ryangerardwilson.com/install
erza run erza.ryangerardwilson.com/first-run
```

From a local checkout:

```bash
python app/main.py run app/examples/docs
python app/main.py run app/examples/tasks/app.erza
python app/main.py run app/examples/greetings
python app/main.py run app/examples/animation
```

If you prefer working inside the app workspace, `cd app && python main.py ...`
also works. The install surface follows the same pattern as your other apps:
`cd app && ./install.sh -u` installs or upgrades the CLI, after which
`erza run ...` works as the installed command.

Canonical launcher and installer surface from the app workspace:

```bash
cd app
python main.py -h
python main.py -v
python main.py run examples/docs
./install.sh -h
./install.sh -v
./install.sh -u
```

Release helper from the repo root:

```bash
./push_release_upgrade.sh
```

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
    <Text>Header mode uses hjkl to move across the section grid. Press Enter to focus the current section.</Text>

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
- move across the header grid with `h`, `j`, `k`, and `l`
- jump directly to the bounds with `gg` and `G`
- enter the current section with `Enter`
- move through the current section line by line with `j` and `k`
- move faster through the current section with `Ctrl+J` and `Ctrl+K`
- play declarative ASCII frame animations inside the runtime
- use `Esc` to return to the header grid, `Backspace` to move back in page history, and `Enter` to open links or dispatch actions inside section mode
- toggle the shortcuts modal with `?`

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

- `app/`: runtime code, examples, tests, and installer metadata
- `app/main.py`: canonical launcher entrypoint for the app workspace
- `app/install.sh`: installer and upgrade path for the app workspace
- `app/requirements.txt`: Python dependency manifest for the app workspace
- `app/_version.py`: single runtime version source
- `push_release_upgrade.sh`: release tag and local upgrade helper
- `docs_website/app/`: Next.js routes
- `docs_website/ui/`: shared React UI pieces for the docs site
- `docs_website/lib/erza-pages.js`: shared route map for same-host browser and `.erza` pages
- `docs_website/lib/site-data.js`: docs content data
- `docs_website/public/assets/landing-demo.mp4`: homepage demo capture
- `docs_website/erzanet_site/`: archived static `.erza` docs source
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
