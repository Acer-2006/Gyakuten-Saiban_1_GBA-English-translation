#!/usr/bin/env python3
"""Build English evidence/profile description images (160x64) for the GBA
Court Record from the DS English name plates and info panels.
Writes the PNGs in place under graphics/evidence_profile_descriptions/."""
import os, re, sys, hashlib
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from dsdata import info_panel, name_plate
ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
src = open(os.path.join(ROOT, 'src/court_record.c')).read()
table = re.findall(r'\.descriptionTiles = (\w+),', src)
gs = open(os.path.join(ROOT, 'data/graphics.s')).read()
sym2file = dict(re.findall(r'\.global (gGfx\w+_description)\n\w+:\n\s*\.incbin "([^"]+)\.4bpp\.lz"', gs))

BG, TEXT, NAME = 9, 8, 15
DS_TEXT, DS_NAME_TEXT = 2, 2
DUMMY = {41, 70, 107}            # unused entries ("ダミー" in both versions)

# The DS English name plates are stored once per distinct name, in order of
# first appearance in this table. Recover that order from the original
# (Japanese) name lines, which repeat for every variant of an entry.
def name_order():
    seen, out = {}, []
    for sym in table:
        path = os.path.join(ROOT, sym2file[sym] + '.png')
        orig = path + '.orig' if os.path.exists(path + '.orig') else path
        top = np.array(Image.open(orig).convert('RGB'))[0:16].tobytes()
        h = hashlib.md5(top).hexdigest()
        if h not in seen:
            seen[h] = len(seen)
        out.append(seen[h])
    return out

def build(i, name_idx):
    path = os.path.join(ROOT, sym2file[table[i]] + '.png')
    if not os.path.exists(path + '.orig'):
        os.rename(path, path + '.orig')
    base = Image.open(path + '.orig')
    pal = base.getpalette()
    a = np.array(base).copy()
    a[:, :152] = BG
    if i not in DUMMY:
        n = np.array(name_plate(name_idx))
        cols = np.where((n == DS_NAME_TEXT).any(0))[0]
        if len(cols):
            w = cols[-1] - cols[0] + 1
            x0 = (152 - w) // 2
            for y in range(16):
                for x in range(w):
                    if n[y, cols[0] + x] == DS_NAME_TEXT:
                        a[y, x0 + x] = NAME
        p = np.array(info_panel(i))
        for k in range(3):
            band = p[3 + 15 * k: 3 + 15 * k + 15]
            for y in range(band.shape[0]):
                for x in range(128):
                    if band[y, x] == DS_TEXT:
                        a[17 + 16 * k + y - 1, 2 + x] = TEXT
    out = Image.fromarray(a, 'P'); out.putpalette(pal)
    out.save(path)

if __name__ == '__main__':
    order = name_order()
    for i in range(len(table)):
        build(i, order[i])
    print('built', len(table), 'descriptions;', len(set(order)), 'distinct names')
