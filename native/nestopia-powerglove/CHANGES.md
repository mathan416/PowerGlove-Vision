# PowerGlove Vision changes to Nestopia

This is an additive modification ledger for the separately named
`lr-nestopia-powerglove` core. It does not replace Nestopia's own source-file
headers, copyright notices, Git history, or `COPYING` file.

## Upstream baseline

| Property | Value |
| --- | --- |
| Project | libretro Nestopia |
| Repository | <https://github.com/libretro/nestopia> |
| Revision | `5a1cd378cb46ca9ccc2dd6f8b2b6a79ab986052e` |
| License | GNU General Public License, version 2 or later as stated by the affected Nestopia source |
| Patch | `native/nestopia-powerglove/nestopia-powerglove.patch` |
| Patch SHA-256 | `6a4318673085eb4eeda3ec84da1f905cf48c8d0e5ed1a07f0d644eb0860622ec` |

At that revision, `source/core/input/NstInpPowerGlove.cpp` begins with
Nestopia's original 2003–2008 Martin Freij copyright and GPL notice. The patch
starts after that complete header and leaves it byte-for-byte unchanged.
`libretro/libretro.cpp` has no file-level copyright or license header at the
pinned revision; the patch leaves its opening includes intact and does not add
a substitute PowerGlove Vision ownership header.

For provenance, the unmodified upstream files have these SHA-256 values:

- `libretro/libretro.cpp`:
  `3e6356e56d1c25e2266be155ea2a0a3155d971e60eecba946026422957f5a25f`
- `source/core/input/NstInpPowerGlove.cpp`:
  `7328ab1cc9cc902ac129d217c4d47faa247d2d6e7d41b8d8ac7eb634c097e7cd`

## PowerGlove Vision modifications — September 4, 2026

Changes in `libretro/libretro.cpp`:

- Added the read-only, versioned PowerGlove Vision latest-sample structure.
- Added coherent-record, profile, calibration, detection, and 250 ms freshness
  validation with neutral behavior for invalid input.
- Registered a separately selectable `Power Glove Vision` libretro controller.
- Connected the existing Nestopia Power Glove device and supplied calibrated
  X/Y plus confirmed Start and Select state through its callback.
- Kept Z, wrist, gesture, finger, and unconfirmed button fields neutral.
- Identified the core as `Nestopia PowerGlove` without changing stock Nestopia.
- Closed the mapped state and removed the callback when a game unloads.

Changes in `source/core/input/NstInpPowerGlove.cpp`:

- Enabled an opt-in native path only when `POWERGLOVE_NATIVE_STATE` is present.
- Used the exact-ROM-confirmed ten-byte Super Glove Ball stream in native mode
  while retaining Nestopia's original twelve-byte behavior otherwise.
- Added opt-in controller-write, returned-bit, packet, and cadence diagnostics
  under `POWERGLOVE_TRACE`.
- Recorded byte-boundary strobes used by the exact ROM without changing their
  ordinary latch processing.

Evidence-driven corrections:

- Corrected camera-to-Nestopia Y orientation after cabinet testing showed that
  the earlier host-side negation inverted physical up and down.
- Kept unknown packet fields neutral and retained the explicit FCEUmm fallback.

## Preservation rule

Future changes must remain in the local patch and be appended to this ledger.
Do not replace or prepend project ownership text over an upstream file header.
Keep upstream author notices and license files in source distributions and
beside installed or distributed core binaries. The build verifies the protected
Nestopia Power Glove header after applying the patch and stops if it changed.
