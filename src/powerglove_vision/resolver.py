# Project: PowerGlove Vision
# File: src/powerglove_vision/resolver.py
# Purpose: Resolve .local names through the host Avahi socket inside App Lab containers.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added persistent host mDNS resolution without pinned IP addresses.
# Full history: docs/CHANGELOG.md and Git history.

"""Use host Avahi for local IPv4 names; retain ordinary DNS elsewhere."""
import ipaddress
import socket
import time
from pathlib import Path

AVAHI_SOCKET = "/run/avahi-daemon/socket"
_cache = {}


def resolve_ipv4(host):
    """Resolve an IPv4 destination, refreshing local addresses every five seconds."""
    name = host.rstrip(".")
    if not name.lower().endswith(".local") or not Path(AVAHI_SOCKET).exists():
        return socket.gethostbyname(host)
    if not name.isascii() or any(c.isspace() for c in name) or len(name) > 253:
        raise socket.gaierror("Invalid local hostname")
    cached = _cache.get(name)
    now = time.monotonic()
    if cached and cached[0] > now:
        return cached[1]
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.5)
        connection.connect(AVAHI_SOCKET)
        connection.sendall(("RESOLVE-HOSTNAME-IPV4 " + name + "\n").encode("ascii"))
        response = b""
        while b"\n" not in response and len(response) < 1024:
            chunk = connection.recv(1024 - len(response))
            if not chunk:
                break
            response += chunk
    fields = response.decode("ascii", "replace").split()
    if len(fields) != 5 or fields[0] != "+" or fields[3].lower().rstrip(".") != name.lower():
        raise socket.gaierror("Avahi could not resolve " + name)
    try:
        address = str(ipaddress.IPv4Address(fields[4]))
    except ValueError:
        raise socket.gaierror("Avahi returned an invalid IPv4 address") from None
    if len(_cache) >= 256:
        _cache.clear()
    _cache[name] = (now + 5.0, address)
    return address
