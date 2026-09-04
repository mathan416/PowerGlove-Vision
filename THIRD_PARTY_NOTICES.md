# Third-party notices

## Google MediaPipe Hand Landmarker

The unmodified Google float16 Hand Landmarker model bundle is distributed at
`models/hand_landmarker.task` under the Apache License, Version 2.0. The full
license is included in `licenses/Apache-2.0.txt`. PowerGlove Vision's MIT license
does not replace the model's Apache 2.0 terms.

Source: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

Google's Hand Landmarker documentation links the following model card, which
states “LICENSED UNDER Apache License, Version 2.0” on page 2:
https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20%28Lite_Full%29%20with%20Fairness%20Oct%202021.pdf

Verified September 4, 2026: the bundled file is byte-for-byte identical to the
versioned official download. Size: 7,819,105 bytes. SHA-256:
`fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`.

The bundle contains `hand_detector.tflite` and `hand_landmarks_detector.tflite`.
No separate upstream NOTICE file is supplied inside that bundle. This document
is PowerGlove Vision's attribution and provenance record, not a Google-authored
NOTICE. No model modifications were made and no Google endorsement is implied.

## MediaPipe runtime

The repackaged MediaPipe wheel retains its upstream Apache 2.0 license inside
the wheel. Its modifications and checksums are described in
[Third-party runtime components](docs/THIRD_PARTY_COMPONENTS.md).

## Optional modified Nestopia core

`lr-nestopia-powerglove` is a modified build of the libretro Nestopia core,
licensed under the GNU General Public License, version 2. It is not covered by
PowerGlove Vision's MIT license. Ordinary release packages provide a pinned
source-build recipe and the local patch rather than a compiled core. The
downloaded upstream source supplies its full `COPYING` text and author notices;
the local core installer copies that license beside the installed binary.

Upstream: https://github.com/libretro/nestopia

Pinned revision: `5a1cd378cb46ca9ccc2dd6f8b2b6a79ab986052e`

Modification and distribution details are recorded in
[`native/nestopia-powerglove/README.md`](native/nestopia-powerglove/README.md)
and [Third-party runtime components](docs/THIRD_PARTY_COMPONENTS.md).
