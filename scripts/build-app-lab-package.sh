#!/usr/bin/env bash
# Project: PowerGlove Vision
# File: scripts/build-app-lab-package.sh
# Purpose: Build a clean, offline-model UNO Q App Lab distribution archive from tracked project sources.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-03 - Included allowlisted public PDF guides in installation packages.
# Full history: docs/CHANGELOG.md and Git history.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly OUTPUT_DIR="${PROJECT_DIR}/output/app-lab"
readonly OUTPUT_ZIP="${OUTPUT_DIR}/PowerGlove-Vision-Uno-Q.zip"
readonly PACKAGE_TMP="$(mktemp -d)"
readonly -a PUBLIC_PDFS=(
  Bad-Street-Brawler-Power-Glove-Programs.pdf
  PowerGlove-Vision-Changelog.pdf
  PowerGlove-Vision-Configuration-Reference.pdf
  PowerGlove-Vision-Contributing.pdf
  PowerGlove-Vision-Gameplay-Guide.pdf
  PowerGlove-Vision-Guide.pdf
  PowerGlove-Vision-Overview.pdf
  PowerGlove-Vision-Security.pdf
  PowerGlove-Vision-Third-Party-Components.pdf
)

# Remove the private staging directory regardless of build success or failure.
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
  --exclude 'output/' \
  --exclude 'tests/' \
  --exclude 'tmp/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '*.pdf' \
  --exclude '.DS_Store' \
  --exclude 'docs/CODE_REVIEW_MAP.txt' \
  --exclude 'docs/cheatsheet.md' \
  "${PROJECT_DIR}/" "${PACKAGE_TMP}/PowerGlove-Vision/"

python3 "${SCRIPT_DIR}/stamp-build-version.py" "${PACKAGE_TMP}/PowerGlove-Vision/src/powerglove_vision/_build_info.json"

mkdir -p "${PACKAGE_TMP}/PowerGlove-Vision/output/pdf"
for PDF_NAME in "${PUBLIC_PDFS[@]}"; do
  cp "${PROJECT_DIR}/output/pdf/${PDF_NAME}" \
    "${PACKAGE_TMP}/PowerGlove-Vision/output/pdf/${PDF_NAME}"
done

cd "${PACKAGE_TMP}"
zip -qr "${PACKAGE_TMP}/verified-package.zip" PowerGlove-Vision
python3 "${SCRIPT_DIR}/verify-app-lab-package.py" "${PACKAGE_TMP}/verified-package.zip"
mv "${PACKAGE_TMP}/verified-package.zip" "${OUTPUT_ZIP}"
echo "Built ${OUTPUT_ZIP}"
