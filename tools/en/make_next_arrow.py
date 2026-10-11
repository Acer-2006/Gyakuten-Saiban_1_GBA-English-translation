#!/usr/bin/env python3
"""The DS's "next" arrow for the text box: graphics/en/next_arrow.png (the
build turns it into next_arrow.4bpp, data/en_graphics.s gGfxEnNextArrow).

On the DS a 9 x 9 white triangle pointing right sits at the right end of the
third line and slides right and back, 1 px every 3 frames (positions 1 2 3 4
3 2, an 18-frame cycle): its tip is 3 px from the box's right border at
position 1 and on the border's inner column at position 4 (measured in the
DS game, frame by frame: columns 243-251 to 246-254, the border at 254-255).
Vertically it sits three quarters of the way down the box: rows 172-180 of
the DS's box at 128-191 (its centre at 176, 48 rows into 64), with nine rows
of box under it. Here it is drawn on the box's own layer (BG1) at the same
distance from the border (238-239), columns 227-235 (position 1) to 230-238
(position 4), and at the same proportion of this box (112-159): rows 144-152,
its centre at 148 (36 rows into 48), over the third line's capitals (144-153
with vwf.h VWF_TEXT_Y), five rows of box under it. Four 2 x 2 tile frames (map rows
18-19, columns 28-29) built on the box's own corner tiles (1, 7, 9, 5 of the
message box tileset), 16 tiles in all, loaded at BG tiles 448-463 (the unused
ASCII charset area). White is palette index 8, as the GBA's own arrow used.
usage: make_next_arrow.py"""
import os
from PIL import Image
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
SRC = os.path.join(ROOT, 'graphics', 'ui', 'message_box', 'save_game_tiles.png')
OUT = os.path.join(ROOT, 'graphics', 'en', 'next_arrow.png')
BASE = (1, 7, 9, 5)        # top-left, top-right, bottom-left, bottom-right of the corner
WHITE = 8
TOP_Y, LEFT_X = 144, 227   # position 1: rows 144-152, columns 227-235
TILE_X, TILE_Y = 224, 144  # the 2 x 2 block's origin (map row 18, column 28)


def main():
    sheet = Image.open(SRC)
    assert sheet.mode == 'P' and sheet.size[0] == 32
    per_row = sheet.size[0] // 8
    out = Image.new('P', (16, 64))
    out.putpalette(sheet.getpalette())
    for pos in range(1, 5):
        for k, tile in enumerate(BASE):
            box = ((tile % per_row) * 8, (tile // per_row) * 8)
            out.paste(sheet.crop(box + (box[0] + 8, box[1] + 8)), ((k % 2) * 8, (pos - 1) * 16 + (k // 2) * 8))
        for r in range(9):
            w = 2 * min(r, 8 - r) + 1
            for k in range(w):
                out.putpixel((LEFT_X + (pos - 1) + k - TILE_X, (pos - 1) * 16 + TOP_Y + r - TILE_Y), WHITE)
    out.save(OUT)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
