# Project: PowerGlove Vision
# File: tests/test_tuning.py
# Purpose: Verify gesture sampling, preview leases, global overrides, and persistence safety.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added personal tuning regression coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Exercise tuning against deterministic hand observations rather than camera hardware."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from powerglove_vision.tuning import TuningManager, suggest, CHANNELS, validate_overrides
from powerglove_vision.gesture import GestureConfig, GestureEngine, SUPPORTED_PROFILES
from powerglove_vision.model import Calibration, HandObservation
from powerglove_vision.debug_server import SharedDebugState


class TuningTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'gesture-tuning.json'
        self.now = 10.
        self.manager = TuningManager(self.path, lambda: self.now)
        self.command('begin')
        self.calibration = Calibration(.5, .5, .2, 0)

    def command(self, action, **extra):
        return self.manager.command(dict(action=action, session='test-session', **extra))

    def phases(self):
        return [[dict.fromkeys(CHANNELS, .1 if i % 2 == 0 else .8) for _ in range(20)] for i in range(7)]

    def test_three_repetitions_produce_release_below_activation(self):
        pair = suggest('index', self.phases())['index']
        self.assertGreater(pair['off'], .1)
        self.assertLess(pair['off'], pair['on'])
        self.assertLess(pair['on'], .8)

    def test_noisy_overlapping_incomplete_or_inconsistent_samples_rejected(self):
        with self.assertRaises(ValueError): suggest('index', self.phases()[:3])
        for phase in (0, 3, 6):
            data = self.phases()
            for sample in data[phase]: sample['index'] = .78 if phase % 2 == 0 else .12
            with self.subTest(phase=phase), self.assertRaises(ValueError): suggest('index', data)

    def test_compound_suggestions_adjust_closed_components(self):
        self.assertEqual(set(suggest('start', self.phases())), {'ring','pinky'})
        self.assertEqual(set(suggest('menu_guard', self.phases())), {'thumb','ring'})

    def test_preview_expiry_and_session_ownership(self):
        self.command('preview', thresholds={'index': {'on':.3, 'off':.2}})
        self.assertEqual(self.manager.configuration(GestureConfig()).pair('index'), (.3,.2))
        with self.assertRaises(ValueError):
            self.manager.command({'action':'begin','session':'another-session'})
        self.now += 7
        self.assertFalse(self.manager.active())
        self.assertEqual(self.manager.configuration(GestureConfig()).pair('index'), (.5,.35))
        self.assertFalse(self.path.exists())

    def test_save_global_independence_restart_and_reset(self):
        self.command('save', thresholds={'index': {'on':.3, 'off':.2}})
        reloaded = TuningManager(self.path)
        for profile in SUPPORTED_PROFILES:
            cfg = reloaded.configuration(GestureConfig())
            engine = GestureEngine(profile, cfg, calibration=self.calibration)
            hand = HandObservation(1, True, .99, .5,.5,.2,0,index_curl=.4,thumb_curl=.4)
            engine.update(hand)
            self.assertTrue(engine.curl_feedback(hand)['index'])
            self.assertFalse(engine.curl_feedback(hand)['thumb'])
        self.command('reset')
        self.assertFalse(TuningManager(self.path).saved)

    def test_invalid_and_failed_saves_leave_previous_settings(self):
        self.command('save', thresholds={'index':{'on':.3,'off':.2}})
        original = self.path.read_text()
        for pair in ({'on':.2,'off':.3}, {'on':float('nan'),'off':.1}, {'on':True,'off':0}, {'on':1.1,'off':.2}):
            with self.assertRaises(ValueError): validate_overrides({'index':pair})
        with patch('powerglove_vision.game_registry.atomic_write', side_effect=OSError):
            with self.assertRaises(OSError): self.command('save', thresholds={'index':{'on':.8,'off':.6}})
        self.assertEqual(self.path.read_text(), original)
        self.assertEqual(self.manager.saved['index']['on'], .3)

    def test_fresh_high_confidence_frames_only_and_calibration_invalidation(self):
        self.command('record')
        def observe(t, confidence=.9):
            hand = HandObservation(t,True,confidence,.5,.5,.2,0,index_curl=.1)
            self.manager.observe(hand,self.calibration,GestureConfig(),True)
        for i in range(15): observe(1)
        self.assertEqual(self.manager.snapshot()['samples'],1)
        observe(2,.1)
        self.assertEqual(self.manager.snapshot()['samples'],1)
        for i in range(15): observe(3+i)
        self.now += 3.1
        observe(19)
        self.assertEqual(self.manager.snapshot()['completed_phases'],1)
        self.manager.invalidate()
        self.assertEqual(self.manager.snapshot()['completed_phases'],0)

    def test_tuning_keeps_practice_active_despite_dashboard_reset(self):
        shared = SharedDebugState(True)
        shared.tuning = self.manager
        self.assertTrue(shared.take_practice_request())
        shared.request_profile('program_g', 'RetroPie launch hook', 'Gun.Smoke')
        shared.request_practice('',False,reset=True)
        self.assertTrue(shared.practice_active)
        self.assertEqual(shared.take_profile_request()[0], 'program_g')
        self.command('end')
        self.assertFalse(shared.take_practice_request())

    def test_camera_loss_finishes_recording_with_useful_error(self):
        self.command('record')
        self.now += 3.1
        state = self.manager.snapshot()
        self.assertFalse(state['recording'])
        self.assertIn('Not enough', state['error'])
        self.assertEqual(state['completed_phases'], 0)
