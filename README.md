# erza

`erza` is a language project focused only on building terminal user interfaces.

This repository now includes a runnable v0 Python prototype with:

- `.erza` component files as the primary authoring surface
- HTML-like component tags
- PHP-style template blocks and output tags
- a small Python backend bridge
- terminal-native rendering through `curses`
- `hjkl`-first focus movement with arrow-key compatibility
- transparent/default terminal backgrounds and host terminal typography

## Direction

- `.erza` files define TUI components with HTML-like structure
- PHP-style template blocks and output tags drive dynamic UI composition
- Components render terminal-native layouts, widgets, and interactions
- `hjkl`-first navigation is the default interaction model
- Transparent or no-color backgrounds are the default visual baseline
- Typography inherits the user's existing terminal font
- Backend logic is optional and language-agnostic by design
- Python is the first prototype backend for examples and initial tooling
- A small, inspectable toolchain

See [`PRODUCT_SPEC.md`](PRODUCT_SPEC.md) for the current product definition.

## Quick Start

```bash
python -m erza run examples/tasks/app.erza
python -m erza run examples/greetings
```

If you prefer, `PYTHONPATH=src python -m erza ...` also works. An installed CLI
is available through `python -m pip install -e .` when `pip` is present.

`erza` automatically loads `backend.py` from the same directory as the `.erza`
entry file unless `--backend` is provided explicitly. If you pass a directory,
`erza` looks for `index.erza` inside it. If you omit the source entirely,
`erza run` defaults to the current directory.

## V0 Surface Area

Supported components:

- `<Screen title="...">`
- `<Column gap="...">`
- `<Row gap="...">`
- `<Header>`
- `<Text>`
- `<Button on:press="handler.name">`

Supported template features:

- `<?= expr ?>` output tags
- `<? name = expr ?>` assignments
- `<? if expr ?> ... <? else ?> ... <? endif ?>`
- `<? for item in items ?> ... <? endfor ?>`
- `backend("handler.name", **kwargs)` calls inside expressions

The v0 expression engine is intentionally constrained. It supports plain values,
dot access such as `task.title`, simple comparisons, boolean logic, list/dict
literals, and `backend(...)` calls.

## Example

```erza
<Screen title="Tasks">
  <? tasks = backend("tasks.list") ?>

  <Column gap="1">
    <Header>Open Tasks</Header>

    <? for task in tasks ?>
      <Row gap="2">
        <Text><?= task.title ?></Text>
        <Button on:press="tasks.complete" task:id="<?= task.id ?>">
          Complete
        </Button>
      </Row>
    <? endfor ?>
  </Column>
</Screen>
```

The bundled example in [`examples/tasks/app.erza`](examples/tasks/app.erza)
demonstrates the full v0 loop:

- query backend data during template expansion
- render terminal-native rows and buttons
- move focus with `hjkl`
- dispatch a button press to Python and re-render from backend state

## Docs Site

The repo also includes a static documentation site authored in `.erza` and
built for GitHub Pages.

```bash
./update_docs.sh
python -m erza run examples/greetings
```

Relevant paths:

- `website/`: `.erza` docs source plus static assets
- `scripts/build_docs.py`: docs-site compiler entrypoint
- `src/erza/docs_builder.py`: build logic shared with tests
- `.github/workflows/deploy-docs.yml`: GitHub Pages deployment

## Repo Layout

- `src/erza/template.py`: constrained `.erza` template engine
- `src/erza/parser.py`: rendered-markup to component-tree compiler
- `src/erza/runtime.py`: terminal renderer, focus model, and event loop
- `src/erza/backend.py`: Python backend bridge
- `examples/tasks/`: runnable end-to-end example
- `tests/`: unit coverage for template expansion and runtime focus behavior

## Status

This is still intentionally small. v0 proves the core language/runtime loop
without widening the project into web UI, generic CLI tooling, or a large
framework.
