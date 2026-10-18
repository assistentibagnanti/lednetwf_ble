import hashlib
import json
import unittest

from matrix_assets import ASSETS, load_font, load_icons
from matrix_canvas import content_canvas, text_canvas, wire_pixels


class MatrixAssetTests(unittest.TestCase):
    def test_vendored_sources_match_recorded_hashes(self):
        for entry in json.loads((ASSETS / "sources.json").read_text()):
            self.assertEqual(hashlib.sha256((ASSETS / entry["file"]).read_bytes()).hexdigest(),
                             entry["sha256"], entry["file"])

    def test_font8x8_matches_upstream_A_orientation(self):
        face = load_font("font8x8")
        self.assertEqual(set(face.glyphs), {chr(i) for i in range(32, 128)} |
                         {chr(i) for i in range(160, 256)})
        canvas = text_canvas("A", width=8, font="font8x8")
        self.assertEqual([x for x, bit in enumerate(canvas[0]) if bit], [2, 3])
        self.assertEqual([x for x, bit in enumerate(canvas[4]) if bit], list(range(6)))
        for value in ("Èéà°", "CIAO"):
            text_canvas(value, font="font8x8")
        with self.assertRaises(ValueError):
            text_canvas("12345", font="font8x8")

    def test_tiny_font_keeps_case_accents_descenders_and_eight_characters(self):
        face = load_font("tom-thumb")
        self.assertNotEqual(face.glyphs["A"], face.glyphs["a"])
        self.assertTrue(face.glyphs["g"][-1])
        for value in ("12345678", "Èéà°€"):
            text_canvas(value, font="tom-thumb")
        with self.assertRaises(ValueError):
            text_canvas("123456789", font="tom-thumb")

    def test_icon_and_temperature_fit_without_overlapping(self):
        canvas = content_canvas("22.5°", "sunny", font="tom-thumb")
        self.assertTrue(all(not row[8] for row in canvas))
        self.assertTrue(any(any(row[:8]) for row in canvas))
        self.assertTrue(any(any(row[9:]) for row in canvas))
        pixels = wire_pixels(canvas, count=256, layout="columns-serpentine")
        self.assertEqual(sum(any(p) for p in pixels), sum(sum(row) for row in canvas))
        with self.assertRaises(ValueError):
            content_canvas("22.5°", "sunny", font="classic5x7")

    def test_icon_bit_orientation_and_unknown_content(self):
        icons = load_icons()
        self.assertEqual(icons["left_col"], (1,) * 8)
        self.assertEqual(icons["top_row"], (255,) + (0,) * 7)
        for name in icons:
            content_canvas(icon=name)
        with self.assertRaises(ValueError):
            content_canvas(icon="missing")
        with self.assertRaises(ValueError):
            text_canvas("🙂", font="tom-thumb")


if __name__ == "__main__":
    unittest.main()
