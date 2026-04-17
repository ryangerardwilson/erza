# example.md

This file is a worked example of a small `erza` app.

It shows the same tiny app through two backend shapes:

- a local Python `backend.py`
- a remote Node.js host implementing the `erza` protocol

## Minimal social app

The app shape is intentionally small:

- one `index.erza`
- two tabs: `Feed` and `Profile`
- one compose modal
- one backend write route
- one backend read value

## index.erza

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

## Python local backend

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

Run it locally:

```bash
python app/main.py run path/to/app
```

## Node.js remote backend

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

Open it remotely:

```bash
python app/main.py run localhost:3000
```

## What this proves

- the `.erza` file stays the same across backend languages
- Python is the built-in local path in this repo
- Node.js fits by implementing the remote protocol
- even a tiny app already gets tabs, modals, forms, and backend state
