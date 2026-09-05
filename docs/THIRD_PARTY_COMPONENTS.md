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

## Modified Nestopia libretro core

The optional `lr-nestopia-powerglove` core is built from libretro Nestopia
revision `5a1cd378cb46ca9ccc2dd6f8b2b6a79ab986052e`. Nestopia identifies its
license as the GNU General Public License, version 2. PowerGlove Vision's MIT
license does not replace the license of Nestopia or the resulting modified core.

| Property | Value |
| --- | --- |
| Component | libretro Nestopia with the PowerGlove Vision native-state patch |
| Upstream project | <https://github.com/libretro/nestopia> |
| Pinned revision | `5a1cd378cb46ca9ccc2dd6f8b2b6a79ab986052e` |
| Upstream license | GNU General Public License, version 2 |
| Local modification | `native/nestopia-powerglove/nestopia-powerglove.patch` |
| Patch SHA-256 | `6a4318673085eb4eeda3ec84da1f905cf48c8d0e5ed1a07f0d644eb0860622ec` |
| Modified upstream files | `libretro/libretro.cpp`; `source/core/input/NstInpPowerGlove.cpp` |
| Modification ledger | `native/nestopia-powerglove/CHANGES.md` |
| Build recipe | `scripts/build-nestopia-powerglove.sh` |
| Built core name | `nestopia_powerglove_libretro.so` on RetroPie |
| Installed core directory | `/opt/retropie/libretrocores/lr-nestopia-powerglove/` |

Ordinary releases contain the patch and build recipe, not a compiled Nestopia
core. If the user accepts the RetroPie installer's optional native-core step,
the target machine downloads the pinned upstream source, including its author
notices and `COPYING` file, applies the patch, and builds for its own processor.
The core installer places `COPYING` and the local distribution note beside the
installed binary. It also installs the separate PowerGlove Vision modification
ledger. The original Nestopia copyright/GPL header in
`NstInpPowerGlove.cpp` remains byte-for-byte intact, and the build stops if a
future patch changes it. Stock Nestopia remains untouched and FCEUmm remains
available.

If prebuilt cores are published in the future, produce separately identified
artifacts for every tested RetroPie architecture. Accompany each binary with
the exact complete corresponding source archive used to build it, the local
patch and build instructions, all upstream notices, and the GPLv2 license. A
Git commit or patch URL alone is not the project's binary-distribution plan.
ROM images are never part of a source or binary core artifact.

At runtime, RetroArch loads the custom core only for an explicitly selected ROM.
The launch entry passes the read-only latest-sample file through
`POWERGLOVE_NATIVE_STATE`; the default path is `/run/powerglove/native-state`.
The patch registers a separately named **Power Glove Vision** controller and
identifies the library as **Nestopia PowerGlove**. Invalid, stale, uncalibrated,
lost-tracking, or wrong-profile samples are neutralized. The compatibility
record in [Super Glove Ball native compatibility](super-glove-ball-native.md)
separates exact-ROM-confirmed behavior from fields that remain unknown.

The local patch changes only `libretro/libretro.cpp` and
`source/core/input/NstInpPowerGlove.cpp`. SHA-256 values for both pristine
upstream files are recorded in the modification ledger. The build applies the
patch only after checking out the pinned commit, rejects unrelated source-tree
changes, and verifies that Nestopia's original 22-line Power Glove copyright
and GPL header remains byte-for-byte identical.

## External RetroPie emulator dependencies

PowerGlove Vision uses RetroPie-provided emulator software but does not include
those binaries in its installation archives. When either dependency is absent,
the RetroPie installer can ask the user's existing RetroPie Setup installation
to install it. That operation remains governed by RetroPie and the upstream
licenses.

| Component | PowerGlove Vision use | Upstream and license | Distribution boundary |
| --- | --- | --- | --- |
| RetroArch | Libretro frontend used to load FCEUmm and `lr-nestopia-powerglove` | [RetroArch](https://github.com/libretro/RetroArch), GPLv3 | Installed by RetroPie; not modified or redistributed by PowerGlove Vision |
| FCEUmm | Default NES core for standard D-pad/button mappings and the complete Super Glove Ball fallback | [FCEUmm](https://github.com/libretro/libretro-fceumm), GPLv2 | Stock RetroPie core; not modified or redistributed by PowerGlove Vision |

The deterministic direction benchmark separately builds stock FCEUmm revision
`236ccdfc911e84c60fea6b9d0699c2d440a8de14` in an isolated working directory.
That pin makes the benchmark reproducible; it does not replace the user's
RetroPie core, install FCEUmm, or make the benchmark binary a release artifact.

## Updating runtime components

### MediaPipe wheel or Hand Landmarker model

Before publishing a wheel or model update, complete these steps. The
[command reference](CONFIGURATION_REFERENCE.md#build-inspect-or-maintain-project-files)
explains the build and verification scripts.

  1. Record the official source URL, version, license, size, and SHA-256 here.
  2. Update the pinned values in `src/powerglove_vision/runtime_assets.py`, `scripts/fetch-runtime-assets.sh`, `scripts/verify-app-lab-package.py`, and `models/SHA256SUMS` when changing the model.
  3. If repackaging another wheel, record every difference from upstream and retain its license files.
  4. Build the App Lab installation ZIP and confirm it contains one wheel, the verified model, its license and notices, and only the root `sketch/` application sketch.
  5. Test first-launch offline model installation, download fallback, and checksum verification, background preloading with capture off, first activation after reboot, camera initialization, tracking, the Glove Academy and Dashboard pages, and controller output on the UNO Q before publishing the package.

### Modified Nestopia core

Before changing the Nestopia revision or native patch:

  1. Select an exact upstream commit from the official libretro Nestopia repository. Record the commit, upstream license, affected pristine-file SHA-256 values, and new patch SHA-256 in this document and `native/nestopia-powerglove/CHANGES.md`.
  2. Update the identical revision pin in `scripts/build-nestopia-powerglove.sh`, the native-core README, the modification ledger, tests, and compatibility/benchmark documents. Do not use a moving branch or tag as the build identity.
  3. Rebase `native/nestopia-powerglove/nestopia-powerglove.patch` onto a clean checkout. Preserve all upstream headers and notices. The guarded build must still reject changes to the original `NstInpPowerGlove.cpp` header.
  4. Run the native-core, state-bridge, installer, selection, exact-ROM trace, safe-neutral, and direction-response tests. Reconfirm packet length, detection, bit order, boundaries, timing, X/Y orientation, Start behavior, tracking-loss release, and the explicit FCEUmm rollback on the cabinet.
  5. Build the RetroPie installation archive and verify it contains the patch, build/install recipes, modification ledger, and third-party notices, but no ROM or compiled core. If publishing a binary separately, provide the exact complete corresponding source and GPL materials described above.

When the benchmark FCEUmm pin changes, record the new official revision in the
benchmark document and rerun both the native and standard-joypad lanes. Normal
RetroPie FCEUmm and RetroArch upgrades remain the responsibility of RetroPie;
retest controller selection and fallback gameplay before claiming compatibility.

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
