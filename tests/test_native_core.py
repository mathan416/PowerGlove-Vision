# Project: PowerGlove Vision
# File: tests/test_native_core.py
# Purpose: Keep the experimental Nestopia core isolated and evidence-gated.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Required installed records to identify the exact local patch.
#   2026-09-04 - Added isolation, protocol evidence, and distribution checks.
# Full history: docs/CHANGELOG.md and Git history.

"""Check the reproducible native research spike without building over the network."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NativeCoreTests(unittest.TestCase):
    def test_build_is_pinned_separate_and_uses_local_patch(self):
        script = (ROOT / "scripts/build-nestopia-powerglove.sh").read_text()
        self.assertIn("5a1cd378cb46ca9ccc2dd6f8b2b6a79ab986052e", script)
        self.assertIn("nestopia_powerglove_libretro", script)
        self.assertIn("native/nestopia-powerglove/nestopia-powerglove.patch", script)
        self.assertNotIn("/opt/retropie/libretrocores", script)
        self.assertNotIn("reset --hard", script)
        self.assertIn('cat-file -e "$revision^{commit}"', script)
        self.assertIn('make -C "$source_dir/libretro" -j"${JOBS:-2}" >&2', script)
        self.assertIn("The patch changed Nestopia's original copyright/license header", script)
        self.assertIn("NstInpPowerGlove.cpp", script)

    def test_patch_has_coherent_stale_safe_xy_bridge_and_trace(self):
        patch = (ROOT / "native/nestopia-powerglove/nestopia-powerglove.patch").read_text()
        for evidence in (
            'memcmp(out->magic, "PGV1", 4)',
            "out->guard_begin != out->guard_end",
            "now - out->arrived_ns <= 250000000ULL",
            "out->profile != 1",
            "glove.x =",
            "glove.y =",
            "glove.x = 128",
            "glove.y = 128",
            "Nestopia's 128-glove.y packet",
            "host value directly compensates",
            "PowerGloveVisionNativeEnabled() ? 10U : 12U",
            "glove.distance = 0",
            "glove.wrist = 0",
            "GESTURE_OPEN",
            "POWERGLOVE_TRACE",
            "PGV read bit=",
            "PGV config/write bit=",
            "packet boundary falling-strobe",
            "packet clock=%lu bytes=",
            'library_name     = "Nestopia PowerGlove"',
        ):
            self.assertIn(evidence, patch)

    def test_compatibility_record_separates_confirmed_and_unknown_fields(self):
        record = (ROOT / "docs/super-glove-ball-native.md").read_text()
        self.assertIn("NESdev material is a source of testable hypotheses", record)
        self.assertIn("Detection signature, packet length, boundaries, and bit order | Confirmed", record)
        self.assertIn("Z, wrist rotation, finger state, and action-button encoding | Unknown", record)
        self.assertIn("explicit FCEUmm", record)

    def test_trace_runner_records_digest_phases_and_safe_neutral_cases(self):
        runner = (ROOT / "scripts/run-nestopia-powerglove-trace.py").read_text()
        for evidence in (
            "rom_sha256", "trace_evidence", '"tracking_lost"',
            '"uncalibrated"', '"stale"', "packet_values",
        ):
            self.assertIn(evidence, runner)

    def test_distribution_keeps_gpl_notice_with_installed_core(self):
        installer = (ROOT / "scripts/install-nestopia-powerglove.sh").read_text()
        notice = (ROOT / "native/nestopia-powerglove/README.md").read_text()
        changes = (ROOT / "native/nestopia-powerglove/CHANGES.md").read_text()
        self.assertIn('destination/source/COPYING', installer)
        self.assertIn('target/COPYING', installer)
        self.assertIn('POWERGLOVE-VISION-CHANGES.md', installer)
        self.assertIn("GNU General Public License, version 2", notice)
        self.assertIn("not a compiled core", notice)
        self.assertIn("6a4318673085eb4eeda3ec84da1f905cf48c8d0e5ed1a07f0d644eb0860622ec", notice)
        self.assertIn("Martin Freij", changes)
        self.assertIn("leaves it byte-for-byte unchanged", changes)
        self.assertIn("camera-to-Nestopia Y orientation", changes)
        self.assertIn("6a4318673085eb4eeda3ec84da1f905cf48c8d0e5ed1a07f0d644eb0860622ec", changes)

    def test_patch_does_not_remove_upstream_attribution(self):
        patch = (ROOT / "native/nestopia-powerglove/nestopia-powerglove.patch").read_text()
        removed = [line[1:] for line in patch.splitlines()
                   if line.startswith("-") and not line.startswith("---")]
        protected_words = ("copyright", "license", "nestopia is free software", "martin freij")
        self.assertFalse(any(word in line.lower()
                             for line in removed for word in protected_words))


if __name__ == "__main__":
    unittest.main()
