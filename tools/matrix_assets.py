"""Local bitmap assets. Read source data without executing upstream code."""
import ast
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

ASSETS = Path(__file__).with_name("assets")
FONT_NAMES = ("classic5x7", "tom-thumb", "font8x8")


@dataclass(frozen=True)
class BitmapFont:
    width: int
    height: int
    advance: int
    glyphs: dict


@lru_cache
def load_font(name):
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
    if name == "tom-thumb":
        source = (ASSETS / "upstream/tom-thumb.bdf").read_text()
        glyphs = {}
        for block in re.findall(r"STARTCHAR .*?\n(.*?)ENDCHAR", source, re.S):
            code = int(re.search(r"^ENCODING (\d+)$", block, re.M)[1])
            w, h, dx, dy = map(int, re.search(r"^BBX (.*)$", block, re.M)[1].split())
            bitmap = block.split("BITMAP\n", 1)[1].splitlines()
            rows = [0] * 6
            for y, value in enumerate(bitmap):
                bits = int(value, 16)
                for x in range(w):
                    if bits & (1 << (((w + 7) // 8) * 8 - 1 - x)):
                        px, py = dx + x, 5 - (dy + h) + y
                        if not (0 <= px < 3 and 0 <= py < 6):
                            raise ValueError("Bundled BDF glyph exceeds its cell")
                        rows[py] |= 1 << px
            glyphs[chr(code)] = tuple(rows)
        return BitmapFont(3, 6, 4, glyphs)
    raise ValueError(f"Unknown external font: {name}")


@lru_cache
def load_icons():
    source = (ASSETS / "upstream/rpi-weather/led8x8icons.py").read_text()
    # literal_eval accepts the dictionary data only; never import upstream code.
    values = ast.literal_eval(source.split("LED8x8ICONS =", 1)[1].strip())
    return {name.lower(): tuple((value >> (8 * y)) & 255 for y in range(8))
            for name, value in values.items() if name}
