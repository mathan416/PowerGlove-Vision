#!/usr/bin/env bash
# Project: VirtualGlove
# File: scripts/install-uno-q-shutdown-helper.sh
# Purpose: Install narrow host helpers for confirmed shutdown and guarded USB camera recovery.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Installed uhubctl for supported per-port camera power cycling.
#   2026-09-05 - Added one-shot UVC camera hub recovery and autosuspend prevention.
#   2026-09-03 - Added with standardized source documentation.
#   2026-09-03 - Made the readiness marker persistent across boots and app replacement.
# Full history: docs/CHANGELOG.md and Git history.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly UNO_TARGET="${1:-${UNO_Q_SSH_TARGET:-arduino@arduiain.local}}"
readonly REMOTE_APP_DIR="/home/arduino/ArduinoApps/powerglove-vision"
readonly REMOTE_PATH_UNIT="/tmp/powerglove-system-shutdown.path"
readonly REMOTE_SERVICE_UNIT="/tmp/powerglove-system-shutdown.service"
readonly REMOTE_TMPFILES_CONFIG="/tmp/powerglove-system-shutdown.conf"
readonly REMOTE_CAMERA_PATH_UNIT="/tmp/powerglove-camera-recovery.path"
readonly REMOTE_CAMERA_SERVICE_UNIT="/tmp/powerglove-camera-recovery.service"
readonly REMOTE_CAMERA_HELPER="/tmp/powerglove-camera-recovery"
readonly REMOTE_CAMERA_TMPFILES_CONFIG="/tmp/powerglove-camera-recovery.conf"
SSH_OPTIONS=()

if [[ -n "${UNO_Q_SSH_IDENTITY:-}" ]]; then
  [[ -f "${UNO_Q_SSH_IDENTITY}" ]] || { echo "error: UNO_Q_SSH_IDENTITY is not a file" >&2; exit 2; }
  SSH_OPTIONS=(-i "${UNO_Q_SSH_IDENTITY}")
fi

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage: scripts/install-uno-q-shutdown-helper.sh [user@uno-q-host]

Install fixed-purpose, root-owned helpers that let VirtualGlove ask the
UNO Q to shut Linux down cleanly and recover its one UVC camera. A connected
camera and parent hub are enrolled now; otherwise enrollment occurs on first
use. The remote sudo command prompts for the UNO Q account password. No password
is read or stored by this script.
USAGE
  exit 0
fi

if [[ $# -gt 1 || "${UNO_TARGET}" == -* || "${UNO_TARGET}" =~ [[:space:]\'] ]]; then
  echo "error: expected one user@host SSH destination" >&2
  exit 2
fi

scp "${SSH_OPTIONS[@]}" "${PROJECT_DIR}/uno-q/powerglove-system-shutdown.path" "${UNO_TARGET}:${REMOTE_PATH_UNIT}"
scp "${SSH_OPTIONS[@]}" "${PROJECT_DIR}/uno-q/powerglove-system-shutdown.service" "${UNO_TARGET}:${REMOTE_SERVICE_UNIT}"
scp "${SSH_OPTIONS[@]}" "${PROJECT_DIR}/uno-q/powerglove-system-shutdown.conf" "${UNO_TARGET}:${REMOTE_TMPFILES_CONFIG}"
scp "${SSH_OPTIONS[@]}" "${PROJECT_DIR}/uno-q/powerglove-camera-recovery.path" "${UNO_TARGET}:${REMOTE_CAMERA_PATH_UNIT}"
scp "${SSH_OPTIONS[@]}" "${PROJECT_DIR}/uno-q/powerglove-camera-recovery.service" "${UNO_TARGET}:${REMOTE_CAMERA_SERVICE_UNIT}"
scp "${SSH_OPTIONS[@]}" "${PROJECT_DIR}/uno-q/powerglove-camera-recovery.py" "${UNO_TARGET}:${REMOTE_CAMERA_HELPER}"
scp "${SSH_OPTIONS[@]}" "${PROJECT_DIR}/uno-q/powerglove-camera-recovery.conf" "${UNO_TARGET}:${REMOTE_CAMERA_TMPFILES_CONFIG}"

ssh -t "${SSH_OPTIONS[@]}" "${UNO_TARGET}" \
  "sudo apt-get update && \
   sudo apt-get install -y uhubctl && \
   sudo install -m 0644 '${REMOTE_PATH_UNIT}' /etc/systemd/system/powerglove-system-shutdown.path && \
   sudo install -m 0644 '${REMOTE_SERVICE_UNIT}' /etc/systemd/system/powerglove-system-shutdown.service && \
   sudo install -m 0644 '${REMOTE_TMPFILES_CONFIG}' /etc/tmpfiles.d/powerglove-system-shutdown.conf && \
   sudo install -m 0644 '${REMOTE_CAMERA_PATH_UNIT}' /etc/systemd/system/powerglove-camera-recovery.path && \
   sudo install -m 0644 '${REMOTE_CAMERA_SERVICE_UNIT}' /etc/systemd/system/powerglove-camera-recovery.service && \
   sudo install -m 0755 '${REMOTE_CAMERA_HELPER}' /usr/local/libexec/powerglove-camera-recovery && \
   sudo install -m 0644 '${REMOTE_CAMERA_TMPFILES_CONFIG}' /etc/tmpfiles.d/powerglove-camera-recovery.conf && \
   sudo /usr/local/libexec/powerglove-camera-recovery --configure-if-present && \
   sudo systemctl daemon-reload && \
   sudo systemctl enable --now powerglove-system-shutdown.path && \
   sudo systemctl enable --now powerglove-camera-recovery.path && \
   sudo systemd-tmpfiles --create /etc/tmpfiles.d/powerglove-system-shutdown.conf && \
   sudo systemd-tmpfiles --create /etc/tmpfiles.d/powerglove-camera-recovery.conf && \
   rm -f '${REMOTE_PATH_UNIT}' '${REMOTE_SERVICE_UNIT}' '${REMOTE_TMPFILES_CONFIG}' '${REMOTE_CAMERA_PATH_UNIT}' '${REMOTE_CAMERA_SERVICE_UNIT}' '${REMOTE_CAMERA_HELPER}' '${REMOTE_CAMERA_TMPFILES_CONFIG}' && \
   systemctl is-enabled powerglove-system-shutdown.path && \
   systemctl is-active powerglove-system-shutdown.path && \
   systemctl is-enabled powerglove-camera-recovery.path && \
   systemctl is-active powerglove-camera-recovery.path"

echo "UNO Q shutdown and camera-recovery helpers installed."
