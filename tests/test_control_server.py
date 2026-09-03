# Copyright (c) 2026 Iain Bennett
import json
import tempfile
import unittest
from pathlib import Path

from powerglove_vision.control_server import DASHBOARD, LOGO_PATH, SETUP, ControlState
from powerglove_vision.debug_server import SharedDebugState


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

    def test_logo_is_available_to_both_web_pages(self):
        self.assertTrue(LOGO_PATH.is_file())
        logo_url = b"/assets/powerglove-vision-logo.png"
        self.assertIn(logo_url, DASHBOARD)
        self.assertIn(logo_url, SETUP)

    def test_controller_connection_starts_disarmed_every_launch(self):
        self.assertFalse(self.state.controller_enabled())
        self.assertFalse(self.state.snapshot()["controller_enabled"])
        self.assertFalse(self.state.public_config()["controller_enabled"])

        self.state.set_controller_enabled(True)
        self.assertTrue(self.state.snapshot()["controller_enabled"])
        self.assertTrue(self.state.public_config()["controller_enabled"])

        restarted = ControlState(self.path)
        self.assertFalse(restarted.controller_enabled())

    def test_worker_controller_request_is_consumed_once(self):
        shared = SharedDebugState()
        self.assertIsNone(shared.take_controller_request())
        shared.request_controller(True)
        self.assertTrue(shared.take_controller_request())
        self.assertIsNone(shared.take_controller_request())


if __name__ == "__main__":
    unittest.main()
