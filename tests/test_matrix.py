import unittest

from powerglove_vision.matrix import MatrixStatus, UnoQMatrix


class MatrixTests(unittest.TestCase):
    def test_status_is_sent_over_bridge(self):
        calls = []
        matrix = UnoQMatrix(call=lambda *args: calls.append(args))
        self.assertTrue(matrix.set_status(MatrixStatus.LOADING))
        self.assertTrue(matrix.set_status(MatrixStatus.READY))
        self.assertEqual(
            calls,
            [
                ("set_powerglove_status", int(MatrixStatus.LOADING)),
                ("set_powerglove_status", int(MatrixStatus.READY)),
            ],
        )

    def test_duplicate_status_is_not_resent(self):
        calls = []
        matrix = UnoQMatrix(call=lambda *args: calls.append(args))
        matrix.set_status(MatrixStatus.TRACKING)
        matrix.set_status(MatrixStatus.TRACKING)
        self.assertEqual(len(calls), 1)

    def test_bridge_failure_does_not_crash_vision(self):
        def fail(*_args):
            raise RuntimeError("not ready")

        matrix = UnoQMatrix(call=fail)
        self.assertFalse(matrix.set_status(MatrixStatus.LOADING))
        self.assertEqual(matrix.last_error, "not ready")

    def test_profile_codes_are_sent_over_bridge(self):
        calls = []
        matrix = UnoQMatrix(call=lambda *args: calls.append(args))
        matrix.set_profile("program_c")
        matrix.set_profile("bad_street_brawler")
        matrix.set_profile("super_glove_ball")
        matrix.set_profile(None)
        self.assertEqual(calls, [
            ("set_powerglove_profile", 3),
            ("set_powerglove_profile", 10),
            ("set_powerglove_profile", 11),
            ("set_powerglove_profile", 0),
        ])


if __name__ == "__main__":
    unittest.main()
