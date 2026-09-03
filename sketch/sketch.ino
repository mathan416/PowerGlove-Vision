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

// Pinball-display-inspired attract sequence for the healthy gestures-paused
// state. The frames deliberately separate the streak, travelling cuff, open
// hand, clench, spark path, and pulse so each beat reads on the 13x8 display.
const char* const idleFrames[][8] = {
  {
    "17...........", ".173.........", ".173.........", "..173........",
    "..173........", ".173.........", ".173.........", "17...........",
  },
  {
    "....17.......", ".....173.....", ".....173.....", "......173....",
    "......173....", ".....173.....", ".....173.....", "....17.......",
  },
  {
    "........17...", ".........173.", ".........173.", "..........173",
    "..........173", ".........173.", ".........173.", "........17...",
  },
  {
    ".............", ".............", ".............", ".............",
    ".............", ".............", "47...........", "47...........",
  },
  {
    ".............", ".............", ".............", ".............",
    ".............", ".............", "4447.........", "4447.........",
  },
  {
    ".............", ".............", ".............", ".............",
    ".............", ".............", "...4447......", "...4447......",
  },
  {
    "....4.4.4.4..", "....4.4.4.4..", "...44444444..", "..444444444..",
    "..44444444...", "...444444....", "...4444......", "...4444......",
  },
  {
    ".............", "...555555....", "..55555555...", "..55333355...",
    "..55555555...", "...555555....", "...5555......", "...5555......",
  },
  {
    "....3.3.3.3..", "....3.3.3.3..", "...33333333..", "..333333333..",
    "..33333333...", "...333333....", "...3333......", "...3333......",
  },
  {
    "....2.2.2.2..", "....2.2.2.2..", "...22222222..", "..222222222..",
    "..22222222...", "...242222....", "...4742......", "...2422......",
  },
  {
    "....2.2.2.2..", "....2.2.2.2..", "...22222222..", "..222222222..",
    "..22422222...", "...474222....", "...2422......", "...2222......",
  },
  {
    "....2.2.2.2..", "....2.2.2.2..", "...22422222..", "..224742222..",
    "..24742222...", "...242222....", "...2222......", "...2222......",
  },
  {
    "....2.2.2.2..", "....2.4.2.2..", "...22474222..", "..222474222..",
    "..22242222...", "...222222....", "...2222......", "...2222......",
  },
  {
    "....2.2.4.2..", "....2.2.4.2..", "...22224742..", "..222222422..",
    "..22222222...", "...222222....", "...2222......", "...2222......",
  },
  {
    "....2.2.2.4..", "....2.2.4.7..", "...22222242..", "..222222222..",
    "..22222222...", "...222222....", "...2222......", "...2222......",
  },
  {
    "....3.3.3.3..", "....3.3.3.3..", "...33333333..", "..333333333..",
    "..33333333...", "...333333....", "...3333......", "...3333......",
  },
  {
    "....7.7.7.7..", "....7.7.7.7..", "...77777777..", "..777777777..",
    "..77777777...", "...777777....", "...7777......", "...7777......",
  },
  {
    "....4.4.4.4..", "....4.4.4.4..", "...44444444..", "..444444444..",
    "..44444444...", "...444444....", "...4444......", "...4444......",
  },
};

// Per-frame timing makes the action beats crisp while preserving a readable
// final hold. Short spark frames imply speed; the bright pulse is intentionally
// brief so it reads as one flash instead of a second glove design.
const uint16_t idleFrameDurations[] = {
  90, 90, 110, 110, 110, 130, 190, 140, 150,
  85, 85, 85, 85, 85, 85, 100, 110, 900,
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

void drawRows(const char* const rows[8]);

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

// Router Bridge endpoint: request a bounded status code from the Linux app.
void set_powerglove_status(int status) {
  if (status < PG_OFF || status > PG_GESTURES_IDLE) {
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
    drawRows(idleFrames[animationFrame]);
    nextFrameAt = now + idleFrameDurations[animationFrame];
    animationFrame = (animationFrame + 1) %
      (sizeof(idleFrames) / sizeof(idleFrames[0]));
  }
}
