#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/avahi-resolver-service.py
# Purpose: Expose only Avahi IPv4 .local lookups over an app-private Unix socket.
# Author: Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Add app-owned resolver to survive App Lab Compose regeneration.
# Full history: docs/CHANGELOG.md and Git history.

"""A bounded, local-only Avahi lookup bridge; never accepts arbitrary commands."""
import os
import re
import socket
import socketserver
import stat
from pathlib import Path

SOCKET = Path('/app/data/.avahi-resolver.sock')


def lookup(request):
    """Validate a single IPv4 .local query before forwarding it to host Avahi."""
    if not re.fullmatch(rb'RESOLVE-HOSTNAME-IPV4 [A-Za-z0-9][A-Za-z0-9.-]{0,246}\.local\n', request, re.I):
        return b'-1 Invalid local query\n'
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as upstream:
        upstream.settimeout(0.4)
        upstream.connect('/run/avahi-daemon/socket')
        upstream.sendall(request)
        response = b''
        while b'\n' not in response and len(response) < 1024:
            chunk = upstream.recv(1024 - len(response))
            if not chunk:
                break
            response += chunk
        return response if response.endswith(b'\n') else b'-1 Invalid response\n'


class Handler(socketserver.StreamRequestHandler):
    """Serve one size-limited query, failing closed if Avahi is not ready."""
    timeout = 0.5

    def handle(self):
        """Return a protocol error for unavailable Avahi without stopping the service."""
        try:
            response = lookup(self.rfile.readline(300))
        except OSError:
            response = b'-1 Avahi unavailable\n'
        try:
            self.wfile.write(response)
        except OSError:
            pass


def main():
    """Replace a stale socket and listen without publishing a network port."""
    SOCKET.parent.mkdir(parents=True, exist_ok=True)
    if SOCKET.exists() or SOCKET.is_symlink():
        if not stat.S_ISSOCK(SOCKET.lstat().st_mode):
            raise RuntimeError('Refusing to replace a non-socket resolver path')
        SOCKET.unlink()
    os.umask(0o117)
    with socketserver.UnixStreamServer(str(SOCKET), Handler) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
