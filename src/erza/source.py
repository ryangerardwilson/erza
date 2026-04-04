from __future__ import annotations

from pathlib import Path


class SourceResolutionError(RuntimeError):
    """Raised when an erza source path cannot be resolved."""


def resolve_local_source_path(source: Path) -> Path:
    candidate = source.resolve()
    if not candidate.exists():
        raise SourceResolutionError(f"source path does not exist: {source}")
    if candidate.is_dir():
        candidate = candidate / "index.erza"
        if not candidate.exists():
            raise SourceResolutionError(f"directory does not contain index.erza: {source}")
    if candidate.is_dir():
        raise SourceResolutionError(f"source path is a directory, not a file: {candidate}")
    return candidate


def resolve_relative_source(base_file: Path, href: str) -> Path:
    candidate = Path(href)
    if not candidate.is_absolute():
        candidate = base_file.resolve().parent / candidate
    return resolve_local_source_path(candidate)
