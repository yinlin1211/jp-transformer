#!/usr/bin/env bash
# Render ABC files to staff SVG with abcjs.
# Usage: ABC_RENDERER=/path/to/render_abc.js bash scripts/render_abcjs.sh [in-dir] [out-dir]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RENDERER="${ABC_RENDERER:-/mnt/ssd/lian/白马入芦花janpu/local_jianpu_abc_demo/scripts/render_abc.js}"
IN="${1:-$ROOT/rt_abc}"
OUT="${2:-$ROOT/staff_abcjs}"

if [[ ! -f "$RENDERER" ]]; then
  echo "renderer not found: $RENDERER" >&2
  echo "set ABC_RENDERER=/path/to/local_jianpu_abc_demo/scripts/render_abc.js" >&2
  exit 1
fi

mkdir -p "$OUT"
for f in "$IN"/*.abc; do
  name="$(basename "$f" .abc)"
  node "$RENDERER" "$f" "$OUT/$name.svg"
done
