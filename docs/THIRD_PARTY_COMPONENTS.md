# Third-party runtime components

PowerGlove Vision's original source code and associated documentation are
licensed under the repository's MIT License. That license does not replace the
licenses or terms that apply to third-party software and model files.

## MediaPipe 0.10.18 ARM64 wheel

The UNO Q runtime uses this tracked wheel:

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
The Python package code and compiled MediaPipe binaries were not modified. The
wheel dependency metadata was changed as follows, and its `RECORD` was rebuilt:

- removed the `jax` dependency declaration;
- removed the `jaxlib` dependency declaration;
- replaced `opencv-contrib-python` with
  `opencv-contrib-python-headless==4.10.0.84`;
- omitted the upstream wheel's empty `mediapipe.libs` directory.

These changes avoid unnecessary JAX installation and GUI OpenCV dependencies
on the UNO Q. The repacked wheel retains MediaPipe's Apache 2.0 license at
`mediapipe-0.10.18.dist-info/LICENSE`. Do not substitute the upstream wheel
without retesting dependency resolution, camera startup, and hand tracking.

## Google Hand Landmarker model

PowerGlove Vision uses Google's float16 Hand Landmarker task bundle.

| Property | Value |
| --- | --- |
| Runtime path | `models/hand_landmarker.task` |
| Official download | <https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task> |
| SHA-256 | `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` |
| Size | 7,819,105 bytes |

The model is not tracked in Git. Both `scripts/build-app-lab-package.sh` and
`scripts/deploy-uno-q-wifi.sh` call `scripts/fetch-runtime-assets.sh`. That
script downloads the model from Google's versioned URL and refuses to install
it if the SHA-256 checksum differs. The generated App Lab ZIP contains the
verified model so the installed application has a fixed runtime asset.

Google's MediaPipe repository is Apache-2.0 licensed and its official examples
direct applications to this model URL. The model download does not place a
separate model-specific license file in this repository. The PowerGlove Vision
MIT License therefore should not be interpreted as licensing the Google model.
Anyone publishing a prebuilt ZIP or otherwise redistributing the model should
confirm that the intended distribution complies with Google's applicable
model terms.

## Updating either component

Treat a wheel or model update as a tested dependency change:

1. Record the official source URL, version, license, size, and SHA-256 here.
2. Update the pinned value in `scripts/fetch-runtime-assets.sh` when changing
   the model.
3. If repackaging another wheel, record every difference from upstream and
   retain its license files.
4. Build the App Lab ZIP and confirm it contains one wheel, one model, and only
   the root `sketch/` application sketch.
5. Test camera initialization, tracking, the Learn and Debug pages, and
   controller output on the UNO Q before publishing the package.
