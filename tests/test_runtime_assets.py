# Copyright (c) 2026 Iain Bennett
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from powerglove_vision.runtime_assets import ensure_hand_landmarker_model


class RuntimeAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.data = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_downloads_and_caches_verified_model(self) -> None:
        content = b"verified model content"
        expected = hashlib.sha256(content).hexdigest()
        calls = []

        def open_model(url, timeout):
            calls.append((url, timeout))
            return io.BytesIO(content)

        path = ensure_hand_landmarker_model(
            self.data, url="https://example.test/model", expected_sha256=expected, opener=open_model
        )
        self.assertEqual(path.read_bytes(), content)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(calls, [("https://example.test/model", 60)])

        def should_not_download(_url, _timeout):
            raise AssertionError("verified cached model should be reused")

        self.assertEqual(
            ensure_hand_landmarker_model(
                self.data, expected_sha256=expected, opener=should_not_download
            ),
            path,
        )

    def test_checksum_failure_does_not_install_download(self) -> None:
        def open_bad_model(_url, timeout):
            self.assertEqual(timeout, 60)
            return io.BytesIO(b"tampered")

        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            ensure_hand_landmarker_model(
                self.data, expected_sha256=hashlib.sha256(b"expected").hexdigest(),
                opener=open_bad_model,
            )
        self.assertFalse((self.data / "models" / "hand_landmarker.task").exists())
        self.assertEqual(list((self.data / "models").glob("*.download")), [])


if __name__ == "__main__":
    unittest.main()
