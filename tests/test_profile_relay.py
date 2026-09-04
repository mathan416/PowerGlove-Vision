# Project: PowerGlove Vision
# File: tests/test_profile_relay.py
# Purpose: Verify bounded UDP relay exchanges and fail-open game-launch reporting.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Covered concurrent replies, invalid traffic, capacity expiry and hook failures.
# Full history: docs/CHANGELOG.md and Git history.

"""Exercise profile transport without hardware or private device settings."""

import contextlib
import importlib.util
import io
import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from powerglove_vision import retropie_hook
from powerglove_vision.profile_control import ProfileCommandServer, send_request

spec = importlib.util.spec_from_file_location("profile_relay", Path(__file__).resolve().parents[1] / "scripts/profile-relay.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RelayTests(unittest.TestCase):
    @contextlib.contextmanager
    def running_relay(self, upstream, **kwargs):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
            listener.bind(("127.0.0.1", 0))
            stopped = threading.Event()
            thread = threading.Thread(target=module.relay, args=(listener, upstream, stopped), kwargs=kwargs)
            thread.start()
            try:
                yield listener.getsockname()
            finally:
                stopped.set()
                thread.join(2)
                self.assertFalse(thread.is_alive())

    def test_concurrent_clients_get_only_their_reply(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as worker:
            worker.bind(("127.0.0.1", 0))
            worker.settimeout(1)
            with self.running_relay(worker.getsockname()) as address:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as a, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as b:
                    a.settimeout(1); b.settimeout(1)
                    a.sendto(b"first", address); b.sendto(b"second", address)
                    requests = [worker.recvfrom(4096), worker.recvfrom(4096)]
                    for data, peer in reversed(requests):
                        worker.sendto(data + b"-ack", peer)
                    self.assertEqual(a.recv(4096), b"first-ack")
                    self.assertEqual(b.recv(4096), b"second-ack")

    def test_oversize_dropped_and_capacity_recovers_after_expiry(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as worker, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            worker.bind(("127.0.0.1", 0)); worker.settimeout(0.1)
            with self.running_relay(worker.getsockname(), timeout=0.15, max_pending=1) as address:
                client.sendto(b"x" * 4097, address)
                with self.assertRaises(socket.timeout): worker.recvfrom(5000)
                client.sendto(b"expires", address)
                self.assertEqual(worker.recvfrom(4096)[0], b"expires")
                client.sendto(b"over-capacity", address)
                with self.assertRaises(socket.timeout): worker.recvfrom(5000)
                time.sleep(0.15)
                client.sendto(b"after-expiry", address)
                self.assertEqual(worker.recvfrom(4096)[0], b"after-expiry")

    def test_signed_exchange_reaches_real_profile_server(self):
        server = ProfileCommandServer("127.0.0.1", 0, "test-profile-token")
        result = {}
        try:
            with self.running_relay(server.socket.getsockname()) as address:
                def client():
                    result.update(send_request(address[0], address[1], "test-profile-token", "program_h", "nes", "Example.nes", 0.2))
                thread = threading.Thread(target=client); thread.start()
                deadline = time.monotonic() + 1
                request = None
                while request is None and time.monotonic() < deadline:
                    request = server.take(); time.sleep(0.005)
                self.assertIsNotNone(request)
                server.acknowledge(request, True, request.profile)
                thread.join(1)
                self.assertFalse(thread.is_alive())
                self.assertTrue(result["accepted"])
                self.assertEqual(result["profile"], "program_h")
        finally:
            server.close()


class HookTests(unittest.TestCase):
    def test_rejection_is_not_reported_as_acknowledged(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "launcher.json"
            settings.write_text(json.dumps({"uno_q": "example.local", "token_file": "unused"}))
            for ack in ({"accepted": False, "profile": None}, {"accepted": True, "profile": "program_b"}):
                output = io.StringIO()
                with patch("sys.argv", ["hook", "end", "--settings", str(settings)]), patch.object(retropie_hook, "read_token", return_value="test-profile-token"), patch.object(retropie_hook, "send_request", return_value=ack), contextlib.redirect_stdout(output):
                    self.assertEqual(retropie_hook.main(), 0)
                self.assertIn("rejected", output.getvalue())
                self.assertNotIn("acknowledged", output.getvalue())

    def test_missing_settings_does_not_fail_game_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("sys.argv", ["hook", "start", "--settings", str(Path(directory) / "missing")]), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(retropie_hook.main(), 0)
            self.assertIn("unavailable", output.getvalue())


class VisionControlTests(unittest.TestCase):
    def test_off_applies_during_blocked_camera_open_or_read(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from powerglove_vision import vision_app
        from powerglove_vision.profile_control import ProfileRequest

        for operation in ("open", "read"):
            blocked = threading.Event()
            release = threading.Event()
            finished = threading.Event()
            sent = []
            capture = MagicMock()
            tracker = MagicMock()
            def wait_for_release():
                blocked.set()
                release.wait(2)
                finished.set()
                return False, None
            capture.read.side_effect = wait_for_release
            def prepare(_args):
                if operation == "open":
                    wait_for_release()
                return MagicMock(), capture, tracker
            def take():
                if blocked.is_set() and not sent:
                    sent.append(True)
                    return ProfileRequest("off-test", None, "nes", "", ("127.0.0.1", 1))
                return None
            def update(state, **_kwargs):
                if sent and state.get("active_profile") == "off":
                    raise KeyboardInterrupt
            server = MagicMock(); server.take.side_effect = take
            shared = MagicMock()
            shared.take_profile_request.return_value = None
            shared.take_practice_request.return_value = None
            shared.take_controller_request.return_value = None
            shared.take_calibration_request.return_value = False
            shared.update_status.side_effect = update
            args = SimpleNamespace(profile="program_h", no_matrix=True, controller_enabled=False,
                                   token="test-profile-token", receiver="", port=55355,
                                   profile_listen="127.0.0.1", profile_port=55356,
                                   web_host="127.0.0.1", web_port=8089, config=None)
            try:
                with patch.object(vision_app, "build_parser") as parser, patch.object(vision_app, "load_calibration", return_value=None), patch.object(vision_app, "UnoQMatrix"), patch.object(vision_app, "UdpSender"), patch.object(vision_app, "ProfileCommandServer", return_value=server), patch.object(vision_app, "SharedDebugState", return_value=shared), patch.object(vision_app, "start_debug_server"), patch.object(vision_app.signal, "signal"), patch.object(vision_app, "_prepare_vision", side_effect=prepare):
                    parser.return_value.parse_args.return_value = args
                    started = time.monotonic()
                    self.assertEqual(vision_app.main(), 0)
                    self.assertLess(time.monotonic() - started, 1)
                    self.assertTrue(sent)
                    self.assertFalse(release.is_set())
            finally:
                release.set()
                self.assertTrue(finished.wait(1))
