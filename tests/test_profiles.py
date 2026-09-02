import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from powerglove_vision.profile_control import (
    load_registry,
    select_profile,
    sign_message,
    send_request,
    verify_message,
    ProfileCommandServer,
)


class ProfileTests(unittest.TestCase):
    def test_signature_detects_tampering(self):
        message = sign_message({"protocol": "powerglove-profile/1", "profile": "program_b"}, "a-long-test-token")
        self.assertTrue(verify_message(message, "a-long-test-token"))
        message["profile"] = "program_g"
        self.assertFalse(verify_message(message, "a-long-test-token"))

    def test_registry_uses_exact_case_insensitive_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "games.json"
            path.write_text(json.dumps({"games": {"Joust (USA).nes": "program_b"}}))
            registry = load_registry(path)
        self.assertEqual(select_profile(registry, "nes", "/roms/JOUST (USA).NES"), "program_b")
        self.assertIsNone(select_profile(registry, "snes", "/roms/JOUST (USA).NES"))
        self.assertIsNone(select_profile(registry, "nes", "/roms/Other.nes"))

    def test_registry_rejects_unknown_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "games.json"
            path.write_text(json.dumps({"games": {"Mystery.nes": "run-a-command"}}))
            with self.assertRaises(ValueError):
                load_registry(path)

    def test_command_server_acknowledges_profile(self):
        token = "a-long-test-token"
        server = ProfileCommandServer("127.0.0.1", 0, token)
        port = server.socket.getsockname()[1]
        result = {}

        def client():
            result.update(send_request(
                "127.0.0.1", port, token, "program_g", "nes",
                "/roms/Gun.Smoke (USA).nes", 0.2,
            ))

        thread = threading.Thread(target=client)
        thread.start()
        request = None
        deadline = time.monotonic() + 1
        while request is None and time.monotonic() < deadline:
            request = server.take()
            time.sleep(0.005)
        self.assertIsNotNone(request)
        server.acknowledge(request, True, request.profile)
        thread.join(timeout=1)
        server.close()
        self.assertFalse(thread.is_alive())
        self.assertTrue(result["accepted"])
        self.assertEqual(result["profile"], "program_g")


if __name__ == "__main__":
    unittest.main()
