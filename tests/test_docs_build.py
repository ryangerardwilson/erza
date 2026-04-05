from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from erza.docs_builder import build_docs


class DocsBuildTests(unittest.TestCase):
    def test_build_docs_renders_templates_and_support_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            output = root / "output"
            assets = source / "assets"
            nested = source / "components"
            assets.mkdir(parents=True)
            nested.mkdir(parents=True)

            (source / "index.erza").write_text(
                "<!DOCTYPE html><html><body><h1><?= site.domain ?></h1></body></html>",
                encoding="utf-8",
            )
            (nested / "index.erza").write_text(
                "<!DOCTYPE html><html><body><p>nested</p></body></html>",
                encoding="utf-8",
            )
            (assets / "site.css").write_text("body { color: black; }", encoding="utf-8")

            written = build_docs(source, output, domain="docs.example.com")

            self.assertIn(output / "index.html", written)
            self.assertIn(output / "components" / "index.html", written)
            self.assertEqual(
                (output / "index.html").read_text(encoding="utf-8"),
                "<!DOCTYPE html><html><body><h1>docs.example.com</h1></body></html>",
            )
            self.assertTrue((output / "assets" / "site.css").exists())
            self.assertEqual(
                (output / "CNAME").read_text(encoding="utf-8"),
                "docs.example.com\n",
            )
            self.assertTrue((output / ".nojekyll").exists())


if __name__ == "__main__":
    unittest.main()
