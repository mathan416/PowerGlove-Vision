#!/usr/bin/env bash
# Project: PowerGlove Vision
# File: scripts/install-uno-q-shutdown-helper.sh
# Purpose: Install the narrow systemd helper that permits confirmed dashboard shutdown of the UNO Q.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added with standardized source documentation.
# Full history: docs/CHANGELOG.md and Git history.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly UNO_TARGET="${1:-${UNO_Q_SSH_TARGET:-arduino@arduiain.local}}"
readonly REMOTE_APP_DIR="/home/arduino/ArduinoApps/powerglove-vision"
readonly REMOTE_PATH_UNIT="/tmp/powerglove-system-shutdown.path"
readonly REMOTE_SERVICE_UNIT="/tmp/powerglove-system-shutdown.service"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage: scripts/install-uno-q-shutdown-helper.sh [user@uno-q-host]

Install the fixed-purpose, root-owned helper that lets PowerGlove Vision ask
the UNO Q to shut Linux down cleanly. The remote sudo command prompts for the
UNO Q account password. No password is read or stored by this script.
USAGE
  exit 0
fi

if [[ $# -gt 1 || "${UNO_TARGET}" == -* || "${UNO_TARGET}" =~ [[:space:]\'] ]]; then
  echo "error: expected one user@host SSH destination" >&2
  exit 2
fi

scp "${PROJECT_DIR}/uno-q/powerglove-system-shutdown.path" "${UNO_TARGET}:${REMOTE_PATH_UNIT}"
scp "${PROJECT_DIR}/uno-q/powerglove-system-shutdown.service" "${UNO_TARGET}:${REMOTE_SERVICE_UNIT}"

ssh -t "${UNO_TARGET}" \
  "sudo install -m 0644 '${REMOTE_PATH_UNIT}' /etc/systemd/system/powerglove-system-shutdown.path && \
   sudo install -m 0644 '${REMOTE_SERVICE_UNIT}' /etc/systemd/system/powerglove-system-shutdown.service && \
   sudo systemctl daemon-reload && \
   sudo systemctl enable --now powerglove-system-shutdown.path && \
   mkdir -p '${REMOTE_APP_DIR}/data' && \
   touch '${REMOTE_APP_DIR}/data/.shutdown-enabled' && \
   rm -f '${REMOTE_PATH_UNIT}' '${REMOTE_SERVICE_UNIT}' && \
   systemctl is-enabled powerglove-system-shutdown.path && \
   systemctl is-active powerglove-system-shutdown.path"

echo "UNO Q shutdown helper installed."
