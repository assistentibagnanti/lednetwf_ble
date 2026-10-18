"""Small dependency-free 5x7 text renderer and matrix-to-wire mapping."""
from matrix_smear import pixel_index

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


def text_canvas(text, width=32, height=8):
    """Render centered static text; reject overflow instead of truncating it."""
    text = text.upper()
    if not text or height < 7 or width < 1:
        raise ValueError("Text must be nonempty and canvas height at least 7")
    if len(text) * 6 - 1 > width:
        raise ValueError(f"Text is too wide ({len(text) * 6 - 1} pixels) for {width}; use at most {(width + 1) // 6} characters")
    if any(char not in FONT for char in text):
        raise ValueError("Unsupported character; use A-Z, 0-9, space, . : - + ° % /")
    canvas = [[False] * width for _ in range(height)]
    left = (width - (len(text) * 6 - 1)) // 2
    top = (height - 7) // 2
    for index, char in enumerate(text):
        for x, column in enumerate(bytes.fromhex(FONT[char])):
            for y in range(7):
                canvas[top + y][left + index * 6 + x] = bool(column & (1 << y))
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
            if active:
                px, py = (width - 1 - x, height - 1 - y) if rotate else (x, y)
                pixels[pixel_index(px, py, width, height, layout)] = encoded
    return pixels


def ascii_preview(canvas):
    return "\n".join("".join("##" if p else "  " for p in row) for row in canvas)
