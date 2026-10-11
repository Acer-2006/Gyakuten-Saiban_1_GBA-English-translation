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
  Episode select           the four DS English episode titles (DS plates, scaled down)
  Testimony label          DS English graphic (same GBA format in data.bin)
  Move / Talk menu plates  location and topic labels (tools/en/topics.py)

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

# The DS English Move / Talk plates (data.bin: 128x32 images, the same size as
# the GBA plates and in the same order as the GBA's: 21 locations, then the
# 125 talk topics of the first four episodes). Their lettering is moved onto
# the Japanese GBA plate in the plate palette (12 white ... 13 darkest), so
# the selected / greyed-out palettes the game swaps in still apply; the
# letters keep the DS's rows (the DS plate is centred on the same row as the
# GBA one) and are centred across. A word wider than the plate's inside
# (124 px, one free column each side) is narrowed to fit.
EN_LOC_PLATES, EN_TALK_PLATES, DS_PLATE_STRIDE = 0x26b1778, 0x2726f58, 0x8b4
PLATE_INSIDE = (2, 125)          # columns inside the GBA plate's border
PLATE_ROWS = (6, 25)             # rows inside it

def ds_lettering(off, inside):
    """the lettering of the uncompressed DS plate image at off, as darkness
    0 (white) .. 1 (darkest), cropped to its ink; inside = (top, bottom,
    left, right) of the DS plate's inner area -> (array, its top row)"""
    d = data()
    h = d[off:off + 0x14]
    assert h[0] == 3 and h[3] == 0 and h[4:8] == bytes.fromhex('14000000'), hex(off)
    w, ht = 8 << h[1], 8 << h[2]
    size, poff, psize = struct.unpack_from('<III', h, 8)
    body = np.frombuffer(d[off + 0x14:off + 0x14 + size], np.uint8)
    b = np.stack([body & 15, body >> 4], 1).reshape(ht, w).astype(int)
    pal = struct.unpack_from('<16H', d, off + poff)
    lum = lambda c: ((c & 31) * 3 + ((c >> 5) & 31) * 6 + ((c >> 10) & 31)) / 10
    white, dark = lum(pal[2]), lum(pal[15])
    t = np.zeros(b.shape)
    for v in range(4, 16):
        t[b == v] = max(0.0, (white - lum(pal[v])) / (white - dark))   # 0 white .. 1 darkest
    top, bottom, left, right = inside                                  # the DS plate's own edges
    m = np.zeros(t.shape, bool); m[top:bottom + 1, left:right + 1] = True
    t[~m] = 0
    rows = np.where((t > 0).any(1))[0]; cols = np.where((t > 0).any(0))[0]
    return t[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1], rows[0]

def area_resample(t, n, axis=1):
    """t resized to n along axis, each new pixel the average of what it covers"""
    if axis == 0:
        return area_resample(t.T, n).T
    src = t.shape[1]
    if src == n:
        return t
    edges = np.linspace(0, src, n + 1)
    out = np.zeros((t.shape[0], n))
    for k in range(n):
        a0, a1 = edges[k], edges[k + 1]
        for x in range(int(a0), int(np.ceil(a1))):
            w = min(a1, x + 1) - max(a0, x)
            if w > 0:
                out[:, k] += t[:, x] * w
        out[:, k] /= (a1 - a0)
    return out

def plate_ink(t):
    """darkness -> plate palette indices, -1 where the plate stays white"""
    lab = np.array(PLATE_RAMP)[np.clip(np.round(t * (len(PLATE_RAMP) - 1)).astype(int), 0, len(PLATE_RAMP) - 1)]
    lab[lab == 12] = -1
    return lab

def ds_plate_label(off):
    """the lettering of the 128x32 DS plate at off -> (palette indices, -1 transparent; top row)"""
    t, top = ds_lettering(off, (PLATE_ROWS[0], PLATE_ROWS[1], 0, 127))
    room = PLATE_INSIDE[1] - PLATE_INSIDE[0] + 1 - 2
    if t.shape[1] > room:                                               # narrowed to fit, by area
        t = area_resample(t, room)
    return plate_ink(t), top

def menu_plates():
    import glob
    for d, first, n in (('location_choices', EN_LOC_PLATES, 21), ('talk_choices', EN_TALK_PLATES, 125)):
        files = sorted(glob.glob(os.path.join(ROOT, 'graphics', d, '*.png')))
        assert len(files) == n, d
        for k, f in enumerate(files):
            path, a, pal = load(os.path.relpath(f, ROOT))
            a[PLATE_ROWS[0]:PLATE_ROWS[1] + 1, PLATE_INSIDE[0]:PLATE_INSIDE[1] + 1] = 12
            lab, top = ds_plate_label(first + k * DS_PLATE_STRIDE)
            h, w = lab.shape
            x0 = PLATE_INSIDE[0] + (PLATE_INSIDE[1] - PLATE_INSIDE[0] + 1 - w) // 2
            region = a[top:top + h, x0:x0 + w]
            region[lab >= 0] = lab[lab >= 0]
            save(path, a, pal)

# The DS English episode select plates (data.bin: 256x64 images, plate
# 176x58 at (8, 3)): their titles on the GBA episode plates (128x32, the
# first one is the locked "? ? ?"), in the plate palette as above. The DS
# titles are up to 166 px wide and the GBA plate's inside is 124, so all
# four are scaled down evenly by the same factor (the widest just fits, one
# free column each side), averaging what each new pixel covers; the capital
# letters sit centred on the plate, as on the DS.
DS_EPISODE_PLATES = (0x2534d90, 0x2538eb8, 0x253cfe0, 0x2541108)
DS_EPISODE_INSIDE = (6, 57, 11, 181)   # inside the DS plate's border
DS_EPISODE_CAP = 14                    # rows of a capital letter on the DS

