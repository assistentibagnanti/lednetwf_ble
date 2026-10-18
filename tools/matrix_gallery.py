"""Generate an SVG contact sheet of the bundled assets, without Bluetooth."""
import argparse
from html import escape
from pathlib import Path

from matrix_assets import ASSETS, load_icons
from matrix_canvas import content_canvas, text_canvas


def gallery():
    parts = []

    def label(x, y, value, size=15):
        parts.append(f'<text x="{x}" y="{y}" fill="#d9e5ef" font-family="sans-serif" font-size="{size}">{escape(value)}</text>')

    def bitmap(canvas, x, y, scale=4):
        for yy, row in enumerate(canvas):
            for xx, active in enumerate(row):
                parts.append(f'<rect x="{x+xx*scale}" y="{y+yy*scale}" width="{scale-0.5}" height="{scale-0.5}" fill="{"#72efb6" if active else "#263343"}"/>')

    label(24, 32, "32 × 8 LED matrix · bundled fonts and icons", 21)
    examples = [("classic5x7", "22.5°", "5 characters; uppercase"),
                ("tom-thumb", "12:34:56", "8 characters; lowercase and accents"),
                ("font8x8", "Caff", "4 characters; lowercase and accents")]
    for i, (font, sample, note) in enumerate(examples):
        y = 70 + i * 68
        label(24, y, f"{font} — {note}")
        bitmap(text_canvas(sample, font=font), 24, y + 10)
    label(24, 282, "Combined: weather + temperature (Tom Thumb)")
    bitmap(content_canvas("22.5°", "sunny", font="tom-thumb"), 24, 294)
    label(24, 362, "8 × 8 icons (original rpi-weather data)", 18)
    icons = load_icons()
    for i, name in enumerate(icons):
        x, y = 24 + (i % 6) * 112, 382 + (i // 6) * 70
        rows = [[bool(value & (1 << xx)) for xx in range(8)] for value in icons[name]]
        bitmap(rows, x, y)
        label(x, y + 48, name, 12)
    height = 402 + ((len(icons) + 5) // 6) * 70
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="720" height="{height}" viewBox="0 0 720 {height}">'
            f'<rect width="720" height="{height}" fill="#121c28"/>' + "".join(parts) + '</svg>\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ASSETS / "preview.svg")
    args = parser.parse_args()
    args.output.write_text(gallery())
    print(args.output)
