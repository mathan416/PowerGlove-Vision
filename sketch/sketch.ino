// Project: PowerGlove Vision
// File: sketch/sketch.ino
// Purpose: Render protected status, pairing, and gesture-profile feedback on the UNO Q LED matrix.
// Author: Iain Bennett
// Copyright (c) 2026 Iain Bennett
// SPDX-License-Identifier: MIT
// Change log:
//   2026-09-02 - Added to PowerGlove Vision.
//   2026-09-03 - Standardized source documentation and maintenance metadata.
//   2026-09-03 - Added the gestures-idle Power Glove attract animation.
//   2026-09-03 - Refined the attract animation with cuff travel, spark motion, and grayscale pulsing.
//   2026-09-03 - Added a scanning L animation for Learn mode.
// Full history: docs/CHANGELOG.md and Git history.

#include "Arduino_RouterBridge.h"
#include <Arduino_LED_Matrix.h>

// App Lab starts this sketch after the UNO Q's protected system-boot display
// has finished. The Python vision process then selects one of these states.
enum PowerGloveStatus {
  PG_OFF = 0,
  PG_LOADING = 1,
  PG_READY = 2,
  PG_TRACKING = 3,
  PG_ERROR = 4,
  PG_PAIRING = 5,
  PG_GESTURES_IDLE = 6,
  PG_LEARNING = 7,
  PG_TUNING = 8,
};

Arduino_LED_Matrix matrix;
volatile int requestedStatus = PG_LOADING;
volatile int requestedProfile = 0;
volatile uint32_t requestedPairingId = 0;
volatile int requestedPairingPin = 0;
int drawnStatus = -1;
int drawnProfile = -1;
unsigned long nextFrameAt = 0;
uint8_t animationFrame = 0;

// Original 8-bit artwork sized for the UNO Q's 8x13 blue matrix. Characters
// encode brightness: '.' is off, '1' through '7' select exact grayscale
// levels, 'o' is legacy dim, and 'O' is full brightness.
const char* const loadingFrames[][8] = {
  {
    "..O.O.O.O....",
    "..o.o.o.o....",
    "..oooooooo...",
    "..ooooooo....",
    "..oooooo.....",
    "...oooo......",
    "...oooo......",
    "...oooo......",
  },
  {
    "..o.o.o.o....",
    "..O.O.O.O....",
    "..oooooooo...",
    "..ooooooo....",
    "..oooooo.....",
    "...oooo......",
    "...oooo......",
    "...oooo......",
  },
  {
    "..o.o.o.o....",
    "..o.o.o.o....",
    "..OOOOOOOO...",
    "..ooooooo....",
    "..oooooo.....",
    "...oooo......",
    "...oooo......",
    "...oooo......",
  },
  {
    "..o.o.o.o....",
    "..o.o.o.o....",
    "..oooooooo...",
    "..OOOOOOO....",
    "..OOOOOO.....",
    "...oooo......",
    "...oooo......",
    "...oooo......",
  },
  {
    "..o.o.o.o....",
    "..o.o.o.o....",
    "..oooooooo...",
    "..ooooooo....",
    "..oooooo.....",
    "...OOOO......",
    "...OOOO......",
    "...OOOO......",
  },
};

const char* const readyFrame[8] = {
  ".OOOO..OOOOO.",
  ".O...O.O.....",
  ".OOOO..O.OOO.",
  ".O.....O...O.",
  ".O.....O...O.",
  ".O.....OOOOO.",
  ".............",
  ".O.O.O.O.O.O.",
};

const char* const trackingFrames[][8] = {
  {
    ".....OOO.....", "...OOoOOO...", "..OO...OOO...", "..O..O..O....",
    "..OO...OO....", "...OOOOO.....", ".....O.......", "....OOO......",
  },
  {
    ".....ooo.....", "...ooOooo...", "..oo...ooo...", "..o..O..o....",
    "..oo...oo....", "...ooooo.....", ".....O.......", "....ooo......",
  },
};

const char* const errorFrame[8] = {
  ".OO.......OO.", ".oOO.....OOo.", "...OO...OO...", "....OO.OO....",
  ".....OOO.....", "....OO.OO....", "...OO...OO...", ".OO.......OO.",
};

// Pinball-display-inspired glove silhouettes for the healthy gestures-paused
// state. Edge highlighting gives the tiny monochrome image depth without
// saturating the palm into an unreadable rectangle.
const char* const idleOpenGlove[8] = {
  "....#.#.#.#..", "....#.#.#.#..", "...########..", "..#########..",
  "..########...", "...######....", "...####......", "...####......",
};

const char* const idleCurlGlove[8] = {
  ".............", "....#.#.#.#..", "...########..", "..#########..",
  "..########...", "...######....", "...####......", "...####......",
};

