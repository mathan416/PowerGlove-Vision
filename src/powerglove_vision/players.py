# Project: PowerGlove Vision
# File: src/powerglove_vision/players.py
# Purpose: Persist bounded player presets, Academy progress, and portable hand settings.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-06 - Preserve and map optional per-player comfortable reach spans.
#   2026-09-06 - Implement approved player and connectivity refinements.
#   2026-09-06 - Add complete hand-setup backups and explicit calibration restoration.
#   2026-09-06 - Add atomic player presets and credential-free hand backups.

"""Owned under the tuning lock; one atomic file is authoritative for all players."""

import copy
import json
import uuid
import math
from dataclasses import asdict

from .model import Calibration

COURSE = 1
LESSONS = 16
MAX_PLAYERS = 12


def calibration_value(data):
    """Accept only finite, bounded neutral-pose fields from a portable backup."""
    if (not isinstance(data, dict) or set(data) != {"version", "neutral"}
            or type(data["version"]) is not int or data["version"] not in (1, 2)):
        raise ValueError("Invalid hand calibration format.")
    values = data["neutral"]
    required = {"palm_x", "palm_y", "palm_scale", "roll"}
    if not isinstance(values, dict) or not required <= set(values) or set(values) - required - {"noise_x", "noise_y", "reach_left", "reach_right", "reach_up", "reach_down"}:
        raise ValueError("Invalid hand calibration fields.")
    value = Calibration(**values)
    fields = asdict(value)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in fields.values()):
        raise ValueError("Calibration must contain finite numbers.")
    if (not value.valid_reach() or not 0 <= value.palm_x <= 1 or not 0 <= value.palm_y <= 1
            or not 0 < value.palm_scale <= 2 or not -math.pi <= value.roll <= math.pi
            or not 0 <= value.noise_x <= 1 or not 0 <= value.noise_y <= 1):
        raise ValueError("Calibration values are outside the camera range.")
    return {"version": 2, "neutral": fields}


def player_name(value):
    """Allow readable short names without control characters."""
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 32 or not value.isprintable():
        raise ValueError("Use a player name of 1–32 characters.")
    return value.strip()


def progress(value):
    """Validate this course's lesson indices; a new course starts fresh."""
    if not isinstance(value, dict) or set(value) != {"course", "completed", "lesson"}:
        raise ValueError("Invalid Academy progress.")
    if type(value["course"]) is not int or value["course"] != COURSE:
        raise ValueError("This Academy course has changed. Reload the page.")
    done, lesson = value["completed"], value["lesson"]
    if (not isinstance(done, list) or len(done) > LESSONS or
            any(type(n) is not int or not 0 <= n < LESSONS for n in done) or
            type(lesson) is not int or not 0 <= lesson < LESSONS):
        raise ValueError("Invalid Academy lesson.")
    return {"course": COURSE, "completed": sorted(set(done)), "lesson": lesson}


def blank_progress():
    """Return independent progress for a new player."""
    return {"course": COURSE, "completed": [], "lesson": 0}


