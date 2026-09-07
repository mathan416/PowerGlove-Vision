# Project: PowerGlove Vision
# File: tests/test_latency_diagnostics.py
# Purpose: Verify finite timing traces and reject misleading physical latency evidence.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Cover receiver-to-native publication timing.
#   2026-09-06 - Cover drops, clock separation, session reuse, and video timing brackets.
# Full history: docs/CHANGELOG.md and Git history.

"""Test diagnostics independently of cameras and game ROMs."""
import importlib.util
import json
import os
import shutil
import signal
import socket
import sys
import time
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from powerglove_vision.diagnostic_trace import DiagnosticTrace, session_key
from powerglove_vision.transport import UdpSender
from powerglove_vision.model import ControllerState
from powerglove_vision.native_state import decode_record

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'scripts'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trace_analysis = load('analyze-latency-trace')
video_analysis = load('analyze-latency-video')
measure = load('measure-vision-status')


class DiagnosticTests(unittest.TestCase):
    def test_disabled_does_not_open_files_or_start_thread(self):
        with patch.dict(os.environ, {}, clear=True), patch('os.open') as opened:
            self.assertIsNone(DiagnosticTrace.from_environment('controller'))
            opened.assert_not_called()

    def test_finite_private_export_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'trace.json'
            trace = DiagnosticTrace(path, 'controller', capacity=2)
            trace.record({'event':'one'})
            trace.record({'event':'two'})
            trace.record({'event':'three'})
            trace.close()
            report = json.loads(path.read_text())
            self.assertEqual(len(report['events']), 2)
            self.assertEqual(report['dropped'], 1)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                DiagnosticTrace(path, 'controller')

    def test_contention_drops_without_waiting_and_deadline_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            trace = DiagnosticTrace(Path(folder)/'trace', 'controller')
            trace.lock.acquire()
            try:
                trace.record({'event':'busy'})
            finally:
                trace.lock.release()
            self.assertEqual(trace.dropped, 1)
            trace.deadline_ns = 0
            trace.record({'event':'expired'})
            trace.close()
            self.assertFalse(trace.enabled)

    def test_session_hash_is_stable_but_not_raw_identifier(self):
        self.assertEqual(session_key('a'*32), session_key('a'*32))
        self.assertNotEqual(session_key('a'*32), session_key('b'*32))
        self.assertNotEqual(session_key('a'*32), 'a'*32)

    def test_analysis_joins_resets_and_counts_first_consumption_only(self):
        controller = dict(format='powerglove-diagnostic/1', role='controller', dropped=0, events=[
            dict(event='send', session=s, sequence=1, start_ns=100, end_ns=200) for s in ('a','b')])
        controller['events'].append(dict(event='vision', session='a', sequence=1, capture_ns=20,
            start_ns=30, tracking_end_ns=50, end_ns=70))
        receiver = dict(format='powerglove-diagnostic/1', role='receiver', dropped=0, events=[
            dict(event='receive', session=s, sequence=1, received_ns=900000000, validated_ns=900000100,
                 publication_start_ns=900000200, end_ns=900000400, published_ns=900000250+i,
                 native_start_ns=900000210, native_end_ns=900000260,
                 guard=2+i*2) for i,s in enumerate(('a','b'))])
        core = [dict(valid=1, sequence=1, guard=2, published_ns=900000250, consumed_ns=t)
                for t in (901000250, 902000250)]
        report = trace_analysis.analyze(controller, receiver, core)
        self.assertEqual(report['correlated_send_receive'], 2)
        self.assertIsNone(report['network_transit_ms'])
        self.assertAlmostEqual(report['timings_ms']['capture_read_to_send']['p50'], .00018)
        self.assertAlmostEqual(report['timings_ms']['processing_to_send_start']['p50'], .00003)
        self.assertAlmostEqual(
            report['timings_ms']['receiver_to_native_publication']['p50'], .00026
        )
        self.assertAlmostEqual(report['timings_ms']['native_write']['p50'], .00005)
        self.assertEqual(report['publications_without_observed_consumption'], 1)
        timing = report['timings_ms']['publication_record_to_first_core_consumption']
        self.assertEqual(timing['samples'], 1)
        self.assertEqual(timing['p50'], 1)

    def test_tracking_loss_invalidates_stationary_candidate(self):
        window = measure.StatusWindow('neutral')
        for i, detected in enumerate((True, False, True)):
            window.observe(dict(vision_state='active', timestamp=i+1, capture_sequence=i+1,
                detected=detected, calibrated=True, buttons={}, axes={'x':1,'y':2}), 1)
        segment = window.report(3)['segments'][0]
        self.assertEqual(segment['tracking_losses'], 1)
        self.assertFalse(segment['stationary_candidate'])
        self.assertEqual(segment['observation_interval_ms']['max'], 1000)

    def test_actual_sender_receiver_trace_correlates_session_resets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'token').write_text('diagnostic-test-token-only')
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
            sock.close()
            env = dict(os.environ, POWERGLOVE_DIAGNOSTIC_TRACE=str(root/'run'),
                       POWERGLOVE_DIAGNOSTIC_SECONDS='10')
            process = subprocess.Popen([sys.executable, '-m', 'powerglove_vision.receiver',
                '--listen', '127.0.0.1', '--port', str(port), '--token-file', str(root/'token'),
                '--native-state', str(root/'native'), '--dry-run'], env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                with patch.dict(os.environ, env):
                    sender = UdpSender('127.0.0.1', port, 'diagnostic-test-token-only')
                try:
                    for round_number in range(2):
                        if round_number:
                            sender.new_session()
                        deadline, sequence = time.monotonic()+3, 0
                        while time.monotonic() < deadline:
                            sequence += 1
                            state = ControllerState.released(sequence, time.monotonic(), 'super_glove_ball', True)
                            state.detected = True
                            state.axes['x'] = 100 + round_number
                            sender.send(state)
                            time.sleep(.02)
                            if (root/'native').exists():
                                try:
                                    record = decode_record((root/'native').read_bytes())
                                except ValueError:
                                    continue
                                if record['detected'] and record['axes']['x'] == 100+round_number:
                                    break
                        else:
                            self.fail('No authenticated publication')
                finally:
                    sender.close()
                process.send_signal(signal.SIGINT)
                process.communicate(timeout=3)
                self.assertEqual(process.returncode, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=3)
            controller = json.loads(next(root.glob('run.controller.*.json')).read_text())
            receiver = json.loads(next(root.glob('run.receiver.*.json')).read_text())
            report = trace_analysis.analyze(controller, receiver, [])
            self.assertGreaterEqual(report['correlated_send_receive'], 2)
            self.assertEqual(len({e['session'] for e in receiver['events']}), 2)
            self.assertEqual(report['invalid_intervals'], 0)
            self.assertNotIn('diagnostic-test-token-only', json.dumps([controller,receiver]))

    def test_video_brackets_and_occlusion(self):
        annotation = dict(timing_verified=True, trials=[
            dict(label='left-1', direction='left', unoccluded=True, hand_onset=2, game_onset=5),
            dict(label='hidden', unoccluded=False)])
        report, _ = video_analysis.analyze([i/100 for i in range(10)], annotation)
        self.assertAlmostEqual(report['trials'][0]['onset_ms'], 30)
        self.assertAlmostEqual(report['trials'][0]['onset_lower_ms'], 20)
        self.assertAlmostEqual(report['trials'][0]['onset_upper_ms'], 40)
        self.assertEqual(report['rejected_trials'], ['hidden'])

    def test_video_following_and_stationary_remain_separate(self):
        points = [dict(frame=i, hand_x=h, hand_y=10, glove_x=g, glove_y=20)
                  for i,h,g in ((1,0,0),(5,10,0),(10,10,10))]
        annotation = dict(timing_verified=True, trials=[dict(label='right', direction='right',
            unoccluded=True, hand_onset=2, game_onset=6, trajectory=points)],
            stationary=[dict(label='hold', unoccluded=True, tracking_losses=1, points=points)])
        report, _ = video_analysis.analyze([i/100 for i in range(20)], annotation)
        self.assertAlmostEqual(report['trials'][0]['following']['normalized_progress_error_rms'], (1/3)**.5)
        self.assertFalse(report['stationary'][0]['accepted'])
        self.assertEqual(report['stationary'][0]['hand_x']['span'], 10)

    def test_video_rejects_unverified_retiming_gaps_and_no_prior_frame(self):
        with self.assertRaises(ValueError):
            video_analysis.analyze([0,.01,.02], {})
        with self.assertRaises(ValueError):
            video_analysis.analyze([0,.01,.02,.06], dict(timing_verified=True))
        with self.assertRaises(ValueError):
            video_analysis.analyze([0,.01,.01], dict(timing_verified=True))
        with self.assertRaises(ValueError):
            video_analysis.analyze([0,.01,.02], dict(timing_verified=True, trials=[
                dict(label='bad', direction='left', unoccluded=True, hand_onset=0, game_onset=1)]))

    @unittest.skipUnless(shutil.which('c++'), 'C++ compiler unavailable')
    def test_native_buffer_exports_only_on_close_and_stays_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder/'test.cpp'
            source.write_text('#include "diagnostic_trace.h"\n#include <sys/stat.h>\n'
                'int main() { pgv_diagnostic_open(); for(int i=0;i<20003;i++) '
                'pgv_diagnostic_record(true, i, 2, 100); struct stat st; '
                'if(fstat(pgv_diagnostic_fd,&st) || st.st_size) return 2; '
                'pgv_diagnostic_close(); return 0; }')
            subprocess.run(['c++','-std=c++11','-I',str(ROOT/'native/nestopia-powerglove'),
                str(source),'-o',str(folder/'test')], check=True, capture_output=True)
            env = dict(os.environ, POWERGLOVE_CORE_DIAGNOSTIC_TRACE=str(folder/'core.csv'))
            subprocess.run([str(folder/'test')], env=env, check=True)
            lines = (folder/'core.csv').read_text().splitlines()
            self.assertEqual(len(lines), 20002)
            self.assertEqual(lines[-1], '# dropped=3')
            self.assertEqual((folder/'core.csv').stat().st_mode & 0o777, 0o600)
