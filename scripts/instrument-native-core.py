#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/instrument-native-core.py
# Purpose: Instrument only an isolated diagnostic Nestopia build at checked insertion points.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Add bounded core-consumption evidence without altering the production patch.
# Full history: docs/CHANGELOG.md and Git history.

"""Apply exact diagnostic hooks to the pinned, already patched research source."""
import sys
from pathlib import Path


def instrument(source):
    """Reject drift or repeated instrumentation before modifying any source."""
    replacements = {
        'static int pgv_native_fd = -1;': '#include "pgv_diagnostic_trace.h"\n\nstatic int pgv_native_fd = -1;',
        '   const bool valid = pgv_native_read(&sample);':
            '   const bool valid = pgv_native_read(&sample);\n'
            '   pgv_diagnostic_record(valid, valid ? sample.sequence : 0,\n'
            '      valid ? sample.guard_begin : 0, valid ? sample.arrived_ns : 0);',
        '   Api::Input::Controllers::PowerGlove::callback.Set(&powerglove_callback, NULL);':
            '   pgv_diagnostic_open();\n'
            '   Api::Input::Controllers::PowerGlove::callback.Set(&powerglove_callback, NULL);',
        '   pgv_native_close();\n\n   if (machine)':
            '   pgv_native_close();\n   pgv_diagnostic_close();\n\n   if (machine)',
    }
    if 'pgv_diagnostic_' in source or any(source.count(key) != 1 for key in replacements):
        raise ValueError('Diagnostic insertion points changed; use a fresh pinned build')
    for before, after in replacements.items():
        source = source.replace(before, after)
    return source


if __name__ == '__main__':
    path = Path(sys.argv[1])
    path.write_text(instrument(path.read_text()))
