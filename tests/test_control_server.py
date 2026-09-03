# Copyright (c) 2026 Iain Bennett
import json
import http.client
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from powerglove_vision.control_server import DASHBOARD, LEARN, LOGO_PATH, SETUP, ControlState, start_control_server
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
        self.assertIn(logo_url, LEARN)
        self.assertIn(logo_url, SETUP)

    def test_learn_page_is_offline_practice_mode(self):
        self.assertIn(b"Practice gesture recognition without a RetroPie connection", LEARN)
        self.assertIn(b"/api/controller", LEARN)
        self.assertIn(b"enabled:false", LEARN)
        self.assertIn(b"Lesson 1 of 10", LEARN)

    def test_password_pairing_requires_certificate_comparison(self):
        self.assertIn(b"browser certificate fingerprint", SETUP)
        self.assertIn(b"pair-password').disabled=true", SETUP)
        self.assertIn(b"verified').checked", SETUP)

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

    def test_pairing_credentials_are_rejected_over_plain_http(self):
        servers, _state = start_control_server(self.path, "127.0.0.1", 0, 0)
        try:
            port = servers.servers[0].server_address[1]
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            body = json.dumps({"host": "retropie.local", "username": "pi", "password": "secret"})
            connection.request("POST", "/api/pair/ssh", body, {"Content-Type": "application/json"})
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 426)
            connection.close()
        finally:
            servers.shutdown()

    def test_pairing_requires_a_physical_single_use_pin(self):
        displayed = []
        state = ControlState(self.path, lambda identity, pin: displayed.append((identity, pin)))
        state.configure_pairing_identity("1A2B3C4")
        result = state.begin_pairing("retropieconsole.local", "code")
        self.assertEqual(result["certificate_id"], "1A2B3C4")
        self.assertEqual(displayed[0][0], "1A2B3C4")
        self.assertRegex(displayed[0][1], r"^\d{6}$")

        wrong_pin = "999999" if displayed[0][1] != "999999" else "000000"
        with self.assertRaisesRegex(ValueError, "rejected"):
            state.authorize_pairing("retropieconsole.local", "code", wrong_pin)
        state.authorize_pairing("retropieconsole.local", "code", displayed[0][1])
        with self.assertRaisesRegex(ValueError, "expired"):
            state.authorize_pairing("retropieconsole.local", "code", displayed[0][1])

    def test_https_pairing_route_requires_matrix_pin_before_token_export(self):
        displayed = []
        servers, _state = start_control_server(
            self.path, "127.0.0.1", 0, 0,
            pairing_display=lambda identity, pin: displayed.append((identity, pin)),
        )
        try:
            secure_port = servers.servers[1].server_address[1]
            context = ssl._create_unverified_context()

            unauthorized = json.dumps({
                "host": "attacker.local", "code": "ABCDE-FGHIJ-23456-7ABCD",
                "device_code": "000000",
            })
            with mock.patch("powerglove_vision.control_server.pair_with_code") as send_token:
                connection = http.client.HTTPSConnection("127.0.0.1", secure_port, context=context)
                connection.request("POST", "/api/pair/code", unauthorized, {"Content-Type": "application/json"})
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 400)
                send_token.assert_not_called()
                connection.close()

            connection = http.client.HTTPSConnection("127.0.0.1", secure_port, context=context)
            begin = json.dumps({"host": "retropie.local", "method": "code"})
            connection.request("POST", "/api/pair/begin", begin, {"Content-Type": "application/json"})
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 200)
            connection.close()

            payload = json.dumps({
                "host": "retropie.local", "code": "ABCDE-FGHIJ-23456-7ABCD",
                "device_code": displayed[0][1],
            })
            with mock.patch("powerglove_vision.control_server.pair_with_code") as send_token:
                connection = http.client.HTTPSConnection("127.0.0.1", secure_port, context=context)
                connection.request("POST", "/api/pair/code", payload, {"Content-Type": "application/json"})
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 200)
                send_token.assert_called_once_with(
                    "retropie.local", 55357, "ABCDE-FGHIJ-23456-7ABCD", "private-token"
                )
                connection.close()
        finally:
            servers.shutdown()


if __name__ == "__main__":
    unittest.main()
