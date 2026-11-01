#!/usr/bin/env python3
"""A Court Record description picture (160x72, 4bpp indexed PNG) as tiles in
the order the Court Record's sprites take them (court_record.c,
UpdateEvidenceSprites):

  rows 0-63    a 64x64 sprite (columns 0-63), a 64x64 sprite (64-127) and a
               32x64 sprite (128-159), each one's tiles row by row
  rows 64-71   five 32x8 sprites (columns 0-31, 32-63, ...), 4 tiles each

180 tiles in all. The last three rows are the panel's bottom border (drawn
by make_descriptions.py), so the strip sprites and the copy of them the
window slides away on BG2 (bg.c) both show it.

usage: desc_tiles.py IN.png OUT.4bpp"""
import sys
import numpy as np
from PIL import Image

W, H = 160, 72
SPRITES = ((0, 0, 8, 8), (64, 0, 8, 8), (128, 0, 4, 8)) + \
          tuple((32 * k, 64, 4, 1) for k in range(5))     # (x, y, tiles across, tiles down)

def tiles(a):
    out = bytearray()
    for x0, y0, tw, th in SPRITES:
        for ty in range(th):
            for tx in range(tw):
                t = a[y0 + ty * 8:y0 + ty * 8 + 8, x0 + tx * 8:x0 + tx * 8 + 8]
                out += bytes((t[:, 0::2] | (t[:, 1::2] << 4)).astype(np.uint8).flatten())
    return bytes(out)

if __name__ == '__main__':
    im = Image.open(sys.argv[1])
    assert im.mode == 'P' and im.size == (W, H), '%s: %s %s, not a %dx%d indexed picture' % (sys.argv[1], im.mode, im.size, W, H)
    a = np.array(im)
    assert a.max() < 16
    open(sys.argv[2], 'wb').write(tiles(a))
