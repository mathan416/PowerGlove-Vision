#!/bin/sh
# Project: PowerGlove Vision
# File: retropie/runcommand-onstart-powerglove.sh
# Purpose: Forward RetroPie game-launch metadata to PowerGlove Vision without replacing existing cabinet hooks.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
# Full history: docs/CHANGELOG.md and Git history.

# Call this from the cabinet's existing runcommand-onstart.sh, preserving its
# controller, RGB, and trackball setup. RetroPie supplies these four arguments.
/opt/powerglove/bin/powerglove-retropie-hook start "$1" "$2" "$3" "$4"
exit 0
