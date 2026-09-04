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
#   2026-09-03 - Verified Help guides and artwork; added an IP fallback for mDNS pauses.
#   2026-09-03 - Used staged SFTP uploads and terminal-backed UNO Q commands.
#   2026-09-03 - Verified every Help guide and all gameplay table illustrations.
#   2026-09-03 - Deployed and verified every allowlisted public PDF guide.
#   2026-09-03 - Preserved PowerGlove Vision as the UNO Q default startup app.
#   2026-09-03 - Restored shutdown readiness when the host helper is active.
#   2026-09-03 - Allowed three minutes for a cold App Lab runtime startup.
#   2026-09-03 - Used the SSH connection address instead of a Docker bridge for health checks.
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
connection, preserve device settings, expose ports 8088 and 8443, keep it as
the default startup app, restart the container, and verify its status. The
default target is:

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
readonly REMOTE_ARCHIVE="/tmp/powerglove-vision-deploy.tar"
readonly LOCAL_ARCHIVE="$(mktemp)"
readonly LOCAL_METADATA_DIR="$(mktemp -d)"
readonly -a SSH_OPTIONS=(
  -o BatchMode=yes
  -o ConnectTimeout=30
  -o ServerAliveInterval=10
  -o ServerAliveCountMax=12
)

# Always remove the local staging archive, including after an interrupted upload.
cleanup() {
  rm -f "${LOCAL_ARCHIVE}"
  rm -rf "${LOCAL_METADATA_DIR}"
}
trap cleanup EXIT

echo "Checking ${UNO_TARGET}..."
ssh -tt "${SSH_OPTIONS[@]}" "${UNO_TARGET}" true >/dev/null
UNO_CONNECTION="$(ssh "${SSH_OPTIONS[@]}" "${UNO_TARGET}" 'printf "%s" "$SSH_CONNECTION"' 2>/dev/null | tr -d '\r' || true)"
read -r _UNO_CLIENT _UNO_CLIENT_PORT UNO_HEALTH_HOST _UNO_SERVER_PORT <<< "${UNO_CONNECTION}"
if [[ -z "${UNO_HEALTH_HOST}" ]]; then
  UNO_HEALTH_HOST="${UNO_HOST}"
fi
UNO_HEALTH_AUTHORITY="${UNO_HEALTH_HOST}"
if [[ "${UNO_HEALTH_AUTHORITY}" == *:* && "${UNO_HEALTH_AUTHORITY}" != \[*\] ]]; then
  UNO_HEALTH_AUTHORITY="[${UNO_HEALTH_AUTHORITY}]"
fi
readonly UNO_CONNECTION UNO_HEALTH_HOST UNO_HEALTH_AUTHORITY

echo "Uploading PowerGlove Vision over Wi-Fi..."
COPYFILE_DISABLE=1 tar \
  --exclude './.git' \
  --exclude './src/powerglove_vision/_build_info.json' \
  --exclude './.cache' \
  --exclude './.venv' \
  --exclude './data' \
  --exclude './output/app-lab' \
  --exclude './output/pdf/PowerGlove-Vision-Quick-Reference.pdf' \
  --exclude './tests' \
  --exclude './tmp' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude './docs/cheatsheet.md' \
  -C "${PROJECT_DIR}" -cf "${LOCAL_ARCHIVE}" .
python3 "${SCRIPT_DIR}/stamp-build-version.py" "${LOCAL_METADATA_DIR}/src/powerglove_vision/_build_info.json"
tar -rf "${LOCAL_ARCHIVE}" -C "${LOCAL_METADATA_DIR}" ./src/powerglove_vision/_build_info.json
scp "${SSH_OPTIONS[@]}" "${LOCAL_ARCHIVE}" "${UNO_TARGET}:${REMOTE_ARCHIVE}"
ssh -tt "${SSH_OPTIONS[@]}" "${UNO_TARGET}" \
  "mkdir -p '${REMOTE_APP_DIR}' && tar --warning=no-unknown-keyword -C '${REMOTE_APP_DIR}' -xf '${REMOTE_ARCHIVE}' && rm -f '${REMOTE_ARCHIVE}'"

echo "Ensuring the secure setup port is published..."
ssh -tt "${SSH_OPTIONS[@]}" "${UNO_TARGET}" \
  "REMOTE_COMPOSE='${REMOTE_COMPOSE}' python3 -c \"import os, pathlib; p=pathlib.Path(os.environ['REMOTE_COMPOSE']); lines=p.read_text().splitlines(); found=any(line.strip() == '- 8443:8443' for line in lines); index=next((i for i, line in enumerate(lines) if line.strip() == '- 8088:8088'), None); assert found or index is not None, 'port 8088 is missing from App Lab compose file'; lines if found else lines.insert(index + 1, lines[index].replace('8088:8088', '8443:8443')); p.write_text('\\n'.join(lines) + '\\n')\""

