#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/profile-relay.py
# Purpose: Forward bounded UDP profile exchanges from the LAN to the App Lab worker.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added persistent App Lab UDP profile ingress without host networking.
# Full history: docs/CHANGELOG.md and Git history.

"""Relay signed profile packets unchanged; only the vision worker authenticates them."""

import selectors
import socket
import threading
import time

MAX_PACKET_BYTES = 4096
MAX_PENDING = 64


def relay(listener, upstream, stopped, timeout=1.0, max_pending=MAX_PENDING):
    """Forward bounded exchanges with separate reply sockets and expiring state.

    The caller owns the listener. The relay holds no token, parses no command,
    and never acknowledges a request itself. Connected upstream sockets accept
    replies only from the worker and keep simultaneous clients isolated.
    """
    pending = {}
    selector = selectors.DefaultSelector()
    selector.register(listener, selectors.EVENT_READ)

    def discard(connection):
        """Release a completed, failed, or expired exchange."""
        selector.unregister(connection)
        pending.pop(connection, None)
        connection.close()

    try:
        while not stopped.is_set():
            for key, _events in selector.select(0.05):
                connection = key.fileobj
                if connection is listener:
                    payload, peer = listener.recvfrom(MAX_PACKET_BYTES + 1)
                    if not payload or len(payload) > MAX_PACKET_BYTES or len(pending) >= max_pending:
                        continue
                    connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                        # Resolve the Compose service for each request, including after recreation.
                        connection.connect(upstream)
                        connection.setblocking(False)
                        connection.send(payload)
                        selector.register(connection, selectors.EVENT_READ)
                        pending[connection] = (peer, time.monotonic() + timeout)
                    except OSError:
                        connection.close()
                else:
                    peer, _deadline = pending[connection]
                    try:
                        response = connection.recv(MAX_PACKET_BYTES + 1)
                        if response and len(response) <= MAX_PACKET_BYTES:
                            listener.sendto(response, peer)
                    except OSError:
                        pass
                    finally:
                        discard(connection)
            now = time.monotonic()
            for connection, (_peer, deadline) in list(pending.items()):
                if now >= deadline:
                    discard(connection)
    finally:
        for connection in list(pending):
            discard(connection)
        selector.close()


def main():
    """Serve the fixed profile-control port in the unprivileged App Lab brick."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
        listener.bind(("0.0.0.0", 55356))
        relay(listener, ("main", 55356), threading.Event())


if __name__ == "__main__":
    main()
