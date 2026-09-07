#!/usr/bin/env python3
"""Opt-in Linux camera/recognition experiment; never sends controller output.

Run only with the normal camera worker stopped, using its Python environment.
The caller owns stopping/restoring supervision. No camera controls, player files,
or installed sources are changed. Images stay in RAM; only numeric evidence is
exported after capture stops. Native profiler files are temporary and private.
"""

from __future__ import annotations

import argparse
import ctypes as C
import errno
import fcntl
import json
import math
import mmap
import os
from pathlib import Path
import select
import sys
import tempfile
import time


class Timeval(C.Structure):
    _fields_ = [('sec', C.c_long), ('usec', C.c_long)]


class Timecode(C.Structure):
    _fields_ = [('type', C.c_uint32), ('flags', C.c_uint32), ('rest', C.c_ubyte * 8)]


class BufferMemory(C.Union):
    _fields_ = [('offset', C.c_uint32), ('ptr', C.c_ulong)]


class Buffer(C.Structure):
    _fields_ = [('index', C.c_uint32), ('type', C.c_uint32),
                ('bytesused', C.c_uint32), ('flags', C.c_uint32),
                ('field', C.c_uint32), ('ts', Timeval), ('tc', Timecode),
                ('sequence', C.c_uint32), ('memory', C.c_uint32),
                ('m', BufferMemory), ('length', C.c_uint32),
                ('reserved2', C.c_uint32), ('request_fd', C.c_int32)]


class RequestBuffers(C.Structure):
    _fields_ = [('count', C.c_uint32), ('type', C.c_uint32),
                ('memory', C.c_uint32), ('capabilities', C.c_uint32),
                ('flags', C.c_uint32)]


REQ, QUERY, QBUF, DQBUF = 0xc0145608, 0xc0585609, 0xc058560f, 0xc0585611
STREAMON, STREAMOFF = 0x40045612, 0x40045613


def stats(values):
    values = sorted(values)
    if not values:
        return {'samples': 0}
    return dict(samples=len(values), mean=sum(values) / len(values), min=values[0],
                p50=values[math.ceil(len(values) * .5) - 1],
                p95=values[math.ceil(len(values) * .95) - 1], max=values[-1])


def driver_age_ms(row, at_ns):
    """Reject unknown/copied clocks, zero timestamps, and impossible future times."""
    if row['flags'] & 0xe000 != 0x2000 or row['driver_ns'] <= 0:
        return None
    delta = at_ns - row['driver_ns']
    return delta / 1e6 if delta >= 0 else None


class RawCamera:
    """Copy newest available MJPEG buffer, return it, then decode outside ownership."""

    def __init__(self, path, buffers, cv2, np):
        if sys.platform != 'linux' or C.sizeof(Buffer) != 88 or C.sizeof(RequestBuffers) != 20:
            raise RuntimeError('This diagnostic requires the Linux 64-bit V4L2 ABI')
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        self.maps, self.rows, self.errors = [], [], []
        self.failed_reads = 0
        self.running = False
        self.cv2, self.np = cv2, np
        try:
            # Read only: validate rather than silently changing the camera format.
            fmt = bytearray(208)
            import struct
            struct.pack_into('I', fmt, 0, 1)
            fcntl.ioctl(self.fd, 0xc0d05604, fmt)
            width, height, fourcc = struct.unpack_from('III', fmt, 8)
            if (width, height, fourcc) != (640, 480, int.from_bytes(b'MJPG', 'little')):
                raise RuntimeError('Expected existing MJPG 640x480 camera configuration')
            req = RequestBuffers(buffers, 1, 1, 0, 0)
            fcntl.ioctl(self.fd, REQ, req)
            self.actual_buffers = req.count
            if req.count != buffers:
                raise RuntimeError(f'Driver granted {req.count} buffers, requested {buffers}')
            for index in range(req.count):
                b = self.buffer()
                b.index = index
                fcntl.ioctl(self.fd, QUERY, b)
                self.maps.append(mmap.mmap(self.fd, b.length, flags=mmap.MAP_SHARED,
                    prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=b.m.offset))
                fcntl.ioctl(self.fd, QBUF, b)
            fcntl.ioctl(self.fd, STREAMON, C.c_uint32(1))
            self.running = True
        except BaseException:
            self.close()
            raise

    @staticmethod
    def buffer():
        b = Buffer()
        b.type, b.memory = 1, 1
        return b

    def read(self):
        try:
            if not self.running or not select.select([self.fd], [], [], 2)[0]:
                self.failed_reads += 1
                return False, None
            b = self.buffer()
            fcntl.ioctl(self.fd, DQBUF, b)
            dropped = 0
            # Bound the drain: at most the originally available driver buffers.
            for _ in range(self.actual_buffers - 1):
                newer = self.buffer()
                try:
                    fcntl.ioctl(self.fd, DQBUF, newer)
                except OSError as exc:
                    if exc.errno == errno.EAGAIN:
                        break
                    raise
                fcntl.ioctl(self.fd, QBUF, b)
                b = newer
                dropped += 1
            dequeued = time.monotonic_ns()
            row = dict(driver_ns=b.ts.sec * 1_000_000_000 + b.ts.usec * 1000,
                       driver_sequence=b.sequence, flags=b.flags,
                       dequeued_ns=dequeued, drained=dropped)
            try:
                if b.bytesused <= 0 or b.bytesused > len(self.maps[b.index]):
                    raise RuntimeError('Invalid camera payload size')
                compressed = self.maps[b.index][:b.bytesused]
            finally:
                fcntl.ioctl(self.fd, QBUF, b)
            row['requeued_ns'] = time.monotonic_ns()
            image = self.cv2.imdecode(self.np.frombuffer(compressed, dtype=self.np.uint8),
                                      self.cv2.IMREAD_COLOR)
            row['decoded_ns'] = time.monotonic_ns()
            if image is None or row['flags'] & 0x40:
                raise RuntimeError('Camera error flag or invalid MJPEG image')
            if len(self.rows) >= 6000:
                raise RuntimeError('Diagnostic capture capacity reached')
            self.rows.append(row)
            return True, (image, row)
        except Exception as exc:
            self.failed_reads += 1
            if len(self.errors) < 20:
                self.errors.append(str(exc))
            return False, None

    def release(self):
        # LatestFrameCapture first signals its stop event, then calls this.
        # Do not unmap memory concurrently with read/decode; close after join.
        pass

    def close(self):
        if self.running:
            fcntl.ioctl(self.fd, STREAMOFF, C.c_uint32(1))
            self.running = False
        for mapping in self.maps:
            mapping.close()
        self.maps.clear()
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


