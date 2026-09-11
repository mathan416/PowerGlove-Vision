# Project: PowerGlove Vision
# File: tests/test_camera_pipeline_benchmark.py
# Purpose: Verify the isolated camera benchmark's timing and buffer safety.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Covered scheduler evidence and capture-isolation lane selection.
#   2026-09-09 - Covered aggregate sustained-load stall evidence.
#   2026-09-06 - Added camera pipeline benchmark regression coverage.
# Full history: docs/CHANGELOG.md and Git history.

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
    def test_counter_and_pressure_deltas_keep_only_cumulative_values(self):
        self.assertEqual(
            bench.counter_delta({'runtime_ns': 10, 'wait': 3},
                                {'runtime_ns': 18, 'wait': 7}),
            {'runtime_ns': 8, 'wait': 4},
        )
        before = {'some': {'avg10': 2.0, 'total': 100}}
        after = {'some': {'avg10': 8.0, 'total': 145}}
        self.assertEqual(bench.pressure_delta(before, after),
                         {'some': {'total_us': 45.0}})
        self.assertIsNone(bench.counter_delta(None, {'runtime_ns': 1}))

    def test_lane_matrix_broadcasts_one_selector_and_rejects_ambiguity(self):
        self.assertEqual(
            bench.lane_matrix((2, 2, 2), ('thread', 'process', 'thread')),
            [(2, 'thread'), (2, 'process'), (2, 'thread')],
        )
        self.assertEqual(
            bench.lane_matrix((1, 2, 1), ('thread',)),
            [(1, 'thread'), (2, 'thread'), (1, 'thread')],
        )
        with self.assertRaises(ValueError):
            bench.lane_matrix((1, 2), ('thread', 'process', 'thread'))

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

    def test_lane_summary_separates_capture_schedule_and_inference_stalls(self):
        capture = [
            dict(driver_ns=1_000_000_000, flags=0x2000, dequeued_ns=1_002_000_000,
                 requeued_ns=1_003_000_000, decoded_ns=1_005_000_000,
                 driver_sequence=10),
            dict(driver_ns=1_033_000_000, flags=0x2000, dequeued_ns=1_052_000_000,
                 requeued_ns=1_053_000_000, decoded_ns=1_057_000_000,
                 driver_sequence=12),
        ]
        samples = [
            dict(capture[0], start_ns=1_006_000_000, end_ns=1_040_000_000,
                 skipped_application_frames=0, driver_to_recognition_ms=6,
                 driver_to_coordinates_ms=40, preprocessing_ms=1, graph_ms=30,
                 landmark_conversion_and_wrapper_ms=2, gesture_and_axes_ms=1),
            dict(capture[1], start_ns=1_108_000_000, end_ns=1_145_000_000,
                 skipped_application_frames=2, driver_to_recognition_ms=74,
                 driver_to_coordinates_ms=112, preprocessing_ms=1, graph_ms=34,
                 landmark_conversion_and_wrapper_ms=2, gesture_and_axes_ms=1),
        ]
        summary = bench.lane_summary(dict(
            buffers=2, capture_isolation='process', samples=samples,
            capture=capture, errors=[], failed_reads=0,
            scheduling={'capture_task': {'runqueue_wait_ns': 7}},
        ))
        self.assertEqual(summary['driver_nominal_sequence_step'], 2)
        self.assertEqual(summary['driver_sequence_discontinuities'], 0)
        self.assertEqual(summary['driver_sequence_nonmodal_steps'], 0)
        self.assertEqual(summary['driver_sequence_forward_skips'], 0)
        self.assertEqual(summary['application_skipped_frames'], 2)
        self.assertEqual(summary['decoded_to_recognition_start_ms']['max'], 51)
        self.assertEqual(summary['stalls']['recognition_start_interval']['over_100_ms'], 1)
        self.assertEqual(summary['graph_ms']['p95'], 34)
        self.assertEqual(summary['tail_events_total'], 1)
        self.assertEqual(summary['tail_events'][0]['boundary'], 'recognition')
        self.assertEqual(summary['tail_events'][0]['driver_sequence'], 12)
        self.assertEqual(summary['tracking_paths'], {'unavailable': 2})
        self.assertEqual(summary['tracking_path_graph_ms']['unavailable']['p95'], 34)
        self.assertEqual(summary['capture_isolation'], 'process')
        self.assertEqual(summary['scheduling']['capture_task']['runqueue_wait_ns'], 7)

    def test_smaller_sequence_step_is_more_coverage_not_a_forward_skip(self):
        capture = []
        for index, sequence in enumerate((10, 12, 13, 15, 19)):
            at = 1_000_000_000 + index * 33_000_000
            capture.append(dict(driver_ns=at, flags=0x2000,
                                dequeued_ns=at + 1_000_000,
                                requeued_ns=at + 2_000_000,
                                decoded_ns=at + 3_000_000,
                                driver_sequence=sequence))
        summary = bench.lane_summary(dict(
            buffers=2, samples=[], capture=capture, errors=[], failed_reads=0,
        ))
        self.assertEqual(summary['driver_nominal_sequence_step'], 2)
        self.assertEqual(summary['driver_sequence_nonmodal_steps'], 2)
        self.assertEqual(summary['driver_sequence_forward_skips'], 2)
        self.assertEqual(summary['driver_sequence_discontinuities'], 2)

    def test_lane_summary_attributes_detector_cost_and_lead_up(self):
        capture = [
            dict(driver_ns=1_000_000_000, flags=0x2000,
                 dequeued_ns=1_002_000_000, requeued_ns=1_003_000_000,
                 decoded_ns=1_008_000_000, driver_sequence=1),
            dict(driver_ns=1_033_000_000, flags=0x2000,
                 dequeued_ns=1_035_000_000, requeued_ns=1_036_000_000,
                 decoded_ns=1_041_000_000, driver_sequence=2),
        ]
        samples = [
            dict(capture[0], start_ns=1_009_000_000, end_ns=1_049_000_000,
                 graph_ms=35.0, detected=True,
                 tracking_path='landmark_continuation',
                 palm_detector_invoked=False, palm_detection_count=None,
                 preprocessing_ms=1.0,
                 landmark_conversion_and_wrapper_ms=2.0,
                 gesture_and_axes_ms=1.0, skipped_application_frames=0,
                 driver_to_recognition_ms=9.0,
                 driver_to_coordinates_ms=49.0),
            dict(capture[1], start_ns=1_076_000_000, end_ns=1_176_000_000,
                 graph_ms=95.0, detected=True,
                 tracking_path='palm_reacquisition',
                 palm_detector_invoked=True, palm_detection_count=1,
                 preprocessing_ms=1.0,
                 landmark_conversion_and_wrapper_ms=2.0,
                 gesture_and_axes_ms=1.0, skipped_application_frames=1,
                 driver_to_recognition_ms=43.0,
                 driver_to_coordinates_ms=143.0),
        ]
        summary = bench.lane_summary(dict(
            buffers=2, capture_isolation='thread', samples=samples,
            capture=capture, failed_reads=0, errors=[], scheduling={},
        ))
        context = summary['detector_context']
        self.assertEqual(context['frames'], 1)
        self.assertEqual(context['paths'], {'palm_reacquisition': 1})
        self.assertEqual(
            context['predecessor_paths'], {'landmark_continuation': 1}
        )
        self.assertEqual(context['previous_graph_ms']['p50'], 35.0)
        self.assertEqual(context['recognition_interval_ms']['p50'], 67.0)
        self.assertEqual(
            context['decoded_to_recognition_start_ms']['p50'], 35.0
        )
        self.assertEqual(context['graph_ms']['p50'], 95.0)
        self.assertEqual(context['skipped_application_frames']['p50'], 1)


if __name__ == '__main__':
    unittest.main()
