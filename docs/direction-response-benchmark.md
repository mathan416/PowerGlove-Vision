# Direction-response benchmark

This deterministic headless benchmark compares the same exact Super Glove Ball
ROM through its native packet path and its conventional FCEUmm joystick path.
Gun.Smoke remains available as an optional positional-FCEUmm reference. This is
a software validation tool, not a substitute for camera, display, or physical
cabinet testing.

## Reproducible inputs

| Lane | Core | Exact game image |
| --- | --- | --- |
| Native coordinates | `Nestopia PowerGlove` built from pinned Nestopia revision `5a1cd378cb46ca9ccc2dd6f8b2b6a79ab986052e` plus the repository patch | `Super Glove Ball (USA)`, SHA-256 `ad60ef1b62cd1b3bc02a9320376067347a8ab2ebbe46e1616693d8379c9d9a7b` |
| Standard joystick | Stock `FCEUmm` revision `236ccdfc911e84c60fea6b9d0699c2d440a8de14` | The same exact `Super Glove Ball (USA)` image |
| Optional standard-D-pad reference | The same stock `FCEUmm` revision | `Gun.Smoke (USA)`, SHA-256 `4ad9629a2bacc158a7f50975869c7dfe533567ae399a5bdc5df2240286df259f` |

ROMs stay outside the project and every result is tied to its digest.
Gun.Smoke uses the positional Program G mapping, making it a useful second
FCEUmm exercise of the shared camera-direction recognition when supplied.

## Method

The runner boots each exact ROM into play and saves one emulator state. For
each direction it restores that same state twice: once for the baseline and
once with only the candidate input changed. It records the first emulated video
frame whose checksum differs. Release uses the same comparison after eight
frames of held input: continuing the hold is the baseline and returning to
neutral is the sole change.

FCEUmm also records whether the libretro input callback was polled on the first
changed frame and which input-device API it requested. For Super Glove Ball it
requested only libretro device `1`, the standard joypad, confirming that the
native state file is not part of that lane. The native lane publishes one
coherent state immediately before every emulated frame; the custom core's packet
trace is the separate evidence that this state is sampled once per frame. The shared recognition check proves
all four directions activate at `0.29` normalized displacement and release at
`0.13`, on the responsive side of the configured `0.28`/`0.14` boundaries.
It also drives the adaptive native coordinate filter directly. A large X/Y
change must use the strongest follow rate immediately, reach at least 90% of
its target within 150 ms, and preserve the bounded neutral-jitter check.

## Results

Three complete executions produced byte-identical reports.

| Lane | Directions | First visible activation | First visible release | First-frame input pickup |
| --- | --- | --- | --- | --- |
| Super Glove Ball / `lr-nestopia-powerglove` | Left, right, up, down | Frame 3, about 50.0 ms at 60 Hz | Frame 3, about 50.0 ms at 60 Hz | Native state published before frame; per-frame packet consumption established by the trace runner |
| The same Super Glove Ball ROM / stock FCEUmm | Left, right, up, down | Frame 3, about 50.0 ms at 60 Hz | Frame 3, about 50.0 ms at 60 Hz | Standard joypad callback polled on frame 1; no native packet input |
| Gun.Smoke / stock FCEUmm reference | Left, right, up, down | Frame 2, about 33.3 ms at 60 Hz | Frame 2, about 33.3 ms at 60 Hz | Standard joypad callback polled on frame 1 |

The native positive-X sweep also diverged on frame 3 at every tested magnitude:
`1024`, `2048`, `4096`, `8192`, `16384`, and `32767`. The smallest step is
about 3.1% of the positive signed coordinate range, so the test demonstrates
continuous small-motion response rather than only edge-to-edge movement.

The same-ROM visual comparison exposed and corrected a native Y-axis wrapping
error that a checksum-only test had missed. The corrected trace now returns
`$80`, `$00`, and `$7F` for Y minimum, center, and maximum, and the corresponding
screens place the Robo-Glove at bottom, center, and top. Conventional FCEUmm
directions also reach their matching screen edges, but they do so as held digital
commands; native coordinates specify an absolute target position. This is the
substantive gameplay difference between the two modes even though their first
visible response occurs on the same emulated frame in this ROM.

These numbers are the first input-caused *visible* frame, not a camera-to-screen
wall-clock claim. Camera capture cadence, the 75 ms Academy polling interval,
display buffering, and physical display latency are intentionally outside this
headless core benchmark.

The Dashboard now reports rolling camera-read-to-send and changed-control-to-send
p50/p95 measurements. Those cover the UNO Q software stage for both FCEUmm and
native X/Y. Receiver publication and the core's next-frame consumption remain
separate stages: the coherent native record timestamps its RetroPie arrival,
and the headless core benchmark publishes the changed record immediately before
an emulated frame.

## Repeatable camera comparison

`scripts/record-vision-benchmark.py` records a temporary local 30-second cue
sequence containing full-field and short movement, neutral jitter, A/B, rolls,
Closed Hand, push, pull, tracking recovery, and near/far poses. The companion
`scripts/benchmark-vision-replay.py` runs the same full frames through MediaPipe
Hands with 1, 2, and 4 inference threads, plus MediaPipe Tasks Video when its
model is supplied. Each runs at 640×480 and a full-field 512×384 resize with
preview work both closed and open; neither resolution crops the image.