class TimedCalls:
    """Measure selected calls without copying the tracker implementation."""

    def __init__(self, target, names):
        self.target, self.names, self.times = target, names, {}

    def __getattr__(self, name):
        value = getattr(self.target, name)
        if name not in self.names:
            return value

        def call(*args, **kwargs):
            started = time.monotonic_ns()
            try:
                return value(*args, **kwargs)
            finally:
                self.times[name] = self.times.get(name, 0) + time.monotonic_ns() - started
        return call


def measure_frame(tracker, engine, frame):
    tracker.cv2.times.clear()
    tracker.hands.times.clear()
    begin = time.monotonic_ns()
    result = tracker.process(frame)
    tracked = time.monotonic_ns()
    engine.update(result.observation)
    end = time.monotonic_ns()
    prep = sum(tracker.cv2.times.values())
    graph = sum(tracker.hands.times.values())
    return result, dict(start_ns=begin, end_ns=end, detected=result.observation.detected,
                       preprocessing_ms=prep / 1e6, graph_ms=graph / 1e6,
                       landmark_conversion_and_wrapper_ms=(tracked - begin - prep - graph) / 1e6,
                       gesture_and_axes_ms=(end - tracked) / 1e6,
                       total_ms=(end - begin) / 1e6)


def wrap_tracker(tracker):
    tracker.preview_enabled = tracker.diagnostics_enabled = False
    tracker.cv2 = TimedCalls(tracker.cv2, {'flip', 'cvtColor'})
    tracker.hands = TimedCalls(tracker.hands, {'process'})


def camera_lane(path, buffers, seconds, tracker, engine):
    from powerglove_vision.realtime import LatestFrameCapture
    import cv2
    import numpy as np
    raw = RawCamera(path, buffers, cv2, np)
    capture = LatestFrameCapture(raw)
    rows, selected, last_detected = [], 0, None
    started = time.monotonic()
    warmup_until, deadline = started + 2, started + 2 + seconds
    try:
        while time.monotonic() < deadline:
            latest = capture.latest_after(selected)
            if latest is None:
                time.sleep(.001)
                continue
            skipped = latest.sequence - selected - 1
            selected = latest.sequence
            if not latest.ok:
                continue
            frame, metadata = latest.frame
            result, timing = measure_frame(tracker, engine, frame)
            if result.observation.detected:
                last_detected = frame
            if time.monotonic() >= warmup_until:
                rows.append(dict(metadata, **timing, capture_sequence=selected,
                    skipped_application_frames=skipped,
                    driver_to_recognition_ms=driver_age_ms(metadata, timing['start_ns']),
                    driver_to_coordinates_ms=driver_age_ms(metadata, timing['end_ns'])))
    finally:
        capture.release()
        capture._thread.join(timeout=3)
        if capture._thread.is_alive():
            raise RuntimeError('Capture thread did not stop; process exit must release camera')
        raw.close()
    capture_rows = [r for r in raw.rows if r['decoded_ns'] >= int(warmup_until * 1e9)]
    return dict(buffers=buffers, samples=rows, capture=capture_rows,
                errors=raw.errors, failed_reads=raw.failed_reads), last_detected


