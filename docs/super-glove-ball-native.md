# Super Glove Ball native-input compatibility record

This document records evidence for the experimental `lr-nestopia-powerglove`
core. It intentionally separates observations from hypotheses. The supported
fallback is still FCEUmm using PowerGlove Vision's shared responsive D-pad and
gesture recognition.

## Evidence order

When sources disagree, use this order:

  1. The exact user-supplied Super Glove Ball ROM's input routines and control flow.
  2. Controlled emulator traces of its writes, reads, assembled bytes, and cadence.
  3. Repeatable in-game detection, out-of-range, and movement behavior.
  4. Nestopia's existing Power Glove implementation.
  5. The game manual and NESdev reverse-engineering notes.

NESdev material is a source of testable hypotheses, not a specification for this
implementation.

## Current compatibility status

| Detail | Status | Evidence or next test |
| --- | --- | --- |
| Shared camera recognition can supply continuous normalized X/Y | Confirmed in application tests | The authenticated receiver publishes the same calibrated axes used by gameplay. |
| A custom core can consume one coherent latest sample per emulated frame | Confirmed in build and unit tests | Versioned 64-byte read-only record with matching even guards; there is no queue or second smoothing stage. |
| Missing, uncalibrated, wrong-profile, or older-than-250 ms samples are neutral | Confirmed in implementation tests | The receiver also publishes a neutral record on transport timeout and shutdown. |
| The candidate core builds separately from stock Nestopia | Confirmed at pinned revision `5a1cd378cb46ca9ccc2dd6f8b2b6a79ab986052e` | Its library name is `Nestopia PowerGlove`; stock source and installed cores are not modified. |
| Candidate X/Y encoding reaches Nestopia's existing Power Glove device | Confirmed for the exact ROM | Minimum, center, and maximum X/Y each produced distinct packets. Cabinet validation corrected the camera-to-Nestopia Y orientation. |
| Detection signature, packet length, boundaries, and bit order | Confirmed | The ROM assembled inverse `$A0` as `$5F`, strobed once per byte, read ten bytes/80 bits per sample MSB first, and required the final stored byte to be `$3F`. |
| Start encoding | Confirmed | Native byte 6 value `$82` left the title screen and began play while the controller stayed in native mode. |
| Z, wrist rotation, finger state, and action-button encoding | Unknown and deliberately neutral | Vary one field at a time now that detection and X/Y are repeatable. Start is the sole confirmed button exception. |
| Poll timing tolerances | Partially confirmed | The headless run sustained ten-byte polling throughout its native phases; hardware timing margins still need cabinet validation. |
| Headless X/Y activation and release responsiveness | Confirmed for the exact ROM | All four axes visibly diverged by frame 3; a 3.1% positive-X step also diverged by frame 3. See the [direction-response benchmark](direction-response-benchmark.md). |
| Cabinet field mapping and stabilization | Confirmed for live tuning | Continuous X/Y maps each side of the calibrated neutral point to the corresponding usable camera boundary, retaining an 8% tracking margin. Light adaptive damping operates in camera space, reducing near-rest jitter without delaying deliberate travel. FCEUmm D-pad thresholds remain hand-relative and unchanged. |
| Portable defaults versus neutral calibration | Confirmed in application and installer tests | Full-field mapping, stabilization, and recognition thresholds ship in the release-owned profile baseline. The camera/player-specific neutral reference uses 24 observations at 70% confidence or better and remains private across updates. |
| Explicit FCEUmm joystick fallback for the same ROM | Confirmed | The ROM enters play using standard Start, requests only the libretro joypad callback, and activates/releases every D-pad direction visibly by frame 3. |

The validated ROM is `Super Glove Ball (USA)` with SHA-256
`ad60ef1b62cd1b3bc02a9320376067347a8ab2ebbe46e1616693d8379c9d9a7b`.
It remains outside the source tree and release packages. These results apply to
that exact image; never silently turn a NESdev assumption into a compatibility
claim for another revision.

## Confirmed exact-ROM packet

The ROM does not consume the full twelve-byte shape described by some secondary
notes. It reads this ten-byte sample, with each transmitted bit inverted by the
ROM while assembling the byte:

| Byte | Confirmed use | Neutral/test values |
| --- | --- | --- |
| 0 | Detection signature | `$A0`, assembled by the ROM as `$5F` |
| 1 | X | `$80` minimum, `$00` center, `$7F` maximum |
| 2 | Y | `$80` minimum, `$00` center, `$7F` maximum |
| 3 | Z candidate | `$00`; behavior not yet implemented |
| 4 | Roll candidate | `$00`; behavior not yet implemented |
| 5 | Finger/gesture candidate | `$00`; behavior not yet implemented |
| 6 | Button | `$FF` neutral; `$82` Start confirmed |
| 7–8 | Unknown | `$00`, preserved conservatively |
| 9 | Validation terminator | `$3F` |

