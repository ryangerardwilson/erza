from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PACKAGE_ROOT = SRC / "erza"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

__path__ = [str(PACKAGE_ROOT)]

from erza.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
