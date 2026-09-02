# Copyright (c) 2026 Iain Bennett. All rights reserved.
import json
import tempfile
import unittest
from pathlib import Path

from powerglove_vision.control_server import ControlState


class ControlStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "device.json"
        self.path.write_text(json.dumps({
            "receiver": "retropieconsole.local", "port": 55355,
            "token": "private-token", "profile": "bad_street_brawler",
            "glove_color": "none", "camera": "auto",
        }))
        self.state = ControlState(self.path)

    def tearDown(self):
        self.temporary.cleanup()

    def test_public_config_never_contains_token(self):
        public = self.state.public_config()
        self.assertNotIn("token", public)
        self.assertTrue(public["paired"])

    def test_save_preserves_token_and_updates_connection(self):
        self.state.save_config({
            "receiver": "arcade.local", "port": 55357,
            "profile": "program_i", "glove_color": "white", "camera": "2",
        })
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["token"], "private-token")
        self.assertEqual(saved["receiver"], "arcade.local")
        self.assertEqual(self.state.revision, 1)

    def test_invalid_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "supported gesture profile"):
            self.state.save_config({
                "receiver": "arcade.local", "port": 55355,
                "profile": "shell_command", "glove_color": "none", "camera": "auto",
            })


if __name__ == "__main__":
    unittest.main()
