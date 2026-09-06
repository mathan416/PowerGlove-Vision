# Project: PowerGlove Vision
# File: tests/test_connectivity_background.py
# Purpose: Verify nonblocking address refresh and independent, fresh host Wi-Fi health.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-06 - Cover slow DNS, newest-state sends, stale answers, and Wi-Fi independence.

"""Exercise connectivity behavior without depending on a physical wireless device."""
import json
import runpy
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from powerglove_vision.resolver import BackgroundAddress
from powerglove_vision.transport import UdpSender,decode_state
from powerglove_vision.controller_protocol import decode_message
from powerglove_vision.model import ControllerState
from powerglove_vision.wifi_status import read_wifi_status
from powerglove_vision.matrix import UnoQMatrix

ROOT=Path(__file__).resolve().parents[1]


class BackgroundTests(unittest.TestCase):
    def test_blocked_dns_does_not_block_send_or_replay_old_states(self):
        entered,release=threading.Event(),threading.Event()
        def slow(_host):
            entered.set();release.wait(2);return '192.0.2.4'
        with patch('powerglove_vision.transport.resolve_ipv4',side_effect=slow),patch('powerglove_vision.transport.socket.socket') as factory:
            sender=UdpSender('cabinet.local',55355,'test-token')
            try:
                self.assertTrue(entered.wait(1))
                started=time.monotonic()
                for n in range(100):
                    self.assertFalse(sender.send(ControllerState.released(n,1,'off',True)))
                self.assertLess(time.monotonic()-started,.1)
                factory.return_value.sendto.assert_not_called()
                release.set()
                deadline=time.monotonic()+1
                while sender.address.current()[0] is None and time.monotonic()<deadline:time.sleep(.005)
                factory.return_value.recvfrom.side_effect = BlockingIOError
                sender._peer = ('192.0.2.4',55355)
                sender.challenge = 'a'*32
                sender._hello_at = float('inf')
                self.assertTrue(sender.send(ControllerState.released(100,1,'off',True)))
                sent=factory.return_value.sendto.call_args[0]
                self.assertEqual(decode_message(sent[0],'test-token')['state']['sequence'],100)
                self.assertEqual(sent[1],('192.0.2.4',55355))
                self.assertEqual(factory.return_value.sendto.call_count,1)
            finally:release.set();sender.close()

    def test_refresh_changes_address_and_stale_failure_expires(self):
        second=threading.Event()
        count=[0]
        def resolve(_host):
            count[0]+=1
            if count[0]==1:return '192.0.2.1'
            second.set();return '192.0.2.2'
        address=BackgroundAddress('cabinet.local',resolve=resolve,refresh_seconds=.01)
        try:
            self.assertTrue(second.wait(1))
            deadline=time.monotonic()+1
            while address.current()[0]!='192.0.2.2' and time.monotonic()<deadline:time.sleep(.005)
            self.assertEqual(address.current()[0],'192.0.2.2')
            address.close()
            address.thread.join(1)
            with address.lock:address.expires=time.monotonic()-1
            self.assertIsNone(address.current()[0])
        finally:address.close()

    def test_literal_address_needs_no_background_lookup(self):
        resolver=Mock()
        address=BackgroundAddress('192.0.2.8',resolve=resolver)
        self.assertEqual(address.current()[0],'192.0.2.8')
        self.assertIsNone(address.thread)
        resolver.assert_not_called()


class WifiTests(unittest.TestCase):
    def test_host_reads_only_wireless_carrier(self):
        read=runpy.run_path(str(ROOT/'uno-q/powerglove-wifi-status.py'))['wifi_state']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ethernet=root/'eth0';ethernet.mkdir();(ethernet/'carrier').write_text('1')
            self.assertEqual(read(root),'unavailable')
            wifi=root/'wlan0';wifi.mkdir();(wifi/'wireless').mkdir();(wifi/'carrier').write_text('0')
            self.assertEqual(read(root),'disconnected')
            (wifi/'carrier').write_text('1')
            self.assertEqual(read(root),'connected')
            (wifi/'carrier').unlink();(wifi/'operstate').write_text('down')
            self.assertEqual(read(root),'disconnected')

    def test_app_rejects_stale_future_and_missing_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'wifi.json'
            self.assertEqual(read_wifi_status(path),'unavailable')
            for delta,expected in [(0,'connected'),(-16,'unavailable'),(5,'unavailable')]:
                path.write_text(json.dumps({'version':1,'state':'connected','observed_at':100+delta}))
                with patch('powerglove_vision.wifi_status.time.time',return_value=100):
                    self.assertEqual(read_wifi_status(path),expected)

    def test_wifi_pixel_does_not_depend_on_console(self):
        calls=[];matrix=UnoQMatrix(call=lambda *args:calls.append(args))
        with patch('powerglove_vision.wifi_status.read_wifi_status',return_value='connected'):
            matrix.set_attract({'matrix_attract':'off'},idle=False)
        self.assertEqual(calls[-1],('set_powerglove_attract',2,4))
        with patch('powerglove_vision.wifi_status.read_wifi_status',return_value='disconnected'):
            matrix.set_attract({'matrix_attract':'off'},idle=False)
        self.assertEqual(calls[-1],('set_powerglove_attract',2,0))