const char* const idleFistGlove[8] = {
  ".............", "...######....", "..########...", "..########...",
  "..########...", "...######....", "...####......", "...####......",
};

// Per-frame timing makes the entrance, finger curl, spark, and outline pulse
// distinct. The final frame holds long enough to serve as a friendly idle icon.
const uint16_t idleFrameDurations[] = {
  75, 75, 75, 105,              // energy streak
  105, 105, 105, 130,           // cuff travels right-to-left
  90, 90, 180,                  // glove rises from the cuff
  90, 125, 90, 150,             // curl, clench, reopen
  70, 70, 70, 70, 70, 70, 70, 70, // spark and comet trail
  90, 120, 850,                 // settle, outline pulse, hold
};

// Five-pixel-wide glyphs A-I, B, S, and G. Program profiles use a large
// centred letter; the dedicated game profiles display BS and GB.
const uint8_t programGlyphs[9][7] = {
  {14,17,17,31,17,17,17}, {30,17,17,30,17,17,30},
  {14,17,16,16,16,17,14}, {30,17,17,17,17,17,30},
  {31,16,16,30,16,16,31}, {31,16,16,30,16,16,16},
  {14,17,16,23,17,17,14}, {17,17,17,31,17,17,17},
  {31,4,4,4,4,4,31},
};
const uint8_t glyphB[7] = {30,17,17,30,17,17,30};
const uint8_t glyphS[7] = {15,16,16,14,1,1,30};
const uint8_t glyphG[7] = {14,17,16,23,17,17,14};
const uint8_t digitGlyphs[10][7] = {
  {14,17,19,21,25,17,14}, {4,12,4,4,4,4,14},
  {14,17,1,2,4,8,31}, {30,1,1,14,1,1,30},
  {2,6,10,18,31,2,2}, {31,16,16,30,1,1,30},
  {14,16,16,30,17,17,14}, {31,1,2,4,8,8,8},
  {14,17,17,14,17,17,14}, {14,17,17,15,1,1,14},
};
const uint8_t glyphN[7] = {17,25,25,21,19,19,17};
const uint8_t glyphP[7] = {30,17,17,30,16,16,16};
const uint8_t glyphT[7] = {31,4,4,4,4,4,4};
const uint8_t glyphL[7] = {16,16,16,16,16,16,31};

void drawRows(const char* const rows[8]);
void setPixelMax(uint8_t* pixels, int x, int y, uint8_t brightness);

// Blend one five-column glyph into the 8x13 matrix framebuffer.
void placeGlyph(uint8_t* pixels, const uint8_t glyph[7], int left, uint8_t brightness) {
  for (int y = 0; y < 7; ++y) {
    for (int x = 0; x < 5; ++x) {
      if (glyph[y] & (1 << (4 - x))) {
        pixels[y * 13 + left + x] = brightness;
      }
    }
  }
}

// Draw one hexadecimal digit used by the physical certificate identity.
void placeHexGlyph(uint8_t* pixels, uint8_t value, int left) {
  if (value < 10) {
    placeGlyph(pixels, digitGlyphs[value], left, 7);
  } else {
    placeGlyph(pixels, programGlyphs[value - 10], left, 7);
  }
}

// Alternate the certificate identity and one-time PIN during secure pairing.
void drawPairing(uint8_t frame) {
  uint8_t pixels[104] = {0};
  if (frame == 0) {
    placeGlyph(pixels, programGlyphs[8], 1, 7);  // I
    placeGlyph(pixels, programGlyphs[3], 7, 7);  // D
  } else if (frame <= 4) {
    const int first = (frame - 1) * 2;
    if (first < 7) placeHexGlyph(pixels, (requestedPairingId >> ((6 - first) * 4)) & 0xF, 1);
    if (first + 1 < 7) placeHexGlyph(pixels, (requestedPairingId >> ((5 - first) * 4)) & 0xF, 7);
  } else if (frame == 5) {
    placeGlyph(pixels, glyphP, 1, 7);
    placeGlyph(pixels, glyphN, 7, 7);
  } else {
    const int first = (frame - 6) * 2;
    int divisor = 1;
    for (int i = 0; i < 5 - first; ++i) divisor *= 10;
    placeGlyph(pixels, digitGlyphs[(requestedPairingPin / divisor) % 10], 1, 7);
    placeGlyph(pixels, digitGlyphs[(requestedPairingPin / (divisor / 10)) % 10], 7, 7);
  }
  matrix.draw(pixels);
}

