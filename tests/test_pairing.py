# Project: PowerGlove Vision
# File: tests/test_pairing.py
# Purpose: Verify pairing codes, certificate identity, TLS time bounds, SSH handling, and token permissions.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-03 - Kept mock-call inspection compatible with Python 3.7.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify pairing codes, certificate identity, TLS time bounds, SSH handling, and token permissions."""

import json
import tempfile
import threading
import socket
import time
import unittest
from pathlib import Path
from unittest import mock

from powerglove_vision.pairing import (
    certificate_code,
    certificate_identity,
    display_pairing_code,
    generate_certificate,
    install_token,
    normalize_pairing_code,
    pair_over_ssh,
    pair_with_code,
    serve_pairing,
)


class PairingTests(unittest.TestCase):
    def test_code_round_trip(self):
        displayed = display_pairing_code("ABCDEFGHIJ", "234567ABCD")
        self.assertEqual(displayed, "ABCDE-FGHIJ-23456-7ABCD")
        self.assertEqual(normalize_pairing_code(displayed.lower()), ("ABCDEFGHIJ", "234567ABCD"))

    def test_invalid_code_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "20"):
            normalize_pairing_code("123-456")

    def test_certificate_produces_stable_code(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            _certificate, _key, pem = generate_certificate(Path(temporary_name), "pairing-test")
            self.assertEqual(len(certificate_code(pem)), 10)
            self.assertEqual(certificate_code(pem), certificate_code(pem))
            self.assertRegex(certificate_identity(pem), r"^[0-9A-F]{7}$")

    def test_token_is_written_with_restricted_permissions(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            token_file = Path(temporary_name) / "token"
            install_token(token_file, "a-secure-controller-token")
            self.assertEqual(token_file.read_text(), "a-secure-controller-token\n")
            self.assertEqual(token_file.stat().st_mode & 0o777, 0o640)

    @mock.patch("powerglove_vision.pairing.subprocess.run")
    def test_password_pairing_uses_python_ssh_without_command_line_secrets(self, run):
        run.return_value.returncode = 0
        run.return_value.stderr = b""
        with tempfile.TemporaryDirectory() as temporary_name:
            pair_over_ssh(
                "retropie.local", "pi", "private-password", "paired-controller-token",
                Path(temporary_name) / "known_hosts", timeout=2,
            )
        positional, keywords = run.call_args
        command = positional[0]
        self.assertEqual(command[:3], ["uv", "run", "--no-project"])
        self.assertNotIn("ssh", command)
        self.assertNotIn("private-password", command)
        self.assertNotIn("paired-controller-token", command)
        payload = json.loads(keywords["input"])
        self.assertEqual(payload["password"], "private-password")
        self.assertEqual(payload["token"], "paired-controller-token")

    def test_one_time_code_pairs_over_pinned_https(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            token_file = Path(temporary_name) / "token"
            ready = threading.Event()
            details = {}
            paired = []

            def on_ready(code, port):
                details.update(code=code, port=port)
                ready.set()

            worker = threading.Thread(
                target=serve_pairing,
                args=("127.0.0.1", 0, token_file, 10, lambda: paired.append(True), on_ready),
                daemon=True,
            )
            worker.start()
            self.assertTrue(ready.wait(5))
            pair_with_code("127.0.0.1", details["port"], details["code"], "paired-controller-token")
            worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(token_file.read_text(), "paired-controller-token\n")
            self.assertEqual(paired, [True])

    def test_silent_tls_client_cannot_hold_pairing_past_deadline(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            ready = threading.Event()
            details = {}
            expired = []

            def run_server():
                try:
                    serve_pairing(
                        "127.0.0.1", 0, Path(temporary_name) / "token", 1,
                        lambda: None,
                        lambda _code, port: (details.update(port=port), ready.set()),
                    )
                except TimeoutError:
                    expired.append(True)

            worker = threading.Thread(target=run_server, daemon=True)
            worker.start()
            self.assertTrue(ready.wait(5))
            started = time.monotonic()
            stalled = socket.create_connection(("127.0.0.1", details["port"]), timeout=2)
            worker.join(3)
            stalled.close()
            self.assertFalse(worker.is_alive())
            self.assertEqual(expired, [True])
            self.assertLess(time.monotonic() - started, 2.5)


if __name__ == "__main__":
    unittest.main()
