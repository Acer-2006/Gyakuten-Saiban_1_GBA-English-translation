"""The text box name tags of the fifth episode (Lana, Gant, Marshall,
Starr, Meekins, Goodman...): the DS keeps its English name-tag sheet in
data.bin in the GBA's own layout (five 48x16 tags per 0x800-byte row, top
halves then bottom halves), at EN_TAGS; the GBA sheet
graphics/ui/message_box/nametags.png is its first nine rows. This writes
the sheet with ROWS rows (tags 45-54 too) to graphics/en/rfta/nametags.png,
the sheet of the Rise from the Ashes build. usage: nametags.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from dsdata import data
from PIL import Image
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
BASE_PNG = os.path.join(ROOT, 'graphics', 'ui', 'message_box', 'nametags.png')
PNG = os.path.join(ROOT, 'graphics', 'en', 'rfta', 'nametags.png')
EN_TAGS = 0x1a87454
ROWS = 11
def sheet(rows):
    d = data(); raw = d[EN_TAGS:EN_TAGS + 0x800 * rows]
    im = Image.new('P', (256, 16 * rows))
    px = im.load()
    for r in range(rows):
        for half in range(2):
            for t in range(5):
                base = r * 0x800 + half * 0x400 + t * 0xC0
                for tile in range(6):
                    for y in range(8):
                        for x in range(8):
                            b = raw[base + tile * 32 + y * 4 + x // 2]
                            v = (b >> 4) if x & 1 else (b & 15)
                            px[t * 48 + tile * 8 + x, r * 16 + half * 8 + y] = v
    return im
if __name__ == '__main__':
    old = Image.open(BASE_PNG)
    new = sheet(ROWS)
    new.putpalette(old.getpalette())
    same = old.tobytes() == new.crop((0, 0, 256, old.height)).tobytes()
    print('first %d rows identical to the current sheet: %s' % (old.height // 16, same))
    new.save(PNG)
    print('wrote', PNG, new.size)
