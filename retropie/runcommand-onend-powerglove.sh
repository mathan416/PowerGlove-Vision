#!/bin/sh
# Project: PowerGlove Vision
# File: retropie/runcommand-onend-powerglove.sh
# Purpose: Tell PowerGlove Vision that a RetroPie game ended without replacing existing cabinet hooks.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
# Full history: docs/CHANGELOG.md and Git history.

# Call this from the cabinet's existing runcommand-onend.sh.
/opt/powerglove/bin/powerglove-retropie-hook end
exit 0
