# Koinonia

`koinonia` is a terminal-native social media prototype for `erza`.

It is intentionally small and uses the current `erza` surface as-is:

- `.erza` files are the primary authoring surface
- feeds, threads, and profiles are composed from `Screen`, `Section`, `Text`, `Link`, `Action`, `Form`, `Input`, and `AsciiAnimation`
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

- serves `/.well-known/erza?path=...` for the terminal client
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
```

Before the first deploy, set these Render environment variables:

- `KOINONIA_SUPABASE_URL`
- `KOINONIA_SUPABASE_SERVICE_ROLE_KEY`

Schema bootstrap for the Supabase project lives in [`supabase_schema.sql`](/home/ryan/Infra/erza/koinonia/supabase_schema.sql).

## Data Direction

Current caveat:

- The local app now persists through Supabase.
- The hosted endpoint serves the same authored screens and backend routes, but the current remote `erza` client still treats local apps as the main mutation path for actions and forms.
