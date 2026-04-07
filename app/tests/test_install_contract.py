from __future__ import annotations

import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "install.sh"


class InstallContractTests(unittest.TestCase):
    def _write_executable(self, path: Path, body: str) -> None:
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    def _run_installer(self, home_dir: Path, *args: str, path_prefix: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(home_dir)
        if path_prefix is not None:
            env["PATH"] = f"{path_prefix}:{env['PATH']}"
        return subprocess.run(
            ["/usr/bin/bash", str(INSTALLER), *args],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )

    def test_dash_v_without_argument_prints_latest_release(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            bin_dir.mkdir()
            home_dir.mkdir()

            self._write_executable(
                bin_dir / "curl",
                "#!/usr/bin/bash\n"
                "if [[ \"$*\" == *\"releases/latest\"* ]]; then\n"
                "  printf 'https://github.com/ryangerardwilson/erza/releases/tag/v0.1.21\\n'\n"
                "  exit 0\n"
                "fi\n"
                "echo unexpected curl call >&2\n"
                "exit 1\n",
            )

            result = self._run_installer(home_dir, "-v", path_prefix=bin_dir)

            self.assertEqual(result.stdout.strip(), "0.1.21")

    def test_upgrade_same_version_uses_dash_v(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            home_dir = tmp_path / "home"
            bin_dir.mkdir()
            home_dir.mkdir()

            self._write_executable(
                bin_dir / "curl",
                "#!/usr/bin/bash\n"
                "if [[ \"$*\" == *\"releases/latest\"* ]]; then\n"
                "  printf 'https://github.com/ryangerardwilson/erza/releases/tag/v0.1.21\\n'\n"
                "  exit 0\n"
                "fi\n"
                "echo unexpected curl call >&2\n"
                "exit 1\n",
            )
            self._write_executable(
                bin_dir / "erza",
                "#!/usr/bin/bash\n"
                "if [[ \"${1:-}\" == \"-v\" ]]; then\n"
                "  printf '0.1.21\\n'\n"
                "  exit 0\n"
                "fi\n"
                "echo unexpected invocation >&2\n"
                "exit 1\n",
            )

            result = self._run_installer(home_dir, "-u", path_prefix=bin_dir)

            self.assertIn("already installed", result.stdout)
            self.assertTrue((home_dir / ".local" / "bin" / "erza").exists())


if __name__ == "__main__":
    unittest.main()