class PlayerSettings:
    """Keep imported data narrow and commit memory only after the disk write."""
    def __init__(self, path, validate, channels):
        self.path, self.validate = path, validate
        self.channels = set(channels)
        self.error = None
        self.legacy_backup = None
        self.legacy_backup_version = 1
        self.data = {"version": 4, "active": "default", "generation": 0,
                     "calibration_restore": None,
                     "players": {"default": {"name": "Player 1", "thresholds": {},
                         "progress": blank_progress(), "needs_center": False, "calibration": None}}}
        try:
            if path.exists():
                if path.stat().st_size > 65536:
                    raise ValueError("Player settings too large")
                saved = json.loads(path.read_text())
                if not isinstance(saved, dict):
                    raise ValueError("Invalid player settings object")
                if saved.get("version") == 1:
                    self.data["players"]["default"]["thresholds"] = validate(saved["thresholds"])
                    self.legacy_backup = json.dumps({"version": 1, "thresholds": self.active["thresholds"]}, indent=2) + "\n"
                else:
                    self.data = self.validate_store(saved)
                    if saved.get("version") in (2, 3):
                        self.legacy_backup = json.dumps(saved, indent=2) + "\n"
                        self.legacy_backup_version = saved["version"]
        except (OSError, ValueError, KeyError, TypeError):
            self.error = "Saved player settings could not be loaded. Restore a hand-settings backup to recover; the original file has not been changed."

    def validate_store(self, data):
        """Validate persisted records before exposing them to the app."""
        data = copy.deepcopy(data)
        if isinstance(data, dict) and data.get("version") == 2 and "calibration_restore" not in data:
            data["version"] = 3
            data["calibration_restore"] = None
        if isinstance(data, dict) and data.get("version") == 3:
            data["version"] = 4
            if not isinstance(data.get("players"), dict):
                raise ValueError("Invalid players")
            for item in data["players"].values():
                if not isinstance(item, dict):
                    raise ValueError("Invalid player record")
                item["calibration"] = None
        if not isinstance(data, dict) or set(data) != {"version", "active", "generation", "players", "calibration_restore"} or type(data["version"]) is not int or data["version"] != 4:
            raise ValueError("Unsupported player settings")
        players = data["players"]
        if not isinstance(players, dict) or not 1 <= len(players) <= MAX_PLAYERS or data["active"] not in players:
            raise ValueError("Invalid players")
        if type(data["generation"]) is not int or data["generation"] < 0:
            raise ValueError("Invalid player revision")
        for key, item in players.items():
            if not isinstance(key, str) or not 1 <= len(key) <= 32 or not key.isalnum():
                raise ValueError("Invalid player identifier")
            if not isinstance(item, dict) or set(item) != {"name", "thresholds", "progress", "needs_center", "calibration"} or type(item["needs_center"]) is not bool:
                raise ValueError("Invalid player record")
            item["name"] = player_name(item["name"])
            item["thresholds"] = self.validate(item["thresholds"])
            item["progress"] = progress(item["progress"])
            if item["calibration"] is not None:
                item["calibration"] = calibration_value(item["calibration"])
        pending = data["calibration_restore"]
        if pending is not None:
            data["calibration_restore"] = calibration_value(pending)
            if not players[data["active"]]["needs_center"]:
                raise ValueError("A pending restore must pause controller output")
        return copy.deepcopy(data)

    @property
    def active(self):
        """Return the active record, only for callers holding the tuning lock."""
        return self.data["players"][self.data["active"]]

    def commit(self, data, recover=False):
        """Preserve both memory and file on validation or write failure."""
        from .game_registry import atomic_write
        if self.error and not recover:
            raise ValueError(self.error)
        clean = self.validate_store(data)
        if self.legacy_backup is not None:
            backup = self.path.with_name("gesture-tuning-v%d-backup.json" % self.legacy_backup_version)
            if not backup.exists():
                atomic_write(backup, self.legacy_backup)
        atomic_write(self.path, json.dumps(clean, ensure_ascii=True, indent=2) + "\n")
        self.data, self.error = clean, None
        self.legacy_backup = None

    def snapshot(self):
        """Return names and progress without thresholds or device credentials."""
        return {"active": self.data["active"], "generation": self.data["generation"],
                "players": [{"id": key, "name": item["name"]} for key, item in self.data["players"].items()],
                "progress": copy.deepcopy(self.active["progress"]),
                "needs_center": self.active["needs_center"],
                "has_saved_calibration": self.active["calibration"] is not None,
                "restoring_calibration": self.data["calibration_restore"] is not None, "error": self.error}

    def save_thresholds(self, values):
        """Save tuning directly into the active player's record."""
        data = copy.deepcopy(self.data)
        data["players"][data["active"]]["thresholds"] = self.validate(values)
        self.commit(data)

    def centered(self, generation, reference=None):
        """Only acknowledge calibration started for the still-active player."""
        if generation == self.data["generation"]:
            data = copy.deepcopy(self.data)
            data["players"][data["active"]]["needs_center"] = False
            if reference is not None:
                data["players"][data["active"]]["calibration"] = calibration_value({"version":2,"neutral":asdict(reference)})
            data["calibration_restore"] = None
            self.commit(data)

    def command(self, request):
        """Apply one bounded operation; reject stale tabs after switches or resets."""
        action = request.get("action")
        if action == "read":
            return self.snapshot()
        if request.get("player") != self.data["active"] or type(request.get("generation")) is not int or request.get("generation") != self.data["generation"]:
            raise ValueError("The active player or progress changed. Reload player settings.")
        if action == "export":
            if self.error:
                raise ValueError(self.error)
            return {"backup": {"format": "powerglove-hand-setup", "version": 2,
                    "name": self.active["name"], "thresholds": copy.deepcopy(self.active["thresholds"]),
                    "calibration": copy.deepcopy(self.active["calibration"])}}
        data = copy.deepcopy(self.data)
        item = data["players"][data["active"]]
        if action in ("create", "select", "delete", "restore"):
            data["calibration_restore"] = None
        if action == "joystick_deadzone":
            value = request.get("value")
            if type(value) not in (int, float) or not 0.14 <= value <= 1.0:
                raise ValueError("Choose a joystick dead zone between 0.14 and 1.00.")
            item["thresholds"].update(self.validate({
                direction: {"on": value, "off": value / 2}
                for direction in ("left", "right", "up", "down")
            }))
            data["generation"] += 1
        elif action == "progress":
            incoming = progress(request.get("progress"))
            incoming["completed"] = sorted(set(item["progress"]["completed"]) | set(incoming["completed"]))
            item["progress"] = incoming
        elif action == "reset_progress":
            item["progress"] = blank_progress()
            data["generation"] += 1
        elif action == "create":
            if len(data["players"]) >= MAX_PLAYERS:
                raise ValueError("You can save up to 12 players.")
            name = player_name(request.get("name"))
            key = uuid.uuid4().hex
            data["players"][key] = {"name": name, "thresholds": copy.deepcopy(item["thresholds"]),
                "progress": blank_progress(), "needs_center": True, "calibration": None}
            data["active"] = key
            data["generation"] += 1
        elif action == "select":
            key = request.get("id")
            if not isinstance(key, str) or key not in data["players"]:
                raise ValueError("Choose an existing player.")
            if key == data["active"] and not (item["needs_center"] and item["calibration"] is not None):
                return self.snapshot()
            data["active"] = key
            data["players"][key]["needs_center"] = True
            data["calibration_restore"] = copy.deepcopy(data["players"][key]["calibration"])
            data["generation"] += 1
        elif action == "reuse_calibration":
            if request.get("confirmed") is not True or item["calibration"] is None:
                raise ValueError("Confirm unchanged camera and playing positions before reusing a saved center.")
            item["needs_center"] = True
            data["calibration_restore"] = copy.deepcopy(item["calibration"])
            data["generation"] += 1
        elif action == "rename":
            item["name"] = player_name(request.get("name"))
        elif action == "delete":
            if len(data["players"]) == 1:
                raise ValueError("Keep at least one player.")
            del data["players"][data["active"]]
            data["active"] = next(iter(data["players"]))
            data["players"][data["active"]]["needs_center"] = True
            data["calibration_restore"] = copy.deepcopy(data["players"][data["active"]]["calibration"])
            data["generation"] += 1
        elif action == "restore":
            backup = request.get("backup")
            if not isinstance(backup, dict) or type(backup.get("version")) is not int:
                raise ValueError("Choose a PowerGlove hand-setup backup.")
            complete = backup.get("format") == "powerglove-hand-setup" and backup["version"] == 2
            required = {"format", "version", "name", "thresholds", "calibration"}
            optional = {"effective_thresholds", "source"}
            if not complete or not required <= set(backup) or set(backup) - required - optional:
                raise ValueError("Choose a version-2 hand-setup backup. Version-1 and device/pairing files are not supported.")
            name = player_name(backup["name"])
            reference = calibration_value(backup["calibration"]) if backup["calibration"] is not None else None
            effective = backup.get("effective_thresholds")
            if effective is not None:
                effective = self.validate(effective)
                if set(effective) != self.channels:
                    raise ValueError("Effective thresholds must include every hand channel.")
            source = backup.get("source")
            if source is not None:
                if (not isinstance(source, dict) or set(source) != {"version", "commit"}
                        or any(not isinstance(v, str) or len(v) > 80 or not v.isprintable() for v in source.values())):
                    raise ValueError("Invalid backup software identity.")
            use_effective = request.get("use_effective_thresholds", False)
            if type(use_effective) is not bool or (use_effective and effective is None):
                raise ValueError("This backup has no complete effective thresholds.")
            reuse = request.get("reuse_calibration", False)
            if type(reuse) is not bool or (reuse and reference is None):
                raise ValueError("This backup has no usable calibration to reuse.")
            overrides = self.validate(backup["thresholds"])
            item["thresholds"] = effective if use_effective else overrides
            item["name"] = name
            item["calibration"] = reference
            item["needs_center"] = True
            if reuse:
                data["calibration_restore"] = reference
            data["generation"] += 1
        else:
            raise ValueError("Unknown player operation.")
        if data != self.data or self.error:
            self.commit(data, recover=action == "restore")
        return self.snapshot()
