# PowerGlove Vision Camera Guide

Your camera is how PowerGlove Vision sees your hand. This guide helps you choose
a camera, get a clear and responsive picture, and recover quickly when the
camera is disconnected or unavailable.

Begin with the automatic settings. They work with ordinary USB cameras and are
the best starting point for most families. The advanced frame-rate, reader,
exposure, and gain controls are available when you need to improve a particular
camera or investigate performance; they do not change how gestures are learned
or mapped to games.

## Start here

Use these settings first:

- **Camera:** Automatic
- **Camera frame rate:** Automatic
- **Camera reader:** Compatible - OpenCV
- **Exposure behavior:** Automatic

Connect one ordinary UVC camera, place the whole hand in view, and check the
Dashboard. Change advanced settings only to solve a visible problem or compare
latency.

## Camera selection

**Automatic** discovers a usable camera when tracking starts. The camera does
not need to be attached during installation; it may be connected later. Setup
refreshes its camera list while the page is open.

Choose a named camera when more than one camera is connected or Automatic picks
the wrong one. A saved camera that is temporarily disconnected stays listed as
unavailable so the Controller does not silently switch devices.

## Frame rate

- **Automatic** prefers 30 fps and accepts the camera driver's usable rate.
- **30 fps** requests the tested gameplay rate.
- **60 fps** is a comparison option for cameras that support it.

An unsupported rate falls back safely. While tracking is active, Setup reports
the actual delivered rate below the camera controls.

## Camera reader

- **Compatible - OpenCV** is the portable default.
- **Low latency - Direct V4L2** is an optional Linux path for supported 64-bit,
  640x480 MJPEG cameras. It consumes the newest camera buffer and falls back to
  OpenCV when its requirements are unavailable.

Direct V4L2 does not change MediaPipe recognition, gestures, calibration, or
controller mappings.

## Exposure and gain

Start with **Automatic**. Brighter images are not always faster: a camera may use
a long exposure in dim light and silently reduce its effective frame rate.

- **Automatic - fixed frame rate** asks a camera that advertises the control to
  preserve frame cadence.
- **Automatic - Razer Kiyo Pro tested** also requests the tested temporary
  HDR-off setting.
- **Manual exposure and gain** is available only with Direct V4L2 and only when
  the camera reports safe limits.

Manual values are camera-specific. Unsupported settings fall back to automatic
exposure and are reported in Setup. Camera automation is restored when tracking
closes. The Razer-specific hardware choice is temporary; repowering the camera
restores its own defaults.

## Lighting and placement

- Light the hand from the front or side, not from a bright window behind it.
- Keep the entire hand, wrist, and intended movement area inside the frame.
- Avoid motion blur by adding room light before increasing gain.
- Keep the camera and playing position consistent with the saved center and
  movement reach.

Glove Academy may warn about a dark hand or a much brighter background. These
warnings are advisory and do not change camera exposure automatically.

## Reconnection and recovery

The Controller looks for the saved camera whenever tracking starts. Supported
camera settings are reapplied after a reconnect. The optional UNO Q recovery
helper can reset the enrolled USB hub when a camera stream remains wedged even
though the camera is still visible to USB.

Automatic camera selection is the portable behavior. Hub reset support depends
on the UNO Q's USB topology and is deliberately allowlisted during enrollment.

## Quick troubleshooting

- **Camera not listed:** reconnect it, wait a few seconds, and reload Setup.
- **Camera listed but no picture:** stop and restart controller output; if the
  hourglass remains, reconnect the camera or its powered hub.
- **Dark or blurry picture:** improve room lighting, then compare fixed-rate
  automatic exposure.
- **Manual controls unavailable:** return to Automatic or use a camera that
  exposes the required UVC controls.
- **Tracking jumps at an edge:** check framing, center, and Movement reach before
  changing exposure.

For symptom-by-symptom recovery, see the
[Troubleshooting guide](TROUBLESHOOTING.md). For every stored field and installed
path, see the [Configuration reference](CONFIGURATION_REFERENCE.md).
