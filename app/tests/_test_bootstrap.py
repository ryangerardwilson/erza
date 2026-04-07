from __future__ import annotations

from pathlib import Path
import sys


def ensure_test_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    for candidate in (root, src):
        text = str(candidate)
        if text not in sys.path:
            sys.path.insert(0, text)
