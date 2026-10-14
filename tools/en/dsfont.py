"""Render English text with the DS English font, as the text box draws it
(graphics/vwf/font_*.bin, which make_vwf_font.py builds from the DS's own
font): each character's pixels drawn at the pen, the pen moving on by the
character's advance (its width and a pixel; 4 for a space)."""
import os
import numpy as np
HERE = os.path.dirname(__file__)
GLYPHS = open(os.path.join(HERE, '..', '..', 'graphics/vwf/font_glyphs.bin'), 'rb').read()
WIDTHS = open(os.path.join(HERE, '..', '..', 'graphics/vwf/font_widths.bin'), 'rb').read()     # columns with pixels
ADVANCE = open(os.path.join(HERE, '..', '..', 'graphics/vwf/font_advance.bin'), 'rb').read()   # the pen's move
ROWS = 16
SPACE = ADVANCE[0xFF]
PUNCT = {'.': 0xE1, ',': 0xEF, "'": 0xF3, ':': 0xED, '!': 0x3E, '?': 0x3F, '-': 0x100,
         '(': 0xE5, ')': 0xE6, '"': 0x101, '&': 0xFC, '/': 0xF1, '*': 0xF2, '+': 0xF0,
         '~': 0xF9, '%': 0xF7, ';': 0x10C, '[': 0x102, ']': 0x103, '#': 0x105}
def code(ch):
    if ch.isdigit(): return ord(ch) - 48
    if 'A' <= ch <= 'Z': return 10 + ord(ch) - 65
    if 'a' <= ch <= 'z': return 36 + ord(ch) - 97
    if ch == ' ': return 0xFF
    return PUNCT[ch]
def text_to_codes(s):
    return [code(c) for c in s]
def layout(codes, space=None, tracking=0):
    """[(pen, code)] of the characters drawn, and where the pixels end"""
    pen, end, out = 0, 0, []
    for c in codes:
        if c == 0xFF:
            pen += SPACE if space is None else space
            continue
        out.append((pen, c))
        end = max(end, pen + WIDTHS[c])
        pen += ADVANCE[c] + tracking
    return out, end
def width(s, space=None, tracking=0):
    return layout(text_to_codes(s), space, tracking)[1]
def render(s, space=None, tracking=0):
    """-> (ROWS x W) uint8 mask, W where the last pixel ends. space: the
    space's advance (the font's, 4, by default); tracking: added to every
    other character's advance (0: the text box's spacing)"""
    placed, end = layout(text_to_codes(s), space, tracking)
    a = np.zeros((ROWS, max(1, end)), np.uint8)
    for x, c in placed:
        g = GLYPHS[c * ROWS * 8:(c + 1) * ROWS * 8]
        for y in range(ROWS):
            for gx in range(WIDTHS[c]):
                b = g[y * 8 + gx // 2]
                v = (b >> 4) if gx & 1 else (b & 15)
                if v: a[y, x + gx] = 1
    return a
def outline(mask):
    m = mask.astype(bool)
    o = np.zeros_like(m)
    H, W = m.shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            sh = np.zeros_like(m)
            ys = slice(max(0, dy), H + min(0, dy)); yd = slice(max(0, -dy), H + min(0, -dy))
            xs = slice(max(0, dx), W + min(0, dx)); xd = slice(max(0, -dx), W + min(0, -dx))
            sh[yd, xd] = m[ys, xs]
            o |= sh
    return o & ~m
