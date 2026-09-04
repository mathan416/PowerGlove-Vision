# Changelog

This file records user-visible PowerGlove Vision changes. The project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) categories and uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Git remains the
authoritative record for line-level and file-level history.

## Unreleased

No changes yet.

## [0.2.5] - 2026-09-04

This release adds web game mappings, personal gesture tuning, reliable game-launch
profile selection, and refreshed illustrated manuals.

### Added

  - Added a dedicated T on the UNO Q matrix while gesture tuning is active.

  - Added a Games JSON editor with paired RetroPie access, duplicate-name validation, conflict detection, verified saves, backup download, and restoration.
  - Added guided Learn tuning with camera measurements, independent gesture thresholds, temporary previews, and persistent personal adjustments shared across profiles.
  - Added a confined RetroPie Games service on TCP 55358 and included it in installation and health checks.

### Fixed

  - Moved game mapping editing into Setup and compacted Learn tuning, placing threshold values beneath the camera.

  - Published UDP profile control through a persistent App Lab brick, acknowledged queued requests independently of camera startup, and corrected launch-hook rejection reporting and configuration-error handling.
  - Kept profile changes responsive during blocked camera startup or reads, and reused the camera and tracker when switching between active profiles.
  - Added exact compressed ROM filenames to the default registry so supported `.zip` and `.7z` games can select their profiles.

### Documentation

  - Refreshed all six interface screenshots on September 4, 2026, blurring camera imagery before capture.
  - Illustrated Setup's Games section and Learn's compact Tune layout across the guides, including the T matrix indicator.
  - Regenerated the printable manuals to match the updated Markdown and screenshots.

  - Reorganized the overview and installation guide around a complete, numbered setup path: Git download, App Lab package import, UNO Q host setup, RetroPie installation, pairing, and gameplay checks.
  - Added Programs A–I controls to the overview and a complete command-line reference with project flags, defaults, arguments, and the system-command options used in the guides.
  - Applied reader-focused writing conventions across the guides, added first-round game exercises, and corrected the RetroPie update path. PDF regeneration remains a separate publication step.

  - Reviewed all Markdown guides for natural English, replacing sentence fragments and compressed notes with complete explanations while retaining concise tables and release entries.

  - Revised the Quick Reference with complete installation prerequisites, camera inspection commands, embedded screenshots, calibration explanations, and step-by-step game registration. Clarified shutdown readiness and local tests.
  - Corrected stale lesson counts, profile descriptions, calibration behaviour, pairing guidance, reboot verification status, and receiver removal steps.
  - Proofread the Quick Reference and normalized Markdown list indentation and continuation text for consistent rendering.
  - Regenerated all ten PDF editions, repaired internal section links, and improved heading and image pagination.

## [0.2.0] - 2026-09-03

### Added

  - Added an app-owned Avahi resolver brick that survives App Lab Compose regeneration, replacing the temporary direct socket mount.

  - Added one-command host setup for RetroPie and UNO Q, with managed-file backups, preserved private configuration, delayed startup, and read-only PASS/FAIL/ACTION checks. Empty pairing tokens no longer cause restart loops.

  - Added explicit A, B, and GLOVE ZAP practice lessons and live indicators. Learn consistently uses the general profile without changing the selected game.

  - Added a Glove Master completion achievement to Learn after all eleven lessons are recognized, with Start again and Dashboard actions. Skips do not count.

  - Added hand illustrations to every Learn lesson and finger/pose feedback for Start and Select. Learn accepts confirmed menu poses after their short button pulse ends, rather than requiring a second hold longer than the pulse.
  - Added a live active-profile selector to the Dashboard without changing the startup profile saved on Setup.
  - Added temporary Learn sessions that start vision while preserving the selected profile and desired controller state, including multi-tab leases and automatic recovery when a page disappears unexpectedly.
  - Added a dedicated matrix gestures-idle state with a pinball-style animated glove, separate from both true shutdown and the flashing error X.
  - Added a dedicated Learn-mode matrix state with a bright `L` and moving grayscale scan highlight.
  - Added a root-owned tmpfiles rule that restores shutdown-helper readiness after reboot or App Lab application replacement.

