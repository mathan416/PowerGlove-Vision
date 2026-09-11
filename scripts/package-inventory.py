#!/usr/bin/env python3
# Project: VirtualGlove
# File: scripts/package-inventory.py
# Purpose: Separate ordinary installation content from developer and research tools.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Added the end-user and Engineering Tools package boundary.
# Full history: docs/CHANGELOG.md and Git history.

"""Declare source-controlled tools that are not needed by an ordinary installation."""

ENGINEERING_FILES = frozenset({
    "native/nestopia-powerglove/diagnostic_trace.h",
    "scripts/analyze-latency-trace.py",
    "scripts/analyze-latency-video.py",
    "scripts/analyze-motion-samples.py",
    "scripts/analyze-motion-trace.py",
    "scripts/application-payload.py",
    "scripts/benchmark-camera-pipeline.py",
    "scripts/benchmark-diagnostic-overhead.py",
    "scripts/benchmark-direction-response.py",
    "scripts/benchmark-frame-preprocessing.py",
    "scripts/benchmark-motion-correction.py",
    "scripts/benchmark-native-motion-curve.py",
    "scripts/benchmark-palm-anchors.py",
    "scripts/benchmark-post-inference.py",
    "scripts/benchmark-staggered-trackers.py",
    "scripts/benchmark-tasks-live-stream.py",
    "scripts/benchmark-vision-replay.py",
    "scripts/build-app-lab-package.sh",
    "scripts/build-architecture-diagrams.py",
    "scripts/build-docs-pdf.py",
    "scripts/build-engineering-tools-package.py",
    "scripts/build-fceumm-benchmark.sh",
    "scripts/build-gesture-crops.py",
    "scripts/build-help-images.py",
    "scripts/build-install-packages.py",
    "scripts/build-installer-scripts.py",
    "scripts/build-matrix-animation-preview.py",
    "scripts/build-matrix-letter-images.py",
    "scripts/capture-guide-screenshots.py",
    "scripts/check-documentation.py",
    "scripts/check-source-docs.py",
    "scripts/compare-motion-matrix.py",
    "scripts/deploy-uno-q-wifi.sh",
    "scripts/fetch-runtime-assets.sh",
    "scripts/guided-vision-benchmark.py",
    "scripts/instrument-native-core.py",
    "scripts/manage-latency-traces.py",
    "scripts/package-inventory.py",
    "scripts/prepare-end-to-end-session.py",
    "scripts/record-vision-benchmark.py",
    "scripts/run-native-latency-session.py",
    "scripts/run-nestopia-powerglove-trace.py",
    "scripts/soak-camera-exposure.py",
    "scripts/soak-full-vision-exposure.py",
    "scripts/stamp-build-version.py",
    "scripts/stamp-firmware-version.py",
    "scripts/templates/install.sh.in",
    "scripts/verify-app-lab-package.py",
})


def is_engineering_file(name: str) -> bool:
    """Return whether a repository-relative path belongs only to engineering work."""
    return name in ENGINEERING_FILES
