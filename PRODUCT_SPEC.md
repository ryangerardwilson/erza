# erza Product Spec

## Product Definition

`erza` is a language and runtime model for building terminal user interfaces.
It does not target general CLI tooling, web apps, or desktop GUI apps.

The primary authoring unit is a `.erza` file. Each `.erza` file describes a TUI
component using:

- HTML-like tags for structure
- PHP-style template delimiters for dynamic sections
- terminal-specific components and layout primitives

The result should feel like writing UI components, not manually scripting a
terminal paint loop.

## Core Idea

An `erza` app is composed of `.erza` components that render terminal-native UI.
These components may optionally call into backend logic. That backend logic is
not tied to one language. The long-term product goal is to let users keep their
application logic in the programming language of their choice.

For prototyping, Python is the reference backend language.

## Goals

- Make TUI authoring feel as direct as component-based UI development
- Keep structure, presentation, and interaction readable in one file
- Support dynamic data and user interaction without requiring a full TUI engine
  to be hand-written
- Default to keyboard-first movement with `hjkl` as the primary navigation model
- Preserve the user's terminal look by defaulting to transparent backgrounds and
  the terminal's existing font
- Allow backend logic to live outside `.erza` when the app needs real state,
  I/O, or business logic
- Keep the authoring model approachable for developers who already understand
  HTML templates and embedded scripting

## Non-Goals

- General-purpose CLI command authoring
- Web browser rendering
- Desktop GUI rendering
- Tying the product permanently to Python
- Making `.erza` files depend on one specific server model or framework

## Authoring Model

`.erza` files combine declarative structure with inline dynamic regions.

Core concepts:

- Tags define layout and widgets
- Attributes configure behavior and styling
- Template output inserts dynamic values
- Template control blocks conditionally render or repeat sections
- Event bindings delegate actions to backend functions

Prototype syntax shape:

```erza
<Screen title="Tasks">
  <? tasks = backend("tasks.list") ?>

  <Column gap="1">
    <Header>Open Tasks</Header>

    <? for task in tasks ?>
      <Row>
        <Text><?= task.title ?></Text>
        <Button on:press="tasks.complete" task:id="<?= task.id ?>">
          Complete
        </Button>
      </Row>
    <? endfor ?>
  </Column>
</Screen>
```

Design intent:

- HTML-like tags make the visual hierarchy obvious
- `<? ... ?>` blocks provide a familiar embedded-template feel without tying the
  component language to one backend language
- `<?= ... ?>` outputs interpolated values into the rendered TUI
- Event attributes such as `on:press` connect the UI to backend actions

## Rendering Model

`.erza` components render to a terminal UI tree, not to HTML.

The runtime should own:

- layout
- focus management
- keyboard input
- repainting
- component lifecycle
- event dispatch
- terminal-safe styling

Even though the authoring syntax is inspired by HTML and PHP, the rendered
result must remain terminal-native in both behavior and constraints.

## Interaction Defaults

`erza` should be keyboard-first by default.

Default interaction rules:

- `hjkl` is the primary directional navigation model
- focus movement and component traversal should be designed around `h`, `j`,
  `k`, and `l`
- support for arrow keys may exist as a compatibility layer, but it should not
  replace `hjkl` as the default documented interaction model
- focus order should remain predictable and inspectable

## Visual Defaults

`erza` should respect the host terminal environment rather than trying to
override it.

Default visual rules:

- background rendering should be transparent or no-color by default
- components should not assume a painted canvas behind the interface
- the runtime should rely on the user's existing terminal font
- `erza` should not attempt to ship or prescribe its own font stack
- additional colors should be optional accents rather than a replacement for
  the host terminal theme

## Backend Model

Backend logic is optional. Static or mostly static TUIs should be possible
without a large backend layer.

When backend logic is needed, `erza` should expose a clean boundary:

- UI components declare what data or actions they need
- the backend provides named functions or handlers
- the runtime passes structured values across that boundary
- the backend returns simple serializable data

Long-term requirement:

- the backend boundary must be language-agnostic

Prototype requirement:

- the first backend adapter should be Python

## Python Prototype

The prototype should assume that `.erza` components can call Python-backed
functions through a small runtime bridge.

Prototype expectations:

- Python is the example backend in docs and demos
- backend handlers return plain structured data such as strings, numbers, lists,
  and dictionaries
- event handlers map cleanly to Python functions
- the integration stays small and inspectable rather than framework-heavy

Illustrative Python backend:

```python
def tasks_list():
    return [
        {"id": 1, "title": "Write the first erza parser"},
        {"id": 2, "title": "Prototype button events"},
    ]


def tasks_complete(task_id: int):
    print(f"completed {task_id}")
```

## Product Boundary

`erza` should focus on:

- component authoring
- TUI rendering
- backend integration boundaries
- developer ergonomics for terminal apps
- predictable keyboard navigation
- terminal-native visual restraint

`erza` should not drift into:

- a general shell scripting language
- a web-first framework with terminal output as a side effect
- a backend framework competing with the user's chosen language stack
- a styled terminal shell that overrides the user's terminal identity

## Early Prototype Priorities

- Define the `.erza` file grammar
- Define a minimal component set for layout and text interaction
- Build a renderer that can mount a simple screen and respond to keyboard input
- Prove the Python backend bridge with one small end-to-end example
- Keep the architecture open for non-Python backend adapters later
