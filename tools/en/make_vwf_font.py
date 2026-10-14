#!/usr/bin/env python3
"""Build the text box font from the DS English release's own font.
usage: make_vwf_font.py DS_data.bin DS_arm9.bin out_glyphs.bin out_widths.bin out_advance.bin

The DS draws its text box from two 16x16 4bpp fonts in data.bin (ARM9
0x020245b8, in English mode): characters 0-0xFF from the English font at
0x1bfc374, the others from the Japanese one at 0x1bcb374 (the English
script uses a few of them: - " [ ] $ # and so on, and a handful of kanji).
Each character is its 16x16 cell drawn at the pen, and the pen moves on by
the character's width from the ARM9 table at 0x020b3d08 (characters below
0x110; 14 for the rest). (Until v0.7.54 the font was the Japanese font's own
Latin letters, which are drawn differently and sit 4 rows lower.)

Here every character keeps its cell, columns and rows as the DS has them:
  glyphs   16 rows x 16 px, 4bpp: the cell's rows -1..14 (the cell moved one
           row down, so the capitals start two rows in, as before: the box's
           layout stays), from its column 0, so the DS's left bearings stay
  widths   how many columns to draw: the last column with a pixel, plus one
  advance  how far the pen moves: the DS's width less ADVANCE_TIGHTER. The
           GBA's text box is narrower than the DS's (224 px a line against
           about 236); at the DS's own widths 546 lines of the four episodes
           would not fit, one pixel less a character they all do."""
import sys
EN_FONT, JP_FONT = 0x1bfc374, 0x1bcb374
WIDTH_TABLE = 0x020b3d08 - 0x02000000
COUNT = 1400
ROWS = 16
ROW_SHIFT = 1              # cell row r is glyph row r + 1
ADVANCE_TIGHTER = 1
OTHER_ADVANCE = 14         # the DS's for characters from 0x110 on


def cell(raw):
    a = [[0] * 16 for _ in range(16)]
    for t in range(4):
        tx, ty = t % 2, t // 2
        for y in range(8):
            for x in range(8):
                b = raw[t * 32 + y * 4 + x // 2]
                a[ty * 8 + y][tx * 8 + x] = (b >> 4) if x & 1 else (b & 15)
    return a


def main():
    d = open(sys.argv[1], 'rb').read()
    arm9 = open(sys.argv[2], 'rb').read()
    table = arm9[WIDTH_TABLE:WIDTH_TABLE + 0x110]
    glyphs = bytearray(); widths = bytearray(); advance = bytearray()
    for g in range(COUNT):
        base = EN_FONT if g <= 0xFF else JP_FONT
        a = cell(d[base + g * 0x80: base + (g + 1) * 0x80])
        cols = [x for x in range(16) if any(a[y][x] for y in range(16))]
        widths.append(cols[-1] + 1 if cols else 0)
        adv = table[g] if g < 0x110 else OTHER_ADVANCE
        advance.append(max(0, adv - ADVANCE_TIGHTER) if adv else 0)
        for y in range(ROWS):
            src = y - ROW_SHIFT
            row = a[src] if 0 <= src < 16 else [0] * 16
            for x in range(0, 16, 2):
                glyphs.append(row[x] | (row[x + 1] << 4))
    open(sys.argv[3], 'wb').write(glyphs)
    open(sys.argv[4], 'wb').write(widths)
    open(sys.argv[5], 'wb').write(advance)
    print('glyphs', COUNT, 'bytes', len(glyphs), 'space advance', advance[0xFF])


if __name__ == '__main__':
    main()
