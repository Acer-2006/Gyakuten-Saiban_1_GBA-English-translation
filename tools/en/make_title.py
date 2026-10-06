#!/usr/bin/env python3
"""Build the English GBA title screen (240x160, 8bpp) from the DS English title
image (256x192, 8bpp, LZ-compressed at 0x1a7c1cc in the US data.bin)."""
import os, sys, shutil
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from dsdata import data, lz10
ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
EN_TITLE = 0x1a7c1cc

def ds_title():
    raw = lz10(data(), EN_TITLE)
    palb, px = raw[:512], raw[512:]
    pal = []
    for i in range(256):
        c = palb[2*i] | palb[2*i+1] << 8
        pal.append(((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3))
    img = Image.new('RGB', (256, 192)); P = img.load()
    for t in range(32 * 24):
        tx, ty = t % 32, t // 32
        for y in range(8):
            for x in range(8):
                P[tx*8+x, ty*8+y] = pal[px[t*64 + y*8 + x]]
    return img

src = ds_title()
out = Image.new('RGB', (240, 160), (0, 0, 0))
# logo + silhouette (rows 14-164), scaled to leave room for the menu at y=112
logo = src.crop((4, 14, 252, 165))
scale = 111 / logo.height
logo = logo.resize((round(logo.width * scale), 111), Image.LANCZOS)
out.paste(logo, ((240 - logo.width) // 2, 0))
# copyright line, unscaled, at the bottom. It is 245 px wide on the DS, so
# narrow each of the five word gaps (3-4 px) by 1 px to fit the GBA's 240 px.
drop = {55, 94, 145, 166, 201}
keep = [x for x in range(7, 252) if x not in drop]
s = np.array(src)[180:192]
cr = Image.fromarray(s[:, keep])
out.paste(cr, ((240 - len(keep)) // 2, 149))
# 15-bit colour, then a 255-colour palette with black at index 0
a = (np.array(out) >> 3) << 3
q = Image.fromarray(a.astype(np.uint8)).quantize(colors=255, method=Image.MEDIANCUT, dither=Image.NONE)
pal = q.getpalette()[:255*3]
idx = np.array(q) + 1
final = Image.fromarray(idx.astype(np.uint8), 'P')
final.putpalette([0, 0, 0] + pal + [0, 0, 0] * (256 - 256))
path = os.path.join(ROOT, 'graphics/title_screen.png')
if not os.path.exists(path + '.orig'):
    shutil.copy(path, path + '.orig')
final.save(path)
out.save(os.path.join(ROOT, 'graphics/title_screen_preview_rgb.png'))
print('title written', final.size)
