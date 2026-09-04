#!/usr/bin/env bash
# Project: PowerGlove Vision
# File: scripts/fetch-runtime-assets.sh
# Purpose: Download and SHA-256 verify the official Google Hand Landmarker model for local or offline staging.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added with standardized source documentation.
# Full history: docs/CHANGELOG.md and Git history.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly MODEL_DIR="${PROJECT_DIR}/data/models"
readonly MODEL_PATH="${MODEL_DIR}/hand_landmarker.task"
readonly MODEL_URL="https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
readonly MODEL_SHA256="fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"

# Print the SHA-256 digest of one file without loading the asset into memory.
sha256_file() {
  python3 - "$1" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

digest = sha256()
with Path(sys.argv[1]).open("rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
print(digest.hexdigest())
PY
}

if [[ -f "${MODEL_PATH}" ]] && [[ "$(sha256_file "${MODEL_PATH}")" == "${MODEL_SHA256}" ]]; then
  echo "Hand Landmarker model is present and verified."
  exit 0
fi

mkdir -p "${MODEL_DIR}"
temporary_model="$(mktemp "${MODEL_DIR}/hand_landmarker.task.XXXXXX")"
# Delete an incomplete download when verification or installation fails.
cleanup() {
  rm -f "${temporary_model}"
}
trap cleanup EXIT

if [[ -f "${PROJECT_DIR}/models/hand_landmarker.task" ]]; then
  echo "Installing the bundled Google Hand Landmarker model..."
  cp "${PROJECT_DIR}/models/hand_landmarker.task" "${temporary_model}"
else
  echo "Downloading the official Google Hand Landmarker model..."
  curl --fail --location --silent --show-error "${MODEL_URL}" --output "${temporary_model}"
fi

actual_sha256="$(sha256_file "${temporary_model}")"
if [[ "${actual_sha256}" != "${MODEL_SHA256}" ]]; then
  echo "error: Hand Landmarker checksum mismatch" >&2
  echo "expected: ${MODEL_SHA256}" >&2
  echo "actual:   ${actual_sha256}" >&2
  exit 1
fi

chmod 0644 "${temporary_model}"
mv "${temporary_model}" "${MODEL_PATH}"
trap - EXIT
echo "Installed verified model at ${MODEL_PATH}"
