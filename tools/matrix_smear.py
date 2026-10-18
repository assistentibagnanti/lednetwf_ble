"""A3 0x59 RGB framing, segment configuration and matrix wire mappings.

Protocol reference: 8none1/zengge_lednetwf README, Header and Smear sections.
segment_config builds persistent configuration commands; callers handle recovery.
"""
from __future__ import annotations


def segment_config(response, pixels_per_segment=None, segments=None):
    """Build A3 0x62 from a validated 0x63 capture, preserving music/IC/order.

    Returns (command, expected readback). This command persists configuration;
    callers must restore the original command even after a failed experiment.
    """
    if len(response) != 11 or response[:2] != b"\x00\x63" or sum(response[:-1]) & 255 != response[-1]:
        raise ValueError("Expected complete checksummed A3 IC configuration")
    expected = bytearray(response)
    if pixels_per_segment is not None:
        if not 1 <= pixels_per_segment <= 300:
            raise ValueError("Pixels per segment must be 1..300")
        expected[2:4] = pixels_per_segment.to_bytes(2, "big")
    if segments is not None:
        if not 1 <= segments <= 64:
            raise ValueError("Segment count must be 1..64")
        expected[4:6] = segments.to_bytes(2, "big")
    expected[-1] = sum(expected[:-1]) & 255
    command = bytearray([0x62]) + expected[2:10] + bytes([0xF0])
    command.append(sum(command) & 255)
    return bytes(command), bytes(expected)


def smear_payload(pixels, brightness=20, variant="legacy"):
    """Build a static RGB smear frame with dynamic size and checksum."""
    if not 1 <= len(pixels) <= 1000:
        raise ValueError("Expected 1..1000 pixels")
    if not 1 <= brightness <= 100:
        raise ValueError("Brightness must be 1..100")
    if variant not in ("legacy", "a3-zero-tail"):
        raise ValueError("Unknown smear variant")
    data = bytearray([0x59])
    if variant == "a3-zero-tail":
        # Issue #6 comment-1902776898: duplicate transport total length.
        # Two unknown fields: zero worked on the tested A3; meaning is unknown.
        data.extend((3 * len(pixels) + 9).to_bytes(2, "big"))
    for pixel in pixels:
        if len(pixel) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in pixel):
            raise ValueError("Pixels must be RGB byte triples")
        if variant == "a3-zero-tail":
            data.extend(round(v * brightness / 100) for v in pixel)
        else:
            data.extend(pixel)
    if variant == "a3-zero-tail":
        data.extend([0, 0, 1, 50, 0])  # unknown, unknown, static, speed, direction
    else:
        data.extend([1, 50, brightness, 0])  # static, speed, brightness, direction
    data.append(sum(data) & 255)
    return bytes(data)


def transport_packets(payload, sequence, max_write=180, command_id=0x0B):
    """Encode v0 first/continuation headers, respecting ATT write size.

    First header: 8 bytes; continuation header: 5 bytes. The command ID is
    included only in the first fragment. This follows the retired project's
    Header section; fragmented A3 frames are verified on the calibrated target.
    """
    if not payload or len(payload) > 65535 or not 9 <= max_write <= 255:
        raise ValueError("Invalid payload or ATT write limit")
    if not 0 <= sequence <= 255 or not 0 <= command_id <= 255:
        raise ValueError("Sequence and command ID must be bytes")
    fragmented = len(payload) + 8 > max_write
    packets = []
    offset = 0
    index = 0
    while offset < len(payload):
        capacity = max_write - (8 if index == 0 else 5)
        chunk = payload[offset:offset + capacity]
        offset += len(chunk)
        control = index | (0x8000 if offset == len(payload) else 0)
        header = bytearray([0x40 if fragmented else 0, sequence])
        header.extend(control.to_bytes(2, "big"))
        if index == 0:
            header.extend(len(payload).to_bytes(2, "big"))
            header.extend([len(chunk) + 1, command_id])
        else:
            header.append(len(chunk))
        packets.append(bytes(header) + chunk)
        index += 1
    return packets


def pixel_index(x, y, width=32, height=8, layout="rows-serpentine"):
    """Map top-left coordinates to a physical wire index; wiring is unverified."""
    if width < 1 or height < 1 or not (0 <= x < width and 0 <= y < height):
        raise ValueError("Pixel outside matrix")
    if layout == "rows":
        return y * width + x
    if layout == "rows-serpentine":
        return y * width + (width - x - 1 if y % 2 else x)
    if layout == "columns":
        return x * height + y
    if layout == "columns-serpentine":
        return x * height + (height - y - 1 if x % 2 else y)
    raise ValueError("Unknown layout")
