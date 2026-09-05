# Project: PowerGlove Vision
# File: tests/test_install_packages.py
# Purpose: Test release validation, safe updates, and installer entry points without host changes.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added two-machine installation regression coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Exercise real staging and archive handling with simulated privileged commands."""
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install-package.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class PackageContentTests(unittest.TestCase):
    def test_local_matrix_exports_rejected_but_guide_images_allowed(self):
        spec = importlib.util.spec_from_file_location(
            'package_verifier', ROOT / 'scripts/verify-app-lab-package.py')
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'package.zip'
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('PowerGlove-Vision/assets/matrix/A.png', 'duplicate')
                output.writestr('PowerGlove-Vision/docs/images/matrix/A.jpg', 'guide')
            errors = verifier.archive_errors(archive)
            duplicates = [error for error in errors if 'local duplicate matrix' in error]
            self.assertEqual(len(duplicates), 1)
            self.assertIn('assets/matrix/A.png', duplicates[0])


class ArchiveTests(unittest.TestCase):
    def package(self, directory, machine='retropie', extra=None):
        archive = Path(directory) / 'package.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('PowerGlove-Vision/install-release.json', json.dumps(
                dict(format=1, machine=machine, version='dev-test')))
            for name in ('scripts/setup-machine.py', 'scripts/installation-manifest.py',
                         'scripts/install-nestopia-powerglove.sh',
                         'scripts/configure-super-glove-ball-core.py',
                         'src/powerglove_vision/receiver.py',
                         'src/powerglove_vision/gesture.py',
                         'src/powerglove_vision/tracker.py',
                         'src/powerglove_vision/tuning.py',
                         'src/powerglove_vision/vision_app.py',
                         'config/games.json', 'config/profiles.json',
                         'retropie/powerglove-receiver.service',
                         'native/nestopia-powerglove/nestopia-powerglove.patch',
                         'native/nestopia-powerglove/README.md',
                         'native/nestopia-powerglove/CHANGES.md'):
                output.writestr('PowerGlove-Vision/' + name, 'test')
            if extra:
                output.writestr(*extra)
        return archive

    def test_valid_package_and_wrong_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.package(directory)
            source = installer.unpack(archive, Path(directory) / 'extract', 'retropie', 'dev-test')
            self.assertTrue((source / 'scripts/setup-machine.py').is_file())
            for machine, version in [('uno-q', 'dev-test'), ('retropie', 'v-other')]:
                with self.assertRaisesRegex(ValueError, 'does not match'):
                    installer.unpack(archive, Path(directory) / 'bad', machine, version)

    def test_traversal_private_files_and_links_rejected_before_extract(self):
        link = zipfile.ZipInfo('PowerGlove-Vision/link')
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        for name in ('../escape', '/absolute', 'PowerGlove-Vision/data/token',
                     'PowerGlove-Vision/docs/cheatsheet.md', link):
            with tempfile.TemporaryDirectory() as directory:
                archive = self.package(directory, extra=(name, 'bad'))
                target = Path(directory) / 'extract'
                with self.assertRaises(ValueError):
                    installer.unpack(archive, target, 'retropie', 'dev-test')
                self.assertFalse(target.exists())

    def test_duplicate_and_incomplete_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.package(directory, extra=('PowerGlove-Vision/config/games.json', 'duplicate'))
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                installer.unpack(archive, Path(directory) / 'bad', 'retropie', 'dev-test')
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('PowerGlove-Vision/install-release.json', json.dumps(
                    dict(format=1, machine='retropie', version='dev-test')))
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                installer.unpack(archive, Path(directory) / 'bad', 'retropie', 'dev-test')

    def test_fresh_and_repeat_unoq_staging_preserves_private_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'source'
            source.mkdir()
            (source / 'app.yaml').write_text('new application')
            app = root / 'home/ArduinoApps/powerglove-vision'
            setup = installer.load_setup(ROOT)
            setup.BACKUPS = root / 'backups'
            account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
            with patch.object(installer, 'APP', app), patch.object(installer.pwd, 'getpwnam', return_value=account), \
                 patch.object(installer.os, 'chown'), patch.object(setup, 'run') as command:
                installer.stage_unoq(source, setup)
                self.assertEqual((app / 'app.yaml').read_text(), 'new application')
                (app / 'data').mkdir()
                (app / 'data/device.json').write_text('private-pairing-and-tuning')
                (app / 'data/calibration.json').write_text('private-neutral-reference')
                (app / 'data/gesture-tuning.json').write_text('private-gesture-thresholds')
                (app / 'docs').mkdir()
                (app / 'docs/cheatsheet.md').write_text('local cabinet')
                (app / '.cache').mkdir()
                (app / '.cache/app-compose.yaml').write_text('generated')
                (source / 'app.yaml').write_text('upgrade')
                installer.stage_unoq(source, setup)
                installer.stage_unoq(source, setup)
                self.assertEqual((app / 'data/device.json').read_text(), 'private-pairing-and-tuning')
                self.assertEqual((app / 'data/calibration.json').read_text(), 'private-neutral-reference')
                self.assertEqual((app / 'data/gesture-tuning.json').read_text(), 'private-gesture-thresholds')
                self.assertEqual((app / 'docs/cheatsheet.md').read_text(), 'local cabinet')
                command.assert_any_call('runuser', '-u', 'arduino', '--', 'arduino-app-cli', 'app', 'start', app)
                self.assertTrue(list((root / 'backups').rglob('app.yaml')))


