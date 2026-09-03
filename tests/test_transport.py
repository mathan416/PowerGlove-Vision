# Copyright (c) 2026 Iain Bennett
import unittest
from socket import gaierror
from unittest.mock import Mock, patch

from powerglove_vision.model import ControllerState
from powerglove_vision.transport import UdpSender, decode_state, encode_state


class TransportTests(unittest.TestCase):
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
