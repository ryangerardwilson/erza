from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from erza.cli import _build_parser, _resolve_source_path


class CliTests(unittest.TestCase):
    def test_run_defaults_to_current_directory(self) -> None:
        parser = _build_parser()

        args = parser.parse_args(["run"])

        self.assertEqual(args.source, Path("."))

    def test_directory_source_resolves_to_index_erza(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = root / "index.erza"
            entry.write_text("<Screen title='Test'></Screen>", encoding="utf-8")

            resolved = _resolve_source_path(root)

            self.assertEqual(resolved, entry.resolve())

    def test_directory_without_index_erza_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                _resolve_source_path(Path(tmp))


if __name__ == "__main__":
    unittest.main()