class BootstrapTests(unittest.TestCase):
    def execute(self, args, call_result=0, **patches):
        script = (ROOT / 'scripts/install-retropie.sh').read_text()
        code = script.split("exec python3 -c '\n", 1)[1].rsplit("' \"$@\"", 1)[0]
        with patch('sys.argv', ['installer'] + args), patch('sys.platform', 'linux'), \
             patch('os.geteuid', return_value=1000), \
             patch('urllib.request.urlopen', **patches) as network, \
             patch('subprocess.call', return_value=call_result) as call:
            with self.assertRaises(SystemExit) as result:
                exec(compile(code, 'bootstrap', 'exec'), {'__name__': '__main__'})
            return result.exception.code, network, call

    def test_check_never_downloads(self):
        with patch.object(Path, 'is_file', return_value=True):
            result, network, call = self.execute(['--check'])
        self.assertEqual(result, 0)
        network.assert_not_called()
        self.assertIn('--check', call.call_args[0][0])

    def test_download_failure_never_invokes_sudo(self):
        result, _, call = self.execute(['--version', 'v-test'], side_effect=OSError('network interrupted'))
        self.assertEqual(result, 1)
        call.assert_not_called()

    def test_bad_checksum_never_invokes_sudo(self):
        result, _, call = self.execute(['--version', 'v-test'], side_effect=[
            io.BytesIO(('0' * 64 + '  install-package.py\n').encode()), io.BytesIO(b'corrupt')])
        self.assertEqual(result, 1)
        call.assert_not_called()

    def test_verified_development_package_and_denied_sudo(self):
        import hashlib
        driver, package = b'driver', b'package'
        sums = (hashlib.sha256(driver).hexdigest() + '  install-package.py\n' +
                hashlib.sha256(package).hexdigest() + '  PowerGlove-Vision-RetroPie.zip\n').encode()
        result, network, call = self.execute(['--development', 'dev-test', '--peer', 'uno.local'],
                                             side_effect=[io.BytesIO(sums), io.BytesIO(driver), io.BytesIO(package)])
        self.assertEqual(result, 0)
        self.assertIn('dev-test', network.call_args[0][0])
        self.assertEqual(call.call_args[0][0][-2:], ['--peer', 'uno.local'])

    def test_latest_release_is_resolved_once_and_pinned_for_downloads(self):
        import hashlib
        driver, package = b'driver', b'package'
        sums = (hashlib.sha256(driver).hexdigest() + '  install-package.py\n' +
                hashlib.sha256(package).hexdigest() + '  PowerGlove-Vision-RetroPie.zip\n').encode()
        result, network, call = self.execute([], side_effect=[
            io.BytesIO(b'{"tag_name":"v0.3.0"}'), io.BytesIO(sums),
            io.BytesIO(driver), io.BytesIO(package)])
        self.assertEqual(result, 0)
        self.assertTrue(network.call_args_list[0][0][0].endswith('/releases/latest'))
        for request in network.call_args_list[1:]:
            self.assertIn('/releases/download/v0.3.0/', request[0][0])
        self.assertEqual(call.call_args[0][0][-2:], ['--version', 'v0.3.0'])

    def test_denied_sudo_is_returned_to_user(self):
        with patch.object(Path, 'is_file', return_value=True):
            result, network, call = self.execute(['--check'], call_result=1)
        self.assertEqual(result, 1)
        network.assert_not_called()
        self.assertEqual(call.call_args[0][0][0], 'sudo')

    def test_no_tty_does_not_confirm(self):
        with patch.object(installer.sys.stdin, 'isatty', return_value=False):
            self.assertFalse(installer.confirm('interrupt?'))


if __name__ == '__main__':
    unittest.main()

