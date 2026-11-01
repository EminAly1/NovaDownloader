#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
if [[ ! -d .venv/bin ]] || ! command -v npm >/dev/null 2>&1; then
  echo "Önce scripts/setup-dev.sh çalıştırın; yerel Deno kurulumu için npm gerekli." >&2
  exit 1
fi
case "$(uname -m)" in
  x86_64) deno_platform="linux-x64-glibc" ;;
  aarch64|arm64) deno_platform="linux-arm64-glibc" ;;
  *) echo "Bu kurulum betiği Linux x64/arm64 glibc içindir." >&2; exit 1 ;;
esac
if [[ "$(uname -s)" != Linux ]]; then
  echo "Bu kurulum betiği Linux içindir." >&2
  exit 1
fi
mkdir -p .tools/deno
cp scripts/deno/package.json scripts/deno/package-lock.json .tools/deno/
# npm checks the lockfile's integrity hashes. No lifecycle script or fallback download runs.
npm ci --prefix .tools/deno --ignore-scripts --no-audit --no-fund
deno_binary="$project_root/.tools/deno/node_modules/@deno/$deno_platform/deno"
[[ -x "$deno_binary" ]] || { echo "Deno platform paketi kurulamadı." >&2; exit 1; }
if [[ -e .venv/bin/deno && ! -L .venv/bin/deno ]]; then
  echo ".venv/bin/deno mevcut; kullanıcı dosyasının üzerine yazılmadı." >&2
  exit 1
fi
if [[ -L .venv/bin/deno && "$(readlink .venv/bin/deno)" != "$deno_binary" ]]; then
  echo ".venv/bin/deno farklı bir hedefe bağlı; kullanıcı bağlantısı değiştirilmedi." >&2
  exit 1
fi
ln -sfn "$deno_binary" .venv/bin/deno
.venv/bin/deno --version
