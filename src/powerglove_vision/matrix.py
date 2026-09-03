# Project: PowerGlove Vision
# File: src/powerglove_vision/matrix.py
# Purpose: Drive UNO Q LED matrix status, pairing, and active-profile displays through Router Bridge.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
# Full history: docs/CHANGELOG.md and Git history.

"""Drive UNO Q LED matrix status, pairing, and active-profile displays through Router Bridge."""

from __future__ import annotations

import time
from enum import IntEnum
from typing import Any, Callable


class MatrixStatus(IntEnum):
    """Enumerate the display states understood by the UNO Q sketch."""
    OFF = 0
    LOADING = 1
    READY = 2
    TRACKING = 3
    ERROR = 4
    PAIRING = 5


class UnoQMatrix:
    """Optional bridge to the UNO Q's STM32-driven 8x13 LED matrix."""

    def __init__(
        self,
        enabled: bool = True,
        call: Callable[..., Any] | None = None,
    ) -> None:
        self.enabled = enabled
        self.last_status: MatrixStatus | None = None
        self.last_error: str | None = None
        self.last_profile: str | None = None
        self.pairing_until = 0.0
        self._call = call
        if enabled and self._call is None:
            try:
                from arduino.app_utils import Bridge

                self._call = Bridge.call
            except ImportError:
                # Development computers and ordinary Debian installations do
                # not provide App Lab's Bridge. Matrix support is optional.
                self.enabled = False

    @property
    def available(self) -> bool:
        """Return whether Router Bridge matrix calls can currently be attempted."""
        return self.enabled and self._call is not None

    def set_status(self, status: MatrixStatus) -> bool:
        """Display a new status unless a temporary pairing display owns the matrix."""
        if status not in {MatrixStatus.OFF, MatrixStatus.PAIRING} and time.monotonic() < self.pairing_until:
            return self.available
        if status == self.last_status:
            return self.available
        self.last_status = status
        if not self.available:
            return False
        try:
            assert self._call is not None
            self._call("set_powerglove_status", int(status))
            self.last_error = None
            return True
        except Exception as exc:  # Bridge errors vary by App Lab release.
            self.last_error = str(exc)
            return False

    def show_pairing(self, certificate_id: str, pin: str, seconds: int = 120) -> bool:
        """Show a certificate prefix and one-time approval PIN on the physical matrix."""
        if len(certificate_id) != 7 or any(character not in "0123456789ABCDEF" for character in certificate_id):
            raise ValueError("invalid certificate identity")
        if len(pin) != 6 or not pin.isdigit():
            raise ValueError("invalid pairing PIN")
        self.pairing_until = time.monotonic() + seconds
        self.last_status = MatrixStatus.PAIRING
        if not self.available:
            return False
        try:
            assert self._call is not None
            self._call("set_powerglove_pairing", int(certificate_id, 16), int(pin))
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def set_profile(self, profile: str | None) -> bool:
        """Display the compact numeric code for the active gesture profile."""
        codes = {
            **{f"program_{letter}": index for index, letter in enumerate("abcdefghi", 1)},
            "bad_street_brawler": 10,
            "super_glove_ball": 11,
        }
        if profile == self.last_profile:
            return self.available
        self.last_profile = profile
        if not self.available:
            return False
        try:
            assert self._call is not None
            self._call("set_powerglove_profile", codes.get(profile, 0))
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False
