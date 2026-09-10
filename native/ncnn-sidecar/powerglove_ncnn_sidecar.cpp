/*
 * Project: PowerGlove Vision
 * File: native/ncnn-sidecar/powerglove_ncnn_sidecar.cpp
 * Purpose: Experimental persistent ncnn CPU inference worker.
 * Author: Iain Bennett
 * Copyright (c) 2026 Iain Bennett
 * SPDX-License-Identifier: MIT
 * Change log:
 *   2026-09-09 - Added the persistent ncnn CPU research worker.
 * Full history: docs/CHANGELOG.md and Git history.
 *
 * This research worker is not selected by the production Controller. It keeps
 * the exact palm and landmark networks warm and exchanges fixed binary records
 * with a parent benchmark process.
 */

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "net.h"

namespace {

constexpr std::uint32_t kRequestMagic = 0x50474e43;  // PGNC
constexpr std::uint32_t kResponseMagic = 0x50474e52; // PGNR
constexpr std::uint32_t kPalm = 1;
constexpr std::uint32_t kLandmark = 2;

struct Request {
    std::uint32_t magic;
    std::uint32_t operation;
    std::uint32_t byte_count;
};

struct Response {
    std::uint32_t magic;
    std::uint32_t operation;
    std::uint32_t status;
    std::uint32_t float_count;
    std::uint32_t inference_us;
};

bool read_exact(void* destination, std::size_t bytes) {
    auto* output = static_cast<unsigned char*>(destination);
    while (bytes > 0) {
        const std::size_t count = std::fread(output, 1, bytes, stdin);
        if (count == 0) return false;
        output += count;
        bytes -= count;
    }
    return true;
}

bool write_exact(const void* source, std::size_t bytes) {
    const auto* input = static_cast<const unsigned char*>(source);
    while (bytes > 0) {
        const std::size_t count = std::fwrite(input, 1, bytes, stdout);
        if (count == 0) return false;
        input += count;
        bytes -= count;
    }
    return true;
}

std::size_t logical_size(const ncnn::Mat& value) {
    return static_cast<std::size_t>(value.w) * std::max(1, value.h)
        * std::max(1, value.d) * std::max(1, value.c) * value.elempack;
}

bool append_output(const ncnn::Mat& packed, std::size_t expected,
                   std::vector<float>* output) {
    ncnn::Mat unpacked;
    ncnn::convert_packing(packed, unpacked, 1);
    const std::size_t available = logical_size(unpacked);
    if (available < expected) return false;
    const float* values = static_cast<const float*>(unpacked.data);
    output->insert(output->end(), values, values + expected);
    return true;
}

int run(ncnn::Net* network, const char* input_name,
        const std::vector<std::pair<const char*, std::size_t>>& output_names,
        const std::vector<unsigned char>& input, int width, int height,
        std::vector<float>* output, std::uint32_t* elapsed_us) {
    ncnn::Mat tensor = ncnn::Mat::from_pixels(
        input.data(), ncnn::Mat::PIXEL_RGB, width, height);
    if (input.size() != static_cast<std::size_t>(width * height * 3)) return 10;
    const float normalization[3] = {1.0F / 255.0F, 1.0F / 255.0F, 1.0F / 255.0F};
    tensor.substract_mean_normalize(nullptr, normalization);

    ncnn::Extractor extractor = network->create_extractor();
    if (extractor.input(input_name, tensor) != 0) return 11;
    const auto started = std::chrono::steady_clock::now();
    for (const auto& item : output_names) {
        ncnn::Mat value;
        if (extractor.extract(item.first, value) != 0) return 12;
        if (!append_output(value, item.second, output)) return 13;
    }
    const auto finished = std::chrono::steady_clock::now();
    *elapsed_us = static_cast<std::uint32_t>(
        std::chrono::duration_cast<std::chrono::microseconds>(finished - started).count());
    return 0;
}

bool load(ncnn::Net* network, const std::string& root,
          const char* stem, int threads) {
    network->opt.num_threads = threads;
    network->opt.use_vulkan_compute = false;
    network->opt.use_fp16_packed = false;
    network->opt.use_fp16_storage = false;
    network->opt.use_fp16_arithmetic = false;
    return network->load_param((root + "/" + stem + ".param").c_str()) == 0
        && network->load_model((root + "/" + stem + ".bin").c_str()) == 0;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::fprintf(stderr, "usage: %s MODEL_DIRECTORY THREADS\n", argv[0]);
        return 2;
    }
    const int threads = std::max(1, std::min(4, std::atoi(argv[2])));
    ncnn::Net palm;
    ncnn::Net landmark;
    if (!load(&palm, argv[1], "palm-lite-op", threads)
            || !load(&landmark, argv[1], "hand_exact", threads)) {
        std::fprintf(stderr, "could not load ncnn models\n");
        return 3;
    }

    for (;;) {
        Request request{};
        if (!read_exact(&request, sizeof(request))) break;
        if (request.magic != kRequestMagic) return 4;
        if (request.operation == 0) break;
        const std::uint32_t expected = request.operation == kPalm
            ? 192U * 192U * 3U : request.operation == kLandmark
            ? 224U * 224U * 3U : 0U;
        if (expected == 0 || request.byte_count != expected) return 5;

        std::vector<unsigned char> input(expected);
        if (!read_exact(input.data(), input.size())) return 6;
        std::vector<float> output;
        std::uint32_t inference_us = 0;
        int status = 0;
        if (request.operation == kPalm) {
            output.reserve(2016 + 2016 * 18);
            status = run(&palm, "input", {{"cls", 2016}, {"reg", 2016 * 18}},
                         input, 192, 192, &output, &inference_us);
        } else {
            output.reserve(63 + 1 + 1 + 63);
            status = run(&landmark, "input_1",
                         {{"Identity", 63}, {"Identity_1", 1},
                          {"Identity_2", 1}, {"Identity_3", 63}},
                         input, 224, 224, &output, &inference_us);
        }
        Response response{kResponseMagic, request.operation,
                          static_cast<std::uint32_t>(status),
                          static_cast<std::uint32_t>(output.size()), inference_us};
        if (!write_exact(&response, sizeof(response))
                || (!output.empty() && !write_exact(
                    output.data(), output.size() * sizeof(float)))) return 7;
        std::fflush(stdout);
    }
    return 0;
}
