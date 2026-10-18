"""Offline checks of captured query compatibility and RGB frame boundaries."""
import unittest

from matrix_smear import pixel_index, smear_payload, transport_packets


class MatrixTransportTests(unittest.TestCase):
    def test_captured_state_query(self):
        self.assertEqual(transport_packets(bytes.fromhex("818a8b96"), 1),
                         [bytes.fromhex("000180000004050b818a8b96")])
        self.assertEqual(transport_packets(bytes.fromhex("818a8b96"), 1, command_id=10),
                         [bytes.fromhex("000180000004050a818a8b96")])

    def test_legacy_48_led_header_and_rgb_order(self):
        frame = smear_payload([(255, 0, 0)] + [(0, 0, 0)] * 47)
        packet, = transport_packets(frame, 16)
        self.assertEqual(packet[:11], bytes.fromhex("001080000096970b59ff00"))
        self.assertEqual(frame[-5:-1], bytes([1, 50, 20, 0]))
        self.assertEqual(sum(frame[:-1]) & 255, frame[-1])

    def test_fragment_reassembly_at_small_and_large_mtu(self):
        for count in (1, 48, 57, 256, 300):
            frame = smear_payload([(i % 256, 0, 255) for i in range(count)])
            for limit in (20, 180, 255):
                with self.subTest(count=count, limit=limit):
                    packets = transport_packets(frame, 255, max_write=limit)
                    recovered = bytearray()
                    for i, p in enumerate(packets):
                        self.assertLessEqual(len(p), limit)
                        self.assertEqual(p[1], 255)
                        self.assertEqual(int.from_bytes(p[2:4], "big") & 0x7FFF, i)
                        self.assertEqual(bool(p[2] & 128), i == len(packets) - 1)
                        self.assertEqual(bool(p[0] & 64), len(packets) > 1)
                        if i == 0:
                            self.assertEqual(int.from_bytes(p[4:6], "big"), len(frame))
                            self.assertEqual(p[6], len(p) - 7)
                            recovered.extend(p[8:])
                        else:
                            self.assertEqual(p[4], len(p) - 5)
                            recovered.extend(p[5:])
                    self.assertEqual(recovered, frame)

    def test_matrix_layouts_cover_exactly_256_pixels(self):
        for layout in ("rows", "rows-serpentine", "columns", "columns-serpentine"):
            indices = {pixel_index(x, y, layout=layout) for y in range(8) for x in range(32)}
            self.assertEqual(indices, set(range(256)))

    def test_invalid_input_rejected(self):
        for pixels in ([], [(256, 0, 0)], [(-1, 0, 0)], [(1, 2)]):
            with self.assertRaises(ValueError):
                smear_payload(pixels)
        with self.assertRaises(ValueError):
            transport_packets(b"x", 1, max_write=8)
        with self.assertRaises(ValueError):
            pixel_index(32, 0)


if __name__ == "__main__":
    unittest.main()
