# Project: PowerGlove Vision
# File: tests/test_transport.py
# Purpose: Verify controller packet protocol validation and sender recovery from network failures.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify controller packet protocol validation and sender recovery from network failures."""

import unittest
from socket import gaierror
from unittest.mock import Mock, patch

from powerglove_vision.model import ControllerState
from powerglove_vision.transport import UdpSender, decode_state, encode_state


class TransportTests(unittest.TestCase):
    def setUp(self):
        resolver = patch("powerglove_vision.transport.resolve_ipv4", return_value="192.0.2.1")
        resolver.start()
        self.addCleanup(resolver.stop)

    @patch("powerglove_vision.transport.resolve_ipv4")
    @patch("powerglove_vision.transport.socket.socket")
    def test_blank_destination_never_resolves_or_sends(self, socket_factory, resolver):
        """Local practice cannot accidentally send to an implicit network destination."""
        sender = UdpSender("", 55355, "secret")
        self.assertFalse(sender.send(ControllerState.released(1, 1.0, "off", False)))
        resolver.assert_not_called()
        socket_factory.return_value.sendto.assert_not_called()
        self.assertIn("Connection", sender.last_error)

    def test_round_trip(self):
        state = ControllerState.released(7, 1.5, "bad_street_brawler", True)
        decoded = decode_state(encode_state(state, "secret", "session-one"))
        self.assertEqual(decoded["sequence"], 7)
        self.assertEqual(decoded["token"], "secret")
        self.assertEqual(decoded["protocol"], "powerglove-vision/1")
        self.assertEqual(decoded["session"], "session-one")

    def test_wrong_protocol_rejected(self):
        with self.assertRaises(ValueError):
            decode_state(b'{"protocol":"other"}')

    @patch("powerglove_vision.transport.socket.socket")
    def test_temporary_name_failure_does_not_stop_sender(self, socket_factory):
        udp_socket = Mock()
        udp_socket.sendto.side_effect = gaierror(-2, "Name or service not known")
        socket_factory.return_value = udp_socket
        sender = UdpSender("retropieconsole.local", 55355, "secret")
        state = ControllerState.released(1, 1.0, "bad_street_brawler", True)

        self.assertFalse(sender.send(state))
        self.assertIn("Name or service not known", sender.last_error)
        self.assertFalse(sender.send(state))
        udp_socket.sendto.assert_called_once()

    @patch("powerglove_vision.transport.socket.socket")
    def test_successful_send_reports_receiver_available(self, socket_factory):
        sender = UdpSender("retropieconsole.local", 55355, "secret")
        state = ControllerState.released(1, 1.0, "bad_street_brawler", True)

        self.assertTrue(sender.send(state))
        self.assertIsNone(sender.last_error)


if __name__ == "__main__":
    unittest.main()
