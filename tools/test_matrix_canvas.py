import unittest

from matrix_canvas import LAYOUTS, text_canvas, wire_pixels


class MatrixCanvasTests(unittest.TestCase):
    def test_number_one_has_centered_vertical_stroke(self):
        canvas = text_canvas("1")
        self.assertEqual(len(canvas), 8)
        self.assertEqual(len(canvas[0]), 32)
        self.assertTrue(all(canvas[y][15] for y in range(7)))
        self.assertFalse(any(canvas[7]))
        self.assertTrue(all(not any(row[:13] + row[18:]) for row in canvas))

    def test_temperature_and_word_fit_without_clipping(self):
        for text in ("22.5°", "CIAO", "12:34", "-5°C"):
            canvas = text_canvas(text)
            self.assertTrue(any(any(row) for row in canvas))
        with self.assertRaises(ValueError):
            text_canvas("123456")
        with self.assertRaises(ValueError):
            text_canvas("È")

    def test_sparse_pixels_map_without_duplicates_or_padding_light(self):
        canvas = [[False] * 32 for _ in range(8)]
        canvas[0][0] = True
        canvas[1][0] = True
        expected = {"rows": {0, 32}, "rows-serpentine": {0, 63},
                    "columns": {0, 1}, "columns-serpentine": {0, 1}}
        for layout in LAYOUTS:
            pixels = wire_pixels(canvas, layout=layout)
            self.assertEqual({i for i, p in enumerate(pixels) if any(p)}, expected[layout])
            self.assertEqual(pixels[256:], [(0, 0, 0)] * 44)

    def test_color_swap_and_rotation_are_software_only(self):
        canvas = [[False] * 32 for _ in range(8)]
        canvas[0][0] = True
        pixels = wire_pixels(canvas, layout="rows", color=(255, 0, 0),
                             channel_order="GRB", rotate=True)
        self.assertEqual(pixels[255], (0, 255, 0))
        self.assertEqual(sum(any(pixel) for pixel in pixels), 1)

    def test_too_small_capacity_is_rejected(self):
        with self.assertRaises(ValueError):
            wire_pixels(text_canvas("CIAO"), count=255)


if __name__ == "__main__":
    unittest.main()
