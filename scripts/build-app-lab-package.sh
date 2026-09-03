#!/usr/bin/env bash
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly OUTPUT_DIR="${PROJECT_DIR}/output/app-lab"
readonly OUTPUT_ZIP="${OUTPUT_DIR}/PowerGlove-Vision-Uno-Q.zip"
readonly PACKAGE_TMP="$(mktemp -d)"

cleanup() {
  rm -rf "${PACKAGE_TMP}"
}
trap cleanup EXIT

mkdir -p "${OUTPUT_DIR}" "${PACKAGE_TMP}/PowerGlove-Vision"
rsync -a \
  --exclude '.git/' \
  --exclude '.cache/' \
  --exclude '.venv/' \
  --exclude 'data/' \
  --exclude 'models/hand_landmarker.task' \
  --exclude 'output/' \
  --exclude 'tests/' \
  --exclude 'tmp/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '*.pdf' \
  --exclude '.DS_Store' \
  --exclude 'docs/cheatsheet.md' \
  "${PROJECT_DIR}/" "${PACKAGE_TMP}/PowerGlove-Vision/"

rm -f "${OUTPUT_ZIP}"
cd "${PACKAGE_TMP}"
zip -qr "${OUTPUT_ZIP}" PowerGlove-Vision
echo "Built ${OUTPUT_ZIP}"
