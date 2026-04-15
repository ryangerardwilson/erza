# Koinonia

`koinonia` is a terminal-native social media prototype for `erza`.

It is intentionally small and now follows the single-screen app direction:

- one `index.erza` file is the whole app surface
- top-level sections act like tabs that change with login state
- logged-out viewers see `Why Koinonia` and `Login / Sign Up`
- logged-in viewers see `Feed` and `Profile`, and both tabs open with a post form
- state is stored in Supabase and accessed through a compact Python backend so the language shape can keep moving

## Local Run

From the repo root:

```bash
python app/main.py run koinonia
```

This gives you the full current local loop, including actions and forms.

Required local environment:

- `KOINONIA_SUPABASE_URL`
- `KOINONIA_SUPABASE_SERVICE_ROLE_KEY`

## Render Deploy

This directory includes a Render Blueprint at [`render.yaml`](/home/ryan/Infra/erza/koinonia/render.yaml).

The service entrypoint is [`render_service.py`](/home/ryan/Infra/erza/koinonia/render_service.py), which:

- serves one `index.erza` app through `/.well-known/erza?path=...`
- exposes the existing backend form routes over HTTP
- keeps a small in-memory session per browser/client cookie
- reads and writes persistent social state through Supabase

To deploy:

1. Push this repo to GitHub.
2. In Render, create a new Blueprint.
3. Point the Blueprint path to `koinonia/render.yaml`.
4. Deploy.

After deploy, the hosted app is reachable with:

```bash
erza run <your-render-host>
python app/main.py run <your-render-host> -u <username> -p <password>
```

The host also exposes the standardized remote auth endpoint:

- `POST /.well-known/erza/auth`

Before the first deploy, set these Render environment variables:

- `KOINONIA_SUPABASE_URL`
- `KOINONIA_SUPABASE_SERVICE_ROLE_KEY`

Schema bootstrap for the Supabase project lives in [`supabase_schema.sql`](/home/ryan/Infra/erza/koinonia/supabase_schema.sql).
