# Setup and code review — 6 September 2026

Initial review baseline: `dev` at `e4a18f9668ddbcdd28f49b8f0e18edccceaad601`.
Updated after the approved follow-ups, deployment of runtime commit `a7131f8`,
and publication of `v0.3.2-rc.6`. The implementation decisions below are complete;
physical latency testing remains deferred to the next cabinet session.

## Coverage and completed fixes

Initial fixes: [4315a29](https://github.com/mathan416/PowerGlove-Vision/commit/4315a29).

The review followed Setup through its HTTP routes, device settings, supervisor
and worker controls, then examined player/backup persistence, capture and sender
boundaries, profile messages, receiver/native-state publication, pairing, and
installation manifest handling. Existing regression tests cover the wider
application and installation paths. This is not a line-by-line audit of upstream
MediaPipe or emulator source, nor a substitute for live camera-to-display tests.

- Grouped Setup into connection/startup, pairing, idle display, controller/power,
  and game mappings. Advanced connection fields are collapsed. Labels distinguish
  name resolution from delivery, stored credentials from confirmed pairing, and
  the informational hand/glove label from recognition settings.
- Added initial-load retry and recoverable action errors. Controller and pairing
  refreshes retain unsaved connection edits. Changing the pairing destination
  clears physical approval; password fields are cleared after an attempt.
- Serialized device-setting writes and used private atomic replacement, preventing
  concurrent connection/attract saves from losing a preference or sharing a
  temporary filename. First-run device configuration is private from creation.
- Retained and retried the latest explicit Start/Stop request when the worker is
  unavailable. The API returns HTTP 202 for pending delivery; the supervisor
  retries without adding a camera or controller-state queue. Worker acceptance
  means the request reached its control handler, not that an emulator consumed it.
- Moved supervised worker token loading from process arguments to private device
  configuration. Existing command-line token options remain available for compatibility.
- Applied browser cross-site mutation checks consistently and required JSON for
  connection settings. Removed a duplicate unreachable calibration route.
- Made receiver socket timeouts neutralize native state as well as the virtual
  gamepad. Malformed deeply nested JSON no longer terminates the profile listener.

Validation includes failure-path and concurrency regression tests, the full unit
suite, source/documentation/package checks, and isolated Chrome checks of load
retry, failed-save recovery, unsaved edits, pending delivery, pairing reset,
attract saves, HTTP pairing restrictions, and 320/390/768-pixel layouts.
Documentation screenshots use simulated device data. Physical gameplay, hardware
shutdown, and live password pairing were not exercised for this review.

## Completed parking-lot decisions

All six implementation proposals were approved, implemented, and deployed. This
records their current behavior rather than the limitations that prompted them.

| Item | Implemented outcome | Evidence |
| --- | --- | --- |
| Calibration per player | Each player has a separate saved calibration. `data/calibration.json` remains the active physical reference. Fresh centering is the default when switching; same-position reuse is explicit. New players copy sensitivity, not another player's center. | [d7a264c](https://github.com/mathan416/PowerGlove-Vision/commit/d7a264c) |
| Backups across future defaults | Complete version-2 hand-setup backups include personal overrides, effective thresholds for all 13 channels, software identity, and player calibration. Restore offers saved sensitivity or personal overrides, explicitly confirms calibration reuse, and preserves Academy progress. Portable version 1 is rejected; internal store migrations retain private recovery backups. | [d7a264c](https://github.com/mathan416/PowerGlove-Vision/commit/d7a264c) |
| Hostname refresh during movement | DNS/mDNS refresh runs in a background thread. Sending uses the current address without a lookup or retained controller-state queue; unavailable addresses cause the current state to be skipped. | [d7a264c](https://github.com/mathan416/PowerGlove-Vision/commit/d7a264c), [measurement report](../direction-response-benchmark.md) |
| Controller transport evolution | Version-2 controller messages use HMAC-SHA256 without transmitting the shared secret. Receiver-issued challenges and increasing sequences reject stale/replayed input across sessions and restarts. Both devices require coordinated upgrades; legacy reception is an explicit temporary migration option. | [4f6600c](https://github.com/mathan416/PowerGlove-Vision/commit/4f6600c), [upgrade procedure](../CONFIGURATION_REFERENCE.md#signed-controller-transport-and-upgrades) |
| Independent Wi-Fi indication | A read-only host sampler reports wireless carrier status in Setup and a fourth Off-mode pixel. Existing app and console pixels retain their meanings. Installation/upgrade includes the sampler; game modes, T and L are unchanged. | [d7a264c](https://github.com/mathan416/PowerGlove-Vision/commit/d7a264c) |
| Remaining web-module cleanup | Shared shell, Dashboard, Academy, Games, and tuning code have separate modules. Obsolete tuning definitions were removed and a small compatibility re-export remains. Compared Dashboard, Academy, Play, and Setup output was byte-for-byte identical before and after extraction. | [d7fc083](https://github.com/mathan416/PowerGlove-Vision/commit/d7fc083) |

The signed transport preserves newest-state-only delivery and the 250 ms release
deadline for both native state and the virtual gamepad. Handshakes and rejected
traffic cannot postpone neutralization. The native-state record format is
unchanged, so this update does not require rebuilding `lr-nestopia-powerglove`.

Deployment exposed a cabinet with both Ethernet and Wi-Fi: replies could leave
through a different local address and be discarded before reaching the Controller
container. [a7131f8](https://github.com/mathan416/PowerGlove-Vision/commit/a7131f8)
uses Linux `IP_PKTINFO` to reply from the contacted receiver address/interface.
A Linux regression test verifies the reply source address. Alternate-source
replies are accepted by the sender only with valid authentication, current
request/session correlation, and the configured receiver port.

## Validation and deployment evidence

- All 355 tests passed on Python 3.7 and Python 3.12. Source, documentation, and
  package checks passed. Affected maintained guides and READMEs were updated;
  affected PDFs were rebuilt and visually inspected.
- Browser checks covered player/backup behavior and Setup failure recovery,
  retry, draft preservation, and 320/390/768-pixel layouts. Live mobile Help and
  a complete version-2 backup were also checked.
- Both devices were deployed at runtime commit `a7131f8`. The PowerGlove Vision
  Controller reported matching running/expected firmware fingerprint
  `6eb0cb837581589fdf1051a12f066fd558799549951ab8dd0cb45d5bda39f91b`.
  Installation manifests passed; the RetroPie receiver and Games services were
  active with legacy controller reception disabled.
- Private recovery backups were retained. Controller hand settings, calibration,
  armed state, and pairing token were preserved; the current attract preference
  was retained. RetroPie configuration checksums were unchanged.
- An isolated receiver test accepted 18 states across two sessions, dropped the
  initial handshake frame in each, and rejected a retired-session packet. It used
  a separate native-state file and no virtual gamepad. Production handshake-only
  probes authenticated through both cabinet interfaces with the expected reply
  source; they did not inject gameplay input.
- Before background refresh, 12 isolated cold hostname lookups on the Controller
  measured 2.35 ms median and 107.54 ms maximum. This is lookup timing, not measured
  camera-to-display improvement.
- With 2,000 measured iterations per path, signed transport added 0.1104 ms median
  encoding time on the Controller and 0.3398 ms median validation time on RetroPie
  compared with the previous protocol. These isolated measurements exclude
  network, handshake, state publication, core consumption, and display. See the
  [benchmark report](../direction-response-benchmark.md) for methodology and tails.

## Release-candidate publication

The maintainer authorized the main merge and next release candidate.
[PR #9](https://github.com/mathan416/PowerGlove-Vision/pull/9) merged at
`57ee3ceace8d53ad017df4606ac16ec56259a7ab`; `dev` was synchronized afterward.
[v0.3.2-rc.6](https://github.com/mathan416/PowerGlove-Vision/releases/tag/v0.3.2-rc.6)
was published as a prerelease at that commit. The latest stable release remains
`v0.3.1` at publication time.

The [release workflow](https://github.com/mathan416/PowerGlove-Vision/actions/runs/34038712545)
and quality checks passed. Downloaded installer scripts and both device packages
matched the published checksums. ZIP integrity, candidate/commit identities,
firmware fingerprint, private-data/ROM exclusions, and the Controller App Lab
package check passed.

The deployed runtime remains `a7131f8`: subsequent candidate preparation changed
documentation and release metadata, and did not trigger another deployment.
Publication is not evidence of a fresh installation or a new live gameplay test.
See the [changelog](../CHANGELOG.md) for the candidate's changes and limitations.

## Remaining parking lot and validation

| Item | Current evidence | Next step |
| --- | --- | --- |
| Native Super Glove Ball latency and stationary jitter | Earlier native gameplay confirmed playable continuous X/Y, with visible delay. Neither the lookup sample nor transport microbenchmark measures the full path. | Record synchronized hand and screen movement; measure capture, inference, send, network reception, state publication, core consumption, and display separately. Establish stationary jitter before tuning. Preserve newest-frame/state-only processing and avoid unnecessary smoothing. |
| Live gameplay on rc.6 | Installed transport and firmware checks passed. The previously completed native game predates these changes. | Repeat gameplay with the candidate, checking movement and the confirmed native actions. |
| Fresh-device installation | Upgrade deployments and published-package checks passed. | Exercise both published installers on fresh devices. |
| Remaining physical checks | Hardware shutdown and live password pairing were not exercised in this review. Firmware identity does not establish visual matrix behavior. | Check these hardware interactions and the Wi-Fi indicator visually during an available device session. |

These are outstanding measurements and validation, not unapproved implementation
proposals or newly imposed release gates. Unused native packet fields, including
wrist rotation, remain deliberately neutral; they are not missing confirmed
Super Glove Ball functionality.

## Latency test preparation follow-up

Prepared guided windows, bounded optional Controller/receiver traces, a separate
diagnostic core build, and original-video indexing/annotation tools. See the
[native session procedure](../direction-response-benchmark.md#native-latency-and-stationary-jitter-session).
Local synthetic and regression checks validate the tools; physical recording,
actual-device overhead comparison, and accepted stationary baselines remain
pending. The maintainer chose to prepare tools now and record later. No device
deployment, core selection, or responsiveness tuning is part of this preparation.
