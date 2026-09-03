#!/usr/bin/env bash
# Project: PowerGlove Vision
# File: scripts/deploy-uno-q-wifi.sh
# Purpose: Deploy the application over authenticated SSH, preserve device data, restart it, and verify health.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
# Full history: docs/CHANGELOG.md and Git history.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

UNO_TARGET="${UNO_Q_SSH_TARGET:-arduino@arduiain.local}"
REMOTE_APP_DIR="${UNO_Q_APP_DIR:-/home/arduino/ArduinoApps/powerglove-vision}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage: scripts/deploy-uno-q-wifi.sh [user@uno-q-host]

Deploy the PowerGlove Vision Linux application over an authenticated SSH
connection, preserve device settings, expose ports 8088 and 8443, restart the
container, and verify its status. The default target is:

  arduino@arduiain.local

Environment overrides:
  UNO_Q_SSH_TARGET  SSH destination
  UNO_Q_APP_DIR     Remote App Lab application directory
USAGE
  exit 0
fi

if [[ $# -gt 1 ]]; then
  echo "error: expected at most one SSH destination" >&2
  exit 2
fi

if [[ $# -eq 1 ]]; then
  UNO_TARGET="$1"
fi

readonly UNO_TARGET REMOTE_APP_DIR
readonly UNO_HOST="${UNO_TARGET#*@}"
readonly REMOTE_COMPOSE="${REMOTE_APP_DIR}/.cache/app-compose.yaml"

echo "Checking ${UNO_TARGET}..."
ssh -o BatchMode=yes -o ConnectTimeout=8 "${UNO_TARGET}" true

echo "Uploading PowerGlove Vision over Wi-Fi..."
ssh -o BatchMode=yes "${UNO_TARGET}" "mkdir -p '${REMOTE_APP_DIR}'"
COPYFILE_DISABLE=1 tar \
  --exclude './.git' \
  --exclude './.cache' \
  --exclude './.venv' \
  --exclude './data' \
  --exclude './models/hand_landmarker.task' \
  --exclude './output' \
  --exclude './tests' \
  --exclude './tmp' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '*.pdf' \
  --exclude '.DS_Store' \
  --exclude './docs/cheatsheet.md' \
  -C "${PROJECT_DIR}" -cf - . | \
  ssh -o BatchMode=yes "${UNO_TARGET}" \
    "tar --warning=no-unknown-keyword -C '${REMOTE_APP_DIR}' -xf -"

echo "Ensuring the secure setup port is published..."
ssh -o BatchMode=yes "${UNO_TARGET}" \
  "REMOTE_COMPOSE='${REMOTE_COMPOSE}' python3 -c \"import os, pathlib; p=pathlib.Path(os.environ['REMOTE_COMPOSE']); lines=p.read_text().splitlines(); found=any(line.strip() == '- 8443:8443' for line in lines); index=next((i for i, line in enumerate(lines) if line.strip() == '- 8088:8088'), None); assert found or index is not None, 'port 8088 is missing from App Lab compose file'; lines if found else lines.insert(index + 1, lines[index].replace('8088:8088', '8443:8443')); p.write_text('\\n'.join(lines) + '\\n')\""

echo "Restarting the UNO Q application..."
ssh -o BatchMode=yes "${UNO_TARGET}" \
  "docker compose -f '${REMOTE_COMPOSE}' up -d --force-recreate"

echo "Waiting for the dashboard..."
ready=false
for _ in {1..30}; do
  if curl --fail --silent --show-error --max-time 2 \
      "http://${UNO_HOST}:8088/status" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done

if [[ "${ready}" != true ]]; then
  echo "error: the UNO Q app did not become ready at http://${UNO_HOST}:8088" >&2
  exit 1
fi

curl --fail --silent --show-error --max-time 5 \
  "http://${UNO_HOST}:8088/debug" >/dev/null
curl --fail --silent --show-error --max-time 5 \
  "http://${UNO_HOST}:8088/learn" >/dev/null
curl --insecure --fail --silent --show-error --max-time 5 \
  "https://${UNO_HOST}:8443/setup" >/dev/null

echo "Deployment complete."
echo "  Learn:  http://${UNO_HOST}:8088/learn"
echo "  Debug:  http://${UNO_HOST}:8088/debug"
echo "  Setup:  https://${UNO_HOST}:8443/setup"
