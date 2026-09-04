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

The model is not tracked in Git and is not included in the App Lab installation
ZIP. The first time an active gesture profile needs vision, the application
downloads it from Google's versioned URL into the private, persistent
`data/models/` directory. **Gestures off** does not download or open the model.
If the file's SHA-256 checksum differs from the expected value, the application
reports the problem on Dashboard and retries. The web interface remains available. Later
launches reuse the verified cached model. Wi-Fi deployments preserve `data/`,
so an application update does not download the model again.

`scripts/fetch-runtime-assets.sh` provides an optional manual prefetch using
the same URL and checksum. It writes to the same private `data/models/` path and
is useful for development or for preparing the app before an offline session.

Google's MediaPipe repository is Apache-2.0 licensed and its official examples
direct applications to this model URL. The model download does not place a
separate model-specific license file in this repository. The PowerGlove Vision
MIT License therefore should not be interpreted as licensing the Google model.
The project avoids redistributing the model by having each installation fetch
it directly from Google. Anyone who independently bundles or redistributes the
model should confirm that the intended distribution complies with Google's
applicable model terms.

## Documentation illustration provenance

The gesture sheets under `docs/images/gestures/` were generated on September 3,
2026 with OpenAI's image-generation tool from project-authored prompts, then
selected and arranged for the PowerGlove Vision gameplay guide. They are
documentation assets, not runtime dependencies. No game screenshots, scans,
box art, characters, publisher logos, or other source images were supplied to
the generator.

The repository applies its MIT License to these curated project assets to the
extent the project owner has rights in them. Game names and other third-party
marks remain the property of their respective owners.

## Updating either component

Before publishing a wheel or model update, complete these steps. The
[command reference](CONFIGURATION_REFERENCE.md#build-inspect-or-maintain-project-files)
explains the build and verification scripts.

  1. Record the official source URL, version, license, size, and SHA-256 here.
  2. Update the pinned value in `scripts/fetch-runtime-assets.sh` when changing the model.
  3. If repackaging another wheel, record every difference from upstream and retain its license files.
  4. Build the App Lab installation ZIP and confirm it contains one wheel, no model file, and only the root `sketch/` application sketch.
  5. Test first-launch download and checksum verification, camera initialization, tracking, the Learn and Debug pages, and controller output on the UNO Q before publishing the package.
