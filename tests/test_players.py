# Project: PowerGlove Vision
# File: tests/test_players.py
# Purpose: Verify player migration, persistent progress, bounded backups, and atomic changes.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Cover player isolation, stale writes, calibration gates, and recovery.
# Full history: docs/CHANGELOG.md and Git history.

"""Exercise persisted user data rather than matching implementation strings."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from powerglove_vision.tuning import TuningManager


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "gesture-tuning.json"
        self.path.write_text(json.dumps({"version": 1, "thresholds": {"index": {"on": .6, "off": .4}}}))
        self.manager = TuningManager(self.path)

    def command(self, action, **extra):
        state = self.manager.player_snapshot()
        return self.manager.player_command(dict(action=action, player=state["active"], generation=state["generation"], **extra))

    def test_legacy_settings_migrate_only_after_a_successful_write(self):
        self.assertEqual(json.loads(self.path.read_text())["version"], 1)
        self.assertEqual(self.manager.saved["index"]["on"], .6)
        self.command("rename", name="Alex")
        restored = TuningManager(self.path)
        self.assertEqual(restored.player_snapshot()["players"][0]["name"], "Alex")
        self.assertEqual(restored.saved, self.manager.saved)
        self.assertEqual(json.loads(self.path.read_text())["version"], 2)

    def test_players_isolate_tuning_and_progress(self):
        self.command("progress", progress={"course":1,"completed":[0,1],"lesson":2})
        new = self.command("create", name="Sam")
        self.assertEqual(new["progress"]["completed"], [])
        self.assertTrue(self.manager.needs_center())
        self.manager.players.save_thresholds({"thumb":{"on":.7,"off":.3}})
        self.command("select", id="default")
        self.assertEqual(self.manager.saved, {"index":{"on":.6,"off":.4}})
        self.assertEqual(self.manager.player_snapshot()["progress"]["completed"], [0,1])

    def test_progress_survives_restart_and_stale_tabs_cannot_undo_reset(self):
        state=self.command("progress", progress={"course":1,"completed":list(range(16)),"lesson":15})
        self.assertEqual(len(TuningManager(self.path).player_snapshot()["progress"]["completed"]),16)
        self.command("reset_progress")
        with self.assertRaises(ValueError):
            self.manager.player_command({"action":"progress","player":state["active"],"generation":state["generation"],"progress":state["progress"]})
        self.assertEqual(self.manager.player_snapshot()["progress"]["completed"],[])

    def test_export_is_allowlisted_and_restore_requires_fresh_center(self):
        backup=self.command("export")["backup"]
        self.assertEqual(set(backup),{"format","version","name","thresholds"})
        backup["thresholds"]={"thumb":{"on":.7,"off":.4}}
        self.command("restore",backup=backup)
        self.assertTrue(self.manager.needs_center())
        self.assertEqual(TuningManager(self.path).saved,backup["thresholds"])
        self.manager.begin_center()
        self.manager.finish_center()
        self.assertFalse(TuningManager(self.path).needs_center())

    def test_calibration_for_a_previous_player_does_not_unlock_new_player(self):
        self.command("create",name="Alex")
        self.manager.begin_center()
        self.command("select",id="default")
        self.manager.finish_center()
        self.assertTrue(self.manager.needs_center())

    def test_bad_imports_and_failed_writes_leave_file_and_memory_unchanged(self):
        original=self.path.read_bytes()
        backup=self.command("export")["backup"]
        for bad in (dict(backup,token="private"),dict(backup,calibration={}),dict(backup,thresholds={"index":{"on":float('nan'),"off":.1}}),{}):
            with self.assertRaises(ValueError):self.command("restore",backup=bad)
        with patch('powerglove_vision.game_registry.atomic_write',side_effect=OSError):
            with self.assertRaises(OSError):self.command("create",name="Unwritten")
        self.assertEqual(self.path.read_bytes(),original)
        self.assertEqual(len(self.manager.player_snapshot()["players"]),1)

    def test_tuning_lease_blocks_switching_and_restoration(self):
        self.manager.command({"action":"begin","session":"test-session"})
        with self.assertRaises(ValueError):self.command("create",name="Alex")
        self.assertEqual(self.command("read")["active"],"default")

    def test_player_limit_and_invalid_progress(self):
        for n in range(11):self.command("create",name="Player "+str(n))
        with self.assertRaises(ValueError):self.command("create",name="Overflow")
        for value in ({"course":1,"completed":[16],"lesson":0},{"course":True,"completed":[],"lesson":0},{"course":1,"completed":[True],"lesson":0}):
            with self.assertRaises(ValueError):self.command("progress",progress=value)

    def test_corruption_is_not_silently_overwritten_by_progress(self):
        self.path.write_text('{broken')
        self.manager=TuningManager(self.path)
        self.assertIsNotNone(self.manager.player_snapshot()["error"])
        with self.assertRaises(ValueError):self.command("progress",progress={"course":1,"completed":[],"lesson":0})
        self.assertEqual(self.path.read_text(),'{broken')


if __name__ == '__main__':
    unittest.main()
