#!/usr/bin/env python3
"""English UI labels for the GBA menus, drawn with the DS English font into the
original images (same size, same palette indices), or taken directly from the
DS English data where the DS has the very same graphic.

  Court Record tabs        Evidence / Profiles           DS font, outlined
  Court Record A/B labels  OK / Back                     DS font, outlined
  Investigation buttons    Examine / Move / Talk / Present
  Cross-exam buttons       Press / Present
  Save prompt              Yes / No                      DS English answer buttons
  Continue options         Resume from save / Restart chapter
  Episode select           the four DS English episode titles
  Testimony label          DS English graphic (same GBA format in data.bin)

The Japanese originals are kept as *.png.orig. Run relocate_assets.py after."""
import os, sys, shutil, struct
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from dsfont import render, outline
from dsdata import data, entry

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
EN_BTN = 0x263bf4c               # DS English answer buttons (256x32, 4bpp linear)
DS_TESTIMONY_EN = 0x1a961f4      # 64x64 GBA-format sprite, follows the Japanese one

def load(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path + '.orig'):
        shutil.copy(path, path + '.orig')
    im = Image.open(path + '.orig')
    return path, np.array(im).copy(), im.getpalette()

def save(path, a, pal):
    im = Image.fromarray(a.astype(np.uint8), 'P'); im.putpalette(pal); im.save(path)

def text_mask(s, space=4):
    return render(s, space=space)[:, :-1] if s else np.zeros((13, 0), np.uint8)  # drop trailing tracking

def stamp(a, mask, x0, y0, color):
    ys, xs = np.nonzero(mask)
    assert len(ys) == 0 or ((ys + y0).min() >= 0 and (ys + y0).max() < a.shape[0]
                            and (xs + x0).min() >= 0 and (xs + x0).max() < a.shape[1]), 'text does not fit'
    a[ys + y0, xs + x0] = color

def outlined(a, s, x0, y0, ink, edge, align='left', box=None):
    """draw s with a 1-pixel outline; (x0, y0) is the top-left of the outlined
    box, or with align='center' box=(left, right) centres it horizontally"""
    m = text_mask(s)
    p = np.zeros((m.shape[0] + 2, m.shape[1] + 2), np.uint8); p[1:-1, 1:-1] = m
    if align == 'center':
        x0 = box[0] + (box[1] - box[0] + 1 - p.shape[1]) // 2
    stamp(a, outline(p), x0, y0, edge)
    stamp(a, p, x0, y0, ink)

def plain(a, s, y0, ink, box):
    m = text_mask(s)
    x0 = box[0] + (box[1] - box[0] + 1 - m.shape[1]) // 2
    stamp(a, m, x0, y0, ink)

# ---------------------------------------------------------------- sprites
def court_record_tabs():
    for rel, s in (('graphics/ui/court_record/evidence_text.png', 'Evidence'),
                   ('graphics/ui/court_record/profiles_text.png', 'Profiles')):
        path, a, pal = load(rel)
        a[:] = 0
        outlined(a, s, 0, 0, 12, 10)
        save(path, a, pal)
    path, a, pal = load('graphics/ui/court_record/present_back_text.png')
    a[:] = 0
    outlined(a, 'OK', 0, 0, 12, 10)
    outlined(a, 'Back', 0, 16, 12, 10)
    save(path, a, pal)

def action_buttons():
    path, a, pal = load('graphics/ui/investigation/action_buttons.png')
    for k, s in enumerate(('Examine', 'Move', 'Talk', 'Present')):
        y = 32 * k
        a[y + 14:y + 29, 2:58] = 1              # clear the Japanese label (button face)
        outlined(a, s, 0, y + 15, 3, 14, 'center', (2, 57))
    save(path, a, pal)

def press_present():
    path, a, pal = load('graphics/ui/trial/press_present_buttons.png')
    a[0:13, 12:62] = 1
    a[16:29, 2:53] = 1
    plain(a, 'Press', 0, 3, (12, 61))
    plain(a, 'Present', 16, 3, (2, 52))
    save(path, a, pal)

# ---------------------------------------------------------------- plates
# The white plates (save prompt, continue options, episode select) share one
# palette: 12 white ... 4 dark red, 13 darkest.
PLATE_RAMP = [12, 11, 10, 9, 8, 7, 6, 5, 4, 13]

