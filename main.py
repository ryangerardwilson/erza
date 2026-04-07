from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
APP_ROOT = ROOT / "app"
APP_MAIN = APP_ROOT / "main.py"


def _load_app_main():
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))
    spec = importlib.util.spec_from_file_location("erza_app_main", APP_MAIN)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load app main from {APP_MAIN}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    module = _load_app_main()
    return module.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
