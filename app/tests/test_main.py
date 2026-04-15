from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from contextlib import redirect_stdout

from _test_bootstrap import ensure_test_paths

ensure_test_paths()


APP_ROOT = Path(__file__).resolve().parents[1]
APP_MAIN = APP_ROOT / "main.py"
VERSION_FILE = APP_ROOT / "_version.py"


def _load_app_main_module():
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))
    spec = importlib.util.spec_from_file_location("erza_app_main_test", APP_MAIN)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {APP_MAIN}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MainContractTests(unittest.TestCase):
    def test_no_args_matches_help(self) -> None:
        no_args = subprocess.run(
            [sys.executable, str(APP_MAIN)],
            capture_output=True,
            text=True,
            check=True,
        )
        help_result = subprocess.run(
            [sys.executable, str(APP_MAIN), "-h"],
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(no_args.stdout, help_result.stdout)

    def test_help_is_human_written(self) -> None:
        result = subprocess.run(
            [sys.executable, str(APP_MAIN), "-h"],
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertIn("flags:\n", result.stdout)
        self.assertIn("commands:\n", result.stdout)
        self.assertIn("examples:\n", result.stdout)
        self.assertIn("erza run [source] [--backend <path>] [-u <username> -p <password>]", result.stdout)
        self.assertNotIn("usage:", result.stdout.lower())

    def test_dash_v_prints_runtime_version_exactly(self) -> None:
        result = subprocess.run(
            [sys.executable, str(APP_MAIN), "-v"],
            capture_output=True,
            text=True,
            check=True,
        )

        expected = VERSION_FILE.read_text(encoding="utf-8").split('"')[1]
        self.assertEqual(result.stdout, f"{expected}\n")

    def test_upgrade_invokes_installer_upgrade_mode(self) -> None:
        module = _load_app_main_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_script = root / "install.sh"
            stamp = root / "installer-args.txt"
            install_script.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "if [[ \"${1:-}\" == \"-v\" ]]; then\n"
                "  printf '0.0.1\\n'\n"
                "  exit 0\n"
                "fi\n"
                f"printf '%s\\n' \"$*\" > {stamp}\n",
                encoding="utf-8",
            )
            install_script.chmod(0o755)

            module.SPEC = module.AppSpec(
                app_name=module.SPEC.app_name,
                version=module.SPEC.version,
                help_text=module.SPEC.help_text,
                install_script_path=install_script,
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(module.main(["-u"]), 0)
            self.assertEqual(stamp.read_text(encoding="utf-8").strip(), "-u")


if __name__ == "__main__":
    unittest.main()
