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
from powerglove_vision.gesture import GestureConfig, GestureEngine, SUPPORTED_PROFILES, MENU_FINGERS, finger_pose_feedback
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
        self.manager.observe(HandObservation(0, True, .99, .5,.5,.2,0), self.calibration, GestureConfig(), True)

    def command(self, action, **extra):
        return self.manager.command(dict(action=action, session='test-session', **extra))

    def phases(self):
        return [[dict.fromkeys(CHANNELS, .1 if i % 2 == 0 else .8) for _ in range(20)] for i in range(3)]

    def test_three_recordings_produce_release_below_activation(self):
        pair = suggest('index', self.phases())['index']
        self.assertGreater(pair['off'], .1)
        self.assertLess(pair['off'], pair['on'])
        self.assertLess(pair['on'], .8)

    def test_noisy_overlapping_incomplete_or_inconsistent_samples_rejected(self):
        with self.assertRaises(ValueError): suggest('index', self.phases()[:2])
        for phase in (0, 1, 2):
            data = self.phases()
            for sample in data[phase]: sample['index'] = .78 if phase % 2 == 0 else .12
            with self.subTest(phase=phase), self.assertRaises(ValueError): suggest('index', data)

    def test_compound_suggestions_adjust_closed_components(self):
        phases = self.phases()
        for sample in phases[1]: sample['index'] = sample['middle'] = .1
        self.assertEqual(set(suggest('start', phases)), {'ring','pinky'})
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

    def test_hand_setup_then_individual_tuning_preserves_extended_thresholds(self):
        self.command('select', gesture='hand_setup')
        self.manager.phases = self.phases()
        state = self.command('suggest')
        self.assertEqual(state['mode'], 'hand_setup')
        self.assertEqual(len(state['preview']), 5)
        self.command('save', thresholds=state['preview'])
        original = dict(self.manager.saved)
        self.command('select', gesture='start')
        phases = self.phases()
        for sample in phases[1]:
            sample['index'] = sample['middle'] = .1
            sample['ring'] = sample['pinky'] = .65
        self.manager.phases = phases
        state = self.command('suggest')
        self.assertEqual(set(state['preview']), {'ring', 'pinky'})
        self.command('save', thresholds=state['preview'])
        self.assertEqual(self.manager.saved['index'], original['index'])
        self.assertEqual(self.manager.saved['middle'], original['middle'])
        self.command('select', gesture='hand_setup')
        self.command('reset')
        self.assertEqual(self.manager.saved, {})

    def test_recording_three_phases_and_failed_analysis_clears_preview(self):
        self.command('select', gesture='hand_setup')
        for phase in range(3):
            self.command('record')
            for frame in range(15):
                value = .7 if phase == 1 else .1
                hand = HandObservation(100+phase*20+frame, True, .99, .5,.5,.2,0,
                                       **{k+'_curl': value for k in ('thumb','index','middle','ring','pinky')})
                self.manager.observe(hand, self.calibration, GestureConfig(), True)
            self.now += 3.1
            self.command('heartbeat')
            self.manager.observe(hand, self.calibration, GestureConfig(), True)
        self.assertEqual(self.manager.snapshot()['completed_phases'], 3)
        with self.assertRaises(ValueError): self.command('record')
        self.assertEqual(len(self.command('suggest')['preview']), 5)
        for sample in self.manager.phases[2]: sample['thumb'] = .69
        with self.assertRaisesRegex(ValueError, 'thumb'): self.command('suggest')
        self.assertIsNone(self.manager.preview)
        self.assertFalse(self.path.exists())

    def test_short_recording_and_stale_tracking_rejected(self):
        phases = self.phases()
        phases[1] = phases[1][:11]
        with self.assertRaises(ValueError): suggest('hand_setup', phases)
        self.now += 2.1
        with self.assertRaisesRegex(ValueError, 'tracking'): self.command('record')
        self.assertEqual(self.manager.snapshot()['finger_feedback'], {})

    def test_menu_feedback_matches_recognition_with_default_and_personal_values(self):
        personal = suggest('hand_setup', self.phases())
        for cfg in (GestureConfig(), GestureConfig(thresholds=personal)):
            for gesture, requirements in MENU_FINGERS.items():
                for failure in (None, *requirements):
                    values = {finger: .8 if closed else .1 for finger, closed in requirements.items()}
                    if failure:
                        values[failure] = .1 if requirements[failure] else .8
                    hand = HandObservation(1, True, .99, .5,.5,.2,0,
                                           **{k+'_curl': v for k,v in values.items()})
                    engine = GestureEngine('bad_street_brawler', cfg, calibration=self.calibration)
                    engine.update(hand)
                    feedback = finger_pose_feedback(cfg, gesture, requirements, hand.fingers)
                    self.assertEqual(all(f['matches'] for f in feedback.values()), failure is None)
                    held = engine._start_gesture if gesture == 'start' else engine._select_gesture
                    self.assertEqual(held.started_at is not None, failure is None)
                    self.command('select', gesture=gesture)
                    self.manager.observe(hand, self.calibration, cfg, True)
                    self.assertEqual(self.manager.snapshot()['finger_feedback'], feedback)

    def test_hand_setup_recognizes_personal_extension_above_default_cutoff(self):
        phases = self.phases()
        for i, phase in enumerate(phases):
            for sample in phase:
                for finger in ('thumb', 'index', 'middle', 'ring', 'pinky'):
                    sample[finger] = .65 if i == 1 else .38
        cfg = GestureConfig(thresholds=suggest('hand_setup', phases))
        for gesture, requirements in MENU_FINGERS.items():
            values = {finger: .65 if closed else .38 for finger, closed in requirements.items()}
            hand = HandObservation(1, True, .99, .5,.5,.2,0,
                                   **{k+'_curl': v for k,v in values.items()})
            self.assertFalse(all(x['matches'] for x in finger_pose_feedback(
                GestureConfig(), gesture, requirements, hand.fingers).values()))
            engine = GestureEngine('bad_street_brawler', cfg, calibration=self.calibration)
            first = engine.update(hand)
            self.assertFalse(first.buttons[gesture])
            hand.timestamp = 1.8
            held = engine.update(hand)
            self.assertTrue(held.buttons[gesture])


    def test_each_extended_finger_is_required_in_every_recording(self):
        for gesture, extended in (("start", ("index", "middle")), ("select", ("thumb",))):
            for finger in extended:
                for phase_index in range(3):
                    phases = self.phases()
                    for sample in phases[1]:
                        for name in extended: sample[name] = .1
                    for sample in phases[phase_index]: sample[finger] = .6
                    with self.subTest(gesture=gesture, finger=finger, phase=phase_index):
                        with self.assertRaisesRegex(ValueError, finger + " extended"):
                            suggest(gesture, phases)

    def test_personal_extension_and_strict_boundary_are_used_by_analysis(self):
        for gesture, extended in (("start", ("index", "middle")), ("select", ("thumb",))):
            phases = self.phases()
            for phase in phases:
                for sample in phase:
                    for finger in extended: sample[finger] = .38
            personal = {finger: {"on": .6, "off": .4} for finger in extended}
            with self.assertRaisesRegex(ValueError, "extended"): suggest(gesture, phases)
            result = suggest(gesture, phases, GestureConfig(thresholds=personal))
            self.assertTrue(set(result).isdisjoint(extended))
            for sample in phases[1]: sample[extended[0]] = .4
            with self.assertRaisesRegex(ValueError, "extended"):
                suggest(gesture, phases, GestureConfig(thresholds=personal))

    def test_simultaneous_pose_and_noise_tolerance(self):
        phases = self.phases()
        for sample in phases[1]: sample['index'] = sample['middle'] = .1
        phases[1][0]['index'] = phases[1][1]['index'] = .7
        suggest('start', phases)  # Eighteen out of twenty complete poses.
        phases[1][2]['middle'] = phases[1][3]['middle'] = .7
        with self.assertRaisesRegex(ValueError, 'together'): suggest('start', phases)

    def test_failed_extended_check_clears_preview_without_changing_saved_values(self):
        self.command('save', thresholds={'index': {'on': .6, 'off': .4}})
        original = self.path.read_text()
        self.command('select', gesture='start')
        phases = self.phases()
        for phase in phases:
            for sample in phase: sample['index'] = sample['middle'] = .1
        for sample in phases[1]: sample['ring'] = sample['pinky'] = .8
        self.manager.phases = phases
        self.command('suggest')
        for sample in phases[1]: sample['index'] = .5
        with self.assertRaisesRegex(ValueError, 'index extended'): self.command('suggest')
        self.assertIsNone(self.manager.preview)
        self.assertEqual(self.path.read_text(), original)

    def test_missing_or_nonfinite_required_finger_samples_are_rejected(self):
        for value in (None, float('nan'), float('inf'), True):
            phases = self.phases()
            for sample in phases[1]: sample['index'] = sample['middle'] = .1
            phases[1][0]['index'] = value
            with self.assertRaisesRegex(ValueError, 'invalid'): suggest('start', phases)
