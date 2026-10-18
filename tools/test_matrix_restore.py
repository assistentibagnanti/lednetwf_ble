"""Recovery must survive a controller restart and use a fresh GATT client."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from matrix_restore import restore_backup
from matrix_smear import segment_config


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_config_restart_then_fresh_connection_restores_microphone(self):
        config = bytes.fromhex("0063001e000a01001e0ab4")
        _, temporary = segment_config(config, 256, 1)
        mic = bytes.fromhex("720126040000000000002832f7")
        state_body = bytes.fromhex("81a32362043200000000030000")
        state = state_body + bytes([sum(state_body) & 255])
        backup = {"address": "00:00:00:00:00:01", "notifications": [
            {"query": label, "hex": (bytes(8) + data).hex()}
            for label, data in (("get_symp_config_v2", config),
                                ("symp_get_mic_info", mic), ("state_upload", state))]}
        clients = []
        writes = []
        live = {"config": temporary, "mic_restored": False}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                if clients:
                    assert not clients[-1].is_connected
                self.is_connected = True
                self.buffer = bytearray()
                clients.append(self)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                self.is_connected = False

            async def start_notify(self, uuid, handler):
                self.handler = handler

            async def write_gatt_char(self, uuid, packet, **kwargs):
                index = int.from_bytes(packet[2:4], "big") & 0x7FFF
                if index == 0:
                    self.buffer = bytearray(packet[8:])
                else:
                    self.buffer.extend(packet[5:])
                if not packet[2] & 128:
                    return
                raw = bytes(self.buffer)
                writes.append(raw)
                if raw[0] == 0x62:
                    self.assert_restore = raw == segment_config(config)[0]
                    assert self.assert_restore
                    live["config"] = config
                    self.is_connected = False
                    raise RuntimeError("Controller restarted after configuration write")
                if raw[0] == 0x73:
                    assert raw[1:-1] == mic[1:-1]
                    assert sum(raw[:-1]) & 255 == raw[-1]
                    live["mic_restored"] = True
                    return
                response = {0x81: state, 0x63: live["config"], 0x72: mic}[raw[0]]
                self.handler(None, bytes(8) + response)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.json"
            path.write_text(json.dumps(backup))
            with patch("bleak.BleakClient", FakeClient), \
                 patch("bleak.BleakScanner.find_device_by_address", AsyncMock(return_value=object())), \
                 patch("matrix_restore.asyncio.sleep", AsyncMock()):
                await restore_backup(path)
        self.assertEqual(len(clients), 2)
        self.assertTrue(live["mic_restored"])
        self.assertEqual(live["config"], config)
        self.assertEqual(sum(raw[0] == 0x62 for raw in writes), 1)


if __name__ == "__main__":
    unittest.main()