The replay report includes inference p50/p95, detection continuity, cue
recognition, first recognition within each cue, neutral false activations,
coordinate jitter, and preview cost. Live Dashboard readings remain authoritative
for latest-camera-frame age because an offline replay has no live capture queue.
The temporary AVI and cue sidecar must be deleted after aggregate conclusions
are retained. The proven 640×480 configuration remains the default unless a
candidate improves p95 by at least 15%, introduces no neutral false activation,
meets the response targets, and loses no more than one percentage point of
labeled recognition.

For a user-paced capture, `scripts/guided-vision-benchmark.py` serves a temporary
live camera page. Nothing is recorded while the player frames a pose. Selecting
**Record this step** starts a two-second countdown and records only that labeled
step; the player decides when to continue. The completed camera source remains
local and releases the camera automatically. A fixed-duration subset may then
be sampled from those confirmed steps for repeatable replay. Guided capture is
diagnostic evidence, not training data or an automatic part of Glove Academy.

### Preliminary UNO Q steady-state timing

After deploying 0.3.2-dev on September 5, 2026, two controller-off 300-sample
smoke-test windows exercised the current MediaPipe Hands configuration at
640×480. These validate the camera, inference, state calculation, telemetry,
and preview isolation; they do not replace the labeled clip or console tests.

| Preview state | Recognition rate | Inference p50 / p95 | Camera read to decision p50 / p95 |
| --- | ---: | ---: | ---: |
| Dashboard closed | 11.4 Hz | 87.9 / 98.4 ms | 109.6 / 127.9 ms |
| Dashboard stream open | 11.8 Hz | 88.0 / 97.6 ms | 108.2 / 125.7 ms |

The preview-open window did not materially increase p95. Controller delivery
was intentionally stopped, so no changed-control-to-send samples were recorded;
that metric requires the authenticated RetroPie receiver during the live test.

### Guided replay result — September 5, 2026

A player-confirmed guided session recorded 1,575 frames across 52 seconds at an
effective 30.29 fps. A 30-second comparison subset retained the first two seconds
of every labeled step at 15 fps, giving all 16 lanes the same 450 source frames
and 67 ms temporal resolution. The complete guided source was preserved while
the comparison ran.

| Backend and full-frame size | Threads | Preview | Inference p50 / p95 | Detection continuity | Neutral false frames |
| --- | ---: | --- | ---: | ---: | ---: |
| MediaPipe Hands, 640×480 | 1 | Closed | 96.51 / 207.60 ms | 71.33% | 14 |
| MediaPipe Hands, 640×480 | 2 | Closed | 92.94 / 217.40 ms | 71.33% | 14 |
| MediaPipe Hands, 640×480 | 4 | Closed | 98.60 / 190.18 ms | 71.33% | 14 |
| MediaPipe Tasks Video, 640×480 | 1 | Closed | 184.55 / 403.13 ms | 82.89% | 44 |
| MediaPipe Hands, 512×384 | 4 | Closed | 97.37 / 213.53 ms | 72.67% | 60 |
| MediaPipe Tasks Video, 512×384 | 1 | Closed | 183.85 / 401.05 ms | 81.11% | 43 |
| MediaPipe Hands, 640×480 | 4 | Open | 99.45 / 190.36 ms | 71.33% | 14 |
| MediaPipe Tasks Video, 640×480 | 1 | Open | 187.21 / 382.52 ms | 82.89% | 44 |

Tasks Video recovered difficult A, B, and Closed Hand poses that the proven
backend missed in the selected windows, but approximately doubled median
inference time and exceeded the gameplay latency target decisively. The
512×384 resize did not improve p95 by the required 15%; it increased neutral
false activations and weakened roll recognition. Thread count did not change
recognition, and no alternative produced a consistent qualifying latency gain.
The deployed choice therefore remains **MediaPipe Hands (proven)** at 640×480
with four inference threads. Preview encoding at that size measured about 9.6 ms
p95 and did not materially increase inference p95.

The replay deliberately saturates inference and produced higher tail latency
than real-time capture. The live steady-state p95 measurements above remain the
authoritative gameplay-stage values. Replay is used for relative comparisons
and identical-frame recognition evidence.

The guided source also documented a difficult backlit scene. Mean luma was
approximately 77–79 on a 0–255 scale and 34–38% of pixels were below luma 32.
The camera was already using automatic exposure. Its hardware backlight
compensation made a reversible still-image test slightly darker, while restoring
brightness and contrast to factory defaults helped only modestly. No camera
control was promoted globally. Front lighting or moving the bright window out
of the background is the safer remedy because forced exposure can add motion
blur and reduce the stable frame rate.

## Run it again

Build the two isolated benchmark cores:

```sh
scripts/build-nestopia-powerglove.sh
scripts/build-fceumm-benchmark.sh
```

Then supply external paths to the exact ROMs:

```sh
python3 scripts/benchmark-direction-response.py \
  --nestopia-core build/nestopia-powerglove/nestopia_powerglove_libretro.so \
  --super-glove-ball-rom "/path/to/Super Glove Ball (USA).nes" \
  --fceumm-core build/fceumm-benchmark/fceumm_libretro.so \
  --scratch /tmp/powerglove-direction-benchmark \
  --output /tmp/powerglove-direction-benchmark/result.json
```

On macOS, use the emitted `.dylib` paths instead of `.so`. Build products,
scratch state, reports, and ROMs are not release-package content. The runner's
`--fceumm-rom` option adds the optional Gun.Smoke reference lane.
