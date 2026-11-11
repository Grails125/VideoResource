#!/usr/bin/env bash
set -euo pipefail

if command -v ffmpeg >/dev/null; then
  timeout --kill-after=5s 10s ffmpeg -version
  exit 0
fi

sources="${RUNNER_TEMP:?}/yingchuan-ubuntu.sources"
cat > "$sources" <<'SOURCES'
Types: deb
URIs: https://archive.ubuntu.com/ubuntu
Suites: noble noble-updates
Components: main universe
Architectures: amd64
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: https://security.ubuntu.com/ubuntu
Suites: noble-security
Components: main universe
Architectures: amd64
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
SOURCES

options=(
  -o "Dir::Etc::sourcelist=$sources"
  -o Dir::Etc::sourceparts=-
  -o APT::Update::Error-Mode=any
  -o Acquire::Retries=0
  -o Acquire::http::Timeout=15
  -o Acquire::https::Timeout=15
  -o DPkg::Lock::Timeout=15
)

printf 'Updating Ubuntu indexes from official HTTPS archives (60s limit).\n'
timeout --kill-after=10s 60s sudo -n env DEBIAN_FRONTEND=noninteractive apt-get "${options[@]}" update
printf 'Installing FFmpeg from signed Ubuntu packages (180s limit).\n'
timeout --kill-after=10s 180s sudo -n env DEBIAN_FRONTEND=noninteractive apt-get "${options[@]}" install --no-install-recommends -y ffmpeg
timeout --kill-after=5s 10s ffmpeg -version
