`erza` runtime workspace.

Primary project documentation lives in the repo-root `README.md`.

This directory contains the launcher, runtime source, runnable examples, test
suite, and install metadata for the app workspace.

Canonical app entrypoints in this workspace:

```bash
python main.py -h
python main.py -v
python main.py run examples/docs
./install.sh -h
./install.sh -v
./install.sh -u
```

Reusable Python UI surfaces:

- `erza.chat`: conversation list, boxed transcript, composer, fixed file picker,
  normal/insert mode, and file opening for Slack-like DM/GDM apps.
- `erza.input_edit`: shared single-line input editing for Erza form fields and
  chat composers.
