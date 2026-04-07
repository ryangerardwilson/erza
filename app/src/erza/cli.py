from __future__ import annotations

import argparse
from pathlib import Path
from typing import TypeAlias

from erza.backend import BackendBridge
from erza.remote import RemoteApp, RemoteError, is_remote_source, normalize_remote_url
from erza.runtime import ErzaApp, StaticScreenApp, run_curses_app
from erza.source import SourceResolutionError, resolve_local_source_path


AppSource: TypeAlias = Path | str


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        try:
            source = _resolve_source_path(args.source)
        except (SourceResolutionError, RemoteError) as exc:
            parser.error(str(exc))
        if isinstance(source, str) and args.backend is not None:
            parser.error("--backend is only supported for local .erza sources")
        if args.backend is not None and not args.backend.exists():
            parser.error(f"backend module does not exist: {args.backend}")
        try:
            app = _build_app(source, args.backend)
        except RemoteError as exc:
            parser.error(str(exc))
        try:
            run_curses_app(app)
        except RemoteError as exc:
            parser.error(str(exc))
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
        default=".",
        help="path, directory, URL, or bare domain to open",
    )
    run.add_argument(
        "--backend",
        type=Path,
        help="optional Python backend module; defaults to backend.py next to the source",
    )

    return parser


def _resolve_source_path(source: str) -> AppSource:
    if source.strip().startswith(("http://", "https://")):
        return normalize_remote_url(source)

    path_source = Path(source)
    if path_source.exists() or source in {".", ".."}:
        return resolve_local_source_path(path_source)

    if is_remote_source(source):
        return normalize_remote_url(source)

    return resolve_local_source_path(path_source)


def _build_app(source: AppSource, backend: Path | None) -> ErzaApp | RemoteApp | StaticScreenApp:
    if isinstance(source, Path):
        loaded_backend = _load_backend(source, backend)
        return ErzaApp(source, backend=loaded_backend, backend_path=backend)

    return RemoteApp(source)


def _load_backend(source: Path, backend: Path | None) -> BackendBridge:
    if backend is not None:
        return BackendBridge.from_module_path(backend)

    inferred = source.resolve().with_name("backend.py")
    if inferred.exists():
        return BackendBridge.from_module_path(inferred)
    return BackendBridge.empty()
