# Project: PowerGlove Vision
# File: tests/test_setup_machine.py
# Purpose: Verify installer preservation, backups, hook integration and repeatability.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added isolated filesystem installation tests.
# Full history: docs/CHANGELOG.md and Git history.

"""Exercise installation without changing the host OS or invoking apt/systemd."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("setup_machine", ROOT / "scripts/setup-machine.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def test_hook_inserted_before_exit_and_is_idempotent(self):
        original = "#!/bin/bash\necho existing\nexit 0\n"
        updated = setup.hook_content(original, "start")
        self.assertIn(original.split("\n", 1)[1], updated)
        self.assertLess(updated.index("powerglove.sh"), updated.index("exit 0"))
        self.assertEqual(setup.hook_content(updated, "start"), updated)
        with self.assertRaises(ValueError):
            setup.hook_content("#!/usr/bin/python3\nprint('custom')\n", "start")

    def test_files_are_backed_up_and_tokens_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "settings"
            file.write_text("original")
            with patch.object(setup, "BACKUPS", root / "backups"):
                setup.write_file(file, "new", preserve=True)
                self.assertEqual(file.read_text(), "original")
                setup.write_file(file, "new")
                self.assertEqual(file.read_text(), "new")
                backups = list((root / "backups").rglob("settings"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_text(), "original")
                link = root / "link"
                link.symlink_to(file)
                with self.assertRaises(ValueError):
                    setup.write_file(link, "bad")

    def test_retropie_install_twice_preserves_existing_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def mapped(value):
                path = Path(value)
                if str(path).startswith(("/etc/", "/opt/", "/dev/")):
                    return root / str(path).lstrip("/")
                return path
            base = mapped("/opt/retropie/configs/all")
            base.mkdir(parents=True)
            hook = base / "runcommand-onstart.sh"
            hook.write_text("#!/bin/sh\necho lighting\nexit 0\n")
            config = mapped("/etc/powerglove")
            config.mkdir(parents=True)
            (config / "token").write_text("existing-private-token")
            (config / "launcher.json").write_text('{"uno_q":"existing.local"}')
            (config / "games.json").write_text('{"custom":"game"}')
            with patch.object(setup, "Path", side_effect=mapped), patch.object(setup, "BACKUPS", root / "backups"), patch.object(setup, "run") as command, patch.object(setup.os, "chown"), patch.object(setup.grp, "getgrnam", return_value=SimpleNamespace(gr_gid=100)):
                setup.install_retropie("new.local")
                first = hook.read_text()
                setup.install_retropie("new.local")
            self.assertEqual(hook.read_text(), first)
            self.assertEqual((config / "token").read_text(), "existing-private-token")
            self.assertEqual((config / "launcher.json").read_text(), '{"uno_q":"existing.local"}')
            self.assertEqual((config / "games.json").read_text(), '{"custom":"game"}')
            self.assertTrue(mapped("/opt/powerglove/bin/powerglove-receiver").exists())
            self.assertTrue(mapped("/etc/systemd/system/powerglove-receiver.timer").exists())
            self.assertIn("echo lighting", first)
            command.assert_any_call("apt-get", "install", "-y", "python3", "python3-evdev", "openssl", "avahi-daemon", "libnss-mdns")
            command.assert_any_call("systemctl", "enable", "--now", "avahi-daemon")

    def test_unoq_install_twice_preserves_private_data_and_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "app"
            (app / ".cache").mkdir(parents=True)
            (app / "data").mkdir()
            (app / "scripts").mkdir()
            (app / "uno-q").mkdir()
            (app / "data/device.json").write_text('{"token":"keep-this-private","profile":"off"}')
            compose = app / ".cache/app-compose.yaml"
            compose.write_text("services:\n  main:\n    volumes:\n    - /app:/app\n    ports:\n    - 8088:8088\n")
            for original in (ROOT / "uno-q").glob("powerglove-system-shutdown.*"):
                (app / "uno-q" / original.name).write_bytes(original.read_bytes())
            (app / "scripts/configure-uno-q-mdns.py").write_bytes((ROOT / "scripts/configure-uno-q-mdns.py").read_bytes())
            class AppPath:
                def __str__(self):
                    return "/home/arduino/ArduinoApps/powerglove-vision"
                def __truediv__(self, relative):
                    return app / relative
            def mapped(value):
                path = Path(value)
                return root / str(path).lstrip("/") if str(path).startswith("/etc/") else path
            with patch.object(setup, "SOURCE", AppPath()), patch.object(setup, "Path", side_effect=mapped), patch.object(setup, "BACKUPS", root / "backups"), patch.object(setup, "run") as command, patch.object(setup.os, "chown"), patch.object(setup.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=1000, pw_gid=1000)):
                setup.install_unoq(None)
                first = compose.read_text()
                setup.install_unoq(None)
            command.assert_any_call("apt-get", "install", "-y", "avahi-daemon", "libnss-mdns")
            command.assert_any_call("systemctl", "enable", "--now", "avahi-daemon")
            self.assertEqual(first, compose.read_text())
            self.assertEqual(first.count("target: /run/avahi-daemon"), 1)
            self.assertEqual(first.count("- 8443:8443"), 1)
            self.assertEqual(first.count("bricks/local/profile_control/brick_compose.yaml"), 1)
            self.assertEqual((app / "data/device.json").read_text(), '{"token":"keep-this-private","profile":"off"}')
            self.assertTrue(mapped("/etc/systemd/system/powerglove-system-shutdown.path").exists())
            service = mapped("/etc/systemd/system/powerglove-system-shutdown.service").read_text()
            self.assertIn("ExecStart=/usr/bin/systemctl --no-block halt", service)
            self.assertNotIn("--no-block poweroff", service)
