# Project: PowerGlove Vision
# File: tests/test_power_glove_rom_registry.py
# Purpose: Keep the audited Power Glove game list and shared mappings complete.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PowerGloveRomRegistryTests(unittest.TestCase):
    def test_all_audited_us_roms_have_expected_shared_profiles(self):
        games = json.loads((ROOT / "config/games.json").read_text())["games"]
        expected = {
            "Bad Street Brawler (USA)": "bad_street_brawler",
            "Defender II (USA)": "program_e",
            "Gyruss (USA)": "program_c",
            "Gun.Smoke (USA)": "program_g",
            "Joust (USA)": "program_b",
            "Knight Rider (USA)": "program_i",
            "Sesame Street 123 (USA)": "program_f",
            "Super Glove Ball (USA)": "super_glove_ball",
        }
        for stem, profile in expected.items():
            for extension in (".nes", ".zip", ".7z"):
                self.assertEqual(games[stem + extension], profile)

    def test_audit_keeps_native_protocol_unique_to_super_glove_ball(self):
        audit = (ROOT / "docs/power-glove-rom-input-audit.md").read_text()
        self.assertEqual(audit.count("native ten-byte Power Glove stream"), 1)
        self.assertIn("Only Super Glove Ball", audit)


if __name__ == "__main__":
    unittest.main()
