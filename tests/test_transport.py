# Copyright (c) 2026 Iain Bennett
import unittest

from powerglove_vision.model import ControllerState
from powerglove_vision.transport import decode_state, encode_state


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


if __name__ == "__main__":
    unittest.main()
