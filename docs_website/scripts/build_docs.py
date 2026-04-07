from __future__ import annotations

from pathlib import Path
import sys


DOCS_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = DOCS_ROOT.parent
SRC = REPO_ROOT / "app" / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from erza.docs_builder import DEFAULT_DOMAIN, build_docs


def main() -> int:
    source_dir = DOCS_ROOT / "website"
    output_dir = DOCS_ROOT / "site"
    written = build_docs(source_dir, output_dir, domain=DEFAULT_DOMAIN)
    print(f"built {len(written)} docs artifacts into {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
