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
};

Arduino_LED_Matrix matrix;
volatile int requestedStatus = PG_LOADING;
volatile int requestedProfile = 0;
int drawnStatus = -1;
int drawnProfile = -1;
unsigned long nextFrameAt = 0;
uint8_t animationFrame = 0;

// Original 8-bit artwork sized for the UNO Q's 8x13 blue matrix. Characters
// encode brightness: '.' is off, 'o' is dim, 'O' is full brightness.
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

void drawRows(const char* const rows[8]);

void placeGlyph(uint8_t* pixels, const uint8_t glyph[7], int left, uint8_t brightness) {
  for (int y = 0; y < 7; ++y) {
    for (int x = 0; x < 5; ++x) {
      if (glyph[y] & (1 << (4 - x))) {
        pixels[y * 13 + left + x] = brightness;
      }
    }
  }
}

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

void drawRows(const char* const rows[8]) {
  uint8_t pixels[104];
  for (int y = 0; y < 8; ++y) {
    for (int x = 0; x < 13; ++x) {
      const char value = rows[y][x];
      pixels[y * 13 + x] = value == 'O' ? 7 : (value == 'o' ? 2 : 0);
    }
  }
  matrix.draw(pixels);
}

void set_powerglove_status(int status) {
  if (status < PG_OFF || status > PG_ERROR) {
    status = PG_ERROR;
  }
  requestedStatus = status;
}

void set_powerglove_profile(int profile) {
  requestedProfile = (profile >= 0 && profile <= 11) ? profile : 0;
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);
  matrix.clear();

  Bridge.begin();
  Bridge.provide("set_powerglove_status", set_powerglove_status);
  Bridge.provide("set_powerglove_profile", set_powerglove_profile);
}

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
  }
}