### Changed

  - Shutdown now requests a graceful system halt instead of poweroff, which was observed to reboot the UNO Q. Reinstall the host helper to apply this change; hardware tests subsequently confirmed automatic restart with both the powered hub and direct Mac USB connection. Remaining halted is a known unresolved limitation.

  - New installations leave the RetroPie destination blank, show generic hostname examples, and keep local practice available before pairing. Controller start requires a destination; saved destinations survive updates.


  - Added persistent host Avahi resolution for `.local` gameplay and pairing destinations, with five-second address refresh and deployment mount setup.

  - Standardized Dashboard/Learn Calibrate actions with red busy and blue completed feedback, consistent navigation buttons, and shorter Connection/Shutdown labels.
  - Prioritized controller transmission before matrix updates and limited browser JPEG encoding to 15 fps; added inference_ms and send_ms diagnostics.
  - Prepared SSH pairing dependencies separately in the persistent runtime cache so dependency downloads do not consume the SSH connection deadline.

  - Tuned thumbs-up/Select closed-finger detection to 0.42 using live pose measurements, retaining the straight-thumb requirement and deliberate hold.

  - Tuned V/Start closed ring and pinky detection to 0.42 using live pose measurements, retaining straight index/middle checks and the deliberate hold.

  - Tuned curl activation/release to 0.50/0.35 using live comfortable index-curl measurements. Learn now follows the same hysteresis state as gameplay, independent of pulsed buttons. Calibration resets held finger switches.

  - Finger curl now uses the strongest joint bend and includes the base knuckle for the four fingers. Learn exposes exact curls, a magnified landmark view, and forward-movement readings. Push lessons use continuous feedback so a one-frame event cannot be missed by browser polling.
  - Camera finger curl now uses 3D world landmarks, with an aspect-corrected normalized-depth fallback. Movement and gesture thresholds are unchanged.

  - Made Dashboard and Learn show camera/tracker startup with elapsed time and a first-start explanation, without enabling the camera in Gestures off.
  - Kept Learn startup feedback updating before camera frames arrive and disabled centring until vision is active.
  - Replaced generic Program A–I labels on Dashboard and Setup with the program letter and its intended game or use, while retaining the existing profile IDs.
  - Standardized the reader-facing game name “Gun Smoke” throughout Help and the public guides; exact `Gun.Smoke` ROM basenames remain unchanged for matching.
  - Made leaving Learn restore the selected profile, camera state, and controller state. Loading or refreshing the Dashboard now clears abandoned Learn sessions, prevents their old heartbeats from reactivating vision, and reapplies the selected mode.
  - Made Wi-Fi deployments preserve PowerGlove Vision as the UNO Q default startup app so the dashboard returns after a board reboot.
  - Made Wi-Fi deployments restore the shutdown readiness marker when the installed host watcher is active.
  - Extended deployment health verification to tolerate a three-minute cold App Lab runtime startup.
  - Made deployment verification use the UNO Q address from the active SSH connection instead of accidentally selecting a Docker bridge interface.
  - Made **Gestures off** a healthy worker state that releases controller input, closes the camera and MediaPipe tracker, and keeps the website and authenticated RetroPie profile listener available.
  - Made camera and model initialization lazy so idle mode performs no capture or vision processing and can return to an active profile without restarting the website.
  - Reworked the matrix attract sequence into distinct pinball-style beats: a four-frame energy sweep, a broad travelling cuff, a staged glove reveal, intermediate finger curls, an eight-position spark with a comet trail, one outline pulse, and a readable hold.
  - Used the UNO Q matrix's full eight-level grayscale range to separate the dim glove body, spark halo, bright spark, and whole-glove pulse.

### Documentation

  - Documented the UNO Q matrix as an eight-level monochrome DMD/BitPixel-style design target, including silhouette, contrast, motion, pulse, and physical review guidance for future animations.
  - Standardized source headers with each file's purpose, author, copyright, SPDX license identifier, local history, and links to the complete history.
  - Documented public interfaces and non-obvious security, lifecycle, tracking, packaging, and rendering functions.
  - Added this centralized project changelog and its print-ready PDF edition.
  - Added an automated audit for required source headers, module descriptions, and production Python interface docstrings.
  - Added a complete configuration reference covering JSON templates and active copies, gesture thresholds, manifests, RetroArch mapping, systemd units, generated state, secret handling, and the App Lab installation ZIP location.
  - Added GitHub Actions checks for supported Python versions, tests, source and documentation audits, syntax, PDF builds, and App Lab installation ZIP verification.
  - Added a security policy for private reporting, pairing and network boundaries, shared-token handling, shutdown permissions, and dependency integrity.
  - Added a contributing guide for code style, tests, documentation, changelog, generated artifacts, commits, and pull requests.
  - Added reusable documentation and App Lab installation package verification tools.
  - Added an illustrated, one-page-per-game handbook for all eight automatically configured titles, with original direction, finger-pose, wrist, and depth art.
  - Placed cropped gesture illustrations beside the corresponding instructions in the gameplay handbook, including the universal V-sign and thumbs-up controls.
  - Added the same contextual gesture illustrations to every Program A-I card and documented the menu gestures shared by all nine programs.
  - Added an off-script gameplay section that encourages safe experiments with other NES and Famicom games, especially the unassigned A, D, and H programs.
  - Updated the cabinet cheat sheet with off-script profile testing, safe behaviour for unknown games, and exact ROM registration guidance.
  - Renamed the built-in installation Help route, retained the original URL as an alias, and aligned its summaries with the Play Checklist terminology.
  - Extended the documentation audit to require Help-library coverage and a gameplay section for every title in the shipped game registry.
  - Expanded Wi-Fi deployment verification to confirm the current installation and gameplay guides, raw Markdown, and gesture artwork on the UNO Q.
  - Fixed the Help renderer so the allowlisted gesture images embedded in control tables appear alongside their actions, while unsafe raw HTML remains escaped.
  - Extended UNO Q deployment checks across every Help guide and representative gameplay and Programs A-I illustrations.
  - Documented the required Markdown-to-PDF workflow and UNO Q Help synchronization steps for documentation contributions.
  - Added offline PDF links to every public Help guide and the project overview, while keeping the cabinet-specific quick-reference PDF private.
  - Included the nine allowlisted public PDFs in UNO Q deployments and App Lab installation packages, with package and live-route verification.
  - Established `dev` as the integration branch, documented release and hotfix promotion into `main`, and enabled CI validation for pushes to both branches.
  - Refreshed the Dashboard, Learn, and Setup screenshots from the running UNO Q after the tagline, compact diagnostics, and safe-shutdown controls were added.
  - Added an offline Help library that renders the maintained public Markdown guides with responsive navigation, contents links, illustrations, tables, code samples, and access to the original source.
  - Added a dynamic **This cabinet** Help page whose UNO Q links follow the browser's validated hostname or IP and whose non-secret RetroPie values come from the active configuration.
  - Rewrote the configuration reference for public installations, with guided UNO Q and RetroPie setup, field-level behaviour, safe gesture tuning, network boundaries, backup and recovery advice, and symptom-based troubleshooting.
  - Renamed the Field Guide as the Installation Guide and generalized camera instructions for UVC-compatible USB cameras while recording the Razer Kiyo as tested reference hardware.

