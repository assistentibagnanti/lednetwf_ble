# Third-party bitmap assets

The original files are preserved under `upstream/`. `sources.json` records their
download URLs (Git commit pinned where available) and SHA-256 hashes. They are
read locally; using the renderer needs neither network access nor extra packages.

## font8x8 — public domain

Daniel Hepper, derived from Marcel Sondaar and IBM public domain VGA fonts.
Source: https://github.com/dhepper/font8x8
The original notices are in both headers and `upstream/font8x8/README`.
Includes basic Latin and extended Latin, including Italian accented letters and °.
Rows are stored least significant bit first, corresponding to the leftmost pixel.

## Tom Thumb — CC0 option

Robey Pointer, based on Brian Swetland's small monospace font.
Source and explicit license statement:
https://robey.lag.net/2010/01/23/tiny-monospace-font.html

The author's 2015 update permits this font under CC0 or CC BY 3.0 as alternatives
to the original MIT license. This distribution uses the CC0 option:
https://creativecommons.org/publicdomain/zero/1.0/
The BDF's original MIT property is preserved unchanged.
The active glyph width is 3 pixels with a 4-pixel advance; the 6-pixel-high cell
preserves descenders. Most capital letters and digits occupy 3×5 active pixels.

## rpi-weather 8×8 icons — MIT

Copyright (c) 2016 Carter Nelson.
Source: https://github.com/caternuson/rpi-weather
Full license: `upstream/rpi-weather/LICENSE` (retained in this distribution).
The upstream dictionary is parsed as literal data, never imported or executed.
Includes six weather patterns, digits, kanji digits, and diagnostic patterns.
`rain` is the original abstract rain pattern, not a newly drawn cloud icon.

The containing project's MIT license does not replace these source notices.

## Spleen 5×8 — BSD-2-Clause

Frédéric Cambus, https://github.com/fcambus/spleen.
The original BDF and full license are preserved in `upstream/spleen/`.
The 5-pixel cell includes spacing; six cells fit in a 32-pixel line.

## Espruino numeric font — MIT

Copyright (c) 2017 Gordon Williams, Pur3 Ltd.
Source: https://github.com/espruino/EspruinoDocs/blob/master/modules/Font4x8Numeric.js
Original code and license are in `upstream/EspruinoDocs/`.
Digits have three active columns, one spacing column, and eight active rows.
The added space, decimal point, colon, minus and degree glyphs are original
additions under this project's MIT license.

## Open Iconic silhouettes — MIT

Copyright (c) 2014 Waybury, https://github.com/iconic/open-iconic.
Native 8×8 PNGs and `ICON-LICENSE` are in `upstream/open-iconic/`.
`open-iconic-8x8.json` records their alpha masks (threshold >127), at original
resolution. Color cloud, rain and moon sprites use these masks with original
RGB palettes applied by `matrix_assets.py`. The full-height yellow/white sun
is an original sprite drawn directly in that module under the project's MIT
license. No third-party colored artwork is represented as an original design.
