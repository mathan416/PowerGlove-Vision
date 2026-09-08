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
from powerglove_vision import camera_controls
from powerglove_vision.vision_app import _camera_rate_attempts, build_parser


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
        self.assertEqual(candidate[candidate.index('--camera-exposure')+1],
                         'kiyo-low-latency')
        self.assertEqual(candidate[candidate.index('--inference-threads')+1], '4')
        self.assertEqual(candidate[candidate.index('--tracking-confidence')+1], '0.4')
        self.assertEqual(candidate[candidate.index('--fps')+1], '0')
        tuned=command({'tracking_confidence':.45},Path('/tmp/model'))
        self.assertEqual(tuned[tuned.index('--tracking-confidence')+1], '0.45')
        self.assertEqual(command({'camera_fps':30},Path('/tmp/model'))[
            command({'camera_fps':30},Path('/tmp/model')).index('--fps')+1], '30')
        self.assertEqual(command({'camera_fps':25},Path('/tmp/model'))[
            command({'camera_fps':25},Path('/tmp/model')).index('--fps')+1], '0')
        direct=command({'camera_backend':'direct-v4l2',
                        'camera_exposure':'low-latency',
                        'tracker_graph':'lean-image'},Path('/tmp/model'))
        self.assertEqual(direct[direct.index('--capture-backend')+1], 'direct-v4l2')
        self.assertEqual(direct[direct.index('--camera-exposure')+1], 'low-latency')
        self.assertEqual(direct[direct.index('--tracker-graph')+1], 'lean-image')

    def test_standard_low_latency_controls_are_queried_before_writes(self):
        values={camera_controls.EXPOSURE_AUTO:3,
                camera_controls.EXPOSURE_AUTO_PRIORITY:1}
        writes=[]
        def ioctl(_fd,request,data):
            control=struct.unpack_from('I',data,0)[0]
            if request==camera_controls.VIDIOC_QUERYCTRL:
                struct.pack_into('II',data,0,control,1)
                data[8:16]=b'exposure'
                struct.pack_into('iiii',data,40,0,3,1,1)
                struct.pack_into('I',data,56,0)
            elif request==camera_controls.VIDIOC_S_CTRL:
                _,value=struct.unpack('Ii',data);values[control]=value;writes.append((control,value))
            elif request==camera_controls.VIDIOC_G_CTRL:
                struct.pack_into('i',data,4,values[control])
        with patch.object(camera_controls.sys,'platform','linux'), \
             patch.object(camera_controls.os,'open',return_value=7), \
             patch.object(camera_controls.os,'close'):
            report=camera_controls.configure_low_latency('/dev/video2',ioctl)
        self.assertTrue(report['applied'])
        self.assertEqual(writes,[(camera_controls.EXPOSURE_AUTO,3),
                                 (camera_controls.EXPOSURE_AUTO_PRIORITY,0)])

    def test_unsupported_standard_controls_never_write(self):
        writes=[]
        def ioctl(_fd,request,_data):
            if request==camera_controls.VIDIOC_QUERYCTRL:raise OSError('unsupported')
            writes.append(request)
        with patch.object(camera_controls.sys,'platform','linux'), \
             patch.object(camera_controls.os,'open',return_value=7), \
             patch.object(camera_controls.os,'close'):
            report=camera_controls.configure_low_latency('/dev/video9',ioctl)
        self.assertFalse(report['supported']);self.assertEqual(writes,[])

    def test_every_camera_rate_falls_back_to_driver_negotiation(self):
        self.assertEqual(_camera_rate_attempts(0), (30, None))
        self.assertEqual(_camera_rate_attempts(30), (30, None))
        self.assertEqual(_camera_rate_attempts(60), (60, None))
