# Changelog

This file records user-visible PowerGlove Vision changes. The project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) categories and uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Git remains the
authoritative record for line-level and file-level history.

## Unreleased

### Documentation

- Standardized source headers with each file's purpose, author, copyright,
  SPDX license identifier, local history, and links to the complete history.
- Documented public interfaces and non-obvious security, lifecycle, tracking,
  packaging, and rendering functions.
- Added this centralized project changelog and its print-ready PDF edition.
- Added an automated audit for required source headers, module descriptions,
  and production Python interface docstrings.

## 0.1.0 - 2026-09-03

### Added

- Camera-only Power Glove tracking on Arduino UNO Q with MediaPipe.
- Gesture profiles for Bad Street Brawler, Super Glove Ball, and cartridge-free
  Programs A-I.
- Authenticated UDP profile selection and virtual Linux gamepad output for
  RetroPie, including per-game runcommand hooks.
- Dashboard, live diagnostics, offline gesture lessons, configuration controls,
  camera recovery, controller start/stop controls, and UNO Q matrix feedback.
- Wi-Fi deployment, App Lab packaging, runtime-asset retrieval, branded PDF
  generation, and a fixed-purpose host shutdown helper.
- Project overview, field guide, quick reference, profile handbook, third-party
  component notice, screenshots, and reproducible build instructions.

### Changed

- Delayed RetroPie receiver startup until EmulationStation finishes its initial
  device scan, preventing the virtual controller from disrupting cabinet input.
- Made the controller start disarmed and kept tracking/dashboard operation alive
  when RetroPie or the camera temporarily becomes unavailable.
- Moved private device settings and downloaded model data outside the public
  App Lab package.
- Changed the public package to download Google's Hand Landmarker model on first
  launch and verify its pinned SHA-256 digest before installation.

### Fixed

- Recovered cleanly from USB camera disconnects and slow UVC camera wake-up.
- Kept the vision loop responsive through receiver, DNS, Wi-Fi, and mDNS loss.
- Corrected password pairing so credentials never appear in command arguments
  and the shared token is transferred and installed reliably.
- Corrected UNO Q dependency isolation, secure token upload, PDF builder file
  mode, landscape diagnostics layout, and cabinet launch integration.

### Security

- Added short-lived TLS pairing with certificate comparison, a physical
  single-use PIN, bounded handshakes, and restricted token-file permissions.
- Required confirmation and a fixed host-side request path for system shutdown.
- Added a third-party component notice covering licenses, provenance, pinned
  versions, checksums, and update procedure.
