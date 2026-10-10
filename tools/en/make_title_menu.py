#!/usr/bin/env python3
"""English "New Game" / "Continue" title options drawn with the DS font,
in the same 64x32 sprite sheet and palette indices as the original."""
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
for row, label in ((0, 'New Game'), (1, 'Continue')):
    m = render(label, space=3)
    # pad by one pixel for the outline
    p = np.zeros((m.shape[0] + 2, m.shape[1] + 2), np.uint8); p[1:-1, 1:-1] = m
    o = outline(p)
    h, w = p.shape
    if w > 64: raise SystemExit('%s too wide (%d px)' % (label, w))
    x0 = (64 - w) // 2; y0 = row * 16 + (16 - h) // 2 + 1
    sub = a[y0:y0 + h, x0:x0 + w]
    sub[o] = 3
    sub[p.astype(bool)] = 1
img = Image.fromarray(a, 'P'); img.putpalette(tpl.getpalette()); img.save(path)
print('title menu written')
