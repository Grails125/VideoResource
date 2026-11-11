import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


WHEEL = "imageio_ffmpeg-0.8.1-py3-none-manylinux_2_28_x86_64.whl"
WHEEL_SHA256 = "050d6850601c3b3890bd2b28306f3b842b3daea390a561101174375a1c460bda"
BINARY = "imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v9.0.2"
BINARY_SHA256 = "0d709a0bed1a43f24cd2c420878c63afea4580671b6949ad19ed124572f3bc3d"
BUILD = "n9.0.2-17-g2a571b6068-20260930"
PACKAGE_LICENSE = "imageio_ffmpeg-0.8.1.dist-info/licenses/LICENSE"
GPL_LICENSE = Path("/usr/share/common-licenses/GPL-3")
DOWNLOADS = (
    "https://files.pythonhosted.org/packages/de/0f/49292fbef69ee10ebcf97bb741602521caafcc6966d5fa1a2b868cc15655/" + WHEEL,
    "https://github.com/imageio/imageio-ffmpeg/releases/download/v0.8.1/" + WHEEL,
)
MAX_WHEEL = 80 * 1024 * 1024
MAX_BINARY = 180 * 1024 * 1024


def verify_file(path, expected, maximum):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise RuntimeError("FFmpeg 文件不存在、类型无效或超过大小上限")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise RuntimeError("FFmpeg SHA-256 不匹配；停止准备，请清除对应损坏缓存")


def obtain_wheel(cache):
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / WHEEL
    if destination.exists():
        verify_file(destination, WHEEL_SHA256, MAX_WHEEL)
        print("FFmpeg: verified cached wheel", flush=True)
        return destination
    with tempfile.TemporaryDirectory(prefix="ffmpeg-fetch-", dir=cache) as folder:
        staging = Path(folder)
        requirement = staging / "requirement.txt"
        for index, url in enumerate(DOWNLOADS):
            requirement.write_text(f"{url} --hash=sha256:{WHEEL_SHA256}\n", encoding="utf-8")
            print(f"FFmpeg: downloading fixed wheel from source {index + 1}/{len(DOWNLOADS)}", flush=True)
            try:
                subprocess.run([
                    sys.executable, "-m", "pip", "--disable-pip-version-check", "download",
                    "--no-index", "--no-deps", "--only-binary=:all:", "--require-hashes",
                    "--platform", "manylinux_2_28_x86_64", "--timeout", "15", "--retries", "0",
                    "--dest", str(staging), "--requirement", str(requirement),
                ], timeout=120, check=True)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                (staging / WHEEL).unlink(missing_ok=True)
                continue
            downloaded = staging / WHEEL
            verify_file(downloaded, WHEEL_SHA256, MAX_WHEEL)
            os.replace(downloaded, destination)
            return destination
    raise RuntimeError("FFmpeg 固定包下载失败；请检查 runner 的 DNS 与出网，原报告保留")


def prepare(cache, installation):
    wheel = obtain_wheel(cache)
    installation.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel) as archive:
        member = archive.getinfo(BINARY)
        license_member = archive.getinfo(PACKAGE_LICENSE)
        if not 0 < member.file_size <= MAX_BINARY or license_member.file_size > 16384:
            raise RuntimeError("FFmpeg 包内文件超过上限")
        with tempfile.TemporaryDirectory(prefix="ffmpeg-unpack-", dir=installation) as folder:
            staged = Path(folder) / "ffmpeg"
            with archive.open(member) as source, staged.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            verify_file(staged, BINARY_SHA256, MAX_BINARY)
            staged.chmod(0o755)
            licenses = installation / "licenses"
            licenses.mkdir(exist_ok=True)
            (licenses / "imageio-BSD-2-Clause.txt").write_bytes(archive.read(license_member))
            shutil.copyfile(GPL_LICENSE, licenses / "FFmpeg-GPL-3.0.txt")
            (licenses / "SOURCE.txt").write_text(
                "imageio-ffmpeg 0.8.1: https://github.com/imageio/imageio-ffmpeg/tree/v0.8.1\n"
                f"FFmpeg {BUILD}: https://github.com/FFmpeg/FFmpeg/tree/2a571b6068\n",
                encoding="utf-8",
            )
            executable = installation / "ffmpeg"
            os.replace(staged, executable)
    result = subprocess.run([str(executable), "-version"], capture_output=True, text=True, timeout=10, check=True)
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    if not first_line.startswith("ffmpeg version " + BUILD):
        raise RuntimeError("FFmpeg 实际构建版本不匹配")
    print(first_line, flush=True)
    return executable


def main():
    parser = argparse.ArgumentParser(description="从固定公开 wheel 准备 Linux x64 CI FFmpeg，不使用 APT。")
    parser.add_argument("--cache-dir", type=Path, default=Path.home() / ".cache/yingchuan-ffmpeg")
    parser.add_argument("--install-dir", type=Path,
                        default=Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "yingchuan-ffmpeg")
    options = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
        raise RuntimeError("CI FFmpeg 固定包仅支持 Linux x64")
    executable = prepare(options.cache_dir, options.install_dir)
    if path_file := os.environ.get("GITHUB_PATH"):
        with Path(path_file).open("a", encoding="utf-8") as output:
            output.write(str(executable.parent.resolve()) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
