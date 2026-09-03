#!/usr/bin/env python3
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
"""Password-authenticated RetroPie pairing using a temporary Python SSH client."""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

import paramiko


REMOTE_PROGRAM = (
    "import grp,os,subprocess,sys;"
    "p='/etc/powerglove/token';t=sys.stdin.readline().strip();"
    "assert 16<=len(t)<=256 and not any(c.isspace() for c in t);"
    "os.makedirs('/etc/powerglove',exist_ok=True);q=p+'.pairing-tmp';"
    "open(q,'w').write(t+'\\n');os.chmod(q,0o640);"
    "os.chown(q,0,grp.getgrnam('input').gr_gid);os.replace(q,p);"
    "subprocess.check_call(['systemctl','restart','powerglove-receiver.service'])"
)


def main() -> int:
    request = json.load(sys.stdin)
    known_hosts = Path(str(request["known_hosts"]))
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    known_hosts.touch(mode=0o600, exist_ok=True)
    os.chmod(known_hosts, 0o600)

    client = paramiko.SSHClient()
    client.load_host_keys(str(known_hosts))
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        timeout = float(request.get("timeout", 30.0))
        client.connect(
            hostname=str(request["host"]),
            username=str(request["username"]),
            password=str(request["password"]),
            timeout=timeout,
            auth_timeout=timeout,
            banner_timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        command = "sudo -k -S -p '' /usr/bin/python3 -c " + shlex.quote(REMOTE_PROGRAM)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        stdin.write(str(request["password"]) + "\n" + str(request["token"]) + "\n")
        stdin.flush()
        stdin.channel.shutdown_write()
        status = stdout.channel.recv_exit_status()
        error = stderr.read().decode("utf-8", "replace").strip()
        if status:
            raise RuntimeError(error.splitlines()[-1] if error else "RetroPie pairing command failed")
        client.save_host_keys(str(known_hosts))
        os.chmod(known_hosts, 0o600)
        return 0
    finally:
        client.close()
        request["password"] = ""
        request["token"] = ""


if __name__ == "__main__":
    raise SystemExit(main())
