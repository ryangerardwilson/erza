# erza Forms Spec

## Purpose

This document defines the first real interactive form model for `erza`.

The goal is not to recreate browser forms or add a JavaScript event system. The
goal is to keep authoring close to HTML while only implementing the minimum
needed for:

- local text input
- submit to a backend URL
- rerender after submit
- future parity between localhost apps and remote erzanet apps

## Core Rule

Forms submit to a backend URL.

They do not dispatch handler names, client-side events, or JavaScript-like
callbacks.

The runtime model should be:

```text
submit(form.action, data) -> result
```

Where:

- `form.action` is a URL such as `/auth/login`
- `data` is a flat mapping of field names to string values
- `result` tells the runtime what to do next

## Authoring Model

The intended v1 syntax is:

```erza
<Screen title="Sign In">
  <Section title="Account">
    <Form action="/auth/login" submit-button-text="Sign in">
      <Input name="email" type="text" label="Email" required="mandatory" />
      <Input name="password" type="password" label="Password" required="mandatory" />
    </Form>
  </Section>
</Screen>
```

This stays close to HTML while removing everything `erza` does not need.

## V1 Components

### `<Form>`

Required attributes:

- `action`

Optional attributes:

- `method`
- `submit-button-text`

Rules:

- `method` defaults to `post`
- v1 only supports `post`
- `submit-button-text` defaults to `Submit`
- a form owns an implicit submit control at the end of the form
- a form may contain `Input`, `Text`, `Header`, `Row`, and `Column`

### `<Input>`

Required attributes:

- `name`

Optional attributes:

- `type`
- `value`
- `label`
- `required`

Rules:

- `type` defaults to `text`
- v1 supports only `text` and `password`
- `required` defaults to `optional`
- `required="mandatory"` marks the field with a leading `*` and blocks empty submit
- all submitted values are strings
- `<Input>` is only valid inside `<Form>`

## Architectural Direction

The current direct local runtime path is not enough for real forms. Forms should
be built on a localhost app server.

`erza run app/examples/login`

should conceptually do this:

1. resolve the local app
2. start an ephemeral localhost server for that app
3. create a local session
4. fetch the initial screen from that server
5. let the runtime edit fields locally
6. submit to the form's backend URL through that local server
7. rerender from the updated server state

This gives local apps and future remote apps the same basic shape.

## Localhost Server Responsibilities

The localhost app server should own:

- route resolution
- session lifecycle
- backend dispatch
- persistent server-side state for the current session
- rerendering the next `.erza` page after submit

The terminal runtime should own:

- rendering
- focus
- cursor movement
- temporary in-progress field edits
- showing backend errors or status

The backend server should be authoritative after submit.

## Submit Contract

The runtime should submit forms as plain HTTP-style requests.

Example:

```text
POST /auth/login
Content-Type: application/json
```

Body:

```json
{
  "email": "user@example.com",
  "password": "secret"
}
```

For v1, JSON is sufficient. There is no need to implement full browser form
encoding rules unless they become necessary later.

## Result Contract

The submit result should stay very small.

Supported v1 outcomes:

### Refresh

The backend updates state and the runtime reloads the current page.

This can be represented either by:

- an empty success response, or
- `{ "type": "refresh" }`

### Redirect

The backend asks the runtime to open another page.

```json
{
  "type": "redirect",
  "href": "/dashboard"
}
```

### Error

The backend reports a submission failure without leaving the current page.

```json
{
  "type": "error",
  "message": "Invalid email or password"
}
```

The runtime should show the error in the status area and then rerender the
current page.

## State Ownership

There are two different kinds of form state.

### Local edit state

While the user is typing, the runtime keeps:

- active field
- current cursor position
- current unsaved text for that field

This state is local to the TUI.

### Server state

After submit, the server becomes authoritative for:

- accepted field values
- validation errors
- route changes
- page rerendering

This lets local apps and future remote apps behave the same way.

## Runtime Interaction Model

Forms should fit the current `erza` navigation model instead of replacing it.

### Header mode

- current section-header strip behavior stays the same

### Section mode

- `j` and `k` move through section lines
- `Enter` on an input enters edit mode
- `Enter` on the implicit submit line submits the form
- `Enter` on a normal link still opens the link
- `Esc` exits section mode back to the header strip

### Edit mode

- printable characters insert into the current input
- `Backspace` deletes one character
- `Left` and `Right` move the cursor
- `Home` and `End` move to bounds
- `Enter` commits the current field edit and returns to section mode
- `Esc` cancels edit mode and returns to section mode

While in edit mode:

- page history should not trigger
- section movement keys should not move focus

## Rendering Rules

V1 inputs should remain single-line.

Recommended presentation:

```text
Email    [ user@example.com                 ]
Password [ ********                        ]
[ Sign in ]
```

Rules:

- inputs should render on one line
- password inputs should mask displayed characters
- placeholder text is intentionally not part of the form model
- focused inputs should show a visible cursor or insertion point

## Parser Rules

The parser should enforce these constraints:

- `<Form>` requires `action`
- `<Input>` requires `name`
- `<Input>` may only appear inside `<Form>`
- `<Input type="...">` must be one of the supported input types

## Non-Goals For V1

The following should not be included in the first form release:

- textarea
- checkbox
- radio
- select
- multi-step form wizards
- file upload
- client-side validation rules
- HTML compatibility features like `enctype`
- arbitrary client event handlers

## Implementation Phases

### Phase 1: Syntax and model

- add `Form` and `Input` to the component model
- add parser support and validation rules

### Phase 2: Localhost app server

- introduce the local session server
- make local apps render through that server instead of direct backend calls

### Phase 3: Runtime editing

- add input targets
- add edit mode
- add submit behavior

### Phase 4: Example app

- add a minimal login or contact example
- verify success, redirect, and error flows

### Phase 5: Documentation

- document authoring rules
- document runtime interaction
- document localhost form flow

## Open Questions

These can be resolved after the first working implementation:

- Should submit responses be plain status codes plus rerender, or typed JSON
  results?
- Should `label` live as an input attribute, or should labels remain separate
  text lines in author code?
- Should there be a visible form-level error region in addition to the status
  bar?
- Should form state survive page history moves inside the same session?
