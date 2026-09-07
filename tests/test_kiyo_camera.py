# Project: PowerGlove Vision
# File: tests/test_kiyo_camera.py
# Purpose: Verify narrow Kiyo controls and opt-in camera configuration.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Test descriptor bounds, HDR command, exposure verification, and camera identity.
# Full history: docs/CHANGELOG.md and Git history.

"""Camera commands must be bounded, model-specific, and never save onboard."""

import ctypes
from pathlib import Path
import runpy
import struct
import tempfile
import unittest
from unittest.mock import patch

from powerglove_vision import kiyo_camera as kiyo
from powerglove_vision.vision_app import build_parser


class KiyoTests(unittest.TestCase):
    def test_descriptor_identity_and_invalid_lengths(self):
        descriptor=bytes([20,0x24,6,7])+kiyo.GUID
        self.assertEqual(kiyo.extension_unit(bytes([2,1])+descriptor),7)
        for data in (b'',b'\0\1',b'\x20\x24',bytes([20,0x24,6,7])+bytes(16)):
            with self.assertRaises(ValueError): kiyo.extension_unit(data)

    def test_only_hdr_off_and_standard_exposure_commands_are_sent(self):
        commands=[]
        def ioctl(fd,request,data):
            if isinstance(data,kiyo.ExtensionQuery):
                if data.query==0x85: ctypes.c_uint16.from_address(data.data).value=8
                else: commands.append(ctypes.string_at(data.data,data.size))
            elif request==0xc008561c: commands.append(struct.unpack('Ii',data))
            else:
                control,_=struct.unpack('Ii',data)
                struct.pack_into('i',data,4,3 if control==kiyo.AUTO_EXPOSURE else 0)
        kiyo.apply_controls(3,7,ioctl)
        self.assertEqual(commands,[bytes.fromhex('ff02000000000000'),(kiyo.AUTO_EXPOSURE,3),(kiyo.DYNAMIC_FRAMERATE,0)])

    def test_unexpected_control_length_never_writes(self):
        for size in (0,7,65,65535):
            calls=[]
            def ioctl(fd,request,data):
                calls.append(data.query)
                ctypes.c_uint16.from_address(data.data).value=size
            with self.assertRaises(ValueError): kiyo.apply_controls(3,7,ioctl)
            self.assertEqual(calls,[0x85])

    def test_other_cameras_are_not_opened_for_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            usb=Path(directory);(usb/'idVendor').write_text('1234');(usb/'idProduct').write_text('0e05')
            camera=usb/'video4linux';camera.mkdir();(camera/'video2').mkdir()
            with patch.object(kiyo.sys,'platform','linux'), patch.object(kiyo.os,'open') as opened:
                self.assertFalse(kiyo.configure_kiyo('/dev/video2',camera))
                opened.assert_not_called()

    def test_controls_stay_opt_in_and_supervisor_passes_config(self):
        args=build_parser().parse_args(['--receiver','test','--token','x'*16])
        self.assertEqual(args.camera_buffers,1);self.assertFalse(args.kiyo_hdr_off)
        root=Path(__file__).resolve().parents[1]
        command=runpy.run_path(str(root/'python/main.py'))['worker_command']
        original=command({},Path('/tmp/model'))
        self.assertNotIn('--camera-buffers',original);self.assertNotIn('--kiyo-hdr-off',original)
        candidate=command({'camera_buffers':2,'kiyo_hdr_off':True},Path('/tmp/model'))
        self.assertEqual(candidate[candidate.index('--camera-buffers')+1],'2')
        self.assertIn('--kiyo-hdr-off',candidate)
        self.assertNotIn('--inference-threads',candidate)
