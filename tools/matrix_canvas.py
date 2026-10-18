"""Small dependency-free 5x7 text renderer and matrix-to-wire mapping."""
from matrix_smear import pixel_index
from matrix_assets import BitmapFont, FONT_NAMES, load_font, load_icons, load_color_icons

# Five vertical columns per glyph, low bit at the top. Lowercase uses capitals.
FONT = {
    " ": "0000000000", "0": "3e5149453e", "1": "00427f4000",
    "2": "4261514946", "3": "2141454b31", "4": "1814127f10",
    "5": "2745454539", "6": "3c4a494930", "7": "0171090503",
    "8": "3649494936", "9": "064949291e", "A": "7e1111117e",
    "B": "7f49494936", "C": "3e41414122", "D": "7f4141221c",
    "E": "7f49494941", "F": "7f09090901", "G": "3e41495172",
    "H": "7f0808087f", "I": "00417f4100", "J": "2040413f01",
    "K": "7f08142241", "L": "7f40404040", "M": "7f020c027f",
    "N": "7f0408107f", "O": "3e4141413e", "P": "7f09090906",
    "Q": "3e4151215e", "R": "7f09192946", "S": "4649494931",
    "T": "01017f0101", "U": "3f4040403f", "V": "1f2040201f",
    "W": "3f4038403f", "X": "6314081463", "Y": "0708700807",
    "Z": "6151494543", ".": "0060600000", ":": "0036360000",
    "-": "0808080808", "+": "08083e0808", "°": "0609090600",
    "%": "2313086462", "/": "2010080402",
}
LAYOUTS = ("rows", "rows-serpentine", "columns", "columns-serpentine")
CHANNEL_ORDERS = ("RGB", "RBG", "GRB", "GBR", "BRG", "BGR")


def text_canvas(text, width=32, height=8, font="classic5x7", fill_height=False):
    """Render centered static text; reject overflow instead of truncating it."""
    if font == "classic5x7":
        text = text.upper()
        glyphs = {char: tuple(sum(((column >> y) & 1) << x
                                  for x, column in enumerate(bytes.fromhex(value)))
                              for y in range(7)) for char, value in FONT.items()}
        face = BitmapFont(5, 7, 6, glyphs)
    else:
        face = load_font(font)
    if not text or height < face.height or width < 1:
        raise ValueError(f"Text must be nonempty and canvas height at least {face.height}")
    text_width = (len(text) - 1) * face.advance + face.width
    if text_width > width:
        raise ValueError(f"Text is too wide ({text_width} pixels) for {width} with {font}")
    missing = sorted(set(text) - face.glyphs.keys())
    if missing:
        raise ValueError(f"Unsupported characters for {font}: {''.join(missing)!r}")
    canvas = [[False] * width for _ in range(height)]
    left = (width - text_width) // 2
    top = (height - face.height) // 2
    for index, char in enumerate(text):
        for y, row in enumerate(face.glyphs[char]):
            for x in range(face.width):
                canvas[top + y][left + index * face.advance + x] = bool(row & (1 << x))
    if fill_height:
        occupied = [y for y, row in enumerate(canvas) if any(row)]
        if occupied:
            start, end = occupied[0], occupied[-1] + 1
            canvas = [canvas[start + y * (end - start) // height][:] for y in range(height)]
    return canvas


def content_canvas(text=None, icon=None, width=32, height=8, font="classic5x7", fill_height=False):
    """Combine an 8x8 icon at the left and centered text in the remaining area."""
    if icon is None:
        return text_canvas(text, width, height, font, fill_height)
    icons = load_icons()
    if icon not in icons or width < 8 or height < 8:
        raise ValueError("Unknown icon or canvas too small for an 8x8 icon")
    canvas = [[False] * width for _ in range(height)]
    left = 0 if text else (width - 8) // 2
    top = (height - 8) // 2
    for y, row in enumerate(icons[icon]):
        for x in range(8):
            canvas[top + y][left + x] = bool(row & (1 << x))
    if text:
        rendered = text_canvas(text, width - 9, height, font, fill_height)
        for y, row in enumerate(rendered):
            canvas[y][9:] = row
    return canvas


def rgb_content_canvas(text=None, icon=None, width=32, height=8, font="classic5x7",
                       text_color=(255, 255, 255), icon_color=None, fill_height=False):
    for color in (text_color, icon_color):
        if color is not None and (len(color) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in color)):
            raise ValueError("Colors must contain three RGB bytes")
    mask = content_canvas(text, icon, width, height, font, fill_height)
    canvas = [[tuple(text_color) if active else (0, 0, 0) for active in row] for row in mask]
    if icon:
        left, top = (0 if text else (width - 8) // 2), (height - 8) // 2
        image = load_color_icons().get(icon) if icon_color is None else None
        for y in range(8):
            for x in range(8):
                canvas[top + y][left + x] = (image[y][x] if image is not None else
                    tuple(icon_color or text_color) if mask[top + y][left + x] else (0, 0, 0))
    return canvas


def wire_pixels(canvas, count=300, layout="rows-serpentine", color=(255, 255, 255),
                channel_order="RGB", rotate=False):
    """Map a bitmap to the wire; pad unused configured positions with black.

    channel_order is the order of semantic RGB bytes sent over BLE, independent
    from the persistent hardware configuration, which this tool never rewrites.
    """
    if not canvas or not canvas[0] or any(len(row) != len(canvas[0]) for row in canvas):
        raise ValueError("Canvas must be a nonempty rectangle")
    height, width = len(canvas), len(canvas[0])
    if count < width * height:
        raise ValueError("Configured wire capacity is smaller than matrix area")
    if channel_order not in CHANNEL_ORDERS or layout not in LAYOUTS:
        raise ValueError("Invalid layout or channel order")
    if len(color) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in color):
        raise ValueError("Color must contain three RGB bytes")
    encoded = tuple(color["RGB".index(c)] for c in channel_order)
    pixels = [(0, 0, 0)] * count
    for y, row in enumerate(canvas):
        for x, active in enumerate(row):
            if isinstance(active, (tuple, list)):
                if len(active) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in active):
                    raise ValueError("RGB canvas pixels must contain three bytes")
                value = tuple(active["RGB".index(c)] for c in channel_order)
            else:
                value = encoded if active else (0, 0, 0)
            if any(value):
                px, py = (width - 1 - x, height - 1 - y) if rotate else (x, y)
                pixels[pixel_index(px, py, width, height, layout)] = value
    return pixels


def ascii_preview(canvas):
    return "\n".join("".join("##" if (any(p) if isinstance(p, (tuple, list)) else p) else "  " for p in row) for row in canvas)
