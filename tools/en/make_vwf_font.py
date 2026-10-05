#!/usr/bin/env python3
"""Build the variable-width font from the DS English charset.
usage: make_vwf_font.py DS_data.bin out_glyphs.bin out_widths.bin
Each glyph: 13 rows x 16 px, 4bpp, left-aligned (8 bytes per row = 104 bytes).
"""
import sys
CHARSET_OFF = 0x1bcb374   # DS data.bin offset of the 16x16 charset
COUNT = 1400
ROW0 = 3                   # first cell row kept (Latin caps start at row 5)
ROWS = 13
# Some DS punctuation sits higher in its cell than the Latin letters.
# Shift those down (in pixels) so they line up with the text baseline.
Y_SHIFT = {0x100: 5,   # '-' hyphen: move from cap height to mid x-height
           0x101: 4,   # '"' double quote
           0x102: 3, 0x103: 3, 0x104: 3, 0x105: 3,   # [ ] $ #
           0x106: 2, 0x107: 2, 0x108: 2, 0x109: 2, 0x10A: 2}  # > < = etc
def cell(raw):
    a = [[0]*16 for _ in range(16)]
    for t in range(4):
        tx, ty = t % 2, t // 2
        for y in range(8):
            for x in range(8):
                b = raw[t*32 + y*4 + x//2]
                a[ty*8+y][tx*8+x] = (b >> 4) if x & 1 else (b & 15)
    return a
d = open(sys.argv[1], 'rb').read()
glyphs = bytearray(); widths = bytearray()
for g in range(COUNT):
    a = cell(d[CHARSET_OFF + g*0x80: CHARSET_OFF + (g+1)*0x80])
    sh = Y_SHIFT.get(g, 0)
    if sh:
        a = [[0]*16 for _ in range(sh)] + a[:16-sh]
    cols = [x for x in range(16) if any(a[y][x] for y in range(16))]
    if cols:
        left, right = cols[0], cols[-1]
    else:
        left, right = 0, -1
    w = right - left + 1
    widths.append(max(0, w))
    for y in range(ROW0, ROW0 + ROWS):
        row = [a[y][x + left] if x + left < 16 else 0 for x in range(16)]
        for x in range(0, 16, 2):
            glyphs.append(row[x] | (row[x+1] << 4))
open(sys.argv[2], 'wb').write(glyphs)
open(sys.argv[3], 'wb').write(widths)
print('glyphs', COUNT, 'bytes', len(glyphs))
