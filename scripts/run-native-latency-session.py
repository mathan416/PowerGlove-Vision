#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/run-native-latency-session.py
# Purpose: Guide repeatable stationary and movement windows with read-only status collection.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Add operator-paced native latency session evidence.
# Full history: docs/CHANGELOG.md and Git history.

"""Coordinate an external recording; never start controls, change settings, or open a camera."""
import argparse
import importlib.util
import json
import threading
import time
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('status_measurement', Path(__file__).with_name('measure-vision-status.py'))
measurement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measurement)


def collect_window(url, output, label, phase, seconds):
    """Keep operator cues separate from telemetry and from the video's clock."""
    print('\n%s: %d seconds. Start external recording before continuing.' % (label, seconds))
    input('Press Enter when framed and ready (Ctrl-C cancels): ')
    for remaining in (3, 2, 1):
        print(remaining, flush=True)
        time.sleep(1)
    result = []
    thread = threading.Thread(target=lambda: result.append(measurement.collect(url, seconds, .05, phase)))
    thread.start()
    started = time.monotonic()
    if phase == 'movement':
        for trial in range(10):
            time.sleep(max(0, started + trial * 6 - time.monotonic()))
            print('%s %d/10: %s step, then hold' % (label, trial+1, 'SHORT' if trial < 5 else 'LONG'), flush=True)
            time.sleep(max(0, started + trial * 6 + 3 - time.monotonic()))
            print('Return to center and hold', flush=True)
    else:
        print('Hold an open hand still; support your forearm if practical.', flush=True)
    thread.join()
    report = result[0]
    report['window_label'] = label
    report['cue_clock'] = 'Mac local pacing only; not synchronized to video or device clocks'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print('Finished: %d fresh samples, %d request errors.' % (report['observed_samples'], report['request_errors']))
    if not report['observed_samples']:
        raise RuntimeError('No active samples; verify delivery and status before continuing')
    if phase == 'neutral' and (len(report['segments']) != 1 or not report['segments'][0]['stationary_candidate']):
        print('REPEAT NEEDED: tracking/calibration/conditions or gesture checks failed. Video review is also required.')


def main():
    """Create one new local session directory and ask before each physical window."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status-url', type=measurement.status_url, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    print('Preflight: native core/device 517; active player and calibration; Robo-Glove follows hand;')
    print('preview CLOSED; stable lighting; same game conditions; original hand+screen video framing checked.')
    print('Verify software identities and effective per-game video overrides separately. No configuration is changed.')
    for index in range(1, 4):
        label = 'neutral-%d' % index
        collect_window(args.status_url, args.output_dir / (label+'.json'), label, 'neutral', 20)
    for direction in ('left', 'right', 'up', 'down'):
        collect_window(args.status_url, args.output_dir / (direction+'.json'), direction, 'movement', 60)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