class PreflightTests(unittest.TestCase):
    def test_wrong_platform_stops_before_commands(self):
        with patch.object(installer.sys, 'platform', 'darwin'), patch.object(installer.subprocess, 'run') as command:
            with self.assertRaisesRegex(ValueError, 'requires Linux'):
                installer.preflight('uno-q')
            command.assert_not_called()

    def test_active_retropie_requires_closed_game(self):
        with patch.object(installer.sys, 'platform', 'linux'), patch.object(installer.os, 'geteuid', return_value=0), \
             patch.object(installer.shutil, 'which', return_value='/usr/bin/command'), \
             patch.object(installer.shutil, 'disk_usage', return_value=SimpleNamespace(free=10 * 1024 ** 3)), \
             patch.object(Path, 'is_dir', return_value=True), \
             patch.object(installer.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
             patch.object(installer, 'confirm', return_value=False):
            with self.assertRaisesRegex(ValueError, 'close RetroArch'):
                installer.preflight('retropie')

    def test_active_unoq_denied_and_unknown_cli(self):
        for version, message in [(b'Arduino App CLI version 0.12.0\ndaemon version: 0.12.0', 'validated'),
                                 (b'Arduino App CLI version 0.13.0\ndaemon version: 0.13.0', 'active session')]:
            with patch.object(installer.sys, 'platform', 'linux'), patch.object(installer.os, 'geteuid', return_value=0), \
                 patch.object(installer.shutil, 'which', return_value='/usr/bin/command'), \
                 patch.object(installer.shutil, 'disk_usage', return_value=SimpleNamespace(free=10 * 1024 ** 3)), \
                 patch.object(Path, 'read_bytes', return_value=b'arduino,imola'), \
                 patch.object(Path, 'is_file', return_value=True), patch.object(Path, 'exists', return_value=False), \
                 patch.object(installer.pwd, 'getpwnam'), \
                 patch.object(installer.subprocess, 'check_output', return_value=version), \
                 patch.object(installer.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"controller_enabled":true}')), \
                 patch.object(installer, 'confirm', return_value=False):
                with self.assertRaisesRegex(ValueError, message):
                    installer.preflight('uno-q')


class GameSetupTests(unittest.TestCase):
    def test_missing_emulator_offer_accept_and_decline(self):
        for accept in (True, False):
            setup = installer.load_setup(ROOT)
            with patch.object(Path, 'is_file', side_effect=lambda path=None: True) as exists, \
                 patch.object(setup.pwd, 'getpwnam', return_value=SimpleNamespace(pw_dir='/home/pi')), \
                 patch.dict(os.environ, {'SUDO_USER': 'pi'}), \
                 patch.object(setup, 'registered_roms', return_value=[]), patch.object(setup, 'run') as command:
                # Core, binary missing; Setup present; each package still missing until installed.
                exists.side_effect = [False, True] + ([False, False] if accept else [])
                setup.configure_games(lambda message: accept)
            if accept:
                self.assertEqual(command.call_count, 4)
                self.assertIn('install_bin', command.call_args_list[0][0])
            else:
                command.assert_not_called()

    def test_native_core_offer_builds_and_registers_without_selecting_rom(self):
        setup = installer.load_setup(ROOT)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()

            def mapped(value):
                path = Path(value)
                if str(path).startswith("/opt/retropie"):
                    return root / str(path).lstrip("/")
                return path

            prefix = mapped("/opt/retropie")
            fceumm = prefix / "libretrocores/lr-fceumm/fceumm_libretro.so"
            native = prefix / "libretrocores/lr-nestopia-powerglove/nestopia_powerglove_libretro.so"
            retroarch = prefix / "emulators/retroarch/bin/retroarch"
            system = prefix / "configs/nes/emulators.cfg"
            for path in (fceumm, retroarch):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"binary")
            system.parent.mkdir(parents=True, exist_ok=True)
            system.write_text('default = "lr-fceumm"\nlr-fceumm = "/retroarch -L ' + str(fceumm) + ' %ROM%"\n')
            rom = root / "home/pi/RetroPie/roms/nes/Super Glove Ball (USA).nes"
            rom.parent.mkdir(parents=True)
            rom.write_bytes(b"test-only")

            def command(*args):
                if args[0] == "bash" and "install-nestopia-powerglove.sh" in str(args[1]):
                    native.parent.mkdir(parents=True, exist_ok=True)
                    native.write_bytes(b"native")

            real_temporary_directory = tempfile.TemporaryDirectory
            with patch.object(setup, "Path", side_effect=mapped), \
                 patch.object(setup, "BACKUPS", root / "backups"), \
                 patch.object(setup, "registered_roms", return_value=[(rom, "super_glove_ball")]), \
                 patch.object(setup.tempfile, "TemporaryDirectory",
                              side_effect=lambda **kwargs: real_temporary_directory(
                                  prefix=kwargs.get("prefix"), dir=str(root))), \
                 patch.object(setup, "run", side_effect=command) as run:
                setup.configure_games(lambda _message: True)

            run.assert_any_call("apt-get", "install", "-y", "git", "build-essential")
            self.assertIn("lr-nestopia-powerglove", system.read_text())
            games = prefix / "configs/all/emulators.cfg"
            self.assertFalse(games.exists())
            self.assertEqual(
                (prefix / "configs/nes/powerglove-native.cfg").read_text(),
                'input_libretro_device_p1 = "517"\n',
            )

    def test_helper_failure_is_not_silently_accepted(self):
        setup = installer.load_setup(ROOT)
        with tempfile.TemporaryDirectory() as directory:
            setup.SOURCE = ROOT
            account = SimpleNamespace(pw_dir=str(Path(directory).resolve()), pw_uid=os.getuid(), pw_gid=os.getgid())
            with patch.object(setup.pwd, 'getpwnam', return_value=account), patch.object(setup.os, 'chown'), \
                 patch.object(setup, 'run', side_effect=OSError('systemd unavailable')):
                with self.assertRaisesRegex(OSError, 'systemd unavailable'):
                    setup.install_early_start()
