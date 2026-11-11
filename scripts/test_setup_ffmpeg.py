import contextlib
import hashlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import setup_ffmpeg as setup


class SetupFFmpegTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.installation = self.root / "installed"
        self.wheel = self.cache / setup.WHEEL
        self.binary = b"synthetic executable"
        self.gpl = self.root / "GPL-3"
        self.gpl.write_text("Synthetic GPL license", encoding="utf-8")
        with zipfile.ZipFile(self.wheel, "w") as archive:
            archive.writestr(setup.BINARY, self.binary)
            archive.writestr(setup.PACKAGE_LICENSE, b"Synthetic package license")
            archive.writestr("../must-not-extract", b"unselected entry")
            archive.writestr("imageio_ffmpeg/__init__.py", b"must not import or install")
        for attribute, value in (
            ("WHEEL_SHA256", hashlib.sha256(self.wheel.read_bytes()).hexdigest()),
            ("BINARY_SHA256", hashlib.sha256(self.binary).hexdigest()),
            ("GPL_LICENSE", self.gpl),
        ):
            patcher = patch.object(setup, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def version(self):
        return subprocess.CompletedProcess([], 0, "ffmpeg version " + setup.BUILD + "\n", "")

    def test_cached_wheel_and_binary_are_verified_before_version_check(self):
        with patch.object(setup.subprocess, "run", return_value=self.version()) as run:
            executable = setup.prepare(self.cache, self.installation)
        self.assertEqual(executable.read_bytes(), self.binary)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], [str(executable), "-version"])
        self.assertEqual((self.installation / "licenses/FFmpeg-GPL-3.0.txt").read_text(), "Synthetic GPL license")
        self.assertFalse((self.root / "must-not-extract").exists())
        self.assertFalse((self.installation / "imageio_ffmpeg").exists())

    def test_corrupt_cache_never_executes_or_downloads(self):
        self.wheel.write_bytes(b"corrupt cache")
        with patch.object(setup.subprocess, "run") as run, self.assertRaisesRegex(RuntimeError, "SHA-256"):
            setup.prepare(self.cache, self.installation)
        run.assert_not_called()
        self.assertFalse(self.installation.exists())

    def test_wrong_binary_digest_preserves_previous_executable(self):
        self.installation.mkdir()
        executable = self.installation / "ffmpeg"
        executable.write_bytes(b"previous executable")
        with patch.object(setup, "BINARY_SHA256", "0" * 64), patch.object(setup.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                setup.prepare(self.cache, self.installation)
        self.assertEqual(executable.read_bytes(), b"previous executable")
        run.assert_not_called()

    def test_download_uses_fixed_url_hash_and_no_index_or_dependencies(self):
        fixture = self.root / "fixture.whl"
        shutil.move(self.wheel, fixture)

        def download(command, **kwargs):
            requirement = Path(command[command.index("--requirement") + 1]).read_text()
            self.assertIn(setup.DOWNLOADS[0], requirement)
            self.assertIn("--hash=sha256:" + setup.WHEEL_SHA256, requirement)
            self.assertIn("--no-index", command)
            self.assertIn("--no-deps", command)
            self.assertIn("--require-hashes", command)
            self.assertEqual(kwargs["timeout"], 120)
            shutil.copyfile(fixture, Path(command[command.index("--dest") + 1]) / setup.WHEEL)
            return subprocess.CompletedProcess(command, 0)

        with patch.object(setup.subprocess, "run", side_effect=download):
            self.assertEqual(setup.obtain_wheel(self.cache), self.wheel)
        self.assertEqual(self.wheel.read_bytes(), fixture.read_bytes())

    def test_download_timeout_uses_only_the_second_pinned_mirror(self):
        fixture = self.root / "fixture.whl"
        shutil.move(self.wheel, fixture)
        attempts = []

        def download(command, **kwargs):
            requirement = Path(command[command.index("--requirement") + 1]).read_text()
            attempts.append(requirement)
            if len(attempts) == 1:
                raise subprocess.TimeoutExpired(command, 120)
            shutil.copyfile(fixture, Path(command[command.index("--dest") + 1]) / setup.WHEEL)
            return subprocess.CompletedProcess(command, 0)

        with patch.object(setup.subprocess, "run", side_effect=download):
            setup.obtain_wheel(self.cache)
        self.assertEqual(len(attempts), 2)
        self.assertIn(setup.DOWNLOADS[1], attempts[1])
        self.assertTrue(all(setup.WHEEL_SHA256 in attempt for attempt in attempts))

    def test_all_network_failures_leave_no_cached_package_or_executable(self):
        self.wheel.unlink()
        with patch.object(setup.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pip")) as run:
            with self.assertRaisesRegex(RuntimeError, "DNS"):
                setup.prepare(self.cache, self.installation)
        self.assertEqual(run.call_count, 2)
        self.assertFalse(self.wheel.exists())
        self.assertFalse(self.installation.exists())

    def test_version_failure_does_not_advertise_path(self):
        path_file = self.root / "github-path"
        path_file.write_text("previous\n", encoding="utf-8")
        with patch.object(setup.platform, "system", return_value="Linux"), \
                patch.object(setup.platform, "machine", return_value="x86_64"), \
                patch.dict(os.environ, {"GITHUB_PATH": str(path_file)}), \
                patch("sys.argv", ["setup_ffmpeg.py", "--cache-dir", str(self.cache), "--install-dir", str(self.installation)]), \
                patch.object(setup.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "ffmpeg")):
            with self.assertRaises(subprocess.CalledProcessError):
                setup.main()
        self.assertEqual(path_file.read_text(), "previous\n")

    def test_main_adds_verified_executable_to_path(self):
        path_file = self.root / "github-path"
        with patch.object(setup.platform, "system", return_value="Linux"), \
                patch.object(setup.platform, "machine", return_value="x86_64"), \
                patch.dict(os.environ, {"GITHUB_PATH": str(path_file)}), \
                patch("sys.argv", ["setup_ffmpeg.py", "--cache-dir", str(self.cache), "--install-dir", str(self.installation)]), \
                patch.object(setup.subprocess, "run", return_value=self.version()):
            self.assertEqual(setup.main(), 0)
        self.assertEqual(path_file.read_text().strip(), str(self.installation.resolve()))

    def test_unsupported_platform_fails_before_network(self):
        with patch.object(setup.platform, "system", return_value="Windows"), \
                patch("sys.argv", ["setup_ffmpeg.py"]), patch.object(setup.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "Linux x64"):
                setup.main()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