### Fixed

  - Changed Wi-Fi deployment to use SFTP staging and terminal-backed remote commands for UNO Q systems that stall non-terminal SSH sessions.
  - Allowed the UNO Q deployment health check to use the board's current IP when its `.local` name pauses during a container restart.
  - Published the host shutdown request atomically so a filesystem observer cannot consume the request between file creation and the final content write.
  - Updated the GitHub Actions workflow to use the current Node 24 action releases and run the Python 3.7 compatibility job on Ubuntu 22.04.
  - Corrected Program I so index curl accelerates in Knight Rider, a forward push accelerates with turbo, and thumb curl fires the weapons.

## 0.1.0 - 2026-09-03

### Added

  - Camera-only Power Glove tracking on Arduino UNO Q with MediaPipe.
  - Gesture profiles for Bad Street Brawler, Super Glove Ball, and cartridge-free Programs A-I.
  - Authenticated UDP profile selection and virtual Linux gamepad output for RetroPie, including per-game runcommand hooks.
  - Dashboard, live diagnostics, offline gesture lessons, configuration controls, camera recovery, controller start/stop controls, and UNO Q matrix feedback.
  - Wi-Fi deployment, App Lab packaging, runtime-asset retrieval, branded PDF generation, and a fixed-purpose host shutdown helper.
  - Project overview, installation guide, quick reference, profile handbook, third-party component notice, screenshots, and reproducible build instructions.

### Changed

  - Delayed RetroPie receiver startup until EmulationStation finishes its initial device scan, preventing the virtual controller from disrupting cabinet input.
  - Made the controller start disarmed and kept tracking/dashboard operation alive when RetroPie or the camera temporarily becomes unavailable.
  - Moved private device settings and downloaded model data outside the App Lab installation ZIP.
  - Changed the App Lab installation ZIP to download Google's Hand Landmarker model on first launch and verify its pinned SHA-256 digest before installation.

### Fixed

  - Recovered cleanly from USB camera disconnects and slow UVC camera wake-up.
  - Kept the vision loop responsive through receiver, DNS, Wi-Fi, and mDNS loss.
  - Corrected password pairing so credentials never appear in command arguments and the shared token is transferred and installed reliably.
  - Corrected UNO Q dependency isolation, secure token upload, PDF builder file mode, landscape diagnostics layout, and cabinet launch integration.

### Security

  - Added short-lived TLS pairing with certificate comparison, a physical single-use PIN, bounded handshakes, and restricted token-file permissions.
  - Required confirmation and a fixed host-side request path for system shutdown.
  - Added a third-party component notice covering licenses, provenance, pinned versions, checksums, and update procedure.


### Neutral calibration retention

The app now saves completed calibration so the reference survives transitions
between Learn and gameplay, profile changes, camera reconnections, and restarts.
When you recalibrate, the app replaces the saved reference atomically.


### RetroPie mDNS installation

The RetroPie setup command now installs `avahi-daemon` and `libnss-mdns`, enables Avahi at boot, and checks both the service and dependency. Existing hostname configuration and pairing settings are preserved. Fresh-machine installation has not yet been tested.


The UNO Q installer also installs and checks `libnss-mdns` alongside Avahi for host-level resolution, while retaining the separate app-container resolver.


### Documentation and shutdown wording consistency

The documentation now explains when to recalibrate, which files to back up,
and what the hand-identification score means. Shutdown confirmations also
explain that the UNO Q may restart automatically.
