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

These are decisions or measurements, not promises of current functionality.
No change below has been applied by this review.

| Item | Evidence and decision to make | Suggested next step |
| --- | --- | --- |
| Native Super Glove Ball latency | Continuous X/Y is playable, but visible delay remains. Current status timing does not measure the entire capture-to-display path. | Record synchronized hand and screen movement; separate capture, inference, send, receive, publication, core consumption, and display. Establish stationary jitter before tuning. |
| Calibration per player | Player sensitivity and Academy progress are individual; `data/calibration.json` remains a shared physical reference. Switching players requires fresh centering. | Decide whether saved player-specific references would be useful. Keep fresh centering the default unless the camera and playing position are explicitly confirmed unchanged. |
| Backups across future defaults | Version-2 hand backups contain personal threshold overrides; an empty `thresholds` object means use installed defaults. Future default changes can therefore alter the effective setup after restore. | Decide whether a future backup should also record effective thresholds and source software identity, with a review step before importing old defaults. Keep version-1 and version-2 imports compatible. |
| Hostname refresh during movement | `UdpSender.send` resolves its destination through the cached resolver. A cache miss can perform synchronous resolution on the send path. | Measure cache-miss timing first; consider background refresh only if it materially affects movement. Preserve newest-state-only delivery. |
| Controller transport evolution | Controller packets use the existing shared-token protocol and per-session sequencing. Profile commands use signed messages. Stronger controller authentication and retired-session handling would require coordinated updates. | Decide whether to schedule a versioned protocol migration with compatibility and rollback tests. See the existing trusted-LAN security model. |
| Independent Wi-Fi indication | Off-mode pixels report app health and the paired console's Games-service reachability/authentication. They do not independently report Wi-Fi association. | Keep these meanings, or add a separate host Wi-Fi signal and choose its matrix presentation. Do not infer Wi-Fi failure from an offline console. |
| Remaining web-module cleanup | Setup is now isolated in `setup_web.py`; Dashboard/Academy routes and older embedded UI definitions remain large. | Schedule small module extractions with browser regression checks if further UI work makes them useful. Avoid mixing a broad rewrite with latency tuning. |

Keep this list current when a decision is made: record the outcome and link the
implementing commit or measurement report. Do not silently turn parked items
into release requirements.
