"""Display A3 RGB bitmaps, with optional retained drawing sessions.

Default is an offline preview. --apply is needed for any Bluetooth access.
Independent pixels, columns-serpentine text and RGB order are visually confirmed
on one 32x8 target. Other controllers and wiring still require calibration.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from matrix_smear import smear_payload, transport_packets, segment_config
from matrix_canvas import LAYOUTS, CHANNEL_ORDERS, content_canvas, wire_pixels, ascii_preview
from matrix_assets import FONT_NAMES, load_icons

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
    config_attempted = False
    probe_completed = False
    frame_count = args.width * args.height if args.single_segment else args.count
    if len(mic) != 13 or mic[0] != 0x72 or state[1] != 0xA3:
        raise ValueError("Expected an A3 backup with full microphone response")
    restore = bytearray([0x73]) + mic[1:-1]
    restore.append(sum(restore) & 255)
    queue = asyncio.Queue()
    sequence = 0
    report = {"address": backup["address"], "backup": str(args.backup.resolve()),
              "experimental": True, "pixel": args.pixel, "frame_pixels": args.count,
              "solid_cycle": args.solid_cycle,
              "pixel_range": args.pixel_range,
              "pixel_indices": args.pixel_indices,
              "pause_mic": args.pause_mic,
              "keep_drawing": args.keep_drawing,
              "variant": args.variant,
              "text": args.text, "layout": args.layout, "layout_cycle": args.layout_cycle,
              "font": args.font, "icon": args.icon,
              "channel_order": args.channel_order, "rotate": args.rotate,
              "single_segment": args.single_segment, "drawing_frame_pixels": frame_count,
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

    async def send(client, data, family, fragment_delay=0.06):
        nonlocal sequence
        sequence = (sequence + 1) & 255
        char = client.services.get_characteristic(WRITE)
        limit = min(180, char.max_write_without_response_size)
        for packet in transport_packets(data, sequence, max_write=limit, command_id=family):
            report["events"].append({"tx": packet.hex()})
            save()
            await client.write_gatt_char(char, packet, response=False)
            await asyncio.sleep(fragment_delay)

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
            before_mic = await query(client, "720072", b"\x72")
            before_state = await query(client, "818a8b96", b"\x81")
            before_config = await query(client, "631221f086", b"\x00\x63")
            paused_mic = bytearray(mic)
            paused_mic[1] = 0
            paused_mic[-1] = sum(paused_mic[:-1]) & 255
            command, expected = segment_config(config, frame_count, 1)
            continuing = (args.keep_drawing and before_config == expected
                          and before_mic == bytes(paused_mic)
                          and before_state[:3] == state[:3] and before_state[3] == 0x24)
            original = (before_mic == mic and before_state[:5] == state[:5]
                        and before_config == config)
            if not (original or continuing):
                raise RuntimeError("Settings match neither original backup nor the retained drawing session; aborting")
            if (config[2] << 8 | config[3]) * config[5] != args.count:
                raise RuntimeError("Frame size must match existing LED configuration")
            try:
                if continuing:
                    config_attempted = True
                    report["continued_drawing_session"] = True
                    print("Continuing retained drawing session without reconfiguring segments", flush=True)
                elif args.single_segment:
                    config_attempted = True  # A failed write may still reach the controller.
                    print(f"Temporarily using one drawing segment of {frame_count} pixels; music settings preserved", flush=True)
                    await send(client, command, 0x0B)
                    await asyncio.sleep(1)
                    if await query(client, "631221f086", b"\x00\x63") != expected:
                        raise RuntimeError("Temporary segment configuration not confirmed")
                    report["temporary_segment_configuration_verified"] = True
                    save()
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
                if args.pixel_range is not None or args.pixel_indices is not None:
                    color = tuple(args.color["RGB".index(c)] for c in args.channel_order)
                    frames = []
                    indices = (args.pixel_indices if args.pixel_indices is not None else
                               range(args.pixel_range[0], args.pixel_range[1] + 1))
                    for index in indices:
                        pixels = [(0, 0, 0)] * frame_count
                        pixels[index] = color
                        frames.append((f"wire pixel {index}", smear_payload(pixels, variant=args.variant)))
                elif args.layout_cycle or args.text is not None or args.icon is not None:
                    canvas = content_canvas(args.text or ("1234" if args.layout_cycle else None),
                                            args.icon, args.width, args.height, args.font)
                    layouts = LAYOUTS if args.layout_cycle else (args.layout,)
                    frames = [(f"{layout}: {args.text or args.icon or '1234'}", smear_payload(
                        wire_pixels(canvas, frame_count, layout, args.color,
                                    args.channel_order, args.rotate), variant=args.variant))
                              for layout in layouts]
                elif args.solid_cycle:
                    frames = [("all red", smear_payload([(255, 0, 0)] * frame_count, variant=args.variant)),
                              ("all green", smear_payload([(0, 255, 0)] * frame_count, variant=args.variant)),
                              ("all blue", smear_payload([(0, 0, 255)] * frame_count, variant=args.variant))]
                else:
                    frames = [(f"only wire pixel {args.pixel}, RGB={tuple(args.color)}", payload)]
                report["states_during_probe"] = []
                for label, frame in frames:
                    print(f"Experimental smear: {label} for {args.seconds}s", flush=True)
                    started = asyncio.get_running_loop().time()
                    await send(client, frame, 0x0B,
                               fragment_delay=0.005 if args.pixel_range is not None else 0.06)
                    if args.pixel_range is not None:
                        await asyncio.sleep(max(0, args.seconds - (asyncio.get_running_loop().time() - started)))
                        continue
                    await asyncio.sleep(args.seconds)
                    state_during = await query(client, "818a8b96", b"\x81")
                    report["states_during_probe"].append({"frame": label, "state": state_during.hex()})
                    save()
                probe_completed = True
            finally:
                if args.keep_drawing and probe_completed:
                    report["drawing_left_active"] = True
                    save()
                    print("Drawing mode retained as requested; original backup preserved for final restoration", flush=True)
                else:
                    print("Restoring original segments and microphone configuration", flush=True)
                    if config_attempted:
                        # A config write may restart the controller. Never reuse a
                        # client or notification subscription across that restart.
                        try:
                            await client.disconnect()
                        except Exception as error:
                            report.setdefault("disconnect_errors", []).append(repr(error))
                        from matrix_restore import retry_restore
                        await retry_restore(args.backup, 30)
                        report["restored"] = True
                        save()
                    for attempt in range(2):
                        if report["restored"]:
                            break
                        try:
                            if not client.is_connected:
                                await client.connect()
                                await client.start_notify(NOTIFY, notify)
                                await asyncio.sleep(0.5)
                            await send(client, restore, 0x0B)
                            await asyncio.sleep(0.5)
                            mic_after = await query(client, "720072", b"\x72")
                            state_after = await query(client, "818a8b96", b"\x81")
                            config_after = await query(client, "631221f086", b"\x00\x63")
                            report["restored"] = (mic_after == mic and state_after[:5] == state[:5]
                                                  and config_after == config)
                            save()
                            if report["restored"]:
                                break
                        except Exception as error:
                            report.setdefault("restore_errors", []).append(repr(error))
                            save()
                            if attempt == 0:
                                await asyncio.sleep(1)
                    if not report["restored"]:
                        raise RuntimeError("Restoration did not match backup; stop testing")
                    print("Original microphone, operating mode and LED settings verified", flush=True)
            if client.is_connected:
                await client.stop_notify(NOTIFY)
    except BaseException as error:
        report["error"] = repr(error)
        raise
    finally:
        save()
        print(f"Log: {log_path}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--list-assets", action="store_true", help="List local fonts and icons without Bluetooth")
    parser.add_argument("--font", choices=FONT_NAMES, default="classic5x7")
    parser.add_argument("--icon", choices=tuple(load_icons()), help="8x8 icon, alone or to the left of text")
    parser.add_argument("--count", type=int, default=300, help="Original configured wire capacity, not matrix area")
    parser.add_argument("--pixel", type=int, default=0)
    parser.add_argument("--pixel-indices", nargs="+", type=int,
                        help="Show selected wire indices in order, querying controller after each frame")
    parser.add_argument("--pixel-range", nargs=2, type=int, metavar=("FIRST", "LAST"),
                        help="Walk inclusive wire indices, one lit pixel per frame, at --seconds interval")
    parser.add_argument("--seconds", type=float, default=4)
    parser.add_argument("--solid-cycle", action="store_true", help="Try red, green, blue for --seconds each")
    parser.add_argument("--keep-drawing", action="store_true",
                        help="Retain drawing mode after success and allow subsequent tests to reuse it; restore on errors")
    parser.add_argument("--pause-mic", action="store_true", help="Temporarily disable the captured microphone configuration before drawing")
    parser.add_argument("--variant", choices=("legacy", "a3-zero-tail"), default="legacy",
                        help="A3 layout from upstream issue #6; unknown tail bytes explicitly tested as zero")
    parser.add_argument("--text", help="Static text, limited to the selected font's glyphs and available width")
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--height", type=int, default=8)
    parser.add_argument("--layout", choices=LAYOUTS, default="rows-serpentine")
    parser.add_argument("--layout-cycle", action="store_true", help="Show the text through all four possible wire layouts")
    parser.add_argument("--channel-order", choices=CHANNEL_ORDERS, default="RGB")
    parser.add_argument("--color", nargs=3, type=int, default=(255, 255, 255), metavar=("R", "G", "B"))
    parser.add_argument("--rotate", action="store_true", help="Rotate the drawing by 180 degrees in software")
    parser.add_argument("--single-segment", action="store_true", help="Temporarily set one drawing segment of width*height pixels, preserve music config, then restore all settings")
    parser.add_argument("--log-dir", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.list_assets:
        print("Fonts: " + ", ".join(FONT_NAMES))
        print("Icons: " + ", ".join(load_icons()))
        return
    if args.apply and args.backup is None:
        parser.error("--apply requires --backup")
    if args.keep_drawing and not args.single_segment:
        parser.error("Retained drawing sessions require --single-segment")
    if args.single_segment and not args.pause_mic:
        parser.error("Temporary segment changes require --pause-mic and automatic full backup recovery")
    frame_count = args.width * args.height if args.single_segment else args.count
    if not 0 <= args.pixel < frame_count or not 0.1 <= args.seconds <= 10:
        parser.error("Invalid pixel or duration")
    if args.pixel_indices is not None:
        if any(not 0 <= index < frame_count for index in args.pixel_indices):
            parser.error("Pixel indices must be inside the frame")
        if args.pixel_range is not None or args.solid_cycle or args.text is not None or args.layout_cycle or args.icon is not None:
            parser.error("Choose only one type of frame sequence")
    if args.pixel_range is not None:
        first, last = args.pixel_range
        if not 0 <= first <= last < frame_count:
            parser.error("Pixel range must be ordered and inside the frame")
        if args.solid_cycle or args.text is not None or args.layout_cycle or args.icon is not None:
            parser.error("Pixel range cannot be combined with text or solid colors")
    if args.single_segment and (args.variant != "a3-zero-tail" or not 1 <= frame_count <= 300):
        parser.error("Single segment requires A3 variant and 1..300 matrix pixels")
    if args.solid_cycle and (args.text is not None or args.layout_cycle or args.icon is not None):
        parser.error("Choose either text/layout test or solid colors")
    try:
        if args.text is not None or args.layout_cycle or args.icon is not None:
            canvas = content_canvas(args.text or ("1234" if args.layout_cycle else None),
                                    args.icon, args.width, args.height, args.font)
            pixels = wire_pixels(canvas, frame_count, args.layout, args.color,
                                 args.channel_order, args.rotate)
            print(ascii_preview(canvas))
        else:
            if any(not 0 <= c <= 255 for c in args.color):
                raise ValueError("Color must contain RGB bytes from 0 to 255")
            pixels = [(0, 0, 0)] * frame_count
            pixels[args.pixel] = tuple(args.color["RGB".index(c)] for c in args.channel_order)
    except ValueError as error:
        parser.error(str(error))
    payload = smear_payload(pixels, variant=args.variant)
    packets = transport_packets(payload, 1)
    print(f"Frame: {len(payload)} bytes, {len(packets)} transport packets at 180 bytes max")
    if args.apply:
        backup = json.loads(args.backup.read_text())
        asyncio.run(apply(args, backup, payload))
    else:
        print("Offline preview only. Use --apply and --backup for Bluetooth display.")


if __name__ == "__main__":
    main()
