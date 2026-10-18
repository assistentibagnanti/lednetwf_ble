# Experimental A3 matrix probe

This diagnostic investigates `0x59` smear frames on an A3 controller.
The final calibrated result includes visually confirmed independent pixels,
32×8 text, columns-serpentine wiring and RGB colors. Earlier failed attempts below
are retained as experiment history; see the final section for the working setup. The diagnostic is not exposed through Home Assistant.

References:

- https://github.com/8none1/zengge_lednetwf#header
- https://github.com/8none1/zengge_lednetwf#smear
- https://github.com/lightinglibs/flux_led/blob/master/flux_led/protocol.py (`MusicMode`, addressable music commands)

The retired project documents pixel-wise RGB smear for a 48-LED controller and
explicitly leaves its other firmware variant undocumented. Its ten public forks
were checked: no additional smear implementation was found. Fifteen public forks
of lednetwf_ble were checked; differences in protocol/device code did not add A3
bitmap, text, or smear support. This search cannot establish hardware capability.

`matrix_smear.py` removes the old fixed 48-pixel lengths, encodes v0 fragmentation,
and provides four 2D wire mappings. Neither fragmentation for A3 smear nor the
matrix wiring has been confirmed on the target hardware. Offline tests verify
byte sizes, RGB order, captured short-query framing, and lossless reassembly.

## Probe

Use a separately stored backup from the read-only queries. The JSON must contain
`address` and raw `notifications` labelled `state_upload`, `symp_get_mic_info`, and
`get_symp_config_v2`. Backups and capture logs contain device addresses; keep them
outside the repository.

```bash
python tools/test_matrix_smear.py
python tools/matrix_probe.py --backup /path/to/backup.json --count 300
```

The second command is offline. `--count` is the **existing configured wire
capacity**, not a request to change it. For the investigated panel the advertised
physical matrix is 32×8, but the read-only controller response describes 30 pixels
per segment and 10 segments (300 capacity). Pad the frame with black; do not
rewrite the LED hardware configuration to reconcile these two values.

An explicit `--apply` enables the hardware test. It checks the exact original
microphone configuration, operating mode, and LED configuration before writing.
It tries a static black frame with one red pixel at 20% brightness for four
seconds, then reapplies all captured microphone parameters in a `finally` block.
It checks the microphone, mode and LED configuration against the backup after
restoration and logs both directions. A lost connection or process/host failure
can prevent the restore; keep the original app or remote available.

```bash
python tools/matrix_probe.py --backup /path/to/backup.json --count 300 \
  --pixel 0 --log-dir /path/to/captures --apply
```

Receiving a GATT acknowledgement or unchanged state is **not** proof of pixel
support. A person must confirm the single red pixel on the panel. If the device
ignores the command, do not enable this feature in Home Assistant or call it
supported. Text rendering should follow only after this check and wire mapping.

## First A3 hardware attempt (2026-10-18)

A 906-byte static RGB frame (300 configured positions, one red pixel) was sent
using six v0 transport fragments at a conservative 180-byte write limit. The
controller still reported mode `0x62` (sound reactive) during the test. No smear
acknowledgement or state transition was observed, so pixel control is **not
confirmed** and the command may have been ignored. Visual confirmation is pending.
The exact microphone parameters, operating mode/effect and LED configuration were
successfully restored and read back. Do not infer that packet delivery establishes
compatibility. Next evidence should be an app capture of DIY drawing on this A3,
or a verified A3-specific command format, before trying additional opcodes.

## Follow-up full-frame attempts

Two further attempts sent 300 RGB positions all red for five seconds, then all
green for five seconds. The first left the microphone enabled. The second first
disabled it by changing only the enable byte in the captured microphone settings;
a readback confirmed the microphone was disabled before sending any smear data.
The user confirmed **no visible color change in either attempt**. The reported
mode stayed `0x62`. All captured microphone parameters and LED settings matched
the original backup after restoration in both attempts.