// Render a compact program or game-profile identifier.
void drawProfile(int profile, bool pulse) {
  uint8_t pixels[104] = {0};
  const uint8_t brightness = pulse ? 4 : 7;
  if (profile >= 1 && profile <= 9) {
    placeGlyph(pixels, programGlyphs[profile - 1], 4, brightness);
  } else if (profile == 10) {
    placeGlyph(pixels, glyphB, 1, brightness);
    placeGlyph(pixels, glyphS, 7, brightness);
  } else if (profile == 11) {
    placeGlyph(pixels, glyphG, 1, brightness);
    placeGlyph(pixels, glyphB, 7, brightness);
  } else {
    drawRows(readyFrame);
    return;
  }
  matrix.draw(pixels);
}

// Show a legible L with a bright scan line so Learn mode remains visually
// active without resembling a game-profile code or an error condition.
void drawLearning(uint8_t frame) {
  uint8_t pixels[104] = {0};
  placeGlyph(pixels, glyphL, 4, 3);
  const int scanRow = frame % 8;
  for (int x = 4; x < 9; ++x) {
    if (scanRow < 7 && (glyphL[scanRow] & (1 << (8 - x)))) {
      setPixelMax(pixels, x, scanRow, 7);
    }
    if (scanRow > 0 && scanRow - 1 < 7 &&
        (glyphL[scanRow - 1] & (1 << (8 - x)))) {
      setPixelMax(pixels, x, scanRow - 1, 5);
    }
  }
  matrix.draw(pixels);
}

// Convert character-based artwork into matrix brightness values and display it.
void drawRows(const char* const rows[8]) {
  uint8_t pixels[104];
  for (int y = 0; y < 8; ++y) {
    for (int x = 0; x < 13; ++x) {
      const char value = rows[y][x];
      if (value >= '1' && value <= '7') {
        pixels[y * 13 + x] = value - '0';
      } else {
        pixels[y * 13 + x] = value == 'O' ? 7 : (value == 'o' ? 2 : 0);
      }
    }
  }
  matrix.draw(pixels);
}

// Raise one matrix pixel without allowing a dim layer to overwrite a brighter
// outline, spark core, or comet trail.
void setPixelMax(uint8_t* pixels, int x, int y, uint8_t brightness) {
  if (x < 0 || x >= 13 || y < 0 || y >= 8) {
    return;
  }
  const int index = y * 13 + x;
  if (brightness > pixels[index]) {
    pixels[index] = brightness;
  }
}

// Test whether a coordinate belongs to one of the 13x8 glove silhouettes.
bool isGlovePixel(const char* const mask[8], int x, int y) {
  return x >= 0 && x < 13 && y >= 0 && y < 8 && mask[y][x] == '#';
}

// Render a glove with separate body and edge levels. minRow supports the two
// reveal frames that grow the hand upward from the already-positioned cuff.
void drawGlove(
  uint8_t* pixels,
  const char* const mask[8],
  uint8_t bodyBrightness,
  uint8_t edgeBrightness,
  int minRow = 0
) {
  for (int y = minRow; y < 8; ++y) {
    for (int x = 0; x < 13; ++x) {
      if (!isGlovePixel(mask, x, y)) {
        continue;
      }
      const bool edge =
        !isGlovePixel(mask, x - 1, y) || !isGlovePixel(mask, x + 1, y) ||
        !isGlovePixel(mask, x, y - 1) || !isGlovePixel(mask, x, y + 1);
      setPixelMax(pixels, x, y, edge ? edgeBrightness : bodyBrightness);
    }
  }
}

