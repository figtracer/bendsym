#!/usr/bin/env sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
revision=$(sed -n 's/^BEND_REVISION=//p' "$root/toolchain.lock")
target=${BEND_ROOT:-"$root/../bend"}

command -v bun >/dev/null || {
  echo "error: Bun is required (https://bun.sh)" >&2
  exit 1
}

if [ ! -d "$target/.git" ]; then
  git clone https://github.com/bendlang/bend.git "$target"
fi
git -C "$target" fetch origin "$revision"
git -C "$target" checkout --detach "$revision"
bun "$target/bend2/main.ts" --version
