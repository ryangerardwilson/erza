# erza Product Spec

## Product Definition

`erza` is a language and runtime model for building terminal user interfaces.
It does not target general CLI tooling, desktop GUI apps, or browser-compatible
web rendering.

The primary authoring unit is a `.erza` file. The language uses:

- HTML-like tags for structure
- PHP-style template delimiters for dynamic regions
- component-first building blocks with boxed terminal panels as the current house style

The result should feel like designing a structured terminal surface, not like
manually scripting a paint loop.

## Core Thesis

The language should be organized around explicit terminal components instead of
loose headings and ad hoc focusable widgets.

Each screen should be readable as a small set of named regions and components:

- one screen
- several strong panels or flows
- a small number of links, actions, or motion surfaces inside each region

That shape lets the runtime provide a simple navigation contract:

- header mode uses a single horizontal strip of section headers
- `h` and `k` move to the previous header; `j` and `l` move to the next header
- `Enter` focuses the current section body
- `gg` jumps to the first section and `G` jumps to the last
- section mode `j` and `k` move inside the current section line by line
- section mode `Ctrl+J` and `Ctrl+K` move by half a page
- `Esc` exits section mode and returns to the header strip
- section mode `Enter` opens the selected link or activates the selected action
- `Backspace` goes back one page
- `?` toggles the shortcuts modal

This is the default interaction identity for `erza`.

## Goals

- Make TUI authoring feel close to component-based UI development
- Keep structure, content, and interaction readable in one file
- Bias screen design toward calm, sectional composition instead of widget sprawl
- Make keyboard movement predictable and inspectable
- Preserve the user's terminal look by default with transparent/no-color
  backgrounds and host typography
- Keep backend integration optional and language-agnostic at the product level
- Keep the first implementation small enough to revise while the language shape
  is still moving

## Non-Goals

- General-purpose CLI command authoring
- Browser rendering parity
- Desktop GUI rendering
- Tying the product permanently to Python
- Expanding the runtime into a large framework before the core language settles

## Authoring Model

`.erza` combines declarative structure with inline dynamic regions.

The root is always a screen. Inside the screen, the language should prefer
explicit components over raw layout soup.

Current component direction:

- `<Screen>` defines the page shell
- `<Section>` defines the current boxed region primitive
- `<Text>` renders copy or values
- `<Action>` dispatches a backend event
- `<Link>` opens another page
- `<AsciiAnimation>` renders declarative terminal motion from raw ASCII frames
- `<Column>` and `<Row>` remain as support layout for nested composition

Example shape:

```erza
<Screen title="Tasks">
  <? tasks = backend("tasks.list") ?>

  <Section title="Open Tasks">
    <Text>Header mode uses a horizontal strip of section headers. h and k move to the previous header. j and l move to the next header. Press Enter to focus the current section.</Text>

    <? for task in tasks ?>
      <Text><?= task.title ?></Text>
      <Action on:press="tasks.complete" task:id="<?= task.id ?>">
        Complete task
      </Action>
    <? endfor ?>
  </Section>

  <Section title="Explore">
    <Link href="/protocol/">Open protocol notes</Link>
  </Section>
</Screen>
```

Design intent:

- a section should have one responsibility
- section titles should carry orientation, not decoration
- active affordances should be explicit and sparse
- copy should support the work in the section rather than compete with it

## Rendering Model

`.erza` components render to a terminal UI tree, not to HTML.

The runtime owns:

- layout
- section traversal in header mode
- line traversal inside a section in section mode
- page history
- input handling
- repainting
- animation playback
- event dispatch

Even when the syntax borrows from HTML and PHP templates, the rendered result
must remain terminal-native in both behavior and constraints.

## Navigation Model

`erza` is keyboard-first by default.

Default interaction rules:

- header mode uses a single horizontal strip of section headers
- `h` and `k` move to the previous header; `j` and `l` move to the next header
- `Enter` focuses the current section body
- `gg` jumps to the first section and `G` jumps to the last
- section mode `j` and `k` move across rendered lines inside the active section
- section mode `Ctrl+J` and `Ctrl+K` move by half a page
- `Esc` exits section mode and returns to the header strip
- section mode `Enter` opens the selected link or triggers the selected action
- `Backspace` pops one page of history
- `?` toggles the shortcuts modal
- arrow keys and Enter may exist as compatibility helpers, but they are not the
  primary documented interaction model

This should feel like moving between meaningful regions first, then acting
within a region.

## Visual Direction

`erza` should respect the host terminal environment rather than trying to
replace it.

Default visual rules:

- use transparent or no-color backgrounds by default
- inherit the user's terminal font
- avoid high-chrome widget framing
- use section titles and spacing to create hierarchy
- keep color usage optional and restrained

The design target is not "lots of widgets in a terminal." The design target is a
calm terminal surface with strong sectional rhythm.

## Backend Model

Backend logic is optional. Static or mostly static TUIs should still be
possible.

When backend logic is needed, `erza` should expose a clean boundary:

- the UI declares the data and actions it needs
- the backend provides named handlers
- the runtime passes structured values across that boundary
- the backend returns simple serializable data

Long-term requirement:

- the backend boundary must be language-agnostic

Prototype requirement:

- the first backend adapter is Python

## Remote Direction

The future networked version of `erza` should be treated as terminal-app
transport over HTTPS, not as a browser replacement with a different template
syntax.

The intended direction is:

- `.erza` remains the authoring model
- domains become transport endpoints for terminal apps
- the client renders terminal-native screens locally
- the server returns safe declarative UI state, not arbitrary executable code

`erza example.com` should eventually mean "fetch a terminal app from
`https://example.com` and render it locally."

## Python Prototype

The current prototype proves the model with:

- `.erza` templates
- a constrained parser/compiler
- a `curses` runtime
- a small Python backend bridge
- declarative ASCII animation playback in the local runtime
- local examples plus a read-only remote viewer

The prototype should stay easy to inspect and easy to revise while the
component model and erzanet transport shape settle.

## Form Direction

Forms should stay HTML-like in syntax while remaining terminal-native in
behavior.

The intended direction is:

- `<Form action="/path" submit-button-text="...">`
- `<Input name="field">`
- forms own an implicit submit control at the end
- no JavaScript layer
- no handler-name DSL
- localhost-backed submit for local apps
- future parity with remote erzanet apps

See [`FORMS_SPEC.md`](FORMS_SPEC.md) for the exact planned form shape.
