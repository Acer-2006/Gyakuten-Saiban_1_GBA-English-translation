"""Read the English text out of the DS pre-rendered Court Record bitmaps.

The DS stores each evidence/profile description as a 256x64 bitmap and the
"Age: NN" line inside the 128x64 info panels. Glyphs are separated by blank
columns, so each line is cut into glyphs and every glyph is matched exactly
against labelled templates (desc_font_labels.json / info_font_labels.json).
Nothing is guessed: an unknown glyph raises an error."""
import os, sys, json, struct, hashlib
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from dsdata import data, info_panel

HERE = os.path.dirname(__file__)
EN_DESC_FIRST = 0x2b62684     # first of 176 uncompressed description bitmaps
EN_DESC_STRIDE = 0x2034       # 0x14 header + 0x2000 bitmap + 0x20 palette
DESC_HEADER = bytes.fromhex('0305030014000000002000001420000020000000')

def glyph_key(g):
    return hashlib.sha1(bytes([g.shape[1]]) + np.packbits(g).tobytes()).hexdigest()[:16]

def segments(band):
    cols = np.where(band.any(0))[0]
    if not len(cols):
        return []
    out, s, p = [], cols[0], cols[0]
    for c in cols[1:]:
        if c != p + 1:
            out.append((s, p)); s = c
        p = c
    out.append((s, p))
    return out

def read_line(band, labels, space_gap):
    text, prev = '', None
    for s, e in segments(band):
        g = band[:, s:e + 1]
        ch = labels.get(glyph_key(g))
        if ch is None:
            raise ValueError('unknown glyph at x=%d' % s)
        if prev is not None and s - prev - 1 >= space_gap:
            text += ' '
        text += ch
        prev = e
    return text

_dl = _il = None
def desc_bitmap(i):
    o = EN_DESC_FIRST + i * EN_DESC_STRIDE
    d = data()
    assert d[o:o + 20] == DESC_HEADER, 'unexpected description header at %#x' % o
    raw = np.frombuffer(d[o + 0x14:o + 0x2014], np.uint8)
    a = np.zeros(64 * 256, np.uint8)
    a[0::2] = raw & 15; a[1::2] = raw >> 4
    return a.reshape(64, 256)

def description(i):
    """-> list of the DS text lines of description i"""
    global _dl
    if _dl is None:
        _dl = json.load(open(os.path.join(HERE, 'desc_font_labels.json')))
    a = desc_bitmap(i) > 0
    lines = [read_line(a[k * 16:(k + 1) * 16], _dl, 7) for k in range(3)]
    while lines and not lines[-1]:
        lines.pop()
    return lines

def info_line(i, k=0):
    """-> text of line k of info panel i (k=0 holds 'Age: NN' or 'Type: ...')"""
    global _il
    if _il is None:
        _il = json.load(open(os.path.join(HERE, 'info_font_labels.json')))
    p = np.array(info_panel(i)) == 2
    return read_line(p[3 + 15 * k:18 + 15 * k], _il, 4)
