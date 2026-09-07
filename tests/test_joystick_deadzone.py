# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
"""Verify player-isolated dead-zone persistence without resetting hand setup."""
import copy
import tempfile
import unittest
from pathlib import Path
from powerglove_vision.tuning import TuningManager
from powerglove_vision.gesture import GestureConfig

class JoystickTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'gesture-tuning.json'
        self.manager = TuningManager(self.path)

    def command(self, action, **extra):
        s = self.manager.player_snapshot()
        return self.manager.player_command(dict(action=action, player=s['active'], generation=s['generation'], **extra))

    def test_save_persists_and_preserves_other_player_fields(self):
        before = copy.deepcopy(self.manager.players.active)
        old = self.manager.configuration(GestureConfig())
        state = self.command('joystick_deadzone', value=.5)
        after = self.manager.players.active
        for key in before:
            if key != 'thresholds':
                self.assertEqual(before[key], after[key])
        self.assertEqual(old.pair('left'), (.28, .14))
        self.assertEqual(self.manager.configuration(GestureConfig()).pair('left'), (.5, .25))
        self.assertEqual(TuningManager(self.path).player_snapshot()['joystick'], state['joystick'])
        self.assertEqual(self.command('export')['backup']['thresholds']['down'], {'on': .5, 'off': .25})

    def test_invalid_and_stale_requests_do_not_write(self):
        original = self.manager.player_snapshot()
        for value in [True, None, '0.4', .13, 1.01, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                self.command('joystick_deadzone', value=value)
        self.assertFalse(self.path.exists())
        self.command('joystick_deadzone', value=.4)
        with self.assertRaises(ValueError):
            self.manager.player_command(dict(action='joystick_deadzone', player=original['active'], generation=original['generation'], value=.8))
        self.assertEqual(self.manager.saved['left']['on'], .4)

    def test_player_isolation_and_tuning_exclusion(self):
        first = self.manager.player_snapshot()['active']
        self.command('joystick_deadzone', value=.4)
        self.command('create', name='Second')
        self.command('joystick_deadzone', value=.6)
        self.command('select', id=first)
        self.assertEqual(self.manager.saved['down'], {'on': .4, 'off': .2})
        self.manager.session = 'active-test'
        self.manager.expires = self.manager.clock() + 30
        with self.assertRaises(ValueError):
            self.command('joystick_deadzone', value=.7)

if __name__ == '__main__':
    unittest.main()
