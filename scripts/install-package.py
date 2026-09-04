#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/install-package.py
# Purpose: Validate and stage a release, preserving local settings before host setup.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added versioned two-machine installation.
# Full history: docs/CHANGELOG.md and Git history.

"""Install a downloaded, checksum-verified package on its intended Linux host."""
import argparse
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

APP = Path("/home/arduino/ArduinoApps/powerglove-vision")


def load_setup(source):
    """Load the shared host installer from validated release contents."""
    spec = importlib.util.spec_from_file_location("setup_machine", source / "scripts/setup-machine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unpack(archive, destination, machine, version):
    """Reject unsafe paths, special files, duplicate names and wrong release identities."""
    with zipfile.ZipFile(archive) as package:
        seen = set()
        total = 0
        for item in package.infolist():
            path = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (not path.parts or path.parts[0] != "PowerGlove-Vision" or path.is_absolute()
                    or ".." in path.parts or "\\" in item.filename or item.filename in seen
                    or str(path) != item.filename.rstrip("/")
                    or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))):
                raise ValueError("Unsafe or duplicate package member: " + item.filename)
            if set(path.parts[1:]) & {"data", ".cache", ".git", ".venv", "__pycache__"} or path.name == "cheatsheet.md" or any(part.startswith(".powerglove-install") for part in path.parts):
                raise ValueError("Package contains private or generated files")
            total += item.file_size
            if total > 2 * 1024 ** 3:
                raise ValueError("Package expands beyond 2 GiB")
            seen.add(item.filename)
        meta = json.loads(package.read("PowerGlove-Vision/install-release.json"))
        if meta != {"format": 1, "machine": machine, "version": version}:
            raise ValueError("Package version or target does not match the requested release")
        required = ["scripts/setup-machine.py", "scripts/installation-manifest.py", "src/powerglove_vision/receiver.py", "config/games.json"]
        required += (["app.yaml", "sketch/sketch.yaml", "sketch/sketch.ino", "scripts/uno-q-early-start.py",
                      "uno-q/powerglove-early-start.service", "uno-q/powerglove-system-shutdown.path"]
                     if machine == "uno-q" else [
                         "retropie/powerglove-receiver.service",
                         "scripts/install-nestopia-powerglove.sh",
                         "native/nestopia-powerglove/nestopia-powerglove.patch",
                         "native/nestopia-powerglove/README.md",
                     ])
        for relative in required:
            if "PowerGlove-Vision/" + relative not in seen:
                raise ValueError("Incomplete package: " + relative)
        package.extractall(str(destination))
        for item in package.infolist():
            if not item.is_dir():
                (destination / item.filename).chmod(0o755 if item.external_attr >> 16 & 0o111 else 0o644)
    return destination / "PowerGlove-Vision"


def confirm(message):
    """Require an interactive answer for an interruption or optional configuration change."""
    if not sys.stdin.isatty():
        return False
    return input(message + " [y/N] ").strip().lower() in ("y", "yes")


def preflight(machine):
    """Check target identity and supported prerequisites before any host changes."""
    if sys.platform != "linux" or os.geteuid() != 0 or sys.version_info < (3, 7):
        raise ValueError("Installation requires Linux, Python 3.7+, and sudo")
    for command in ("apt-get", "systemctl"):
        if not shutil.which(command):
            raise ValueError("Missing system command: " + command)
    staging = pwd.getpwnam("arduino").pw_dir if machine == "uno-q" else "/var/tmp"
    if shutil.disk_usage(staging).free < 3 * 1024 ** 3:
        raise ValueError("At least 3 GiB free space is required on " + str(staging))
    if shutil.disk_usage("/var/backups").free < 512 * 1024 ** 2:
        raise ValueError("At least 512 MiB free space is required for system packages and backups")
    if machine == "uno-q":
        compatible = Path("/proc/device-tree/compatible").read_bytes()
        if b"arduino,imola" not in compatible:
            raise ValueError("This installer supports the Arduino UNO Q only")
        pwd.getpwnam("arduino")
        if not shutil.which("arduino-app-cli") or not Path("/opt/openocd/bin/openocd").is_file():
            raise ValueError("Complete board provisioning with Arduino App Lab first")
        result = subprocess.check_output(["runuser", "-u", "arduino", "--", "arduino-app-cli", "version"], timeout=20).decode()
        versions = re.findall(r"(?:CLI version|daemon version:)\s+([0-9.]+)", result, re.IGNORECASE)
        if versions != ["0.13.0", "0.13.0"]:
            raise ValueError("This release is validated with App Lab CLI 0.13.0; consult its compatibility guide")
        if (APP / "data/shutdown-request").exists():
            raise ValueError("Pending shutdown request; resolve it before installation")
        try:
            with urllib.request.urlopen("http://127.0.0.1:8088/status", timeout=3) as response:
                status = json.load(response)
        except OSError:
            status = None
        if APP.exists() and status is None:
            if not confirm("Cannot determine application activity. Continue with an app restart?"):
                raise ValueError("No changes made; could not confirm safe restart")
        elif status and (status.get("controller_enabled") or status.get("practice_mode") or
                         status.get("tuning", {}).get("active") or status.get("profile", "off") != "off"):
            if not confirm("PowerGlove Vision is active. Interrupt this session and install?"):
                raise ValueError("No changes made; active session preserved")
    else:
        if not Path("/opt/retropie/configs/all").is_dir():
            raise ValueError("Install and configure RetroPie first")
        running = subprocess.run(["pgrep", "-x", "retroarch"], stdout=subprocess.DEVNULL)
        if running.returncode != 1:
            if not confirm("RetroArch may be running. Close the game, then confirm to continue"):
                raise ValueError("No changes made; close RetroArch and retry")
            if subprocess.run(["pgrep", "-x", "retroarch"], stdout=subprocess.DEVNULL).returncode != 1:
                raise ValueError("RetroArch is still running; no changes made")


