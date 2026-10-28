#!/usr/bin/env python3
"""The fifth episode's fingerprinting (the DS's fingerprint screens, its
0x0207be54-0x020801f0 and the comparison's), from the DS.

The DS starts it with 74 9 n, n the case (0x020c94b4, 16 bytes each: the
picture's background, a count and a pointer to the fingers' records of 0x2e
bytes: the square shown round the finger, the quadrilateral the touch picks
it by, its type at +0x2a (1: a print to compare, 0: none to compare) and its
mask at +0x2b):

  0  the bloody handprint on Gumshoe's locker (Day 2): five fingers in the
     blood, a print beside it; until the first finger is dusted (flag 0x1C
     then set) only the fingers in the blood can be picked, after it only
     the print beside them
  1  the wiped stain in the evidence room (Day 2): the two fingers
  2  the cloth from the Chief's safe (Day 3): five

A finger is dusted on the touch screen: each touch drops powder (four of
its stamps, 0x0206eb70: 128 x 128, data.bin at the literal 0x0206c028, a
random one each frame for four frames, the stamp's dots added to the
powder, saturating), and blowing into the microphone (its level read every
fourth frame) blows the powder away, a quarter of the screen's rows a frame
(0x0206f030): where the finger's mask (data.bin, 256 x 192, a level in each
byte's low nibble, 0x0206f9e4 shifts it up) is at most 0x40 by half the
level, where it is more by the level less the mask's (so the print keeps
its powder). The finger is found (0x0206e600) when, in its rectangle (the
mask records at 0x020c1a4c: type, the record of the rectangle and the
count of pixels needed; type 2 has a second, smaller rectangle that
decides), enough pixels of mask 0x50 and up hold more than 0x80 of powder
and none of mask 0x10 (the ring round the print) holds 0x20 or more.

Then the script takes over (0x0207be54: the sections 13B the first finger's
how-to, 13C the dusting's how-to, 13E the glove print, 13D / file 35's C9
back from the dusting, 13F the print beside the blood, 141 / 12A a wrong
person, file 35's CA no print), and the comparison: the eight people whose
prints Edgeworth gave (their prints at 0x020b0fbc, 96 x 128 in 16 greys,
the palette at the literal 0x0207b498; card order to print 0x020b0ec0), the
print found against the one chosen in three sweeps, the matching points
(0x020b0efc, 16 for each case) counted up, then "Match found." (SE0C0) or
"No matches found." (BGM032); the match goes on in 142, 146 or 12B.

On the GBA the dusting screen is the DS's touch screen scaled by 10/11
(its 176 rows above the "Back" bar into the GBA's 160) and centred: GBA x =
DUST_X + 10/11 x, y = 10/11 y. The fingers' picture is the background, cut
as backgrounds.py cuts it (x - 8, y - 16).

Writes graphics/en/rfta/fingerprint.bin, data/rfta/fingerprint.s (section
rfta_low) and src/data/en_rfta_fingerprint.h. usage: fingerprint.py [--preview DIR]"""
import os, sys, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import dsbin
from dsdata import data
ROOT = os.path.join(HERE, '..', '..', '..')

CASES, CASE_COUNT = 0x020c94b4, 3
FINGER_SIZE = 0x2E
MASKS, MASK_COUNT = 0x020c1a4c, 13
STAMP_PTR = 0x0206c028                  # literal: data.bin offset of the four stamps
STAMP_SIZE = 128
PRINTS, PRINT_COUNT = 0x020b0fbc, 8
PRINT_PAL_PTR = 0x0207b498              # literal: the prints' 16 greys
PRINT_W, PRINT_H = 96, 128
PERSON_PRINT = 0x020b0ec0               # card order -> print
POINTS = 0x020b0efc                     # 16 (x, y) a case, in the print
# the cards: the people, as the DS's comparison screen lists them, and their
# faces (data.bin, 64 x 64, 16 colours, a pixel a nibble row by row, after a
# 0x14-byte header; the offsets the screen reads, 0x02042f3c)
PEOPLE = [('Damon Gant', 65, 'Male', 0x029a4770), ('Mike Meekins', 22, 'Male', 0x029a57d8),
          ('Jake Marshall', 33, 'Male', 0x029a3708), ('Bruce Goodman', 36, 'Male', 0x029a4fa4),
          ('Dick Gumshoe', 30, 'Male', 0x0296a048), ('Lana Skye', 29, 'Female', 0x029a26a0),
          ('Ema Skye', 16, 'Female', 0x029a1e6c), ('Angel Starr', 31, 'Female', 0x029a2ed4)]
# whose print each case finds (the DS's comparison: the card that matches)
ANSWER = {0: 4, 1: 2, 2: 6}             # Gumshoe, Marshall, Ema

DS_W, DS_H = 256, 176                   # the touch screen above its "Back" bar
GBA_W, GBA_H = 240, 160
SCALE = 10 / 11
DUST_X = (GBA_W - int(round(DS_W * SCALE))) // 2
PICTURE_DX, PICTURE_DY = 8, 16          # the fingers' picture, as backgrounds.py cuts it


def u16s(addr, n):
    d = dsbin.data()
    return struct.unpack_from('<%dH' % n, d, addr - dsbin.BASE)


def cases():
    """[{bg, fingers: [{square, quad, type, mask}]}]"""
    out = []
    for c in range(CASE_COUNT):
        d = dsbin.data(); o = CASES + 16 * c - dsbin.BASE
        bg, _, back, _ = struct.unpack_from('<4H', d, o)
        cnt = d[o + 9]; p = struct.unpack_from('<I', d, o + 12)[0]
        fingers = []
        for k in range(cnt):
            r = u16s(p + FINGER_SIZE * k, 23)
            raw = d[p + FINGER_SIZE * k - dsbin.BASE:p + FINGER_SIZE * (k + 1) - dsbin.BASE]
            fingers.append(dict(square=r[0:4], quad=[(r[10 + 2 * i], r[11 + 2 * i]) for i in range(4)],
                                type=raw[0x2A], mask=raw[0x2B]))
        out.append(dict(bg=bg, fingers=fingers))
    return out


