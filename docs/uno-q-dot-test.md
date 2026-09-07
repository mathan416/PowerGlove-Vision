# PowerGlove Vision Controller direct-output dot test

Use the existing `lr-powerglove-dot` core on `retropieconsole.local` as an
optional diagnostic. No second tracker or UNO camera process is needed:

```text
UNO Q camera → existing MediaPipe / mapping / reach calibration
→ signed controller transport → cabinet receiver → /run/powerglove/native-state
→ installed dot core → RetroArch → cabinet display
```

The receiver's 64-byte PGV1 publication matches the installed core. The normal
RetroPie hook selects Super Glove Ball by the content name, independently of
emulator choice, and renews the UNO game session while RetroArch runs. The dot
ignores the ROM. Keep the existing synchronous MediaPipe path as the baseline;
do not enable experimental X/Y tracking for the initial comparison.

## Run the optional test

1. Launch Super Glove Ball through the cabinet's normal game menu. In runcommand,
   choose `lr-powerglove-dot` **for this launch**, preserving the normal emulator
   default. This retains the normal start/end hooks and UNO game session.
2. Select the intended UNO player, start the controller if paused, and verify
   calibration. Close preview. Confirm a yellow dot and `TRACKING` on the cabinet.
   Moving out of view must show `NO INPUT` and remove the dot; returning should
   restore it. If it stays absent, check game context, enabled output, calibration,
   pairing and receiver state before adjusting smoothing.
3. Film hand and cabinet together at a verified high frame rate. Hold still for
   five seconds, make three left/right and three up/down moves with one-second
   holds, then test loss and recovery separately. Preserve the original video.
4. Exit normally to finalize the installed core/receiver traces. Repeat the same
   motions with `lr-nestopia-powerglove` and unchanged player/camera settings.

The installed wrapper enables receiver tracing with a temporary service override
and restarts the receiver on entry/exit. It records for 300 seconds from launch,
stores evidence under `/home/pi/powerglove-latency-tools/sessions`, and restores
dot emulator selections on normal exit using installation-time backups. Use the
one-launch choice to avoid relying on those older selection backups. Relaunch
for a new trace window. Forced termination may leave unfinished traces or the
temporary receiver override; do not treat those files as complete evidence.

## Controller measurement tools

The existing guided session runner now supports dot-labeled status reports:

```sh
python3 scripts/run-native-latency-session.py --test dot \
  --status-url http://arduiain.local:8088/status \
  --output-dir /tmp/uno-dot-session-01
```

It waits for Enter before each physical window and collects read-only Controller
telemetry. It does not launch the game or start camera/output. The full guided
sequence plus preparation exceeds the wrapper's five-minute trace window; start
a new launch when further correlated trace evidence is needed.

For cabinet-side validity and coordinate-range observations, run the new probe
on the cabinet, while the dot is running. From a source checkout on the cabinet:

```sh
python3 scripts/measure-dot-input.py --seconds 30 --output /tmp/uno-dot-input-01.json
```

For the development deployment at `/home/pi/powerglove-latency-tools/uno-q`:

```sh
ssh retropieconsole.local 'PYTHONPATH=/opt/powerglove-src/src python3 /home/pi/powerglove-latency-tools/uno-q/measure-dot-input.py --seconds 30 --output /tmp/uno-dot-input-01.json'
```

The probe only reads the native record, using the cabinet's monotonic clock. It
reports observed validity reasons, losses/recoveries, distinct valid publications,
raw X/Y extrema and predicted dot extrema. It validates magic/version/size,
coherence guards, profile, detection, calibration and 250 ms freshness. Repeated
polls of one publication do not inflate the distinct-publication count. It exits
with status 2 when no valid input was observed, including an idle controller.
No synthetic input is written into the live receiver path.

## Interpret the result

The dot center maps to `(127,115)` by integer division, with bounds
`x=16..239`, `y=24..207` on a 256×224 canvas. The inset border is intentional;
the physical display edges are not the reach targets. It presents at NTSC
60.0988 Hz, XRGB8888, NES aspect ratio and `video_threaded=false` through the
native append config. Check additional live overrides when comparing games.

Limited raw X/Y travel suggests upstream tracking or reach mapping. Use measured
`reach_left`, `reach_right`, `reach_up`, `reach_down` for that player and camera
position. Do not copy Pi spans or camera settings: the recorded Controller capture
comparison favored 640×480 MJPEG with two buffers and HDR off; it did not prove
recognition-under-load or physical latency.

`NO INPUT` indicates failed validity, not slow pursuit. A responsive dot with a
slow game points to behavior downstream of the shared publication; it does not
uniquely isolate game code from emulator simulation. A slow dot still includes
camera buffering, processing, transport and display. Probe polls can miss brief
losses and publications, and predicted coordinates are not displayed frames.
Publication age excludes all time before receiver publication. Use the existing
[latency procedure](direction-response-benchmark.md#native-latency-and-stationary-jitter-session)
for correlated traces and original-video analysis; never subtract clocks across
computers or add independent stage percentiles.

## Setup review — September 6, 2026

The live cabinet has the dot menu entry, active receiver, native append config
and Controller launch hook. The launcher now targets `arduiain.local`, replacing the
obsolete `10.0.2.94` address. Controller status
was idle with controller output paused, so physical movement validation remains
pending. The installed core SHA-256 was
`bb6b6f209232f668604b9ed03173ed310040760f772b0a5981d3e3af06eacce1`.

Re-running the installed core's headless test on the cabinet passed all 12
rendered cases and finalized 12 trace rows with zero drops, using a temporary
synthetic record rather than the live receiver file. The new probe's one-second
live idle check observed 60 wrong-profile polls and no valid publications, as
expected with the game/controller off. Local diagnostic and native-record tests
also passed. These checks establish compatibility, not physical latency.
