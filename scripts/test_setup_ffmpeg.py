import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SetupFFmpegTests(unittest.TestCase):
    def run_setup(self, installed=False, failure=""):
        git = shutil.which("git")
        bash = Path(git).parents[1] / "bin/bash.exe" if os.name == "nt" and git else shutil.which("bash")
        self.assertTrue(bash and Path(bash).is_file(), "安装流程回归需要 Bash（Windows 可使用 Git Bash）")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            binary = root / "bin"
            binary.mkdir()
            wrapper = '''#!/bin/bash
case "${0##*/}" in
  cat)
    while IFS= read -r line || [[ -n "$line" ]]; do printf '%s\\n' "$line"; done ;;
  sudo)
    shift
    if [[ "$1" == env ]]; then shift; export "$1"; shift; fi
    "$@" ;;
  timeout)
    printf 'timeout %s\\n' "$*" >> "$SETUP_LOG"
    [[ "$1" != --kill-after=* ]] || shift
    shift
    if [[ "$1" == ffmpeg && -f "$SETUP_MARKER" ]]; then printf 'ffmpeg fixture\\n'; exit 0; fi
    "$@" ;;
  apt-get)
    printf 'apt %s\\n' "$*" >> "$SETUP_LOG"
    if [[ " $* " == *" update "* ]]; then
      [[ "$SETUP_FAILURE" != update ]] || exit 100
    else
      [[ "$SETUP_FAILURE" != install ]] || exit 124
      : > "$SETUP_MARKER"
    fi ;;
  ffmpeg)
    [[ "$SETUP_FAILURE" != version ]] || exit 1
    printf 'ffmpeg fixture\\n' ;;
esac
'''
            for name in ("cat", "sudo", "timeout", "apt-get") + (("ffmpeg",) if installed else ()):
                path = binary / name
                path.write_text(wrapper, encoding="utf-8", newline="\n")
                path.chmod(0o755)
            binary_path = binary.as_posix()
            if os.name == "nt":
                binary_path = "/" + binary_path[0].lower() + binary_path[2:]
            environment = {**os.environ, "FIXTURE_BIN": binary_path,
                           "RUNNER_TEMP": root.as_posix(), "SETUP_SCRIPT": (ROOT / "scripts/setup_ffmpeg.sh").as_posix(),
                           "SETUP_LOG": (root / "commands.txt").as_posix(),
                           "SETUP_MARKER": (root / "installed").as_posix(), "SETUP_FAILURE": failure}
            result = subprocess.run([str(bash), "--noprofile", "--norc", "-c",
                                     'export PATH="$FIXTURE_BIN"; source "$SETUP_SCRIPT"'],
                                    env=environment, capture_output=True, text=True, timeout=10, check=False)
            log = root / "commands.txt"
            sources = root / "yingchuan-ubuntu.sources"
            return result, log.read_text(encoding="utf-8") if log.exists() else "", sources.read_text(encoding="utf-8") if sources.exists() else ""

    def test_preinstalled_decoder_does_not_access_package_repositories(self):
        result, log, sources = self.run_setup(installed=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("apt ", log)
        self.assertEqual(sources, "")

    def test_install_uses_signed_official_https_sources_and_time_limits(self):
        result, log, sources = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("https://archive.ubuntu.com/ubuntu", sources)
        self.assertIn("https://security.ubuntu.com/ubuntu", sources)
        self.assertIn("Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg", sources)
        self.assertNotIn("azure.archive", sources)
        self.assertIn("Dir::Etc::sourceparts=-", log)
        self.assertIn("Acquire::Retries=0", log)
        self.assertIn("Acquire::https::Timeout=15", log)
        self.assertIn("--kill-after=10s 60s", log)
        self.assertIn("--kill-after=10s 180s", log)
        self.assertIn("ffmpeg fixture", result.stdout)

    def test_failed_index_update_stops_installation(self):
        result, log, _ = self.run_setup(failure="update")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(" install ", log)
        self.assertNotIn("ffmpeg fixture", result.stdout)

    def test_install_timeout_is_not_reported_as_success(self):
        result, _, _ = self.run_setup(failure="install")
        self.assertEqual(result.returncode, 124)
        self.assertNotIn("ffmpeg fixture", result.stdout)

    def test_broken_preinstalled_decoder_fails_without_apt_fallback(self):
        result, log, _ = self.run_setup(installed=True, failure="version")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("apt ", log)


if __name__ == "__main__":
    unittest.main()
