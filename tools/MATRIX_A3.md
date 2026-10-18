# A3 matrix display tools

This branch extends the working A3 `0x59` frame format with a small 5×7 bitmap
font, configurable 32×8 matrix wiring, and software color-order correction.
No LED count, chip type, segment count or persistent color-order setting is
changed. The frame keeps the existing 300-position configured capacity, with
unused positions black. The physical matrix is described as 256 pixels.

## Verified and pending

- A3 full-frame red/green changes are visually confirmed on the target hardware.
- Original microphone parameters and hardware configuration are read back and
  verified after automatic restoration.
- Text rendering, coordinate mapping, padding, channel reordering and transport
  framing pass offline tests.
- The four-layout `1234` hardware calibration has been run; visual selection is
  needed before declaring a wiring layout correct.
- The reported order of the red/green test was reversed. `--channel-order GRB`
  can compensate without changing device settings, but first check the channel
  order visually. White calibration text avoids this ambiguity.

## Setup

Use a Python virtual environment with `bleak` installed. Keep the captured
read-only backup outside the repository. See
[`19_experimental_matrix_probe.md`](../protocol_docs/19_experimental_matrix_probe.md)
for its schema and protocol evidence.

From the repository directory, run offline tests:

```bash
python -m unittest discover -s tools -p 'test_matrix*.py'
```

Preview the bitmap in the terminal (no Bluetooth access):

```bash
python tools/matrix_probe.py --backup /path/to/backup.json \
  --variant a3-zero-tail --text '22.5°'
```

Display a message for five seconds, then return to the original microphone effect:

```bash
python tools/matrix_probe.py --backup /path/to/backup.json \
  --count 300 --variant a3-zero-tail --pause-mic \
  --text CIAO --layout rows-serpentine --seconds 5 \
  --log-dir /path/to/captures --apply
```

The layout in that example is a candidate, not a verified default for every
panel. To find the actual wiring, use `--text 1234 --layout-cycle`: each of
`rows`, `rows-serpentine`, `columns`, `columns-serpentine` appears for the chosen
number of seconds. If the readable text is upside down, repeat its layout with
`--rotate` (180°).

Supported characters: A–Z (lowercase converted to uppercase), digits, spaces,
`. : - + ° % /`. A fixed 32-pixel width fits at most five glyphs, including spaces
and punctuation. Longer input is rejected before connecting; text is never
silently cut. Scrolling is not implemented.

Use `--color 255 0 0` for red text and `--channel-order GRB` only if the visual
channel test establishes that red and green are swapped. RGB values in A3 frames
are scaled to 20% intensity. Unused matrix pixels and capacity padding are black.

The tool checks the saved microphone, mode and hardware configuration before
writing. If someone has changed the settings since the backup it aborts. It
restores the captured microphone settings after the timed display, including on
ordinary exceptions, then compares the readback. A process/host failure or a lost
Bluetooth connection can prevent restoration; the backup remains available.

These are diagnostic tools on a feature branch, not a Home Assistant text entity.
Once wire mapping and sparse text are visually confirmed, the same renderer and
encoder can be connected to a Home Assistant service.
