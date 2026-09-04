#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/setup-machine.py
# Purpose: Install or check UNO Q and RetroPie integration without replacing private settings.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added repeatable host installers with backups and explicit health reports.
#   2026-09-03 - Install and check mDNS dependencies and boot service on both machines.
#   2026-09-04 - Repaired persistent profile transport and asynchronous queue acknowledgements.
# Full history: docs/CHANGELOG.md and Git history.

"""Run on the target Linux host: setup-machine.py {retropie,uno-q} [--check]."""
import argparse
import datetime
import json
import os
import pwd
import grp
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
BACKUPS = Path("/var/backups/powerglove-vision") / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def run(*args):
    """Run one installation step and stop on failure without invoking a shell."""
    subprocess.run(list(map(str, args)), check=True)


def write_file(path, content, mode=0o644, preserve=False):
    """Back up changed managed files; never overwrite a symlink or preserved setting."""
    path = Path(path)
    if any(parent.is_symlink() for parent in [path] + list(path.parents)):
        raise ValueError("Refusing symlink: " + str(path))
    if path.exists() and preserve:
        return
    data = content.encode() if isinstance(content, str) else content
    if path.exists():
        if path.read_bytes() == data and path.stat().st_mode & 0o777 == mode:
            return
        backup = BACKUPS / str(path).lstrip("/")
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(path), str(backup))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".setup-tmp")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("Remove stale installer temporary file: " + str(temporary))
    with temporary.open("xb") as stream:
        stream.write(data)
    temporary.chmod(mode)
    if path.exists() and os.geteuid() == 0:
        owner = path.stat()
        os.chown(str(temporary), owner.st_uid, owner.st_gid)
    os.replace(str(temporary), str(path))


def hook_content(text, action):
    """Add an early, failure-safe shell hook once; preserve all existing commands."""
    executable = "/opt/powerglove-src/retropie/runcommand-on" + action + "-powerglove.sh"
    if any(executable in line and not line.lstrip().startswith("#") for line in text.splitlines()):
        return text
    if text.startswith("#!") and not re.match(r"^#!.*(?:/| )(?:ba|da)?sh(?:\s|$)", text.splitlines()[0]):
        raise ValueError("Existing runcommand hook is not a supported shell script")
    command = executable + (' "$1" "$2" "$3" "$4"' if action == "start" else "")
    block = "# PowerGlove Vision managed launch hook\n" + command + " || true\n"
    if text.startswith("#!"):
        first, _, rest = text.partition("\n")
        return first + "\n" + block + rest
    return "#!/bin/sh\n" + block + text


