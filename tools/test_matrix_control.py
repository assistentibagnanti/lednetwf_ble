import http.client
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from matrix_control import Controller, display_command, make_server, validate_content


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.backup = self.root / "backup.json"
        self.backup.write_text(json.dumps({"notifications": [
            {"query": "get_symp_config_v2", "hex": "00" * 8 + "0063001e000a01001e0ab4"}]}))
        self.content = {"text": "22.5°", "font": "digits3x8", "icon": "color-sun",
                        "color": "#00c8ff", "icon_color": None, "fill_height": True}

    def test_preview_keeps_rgb_colors_and_rejects_overflow(self):
        content, image = validate_content(self.content)
        self.assertEqual(content, self.content)
        colors = {tuple(pixel) for row in image for pixel in row}
        self.assertTrue({(255, 190, 0), (255, 255, 255), (0, 200, 255)} <= colors)
        for bad in ({"text": "123456789"}, {"color": "red"}, {"font": "unknown"},
                    {"fill_height": "false"}, {"icon": ["sunny"]}):
            with self.assertRaises(ValueError):
                validate_content(self.content | bad)

    def test_command_keeps_session_and_treats_message_as_literal_argument(self):
        command = display_command(self.content | {"text": "-1"}, self.backup,
                                  self.root, "columns-serpentine")
        self.assertIn("--text=-1", command)
        self.assertIn("--keep-drawing", command)
        self.assertEqual(command[command.index("--count") + 1], "300")
        self.assertEqual(command[command.index("--color") + 1:command.index("--color") + 4], ["0", "200", "255"])

    def test_busy_device_is_serialized_and_failed_send_releases_controls(self):
        control = Controller(self.backup, self.root / "logs", "columns-serpentine")
        with patch("matrix_control.threading.Thread") as thread:
            self.assertTrue(control.start("display", self.content))
            self.assertTrue(control.status()["busy"])
            self.assertFalse(control.start("restore", {}))
            with patch("matrix_control.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "Device not found")):
                thread.call_args.kwargs["target"]()
        self.assertFalse(control.status()["busy"])
        self.assertEqual(control.status()["error"], "Device not found")
        self.assertIsNone(control.status()["last_content"])

    def test_http_preview_does_not_start_bluetooth_and_rejects_external_requests(self):
        control = Controller(None, self.root, "columns-serpentine", preview_only=True)
        server = make_server(control, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        self.addCleanup(connection.close)
        with patch("matrix_control.subprocess.run") as run:
            connection.request("GET", "/")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn(b"Invia al pannello", response.read())
            connection.request("POST", "/api/preview", json.dumps(self.content))
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(len(json.loads(response.read())["pixels"]), 8)
            connection.request("POST", "/api/display", json.dumps(self.content))
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
            connection.request("POST", "/api/restore", "{}", headers={"Origin": "https://example.com"})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            connection.request("GET", "/api/catalog", headers={"Host": "example.com"})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
