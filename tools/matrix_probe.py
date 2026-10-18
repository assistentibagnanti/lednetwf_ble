"""Try one RGB smear frame and restore the captured microphone configuration.

Default is an offline preview. --apply is needed for any Bluetooth access.
Uniform A3-layout frames have been visually confirmed on one target device.
Individual pixel addressing and matrix wiring remain unverified.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from matrix_smear import smear_payload, transport_packets
from matrix_canvas import LAYOUTS, CHANNEL_ORDERS, text_canvas, wire_pixels, ascii_preview

WRITE = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY = "0000ff02-0000-1000-8000-00805f9b34fb"


def captured_payload(backup, name):
    raw = bytes.fromhex(next(n["hex"] for n in backup["notifications"] if n["query"] == name))
    payload = raw[8:]
    if len(raw) < 9 or sum(payload[:-1]) & 255 != payload[-1]:
        raise ValueError(f"Invalid captured checksum: {name}")
    return payload


async def apply(args, backup, payload):
    from bleak import BleakClient, BleakScanner

    mic = captured_payload(backup, "symp_get_mic_info")
    state = captured_payload(backup, "state_upload")
    config = captured_payload(backup, "get_symp_config_v2")
    if len(mic) != 13 or mic[0] != 0x72 or state[1] != 0xA3:
        raise ValueError("Expected an A3 backup with full microphone response")
    restore = bytearray([0x73]) + mic[1:-1]
    restore.append(sum(restore) & 255)
    queue = asyncio.Queue()
    sequence = 0
    report = {"address": backup["address"], "backup": str(args.backup.resolve()),
              "experimental": True, "pixel": args.pixel, "frame_pixels": args.count,
              "solid_cycle": args.solid_cycle,
              "pause_mic": args.pause_mic,
              "variant": args.variant,
              "text": args.text, "layout": args.layout, "layout_cycle": args.layout_cycle,
              "channel_order": args.channel_order, "rotate": args.rotate,
              "events": [], "restored": False, "pixel_control_confirmed": False}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    log_path = args.log_dir / f"matrix-probe-{stamp}.json"
    args.log_dir.mkdir(parents=True, exist_ok=True)

    def save():
        log_path.write_text(json.dumps(report, indent=2) + "\n")

    def notify(_, data):
        report["events"].append({"rx": bytes(data).hex()})
        save()
        queue.put_nowait(bytes(data)[8:])

    async def send(client, data, family):
        nonlocal sequence
        sequence = (sequence + 1) & 255
        char = client.services.get_characteristic(WRITE)
        limit = min(180, char.max_write_without_response_size)
        for packet in transport_packets(data, sequence, max_write=limit, command_id=family):
            report["events"].append({"tx": packet.hex()})
            save()
            await client.write_gatt_char(char, packet, response=False)
            await asyncio.sleep(0.06)

    async def query(client, raw, prefix):
        while not queue.empty():
            queue.get_nowait()
        await send(client, bytes.fromhex(raw), 0x0A)
        async with asyncio.timeout(5):
            while True:
                data = await queue.get()
                if data.startswith(prefix):
                    if sum(data[:-1]) & 255 != data[-1]:
                        raise RuntimeError("Response checksum mismatch")
                    return data

    save()
    try:
        device = await BleakScanner.find_device_by_address(backup["address"], timeout=12)
        if device is None:
            raise RuntimeError("Device not found")
        async with BleakClient(device, timeout=20) as client:
            await client.start_notify(NOTIFY, notify)
            await asyncio.sleep(0.5)
            if await query(client, "720072", b"\x72") != mic:
                raise RuntimeError("Microphone settings changed since backup; aborting")
            before_state = await query(client, "818a8b96", b"\x81")
            if before_state[:5] != state[:5]:
                raise RuntimeError("Operating mode changed since backup; aborting")
            if await query(client, "631221f086", b"\x00\x63") != config:
                raise RuntimeError("LED configuration changed since backup; aborting")
            if (config[2] << 8 | config[3]) * config[5] != args.count:
                raise RuntimeError("Frame size must match existing LED configuration")
            try:
                if args.pause_mic:
                    pause = bytearray(restore)
                    pause[1] = 0
                    pause[-1] = sum(pause[:-1]) & 255
                    print("Temporarily disabling microphone before drawing", flush=True)
                    await send(client, pause, 0x0B)
                    await asyncio.sleep(0.5)
                    paused = await query(client, "720072", b"\x72")
                    report["mic_pause_verified"] = paused[1] == 0 and paused[2:-1] == mic[2:-1]
                    save()
                    if not report["mic_pause_verified"]:
                        raise RuntimeError("Microphone pause not confirmed; aborting draw")
                if args.layout_cycle or args.text is not None:
                    canvas = text_canvas(args.text or "1234", args.width, args.height)
                    layouts = LAYOUTS if args.layout_cycle else (args.layout,)
                    frames = [(f"{layout}: {args.text or '1234'}", smear_payload(
                        wire_pixels(canvas, args.count, layout, args.color,
                                    args.channel_order, args.rotate), variant=args.variant))
                              for layout in layouts]
                elif args.solid_cycle:
                    frames = [("all red", smear_payload([(255, 0, 0)] * args.count, variant=args.variant)),
                              ("all green", smear_payload([(0, 255, 0)] * args.count, variant=args.variant))]
                else:
                    frames = [(f"wire pixel {args.pixel} red", payload)]
                report["states_during_probe"] = []
                for label, frame in frames:
                    print(f"Experimental smear: {label} for {args.seconds}s", flush=True)
                    await send(client, frame, 0x0B)
                    await asyncio.sleep(args.seconds)
                    state_during = await query(client, "818a8b96", b"\x81")
                    report["states_during_probe"].append({"frame": label, "state": state_during.hex()})
                    save()
            finally:
                print("Restoring original microphone configuration", flush=True)
                # Always attempt a restore after transmission, including failed probes.
                await send(client, restore, 0x0B)
                await asyncio.sleep(0.5)
                mic_after = await query(client, "720072", b"\x72")
                state_after = await query(client, "818a8b96", b"\x81")
                config_after = await query(client, "631221f086", b"\x00\x63")
                report["restored"] = (mic_after == mic and state_after[:5] == state[:5]
                                      and config_after == config)
                save()
                if not report["restored"]:
                    raise RuntimeError("Restoration did not match backup; stop testing")
                print("Original microphone, operating mode and LED settings verified", flush=True)
            await client.stop_notify(NOTIFY)
    except BaseException as error:
        report["error"] = repr(error)
        raise
    finally:
        save()
        print(f"Log: {log_path}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--count", type=int, default=300, help="Existing wire capacity, not matrix area; no settings are changed")
    parser.add_argument("--pixel", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=4)
    parser.add_argument("--solid-cycle", action="store_true", help="Try all red then all green for --seconds each, then restore")
    parser.add_argument("--pause-mic", action="store_true", help="Temporarily disable the captured microphone configuration before drawing")
    parser.add_argument("--variant", choices=("legacy", "a3-zero-tail"), default="legacy",
                        help="A3 layout from upstream issue #6; unknown tail bytes explicitly tested as zero")
    parser.add_argument("--text", help="Static text: A-Z, digits, and basic temperature/time punctuation")
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--height", type=int, default=8)
    parser.add_argument("--layout", choices=LAYOUTS, default="rows-serpentine")
    parser.add_argument("--layout-cycle", action="store_true", help="Show the text through all four possible wire layouts")
    parser.add_argument("--channel-order", choices=CHANNEL_ORDERS, default="RGB")
    parser.add_argument("--color", nargs=3, type=int, default=(255, 255, 255), metavar=("R", "G", "B"))
    parser.add_argument("--rotate", action="store_true", help="Rotate the drawing by 180 degrees in software")
    parser.add_argument("--log-dir", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.pixel < args.count or not 0.1 <= args.seconds <= 10:
        parser.error("Invalid pixel or duration")
    if args.solid_cycle and (args.text is not None or args.layout_cycle):
        parser.error("Choose either text/layout test or solid colors")
    try:
        if args.text is not None or args.layout_cycle:
            canvas = text_canvas(args.text or "1234", args.width, args.height)
            pixels = wire_pixels(canvas, args.count, args.layout, args.color,
                                 args.channel_order, args.rotate)
            print(ascii_preview(canvas))
        else:
            pixels = [(0, 0, 0)] * args.count
            pixels[args.pixel] = (255, 0, 0)
    except ValueError as error:
        parser.error(str(error))
    payload = smear_payload(pixels, variant=args.variant)
    packets = transport_packets(payload, 1)
    print(f"Frame: {len(payload)} bytes, {len(packets)} transport packets at 180 bytes max")
    if args.apply:
        backup = json.loads(args.backup.read_text())
        asyncio.run(apply(args, backup, payload))
    else:
        print("Offline only. Individual pixel addressing and wiring unverified. Use --apply for the timed probe.")


if __name__ == "__main__":
    main()
