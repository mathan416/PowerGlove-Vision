# Project: PowerGlove Vision
# File: src/powerglove_vision/pairing.py
# Purpose: Provision the shared controller token through bounded TLS pairing or authenticated SSH.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
# Full history: docs/CHANGELOG.md and Git history.

"""Short-lived HTTPS pairing for PowerGlove Vision and RetroPie."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.client
import json
import os
import secrets
import socket
import ssl
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable, Optional


PAIRING_PORT = 55357
CODE_PART_LENGTH = 10


class QuietHTTPServer(HTTPServer):
    """Suppress expected request errors during short-lived pairing sessions."""
    def handle_error(self, _request: object, _client_address: object) -> None:
        """Ignore malformed or disconnected pairing clients without noisy tracebacks."""
        return


class BoundedTLSServer(QuietHTTPServer):
    """TLS server that bounds each untrusted handshake and request."""

    def __init__(
        self, server_address: tuple[str, int], handler: type[BaseHTTPRequestHandler],
        context: ssl.SSLContext, deadline: float,
    ) -> None:
        self.tls_context = context
        self.deadline = deadline
        super().__init__(server_address, handler)

    def get_request(self) -> tuple[socket.socket, tuple[str, int]]:
        """Wrap one accepted socket in TLS while enforcing the session deadline."""
        connection, address = super().get_request()
        connection.settimeout(max(0.05, min(1.0, self.deadline - time.monotonic())))
        try:
            return self.tls_context.wrap_socket(connection, server_side=True), address
        except (OSError, ssl.SSLError):
            connection.close()
            raise


def _code_part(value: bytes) -> str:
    """Encode bytes as a short human-readable Base32 verification component."""
    return base64.b32encode(value).decode("ascii").rstrip("=")[:CODE_PART_LENGTH]


def certificate_code(pem: str) -> str:
    """Derive the certificate component of a physical pairing code."""
    der = ssl.PEM_cert_to_DER_cert(pem)
    return _code_part(hashlib.sha256(der).digest())


def certificate_identity(pem: str) -> str:
    """Short hexadecimal prefix users can compare with browser certificate details."""
    der = ssl.PEM_cert_to_DER_cert(pem)
    return hashlib.sha256(der).hexdigest()[:7].upper()


def normalize_pairing_code(code: str) -> tuple[str, str]:
    """Normalize user formatting and split a complete physical pairing code."""
    normalized = "".join(character for character in code.upper() if character.isalnum())
    if len(normalized) != CODE_PART_LENGTH * 2:
        raise ValueError("pairing code must contain 20 letters or numbers")
    return normalized[:CODE_PART_LENGTH], normalized[CODE_PART_LENGTH:]


def display_pairing_code(certificate_part: str, authorization_part: str) -> str:
    """Format certificate and authorization components into readable groups."""
    combined = certificate_part + authorization_part
    return "-".join(combined[index:index + 5] for index in range(0, len(combined), 5))


def generate_certificate(directory: Path, hostname: str, days: int = 1) -> tuple[Path, Path, str]:
    """Create a temporary self-signed pairing certificate and return its verification code."""
    directory.mkdir(parents=True, exist_ok=True)
    certificate = directory / "pairing-cert.pem"
    private_key = directory / "pairing-key.pem"
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-days", str(days), "-subj", f"/CN={hostname}",
        "-addext", f"subjectAltName=DNS:{hostname}",
        "-keyout", str(private_key), "-out", str(certificate),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.chmod(private_key, 0o600)
    pem = certificate.read_text()
    return certificate, private_key, pem


def install_token(token_file: Path, token: str) -> None:
    """Atomically install a validated shared token with restricted permissions."""
    if not 16 <= len(token) <= 256 or any(character.isspace() for character in token):
        raise ValueError("invalid controller token")
    token_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = token_file.with_suffix(".pairing-tmp")
    temporary.write_text(token + "\n")
    os.chmod(temporary, 0o640)
    try:
        import grp
        os.chown(temporary, 0, grp.getgrnam("input").gr_gid)
    except (ImportError, KeyError, PermissionError):
        pass
    os.replace(temporary, token_file)


def serve_pairing(
    host: str,
    port: int,
    token_file: Path,
    timeout: int,
    on_paired: Callable[[], None],
    on_ready: Optional[Callable[[str, int], None]] = None,
) -> str:
    """Serve one bounded, physically authorized token request over TLS."""
    authorization = _code_part(secrets.token_bytes(16))
    paired = False
    rejected_attempts = 0
    with tempfile.TemporaryDirectory(prefix="powerglove-pair-") as temporary_name:
        temporary = Path(temporary_name)
        certificate, private_key, pem = generate_certificate(temporary, "PowerGlove-RetroPie-Pairing")
        code = display_pairing_code(certificate_code(pem), authorization)

        class PairingHandler(BaseHTTPRequestHandler):
            """Accept one authenticated token transfer during the bounded pairing window."""
            def log_message(self, _format: str, *_args: object) -> None:
                return

            def do_POST(self) -> None:
                nonlocal paired, rejected_attempts
                if self.path != "/pair" or paired:
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 1 <= length <= 1024:
                        raise ValueError("invalid pairing request")
                    body = json.loads(self.rfile.read(length))
                    supplied = str(body.get("authorization", "")).upper()
                    if not hmac.compare_digest(supplied, authorization):
                        raise ValueError("pairing code was rejected")
                    install_token(token_file, str(body.get("token", "")))
                    paired = True
                    response = b'{"paired":true}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                except (ValueError, json.JSONDecodeError, OSError) as exc:
                    rejected_attempts += 1
                    response = json.dumps({"error": str(exc)}).encode()
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, private_key)
        deadline = time.monotonic() + timeout
        server = BoundedTLSServer((host, port), PairingHandler, context, deadline)
        server.timeout = 0.5
        print(f"PowerGlove Vision pairing code: {code}", flush=True)
        print(f"This code expires in {timeout} seconds and can be used once.", flush=True)
        if on_ready is not None:
            on_ready(code, int(server.server_address[1]))
        while not paired and rejected_attempts < 5 and time.monotonic() < deadline:
            server.handle_request()
        server.server_close()
        if not paired:
            raise TimeoutError("pairing window expired")
    on_paired()
    return code


def pair_with_code(host: str, port: int, code: str, token: str, timeout: float = 8.0) -> None:
    """Verify a pinned certificate and transfer the shared token over TLS."""
    expected_certificate, authorization = normalize_pairing_code(code)
    discovery_context = ssl._create_unverified_context()
    with socket.create_connection((host, port), timeout=timeout) as raw_connection:
        with discovery_context.wrap_socket(raw_connection, server_hostname=host) as tls_connection:
            der = tls_connection.getpeercert(binary_form=True)
    pem = ssl.DER_cert_to_PEM_cert(der)
    if not hmac.compare_digest(certificate_code(pem), expected_certificate):
        raise ValueError("pairing code does not match the RetroPie certificate")
    context = ssl.create_default_context(cadata=pem)
    context.check_hostname = False
    connection = http.client.HTTPSConnection(host, port, timeout=timeout, context=context)
    payload = json.dumps({"authorization": authorization, "token": token}).encode()
    connection.request("POST", "/pair", body=payload, headers={"Content-Type": "application/json"})
    response = connection.getresponse()
    body = response.read()
    connection.close()
    if response.status != 200:
        try:
            message = json.loads(body).get("error", "pairing failed")
        except (ValueError, json.JSONDecodeError):
            message = "pairing failed"
        raise ValueError(message)


def pair_over_ssh(
    host: str,
    username: str,
    password: str,
    token: str,
    known_hosts: Path,
    timeout: float = 30.0,
) -> None:
    """Install the token with an isolated Python SSH client and private stdin."""
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not host or len(host) > 253 or any(character.isspace() for character in host):
        raise ValueError("enter a valid RetroPie hostname or IP address")
    if not username or len(username) > 64 or any(character not in allowed for character in username):
        raise ValueError("enter a valid RetroPie username")
    if not password or "\n" in password or "\r" in password:
        raise ValueError("enter a valid RetroPie password")
    if not 16 <= len(token) <= 256:
        raise ValueError("invalid controller token")
    helper = Path(__file__).resolve().parents[2] / "python" / "ssh_pair.py"
    command = [
        "uv", "run", "--no-project", "--python", "3.12",
        "--with", "paramiko>=3.4,<5", "python", str(helper),
    ]
    payload = json.dumps({
        "host": host,
        "username": username,
        "password": password,
        "token": token,
        "known_hosts": str(known_hosts),
        "timeout": timeout,
    }).encode()
    try:
        completed = subprocess.run(
            command,
            input=payload,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=timeout + 15,
        )
    finally:
        payload = b""
        password = ""
    if completed.returncode:
        error = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        message = error[-1] if error else "SSH pairing failed"
        raise ValueError(message[:240])


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for serving or initiating pairing."""
    parser = argparse.ArgumentParser(description="Pair PowerGlove Vision with RetroPie")
    parser.add_argument("--listen", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=PAIRING_PORT)
    parser.add_argument("--token-file", type=Path, default=Path("/etc/powerglove/token"))
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--receiver-service", default="powerglove-receiver.service")
    return parser


def main() -> int:
    """Run the selected pairing role and return a process exit status."""
    args = build_parser().parse_args()

    def restart_receiver() -> None:
        """Restart the installed receiver after accepting a new shared token."""
        subprocess.run(["systemctl", "restart", args.receiver_service], check=True)

    try:
        serve_pairing(args.listen, args.port, args.token_file, args.timeout, restart_receiver)
        print("Pairing complete. PowerGlove Vision receiver restarted.", flush=True)
        return 0
    except TimeoutError as exc:
        print(str(exc), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
