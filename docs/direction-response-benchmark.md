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
