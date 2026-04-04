from __future__ import annotations

import argparse
from pathlib import Path

from erza.backend import BackendBridge
from erza.runtime import ErzaApp, run_curses_app


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        try:
            source = _resolve_source_path(args.source)
        except (FileNotFoundError, IsADirectoryError) as exc:
            parser.error(str(exc))
        if args.backend is not None and not args.backend.exists():
            parser.error(f"backend module does not exist: {args.backend}")
        backend = _load_backend(source, args.backend)
        app = ErzaApp(source, backend=backend)
        run_curses_app(app)
        return 0

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="erza")
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="run an .erza component tree")
    run.add_argument(
        "source",
        nargs="?",
        default=Path("."),
        type=Path,
        help="path to a root .erza file or a directory containing index.erza",
    )
    run.add_argument(
        "--backend",
        type=Path,
        help="optional Python backend module; defaults to backend.py next to the source",
    )

    return parser


def _resolve_source_path(source: Path) -> Path:
    candidate = source.resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"source path does not exist: {source}")
    if candidate.is_dir():
        candidate = candidate / "index.erza"
        if not candidate.exists():
            raise FileNotFoundError(f"directory does not contain index.erza: {source}")
    if candidate.is_dir():
        raise IsADirectoryError(f"source path is a directory, not a file: {candidate}")
    return candidate


def _load_backend(source: Path, backend: Path | None) -> BackendBridge:
    if backend is not None:
        return BackendBridge.from_module_path(backend)

    inferred = source.resolve().with_name("backend.py")
    if inferred.exists():
        return BackendBridge.from_module_path(inferred)
    return BackendBridge.empty()
