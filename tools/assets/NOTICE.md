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
