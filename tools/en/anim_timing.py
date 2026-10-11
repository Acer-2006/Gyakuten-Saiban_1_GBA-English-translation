#!/usr/bin/env python3
"""anim_timing.py : frame timings of GBA person animations set to the DS's.

Only the number of frames a picture is held changes; the pictures are the
GBA's own. Each entry: animation file, offset of the animation in it, frame
number, GBA duration, DS duration (measured in DeSmuME, English DS ROM).
Running it again changes nothing."""
import os, struct
ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
FIXES = [
    # Redd White's sparkly hands (GBA 0x1C58 = DS 15:a7): the second picture
    # is held 7 frames on the DS, 6 on the GBA
    ('graphics/animations/characters/animation08.seq', 0x1C58, 1, 6, 7),
]
for path, anim, frame, old, new in FIXES:
    p = os.path.join(ROOT, path)
    b = bytearray(open(p, 'rb').read())
    at = anim + 8 + 8 * frame + 2      # 8-byte header, then 8 bytes a frame (u16 picture, u8 duration, ...)
    if b[at] == new:
        continue
    assert b[at] == old, (path, hex(anim), frame, b[at])
    b[at] = new
    open(p, 'wb').write(bytes(b))
    print('%s %#x frame %d: %d -> %d frames' % (path, anim, frame, old, new))
