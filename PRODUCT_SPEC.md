# erza Product Spec

## Product Definition

`erza` is a language and runtime model for building terminal user interfaces.
It does not target general CLI tooling, desktop GUI apps, or browser-compatible
web rendering.

The primary authoring unit is a `.erza` file. The language uses:

- HTML-like tags for structure
- PHP-style template delimiters for dynamic regions
- section-first components as the main screen-building model

The result should feel like designing a structured terminal surface, not like
manually scripting a paint loop.

## Core Thesis

The language should be organized around sectional components instead of loose
headings and ad hoc focusable widgets.

Each screen should be readable as a stack of named regions:

- one screen
- several sections
- a small number of links or actions inside each section

That shape lets the runtime provide a simple navigation contract:

- `Ctrl+N` and `Ctrl+P` move between sections
- `gg` jumps to the first section and `G` jumps to the last
- `j` and `k` move inside the active section
- `h` goes back one page
- `l` opens the selected link or activates the selected action

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

The root is always a screen, but the primary authoring unit inside a screen is a
section.

Current component direction:

- `<Screen>` defines the page shell
- `<Section>` defines a named navigable region
- `<Text>` renders copy or values
- `<Action>` dispatches a backend event
- `<Link>` opens another page
- `<Column>` and `<Row>` remain as support layout for nested composition

Example shape:

```erza
<Screen title="Tasks">
  <? tasks = backend("tasks.list") ?>

  <Section title="Open Tasks">
    <Text>Ctrl+N/Ctrl+P switch sections. j/k move through work inside the active section.</Text>

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
- section traversal
- item traversal inside a section
- page history
- input handling
- repainting
- event dispatch

Even when the syntax borrows from HTML and PHP templates, the rendered result
must remain terminal-native in both behavior and constraints.

## Navigation Model

`erza` is keyboard-first by default.

Default interaction rules:

- `Ctrl+N` and `Ctrl+P` move across sections
- `gg` jumps to the first section and `G` jumps to the last
- `j` and `k` move across actionable items inside the active section
- `h` pops one page of history
- `l` opens the selected link or triggers the selected action
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
- local examples plus a read-only remote viewer

The prototype should stay easy to inspect and easy to revise while the
section-first language shape settles.
