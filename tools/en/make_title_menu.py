#!/usr/bin/env python3
"""English "New Game" / "Continue" title options drawn with the DS font,
in the same 64x32 sprite sheet and palette indices as the original.
The outline's corners are softened as in the GS2 English patch: an outline
pixel that touches a letter only diagonally takes colour 4, the grey each of
the menu's palettes has between the outline's colour and the black, except
the two the GS2 patch touched up back to the outline's colour (KEEP), and two
grey ones inside the G of "Game" that go, as in the GS3 patch (REMOVE). The
two gaps between the legs of the m of "Game" are filled with the outline, its
bottom pixel with the corners' grey, as in the GS3 patch's 0.16.83 (M_GAPS)."""
import os, sys, shutil
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from dsfont import render, outline
ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
path = os.path.join(ROOT, 'graphics/ui/new_game_continue.png')
if not os.path.exists(path + '.orig'):
    shutil.copy(path, path + '.orig')
tpl = Image.open(path + '.orig')
a = np.zeros((32, 64), np.uint8)
ROWS = 13                     # the labels' rows (no descenders): capitals from row 2
# corners that keep the outline's colour (x, y in the sheet), as in the GS2
# patch (V39): inside the "e" of "New" and inside the "G" of "Game"
KEEP = ((16, 11), (38, 7))
# grey corners that go (transparent), as in the GS3 patch: inside the "G" of
# "Game", where its curve meets the bar
REMOVE = ((32, 10), (33, 11))
# the m of "Game": its two gaps (columns 48 and 52, rows 9-14) filled, as in
# the GS3 patch's 0.16.83 (its sheet differs from this one in these 12 pixels
# only): the outline's colour, the corners' grey on the bottom row
M_GAPS = (48, 52)
M_ROWS = range(9, 15)
for row, label in ((0, 'New Game'), (1, 'Continue')):
    m = render(label, space=3)          # (word spaces of 3, as the title has had)
    assert not m[ROWS:].any()
    m = m[:ROWS]
    # pad by one pixel for the outline
    p = np.zeros((m.shape[0] + 2, m.shape[1] + 2), np.uint8); p[1:-1, 1:-1] = m
    o = outline(p)
    h, w = p.shape
    if w > 64: raise SystemExit('%s too wide (%d px)' % (label, w))
    x0 = (64 - w) // 2; y0 = row * 16 + (16 - h) // 2 + 1
    sub = a[y0:y0 + h, x0:x0 + w]
    # the outline's corners: no letter pixel above, below, left or right
    q = np.pad(p.astype(bool), 1)
    side = q[:-2, 1:-1] | q[2:, 1:-1] | q[1:-1, :-2] | q[1:-1, 2:]
    sub[o] = 3
    sub[o & ~side] = 4
    sub[p.astype(bool)] = 1
for x, y in KEEP:
    assert a[y, x] == 4
    a[y, x] = 3
for x, y in REMOVE:
    assert a[y, x] == 4
    a[y, x] = 0
for x in M_GAPS:
    assert a[M_ROWS[0], x] == 4 and not a[M_ROWS[1]:M_ROWS[-1] + 1, x].any()
    a[M_ROWS[0]:M_ROWS[-1], x] = 3
    a[M_ROWS[-1], x] = 4
img =Image.fromarray(a, 'P'); img.putpalette(tpl.getpalette()); img.save(path)
print('title menu written')
