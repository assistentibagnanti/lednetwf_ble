import hashlib
import json
import unittest

from matrix_assets import ASSETS, load_font, load_icons, load_color_icons
from matrix_canvas import content_canvas, rgb_content_canvas, text_canvas, wire_pixels


class MatrixAssetTests(unittest.TestCase):
    def test_full_height_numeric_font_uses_eight_rows(self):
        face = load_font("digits3x8")
        self.assertEqual(face.glyphs["0"], (7, 5, 5, 5, 5, 5, 5, 7))
        self.assertEqual(face.glyphs["."][-1], 2)
        canvas = text_canvas("12345678", font="digits3x8")
        self.assertTrue(all(any(row) for row in canvas))
        with self.assertRaises(ValueError):
            text_canvas("CIAO", font="digits3x8")

    def test_spleen_and_full_height_text(self):
        self.assertEqual(load_font("spleen5x8").height, 8)
        canvas = text_canvas("CIAO12", font="spleen5x8", fill_height=True)
        self.assertTrue(any(canvas[0]))
        self.assertTrue(any(canvas[-1]))
        self.assertFalse(any(any(row) for row in text_canvas(" ", fill_height=True)))

    def test_multicolor_icon_and_independent_text_survive_wire_encoding(self):
        cyan = (0, 200, 255)
        canvas = rgb_content_canvas("22.5°", "color-sun", font="digits3x8", text_color=cyan)
        colors = {pixel for row in canvas for pixel in row}
        self.assertTrue({(255, 190, 0), (255, 255, 255), cyan, (0, 0, 0)} <= colors)
        rgb = wire_pixels(canvas, count=256, layout="columns-serpentine")
        grb = wire_pixels(canvas, count=256, layout="columns-serpentine", channel_order="GRB")
        self.assertEqual(grb, [(g, r, b) for r, g, b in rgb])
        self.assertEqual(rgb[3 * 8], (255, 190, 0))
        for image in load_color_icons().values():
            self.assertEqual(len(image), 8)
            self.assertTrue(all(len(row) == 8 for row in image))

    def test_explicit_icon_tint_and_invalid_rgb(self):
        canvas = rgb_content_canvas("CIAO", "color-cloud", font="spleen5x8",
                                    text_color=(0, 255, 0), icon_color=(255, 0, 0), fill_height=True)
        self.assertEqual({pixel for row in canvas for pixel in row[:8]}, {(0, 0, 0), (255, 0, 0)})
        self.assertTrue(any((0, 255, 0) in row[9:] for row in canvas))
        with self.assertRaises(ValueError):
            rgb_content_canvas("1", text_color=(256, 0, 0))
        with self.assertRaises(ValueError):
            wire_pixels([[(1, 2)]])

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