def episode_titles():
    path, a, pal = load('graphics/episode_select_options.png')
    titles = [ds_lettering(off, DS_EPISODE_INSIDE)[0] for off in DS_EPISODE_PLATES]
    room = PLATE_INSIDE[1] - PLATE_INSIDE[0] + 1 - 2
    f = room / max(t.shape[1] for t in titles)
    cap = int(round(DS_EPISODE_CAP * f))
    for k, t in enumerate(titles):
        y = 32 * (k + 1)
        a[y + PLATE_ROWS[0]:y + PLATE_ROWS[1] + 1, PLATE_INSIDE[0]:PLATE_INSIDE[1] + 1] = 12
        t = area_resample(area_resample(t, int(round(t.shape[1] * f))), int(round(t.shape[0] * f)), axis=0)
        lab = plate_ink(t)
        h, w = lab.shape
        top = y + PLATE_ROWS[0] + (PLATE_ROWS[1] - PLATE_ROWS[0] + 1 - cap) // 2
        x0 = PLATE_INSIDE[0] + (PLATE_INSIDE[1] - PLATE_INSIDE[0] + 1 - w) // 2
        region = a[top:top + h, x0:x0 + w]
        region[lab >= 0] = lab[lab >= 0]
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
    # the DS lettering rounds the corners of its strokes with colour 3, which
    # is black in this palette (and on the DS): black notches inside the green
    # outline. They are outline here, as on the Japanese label (colour 1)
    a[a == 3] = 1
    a[:32] = jp_size_label(a[:32])
    save(path, a, pal)

# Columns taken out of each DS letter (counted from the letter's left edge) so
# the word fits the Japanese label's box (55 x 30): the T's bar ends, one
# column of each 2-3 pixel wide counter (e, m, o, n). Strokes stay 2 pixels.
# s, t, i and y have no column that can go without thinning a stroke.
TESTIMONY_CUTS = {'T': (0, 7), 'e': (3,), 'm': (3, 6), 'o': (3,), 'n': (3,)}

def jp_size_label(a):
    """The DS "Testimony" lettering (64 x 32) narrowed and shortened to the
    size of the Japanese label: whole letters are moved, columns are only
    taken out of horizontal runs inside letters, and two rows out of the
    straight middle of every letter (rows identical to the one above)."""
    from scipy import ndimage
    fill = a == 2
    lab, n = ndimage.label(fill)
    boxes = sorted((np.nonzero(lab == k)[1].min(), k) for k in range(1, n + 1))
    # the dot of the i joins its stem
    glyphs = []
    for x0, k in boxes:
        xs = np.nonzero(lab == k)[1]
        if glyphs and xs.min() >= glyphs[-1][1] and xs.max() <= glyphs[-1][2]:
            glyphs[-1][0].append(k)
        else:
            glyphs.append([[k], xs.min(), xs.max()])
    assert len(glyphs) == 9, len(glyphs)
    gid = np.zeros_like(lab)
    for g, (ks, x0, x1) in enumerate(glyphs):
        for k in ks:
            gid[lab == k] = g + 1
    # every outline pixel belongs to the nearest letter
    _, (iy, ix) = ndimage.distance_transform_edt(gid == 0, return_indices=True)
    owner = gid[iy, ix]
    owner[a == 0] = 0
    cuts = [TESTIMONY_CUTS.get(c, ()) for c in 'Testimony']
    def edges(piece, val=2):
        return {y: (np.nonzero(r == val)[0].min(), np.nonzero(r == val)[0].max())
                for y, r in enumerate(piece) if (r == val).any()}
    layers = []
    for g, (ks, x0, x1) in enumerate(glyphs):
        cols = [x for x in range(a.shape[1]) if (owner[:, x] == g + 1).any()]
        lo, hi = min(cols), max(cols)
        piece = np.where(owner[:, lo:hi + 1] == g + 1, a[:, lo:hi + 1], 0)
        cut = np.delete(piece, [x0 + c - lo for c in cuts[g]], 1)
        if not layers:
            layers.append((lo, lo, piece, cut))
            continue
        # keep the closest distance between this letter's fill and the
        # previous one's, row by row, as on the DS
        px, plo, ppiece, pcut = layers[-1]
        pe, e, pec, ec = edges(ppiece), edges(piece), edges(pcut), edges(cut)
        both = [y for y in e if y in pe]
        gap = min(lo + e[y][0] - (plo + pe[y][1]) for y in both)
        x = max(px + pec[y][1] + gap - ec[y][0] for y in both)
        layers.append((x, lo, piece, cut))
    out = np.zeros_like(a)
    for val in (1, 2):                           # outlines first, then the fill
        for x, lo, piece, cut in layers:
            m = cut == val
            out[:, x:x + cut.shape[1]][m] = val
    # two rows out of the straight middle of the letters (each the same as the row above)
    for y in (14, 12):
        assert (a[y] == a[y - 1]).all() and (out[y] == out[y - 1]).all()
        out = np.delete(out, y, 0)
    res = np.zeros_like(a)
    res[1:1 + out.shape[0]] = out                 # one empty row on top, as on the Japanese label
    return res

if __name__ == '__main__':
    court_record_tabs()
    action_buttons()
    press_present()
    save_yes_no()
    # the DS English wording of these two options (DS images too wide for the GBA plates)
    plate_texts('graphics/from_save_or_beginning_options.png', ('From save point.', 'From chapter start.'))
    episode_titles()
    testimony()
    save_header()
    menu_plates()
    print('UI labels written')
