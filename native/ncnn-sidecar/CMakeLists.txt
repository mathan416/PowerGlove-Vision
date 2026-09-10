# Project: PowerGlove Vision
# File: native/ncnn-sidecar/CMakeLists.txt
# Purpose: Build the isolated ncnn CPU research sidecar.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Added the isolated ncnn CPU research build.
# Full history: docs/CHANGELOG.md and Git history.

cmake_minimum_required(VERSION 3.16)
project(powerglove_ncnn_sidecar LANGUAGES CXX)

find_package(ncnn REQUIRED)

add_executable(powerglove_ncnn_sidecar powerglove_ncnn_sidecar.cpp)
target_compile_features(powerglove_ncnn_sidecar PRIVATE cxx_std_17)
target_link_libraries(powerglove_ncnn_sidecar PRIVATE ncnn)
