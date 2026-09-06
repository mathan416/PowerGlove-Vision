# Project: PowerGlove Vision
# File: src/powerglove_vision/players.py
# Purpose: Persist bounded player presets, Academy progress, and portable hand settings.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Add atomic player presets and credential-free hand backups.
# Full history: docs/CHANGELOG.md and Git history.

"""Owned under the tuning lock; one atomic file is authoritative for all players."""

import copy
import json
import uuid

COURSE = 1
LESSONS = 16
MAX_PLAYERS = 12


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
    def __init__(self, path, validate):
        self.path, self.validate = path, validate
        self.error = None
        self.legacy_backup = None
        self.data = {"version": 2, "active": "default", "generation": 0,
                     "players": {"default": {"name": "Player 1", "thresholds": {},
                         "progress": blank_progress(), "needs_center": False}}}
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
        except (OSError, ValueError, KeyError, TypeError):
            self.error = "Saved player settings could not be loaded. Restore a hand-settings backup to recover; the original file has not been changed."

    def validate_store(self, data):
        """Validate persisted records before exposing them to the app."""
        if not isinstance(data, dict) or set(data) != {"version", "active", "generation", "players"} or data["version"] != 2:
            raise ValueError("Unsupported player settings")
        players = data["players"]
        if not isinstance(players, dict) or not 1 <= len(players) <= MAX_PLAYERS or data["active"] not in players:
            raise ValueError("Invalid players")
        if type(data["generation"]) is not int or data["generation"] < 0:
            raise ValueError("Invalid player revision")
        for key, item in players.items():
            if not isinstance(key, str) or not 1 <= len(key) <= 32 or not key.isalnum():
                raise ValueError("Invalid player identifier")
            if not isinstance(item, dict) or set(item) != {"name", "thresholds", "progress", "needs_center"} or type(item["needs_center"]) is not bool:
                raise ValueError("Invalid player record")
            item["name"] = player_name(item["name"])
            item["thresholds"] = self.validate(item["thresholds"])
            item["progress"] = progress(item["progress"])
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
            backup = self.path.with_name("gesture-tuning-v1-backup.json")
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
                "needs_center": self.active["needs_center"], "error": self.error}

    def save_thresholds(self, values):
        """Save tuning directly into the active player's record."""
        data = copy.deepcopy(self.data)
        data["players"][data["active"]]["thresholds"] = self.validate(values)
        self.commit(data)

    def centered(self, generation):
        """Only acknowledge calibration started for the still-active player."""
        if generation == self.data["generation"] and self.active["needs_center"]:
            data = copy.deepcopy(self.data)
            data["players"][data["active"]]["needs_center"] = False
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
            return {"backup": {"format": "powerglove-hand-settings", "version": 1,
                    "name": self.active["name"], "thresholds": copy.deepcopy(self.active["thresholds"])}}
        data = copy.deepcopy(self.data)
        item = data["players"][data["active"]]
        if action == "progress":
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
                "progress": blank_progress(), "needs_center": True}
            data["active"] = key
            data["generation"] += 1
        elif action == "select":
            key = request.get("id")
            if not isinstance(key, str) or key not in data["players"]:
                raise ValueError("Choose an existing player.")
            if key == data["active"]:
                return self.snapshot()
            data["active"] = key
            data["players"][key]["needs_center"] = True
            data["generation"] += 1
        elif action == "rename":
            item["name"] = player_name(request.get("name"))
        elif action == "delete":
            if len(data["players"]) == 1:
                raise ValueError("Keep at least one player.")
            del data["players"][data["active"]]
            data["active"] = next(iter(data["players"]))
            data["players"][data["active"]]["needs_center"] = True
            data["generation"] += 1
        elif action == "restore":
            backup = request.get("backup")
            if (not isinstance(backup, dict) or set(backup) != {"format", "version", "name", "thresholds"}
                    or backup["format"] != "powerglove-hand-settings" or backup["version"] != 1):
                raise ValueError("Choose a PowerGlove hand-settings backup. Device and pairing files cannot be imported.")
            player_name(backup["name"])
            item["thresholds"] = self.validate(backup["thresholds"])
            item["needs_center"] = True
            data["generation"] += 1
        else:
            raise ValueError("Unknown player operation.")
        if data != self.data or self.error:
            self.commit(data, recover=action == "restore")
        return self.snapshot()