def ds_button_label(i):
    """English text of DS answer button i, as plate palette indices"""
    raw = entry(EN_BTN, i)
    body = np.frombuffer(raw[0x14:0x1014], np.uint8)
    b = np.stack([body & 15, body >> 4], 1).reshape(32, 256)[6:26, 18:237].astype(int)
    pal = [struct.unpack_from('<H', raw, 0x1014 + 2 * k)[0] for k in range(16)]
    lum = lambda c: ((c & 31) * 3 + ((c >> 5) & 31) * 6 + ((c >> 10) & 31)) / 10
    white, dark = lum(pal[3]), lum(pal[15])
    out = np.full(b.shape, -1)
    for v in range(4, 16):
        t = (white - lum(pal[v])) / (white - dark)          # 0 white .. 1 darkest
        out[b == v] = PLATE_RAMP[min(len(PLATE_RAMP) - 1, int(round(t * (len(PLATE_RAMP) - 1))))]
    out[out == 12] = -1
    rows = np.where((out >= 0).any(1))[0]; cols = np.where((out >= 0).any(0))[0]
    return out[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]

def put_label(a, lab, top, bottom, left, right):
    h, w = lab.shape
    y0 = top + (bottom - top + 1 - h) // 2; x0 = left + (right - left + 1 - w) // 2
    region = a[y0:y0 + h, x0:x0 + w]
    region[lab >= 0] = lab[lab >= 0]

def save_yes_no():
    path, a, pal = load('graphics/save_yes_no.png')
    for k, btn in enumerate((11, 10)):          # "Yes", "No"
        y = 32 * k
        a[y + 6:y + 26, 2:62] = 12
        put_label(a, ds_button_label(btn), y + 6, y + 25, 2, 61)
    save(path, a, pal)

def plate_texts(rel, texts, first=0):
    path, a, pal = load(rel)
    for k, s in enumerate(texts):
        y = 32 * (first + k)
        a[y + 6:y + 26, 2:126] = 12
        plain(a, s, y + 9, 13, (2, 125))
    save(path, a, pal)

# ---------------------------------------------------------------- save header
def save_header():
    """記録 header of the save screen -> "Save" (DS font at 2x, slanted like the
    original lettering). The two 32x32 kanji cells become one 64x32 word; the
    save-screen tilemap in src/bg.c places the two cells side by side."""
    path, a, pal = load('graphics/ui/message_box/save_game_tiles.png')
    m = text_mask('Save')
    m = np.kron(m, np.ones((2, 2), np.uint8))           # 2x, pixel for pixel
    h, w = m.shape
    slant = h // 4
    sk = np.zeros((h, w + slant), np.uint8)
    for y in range(h):
        off = (h - 1 - y) // 4                            # lean right like the kanji
        sk[y, off:off + w] = m[y]
    p = np.zeros((h + 2, sk.shape[1] + 2), np.uint8); p[1:-1, 1:-1] = sk
    edge = outline(p)
    word = np.full((32, 64), 9, np.uint8)
    rows = np.where(p.any(1))[0]
    y0 = (32 - (rows[-1] - rows[0] + 1)) // 2 - rows[0]
    x0 = (64 - p.shape[1]) // 2
    stamp(word, edge, x0, y0, 8)
    stamp(word, p, x0, y0, 14)
    a[192:224, 0:32] = word[:, 0:32]
    a[224:256, 0:32] = word[:, 32:64]
    save(path, a, pal)

# ---------------------------------------------------------------- DS graphic
def testimony():
    path, a, pal = load('graphics/ui/trial/testimony_text_tiles.png')
    raw = np.frombuffer(data()[DS_TESTIMONY_EN:DS_TESTIMONY_EN + 2048], np.uint8)
    t = np.stack([raw & 15, raw >> 4], 1).reshape(64, 8, 8)
    for k in range(64):
        a[(k // 8) * 8:(k // 8) * 8 + 8, (k % 8) * 8:(k % 8) * 8 + 8] = t[k]
    save(path, a, pal)

if __name__ == '__main__':
    court_record_tabs()
    action_buttons()
    press_present()
    save_yes_no()
    plate_texts('graphics/from_save_or_beginning_options.png', ('Resume from save', 'Restart chapter'))
    plate_texts('graphics/episode_select_options.png',
                ('The First Turnabout', 'Turnabout Sisters', 'Turnabout Samurai', 'Turnabout Goodbyes'), first=1)
    testimony()
    save_header()
    print('UI labels written')
