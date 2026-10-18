# Experimental A3 matrix probe

This diagnostic investigates legacy `0x59` smear frames on an A3 controller.
It is **not confirmed A3 support**, and is not exposed through Home Assistant.

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

The tool currently implements the legacy layout, **not this A3 layout**. The
layout mismatch is a plausible explanation, not an experimentally proven cause.
The comment does not supply the two unknown tail values or a complete frame;
do not silently substitute the legacy brightness/speed values. A complete A3
capture or an independently verified implementation is still needed. No A3-layout
commands have been transmitted as part of this research.
