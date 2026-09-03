# Project: PowerGlove Vision
# File: tests/test_control_server.py
# Purpose: Verify dashboard configuration, pairing safeguards, controller state, and guarded shutdown behavior.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-03 - Verified atomic publication of host shutdown requests.
#   2026-09-03 - Verified the bundled Help library, Markdown reader, and assets.
#   2026-09-03 - Verified dynamic UNO Q and RetroPie cabinet details.
#   2026-09-03 - Verified public PDF links, routes, and allowlisting.
#   2026-09-03 - Verified Dashboard profile switching and healthy idle status.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify dashboard configuration, pairing safeguards, controller state, and guarded shutdown behavior."""

import json
import http.client
import os
import ssl
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from powerglove_vision.control_server import (
    DASHBOARD, LEARN, LOGO_PATH, SETUP, ControlState, help_document_page,
    help_index_page, start_control_server,
)
from powerglove_vision.debug_server import SharedDebugState
from powerglove_vision.help_content import guide_pdf, help_asset, render_markdown
from powerglove_vision.help_content import cabinet_reference_content, request_browser_address
from powerglove_vision.vision_app import _base_status


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

    def test_help_is_in_the_primary_navigation(self):
        for page in (DASHBOARD, LEARN, SETUP, help_index_page()):
            self.assertIn(b"href=/help>Help", page)

    def test_help_index_lists_the_public_guides(self):
        page = help_index_page()
        self.assertIn(b"Help, without leaving the glove", page)
        self.assertIn(b"/help/gameplay", page)
        self.assertIn(b"/help/installation", page)
        self.assertIn(b"/help/cabinet", page)
        self.assertIn(b"This cabinet", page)
        self.assertNotIn(b"cheatsheet", page.lower())
        self.assertIn(b"/help-pdf/overview.pdf", page)
        self.assertIsNotNone(help_document_page("field-guide"))

    def test_cabinet_reference_uses_request_address_and_public_config(self):
        body, title = cabinet_reference_content("10.0.2.105:8088", self.state.public_config())
        self.assertEqual(title, "This cabinet")
        self.assertIn("http://10.0.2.105:8088/help", body)
        self.assertIn("https://10.0.2.105:8443/setup", body)
        self.assertIn("retropieconsole.local", body)
        self.assertIn("55355", body)
        self.assertNotIn("private-token", body)

    def test_cabinet_reference_preserves_local_names_and_rejects_bad_hosts(self):
        self.assertEqual(request_browser_address("arduiain.local:8088"), "arduiain.local")
        self.assertEqual(request_browser_address("bad host:8088"), "UNO-Q-NAME.local")

    def test_help_document_renders_markdown_with_contents_and_images(self):
        page = help_document_page("gameplay")
        self.assertIsNotNone(page)
        assert page is not None
        self.assertIn(b"Play with Power Glove Vision", page)
        self.assertIn(b"On this page", page)
        self.assertIn(b"/help-assets/gestures/actions/whole-hand-movement.png", page)
        self.assertIn(b"/help-assets/gestures/actions/v-sign.png", page)
        self.assertIn(b"/help-assets/gestures/actions/thumbs-up.png", page)
        self.assertGreaterEqual(page.count(b"<img loading=lazy"), 46)
        self.assertIn(b"/help/gameplay.md", page)
        self.assertIn(b"/help-pdf/gameplay.pdf", page)

    def test_help_renderer_escapes_html_and_unsafe_links(self):
        rendered, _headings = render_markdown("# Safe\n\n<script>alert(1)</script>\n\n[bad](javascript:alert(1))")
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("javascript:", rendered)
        self.assertIn("href='#'", rendered)

        table, _headings = render_markdown(
            '| Pose |\n| --- |\n| <img src="images/gestures/actions/v-sign.png" alt="V sign" width="72"> |'
        )
        self.assertIn("<img loading=lazy", table)
        self.assertIn("/help-assets/gestures/actions/v-sign.png", table)

        unsafe_table, _headings = render_markdown(
            '| Pose |\n| --- |\n| <img src="images/gestures/actions/v-sign.png" alt="V sign" width="72" onerror="alert(1)"> |'
        )
        self.assertNotIn("<img loading=lazy", unsafe_table)
        self.assertIn("&lt;img", unsafe_table)

    def test_help_assets_are_limited_to_documentation_images(self):
        asset = help_asset("gestures/directional-movement.png")
        self.assertIsNotNone(asset)
        assert asset is not None
        self.assertEqual(asset[1], "image/png")
        self.assertIsNone(help_asset("../../data/device.json"))

    def test_help_pdfs_are_allowlisted_and_exclude_the_cabinet_reference(self):
        document = guide_pdf("gameplay")
        self.assertIsNotNone(document)
        assert document is not None
        self.assertTrue(document[0].startswith(b"%PDF-"))
        self.assertEqual(document[1], "PowerGlove-Vision-Gameplay-Guide.pdf")
        self.assertIsNone(guide_pdf("quick-reference"))
        self.assertIsNone(guide_pdf("../../data/device"))

    def test_help_routes_serve_html_markdown_and_images(self):
        servers, _state = start_control_server(self.path, "127.0.0.1", 0, 0)
        try:
            port = servers.servers[0].server_address[1]
            for path, expected_type in (
                ("/help", "text/html"),
                ("/help/cabinet", "text/html"),
                ("/help/gameplay", "text/html"),
                ("/help/gameplay.md", "text/markdown"),
                ("/help-pdf/gameplay.pdf", "application/pdf"),
                ("/help-assets/gestures/directional-movement.png", "image/png"),
            ):
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                connection.request("GET", path)
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 200, path)
                self.assertTrue(response.getheader("Content-Type").startswith(expected_type), path)
                connection.close()
        finally:
            servers.shutdown()

    def test_learn_page_is_offline_practice_mode(self):
        self.assertIn(b"Practice gesture recognition without a RetroPie connection", LEARN)
        self.assertIn(b"/api/controller", LEARN)
        self.assertIn(b"enabled:false", LEARN)
        self.assertIn(b"Lesson 1 of 10", LEARN)

    def test_password_pairing_requires_certificate_comparison(self):
        self.assertIn(b"browser certificate fingerprint", SETUP)
        self.assertIn(b"pair-password').disabled=true", SETUP)
        self.assertIn(b"verified').checked", SETUP)

    def test_one_time_code_pairing_is_an_advanced_option(self):
        self.assertIn(b"Advanced: pair without a RetroPie password", SETUP)
        self.assertIn(b"Prepare one-time code", SETUP)

    def test_controller_connection_starts_disarmed_every_launch(self):
        self.assertFalse(self.state.controller_enabled())
        self.assertFalse(self.state.snapshot()["controller_enabled"])
        self.assertFalse(self.state.public_config()["controller_enabled"])

        self.state.set_controller_enabled(True)
        self.assertTrue(self.state.snapshot()["controller_enabled"])
        self.assertTrue(self.state.public_config()["controller_enabled"])

        restarted = ControlState(self.path)
        self.assertFalse(restarted.controller_enabled())

    def test_shutdown_controls_are_on_dashboard_and_setup(self):
        for page in (DASHBOARD, SETUP):
            self.assertIn(b"Shutdown system", page)
            self.assertIn(b"/api/system/shutdown", page)
            self.assertIn(b"restore or cycle power", page.lower())

    def test_runtime_profile_selector_is_dashboard_only(self):
        self.assertIn(b"id=profile-selector", DASHBOARD)
        self.assertIn(b"Gestures off", DASHBOARD)
        self.assertIn(b"/api/profile", DASHBOARD)
        self.assertNotIn(b"/api/profile", SETUP)

    def test_runtime_profile_route_rejects_unknown_profiles(self):
        servers, _state = start_control_server(self.path, "127.0.0.1", 0, 0)
        try:
            port = servers.servers[0].server_address[1]
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            connection.request(
                "POST", "/api/profile", json.dumps({"profile": "run-a-command"}),
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 400)
            connection.close()
        finally:
            servers.shutdown()

    def test_runtime_profile_route_forwards_valid_selection_to_worker(self):
        servers, _state = start_control_server(self.path, "127.0.0.1", 0, 0)
        try:
            port = servers.servers[0].server_address[1]
            reply = mock.MagicMock()
            reply.__enter__.return_value.read.return_value = b'{"active_profile":"program_h"}'
            with mock.patch("powerglove_vision.control_server.urllib.request.urlopen", return_value=reply) as open_worker:
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                connection.request(
                    "POST", "/api/profile", json.dumps({"profile": "program_h"}),
                    {"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                body = json.loads(response.read())
                self.assertEqual(response.status, 202)
                self.assertEqual(body["active_profile"], "program_h")
                forwarded = open_worker.call_args.args[0]
                self.assertEqual(forwarded.full_url, "http://127.0.0.1:8089/profile")
                self.assertEqual(json.loads(forwarded.data), {"profile": "program_h"})
                connection.close()
        finally:
            servers.shutdown()

    def test_shutdown_uses_only_the_fixed_host_trigger(self):
        marker = self.path.parent / ".shutdown-enabled"
        marker.touch()
        with mock.patch("powerglove_vision.control_server.os.replace", wraps=os.replace) as replace:
            self.state.schedule_system_shutdown(delay_seconds=0)
            trigger = self.path.parent / "shutdown-request"
            for _attempt in range(50):
                if trigger.exists():
                    break
                time.sleep(0.01)
        replace.assert_called_once()
        self.assertEqual(Path(replace.call_args[0][1]), trigger)
        self.assertEqual(trigger.read_text(), "shutdown\n")
        self.assertEqual(trigger.stat().st_mode & 0o777, 0o600)

    def test_shutdown_requires_installed_host_helper(self):
        with self.assertRaisesRegex(FileNotFoundError, "helper is not installed"):
            self.state.schedule_system_shutdown(delay_seconds=0)

    def test_shutdown_route_requires_confirmation_header(self):
        servers, state = start_control_server(self.path, "127.0.0.1", 0, 0)
        try:
            port = servers.servers[0].server_address[1]
            with mock.patch.object(state, "schedule_system_shutdown") as schedule:
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                body = json.dumps({"confirm": "SHUTDOWN"})
                connection.request("POST", "/api/system/shutdown", body, {"Content-Type": "application/json"})
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 403)
                schedule.assert_not_called()
                connection.close()

                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                connection.request("POST", "/api/system/shutdown", body, {
                    "Content-Type": "application/json", "X-PowerGlove-Action": "shutdown",
                    "Sec-Fetch-Site": "cross-site",
                })
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 403)
                schedule.assert_not_called()
                connection.close()

                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                connection.request("POST", "/api/system/shutdown", body, {
                    "Content-Type": "application/json", "X-PowerGlove-Action": "shutdown",
                })
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 202)
                schedule.assert_called_once_with()
                connection.close()
        finally:
            servers.shutdown()

    def test_worker_controller_request_is_consumed_once(self):
        shared = SharedDebugState()
        self.assertIsNone(shared.take_controller_request())
        shared.request_controller(True)
        self.assertTrue(shared.take_controller_request())
        self.assertIsNone(shared.take_controller_request())

    def test_worker_profile_request_is_consumed_once_and_normalizes_off(self):
        shared = SharedDebugState()
        self.assertIsNone(shared.take_profile_request())
        shared.request_profile(None, "Dashboard", "Manual selection")
        self.assertEqual(shared.take_profile_request(), (None, "Dashboard", "Manual selection"))
        self.assertIsNone(shared.take_profile_request())

    def test_gestures_off_reports_healthy_camera_idle_state(self):
        status = _base_status(None, "Manual selection", "dashboard", True)
        status["vision_state"] = "idle"
        self.assertEqual(status["active_profile"], "off")
        self.assertFalse(status["camera_available"])
        self.assertEqual(status["receiver_error"], "Gestures are paused")

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
