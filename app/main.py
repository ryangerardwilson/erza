#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

from _version import __version__
from rgw_cli_contract import AppSpec, resolve_install_script_path, run_app


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

INSTALL_SCRIPT = resolve_install_script_path(__file__)
HELP_TEXT = """erza
terminal-native runtime for .erza apps and erzanet docs

flags:
  erza -h
    show this help
  erza -v
    print the installed version
  erza -u
    upgrade through install.sh

commands:
  erza run [source] [--backend <path>] [-u <username> -p <password>]
    open a local .erza file, directory, URL, or bare domain

examples:
  erza run examples/docs
  erza run examples/tasks/app.erza
  erza run erza.ryangerardwilson.com
"""
SPEC = AppSpec(
    app_name="erza",
    version=__version__,
    help_text=HELP_TEXT,
    install_script_path=INSTALL_SCRIPT,
)


def _dispatch(argv: list[str]) -> int:
    from erza.cli import main as cli_main

    try:
        return cli_main(argv)
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        print(exc.code, file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    return run_app(SPEC, sys.argv[1:] if argv is None else argv, _dispatch)


if __name__ == "__main__":
    raise SystemExit(main())
