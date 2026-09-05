#!/usr/bin/env bash
# Project: PowerGlove Vision
# File: scripts/build-fceumm-benchmark.sh
# Purpose: Build the pinned stock FCEUmm core used by the deterministic response benchmark.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added an isolated pinned FCEUmm benchmark build.
# Full history: docs/CHANGELOG.md and Git history.
set -eu

revision=236ccdfc911e84c60fea6b9d0699c2d440a8de14
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
destination=${1:-"$root/build/fceumm-benchmark"}
source_dir="$destination/source"

mkdir -p "$destination"
if [ ! -d "$source_dir/.git" ]; then
  git clone https://github.com/libretro/libretro-fceumm.git "$source_dir"
fi
git -C "$source_dir" fetch --depth 1 origin "$revision"
git -C "$source_dir" checkout --detach "$revision"
git -C "$source_dir" reset --hard "$revision"
make -C "$source_dir" -j"${JOBS:-2}"

core=$(find "$source_dir" -maxdepth 1 -type f \( -name 'fceumm_libretro.so' -o -name 'fceumm_libretro.dylib' \) -print | head -n 1)
test -n "$core"
cp "$core" "$destination/fceumm_libretro.${core##*.}"
printf '%s\n' "$destination/fceumm_libretro.${core##*.}"
