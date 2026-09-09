#!/usr/bin/env bash
# Project: PowerGlove Vision
# File: scripts/install-powerglove-dot.sh
# Purpose: Build and install the ROM-free RetroPie calibration test core.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Added the calibration-test installer.
# Full history: docs/CHANGELOG.md and Git history.

set -euo pipefail
readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PREFIX="${1:-/opt/retropie}"
readonly DESTINATION="${PREFIX}/libretrocores/lr-powerglove-dot"
readonly BUILD="$(mktemp -d)"
trap 'rm -rf "${BUILD}"' EXIT

${CXX:-c++} -std=c++11 -O2 -fPIC -shared \
  "${ROOT}/native/powerglove-dot/powerglove_dot.cpp" \
  -o "${BUILD}/powerglove_dot_libretro.so"
install -d -m 0755 "${DESTINATION}"
install -m 0755 "${BUILD}/powerglove_dot_libretro.so" "${DESTINATION}/powerglove_dot_libretro.so"
printf '%s\n' 'Installed lr-powerglove-dot.'