echo "Configuring persistent local hostname resolution..."
ssh "${SSH_OPTIONS[@]}" "${UNO_TARGET}" \
  "test -S /run/avahi-daemon/socket && python3 '${REMOTE_APP_DIR}/scripts/configure-uno-q-mdns.py' '${REMOTE_COMPOSE}'"

echo "Checking the host shutdown helper..."
ssh -tt "${SSH_OPTIONS[@]}" "${UNO_TARGET}" \
  "if systemctl is-active --quiet powerglove-system-shutdown.path; then mkdir -p '${REMOTE_APP_DIR}/data' && touch '${REMOTE_APP_DIR}/data/.shutdown-enabled'; else echo 'warning: install scripts/install-uno-q-shutdown-helper.sh to enable Dashboard shutdown' >&2; fi"

echo "Restarting the UNO Q application..."
ssh -tt "${SSH_OPTIONS[@]}" "${UNO_TARGET}" \
  "arduino-app-cli properties set default '${REMOTE_APP_DIR}' && APP_HOME='${REMOTE_APP_DIR}' docker compose -f '${REMOTE_COMPOSE}' up -d --force-recreate"

echo "Waiting for the dashboard..."
ready=false
for _ in {1..60}; do
  if curl --fail --silent --show-error --max-time 2 \
      "http://${UNO_HEALTH_AUTHORITY}:8088/status" >/dev/null 2>&1; then
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
  "http://${UNO_HEALTH_AUTHORITY}:8088/debug" >/dev/null
curl --fail --silent --show-error --max-time 5 \
  "http://${UNO_HEALTH_AUTHORITY}:8088/learn" >/dev/null
curl --fail --silent --show-error --max-time 5 \
  "http://${UNO_HEALTH_AUTHORITY}:8088/help" >/dev/null
for HELP_SLUG in cabinet installation gameplay programs configuration security components contributing changelog; do
  curl --fail --silent --show-error --max-time 5 \
    "http://${UNO_HEALTH_AUTHORITY}:8088/help/${HELP_SLUG}" >/dev/null
done
for PDF_SLUG in overview installation gameplay programs configuration security components contributing changelog; do
  curl --fail --silent --show-error --max-time 15 \
    "http://${UNO_HEALTH_AUTHORITY}:8088/help-pdf/${PDF_SLUG}.pdf" >/dev/null
done
if curl --fail --silent --show-error --max-time 5 \
    "http://${UNO_HEALTH_AUTHORITY}:8088/help-pdf/quick-reference.pdf" >/dev/null 2>&1; then
  echo "error: cabinet-specific quick-reference PDF was exposed" >&2
  exit 1
fi
curl --fail --silent --show-error --max-time 5 \
  "http://${UNO_HEALTH_AUTHORITY}:8088/help-assets/gestures/actions/v-sign.png" >/dev/null
GAMEPLAY_MARKDOWN="$(curl --fail --silent --show-error --max-time 5 \
  "http://${UNO_HEALTH_AUTHORITY}:8088/help/gameplay.md")"
if [[ "${GAMEPLAY_MARKDOWN}" != *"Take Power Glove Vision off-script"* ]]; then
  echo "error: deployed gameplay Help is not the current edition" >&2
  exit 1
fi
GAMEPLAY_HTML="$(curl --fail --silent --show-error --max-time 5 \
  "http://${UNO_HEALTH_AUTHORITY}:8088/help/gameplay")"
PROGRAMS_HTML="$(curl --fail --silent --show-error --max-time 5 \
  "http://${UNO_HEALTH_AUTHORITY}:8088/help/programs")"
for EXPECTED_IMAGE in v-sign.png thumbs-up.png finger-curl.png wrist-roll.png push-toward-camera.png; do
  if [[ "${GAMEPLAY_HTML}" != *"/help-assets/gestures/actions/${EXPECTED_IMAGE}"* ]]; then
    echo "error: gameplay Help is missing ${EXPECTED_IMAGE}" >&2
    exit 1
  fi
done
if [[ "${GAMEPLAY_HTML}" != *"<img loading=lazy"* || "${PROGRAMS_HTML}" != *"<img loading=lazy"* ]]; then
  echo "error: Help table illustrations were not rendered" >&2
  exit 1
fi
curl --insecure --fail --silent --show-error --max-time 5 \
  "https://${UNO_HEALTH_AUTHORITY}:8443/setup" >/dev/null

echo "Deployment complete."
echo "  Learn:  http://${UNO_HOST}:8088/learn"
echo "  Debug:  http://${UNO_HOST}:8088/debug"
echo "  Help:   http://${UNO_HOST}:8088/help"
echo "  Setup:  https://${UNO_HOST}:8443/setup"
