"""Generate an SVG contact sheet of the bundled assets, without Bluetooth."""
import argparse
from html import escape
from pathlib import Path

from matrix_assets import ASSETS, load_icons, load_color_icons
from matrix_canvas import rgb_content_canvas, text_canvas


def gallery():
    parts = []

    def label(x, y, value, size=15):
        parts.append(f'<text x="{x}" y="{y}" fill="#d9e5ef" font-family="sans-serif" font-size="{size}">{escape(value)}</text>')

    def bitmap(canvas, x, y, scale=4):
        for yy, row in enumerate(canvas):
            for xx, active in enumerate(row):
                if isinstance(active, (tuple, list)):
                    color = '#%02x%02x%02x' % tuple(active) if any(active) else '#263343'
                else:
                    color = '#72efb6' if active else '#263343'
                parts.append(f'<rect x="{x+xx*scale}" y="{y+yy*scale}" width="{scale-0.5}" height="{scale-0.5}" fill="{color}"/>')

    label(24, 32, "32 × 8 LED matrix · bundled fonts and icons", 21)
    examples = [("digits3x8", "12:34:56", "8 characters; native full-height digits", False),
                ("spleen5x8", "CIAO12", "6 characters; expanded to full height", True),
                ("classic5x7", "CIAO", "5 characters; expanded to full height", True),
                ("tom-thumb", "CIAO1234", "8 characters; narrow letters expanded to full height", True),
                ("font8x8", "CIAO", "4 characters", False)]
    for i, (font, sample, note, fill) in enumerate(examples):
        y = 70 + i * 68
        label(24, y, f"{font} — {note}")
        bitmap(text_canvas(sample, font=font, fill_height=fill), 24, y + 10)
    label(24, 430, "Yellow + white sun, cyan full-height digits")
    bitmap(rgb_content_canvas("22.5°", "color-sun", font="digits3x8", text_color=(0,200,255)), 24, 442)
    label(24, 510, "White + blue cloud, green full-height letters")
    bitmap(rgb_content_canvas("CIAO", "color-cloud", font="spleen5x8", text_color=(0,255,80), fill_height=True), 24, 522)
    label(24, 590, "8 × 8 icons · colored alternatives first", 18)
    icons = load_icons()
    names = sorted(icons, key=lambda name: (not name.startswith('color-'), name))
    for i, name in enumerate(names):
        x, y = 24 + (i % 6) * 112, 610 + (i // 6) * 70
        rows = load_color_icons().get(name) or [[bool(value & (1 << xx)) for xx in range(8)] for value in icons[name]]
        bitmap(rows, x, y)
        label(x, y + 48, name, 12)
    height = 630 + ((len(icons) + 5) // 6) * 70
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="720" height="{height}" viewBox="0 0 720 {height}">'
            f'<rect width="720" height="{height}" fill="#121c28"/>' + "".join(parts) + '</svg>\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ASSETS / "preview.svg")
    args = parser.parse_args()
    args.output.write_text(gallery())
    print(args.output)
