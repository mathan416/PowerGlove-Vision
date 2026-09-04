# Project: PowerGlove Vision
# File: tests/test_bsb_zap_setup.py
# Purpose: Verify repeatable Glove Zap setup, option inheritance, and preflight failures.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added isolated configuration checks.
# Full history: docs/CHANGELOG.md and Git history.
"""Exercise RetroPie option changes in a temporary filesystem."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('bsb', Path(__file__).resolve().parents[1] / 'scripts/configure-bsb-zap.py')
bsb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bsb)


class ZapSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rom = self.root / 'roms/nes/Bad Street Brawler (USA).7z'
        self.directory = self.root / 'configs/all/retroarch/config/FCEUmm'
        self.directory.mkdir(parents=True)
        self.put(self.rom, 'rom')
        self.core = self.root / 'libretrocores/lr-fceumm/fceumm_libretro.so'
        self.put(self.core, 'core')
        self.put(self.root / 'emulators/retroarch/bin/retroarch', 'binary')
        self.put(self.root / 'configs/nes/emulators.cfg', 'default = "lr-fceumm"\nlr-fceumm = "retroarch -L ' + str(self.core) + '"\n')
        self.global_file = self.root / 'configs/all/retroarch-core-options.cfg'
        self.put(self.global_file, 'fceumm_up_down_allowed = "disabled"\nfceumm_palette = "custom"\nother_core = "keep"\n')
        self.target = self.directory / (self.rom.stem + '.opt')

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def plan(self):
        return bsb.plan(self.rom, self.root, self.directory)

    def test_creation_preserves_global_and_is_repeatable(self):
        original = self.global_file.read_bytes()
        target, source, content = self.plan()
        self.assertEqual(source, self.global_file)
        backup = bsb.apply(target, content)
        self.assertIn('did not exist', (backup / 'RESTORE.txt').read_text())
        self.assertEqual(bsb.settings(target)['fceumm_palette'], 'custom')
        self.assertNotIn('other_core', target.read_text())
        self.assertEqual(self.global_file.read_bytes(), original)
        with patch.object(bsb, 'apply', side_effect=AssertionError('not idempotent')):
            self.assertEqual(bsb.main(['--rom', str(self.rom), '--prefix', str(self.root), '--apply']), 0)

    def test_existing_file_backup_and_only_option_changed(self):
        original = '# custom\nfceumm_palette = "rgb"\nfceumm_up_down_allowed = "disabled"\n'
        self.put(self.target, original)
        target, source, content = self.plan()
        backup = bsb.apply(target, content)
        self.assertEqual((backup / target.name).read_text(), original)
        self.assertEqual(target.read_text(), original.replace('"disabled"', '"enabled"'))

    def test_directory_then_core_inheritance(self):
        core = self.directory / 'FCEUmm.opt'
        folder = self.directory / 'nes.opt'
        self.put(core, 'fceumm_palette = "core"\n')
        self.assertEqual(self.plan()[1], core)
        self.put(folder, 'fceumm_palette = "folder"\n')
        self.assertEqual(self.plan()[1], folder)
        self.put(self.target, 'fceumm_palette = "game"\n')
        self.assertEqual(self.plan()[1], self.target)

    def test_missing_core_and_wrong_emulator_rejected(self):
        self.core.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'): self.plan()
        self.put(self.core, 'core')
        self.put(self.root / 'configs/all/emulators.cfg', 'nes_BadStreetBrawlerUSA = "lr-nestopia"\n')
        with self.assertRaisesRegex(ValueError, 'lr-nestopia'): self.plan()
        self.assertFalse(self.target.exists())

    def test_read_only_and_running_game(self):
        args = ['--rom', str(self.rom), '--prefix', str(self.root)]
        self.assertEqual(bsb.main(args), 2)
        self.assertFalse(self.target.exists())
        with patch.object(bsb.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertEqual(bsb.main(args + ['--apply']), 2)
        self.assertFalse(self.target.exists())

    def test_disabled_autoload_custom_path_and_symlink(self):
        cfg = self.root / 'configs/nes/retroarch.cfg'
        self.put(cfg, 'game_specific_options = "false"\n')
        with self.assertRaisesRegex(ValueError, 'Automatically'): self.plan()
        self.put(cfg, 'core_options_path = "/custom/options"\n')
        with self.assertRaisesRegex(ValueError, 'Custom'): self.plan()
        cfg.unlink()
        self.target.symlink_to(self.global_file)
        with self.assertRaisesRegex(ValueError, 'symlink'): bsb.apply(self.target, 'bad')