def native_profile_summary(folder):
    from mediapipe.framework import calculator_profile_pb2
    groups = {}
    for path in Path(folder).glob('*.binarypb'):
        report = calculator_profile_pb2.GraphProfile()
        report.ParseFromString(path.read_bytes())
        for trace in report.graph_trace:
            for event in trace.calculator_trace:
                if event.event_type != calculator_profile_pb2.GraphTrace.PROCESS:
                    continue
                if not event.HasField('start_time') or not event.HasField('finish_time'):
                    continue
                if not 0 <= event.node_id < len(trace.calculator_name):
                    continue
                name = trace.calculator_name[event.node_id]
                duration = event.finish_time - event.start_time
                if duration >= 0:
                    groups.setdefault(name, []).append(duration / 1000)
    return {name: stats(values) for name, values in groups.items()}


def replay_lane(frame, profiled, tracker_class, engine_class, calibration_class):
    from google.protobuf import text_format
    from mediapipe.framework import calculator_pb2
    from mediapipe.python.solution_base import SolutionBase
    with tempfile.TemporaryDirectory(prefix='pgv-native-profile-') as folder:
        tracker = tracker_class(inference_threads=2)
        if profiled:
            config = calculator_pb2.CalculatorGraphConfig()
            text_format.Parse(tracker.hands._graph.text_config, config)
            tracker.hands.close()
            p = config.profiler_config
            p.enable_profiler = p.trace_enabled = True
            p.trace_log_capacity = 131072
            p.trace_log_interval_usec = -1  # export only after graph stops
            p.trace_log_margin_usec = 0
            p.trace_log_path = folder + '/'
            tracker.hands = SolutionBase(graph_config=config,
                side_inputs={'model_complexity': 0, 'num_hands': 1, 'use_prev_landmarks': True},
                outputs=['multi_hand_landmarks', 'multi_hand_world_landmarks', 'multi_handedness'])
        wrap_tracker(tracker)
        engine = engine_class('super_glove_ball', calibration=calibration_class(.5, .5, .2, 0))
        rows = []
        try:
            for index in range(45):
                _, timing = measure_frame(tracker, engine, frame)
                timing['warmup'] = index < 10
                rows.append(timing)
        finally:
            tracker.close()
        native = native_profile_summary(folder) if profiled else {}
    landmark_calls = sum(value['samples'] for name, value in native.items()
                         if 'handlandmarkcpu__' in name and 'InferenceCalculator' in name)
    return dict(profiled=profiled, samples=rows, native_calculators_ms=native,
                native_trace_complete=(landmark_calls == len(rows)) if profiled else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', required=True)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--seconds', type=int, choices=range(5, 31), default=10)
    parser.add_argument('--worker-stopped', action='store_true', required=True,
                        help='Acknowledge exclusive camera ownership; caller restores the worker')
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_root / 'src'))
    from powerglove_vision.tracker import MediaPipeTracker
    from powerglove_vision.gesture import GestureEngine
    from powerglove_vision.model import Calibration
    import cv2
    import mediapipe as mp
    tracker = MediaPipeTracker(inference_threads=2)
    wrap_tracker(tracker)
    # Synthetic center for cost measurement only. Never reads or changes player setup.
    engine = GestureEngine('super_glove_ball', calibration=Calibration(.5, .5, .2, 0))
    report = dict(format='powerglove-camera-pipeline/1', opencv=cv2.__version__,
        mediapipe=mp.__version__, lanes=[], replay=[], limitations=[
            'Isolated capture/recognition; no gameplay transmission or supervisor workload.',
            'Driver timestamps are not validated physical exposure timestamps.',
            'Coordinates use a synthetic calibration solely for computation cost.',
            'Native graph process durations include scheduling; they are not CPU-only time.',
            'Native replay timings include warmup; Python replay samples label warmup.',
            'Fixed-frame replay measures profiling overhead, not live tracking reliability.',
            'Finite native trace capacity 131072 events; missing traces invalidate native attribution.',
        ])
    replay_frame = None
    try:
        for buffers in (1, 2, 1):
            lane, frame = camera_lane(args.camera, buffers, args.seconds, tracker, engine)
            report['lanes'].append(lane)
            if frame is not None:
                replay_frame = frame
            print(json.dumps({'completed_buffers': buffers}), flush=True)
    finally:
        tracker.close()
    if replay_frame is not None:
        for profiled in (False, True, False):
            report['replay'].append(replay_lane(replay_frame, profiled, MediaPipeTracker,
                                                GestureEngine, Calibration))
            print(json.dumps({'completed_profiled_replay': profiled}), flush=True)
    else:
        report['recognition_profile_error'] = 'No detected-hand frame; repeat with visible hand'
    print(json.dumps(report, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
