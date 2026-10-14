#!/usr/bin/env python3
"""Build the text box font from the DS English release's own font.
usage: make_vwf_font.py DS_data.bin out_glyphs.bin out_widths.bin out_advance.bin

The DS draws its text box from two 16x16 4bpp fonts in data.bin (ARM9
0x020245b8, in English mode): characters 0-0xFF from the English font at
0x1bfc374, the others from the Japanese one at 0x1bcb374 (the English
script uses a few of them: - " [ ] $ # and so on, and a handful of kanji).
(Until v0.7.54 the font was the Japanese font's own Latin letters, which are
drawn differently and sit 4 rows lower.)

Here every character keeps the DS's pixels and rows, at the spacing the text
box has always had: each letter one pixel after the last, word spaces of 4.
(The first v0.7.55 build spaced them at the DS's widths, from its table at
ARM9 0x020b3d08, less a pixel; that spread the words wider than they had been
and was taken back.)
  glyphs   16 rows x 16 px, 4bpp: the cell's rows -1..14 (the cell moved one
           row down, so the capitals start two rows in, as before: the box's
           layout stays), from the cell's first column with a pixel
  widths   how many columns hold pixels
  advance  how far the pen moves: the width and GAP; SPACE_ADVANCE for the
           space"""
import sys
EN_FONT, JP_FONT = 0x1bfc374, 0x1bcb374
COUNT = 1400
ROWS = 16
ROW_SHIFT = 1              # cell row r is glyph row r + 1
GAP = 1                    # columns between one letter's pixels and the next's
SPACE, SPACE_ADVANCE = 0xFF, 4


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
    glyphs = bytearray(); widths = bytearray(); advance = bytearray()
    for g in range(COUNT):
        base = EN_FONT if g <= 0xFF else JP_FONT
        a = cell(d[base + g * 0x80: base + (g + 1) * 0x80])
        cols = [x for x in range(16) if any(a[y][x] for y in range(16))]
        left, w = (cols[0], cols[-1] - cols[0] + 1) if cols else (0, 0)
        widths.append(w)
        advance.append(SPACE_ADVANCE if g == SPACE else w + GAP if w else 0)
        for y in range(ROWS):
            src = y - ROW_SHIFT
            row = a[src][left:] + [0] * left if 0 <= src < 16 else [0] * 16
            for x in range(0, 16, 2):
                glyphs.append(row[x] | (row[x + 1] << 4))
    open(sys.argv[2], 'wb').write(glyphs)
    open(sys.argv[3], 'wb').write(widths)
    open(sys.argv[4], 'wb').write(advance)
    print('glyphs', COUNT, 'bytes', len(glyphs), 'space advance', advance[SPACE])


if __name__ == '__main__':
    main()
