# Setup and code review — 6 September 2026

Reviewed from `dev` at `e4a18f9668ddbcdd28f49b8f0e18edccceaad601`.
This is a development review, not a release approval. Physical latency testing
remains deferred to the next cabinet session.

## Coverage and completed fixes

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

## Parking lot for Iain

The original review is above. The following approvals were received afterward;
implementation status is recorded below. Physical latency testing remains deferred.

| Item | Evidence and decision to make | Suggested next step |
| --- | --- | --- |
| Native Super Glove Ball latency | Continuous X/Y is playable, but visible delay remains. Current status timing does not measure the entire capture-to-display path. | Record synchronized hand and screen movement; separate capture, inference, send, receive, publication, core consumption, and display. Establish stationary jitter before tuning. |
| Calibration per player | Player sensitivity and Academy progress are individual; `data/calibration.json` remains a shared physical reference. Switching players requires fresh centering. | **Approved and implemented:** separate saved centers; fresh centering remains the default, with explicit same-position reuse. |
| Backups across future defaults | Version-2 hand backups contain personal threshold overrides; an empty `thresholds` object means use installed defaults. Future default changes can therefore alter the effective setup after restore. | **Approved and implemented:** effective thresholds and software identity with restore review. Version 2 is the first supported portable format; version 1 is rejected. Internal store migrations retain recovery backups. |
| Hostname refresh during movement | `UdpSender.send` resolves its destination through the cached resolver. A cache miss can perform synchronous resolution on the send path. | **Approved and implemented:** isolated lookup sample measured 2.35 ms median / 107.54 ms maximum; refresh now runs in the background with no state queue. Physical movement comparison remains pending. |
| Controller transport evolution | Controller packets use the existing shared-token protocol and per-session sequencing. Profile commands use signed messages. Stronger controller authentication and retired-session handling would require coordinated updates. | **Approved and implemented:** signed version-2 sessions with receiver-issued challenges, explicit temporary compatibility, replay/restart tests, and coordinated upgrade/rollback instructions. |
| Independent Wi-Fi indication | Off-mode pixels report app health and the paired console's Games-service reachability/authentication. They do not independently report Wi-Fi association. | **Approved and implemented:** read-only host Wi-Fi sampler, explicit Setup status, and a fourth Off-mode pixel. Console pixels retain their meanings. |
| Remaining web-module cleanup | Setup is now isolated in `setup_web.py`; Dashboard/Academy routes and older embedded UI definitions remain large. | **Approved and implemented:** shared shell, Dashboard, Academy, Games, and tuning modules; obsolete tuning definitions removed. Rendered pages remain byte-for-byte identical. |

Keep this list current when a decision is made: record the outcome and link the
implementing commit or measurement report. Do not silently turn parked items
into release requirements.

## Approved follow-up work

**Controller transport evolution:** Controller packets currently carry the shared
secret and a session/sequence number. A future protocol could authenticate each
message with a signature derived from the secret, without sending the secret
inside the message, and reject packets from retired sessions. This would improve
authentication and handling of delayed old input. It would require coordinated
updates, compatibility/rollback design, and timing measurements on both computers.
This is now implemented without movement smoothing or queued input. See the Configuration Reference for the handshake and upgrade procedure.

**Remaining web-module cleanup:** Extract Dashboard and Glove Academy markup and
scripts from the large combined files, then remove unused older definitions.
This would improve maintainability and make future changes easier to review,
without adding a visible feature. It can be scheduled in small steps with browser
regression checks. The bounded extraction described above is now implemented; HTTP routes and application behavior are preserved.
