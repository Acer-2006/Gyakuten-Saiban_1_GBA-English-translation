#!/usr/bin/env python3
"""Backport the DS English choice-answer buttons.

The DS draws each answer as a 256x32 button image (archive at 0x263bf4c in the
US data.bin, 4bpp linear). We take just the anti-aliased English text from each
button and store it as a GBA sprite strip: 208x16 = six 32x16 sprites + one
16x16 sprite (52 tiles, 0x680 bytes), white text for the GBA choice window.

Also writes tools/en/choice_table.json: which buttons each choice shows, read
from the table the DS code uses (US arm9: keys at 0x020b4954, English button
ids at 0x020b52b4; 6-byte entries, 200 of them).

usage: make_choice_labels.py DS_arm9.bin"""
import os, sys, json, struct
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from dsdata import archive, entry
ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
EN_BTN = 0x263bf4c
W, H = 208, 16
SLOT = 0x680

def button(i):
    raw = entry(EN_BTN, i)
    body = np.frombuffer(raw[0x14:0x1014], dtype=np.uint8)
    return np.stack([body & 15, body >> 4], 1).flatten().reshape(32, 256)

def label(i):
    a = button(i)
    inner = a[6:26, 18:237].astype(int)
    ink = np.where(inner >= 4, inner - 3, 0)            # 0..12 darkness
    rows = np.where(ink.any(1))[0]; cols = np.where(ink.any(0))[0]
    if len(rows) == 0:
        return np.zeros((H, W), np.uint8)
    # 16-row window holding most of the ink
    top = rows[0]
    if rows[-1] - top + 1 > H:
        top = rows[-1] - H + 1 if ink[rows[-1]].sum() > ink[top].sum() else top
    ink = ink[top:top + H, cols[0]:cols[-1] + 1]
    if ink.shape[1] > W:                                 # squeeze the few widest labels
        x = np.linspace(0, ink.shape[1], W + 1)
        ink = np.stack([ink[:, int(x[k]):max(int(x[k]) + 1, int(x[k + 1]))].max(1) for k in range(W)], 1)
    out = np.zeros((H, W), np.uint8)
    out[:ink.shape[0], :ink.shape[1]] = ink
    # darkness -> GBA text palette: 3 white, 2 light grey, 1 dark grey
    pix = np.zeros_like(out)
    pix[out >= 9] = 3
    pix[(out >= 5) & (out < 9)] = 2
    pix[(out >= 2) & (out < 5)] = 1
    return pix

def to_tiles(pix):
    out = bytearray()
    def tile(x0, y0):
        t = bytearray()
        for y in range(8):
            for x in range(0, 8, 2):
                t.append(int(pix[y0 + y, x0 + x]) | int(pix[y0 + y, x0 + x + 1]) << 4)
        return t
    for b in range(6):                                   # 32x16 sprites
        for ty in range(2):
            for tx in range(4):
                out += tile(b * 32 + tx * 8, ty * 8)
    for ty in range(2):                                  # final 16x16 sprite
        for tx in range(2):
            out += tile(192 + tx * 8, ty * 8)
    assert len(out) == SLOT
    return out

if __name__ == '__main__':
    n = len(archive(EN_BTN))
    blob = bytearray()
    for i in range(n):
        blob += to_tiles(label(i))
    os.makedirs(os.path.join(ROOT, 'graphics/en'), exist_ok=True)
    open(os.path.join(ROOT, 'graphics/en/choice_labels.bin'), 'wb').write(blob)
    a9 = open(sys.argv[1], 'rb').read()
    table = []
    for k in range(200):
        sc, _, sec, layout, _ = struct.unpack_from('<BBHBB', a9, 0xb4954 + 6 * k)
        ids = list(struct.unpack_from('<3H', a9, 0xb52b4 + 6 * k))
        if sc == 255: continue
        table.append({'scenario': sc, 'ds_section': sec - 0x80, 'ids': ids})
    json.dump(table, open(os.path.join(os.path.dirname(__file__), 'choice_table.json'), 'w'), indent=0)
    print('labels', n, 'choices', len(table))
