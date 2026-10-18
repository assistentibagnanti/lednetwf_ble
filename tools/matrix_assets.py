"""Local bitmap assets. Read source data without executing upstream code."""
import ast
import base64
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

ASSETS = Path(__file__).with_name("assets")
FONT_NAMES = ("classic5x7", "tom-thumb", "font8x8", "spleen5x8", "digits3x8")


@dataclass(frozen=True)
class BitmapFont:
    width: int
    height: int
    advance: int
    glyphs: dict


@lru_cache
def load_font(name):
    if name == "digits3x8":
        source = (ASSETS / "upstream/EspruinoDocs/modules/Font4x8Numeric.js").read_text()
        data = base64.b64decode(re.search(r'atob\("([A-Za-z0-9+/=]+)"\)', source)[1], validate=True)
        if len(data) != 40:
            raise ValueError("Invalid bundled numeric font")
        glyphs = {str(i): tuple(sum(((data[i * 4 + x] >> (7 - y)) & 1) << x
                                    for x in range(3)) for y in range(8))
                  for i in range(10)}
        # Original punctuation added for time and temperature readouts.
        glyphs.update({" ": (0,) * 8, ".": (0,0,0,0,0,0,0,2),
                       ":": (0,2,2,0,0,2,2,0), "-": (0,0,0,7,0,0,0,0),
                       "°": (7,5,7,0,0,0,0,0)})
        return BitmapFont(3, 8, 4, glyphs)
    if name == "font8x8":
        glyphs = {}
        for filename in ("font8x8_basic.h", "font8x8_ext_latin.h"):
            source = (ASSETS / "upstream/font8x8" / filename).read_text()
            start = 0 if filename == "font8x8_basic.h" else 160
            rows = re.findall(r"^\s*\{\s*([0-9xXa-fA-F, \t]+)\}", source, re.M)
            if len(rows) != (128 if start == 0 else 96):
                raise ValueError("Incomplete bundled font8x8 array")
            # Index by C array order: upstream repeats U+00B2 in two comments.
            for code, row in enumerate(rows, start):
                values = [int(value, 16) for value in re.findall(r"0x[0-9A-Fa-f]+", row)]
                if len(values) != 8:
                    raise ValueError("Invalid bundled font8x8 row")
                if code >= 32:
                    glyphs[chr(code)] = tuple(values)
        return BitmapFont(8, 8, 8, glyphs)
    if name in ("tom-thumb", "spleen5x8"):
        source = (ASSETS / ("upstream/tom-thumb.bdf" if name == "tom-thumb" else
                           "upstream/spleen/spleen-5x8.bdf")).read_text()
        width, height, _, bottom = map(int, re.search(r"^FONTBOUNDINGBOX (.*)$", source, re.M)[1].split())
        glyphs = {}
        for block in re.findall(r"STARTCHAR .*?\n(.*?)ENDCHAR", source, re.S):
            code = int(re.search(r"^ENCODING (-?\d+)$", block, re.M)[1])
            if code < 0:
                continue
            w, h, dx, dy = map(int, re.search(r"^BBX (.*)$", block, re.M)[1].split())
            bitmap = block.split("BITMAP\n", 1)[1].splitlines()
            rows = [0] * height
            for y, value in enumerate(bitmap):
                bits = int(value, 16)
                for x in range(w):
                    if bits & (1 << (((w + 7) // 8) * 8 - 1 - x)):
                        px, py = dx + x, height + bottom - (dy + h) + y
                        if not (0 <= px < width and 0 <= py < height):
                            raise ValueError("Bundled BDF glyph exceeds its cell")
                        rows[py] |= 1 << px
            glyphs[chr(code)] = tuple(rows)
        return BitmapFont(width, height, 4 if name == "tom-thumb" else 5, glyphs)
    raise ValueError(f"Unknown external font: {name}")


@lru_cache
def load_icons():
    source = (ASSETS / "upstream/rpi-weather/led8x8icons.py").read_text()
    # literal_eval accepts the dictionary data only; never import upstream code.
    values = ast.literal_eval(source.split("LED8x8ICONS =", 1)[1].strip())
    icons = {name.lower(): tuple((value >> (8 * y)) & 255 for y in range(8))
             for name, value in values.items() if name}
    icons.update({name: tuple(sum(bool(any(pixel)) << x for x, pixel in enumerate(row))
                                   for row in image) for name, image in load_color_icons().items()})
    return icons


@lru_cache
def load_color_icons():
    """Native RGB sprites; original sun, colorized Open Iconic silhouettes."""
    shapes = json.loads((ASSETS / "open-iconic-8x8.json").read_text())
    images = {}
    for name, shape in shapes.items():
        image = []
        for y, row in enumerate(shape):
            pixels = []
            for x, bit in enumerate(row):
                color = (0, 0, 0)
                if bit == "#":
                    if name == "sun":
                        color = (255, 255, 255) if 2 <= x <= 5 and 2 <= y <= 5 else (255, 190, 0)
                    elif name == "rain":
                        color = (0, 150, 255) if y >= 5 else (255, 255, 255)
                    elif name == "moon":
                        color = (255, 230, 150) if x < 2 else (255, 255, 255)
                    else:
                        color = (255, 255, 255) if y < 5 else (130, 170, 220)
                pixels.append(color)
            image.append(pixels)
        images["color-" + name] = image
    # Original full-height sun: yellow rays with a white center.
    sun = ("...YY...", ".Y.YY.Y.", "..YYYY..", "YYWWWWYY",
           "YYWWWWYY", "..YYYY..", ".Y.YY.Y.", "...YY...")
    palette = {".": (0, 0, 0), "Y": (255, 190, 0), "W": (255, 255, 255)}
    images["color-sun"] = [[palette[bit] for bit in row] for row in sun]
    return images
