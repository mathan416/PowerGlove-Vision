# Third-party runtime components

PowerGlove Vision's original source code and associated documentation are
licensed under the repository's MIT License. That license does not replace the
licenses or terms that apply to third-party software and model files.

## MediaPipe 0.10.18 ARM64 wheel

A wheel (`.whl`) is an installable Python package. This wheel includes
MediaPipe's compiled Linux ARM64 code, so the UNO Q does not need to build it.
The filename's `cp312-cp312` tags identify CPython 3.12 and its binary interface;
`manylinux2014_aarch64` and `manylinux_2_17_aarch64` identify compatible ARM64
Linux environments. The UNO Q uses this tracked file:

```text
python/worker-wheels/mediapipe-0.10.18-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl
```

| Property | Value |
| --- | --- |
| Component | MediaPipe 0.10.18 for CPython 3.12, Linux ARM64 |
| Upstream project | <https://github.com/google-ai-edge/mediapipe> |
| Upstream package | <https://pypi.org/project/mediapipe/0.10.18/> |
| License | Apache License 2.0 |
| PowerGlove repack SHA-256 | `f2617c0960eb35aaa58b76076a9ae629edbf7ec8901d5fab4b046c28d13fbe8d` |
| Original PyPI wheel SHA-256 | `09cbf7dc1f9a2deeaaac687e5f982836623def4cbd3e827d95f86f42450d2dd1` |

### Modification notice

PowerGlove Vision repackaged the upstream wheel for its headless UNO Q worker.
The Python package code and compiled MediaPipe binaries were not modified. The changes listed below were made when repackaging the wheel, and its
`RECORD` file was rebuilt to reflect them:

  - The `jax` dependency declaration was removed.
  - The `jaxlib` dependency declaration was removed.
  - The `opencv-contrib-python` dependency was replaced with `opencv-contrib-python-headless==4.10.0.84`.
  - The upstream wheel's empty `mediapipe.libs` directory was omitted.

These changes avoid unnecessary JAX installation and GUI OpenCV dependencies
on the UNO Q. The repacked wheel retains MediaPipe's Apache 2.0 license at
`mediapipe-0.10.18.dist-info/LICENSE`. Do not substitute the upstream wheel
without retesting dependency resolution, camera startup, and hand tracking.

## Google Hand Landmarker model

PowerGlove Vision uses Google's float16 Hand Landmarker task bundle.

| Property | Value |
| --- | --- |
| UNO Q runtime path | `data/models/hand_landmarker.task` |
| Official download | <https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task> |
| SHA-256 | `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` |
| Size | 7,819,105 bytes |

The unmodified model is preserved in `models/hand_landmarker.task` and included
in the App Lab installation ZIP. Its Apache 2.0 license is in
`licenses/Apache-2.0.txt`; [third-party notices](../THIRD_PARTY_NOTICES.md) record
its source, checksum, and licensing evidence. Google's official Hand Landmarker
[documentation](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker)
links a [model card](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20%28Lite_Full%29%20with%20Fairness%20Oct%202021.pdf)
that explicitly states Apache License, Version 2.0 on page 2. The project's MIT
license does not replace that license. No model modifications were made.

When vision is first activated, the application verifies and copies the bundled
model into private, persistent `data/models/`. A verified cached copy is reused.
A damaged cache is replaced from the bundle; a damaged bundle is rejected.
Google's pinned download is used only when no bundled model is available.
**Gestures off** does not open or install the model. Wi-Fi deployments preserve
`data/` and include the bundled recovery copy. The model therefore does not
require internet access in a complete installation package; Python and other
first-install dependencies may still require downloads.

`scripts/fetch-runtime-assets.sh` follows the same bundled-first policy and
verifies the pinned checksum before installing the private cached copy.
`models/SHA256SUMS` records the preserved model's digest. Keep the model, license,
notices, and checksum together in backups. Store a copy of the recovery archive
on another drive or in your regular off-machine backup; copies on the same Mac
do not protect against loss of that Mac.

## Documentation illustration provenance

The gesture sheets under `docs/images/gestures/` were generated on September 3,
2026 with OpenAI's image-generation tool from project-authored prompts, then
selected and arranged for the PowerGlove Vision gameplay guide. They are
documentation assets, not runtime dependencies. No game screenshots, scans,
box art, characters, publisher logos, or other source images were supplied to
the generator.

The individual gestures and original Pixel Pal mascot under
`docs/images/gestures/v2/` were generated on September 4, 2026 with the same
built-in tool, using the project's generated contact sheet as a style reference.
Their prompts are preserved in `docs/images/gestures/v2/prompts.json`. The
earlier illustrations remain available in their original locations.

The index-curl illustration was subsequently redrawn using a user-supplied
hand photograph as its pose reference. Only the illustrated glove is included;
the reference photograph is not distributed with the project.

The repository applies its MIT License to these curated project assets to the
extent the project owner has rights in them. Game names and other third-party
marks remain the property of their respective owners.

## Updating either component

Before publishing a wheel or model update, complete these steps. The
[command reference](CONFIGURATION_REFERENCE.md#build-inspect-or-maintain-project-files)
explains the build and verification scripts.

  1. Record the official source URL, version, license, size, and SHA-256 here.
  2. Update the pinned values in `src/powerglove_vision/runtime_assets.py`, `scripts/fetch-runtime-assets.sh`, `scripts/verify-app-lab-package.py`, and `models/SHA256SUMS` when changing the model.
  3. If repackaging another wheel, record every difference from upstream and retain its license files.
  4. Build the App Lab installation ZIP and confirm it contains one wheel, the verified model, its license and notices, and only the root `sketch/` application sketch.
  5. Test first-launch offline model installation, download fallback, and checksum verification, background preloading with capture off, first activation after reboot, camera initialization, tracking, the Glove Academy and Dashboard pages, and controller output on the UNO Q before publishing the package.

### Application screenshots

The interface screenshots in `docs/images/` were refreshed from the running
PowerGlove Vision application on September 4, 2026. They cover Dashboard, Glove Academy,
Tune, Setup, Games, and Help. Camera imagery is blurred for privacy; gesture
illustrations remain unchanged. These screenshots are project documentation
assets and add no runtime dependencies.

## Verified UNO Q sketch toolchain

The September 4, 2026 sketch build and firmware deployment used the pinned
`sketch/sketch.yaml`: Arduino Zephyr platform **1.0.0**, Arduino_RouterBridge
**0.4.3**, Arduino_RPClite **0.3.0**, ArxContainer **0.7.0**, ArxTypeTraits
**0.3.2**, DebugLog **0.8.4**, and MsgPack **0.4.2**. The build resolved
Arduino_LED_Matrix **0.1.3** from that platform. Preserve the dependency pins when
synchronizing with App Lab; its shortened generated configuration is not a
replacement for the project's complete configuration. Revalidate compilation
and device operation before changing a pin.