def masks():
    """[{type, threshold, rects: [{x, y, w, h, need, src, size}]}]"""
    out = []
    for i in range(MASK_COUNT):
        d = dsbin.data(); o = MASKS + 16 * i - dsbin.BASE
        t, _, thr, rp = struct.unpack_from('<4I', d, o)
        rects = []
        for k in range(1 if t == 1 else 2):
            v = struct.unpack_from('<10I', d, rp + 0x28 * k - dsbin.BASE)
            rects.append(dict(x=v[1], y=v[2], w=v[3], h=v[4], need=v[5], src=v[8], size=v[9]))
        out.append(dict(type=t, threshold=thr, rects=rects))
    return out


def mask_image(r):
    """the DS's mask: 192 x 256 levels 0-15 (the low nibbles)"""
    a = np.frombuffer(data()[r['src']:r['src'] + r['size']], np.uint8).reshape(192, 256)
    return a & 15


def stamps():
    base = dsbin.u32(STAMP_PTR)
    d = data()
    return [np.frombuffer(d[base + k * STAMP_SIZE ** 2:base + (k + 1) * STAMP_SIZE ** 2], np.uint8).reshape(STAMP_SIZE, STAMP_SIZE)
            for k in range(4)]


def prints():
    d = data()
    out = []
    for k in range(PRINT_COUNT):
        off, size = struct.unpack_from('<II', dsbin.data(), PRINTS + 8 * k - dsbin.BASE)
        b = np.frombuffer(d[off:off + size], np.uint8)
        px = np.stack([b & 15, b >> 4], 1).reshape(-1)
        tw = PRINT_W // 8
        out.append(px.reshape(PRINT_H // 8, tw, 8, 8).transpose(0, 2, 1, 3).reshape(PRINT_H, PRINT_W))
    return out


def print_palette():
    off = dsbin.u32(PRINT_PAL_PTR)
    c = struct.unpack_from('<16H', data(), off)
    return [((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3) for v in c]


def person_print():
    return list(dsbin.data()[PERSON_PRINT - dsbin.BASE:PERSON_PRINT - dsbin.BASE + 8])


def points():
    v = u16s(POINTS, 2 * 16 * CASE_COUNT)
    return [[(v[2 * (16 * c + i)], v[2 * (16 * c + i) + 1]) for i in range(16)] for c in range(CASE_COUNT)]


def face(off):
    d = data()
    t0, ts, p0, ps = struct.unpack_from('<4I', d, off + 4)
    b = np.frombuffer(d[off + t0:off + t0 + ts], np.uint8)
    px = np.stack([b & 15, b >> 4], 1).reshape(64, 64)
    pal = struct.unpack_from('<16H', d, off + p0)
    return px, [((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3) for v in pal]


# ---------------------------------------------------------------- the GBA's
def to_gba(img, fill=0):
    """a DS touch-screen image (192 x 256) on the GBA's dusting screen, by
    sampling (bilinear on the levels)"""
    gy, gx = np.mgrid[0:GBA_H, 0:GBA_W].astype(float)
    sx = (gx - DUST_X + 0.5) / SCALE - 0.5
    sy = (gy + 0.5) / SCALE - 0.5
    x0 = np.floor(sx).astype(int); y0 = np.floor(sy).astype(int)
    fx = sx - x0; fy = sy - y0
    a = img.astype(float)
    def at(y, x):
        ok = (x >= 0) & (x < 256) & (y >= 0) & (y < 192)
        return np.where(ok, a[np.clip(y, 0, 191), np.clip(x, 0, 255)], fill)
    return (at(y0, x0) * (1 - fx) * (1 - fy) + at(y0, x0 + 1) * fx * (1 - fy) +
            at(y0 + 1, x0) * (1 - fx) * fy + at(y0 + 1, x0 + 1) * fx * fy)


def to_gba_nearest(img):
    gy, gx = np.mgrid[0:GBA_H, 0:GBA_W]
    sx = ((gx - DUST_X + 0.5) / SCALE).astype(int)
    sy = ((gy + 0.5) / SCALE).astype(int)
    ok = (sx >= 0) & (sx < 256) & (sy < 192)
    return np.where(ok, img[np.clip(sy, 0, 191), np.clip(sx, 0, 255)], 0)


def finger_planes(m):
    """the GBA's three bit planes for a mask record: the print (the powder
    stays), the pixels counted, the ring that must be clean (each 160 x 240
    bools), and the count needed"""
    img = mask_image(m['rects'][0])
    lv = to_gba(img)
    prt = lv >= 5
    ring = (to_gba_nearest(img) == 1) & ~prt     # (where the scaling made a print pixel of it: the print's)
    r = m['rects'][-1]                  # the rectangle that decides
    region = np.zeros((192, 256), bool)
    region[r['y']:r['y'] + r['h'], r['x']:r['x'] + r['w']] = True
    reg = to_gba_nearest(region.astype(np.uint8)) > 0
    ds_count = ((img >= 5) & region).sum()
    count = prt & reg
    need = int(round(r['need'] * count.sum() / max(ds_count, 1)))
    return prt, count, ring & reg, need


# ---------------------------------------------------------------- the art
# the sprites' colours (OBJ palette 8 while the fingerprints are up)
UI = [None, (248, 248, 248), (24, 24, 24), (120, 48, 0), (88, 32, 0), (224, 224, 224), (160, 160, 160),
      (56, 104, 248), (232, 24, 24), (120, 0, 24), (40, 72, 48), (248, 152, 48), (200, 200, 200),
      (248, 64, 64), (80, 80, 80), (136, 200, 152)]
C_WHITE, C_BLACK, C_BAR, C_BAR_DARK, C_LIGHT, C_GREY, C_BLUE, C_RED, C_DARK_RED, C_LCD, C_ORANGE, \
    C_TAB, C_SCAN, C_DARK, C_LCD_OFF = range(1, 16)
# the dusting screen (BG palette 15): the DS's green, its grid's lines and
# crossings, the powder's four shades (measured off the DS's screen)
DUST = [(0, 0, 0), (0, 128, 24), (32, 168, 64), (40, 176, 80), (104, 176, 112), (152, 200, 160),
        (184, 216, 192), (232, 240, 232)] + [(0, 0, 0)] * 8
GRID = 16                               # the DS's grid: a line every 16 pixels, at 7


def text(s, space=None):
    from dsfont import render
    return render(s, space)


def put(img, mask, x, y, color, edge=None):
    """draw a 16-row text mask (or any mask) into a palette-index image"""
    from dsfont import outline
    h, w = mask.shape
    if edge is not None:
        big = np.zeros((h + 2, w + 2), bool); big[1:-1, 1:-1] = mask > 0
        o = outline(big)
        ys, xs = np.nonzero(o)
        for yy, xx in zip(ys + y - 1, xs + x - 1):
            if 0 <= yy < img.shape[0] and 0 <= xx < img.shape[1]:
                img[yy, xx] = edge
    ys, xs = np.nonzero(mask)
    for yy, xx in zip(ys + y, xs + x):
        if 0 <= yy < img.shape[0] and 0 <= xx < img.shape[1]:
            img[yy, xx] = color


def button_icon(letter):
    """a 12 x 12 round button with its letter (A, B) or the shoulder R"""
    a = np.zeros((12, 12), np.uint8)
    yy, xx = np.mgrid[0:12, 0:12]
    if letter == 'R':
        a[1:11, 0:12] = C_DARK; a[2:10, 1:11] = C_LIGHT
        a[1, 0] = a[1, 11] = a[10, 0] = a[10, 11] = 0
    else:
        r = np.hypot(xx - 5.5, yy - 5.5)
        a[r <= 6.0] = C_LIGHT
    m = text(letter)[2:13]
    w = m.shape[1]
    put(a, m[:10], (12 - w) // 2, 1, C_BAR_DARK)
    return a


def tab(label, letter, w=None):
    """a prompt like the DS's buttons: a dark tab, the button, the label in
    white (w: its width, by default the label's rounded up to 8)"""
    if w is None:
        need = 3 + sum(14 + text(p)[2:15].shape[1] + 6 for p in label) - 6 + 3
        w = (need + 7) // 8 * 8
    a = np.zeros((16, w), np.uint8)
    a[1:15, :] = C_BAR_DARK; a[2:14, 1:w - 1] = C_BAR
    a[1, 0] = a[1, w - 1] = a[14, 0] = a[14, w - 1] = 0
    x = 3
    for part, let in zip(label, letter):
        if let:
            a[2:14, x:x + 12] = np.where(button_icon(let) > 0, button_icon(let), a[2:14, x:x + 12]); x += 14
        m = text(part)[2:15]
        put(a, m, x, 2, C_WHITE)
        x += m.shape[1] + 6
    assert x - 6 + 3 <= w, (label, x)
    return a


def banner(label):
    """the DS's bar over the touch screen: 256 x 16, the label between two arrows"""
    a = np.zeros((16, 256), np.uint8)
    a[0:16, 8:248] = C_LIGHT
    a[1:15, 9:247] = C_BAR_DARK; a[2:14, 10:246] = C_BAR
    for x0 in (14, 236):
        for i in range(5):
            a[5 + i, x0 + i:x0 + 9 - i] = C_WHITE
    m = text(label)[1:15]
    put(a, m, 128 - m.shape[1] // 2, 1, C_WHITE)
    return a


def crosshair():
    """the touch's lines across the picture (64 x 8, 8 x 64: one pixel wide)
    and its square (8 x 8)"""
    h = np.zeros((8, 64), np.uint8); h[0, :] = C_BLUE
    v = np.zeros((64, 8), np.uint8); v[:, 0] = C_BLUE
    sq = np.zeros((8, 8), np.uint8); sq[0, :7] = sq[6, :7] = sq[:7, 0] = sq[:7, 6] = C_BLUE
    sq[1:6, 1:6] = 0
    return h, v, sq


def finger_box():
    """the square round the finger the cross is on: 16 x 16, red"""
    a = np.zeros((16, 16), np.uint8)
    a[0, :] = a[15, :] = a[:, 0] = a[:, 15] = C_RED
    a[1, 1:15] = a[14, 1:15] = a[1:15, 1] = a[1:15, 14] = C_DARK_RED
    return a


def brush():
    """where the powder falls: 16 x 16, a ring"""
    yy, xx = np.mgrid[0:16, 0:16]
    r = np.hypot(xx - 7.5, yy - 7.5)
    a = np.zeros((16, 16), np.uint8)
    a[(r >= 5.5) & (r <= 7.4)] = C_DARK
    a[(r >= 6.0) & (r <= 6.9)] = C_WHITE
    a[7:9, 7:9] = C_WHITE
    return a


def corner():
    """a corner of the marks round a print found: 8 x 8, the top left one"""
    a = np.zeros((8, 8), np.uint8)
    a[0:2, 0:8] = C_RED; a[0:8, 0:2] = C_RED
    return a


def digits():
    """the counter's digits, an LCD's segments: 10 x (16 x 8)"""
    seg = {'a': (1, 1, 6, 2), 'b': (5, 1, 7, 8), 'c': (5, 8, 7, 15), 'd': (1, 13, 6, 15),
           'e': (0, 8, 2, 15), 'f': (0, 1, 2, 8), 'g': (1, 7, 6, 9)}
    on = ['abcdef', 'bc', 'abged', 'abgcd', 'fgbc', 'afgcd', 'afgedc', 'abc', 'abcdefg', 'abfgcd']
    out = []
    for d in range(10):
        a = np.full((16, 8), 0, np.uint8)
        for k, (x0, y0, x1, y1) in seg.items():
            a[y0:y1, x0:x1] = C_LCD if k in on[d] else 0
        out.append(a)
    return out


def cross():
    a = np.zeros((8, 8), np.uint8)
    a[3, 0:7] = C_RED; a[0:7, 3] = C_RED
    a[2, 2:5] = a[4, 2:5] = 0
    a[2, 3] = a[4, 3] = C_RED
    for (y, x) in ((2, 2), (2, 4), (4, 2), (4, 4)):
        a[y, x] = C_DARK_RED
    return a


def scan_bar():
    """the comparison's sweep: 16 rows of red, fading up (64 x 16)"""
    a = np.zeros((16, 64), np.uint8)
    for y in range(16):
        a[y, :] = C_SCAN if y % 3 != 2 or y > 11 else C_RED
        if y < 6:
            a[y, (np.arange(64) + y) % (7 - y) != 0] = 0
    return a


def big_text(s):
    """the result, in the DS font doubled, white with a black edge"""
    m = text(s)[1:15]
    m2 = np.kron(m, np.ones((2, 2), np.uint8))
    h, w = m2.shape
    a = np.zeros((h + 4, w + 4), np.uint8)
    from dsfont import outline
    big = np.zeros((h + 4, w + 4), bool); big[2:-2, 2:-2] = m2 > 0
    o = outline(big)
    o2 = np.zeros_like(o)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            o2 |= np.roll(np.roll(o, dy, 0), dx, 1)
    a[o2 & ~big] = C_BLACK
    a[big] = C_WHITE
    return a


# the comparison screen (BG3, 256 colours): the DS's top screen's panels,
# meter and counter above, its touch screen's card below
LEFT_PRINT = (1, 1)                     # tiles: the prints' 9 x 12 (72 x 96, the DS's at 3/4)
RIGHT_PRINT = (20, 1)
PRINT_TW, PRINT_TH = 9, 12
CARD_ROW = 14                           # the card: rows 14-19, all 30 columns
METER_X, METER_W, METER_BOTTOM = 110, 20, 86
SEGMENTS = 16
DIGITS_XY = (112, 90)
FACE_XY = (20, 116)
PAL_BASE, PAL_METER, PAL_CARD, PAL_LEFT, PAL_RIGHT = 32, 192, 208, 224, 240
PAL_CROSS = PAL_METER - 1               # the matched points' crosses, drawn into the prints
CROSS_RGB = (232, 24, 24)
# the card's colours (BG 208-223)
CARD = [(152, 128, 88), (176, 152, 104), (120, 48, 0), (88, 32, 0), (248, 248, 248), (200, 200, 200),
        (128, 128, 128), (56, 56, 56), (248, 168, 40), (152, 192, 144), (168, 208, 160), (48, 56, 48),
        (16, 16, 16), (136, 184, 136), (96, 88, 72), (232, 232, 232)]
K_TAN, K_TAN2, K_TAB, K_TAB_DARK, K_WHITE, K_LIGHT, K_GREY, K_BAR, K_NAME, K_GREEN, K_GREEN2, K_INK, \
    K_BLACK, K_STATUS, K_EDGE, K_PALE = range(16)
STATUS = ['Comparing', 'Comparing.', 'Comparing..', 'Comparing...', 'Comparison complete.']


def frame_rgb():
    """the comparison screen without its prints and card: 160 x 240 RGB"""
    a = np.zeros((GBA_H, GBA_W, 3), np.uint8)
    for y in range(GBA_H):
        a[y] = (128, 112, 88) if y % 3 == 1 else (96, 88, 72)
    def box(x0, y0, x1, y1, c):
        a[y0:y1, x0:x1] = c
    for (px, py) in (LEFT_PRINT, RIGHT_PRINT):
        x0, y0 = px * 8, py * 8
        x1, y1 = x0 + PRINT_TW * 8, y0 + PRINT_TH * 8
        box(x0 - 4, y0 - 4, x1 + 3, y1 + 3, (232, 232, 232))
        box(x0 - 3, y0 - 3, x1 + 2, y1 + 2, (248, 248, 248))
        box(x0 - 1, y0 - 1, x1 + 1, y1 + 1, (200, 200, 200))
        box(x0, y0, x1, y1, (0, 0, 0))
        for x in range(x0, x1, 4):          # the rulers
            a[y0 - 3:y0 - 2 if x % 16 else y0 - 1, x] = (96, 96, 96)
        for y in range(y0, y1, 4):
            a[y, x0 - 3:x0 - 2 if y % 16 else x0 - 1] = (96, 96, 96)
        mx, my = x0 + PRINT_TW * 4, y0 + PRINT_TH * 4
        a[y0 - 3, mx - 2:mx + 3] = (40, 40, 40); a[y0 - 2, mx - 1:mx + 2] = (40, 40, 40)
        a[my - 2:my + 3, x0 - 3] = (40, 40, 40); a[my - 1:my + 2, x0 - 2] = (40, 40, 40)
    # the meter's column and the counter's window
    box(METER_X - 3, 5, METER_X + METER_W + 3, METER_BOTTOM + 3, (200, 200, 200))
    box(METER_X - 2, 6, METER_X + METER_W + 2, METER_BOTTOM + 2, (64, 72, 80))
    box(DIGITS_XY[0] - 5, DIGITS_XY[1] - 2, DIGITS_XY[0] + 21, DIGITS_XY[1] + 18, (200, 200, 200))
    box(DIGITS_XY[0] - 4, DIGITS_XY[1] - 1, DIGITS_XY[0] + 20, DIGITS_XY[1] + 17, (136, 200, 152))
    return a


def segment_rect(i):
    y1 = METER_BOTTOM - 5 * i
    return METER_X, y1 - 4, METER_X + METER_W, y1


def segment_colours(i, lit, full):
    """a meter segment (0 the lowest): the DS's dark red top five and dark
    slate others, lit pale (the top five orange at a match)"""
    top = i >= SEGMENTS - 5
    if not lit:
        return (112, 0, 40) if top else (40, 56, 72)
    return (248, 120, 32) if top and full else (216, 224, 240)


def card(person=None, status=None):
    """the card's rows (48 x 240, colours CARD): a person's or a status line"""
    a = np.full((48, GBA_W), K_TAN, np.uint8)
    a[::3] = K_TAN2
    # the arrows' tabs
    for x0, d in ((0, -1), (228, 1)):
        a[6:42, x0:x0 + 12] = K_TAB_DARK; a[7:41, x0 + 1:x0 + 11] = K_TAB
        for i in range(5):
            if d < 0:
                a[19 + i:29 - i, x0 + 8 - i] = K_WHITE
            else:
                a[19 + i:29 - i, x0 + 3 + i] = K_WHITE
    if status is not None:
        a[8:40, 14:226] = K_LIGHT; a[9:39, 15:225] = K_STATUS
        m = text(STATUS[status])[1:15]
        put(a, m, 120 - m.shape[1] // 2, 17, K_INK)
        return a
    # the face's frame (the face is a sprite), the name bar, the details
    a[1:47, 14:62] = K_LIGHT; a[2:46, 15:61] = K_GREY
    a[1:47, 64:226] = K_LIGHT
    a[2:16, 65:225] = K_BAR
    a[16:46, 65:225] = K_GREEN; a[17:46:3, 65:225] = K_GREEN2
    if person is not None:
        name, age, gender, _ = PEOPLE[person]
        m = text(name)[1:15]
        put(a, m, 145 - m.shape[1] // 2, 2, K_NAME)
        put(a, text('Age: %d' % age)[1:15], 70, 17, K_INK)
        put(a, text('Gender: %s' % gender)[1:15], 70, 31, K_INK)
    return a


def compare_screen():
    """(the base as 160 x 240 colour indices, its palette (index -> RGB) for
    32-207): the frame quantized to 160 colours, the meter's segments their
    own (192-207), the card's rows and prints left to the cards and prints"""
    from PIL import Image
    rgb = frame_rgb()
    top = rgb[:CARD_ROW * 8]
    q = Image.fromarray(top).quantize(colors=PAL_CROSS - PAL_BASE, method=Image.MEDIANCUT, dither=Image.NONE)
    idx = np.array(q, np.uint8) + PAL_BASE
    pal = (q.getpalette() + [0] * 768)[:3 * (PAL_CROSS - PAL_BASE)]
    out = np.zeros((GBA_H, GBA_W), np.uint8)
    out[:CARD_ROW * 8] = idx
    for i in range(SEGMENTS):
        x0, y0, x1, y1 = segment_rect(i)
        out[y0:y1, x0:x1] = PAL_METER + i
    for (px, py), base in ((LEFT_PRINT, PAL_LEFT), (RIGHT_PRINT, PAL_RIGHT)):
        out[py * 8:(py + PRINT_TH) * 8, px * 8:(px + PRINT_TW) * 8] = base    # (black until a print)
    out[CARD_ROW * 8:] = card() + PAL_CARD
    colours = {PAL_BASE + k: tuple(pal[3 * k:3 * k + 3]) for k in range(PAL_CROSS - PAL_BASE)}
    colours[PAL_CROSS] = CROSS_RGB
    for i in range(SEGMENTS):
        colours[PAL_METER + i] = segment_colours(i, False, False)
    for k, c in enumerate(CARD):
        colours[PAL_CARD + k] = c
    return out, colours


def mock(case, person, comparing=False, count=8):
    """a picture of the comparison screen (for checking the layout)"""
    out, colours = compare_screen()
    pal = np.zeros((256, 3), np.uint8)
    for k, c in colours.items():
        pal[k] = c
    pr = prints(); pp = print_palette()
    left = small_print(pr[person_print()[ANSWER[case]]])
    right = small_print(pr[person_print()[person]])
    for (px, py), base, img in ((LEFT_PRINT, PAL_LEFT, left), (RIGHT_PRINT, PAL_RIGHT, right)):
        out[py * 8:(py + PRINT_TH) * 8, px * 8:(px + PRINT_TW) * 8] = base + img
    for k in range(16):
        pal[PAL_RIGHT + k] = pp[k]
        pal[PAL_LEFT + k] = pp[k] if not comparing else green(pp[k])
    for i in range(SEGMENTS):
        pal[PAL_METER + i] = segment_colours(i, i < count, count >= 16)
    out[CARD_ROW * 8:] = PAL_CARD + (card(status=1) if comparing else card(person))
    img = pal[out]
    # the sprites: the face, the counter
    if not comparing:
        px, fpal = face(PEOPLE[person][3])
        img[FACE_XY[1]:FACE_XY[1] + 40, FACE_XY[0]:FACE_XY[0] + 40] = np.array(fpal, np.uint8)[px[:40, :40]]
    ui = np.array([(0, 0, 0)] + UI[1:], np.uint8)
    for k, dgt in enumerate((count // 10, count % 10)):
        d = digits()[dgt]
        ys, xs = np.nonzero(d)
        img[ys + DIGITS_XY[1], xs + DIGITS_XY[0] + 8 * k] = ui[d[ys, xs]]
    return img


def small_print(img):
    """a print (128 x 96 greys) at 3/4: 96 x 72, by area"""
    from PIL import Image
    im = Image.fromarray((img * 17).astype(np.uint8)).resize((PRINT_TW * 8, PRINT_TH * 8), Image.BOX)
    return np.clip((np.array(im).astype(int) + 8) // 17, 0, 15).astype(np.uint8)


def green(c):
    """the found print as the dusted one: its dark ridges the powder's white,
    the light between the DS's green"""
    t = (c[0] + c[1] + c[2]) / (3 * 248)
    hi, lo = (232, 240, 232), (0, 128, 24)
    return tuple(int(round(hi[k] * (1 - t) + lo[k] * t)) for k in range(3))


# ---------------------------------------------------------------- the output
def rgb5(c):
    return (c[0] >> 3) | (c[1] >> 3) << 5 | (c[2] >> 3) << 10


def tiles4(img):
    """(h, w) 4-bit pixels -> 4bpp tiles, row by row"""
    h, w = img.shape
    out = bytearray()
    for ty in range(h // 8):
        for tx in range(w // 8):
            for row in img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]:
                for x in range(0, 8, 2):
                    out.append(int(row[x]) | int(row[x + 1]) << 4)
    return bytes(out)


def tiles8(img):
    h, w = img.shape
    out = bytearray()
    for ty in range(h // 8):
        for tx in range(w // 8):
            out += bytes(img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].astype(np.uint8).reshape(-1))
    return bytes(out)


def bits(plane):
    """160 x 240 bools -> 30 bytes a row, pixel x in bit x & 7 of byte x >> 3"""
    out = bytearray()
    for row in plane:
        for x in range(0, GBA_W, 8):
            out.append(sum(1 << k for k in range(8) if row[x + k]))
    return bytes(out)


# GBA sprite shapes: (w, h) -> (shape, size)
OBJ_SIZES = {(8, 8): (0, 0), (16, 16): (0, 1), (32, 32): (0, 2), (64, 64): (0, 3),
             (16, 8): (1, 0), (32, 8): (1, 1), (32, 16): (1, 2), (64, 32): (1, 3),
             (8, 16): (2, 0), (8, 32): (2, 1), (16, 32): (2, 2), (32, 64): (2, 3)}


def pieces(img):
    """a sprite image -> [(dx, dy, w, h)] of GBA sizes covering it (left to right)"""
    h, w = img.shape
    widths = {8: (32, 16, 8), 16: (32, 16, 8), 32: (64, 32, 16, 8), 64: (64, 32, 8)}[h]
    out, x = [], 0
    while x < w:
        pw = next(pw for pw in widths if pw <= w - x)
        out.append((x, 0, pw, h)); x += pw
    return out


class SpriteSet:
    """a set of sprites loaded together: their tiles, one after another, and
    their pieces"""
    def __init__(self, name):
        self.name, self.tiles, self.sprites = name, bytearray(), []

    def add(self, key, img, parts=None):
        parts = parts or pieces(img)
        first = len(self.sprites) and sum(len(p) for _, p in self.sprites)
        rec = []
        for dx, dy, w, h in parts:
            rec.append((dx, dy, OBJ_SIZES[(w, h)], len(self.tiles) // 32))
            self.tiles += tiles4(img[dy:dy + h, dx:dx + w])
        self.sprites.append((key, rec))


def stamp_points(st):
    """the dots of a stamp, from its middle, at the GBA's scale"""
    ys, xs = np.nonzero(st)
    dx = np.round((xs - STAMP_SIZE / 2 + 0.5) * SCALE).astype(int)
    dy = np.round((ys - STAMP_SIZE / 2 + 0.5) * SCALE).astype(int)
    return list(zip(dx, dy))


def face_sprite(off):
    """a card's face: 64 x 64 4bpp, the face's 40 x 40 (and its grey) at the
    top left, colour 0 clear: (tiles, 16 colours)"""
    px, pal = face(off)
    sub = px[:40, :40]
    used = sorted(set(sub.reshape(-1).tolist()), key=lambda i: -int((sub == i).sum()))
    while len(used) > 15:                   # (merge the least used into its nearest)
        last = used.pop()
        near = min(used, key=lambda i: sum((a - b) ** 2 for a, b in zip(pal[i], pal[last])))
        sub = np.where(sub == last, near, sub)
    remap = {c: k + 1 for k, c in enumerate(used)}
    img = np.zeros((64, 64), np.uint8)
    img[:40, :40] = np.vectorize(remap.get)(sub)
    cols = [(0, 0, 0)] + [pal[c] for c in used] + [(0, 0, 0)] * (15 - len(used))
    return tiles4(img), cols


def main():
    blob = bytearray()
    defs, h = [], []
    def add(name, data, align=4):
        while len(blob) % align:
            blob.append(0)
        defs.append('#define EN_FP_%s 0x%X' % (name, len(blob)))
        blob.extend(data)
    # the fingers' planes
    ms = masks()
    mrec = []
    for i, m in enumerate(ms):
        prt, cnt, ring, need = finger_planes(m)
        o = len(blob); blob.extend(bits(prt)); blob.extend(bits(cnt)); blob.extend(bits(ring))
        r = m['rects'][-1]
        x0, y0 = DUST_X + int(r['x'] * SCALE), int(r['y'] * SCALE)
        x1, y1 = DUST_X + int(np.ceil((r['x'] + r['w']) * SCALE)), min(GBA_H, int(np.ceil((r['y'] + r['h']) * SCALE)))
        mrec.append((o, need, x0, y0, x1 - x0, y1 - y0))
    # the stamps
    so = []
    for st in stamps():
        pts = stamp_points(st)
        while len(blob) % 2:
            blob.append(0)
        so.append((len(blob), len(pts)))
        blob.extend(b''.join(struct.pack('<bb', x, y) for x, y in pts))
    # the prints at 3/4, 4bpp in BG tiles
    pr = prints()
    add('PRINTS', b''.join(tiles4(small_print(p)) for p in pr))
    # the faces
    fdata = b''
    for person in PEOPLE:
        t, cols = face_sprite(person[3])
        fdata += struct.pack('<16H', *[rgb5(c) for c in cols]) + t
    add('FACES', fdata)
    # the cards: the people, the status lines, the results
    cards = [card(person=k) for k in range(len(PEOPLE))] + [card(status=k) for k in range(len(STATUS))]
    for res in ('Match found.', 'No matches found.'):
        # (a banner the card's width, no arrows: the doubled words need it)
        c = np.full((48, GBA_W), K_TAN, np.uint8)
        c[::3] = K_TAN2
        c[6:42, 2:238] = K_LIGHT; c[7:41, 3:237] = K_STATUS
        t = big_text(res)
        tw = t.shape[1]
        reg = c[24 - t.shape[0] // 2:24 - t.shape[0] // 2 + t.shape[0], 120 - tw // 2:120 - tw // 2 + tw]
        reg[t == C_WHITE] = K_WHITE; reg[t == C_BLACK] = K_BLACK
        cards.append(c)
    # a blank one, under the text box while the script talks over the screen
    c = np.full((48, GBA_W), K_TAN, np.uint8)
    c[::3] = K_TAN2
    cards.append(c)
    add('CARDS', b''.join(tiles4(c) for c in cards))
    # the comparison screen's top rows, 256 colours, and its palette
    base, colours = compare_screen()
    add('COMPARE_TILES', tiles8(base[:CARD_ROW * 8]))
    pal = [0] * 256
    for k, c in colours.items():
        pal[k] = rgb5(c)
    add('COMPARE_PAL', struct.pack('<256H', *pal))
    # the sprites, in three sets
    sets = []
    sel = SpriteSet('SELECT')
    sel.add('BANNER', banner('Select which finger to examine'))
    hl, vl, sq = crosshair()
    hline = np.zeros((32, 64), np.uint8); hline[0, :] = C_BLUE
    vline = np.zeros((64, 32), np.uint8); vline[:, 0] = C_BLUE
    sel.add('HLINE', hline, [(0, 0, 64, 32)])
    sel.add('VLINE', vline, [(0, 0, 32, 64)])
    sel.add('SQUARE', sq, [(0, 0, 8, 8)])
    sel.add('BOX', finger_box(), [(0, 0, 16, 16)])
    sel.add('BACK', tab(['Back'], ['B']))
    sel.add('EXAMINE', tab(['Examine'], ['A']))
    sets.append(sel)
    dust = SpriteSet('DUST')
    dust.add('BANNER', banner('Spread the powder and blow'))
    dust.add('BACK', tab(['Back'], ['B']))
    dust.add('POWDER', tab(['Powder', 'Blow'], ['A', 'R']))
    dust.add('BRUSH', brush(), [(0, 0, 16, 16)])
    dust.add('CORNER', corner(), [(0, 0, 8, 8)])
    sets.append(dust)
    cmp_ = SpriteSet('COMPARE')
    for k, dg in enumerate(digits()):
        cmp_.add('DIGIT%d' % k, dg, [(0, 0, 8, 16)])
    bar = scan_bar()
    cmp_.add('SCAN', np.concatenate([bar[:, :64], bar[:, :8]], 1), [(0, 0, 32, 16), (32, 0, 32, 16), (64, 0, 8, 16)])
    cmp_.add('COMPARE', tab(['Compare'], ['A']))
    sets.append(cmp_)
    piece_lines = []
    for st in sets:
        add('SET_%s' % st.name, bytes(st.tiles))
        defs.append('#define EN_FP_SET_%s_TILES %d' % (st.name, len(st.tiles) // 32))
        for key, rec in st.sprites:
            defs.append('#define EN_FP_%s_%s %d     // %d piece(s)' % (st.name, key, len(piece_lines), len(rec)))
            for k, (dx, dy, (shape, size), tile) in enumerate(rec):
                piece_lines.append('    { %d, %d, %d, %d, %d, %d },' % (dx, dy, shape, size, tile, k == len(rec) - 1))
    # (OBJ tiles 0x1A0-0x27F; the comparison's face after its set)
    assert max(len(st.tiles) // 32 for st in sets) <= 224 and len(cmp_.tiles) // 32 + 64 <= 224, \
        [len(st.tiles) // 32 for st in sets]
    defs.append('#define EN_FP_FACE_TILE %d     // after the comparison\'s set' % (len(cmp_.tiles) // 32))
    os.makedirs(os.path.join(ROOT, 'graphics', 'en', 'rfta'), exist_ok=True)
    open(os.path.join(ROOT, 'graphics', 'en', 'rfta', 'fingerprint.bin'), 'wb').write(blob)
    asm = ['@ generated by tools/en/rfta/fingerprint.py: the fingerprints\' pictures and planes',
           '\t.section rfta_low, "a"', '\t.align 2', '\t.global gEnFingerprintGfx', 'gEnFingerprintGfx:',
           '\t.incbin "graphics/en/rfta/fingerprint.bin"']
    open(os.path.join(ROOT, 'data', 'rfta', 'fingerprint.s'), 'w').write('\n'.join(asm) + '\n')
    # the tables
    h = ['// generated by tools/en/rfta/fingerprint.py: the fingerprints, from the DS',
         '// (the fingers\' picture as the GBA cuts it; the dusting screen the DS\'s touch',
         '// screen at 10/11, from x %d; the comparison\'s prints at 3/4)' % DUST_X]
    h += defs
    h.append('#define EN_FP_DUST_X %d' % DUST_X)
    h.append('#define EN_FP_LEFT_PRINT_X %d' % LEFT_PRINT[0])
    h.append('#define EN_FP_LEFT_PRINT_Y %d' % LEFT_PRINT[1])
    h.append('#define EN_FP_RIGHT_PRINT_X %d' % RIGHT_PRINT[0])
    h.append('#define EN_FP_RIGHT_PRINT_Y %d' % RIGHT_PRINT[1])
    h.append('#define EN_FP_PRINT_TW %d' % PRINT_TW)
    h.append('#define EN_FP_PRINT_TH %d' % PRINT_TH)
    h.append('#define EN_FP_CARD_ROW %d' % CARD_ROW)
    h.append('#define EN_FP_CARD_STATUS %d      // the cards: the people, then the status lines, then the results' % len(PEOPLE))
    h.append('#define EN_FP_CARD_MATCH %d' % (len(PEOPLE) + len(STATUS)))
    h.append('#define EN_FP_CARD_NO_MATCH %d' % (len(PEOPLE) + len(STATUS) + 1))
    h.append('#define EN_FP_CARD_BLANK %d' % (len(PEOPLE) + len(STATUS) + 2))
    h.append('#define EN_FP_PEOPLE %d' % len(PEOPLE))
    h.append('#define EN_FP_SEGMENTS %d' % SEGMENTS)
    h.append('#define EN_FP_DIGITS_X %d' % DIGITS_XY[0])
    h.append('#define EN_FP_DIGITS_Y %d' % DIGITS_XY[1])
    h.append('#define EN_FP_FACE_X %d' % FACE_XY[0])
    h.append('#define EN_FP_FACE_Y %d' % FACE_XY[1])
    h.append('#define EN_FP_PAL_METER %d' % PAL_METER)
    h.append('#define EN_FP_PAL_CROSS %d' % PAL_CROSS)
    h.append('#define EN_FP_PAL_CARD %d' % PAL_CARD)
    h.append('#define EN_FP_PAL_LEFT %d' % PAL_LEFT)
    h.append('#define EN_FP_PAL_RIGHT %d' % PAL_RIGHT)
    h.append('static const struct EnFpPiece sEnFpPieces[] = {')
    h += piece_lines
    h.append('};')
    h.append('static const u16 sEnFpUiPalette[16] = { %s };' % ', '.join('0x%04X' % rgb5(c or (0, 0, 0)) for c in UI))
    h.append('static const u16 sEnFpDustPalette[16] = { %s };' % ', '.join('0x%04X' % rgb5(c) for c in DUST))
    pp = print_palette()
    h.append('static const u16 sEnFpPrintPalette[16] = { %s };' % ', '.join('0x%04X' % rgb5(c) for c in pp))
    h.append('static const u16 sEnFpGreenPalette[16] = { %s };   // the found print as dusted' %
             ', '.join('0x%04X' % rgb5(green(c)) for c in pp))
    segs = []
    for i in range(SEGMENTS):
        segs.append([rgb5(segment_colours(i, lit, full)) for lit, full in ((False, False), (True, False), (True, True))])
    h.append('static const u16 sEnFpSegment[%d][3] = { %s };   // dark, lit, lit at a match' %
             (SEGMENTS, ', '.join('{ 0x%04X, 0x%04X, 0x%04X }' % tuple(s) for s in segs)))
    h.append('static const struct EnFpStamp sEnFpStamps[4] = { %s };' % ', '.join('{ 0x%X, %d }' % s for s in so))
    h.append('static const struct EnFpMask sEnFpMasks[%d] = {' % len(mrec))
    for i, (o, need, x, y, w, hh) in enumerate(mrec):
        h.append('    { .planes = 0x%X, .need = %d, .x = %d, .y = %d, .w = %d, .h = %d }, // DS %d' % (o, need, x, y, w, hh, i))
    h.append('};')
    cs = cases()
    pts = points()
    for c, case in enumerate(cs):
        h.append('static const struct EnFpFinger sEnFpFingers%d[%d] = {' % (c, len(case['fingers'])))
        for f in case['fingers']:
            q = ', '.join('%d, %d' % (x - PICTURE_DX, y - PICTURE_DY) for x, y in f['quad'])
            h.append('    { .quad = { %s }, .x = %d, .y = %d, .type = %d, .mask = %d },' %
                     (q, f['square'][0] - PICTURE_DX, f['square'][1] - PICTURE_DY, f['type'], f['mask']))
        h.append('};')
    h.append('static const struct EnFpCase sEnFpCases[%d] = {' % len(cs))
    for c, case in enumerate(cs):
        h.append('    { .bg = 0x%02X, .count = %d, .answer = %d, .fingers = sEnFpFingers%d,' %
                 (case['bg'], len(case['fingers']), ANSWER[c], c))
        h.append('      .points = { %s } },' % ', '.join('{ %d, %d }' % (x * 3 // 4, y * 3 // 4) for x, y in pts[c]))
    h.append('};')
    h.append('static const u8 sEnFpPersonPrint[%d] = { %s };' % (len(PEOPLE), ', '.join(str(v) for v in person_print())))
    from sfx import NEW_SES
    h.append('#define EN_FP_SE_SCAN %d       // the DS\'s SE0C6, a point counted' % NEW_SES[0x1A6])
    h.append('#define EN_FP_SE_MATCH %d      // SE0C0' % NEW_SES[0x1A0])
    open(os.path.join(ROOT, 'src', 'data', 'en_rfta_fingerprint.h'), 'w').write('\n'.join(h) + '\n')
    print('%d bytes; sets %s tiles' % (len(blob), [len(st.tiles) // 32 for st in sets]))


def preview(out):
    from PIL import Image
    os.makedirs(out, exist_ok=True)
    ms = masks()
    for i, m in enumerate(ms):
        prt, cnt, ring, need = finger_planes(m)
        im = np.zeros((GBA_H, GBA_W, 3), np.uint8)
        im[..., 1] = 100
        im[prt] = (240, 240, 240)
        im[cnt & ~prt] = (255, 0, 0)
        im[ring] = (255, 200, 0)
        Image.fromarray(im).save(os.path.join(out, 'mask_%02d.png' % i))
        print(i, m['type'], [(r['x'], r['y'], r['w'], r['h'], hex(r['need'])) for r in m['rects']],
              'print', prt.sum(), 'counted', cnt.sum(), 'need', need, 'ring', ring.sum())
    for c, cs in enumerate(cases()):
        print('case', c, hex(cs['bg']), [(f['type'], f['mask'], f['square'], f['quad']) for f in cs['fingers']])
    print('person print', person_print())
    print('points', points())
    from PIL import Image
    shots = [mock(0, 4), mock(0, 0), mock(1, 2, True, 12)]
    W = np.zeros((GBA_H, (GBA_W + 4) * len(shots), 3), np.uint8)
    for k, im in enumerate(shots):
        W[:, k * (GBA_W + 4):k * (GBA_W + 4) + GBA_W] = im
    Image.fromarray(W).resize((W.shape[1] * 2, W.shape[0] * 2), Image.NEAREST).save(os.path.join(out, 'compare.png'))
    ui = np.array([(255, 0, 255)] + UI[1:], np.uint8)
    parts = [banner('Select which finger to examine'), banner('Spread the powder and blow'),
             tab(['Back'], ['B']), tab(['Examine'], ['A']), tab(['Powder', 'Blow'], ['A', 'R']),
             tab(['Compare'], ['A']), big_text('Match found.'), big_text('No matches found.')]
    h = sum(p.shape[0] + 4 for p in parts)
    W = np.zeros((h, 256), np.uint8); y = 0
    for p in parts:
        W[y:y + p.shape[0], :p.shape[1]] = p; y += p.shape[0] + 4
    Image.fromarray(ui[W]).resize((512, 2 * h), Image.NEAREST).save(os.path.join(out, 'ui.png'))


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--preview':
        preview(sys.argv[2])
    else:
        main()
