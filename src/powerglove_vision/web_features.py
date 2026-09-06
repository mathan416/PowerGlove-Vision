# Project: PowerGlove Vision
# File: src/powerglove_vision/web_features.py
# Purpose: Re-export maintained game and tuning components for existing callers.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-06 - Separate maintained web modules without changing rendered pages.

"""Re-export maintained game and tuning components for existing callers."""

from .games_web import GAMES_CONTENT, GAMES_SCRIPT
from .tuning_web import TUNE_CONTENT, TUNE_SCRIPT, TUNE_THRESHOLDS
