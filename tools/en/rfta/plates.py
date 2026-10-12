#!/usr/bin/env python3
"""The fifth episode's menu plates, from the DS English data.

The DS keeps its Move and Talk plates as 128x32 images in data.bin (the
GBA's size), in one run: 28 Japanese location plates, the 28 English ones,
188 Japanese talk plates, the 188 English ones. Locations are numbered by
the DS's rooms (the fifth episode's are 0x16-0x1B, plates 22-27), talk
plates by the GBA's topic icons (the fifth episode's are 125-187). As for
the first four episodes (tools/en/make_ui_text.py, menu_plates), the DS's
lettering goes on a GBA plate in the plate palette, so the game's selected /
greyed-out palettes still apply.

The episode select's fifth plate is the DS's "Rise from the Ashes" (the
plate after Turnabout Goodbyes'), scaled by the factor the other four were.

Writes graphics/en/rfta/location_choices.png (GBA rooms 0x10-0x17, the
renumbered DS rooms 0x16-0x1D; the episode uses the first six),
graphics/en/rfta/talk_choices.png (icons 125-187) and
graphics/en/rfta/episode_title.png. usage: plates.py"""
import os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import make_ui_text as ui
ROOT = os.path.join(HERE, '..', '..', '..')
OUT = os.path.join(ROOT, 'graphics', 'en', 'rfta')
DS_LOC_PLATES = 28                       # locations on the DS (rooms 0-0x1B)
FIRST_NEW_ROOM_DS, NEW_ROOMS = 0x16, 8   # DS rooms 0x16-0x1D are GBA rooms 0x10-0x17
FIRST_TOPIC, TOPICS = 125, 63
RFTA_TITLE = 0x2534d90 + 4 * 0x4128      # the DS English episode plate after Turnabout Goodbyes'

def template():
    """a blank GBA plate (the first location plate, Japanese original, inside cleared)"""
    im = Image.open(os.path.join(ROOT, 'graphics', 'location_choices', '001FD96C.png.orig'))
    a = np.array(im).copy()
    a[ui.PLATE_ROWS[0]:ui.PLATE_ROWS[1] + 1, ui.PLATE_INSIDE[0]:ui.PLATE_INSIDE[1] + 1] = 12
    return a, im.getpalette()

def lettered(blank, off):
    a = blank.copy()
    lab, top = ui.ds_plate_label(off)
    h, w = lab.shape
    x0 = ui.PLATE_INSIDE[0] + (ui.PLATE_INSIDE[1] - ui.PLATE_INSIDE[0] + 1 - w) // 2
    region = a[top:top + h, x0:x0 + w]
    region[lab >= 0] = lab[lab >= 0]
    return a

def sheet(plates, pal, name):
    im = Image.fromarray(np.concatenate(plates, 0).astype(np.uint8), 'P')
    im.putpalette(pal)
    im.save(os.path.join(OUT, name))

def episode_title():
    """the fifth title on a GBA episode plate, as make_ui_text.episode_titles does the first four"""
    src = Image.open(os.path.join(ROOT, 'graphics', 'episode_select_options.png.orig'))
    a = np.array(src)[32:64].copy()      # a plate (the first title's) to letter afresh
    a[ui.PLATE_ROWS[0]:ui.PLATE_ROWS[1] + 1, ui.PLATE_INSIDE[0]:ui.PLATE_INSIDE[1] + 1] = 12
    titles = [ui.ds_lettering(off, ui.DS_EPISODE_INSIDE)[0] for off in ui.DS_EPISODE_PLATES]
    room = ui.PLATE_INSIDE[1] - ui.PLATE_INSIDE[0] + 1 - 2
    f = room / max(t.shape[1] for t in titles)
    t = ui.ds_lettering(RFTA_TITLE, ui.DS_EPISODE_INSIDE)[0]
    assert t.shape[1] * f <= room
    cap = int(round(ui.DS_EPISODE_CAP * f))
    t = ui.area_resample(ui.area_resample(t, int(round(t.shape[1] * f))), int(round(t.shape[0] * f)), axis=0)
    lab = ui.plate_ink(t)
    h, w = lab.shape
    top = ui.PLATE_ROWS[0] + (ui.PLATE_ROWS[1] - ui.PLATE_ROWS[0] + 1 - cap) // 2
    x0 = ui.PLATE_INSIDE[0] + (ui.PLATE_INSIDE[1] - ui.PLATE_INSIDE[0] + 1 - w) // 2
    region = a[top:top + h, x0:x0 + w]
    region[lab >= 0] = lab[lab >= 0]
    im = Image.fromarray(a.astype(np.uint8), 'P'); im.putpalette(src.getpalette())
    im.save(os.path.join(OUT, 'episode_title.png'))

def main():
    os.makedirs(OUT, exist_ok=True)
    blank, pal = template()
    locs = []
    for k in range(NEW_ROOMS):
        plate = FIRST_NEW_ROOM_DS + k
        locs.append(lettered(blank, ui.EN_LOC_PLATES + plate * ui.DS_PLATE_STRIDE) if plate < DS_LOC_PLATES else blank)
    sheet(locs, pal, 'location_choices.png')
    talk = [lettered(blank, ui.EN_TALK_PLATES + (FIRST_TOPIC + k) * ui.DS_PLATE_STRIDE) for k in range(TOPICS)]
    sheet(talk, pal, 'talk_choices.png')
    episode_title()
    print('%d location plates, %d talk plates, the episode title' % (len(locs), len(talk)))

if __name__ == '__main__':
    main()
