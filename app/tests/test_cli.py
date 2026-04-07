from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from _test_bootstrap import ensure_test_paths

ensure_test_paths()

from erza.cli import _build_parser, _resolve_source_path
from erza.source import SourceResolutionError


class CliTests(unittest.TestCase):
    def test_run_defaults_to_current_directory(self) -> None:
        parser = _build_parser()

        args = parser.parse_args(["run"])

        self.assertEqual(args.source, ".")

    def test_directory_source_resolves_to_index_erza(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = root / "index.erza"
            entry.write_text("<Screen title='Test'></Screen>", encoding="utf-8")

            resolved = _resolve_source_path(str(root))

            self.assertEqual(resolved, entry.resolve())

    def test_directory_without_index_erza_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(SourceResolutionError):
                _resolve_source_path(tmp)

    def test_http_source_is_treated_as_remote(self) -> None:
        resolved = _resolve_source_path("https://example.com")

        self.assertEqual(resolved, "https://example.com")

    def test_bare_domain_defaults_to_https(self) -> None:
        resolved = _resolve_source_path("example.com/docs")

        self.assertEqual(resolved, "https://example.com/docs")


if __name__ == "__main__":
    unittest.main()