// Render one complete beat of the gestures-paused attract sequence. Motion is
// intentionally broad: the cuff crosses seven columns, the fingers curl over
// three poses, and the spark uses a bright core plus two-position comet trail.
void drawIdleFrame(uint8_t frame) {
  uint8_t pixels[104] = {0};

  if (frame < 4) {
    const int coreX[] = {0, 4, 8, 12};
    for (int y = 0; y < 8; ++y) {
      const int x = coreX[frame] + abs(y - 3) / 2;
      setPixelMax(pixels, x - 2, y, 1);
      setPixelMax(pixels, x - 1, y, 4);
      setPixelMax(pixels, x, y, 7);
    }
  } else if (frame < 8) {
    const int cuffX[] = {10, 8, 5, 3};
    const int left = cuffX[frame - 4];
    for (int y = 6; y < 8; ++y) {
      setPixelMax(pixels, left - 1, y, 2);
      for (int x = left; x < left + 4; ++x) {
        setPixelMax(pixels, x, y, x == left ? 7 : 4);
      }
      setPixelMax(pixels, left + 4, y, 2);
    }
  } else if (frame < 11) {
    const int revealRows[] = {5, 3, 0};
    drawGlove(pixels, idleOpenGlove, 2, 5, revealRows[frame - 8]);
  } else if (frame == 11 || frame == 13) {
    drawGlove(pixels, idleCurlGlove, 2, 5);
  } else if (frame == 12) {
    drawGlove(pixels, idleFistGlove, 2, 6);
  } else if (frame >= 15 && frame < 23) {
    const int sparkX[] = {3, 4, 5, 5, 6, 7, 8, 10};
    const int sparkY[] = {7, 6, 5, 4, 3, 2, 1, 0};
    const int sparkIndex = frame - 15;
    drawGlove(pixels, idleOpenGlove, 1, 3);
    if (sparkIndex >= 2) {
      setPixelMax(
        pixels, sparkX[sparkIndex - 2], sparkY[sparkIndex - 2], 3
      );
    }
    if (sparkIndex >= 1) {
      setPixelMax(
        pixels, sparkX[sparkIndex - 1], sparkY[sparkIndex - 1], 5
      );
    }
    const int x = sparkX[sparkIndex];
    const int y = sparkY[sparkIndex];
    setPixelMax(pixels, x - 1, y, 4);
    setPixelMax(pixels, x + 1, y, 4);
    setPixelMax(pixels, x, y - 1, 4);
    setPixelMax(pixels, x, y + 1, 4);
    setPixelMax(pixels, x, y, 7);
  } else if (frame == 24) {
    drawGlove(pixels, idleOpenGlove, 4, 7);
  } else {
    drawGlove(pixels, idleOpenGlove, 2, 5);
  }

  matrix.draw(pixels);
}

// Router Bridge endpoint: request a bounded status code from the Linux app.
void set_powerglove_status(int status) {
  if (status < PG_OFF || status > PG_TUNING) {
    status = PG_ERROR;
  }
  requestedStatus = status;
}

// Router Bridge endpoint: show the certificate identity and one-time PIN.
void set_powerglove_pairing(int pairingId, int pairingPin) {
  requestedPairingId = (uint32_t)pairingId & 0x0FFFFFFF;
  requestedPairingPin = pairingPin >= 0 && pairingPin <= 999999 ? pairingPin : 0;
  requestedStatus = PG_PAIRING;
}

// Router Bridge endpoint: select the active gesture-profile display.
void set_powerglove_profile(int profile) {
  requestedProfile = (profile >= 0 && profile <= 11) ? profile : 0;
}

// Initialize the matrix, register bridge endpoints, and show loading state.
void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);
  matrix.clear();

  Bridge.begin();
  Bridge.provide("set_powerglove_status", set_powerglove_status);
  Bridge.provide("set_powerglove_profile", set_powerglove_profile);
  Bridge.provide("set_powerglove_pairing", set_powerglove_pairing);
}

// Refresh animations only when their frame or requested state changes.
void loop() {
  const int status = requestedStatus;
  const int profile = requestedProfile;
  const unsigned long now = millis();

  if (status != drawnStatus || profile != drawnProfile) {
    drawnStatus = status;
    drawnProfile = profile;
    animationFrame = 0;
    nextFrameAt = 0;
    if (status == PG_OFF) {
      matrix.clear();
    } else if (status == PG_READY) {
      drawProfile(profile, false);
    }
  }

  if (now < nextFrameAt) {
    return;
  }

  if (status == PG_LOADING) {
    drawRows(loadingFrames[animationFrame]);
    animationFrame = (animationFrame + 1) % 5;
    nextFrameAt = now + 115;
  } else if (status == PG_TRACKING) {
    if (profile == 0) {
      drawRows(trackingFrames[animationFrame]);
    } else {
      drawProfile(profile, animationFrame != 0);
    }
    animationFrame = (animationFrame + 1) % 2;
    nextFrameAt = now + 360;
  } else if (status == PG_ERROR) {
    if (animationFrame == 0) {
      drawRows(errorFrame);
    } else {
      matrix.clear();
    }
    animationFrame = (animationFrame + 1) % 2;
    nextFrameAt = now + 420;
  } else if (status == PG_PAIRING) {
    drawPairing(animationFrame);
    animationFrame = (animationFrame + 1) % 9;
    nextFrameAt = now + 650;
  } else if (status == PG_GESTURES_IDLE) {
    drawIdleFrame(animationFrame);
    nextFrameAt = now + idleFrameDurations[animationFrame];
    animationFrame = (animationFrame + 1) %
      (sizeof(idleFrameDurations) / sizeof(idleFrameDurations[0]));
  } else if (status == PG_TUNING) {
    uint8_t pixels[104] = {0};
    placeGlyph(pixels, glyphT, 4, 7);
    matrix.draw(pixels);
    nextFrameAt = now + 250;
  } else if (status == PG_LEARNING) {
    drawLearning(animationFrame);
    animationFrame = (animationFrame + 1) % 8;
    nextFrameAt = now + 160;
  }
}
