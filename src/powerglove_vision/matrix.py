from __future__ import annotations

from enum import IntEnum
from typing import Any, Callable


class MatrixStatus(IntEnum):
    OFF = 0
    LOADING = 1
    READY = 2
    TRACKING = 3
    ERROR = 4


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
        return self.enabled and self._call is not None

    def set_status(self, status: MatrixStatus) -> bool:
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

    def set_profile(self, profile: str | None) -> bool:
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