The trace runner starts the exact ROM with the Power Glove attached, proves that
native `$82` Start enters play, and holds each X/Y extreme for 120 frames. The
captured screens place the Robo-Glove at left, center, right, bottom, center, and
top respectively. Tracking-lost, uncalibrated, and stale phases then prove that
the core returns X/Y center and no button instead of retaining the last sample.

## Latest-sample interface

The RetroPie receiver owns `/run/powerglove/native-state` and creates it read-only
for consumers. Format version 1 is a fixed 64-byte little-endian record containing:

  - magic, format version, record size, and matching begin/end coherence guards;
  - sample sequence and receiver-arrival monotonic timestamp;
  - signed normalized X, Y, Z, and roll axes;
  - detected and calibrated flags;
  - four finger-flex levels;
  - recognized-button mask and active-profile identifier;
  - reserved bytes that stay zero.

The writer publishes an odd in-progress guard and then an even complete guard.
The core copies one record at the beginning of its input callback and rejects it
unless both guards match and are even. It consumes only current, calibrated,
detected Super Glove Ball samples. Stale or invalid input leaves the emulated
device neutral.

## Build the research core

The build script clones the official libretro Nestopia repository at the pinned
revision into a dedicated build directory, applies the local patch, and emits
`nestopia_powerglove_libretro.so` without changing a stock installation:

```sh
scripts/build-nestopia-powerglove.sh
```

The normal RetroPie installer offers this source build when it finds a registered
Super Glove Ball ROM. Accepting installs Git and standard build tools, builds in
a temporary directory, installs the core under its separate name, copies the
upstream GPLv2 `COPYING` file beside it, and adds the native entry to the launch
menu. It deliberately leaves that ROM's current FCEUmm selection unchanged.

Set `POWERGLOVE_NATIVE_STATE` to use a test record at a different path. Set
`POWERGLOVE_TRACE=1` when launching the custom core to log controller writes,
latch/counter transitions, returned stream bits, and each candidate output
packet. Traces may contain gameplay timing but no camera imagery.

## Exact-ROM validation gate

The exact-ROM software gate below now passes for detection, Start, X/Y, and safe
neutralization. Before enabling the per-ROM emulator choice on a cabinet:

  1. Record the ROM digest and retain the ROM outside release packages.
  2. Trace controller strobes and configuration writes from power-on through the game's detection decision.
  3. Prove the detection signature, packet boundary, bit order, and polling cadence from those traces.
  4. Hold every field neutral, then vary X alone and Y alone through minimum, center, and maximum values.
  5. Confirm repeatable continuous on-screen motion and out-of-range behavior without relying on visual impression alone.
  6. Test stale samples, tracking loss, and unavailable calibration; all must immediately yield neutral native input.
  7. Build the core on the RetroPie host under the separate name `lr-nestopia-powerglove`, verify the camera-to-receiver path, and only then create the per-ROM override.

Keep an explicit FCEUmm per-ROM choice available. If native detection or tracking
regresses, remove only the per-ROM override; the shared FCEUmm fallback remains
playable.

## Compare both modes from EmulationStation

After the custom core has been installed and registered once, RetroPie's launch
menu lists both `lr-fceumm` and `lr-nestopia-powerglove` for this ROM. Choosing
`lr-fceumm` keeps the entire session in standard joystick mode: it receives the
shared Super Glove Ball profile's D-pad, A, B, Start, and Select outputs and does
not read the native-state bridge. The native entry attaches device `517` and
reads continuous coordinates instead.

The launch-menu selection for a ROM is persistent, so a test session should be
followed by choosing `lr-nestopia-powerglove` again if that is the desired saved
default. The command-line selector below performs the same reversible per-ROM
choice; neither route changes the system-wide NES emulator.

On the RetroPie host, build/install and then opt in one exact ROM:

```sh
sudo scripts/install-nestopia-powerglove.sh
sudo python3 scripts/configure-super-glove-ball-core.py \
  --rom "/home/pi/RetroPie/roms/nes/Super Glove Ball (USA).7z" \
  --mode native --apply
```

The selector writes the libretro device value `517` and also supplies
`--device=1:517` to RetroArch. The explicit launch option ensures this RetroArch
build attaches the Power Glove to port 1 before the ROM performs its detection
poll. Roll back only that ROM at any time:

```sh
sudo python3 scripts/configure-super-glove-ball-core.py \
  --rom "/home/pi/RetroPie/roms/nes/Super Glove Ball (USA).7z" \
  --mode fceumm --apply
```

For each later field—Z, rotation, one finger at a time, and one button at a
time—repeat the neutral baseline, single-variable trace, and observable-state
comparison. Preserve unknown bytes and timing behavior conservatively.
