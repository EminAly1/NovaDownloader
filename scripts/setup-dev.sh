#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
if ! command -v uv >/dev/null 2>&1; then
  echo "uv gerekli: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi
uv sync --frozen --group dev
echo "Geliştirme ortamı hazır. Başlatma: .venv/bin/python -m novadownloader"