Thus this legacy smear sequence has failed on the tested A3. This is not evidence
that all per-pixel control is impossible: the opcode, A3 data layout, or transport
fragmentation may differ. Do not advertise text or drawing support based on this
tool. The next useful evidence is a capture of DIY drawing from a compatible
vendor app on the actual A3. Avoid further undocumented command guesses.

The diagnostic offers `--solid-cycle --seconds 5` for visibility and
`--pause-mic` to test the prerequisite used by the integration's color/effect
methods. Both options retain automatic restoration and readback checks.

## A3-specific evidence found in upstream issue comments

https://github.com/8none1/zengge_lednetwf/issues/6#issuecomment-1902776898

On 2024-01-21, contributor nummacway reported that controllers advertising as
LEDnetWF0200A3 use a different `0x59` layout. There is an extra two-byte word
before RGB data, matching transport header bytes 4–5. The tail has five bytes
before its checksum: two unknown bytes, mode, speed, direction. The original
issue reports smear failing on firmware `56.00A3.2D.02,V3` while other effects
work. This is directly relevant to the negative tests above.

The comment does not supply the two unknown tail values or a complete frame.
The legacy layout failed in the tests above. The A3-specific layout was then
implemented and tested as follows.

## Successful A3-layout test (2026-10-18)

`--variant a3-zero-tail --solid-cycle --seconds 5 --pause-mic` uses:

```
59 [total payload length, 2 bytes big endian] [RGB bytes for each position]
00 00 01 32 00 [checksum]
```

The two undocumented fields were explicitly tested as zero. The RGB intensity
was scaled to 20% in the RGB bytes themselves; the unknown tail fields were not
treated as brightness. For 300 configured positions this is a 909-byte payload,
sent in six v0 fragments with a conservative 180-byte write limit. The first
transport header's total length equals the two-byte word following `59`.

The controller changed reported mode from `0x62` to `0x24`. The user visually
confirmed two full-panel colors for five seconds each. All microphone parameters,
operating mode/effect and LED configuration matched the original backup after
automatic restoration.

The requested order was red, then green; the user reported green, then red. R/G
channel order must therefore be checked, rather than silently changing hardware
color-order settings. A uniform frame does not establish individual addressability
or 2D wiring. Next validation: sparse patterns and the 32×8 coordinate map before
implementing text rendering. Do not generalize this result to every A3 firmware.


## Calibrated independent drawing and text (2026-10-18)

The original `0x63` response was `0063001e000a01001e0ab4`, describing normal
30×10 segments with a separate 30×10 music configuration. A single white pixel
was repeated at multiple physical locations. Temporarily using normal 256×1
segments fixes independent drawing while retaining the music fields:

- Temporary command: `620100000101001e0af07d`
- Verified temporary response: `00630100000101001e0a8e`
- Original restore command: `62001e000a01001e0af0a3`

The temporary A3 frame has 256 RGB positions, 777 payload bytes, and the same
A3 layout described above. Both 180-byte and 20-byte write fragmentation have
been used successfully. The user confirmed index 0 top-left and index 1 directly
below, then confirmed an eight-position boundary test through index 255.
Finally, `1234` was perfectly legible with `columns-serpentine`, and the later
three-color test confirmed RGB byte order. These later visual confirmations
supersede the initial uncertain red/green ordering observation.

The controller can restart Bluetooth after a `0x62` configuration write.
`matrix_restore.py` uses fresh connections after such writes, then checks exact
LED configuration, exact microphone parameters, and the saved mode/effect.
Underpowered USB caused flicker and connection failures; the user resolved this
by switching to a power bank. Successful recovery and subsequent tests were
confirmed afterward.

`--keep-drawing` deliberately retains the temporary configuration and paused
microphone between tests, as requested by the user. A subsequent invocation
accepts only the original state or the exact expected retained drawing state.
Final restoration remains a separate explicit command in this workflow.

See [MATRIX_A3.md](../tools/MATRIX_A3.md) for commands and the bundled fonts and
8×8 icons. New assets have offline tests and a local preview; their appearance on
the physical panel is not yet visually confirmed. The existing 5×7 font is
visually confirmed. This branch is still not a Home Assistant display entity.
