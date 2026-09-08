# Project: PowerGlove Vision
# File: tests/test_unoq_camera_recovery_helper.py
# Purpose: Verify first-use camera enrollment and guarded parent-hub recovery.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-08 - Verify present-but-wedged camera recovery and request validation.
#   2026-09-05 - Added isolated helper enrollment, hub-move and reset tests.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify root-helper enrollment and guarded hub recovery in a temporary tree."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "powerglove_camera_recovery_helper",
    ROOT / "uno-q" / "powerglove-camera-recovery.py",
)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class UnoQCameraRecoveryHelperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.driver = self.root / "driver"
        self.driver.mkdir()
        (self.driver / "unbind").touch()
        (self.driver / "bind").touch()
        self.lock = self.root / "lock"
        self.stamp = self.root / "stamp"
        self.config = self.root / "camera.json"
        self.request = self.data / "camera-recovery-request"
        self.usb_devices = self.root / "usb-devices"
        self.usb_devices.mkdir()
        self.patchers = [
            patch.object(helper, "APP_DATA", self.data),
            patch.object(helper, "REQUEST", self.request),
            patch.object(helper, "USB_DEVICES", self.usb_devices),
            patch.object(helper, "USB_DRIVER", self.driver),
            patch.object(helper, "CONFIG", self.config),
            patch.object(helper, "LOCK", self.lock),
            patch.object(helper, "STAMP", self.stamp),
            patch.object(helper, "_config_is_secure", return_value=True),
            patch.object(helper.os, "geteuid", return_value=0),
            patch.object(helper.time, "sleep"),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def device(self, name):
        path = self.root / name
        (path / "power").mkdir(parents=True)
        (path / "power" / "control").write_text("auto")
        return path

    def discovery(self, camera, hub, camera_id=("1532", "0e05"), hub_id=("0bda", "0411")):
        return {
            "camera": {"vendor_id": camera_id[0], "product_id": camera_id[1], "name": "Test camera"},
            "hub": {
                "vendor_id": hub_id[0],
                "product_id": hub_id[1],
                "name": "Test hub",
                "sysfs_name": hub.name,
            },
            "camera_path": camera,
            "hub_path": hub,
        }

    def install_hub_link(self, hub, hub_id=("0bda", "0411")):
        (hub / "idVendor").write_text(hub_id[0])
        (hub / "idProduct").write_text(hub_id[1])
        (hub / "bDeviceClass").write_text("09")
        (self.usb_devices / hub.name).symlink_to(hub)

    def test_discovers_one_video_camera_and_its_nearest_external_hub(self):
        devices = self.root / "sys-devices" / "usb2"
        hub = devices / "2-1"
        camera = hub / "2-1.4"
        interface = camera / "2-1.4:1.0"
        video = interface / "video4linux" / "video1"
        video.mkdir(parents=True)
        for device, identity, device_class, product in (
            (hub, ("0bda", "0411"), "09", "Example powered hub"),
            (camera, ("046d", "0825"), "ef", "Example UVC camera"),
        ):
            (device / "idVendor").write_text(identity[0])
            (device / "idProduct").write_text(identity[1])
            (device / "bDeviceClass").write_text(device_class)
            (device / "product").write_text(product)
        (video / "index").write_text("0")
        (video / "name").write_text("Example UVC camera: Capture")
        (video / "device").symlink_to(interface)
        video_class = self.root / "video-class"
        video_class.mkdir()
        (video_class / "video1").symlink_to(video)
        with patch.object(helper, "VIDEO_CLASS", video_class):
            discovered = helper._discover_cameras()
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0]["camera"]["vendor_id"], "046d")
        self.assertEqual(discovered[0]["hub"]["sysfs_name"], "2-1")

    def test_installer_defers_enrollment_when_camera_is_absent(self):
        with patch.object(helper, "_discover_cameras", return_value=[]):
            self.assertEqual(helper.main(["--configure-if-present"]), 0)
        self.assertFalse(self.config.exists())

    def test_first_healthy_camera_is_enrolled_and_kept_awake(self):
        camera = self.device("2-1.4")
        hub = self.device("2-1")
        self.request.write_text("enroll\n")
        with patch.object(helper, "_discover_cameras", return_value=[self.discovery(camera, hub)]):
            self.assertEqual(helper.main([]), 0)
        saved = json.loads(self.config.read_text())
        self.assertEqual(saved["camera"]["vendor_id"], "1532")
        self.assertEqual(saved["hub"]["sysfs_name"], "2-1")
        self.assertEqual((camera / "power" / "control").read_text(), "on")
        self.assertEqual((hub / "power" / "control").read_text(), "on")
        self.assertEqual((self.driver / "unbind").read_text(), "")

    def test_healthy_camera_moved_to_another_hub_updates_enrollment(self):
        old_camera = self.device("2-1.4")
        old_hub = self.device("2-1")
        helper._write_config(self.discovery(old_camera, old_hub))
        new_camera = self.device("4-2.3")
        new_hub = self.device("4-2")
        self.request.write_text("enroll\n")
        with patch.object(helper, "_discover_cameras", return_value=[self.discovery(new_camera, new_hub)]):
            self.assertEqual(helper.main([]), 0)
        self.assertEqual(json.loads(self.config.read_text())["hub"]["sysfs_name"], "4-2")

    def test_absent_camera_resets_only_the_last_observed_hub(self):
        hub = self.device("2-1")
        camera = self.device("2-1.4")
        self.install_hub_link(hub)
        discovery = self.discovery(camera, hub)
        helper._write_config(discovery)
        self.request.write_text("recover\n")
        with patch.object(helper, "_discover_cameras", side_effect=[[], [discovery]]):
            self.assertEqual(helper.main([]), 0)
        self.assertEqual((self.driver / "unbind").read_text(), "2-1")
        self.assertEqual((self.driver / "bind").read_text(), "2-1")
        self.assertEqual((camera / "power" / "control").read_text(), "on")

    def test_enumerated_camera_with_failed_stream_resets_its_hub(self):
        hub = self.device("2-1")
        camera = self.device("2-1.4")
        self.install_hub_link(hub)
        discovery = self.discovery(camera, hub)
        helper._write_config(discovery)
        self.request.write_text("recover\n")
        with patch.object(helper, "_discover_cameras", side_effect=[[discovery], [discovery]]):
            self.assertEqual(helper.main([]), 0)
        self.assertEqual((self.driver / "unbind").read_text(), "2-1")
        self.assertEqual((self.driver / "bind").read_text(), "2-1")

    def test_enumerated_camera_for_enrollment_is_not_reset(self):
        hub = self.device("2-1")
        camera = self.device("2-1.4")
        discovery = self.discovery(camera, hub)
        self.request.write_text("enroll\n")
        with patch.object(helper, "_discover_cameras", return_value=[discovery]):
            self.assertEqual(helper.main([]), 0)
        self.assertEqual((self.driver / "unbind").read_text(), "")

    def test_unknown_request_action_is_rejected_after_consumption(self):
        self.request.write_text("reset-everything\n")
        with self.assertRaisesRegex(RuntimeError, "unknown action"):
            helper.main([])
        self.assertFalse(self.request.exists())

    def test_refuses_hub_when_identity_at_saved_path_has_changed(self):
        hub = self.device("2-1")
        camera = self.device("2-1.4")
        self.install_hub_link(hub, ("1234", "5678"))
        helper._write_config(self.discovery(camera, hub))
        self.request.write_text("recover\n")
        with patch.object(helper, "_discover_cameras", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "absent or has changed identity"):
                helper.main([])
        self.assertEqual((self.driver / "unbind").read_text(), "")

    def test_refuses_ambiguous_first_use(self):
        camera = self.device("2-1.4")
        hub = self.device("2-1")
        self.request.write_text("enroll\n")
        discovery = self.discovery(camera, hub)
        with patch.object(helper, "_discover_cameras", return_value=[discovery, discovery]):
            with self.assertRaisesRegex(RuntimeError, "expected one UVC camera"):
                helper.main([])
        self.assertFalse(self.config.exists())


if __name__ == "__main__":
    unittest.main()
