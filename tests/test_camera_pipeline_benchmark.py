"""Check timestamp validity, newest driver-buffer selection, and safe release."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('camera_pipeline',
    Path(__file__).resolve().parents[1] / 'scripts/benchmark-camera-pipeline.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class CameraPipelineTests(unittest.TestCase):
    def test_driver_clock_must_be_monotonic_and_not_in_future(self):
        row = dict(driver_ns=1_000_000, flags=0x12001)
        self.assertEqual(bench.driver_age_ms(row, 4_000_000), 3)
        self.assertIsNone(bench.driver_age_ms(row, 999_999))
        for flags in (0, 0x4000, 0x6000):
            self.assertIsNone(bench.driver_age_ms(dict(row, flags=flags), 4_000_000))
        self.assertIsNone(bench.driver_age_ms(dict(row, driver_ns=0), 4_000_000))

    def test_returns_buffers_before_decode_and_uses_newest(self):
        camera = bench.RawCamera.__new__(bench.RawCamera)
        camera.fd, camera.running, camera.actual_buffers = 99, True, 2
        camera.maps, camera.rows, camera.errors = [b'old', b'new'], [], []
        camera.failed_reads = 0
        events = []
        class NP:
            uint8 = object()
            @staticmethod
            def frombuffer(data, dtype):
                return data
        class CV:
            IMREAD_COLOR = 1
            @staticmethod
            def imdecode(data, mode):
                events.append(('decode', data))
                return data
        camera.np, camera.cv2 = NP, CV
        next_index = iter((0, 1))
        def ioctl(fd, op, b):
            if op == bench.DQBUF:
                b.index = next(next_index)
                b.bytesused, b.sequence = 3, 100 + b.index
                b.flags, b.ts.sec = 0x2000, 1
            else:
                events.append(('return', b.index))
        with patch.object(bench.select, 'select', return_value=([99], [], [])), \
                patch.object(bench.fcntl, 'ioctl', side_effect=ioctl):
            ok, (image, row) = camera.read()
        self.assertTrue(ok)
        self.assertEqual(image, b'new')
        self.assertEqual(row['driver_sequence'], 101)
        self.assertEqual(row['drained'], 1)
        self.assertEqual(events, [('return', 0), ('return', 1), ('decode', b'new')])

    def test_histogram_summary_does_not_invent_empty_measurements(self):
        self.assertEqual(bench.stats([]), {'samples': 0})
        self.assertEqual(bench.stats([1, 2, 100])['p95'], 100)


if __name__ == '__main__':
    unittest.main()