def valid_host(value):
    """Accept a simple DNS hostname or IPv4 address, not shell syntax or URLs."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}", value):
        raise argparse.ArgumentTypeError("Use a hostname or IPv4 address")
    return value


def install_retropie(peer):
    """Install the system-Python receiver and preserve cabinet-specific configuration."""
    base = Path("/opt/retropie/configs/all")
    if not base.is_dir():
        raise ValueError("RetroPie configuration directory is missing")
    # Preflight hook compatibility before installing packages or changing files.
    hooks = []
    for action in ("start", "end"):
        path = base / ("runcommand-on" + action + ".sh")
        if path.is_symlink():
            raise ValueError("Refusing symlink: " + str(path))
        text = path.read_text() if path.exists() else ""
        hooks.append((path, hook_content(text, action)))
    launcher = Path("/etc/powerglove/launcher.json")
    if launcher.exists():
        current = json.loads(launcher.read_text())
        if peer and current.get("uno_q") != peer:
            print("ACTION  Existing launcher destination preserved; edit launcher.json if changing machines.")
    if not launcher.exists() and not peer:
        raise ValueError("First installation requires --peer YOUR-UNO-Q.local")
    run("apt-get", "update")
    run("apt-get", "install", "-y", "python3", "python3-evdev", "openssl", "avahi-daemon", "libnss-mdns")
    run("systemctl", "enable", "--now", "avahi-daemon")
    run("modprobe", "uinput")
    write_file("/etc/modules-load.d/powerglove.conf", "uinput\n")
    destination = Path("/opt/powerglove-src")
    for directory in ("src", "retropie", "config", "scripts"):
        for source in (SOURCE / directory).rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                target = destination / source.relative_to(SOURCE)
                if source.resolve() != target.resolve():
                    write_file(target, source.read_bytes(), source.stat().st_mode & 0o777)
    if (SOURCE / "install-release.json").is_file():
        write_file(destination / "install-release.json", (SOURCE / "install-release.json").read_bytes())
    for source in (SOURCE / "retropie/bin").iterdir():
        write_file(Path("/opt/powerglove/bin") / source.name, source.read_bytes(), 0o755)
    for action in ("start", "end"):
        (destination / ("retropie/runcommand-on" + action + "-powerglove.sh")).chmod(0o755)
    write_file("/etc/powerglove/games.json", (SOURCE / "config/games.json").read_bytes(), preserve=True)
    config = json.loads((SOURCE / "config/launcher.example.json").read_text())
    config["uno_q"] = peer
    write_file(launcher, json.dumps(config, indent=2) + "\n", preserve=True)
    # Never truncate an existing token. Empty means pairing is still required.
    token = Path("/etc/powerglove/token")
    write_file(token, b"", 0o640, preserve=True)
    token.chmod(0o640)
    os.chown(str(token), 0, grp.getgrnam("input").gr_gid)
    for unit in ("powerglove-receiver.service", "powerglove-receiver.timer", "powerglove-games.service"):
        write_file(Path("/etc/systemd/system") / unit, (SOURCE / "retropie" / unit).read_bytes())
    profile = "PowerGlove Vision.cfg"
    write_file(base / "retroarch/autoconfig" / profile, (SOURCE / "retropie/retroarch" / profile).read_bytes(), preserve=True)
    for path, content in hooks:
        write_file(path, content, 0o755)
        path.chmod(path.stat().st_mode | 0o111)
    registry_directory = Path(json.loads(launcher.read_text()).get("registry", "/etc/powerglove/games.json")).resolve().parent
    # systemd quoted strings preserve spaces and avoid percent specifier expansion.
    writable = str(registry_directory).replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
    write_file("/etc/systemd/system/powerglove-games.service.d/registry.conf",
               '[Service]\nReadWritePaths=\nReadWritePaths="' + writable + '"\n')
    run("systemctl", "daemon-reload")
    run("systemctl", "enable", "--now", "powerglove-games.service")
    run("systemctl", "restart", "powerglove-games.service")
    run("systemctl", "disable", "powerglove-receiver.service")
    if len(token.read_text().strip()) >= 16:
        run("systemctl", "restart", "powerglove-receiver.service")
    run("systemctl", "enable", "--now", "powerglove-receiver.timer")


def install_unoq(peer):
    """Complete the CLI-started app with networking, shutdown and early startup."""
    app = SOURCE
    if str(app) != "/home/arduino/ArduinoApps/powerglove-vision":
        raise ValueError("UNO Q setup currently requires App Lab path /home/arduino/ArduinoApps/powerglove-vision")
    compose = app / ".cache/app-compose.yaml"
    if not compose.exists():
        raise ValueError("Start the app with install-uno-q.sh before completing host setup")
    if (app / "data/shutdown-request").exists():
        raise ValueError("A pending shutdown request exists; remove it deliberately before setup")
    run("apt-get", "update")
    run("apt-get", "install", "-y", "avahi-daemon", "libnss-mdns")
    run("systemctl", "enable", "--now", "avahi-daemon")
    for suffix, directory in (("path", "/etc/systemd/system"), ("service", "/etc/systemd/system"), ("conf", "/etc/tmpfiles.d")):
        name = "powerglove-system-shutdown." + suffix
        write_file(Path(directory) / name, (app / "uno-q" / name).read_bytes())
    run("systemctl", "daemon-reload")
    run("systemd-tmpfiles", "--create", "/etc/tmpfiles.d/powerglove-system-shutdown.conf")
    run("systemctl", "enable", "--now", "powerglove-system-shutdown.path")
    # Use the same idempotent Compose transformation as Wi-Fi deployment.
    import runpy
    configure = runpy.run_path(str(app / "scripts/configure-uno-q-mdns.py"))["configure"]
    original = compose.read_bytes()
    backup = BACKUPS / "uno-q-app-compose.yaml"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(original)
    configure(compose)
    text = compose.read_text()
    if "- 8443:8443" not in text:
        if "- 8088:8088" not in text:
            raise ValueError("Expected app port 8088 in Compose configuration")
        compose.write_text(text.replace("- 8088:8088", "- 8088:8088\n    - 8443:8443", 1))
    user = pwd.getpwnam("arduino")
    os.chown(str(compose), user.pw_uid, user.pw_gid)
    # App Lab properties belong to the non-root desktop account.
    run("runuser", "-u", "arduino", "--", "arduino-app-cli", "properties", "set", "default", app)
    run("docker", "compose", "-f", compose, "up", "-d", "--force-recreate")
    install_early_start()
    if peer:
        print("Receiver setting is preserved; choose " + peer + " on the Connection page if needed.")


def user_systemctl(*args):
    """Address the Arduino user manager consistently from a sudo installation."""
    user = pwd.getpwnam("arduino")
    prefix = ["runuser", "-u", "arduino", "--"] if os.geteuid() != user.pw_uid else []
    return prefix + ["env", "XDG_RUNTIME_DIR=/run/user/" + str(user.pw_uid),
            "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/" + str(user.pw_uid) + "/bus",
            "systemctl", "--user"] + list(args)


def install_early_start():
    """Install the guarded helper and enable it for subsequent boots without an SWD write now."""
    user = pwd.getpwnam("arduino")
    home = Path(user.pw_dir)
    for source, relative in (("scripts/uno-q-early-start.py", ".local/lib/powerglove/uno-q-early-start.py"),
                             ("uno-q/powerglove-early-start.service", ".config/systemd/user/powerglove-early-start.service")):
        target = home / relative
        if any(parent.is_symlink() for parent in [target] + list(target.parents)):
            raise ValueError("Refusing symbolic helper path: " + str(target))
        write_file(target, (SOURCE / source).read_bytes())
        os.chown(str(target), user.pw_uid, user.pw_gid)
        for parent in target.parents:
            if parent == home:
                break
            os.chown(str(parent), user.pw_uid, user.pw_gid)
    run("loginctl", "enable-linger", "arduino")
    run("systemctl", "start", "user@%s.service" % user.pw_uid)
    run(*user_systemctl("daemon-reload"))
    trial = home / ".config/systemd/user/powerglove-early-start-trial.service"
    if trial.exists():
        run(*user_systemctl("disable", "powerglove-early-start-trial.service"))
    run(*user_systemctl("enable", "powerglove-early-start.service"))
    print("PASS  Early-start helper installed for the next boot; existing sketch animation preserved.")


def wait_unoq():
    """Allow a cold application startup to finish before reporting health."""
    for _ in range(90):
        try:
            urllib.request.urlopen("http://127.0.0.1:8088/status", timeout=2).close()
            return
        except OSError:
            time.sleep(2)


def registered_roms():
    """Find registered NES games in standard RetroPie account ROM directories."""
    config = json.loads(Path("/etc/powerglove/launcher.json").read_text())
    registry = json.loads(Path(config.get("registry", "/etc/powerglove/games.json")).read_text())["games"]
    results = []
    for home in Path("/home").iterdir():
        directory = home / "RetroPie/roms/nes"
        if directory.is_dir():
            for rom in directory.rglob("*"):
                if rom.is_file() and rom.name in registry:
                    results.append((rom, registry[rom.name]))
    return results


def configure_games(confirm):
    """Offer supported emulator installation and prepare registered Bad Street Brawler games."""
    prefix = Path("/opt/retropie")
    core = prefix / "libretrocores/lr-fceumm/fceumm_libretro.so"
    retroarch = prefix / "emulators/retroarch/bin/retroarch"
    if not core.is_file() or not retroarch.is_file():
        user = os.environ.get("SUDO_USER", "")
        home = Path(pwd.getpwnam(user).pw_dir) if user else Path("/root")
        script = home / "RetroPie-Setup/retropie_packages.sh"
        if script.is_file() and confirm("Install missing RetroArch/FCEUmm using RetroPie Setup? This may take several minutes"):
            for package, artifact in (("retroarch", retroarch), ("lr-fceumm", core)):
                if not artifact.is_file():
                    run("bash", script, package, "install_bin")
                    run("bash", script, package, "configure")
        else:
            print("ACTION  Install lr-fceumm using RetroPie Setup, then rerun this installer.")
    import runpy
    zap = runpy.run_path(str(SOURCE / "scripts/configure-bsb-zap.py"))
    for rom, profile in registered_roms():
        if profile != "bad_street_brawler":
            continue
        try:
            configs = prefix / "configs"
            games_path = configs / "all/emulators.cfg"
            system = zap["settings"](configs / "nes/emulators.cfg")
            games = zap["settings"](games_path)
            import hashlib
            key = "a" + hashlib.md5(("nes" + str(rom) + "\n").encode()).hexdigest()
            modern = re.sub(r"[^a-zA-Z0-9_-]", "", "nes_" + rom.stem)
            selected = games.get(key) or games.get(modern) or system.get("default")
            if selected != "lr-fceumm" and core.is_file() and "lr-fceumm" in system:
                if confirm("Use FCEUmm for " + rom.name + " so Glove Zap is supported?"):
                    text = games_path.read_text() if games_path.exists() else ""
                    text = "\n".join(line for line in text.splitlines() if not re.match(r"^\s*" + re.escape(key) + r"\s*=", line))
                    write_file(games_path, text + "\n" + key + ' = "lr-fceumm"\n')
            result = zap["main"](["--rom", str(rom), "--apply"])
            if result:
                print("ACTION  Finish Glove Zap setup for " + rom.name + "; rerun after resolving the message above.")
        except (ValueError, OSError) as error:
            print("ACTION  " + str(error))


class Report:
    """Collect explicit check results without printing private configuration values."""
    def __init__(self):
        self.failures = 0
        self.pending = 0

    def check(self, label, condition, pending=False):
        """Print one result and retain the final exit-code category."""
        if condition:
            print("PASS  " + label)
        elif pending:
            self.pending += 1
            print("ACTION  " + label)
        else:
            self.failures += 1
            print("FAIL  " + label)

    def command(self, label, args):
        """Check a command without displaying logs that may contain private data."""
        try:
            result = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            self.check(label, result.returncode == 0)
        except (OSError, subprocess.TimeoutExpired):
            self.check(label, False)

    def release(self):
        """Display the installed package tag without reading private runtime settings."""
        path = SOURCE / "install-release.json"
        if path.is_file():
            try:
                print("Installed release: " + json.loads(path.read_text())["version"])
            except (ValueError, KeyError):
                self.check("Installed release identity is readable", False)

    def finish(self):
        """Distinguish technical failures from required human pairing/play verification."""
        self.release()
        print("Checks: %d failed, %d require action." % (self.failures, self.pending))
        return 1 if self.failures else 2 if self.pending else 0


def check_retropie(report):
    """Inspect boot configuration, receiver prerequisites and launch integration."""
    report.command("Avahi enabled at boot", ["systemctl", "is-enabled", "--quiet", "avahi-daemon"])
    report.command("Avahi running", ["systemctl", "is-active", "--quiet", "avahi-daemon"])
    report.command("mDNS hostname dependency installed", ["dpkg", "--verify", "libnss-mdns"])
    report.check("uinput device exists", Path("/dev/uinput").exists())
    report.command("Receiver Python dependency", ["python3", "-c", "import evdev"])
    report.command("Delayed boot timer enabled", ["systemctl", "is-enabled", "--quiet", "powerglove-receiver.timer"])
    report.command("Delayed boot timer active", ["systemctl", "is-active", "--quiet", "powerglove-receiver.timer"])
    token = Path("/etc/powerglove/token")
    paired = token.exists() and 16 <= len(token.read_text().strip()) <= 256
    report.check("Local pairing token configured (pair on the Connection page if missing)", paired, pending=True)
    if paired:
        report.command("Receiver service running", ["systemctl", "is-active", "--quiet", "powerglove-receiver.service"])
        report.command("Games service running", ["systemctl", "is-active", "--quiet", "powerglove-games.service"])
    for action in ("start", "end"):
        path = Path("/opt/retropie/configs/all/runcommand-on" + action + ".sh")
        text = path.read_text() if path.exists() else ""
        report.check(action + " launch hook installed", "runcommand-on" + action + "-powerglove.sh" in text)
    launcher = Path("/etc/powerglove/launcher.json")
    try:
        config = json.loads(launcher.read_text())
        socket.getaddrinfo(config["uno_q"], 55356)
        report.check("Configured UNO Q hostname resolves", True)
    except (OSError, ValueError, KeyError):
        report.check("Configured UNO Q hostname resolves", False)
    report.check("RetroArch installed", Path("/opt/retropie/emulators/retroarch/bin/retroarch").is_file(), pending=True)
    report.check("FCEUmm installed for supported NES games", Path("/opt/retropie/libretrocores/lr-fceumm/fceumm_libretro.so").is_file(), pending=True)
    try:
        roms = registered_roms()
        report.check("Registered ROMs found (supply your own games)", bool(roms), pending=True)
        import runpy
        zap = runpy.run_path(str(SOURCE / "scripts/configure-bsb-zap.py"))
        for rom, profile in roms:
            if profile == "bad_street_brawler":
                report.check("Glove Zap configured: " + rom.name,
                             zap["main"](["--rom", str(rom), "--check"]) == 0, pending=True)
    except (OSError, ValueError, KeyError):
        report.check("Game registry readable; review custom ROM paths if needed", False, pending=True)
    report.check("Confirm controls in a game; a local token alone does not prove pairing", False, pending=True)


def check_unoq(report):
    """Check boot persistence, the app-owned resolver and public application health."""
    report.command("Avahi enabled at boot", ["systemctl", "is-enabled", "--quiet", "avahi-daemon"])
    report.command("mDNS hostname dependency installed", ["dpkg", "--verify", "libnss-mdns"])
    report.command("Avahi running", ["systemctl", "is-active", "--quiet", "avahi-daemon"])
    report.command("Shutdown helper enabled", ["systemctl", "is-enabled", "--quiet", "powerglove-system-shutdown.path"])
    report.command("Shutdown helper running", ["systemctl", "is-active", "--quiet", "powerglove-system-shutdown.path"])
    report.check("Shutdown readiness marker", (SOURCE / "data/.shutdown-enabled").exists())
    try:
        args = ["arduino-app-cli", "properties", "get", "default", "--format", "json"]
        if os.geteuid() == 0:
            args = ["runuser", "-u", "arduino", "--"] + args
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=True)
        report.check("PowerGlove Vision is the startup app", json.loads(result.stdout)["app"]["FullPath"] == str(SOURCE))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        report.check("PowerGlove Vision is the startup app", False)

    report.command("Arduino user starts at boot", ["test", "-f", "/var/lib/systemd/linger/arduino"])
    report.command("Early-start helper enabled", user_systemctl("is-enabled", "--quiet", "powerglove-early-start.service"))
    report.check("Early-start helper installed", Path("/home/arduino/.local/lib/powerglove/uno-q-early-start.py").is_file())
    status = {}
    try:
        with urllib.request.urlopen("http://127.0.0.1:8088/status", timeout=3) as response:
            status = json.load(response)
        report.check("Application HTTP status", bool(status.get("version")))
    except (OSError, ValueError):
        report.check("Application HTTP status", False)
    report.check("App-owned Avahi resolver configured", "local:avahi_resolver" in (SOURCE / "app.yaml").read_text() and (SOURCE / "bricks/local/avahi_resolver/brick_compose.yaml").is_file())
    report.command("Profile UDP ingress published", ["docker", "port", "powerglove-vision-profile-relay-1", "55356/udp"])
    code = ("import json; from pathlib import Path; from powerglove_vision.resolver import resolve_ipv4; "
            "d=json.loads(Path('/app/data/device.json').read_text()); resolve_ipv4(d['receiver'])")
    if status.get("connection_configured"):
        report.command("Configured receiver resolves inside app", ["docker", "exec", "-e", "PYTHONPATH=/app/src", "powerglove-vision-main-1", "python3", "-c", code])
    else:
        report.check("Configure your RetroPie destination in Connection", False, pending=True)
    for route in ("help", "help/installation", "help-pdf/installation.pdf"):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8088/" + route, timeout=10) as response:
                report.check("Available: " + route, response.status == 200)
        except OSError:
            report.check("Available: " + route, False)
    report.check("USB camera device present", Path("/dev/v4l/by-id").is_dir() and
                 bool(list(Path("/dev/v4l/by-id").glob("*"))), pending=True)
    report.check("Complete pairing and verify gameplay; credentials remain user-controlled", False, pending=True)


def main():
    """Run installation or read-only checks with an explicit result summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("machine", choices=("retropie", "uno-q"))
    parser.add_argument("--peer", type=valid_host, help="Other machine hostname; required for a new RetroPie installation")
    parser.add_argument("--check", action="store_true", help="Read-only checks; install nothing")
    args = parser.parse_args()
    if sys.platform != "linux" or (not args.check and os.geteuid() != 0):
        parser.error("Run installation on the target Linux machine with sudo")
    try:
        if not args.check:
            required = ("src/powerglove_vision/receiver.py", "config/games.json",
                        "retropie/powerglove-receiver.timer") if args.machine == "retropie" else (
                        "scripts/configure-uno-q-mdns.py", "uno-q/powerglove-system-shutdown.path")
            for relative in required:
                if not (SOURCE / relative).is_file():
                    raise ValueError("Incomplete project download: missing " + relative)
            (install_retropie if args.machine == "retropie" else install_unoq)(args.peer)
            print("Managed-file backups, when changed: " + str(BACKUPS))
            if args.machine == "uno-q":
                wait_unoq()
        report = Report()
        (check_retropie if args.machine == "retropie" else check_unoq)(report)
        return report.finish()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print("FAIL  Setup stopped: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
