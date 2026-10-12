"""The partner portraits the fifth episode's command 76 shows (64x64, 16
colours, 0x820 bytes each at data.bin 0x01bb3074: Ema's twelve, Gumshoe's
six). portraits.py out.png draws the sheet."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from dsdata import data, tiles_to_array
from PIL import Image
PORTRAITS, COUNT = 0x01bb3074, 18
EVIDENCE_ICONS, ICON_COUNT = 0x01b68614, 147     # the Court Record pictures, same format
def picture(base, i):
    d = data(); o = base + 0x820 * i
    pal = [d[o + 2 * k] | d[o + 2 * k + 1] << 8 for k in range(16)]
    cols = [((v & 31) * 8, ((v >> 5) & 31) * 8, ((v >> 10) & 31) * 8) for v in pal]
    arr = tiles_to_array(d[o + 0x20:o + 0x820], 8, 8)
    im = Image.new('RGB', (64, 64)); im.putdata([cols[v] for row in arr for v in row])
    return im
if __name__ == '__main__':
    sheet = Image.new('RGB', (64 * 6, 64 * 3))
    for i in range(COUNT):
        sheet.paste(picture(PORTRAITS, i), ((i % 6) * 64, (i // 6) * 64))
    sheet.save(sys.argv[1])
