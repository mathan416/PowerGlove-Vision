#!/usr/bin/env bash
# Project: PowerGlove Vision
# File: scripts/build-nestopia-powerglove.sh
# Purpose: Build the isolated evidence-gated Nestopia PowerGlove research core.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added the pinned custom Nestopia core build.
#   2026-09-04 - Guarded the original Nestopia Power Glove source header.
# Full history: docs/CHANGELOG.md and Git history.
set -eu

revision=5a1cd378cb46ca9ccc2dd6f8b2b6a79ab986052e
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
destination=${1:-"$root/build/nestopia-powerglove"}
source_dir="$destination/source"

mkdir -p "$destination"
if [ ! -d "$source_dir/.git" ]; then
  git clone https://github.com/libretro/nestopia.git "$source_dir"
fi
if ! git -C "$source_dir" cat-file -e "$revision^{commit}" 2>/dev/null; then
  git -C "$source_dir" fetch --depth 1 origin "$revision"
fi
if git -C "$source_dir" apply --reverse --check "$root/native/nestopia-powerglove/nestopia-powerglove.patch" 2>/dev/null; then
  git -C "$source_dir" apply --reverse "$root/native/nestopia-powerglove/nestopia-powerglove.patch"
fi
if ! git -C "$source_dir" diff --quiet || ! git -C "$source_dir" diff --cached --quiet; then
  printf '%s\n' "The isolated Nestopia source has unrelated tracked changes; use a new build directory." >&2
  exit 1
fi
git -C "$source_dir" checkout --detach "$revision"
git -C "$source_dir" apply --check "$root/native/nestopia-powerglove/nestopia-powerglove.patch"
git -C "$source_dir" apply "$root/native/nestopia-powerglove/nestopia-powerglove.patch"

# The affected Nestopia implementation carries a 22-line upstream copyright
# and GPL header. Compare it directly with the pinned revision after patching;
# PowerGlove Vision changes belong below that header and in CHANGES.md.
header_check=$(mktemp -d)
trap 'rm -rf "$header_check"' EXIT HUP INT TERM
git -C "$source_dir" show "$revision:source/core/input/NstInpPowerGlove.cpp" \
  | sed -n '1,22p' > "$header_check/upstream"
sed -n '1,22p' "$source_dir/source/core/input/NstInpPowerGlove.cpp" \
  > "$header_check/patched"
if ! cmp -s "$header_check/upstream" "$header_check/patched"; then
  printf '%s\n' "The patch changed Nestopia's original copyright/license header." >&2
  exit 1
fi
make -C "$source_dir/libretro" -j"${JOBS:-2}" >&2

core=$(find "$source_dir/libretro" -maxdepth 1 -type f \( -name 'nestopia_libretro.so' -o -name 'nestopia_libretro.dylib' \) -print | head -n 1)
test -n "$core"
cp "$core" "$destination/nestopia_powerglove_libretro.${core##*.}"
printf '%s\n' "$destination/nestopia_powerglove_libretro.${core##*.}"
