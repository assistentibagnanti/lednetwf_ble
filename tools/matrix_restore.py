"""Recover exact saved A3 LED and microphone configuration across device restarts."""
import argparse
import asyncio
import json
import time
from pathlib import Path

from matrix_probe import captured_payload, WRITE, NOTIFY
from matrix_smear import segment_config, transport_packets


async def restore_backup(path, scanner=None):
    from bleak import BleakClient, BleakScanner

    backup = json.loads(path.read_text())
    config = captured_payload(backup, "get_symp_config_v2")
    mic = captured_payload(backup, "symp_get_mic_info")
    state = captured_payload(backup, "state_upload")
    config_command, _ = segment_config(config)
    mic_command = bytearray([0x73]) + mic[1:-1]
    mic_command.append(sum(mic_command) & 255)
    for attempt in range(3):
        print("Searching for controller for recovery", flush=True)
        if scanner is None:
            device = await BleakScanner.find_device_by_address(backup["address"], timeout=3)
        else:
            device = None
            for _ in range(15):
                device = next((d for d in scanner.discovered_devices if d.address.upper() == backup["address"].upper()), None)
                if device is not None:
                    break
                await asyncio.sleep(0.2)
        if device is None:
            raise RuntimeError("Device not found for recovery")
        queue = asyncio.Queue()
        seq = 0
        print("Connecting for recovery", flush=True)
        async with BleakClient(device, timeout=8) as client:
            def notify(_, data):
                print("RX", bytes(data).hex(), flush=True)
                queue.put_nowait(bytes(data)[8:])

            async def send(raw, family):
                nonlocal seq
                seq += 1
                for p in transport_packets(raw, seq, max_write=20, command_id=family):
                    await client.write_gatt_char(WRITE, p, response=False)
                    await asyncio.sleep(0.1)

            async def query(raw, prefix):
                while not queue.empty():
                    queue.get_nowait()
                await send(bytes.fromhex(raw), 10)
                async with asyncio.timeout(5):
                    while True:
                        data = await queue.get()
                        if data.startswith(prefix):
                            if sum(data[:-1]) & 255 != data[-1]:
                                raise RuntimeError("Invalid response checksum")
                            return data

            await client.start_notify(NOTIFY, notify)
            await asyncio.sleep(0.5)
            live_state = await query("818a8b96", b"\x81")
            if live_state[1] != 0xA3:
                raise RuntimeError("Wrong device model; abort recovery")
            live_config = await query("631221f086", b"\x00\x63")
            if live_config != config:
                print("Restoring original LED configuration; controller may restart", flush=True)
                try:
                    await send(config_command, 11)
                except Exception as error:
                    print("Configuration write interrupted:", error, flush=True)
                # Never reuse services or notification subscription after a config write.
            else:
                print("Original LED configuration confirmed. Restoring microphone.", flush=True)
                await send(mic_command, 11)
                await asyncio.sleep(0.5)
                mic_after = await query("720072", b"\x72")
                state_after = await query("818a8b96", b"\x81")
                config_after = await query("631221f086", b"\x00\x63")
                if mic_after == mic and state_after[:5] == state[:5] and config_after == config:
                    print("RECOVERY VERIFIED: original microphone, mode/effect and LED configuration", flush=True)
                    return
        await asyncio.sleep(2)
    raise RuntimeError("Recovery not verified after three fresh connections")


async def retry_restore(path, seconds):
    from bleak import BleakScanner
    deadline = time.monotonic() + seconds
    while True:
        try:
            # Keep BlueZ discovery reference alive while connecting to a
            # device whose advertisement may disappear during its restart.
            async with BleakScanner() as scanner:
                await restore_backup(path, scanner)
            return
        except Exception as error:
            print("Recovery connection attempt:", type(error).__name__, str(error), flush=True)
            if time.monotonic() >= deadline:
                raise
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--retry-seconds", type=int, default=0)
    args = parser.parse_args()
    asyncio.run(retry_restore(args.backup, args.retry_seconds))
