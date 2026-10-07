#!/usr/bin/env python3
"""port_map_markers.py : the DS's map markers that carry text, on the GBA.

The markers the script puts on maps and floor plans (39/3A commands): the
killer and victim symbols on the floor plans (Japanese 犯 / 被, the DS's
"K" / "V") and the labelled areas on the Global Studios map (第1スタジオ,
第2スタジオ, スタッフエリア, 正門; the DS's "Studio 1", "Studio 2",
"Employee Area" and the plain highlight over the main gate, whose name is on
the map itself). tools/en/assets/ds_map_markers/ holds each DS marker as the
English DS game draws it (its sprite read from the DS's OAM, VRAM and palette
in DeSmuME, at the place the script shows it). The DS markers are the same
size, at the same place and in the same 16-colour palette as the GBA's, so
each is written over the GBA's marker picture pixel for pixel.
Markers without text (Mia's outline, the clock, the boats, the car...) stay
the GBA's."""
import os
from PIL import Image
ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
SRC = os.path.join(os.path.dirname(__file__), 'assets', 'ds_map_markers')
NAMES = ['killer', 'victim', 'case3_studio_1', 'case3_studio_2', 'case3_employee_area', 'case3_main_gate']
for n in NAMES:
    dst = os.path.join(ROOT, 'graphics', 'map_markers', n + '.png')
    old = Image.open(dst)
    pal = old.getpalette()[:48]
    cols = [tuple(pal[3 * i:3 * i + 3]) for i in range(16)]
    def idx(c):
        # nearest palette colour (the DS capture is 5-bit colour scaled to 8 bits)
        return min(range(1, 16), key=lambda i: sum((a - b) ** 2 for a, b in zip(cols[i], c)))
    ds = Image.open(os.path.join(SRC, n + '.png')).convert('RGBA')
    assert ds.size == old.size, (n, ds.size, old.size)
    new = Image.new('P', old.size, 0)
    new.putpalette(pal + [0] * (768 - len(pal)))
    for y in range(ds.height):
        for x in range(ds.width):
            r, g, b, a = ds.getpixel((x, y))
            if a:
                i = idx((r, g, b))
                assert sum((p - q) ** 2 for p, q in zip(cols[i], (r, g, b))) < 3 * 8 ** 2, (n, x, y, (r, g, b))
                new.putpixel((x, y), i)
    new.save(dst, transparency=0)
    print(n, old.size)