def stage_unoq(source, setup):
    """Back up managed app files and update them without touching data or local documents."""
    user = pwd.getpwnam("arduino")
    for directory in (APP, APP.parent):
        if directory.is_symlink():
            raise ValueError("Refusing symbolic application directory")
    files = [path for path in source.rglob("*") if path.is_file()]
    for path in files:
        target = APP / path.relative_to(source)
        if any(parent.is_symlink() for parent in [target] + list(target.parents)):
            raise ValueError("Refusing symbolic installation path: " + str(target))
    cache = APP / ".cache/sketch"
    if cache.is_dir() and not (setup.BACKUPS / "previous-sketch-cache").exists():
        shutil.copytree(str(cache), str(setup.BACKUPS / "previous-sketch-cache"), symlinks=True)
    # Stop through App Lab so the sketch and containers share one lifecycle.
    if (APP / ".cache/app-compose.yaml").exists():
        setup.run("runuser", "-u", "arduino", "--", "arduino-app-cli", "app", "stop", APP)
    APP.mkdir(parents=True, exist_ok=True)
    setup.installation_manifest()["apply"](source, APP, setup.BACKUPS / "application-payload")
    for path in files:
        target = APP / path.relative_to(source)
        os.chown(str(target), user.pw_uid, user.pw_gid)
        for parent in target.parents:
            if parent == APP.parent:
                break
            os.chown(str(parent), user.pw_uid, user.pw_gid)
    for name in (".powerglove-install.json", ".powerglove-install.lock"):
        os.chown(str(APP / name), user.pw_uid, user.pw_gid)
    setup.SOURCE = APP
    # Starting an app directory is supported by App Lab; no UI import is required.
    setup.run("runuser", "-u", "arduino", "--", "arduino-app-cli", "app", "start", APP)


def main(argv=None):
    """Install validated release files, complete host setup, then report next steps."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("machine", choices=("uno-q", "retropie"))
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--peer")
    args = parser.parse_args(argv)
    setup = None
    try:
        preflight(args.machine)
        with tempfile.TemporaryDirectory(prefix="powerglove-install-",
                                         dir=pwd.getpwnam("arduino").pw_dir if args.machine == "uno-q" else "/var/tmp") as temporary:
            source = unpack(args.archive, Path(temporary), args.machine, args.version)
            setup = load_setup(source)
            if args.peer:
                setup.valid_host(args.peer)
            if args.machine == "retropie" and not Path("/etc/powerglove/launcher.json").exists() and not args.peer:
                if not sys.stdin.isatty():
                    raise ValueError("First RetroPie installation requires --peer UNO-Q-NAME.local")
                args.peer = setup.valid_host(input("UNO Q hostname or IP address: ").strip())
            setup.BACKUPS.mkdir(parents=True, mode=0o700)
            setup.BACKUPS.chmod(0o700)
            print("Backups: " + str(setup.BACKUPS), flush=True)
            (setup.BACKUPS / "RESTORE.txt").write_text(
                "Stop PowerGlove before recovery. Saved paths below mirror absolute host paths.\n"
                "Copy only the files you need back to those paths, retaining ownership/permissions.\n"
                "Private settings were preserved in place. To recover code/firmware, rerun the previous release installer.\n"
                "Then reload systemd and rerun the installer --check. Do not copy the entire backup over /.\n")
            if args.machine == "uno-q":
                stage_unoq(source, setup)
                setup.install_unoq(args.peer)
                setup.wait_unoq()
            else:
                setup.install_retropie(args.peer)
                setup.configure_games(confirm)
            report = setup.Report()
            (setup.check_unoq if args.machine == "uno-q" else setup.check_retropie)(report)
            if args.machine == "uno-q":
                print("NEXT  Open http://" + socket.gethostname().split(".")[0] + ".local:8088/help for pairing, calibration and gameplay checks.")
            else:
                token = Path("/etc/powerglove/token")
                if not token.is_file() or len(token.read_text().strip()) < 16:
                    print("NEXT  Pair using sudo /opt/powerglove/bin/powerglove-pair.")
                print("NEXT  Confirm PowerGlove Vision is selected in RetroArch Port 1 and test gameplay.")
            return report.finish()
    except (OSError, ValueError, KeyError, argparse.ArgumentTypeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        print("FAIL  Installation stopped: " + str(error), file=sys.stderr)
        if setup:
            print("Recovery instructions and changed-file backups: " + str(setup.BACKUPS), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
