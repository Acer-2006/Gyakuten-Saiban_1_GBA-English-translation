#!/usr/bin/env python3
"""The Blue Badger angle (the DS's 74 8 33: the final day's trial, the
Unstable Jar turned until it looks like the Blue Badger), from the DS, for
evidence3d.py (which carries the jar's model and writes this data with the
viewer's).

What the DS does (its process 20: 0x0207b220, its steps 0x0207af30 (set
up), 0x0207a764 (the player's turn), 0x0207a4dc (the result), its drawing
0x0207a1ec; its state at 0x02318ff0-0x02319160):
- the touch screen fades out (2, 3, 1) and comes back (1, 1, 1) as a panel:
  the jar whole (object record 17, itm05a0) drawn in a 128 x 128 viewport
  at (64, 20) under the 3D viewer's camera (20 back), the model 2 further
  (its matrix the rotation, then 2 toward the back), fovy 53 degrees
  (entry 302 of the sine table, 0x020a2468 + 0xb8); round it a white ring
  with 16 ticks (the texture eff060, 128 x 128) turned by the roll; on the
  right and under it two drums whose ticks (16, 12: angles 11 and 15
  degrees apart from 270) run round as the jar is dragged, along the drum's
  bow (0x020c95a8, 0x020c9454); on the left the roll's two buttons; above,
  Present;
- the jar starts upright (the identity); the + pad held turns it 2 degrees
  a frame about the screen's upright (left, right) and across (up, down),
  L and R held 1 a frame about the line of sight (the roll), each turn
  applied after the jar's own (M = M x R(d)) and the matrix kept square;
  the turns' sines and cosines are the table's entries 22 and 11 (the
  degrees to a 4096th of a turn, cut short): 1.934 and 0.967 degrees;
- Present (X, or the button) reads the angles off the matrix
  (0x02067dac): a = atan2(-y, sqrt(x^2 + z^2)) and b = atan2(x, z) of
  (0, 0, 1) turned, then c = atan2(y, x) of (1, 0, 0) under the matrix
  turned back by b and a; the right angle is a in (300, 320) degrees, b in
  (350, 359) or [0, 10), c in (175, 185);
- then both screens go white (3, 1, 4), "Take that!" (SE 0x37) with
  Phoenix's picture sliding in over speed lines, 61 frames, the fade out
  and in, and section BD (the right angle) or BC (not yet).

On the GBA (en_evidence3d.c, the viewer's renderer and screen) the panel is
the DS's touch screen from (8, 12): the circle and the jar at the DS's size,
the drums, the roll's buttons with L and R, "A Present" over the circle; the
+ pad and L and R turn the jar as the DS's do (the drums' ticks run with
the + pad as they do with the DS's drag); A presents. The DS's "Take
that!" is the GBA's (the bubble over Phoenix on the speed lines, the
script's: translate.py), between the white and the next section."""
import os, sys, struct, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import dsbin
from dsdata import data

RECORD = 17                               # the DS's object record: itm05a0, the jar whole
SINCOS = 0x020a2068                       # the DS's sine and cosine table (4096 pairs)
FOV_ENTRY = 0x100 + 0xb8 // 4             # the projection's: fovy / 2
DISTANCE = 22                             # the viewer's camera 20 back, the jar 2 behind its place
VIEWPORT = (64, 20, 128)                  # x, y, size on the DS's touch screen (its 0x04000580: 0xacc02c40)
CROP = (8, 12)                            # the GBA's screen: the touch screen from here
RING_TEXTURE = 0x02daf168                 # eff060: the ring's ticks, 128 x 128, 16 colours
CURVE_H, CURVE_V = 0x020c95a8, 0x020c9454  # the drums' bows (80, 48 bytes)
TICKS_H = [(270 + 11 * k) % 360 for k in range(16)]   # (the DS works them out as it starts: 0x0207b098)
TICKS_V = [(270 + 15 * k) % 360 for k in range(12)]
DRUM_H = dict(radius=79, middle=124, offset=8)        # x = middle + r sin, y = bow[r - |r sin|] + offset
DRUM_V = dict(radius=47, middle=80, offset=-8)        # y = middle + r sin, x = bow[...] + offset
TURN, ROLL = 2, 1                          # degrees a frame: the + pad, L and R (the DS's sine
                                           # table's entry for them: n * 65536 / 360 >> 4, 22 and 11:
                                           # 1.934 and 0.967 degrees a frame in fact)
CHECK = dict(a=(300, 320), b=((350, 359), (0, 10)), c=(175, 185))   # (open ranges but b's [0, 10))
SECTION_RIGHT, SECTION_WRONG = 0xBD, 0xBC
SE_TAKE_THAT = 0x37

# the panel (the DS's colours, read off its screen)
WOOD, WOOD_LIGHT = (96, 88, 72), (128, 112, 88)
BOX, BOX_DARK, BOX_LIGHT = (104, 80, 48), (96, 72, 48), (136, 120, 96)
GRID_BG, GRID_LINE, GRID_CROSS = (120, 120, 120), (152, 152, 152), (168, 168, 168)
RING, RING_IN, RING_OUT = (224, 224, 224), (192, 192, 192), (144, 144, 144)
RING_R0, RING_R1 = 57, 63                 # the ring's inside and outside (the circle's middle at the viewport's)
BLACK, EDGE = (16, 16, 16), (144, 144, 144)
DRUM_BODY, DRUM_RIM, DRUM_LIGHT, DRUM_SHADE = (224, 224, 224), (208, 208, 208), (248, 248, 248), (168, 160, 160)
DRUM_SIDE = (192, 192, 192)
WHITE, DARK = (248, 248, 248), (64, 64, 64)
BTN, BTN_DARK, BTN_LIGHT, BTN_EDGE, BTN_LOW, BTN_SHADE = (120, 48, 0), (112, 40, 0), (160, 120, 88), (152, 88, 56), \
    (104, 40, 0), (96, 32, 0)
TICK = [(240, 240, 240), (136, 136, 136), (248, 248, 248), (144, 144, 144)]
# the roll's buttons: their places (x0, y0, x1, y1, the cut corner) and arrows ('W' white, 'b' shade; the DS's)
BUTTONS = [(43, 46, 71, 82, 'top'), (43, 85, 71, 121, 'bottom')]
ARROW_UP = (51, 56, ['....bbWW', '...bbWWW', '..bbWWWW', 'bbWWWW..', 'bWWWWW..', 'bbbWWWWb',
                     '..bWWbWb', '.bWWWbbb', '.bWWbb..', '.bWWb...', '.bWWb...', '.bWWb...', '.bbbb...'])
ARROW_DOWN = (51, 96, ['.bbbb...', '.bWWb...', '.bWWb...', '.bWWb...', '.bWWbb..', '.bWWWbbb', '..bWWbWb',
                       'bbbWWWWb', 'bWWWWWWb', 'bbWWWWWb', '.bbWWWWb', '..bbWWWb', '...bbWWb', '....bbWb',
                       '.....bbb'])
TAB_Y = 0                                 # "A Present" (the GBA's), over the circle's top


def sincos(i):
    return struct.unpack_from('<2h', dsbin.data(), SINCOS - dsbin.BASE + 4 * i)


def projection():
    """the focal length in pixels (the viewport's half times cot(fovy / 2))"""
    s, c = sincos(FOV_ENTRY)
    return VIEWPORT[2] / 2 * c / s


def bows():
    d = dsbin.data()
    return (list(d[CURVE_H - dsbin.BASE:CURVE_H - dsbin.BASE + 80]),
            list(d[CURVE_V - dsbin.BASE:CURVE_V - dsbin.BASE + 48]))


def ring_ticks():
    """eff060: 128 x 128 indices, its 16 colours"""
    d = data()
    fmt, wl, hl, fl, doff, dsz, poff, psz = struct.unpack_from('<4B4I', d, RING_TEXTURE)
    assert fmt == 3 and (8 << wl, 8 << hl) == (128, 128)
    raw = np.frombuffer(d[RING_TEXTURE + doff:RING_TEXTURE + doff + dsz], np.uint8)
    px = np.stack([raw & 15, raw >> 4], 1).reshape(128, 128)
    pal = list(struct.unpack_from('<16H', d, RING_TEXTURE + poff))
    return px, pal


def middle():
    """the circle's middle on the DS's touch screen"""
    x, y, n = VIEWPORT
    return x + n // 2, y + n // 2


def panel():
    """the DS's touch screen as the GBA's shows it, 256 x 192 RGB (the
    circle's inside left as the grid's: the picture's place)"""
    H, V = bows()
    a = np.zeros((192, 256, 3), np.uint8)
    for y in range(192):
        a[y] = WOOD_LIGHT if y % 3 == 0 else WOOD
    # the box, its frame inside
    a[29:139, 0:207] = BOX
    a[28, 0:207] = BOX_DARK; a[29:139, 207] = BOX_LIGHT; a[139, 0:207] = BOX_LIGHT
    a[36, 33:199] = BOX_DARK; a[37:131, 32] = BOX_DARK; a[37:131, 199] = BOX_LIGHT; a[131, 32:199] = BOX_LIGHT
    # the roll's buttons
    for x0, y0, x1, y1, cut in BUTTONS:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                k = (x - x0) + (y - y0 if cut == 'top' else y1 - y)        # (the cut corner's diagonal)
                if k < 9:
                    continue
                edge = min(x - x0, x1 - x, y - y0, y1 - y, k - 9)
                a[y, x] = WHITE if edge == 0 else DARK if edge == 1 else BTN
        for y in range(y0 + 2, y1 - 1):
            for x in range(x0 + 2, x1 - 1):
                k = (x - x0) + (y - y0 if cut == 'top' else y1 - y)
                if k < 11:
                    continue
                if y == y0 + 2:
                    a[y, x] = BTN_LIGHT
                elif y == y1 - 2:
                    a[y, x] = BTN_LOW
                elif x == x0 + 2 or x == x1 - 2 or k == 11:
                    a[y, x] = BTN_DARK
    for x0, y0, rows in (ARROW_UP, ARROW_DOWN):
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch != '.':
                    a[y0 + r, x0 + c] = WHITE if ch == 'W' else BTN_SHADE
    # the circle: the ring, the grid's place inside
    cx, cy = middle()
    yy, xx = np.mgrid[0:192, 0:256]
    r = np.hypot(xx + 0.5 - cx, yy + 0.5 - cy)
    a[(r >= RING_R0) & (r < RING_R1 + 1)] = RING_OUT
    a[(r >= RING_R0) & (r < RING_R1)] = RING
    a[(r >= RING_R0) & (r < RING_R0 + 1)] = RING_IN
    # the right drum: the bracket on its flat side, the body, the rim along its bow
    for y in range(36, 132):
        v = abs(y - 84)
        xr = H_V(V, v)
        a[y, 222] = EDGE; a[y, 223] = BLACK
        a[y, 224:xr - 6] = DRUM_SIDE
        a[y, 224] = DRUM_SHADE
        a[y, xr - 6:xr] = DRUM_RIM
        a[y, xr - 6] = DRUM_LIGHT
        a[y, xr] = EDGE
    a[35, 222:234] = EDGE; a[36, 223:233] = BLACK
    a[132, 222:234] = EDGE; a[131, 223:233] = BLACK
    # the bottom drum
    for x in range(47, 209):
        v = abs(x - 128)
        yb = H_H(H, v)
        a[152, x] = EDGE; a[153, x] = BLACK
        a[154:yb - 7, x] = DRUM_BODY
        a[yb - 7:yb, x] = DRUM_RIM
        a[yb - 7, x] = DRUM_LIGHT
        a[yb, x] = DRUM_SHADE
    a[152:162, 46] = EDGE; a[153:161, 47] = BLACK
    a[152:162, 209] = EDGE; a[153:161, 208] = BLACK
    return a


def H_V(V, v):
    """the right drum's outside at v from its middle (its bow, as its ticks')"""
    return V[47 - min(v, 47)] - 8 + 6


def H_H(H, v):
    return H[79 - min(v, 79)] + 8 + 6


def screen():
    """the GBA's 240 x 160 (RGB), with "A Present" and the L and R"""
    import fingerprint as fp
    import evidence3d as e3
    a = panel()[CROP[1]:CROP[1] + 160, CROP[0]:CROP[0] + 240].copy()
    ui = [(0, 0, 0)] + list(fp.UI[1:])
    def paste(img, x, y):
        ys, xs = np.nonzero(img)
        a[ys + y, xs + x] = np.array(ui, np.uint8)[img[ys, xs]]
    t = fp.tab(['Present'], ['A'])
    paste(t, 120 - t.shape[1] // 2, TAB_Y)
    # the shoulders over the roll's buttons (where the DS has a light)
    for letter, (x0, y0, x1, y1, cut) in zip('LR', BUTTONS):
        ic = e3.shoulder(letter)
        x = x1 - 13 - CROP[0]
        y = (y0 + 9 if cut == 'top' else y1 - 9 - 11) - CROP[1]
        paste(ic, x, y)
    return a


def circle_tiles():
    """the picture's tiles on the GBA's screen (x0, y0 in tiles: 16 x 16)"""
    cx, cy = middle()
    gx, gy = cx - 64 - CROP[0], cy - 64 - CROP[1]
    assert gx % 8 == 0 and gy % 8 == 0
    return gx // 8, gy // 8


def tick_sprites():
    """the drums' ticks: the bottom one's (2 x 6 upright), the right one's (6 x 2)"""
    h = np.zeros((8, 8), np.uint8); h[0:6, 0] = 1; h[0:6, 1] = 2
    v = np.zeros((8, 8), np.uint8); v[0, 0:6] = [1, 3, 3, 3, 3, 1]; v[1, 0:6] = [2, 4, 4, 4, 4, 2]
    return h, v


def tiles4(img):
    h, w = img.shape
    out = bytearray()
    for ty in range(h // 8):
        for tx in range(w // 8):
            for row in img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]:
                for x in range(0, 8, 2):
                    out.append(int(row[x]) | int(row[x + 1]) << 4)
    return bytes(out)


def rgb5(c):
    r, g, b = (int(v) for v in c)
    return (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10


def export(blob, align, record_index, pal_first, view_tiles):
    """the panel's data (into blob, evidence3d.py's) and its header lines:
    its tiles (8bpp, colours from pal_first), map (30 x 20; the picture's
    tiles the frame buffer's, 24 a row), the masks of the tiles the ring
    crosses, the grid's tiles and map, the sprites"""
    import fingerprint as fp
    a = screen()
    gx, gy = circle_tiles()
    cx, cy = middle()
    colours = []
    def index(c):
        c = tuple(int(v) for v in c)
        if c not in colours:
            colours.append(c)
        return pal_first + colours.index(c)
    # what is the grid's (inside the ring, under the picture)
    yy, xx = np.mgrid[0:160, 0:240]
    inside = np.hypot(xx + CROP[0] + 0.5 - cx, yy + CROP[1] + 0.5 - cy) < RING_R0
    tab = np.zeros((160, 240), bool)
    t = fp.tab(['Present'], ['A'])
    tab[TAB_Y:TAB_Y + t.shape[0], 120 - t.shape[1] // 2:120 - t.shape[1] // 2 + t.shape[1]] = t > 0
    idx = np.zeros((160, 240), np.int32)
    for y in range(160):
        for x in range(240):
            idx[y, x] = 0 if (inside[y, x] and not tab[y, x]) else index(a[y, x])
    assert pal_first + len(colours) <= 256, len(colours)
    tiles, seen, tmap, masks, mask_at = [], {}, [0] * 600, [], []
    for ty in range(20):
        for tx in range(30):
            t8 = idx[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].astype(np.uint8)
            fx, fy = tx - gx, ty - gy
            if 0 <= fx < 16 and 0 <= fy < 16 and not t8.all():
                # (the picture's: under the ring's pixels, where it crosses)
                tmap[ty * 30 + tx] = fy * 24 + fx
                if t8.any():
                    mask_at.append(fy * 24 + fx)
                    masks.append(bytes(t8.reshape(-1)))
                continue
            key = t8.tobytes()
            if key not in seen:
                seen[key] = len(tiles); tiles.append(t8)
            tmap[ty * 30 + tx] = view_tiles + seen[key]
    # the grid (BG2, 4 bits): a line through the circle's middle every 16
    g = np.zeros((16, 16), np.uint8)
    g[:, :] = 1
    ox, oy = (cx - CROP[0]) % 16, (cy - CROP[1]) % 16
    g[:, ox] = 2; g[oy, :] = 2; g[oy, ox] = 3
    grid_map = []
    for ty in range(20):
        for tx in range(30):
            if 0 <= tx - gx < 16 and 0 <= ty - gy < 16:
                grid_map.append(((tx & 1) | (ty & 1) << 1) + 1)
            else:
                grid_map.append(0)
    # the ring's ticks: four 64 x 64 quarters
    rpx, rpal = ring_ticks()
    quarters = b''.join(tiles4(rpx[y:y + 64, x:x + 64]) for y in (0, 64) for x in (0, 64))
    h, v = tick_sprites()
    lines = []
    def add(name, b, note=''):
        align()
        lines.append('#define EN3D_BADGER_GFX_%s 0x%X%s' % (name, len(blob), ('  // ' + note) if note else ''))
        blob.extend(b)
    add('TILES', b''.join(bytes(t.reshape(-1)) for t in tiles), '8bpp, after the frame buffer\'s')
    add('MAP', struct.pack('<600H', *tmap), '30 x 20')
    add('MASKS', b''.join(masks), 'the ring\'s tiles: 0 the picture\'s')
    add('MASK_AT', struct.pack('<%dH' % len(mask_at), *mask_at), 'their frame buffer tiles')
    add('GRID', tiles4(g), '4 tiles, 4 bits')
    add('GRID_MAP', bytes(grid_map), '30 x 20: tile + 1, 0 none')
    add('RING', quarters, 'the ring\'s ticks: four 64 x 64 quarters')
    add('TICKS', tiles4(h) + tiles4(v), 'the bottom drum\'s, the right one\'s')
    H, V = bows()
    F = projection()
    st, ct = sincos(TURN * 65536 // 360 >> 4)
    sr, cr = sincos(ROLL * 65536 // 360 >> 4)
    lines += ['#define EN3D_BADGER_TURN_SIN %d   // (1.14: the DS\'s 1.12 entry)' % (4 * st),
              '#define EN3D_BADGER_TURN_COS %d' % (4 * ct),
              '#define EN3D_BADGER_ROLL_SIN %d' % (4 * sr), '#define EN3D_BADGER_ROLL_COS %d' % (4 * cr)]
    lines += ['#define EN3D_BADGER_RECORD %d     // (the DS\'s object record %d)' % (record_index, RECORD),
              '#define EN3D_BADGER_TILES %d' % len(tiles),
              '#define EN3D_BADGER_COLOURS %d' % len(colours),
              '#define EN3D_BADGER_MASKS %d' % len(masks),
              '#define EN3D_BADGER_VIEW_X %d    // the picture on the screen (tiles)' % gx,
              '#define EN3D_BADGER_VIEW_Y %d' % gy,
              '#define EN3D_BADGER_F %d          // the focal length, 1/16 pixel' % int(F * 16 + 0.5),
              '#define EN3D_BADGER_Z (%d << 12)   // the jar behind its place (1.19.12)' % -(DISTANCE - 20),
              '#define EN3D_BADGER_RING_X %d     // the circle\'s middle on the screen' % (cx - CROP[0]),
              '#define EN3D_BADGER_RING_Y %d' % (cy - CROP[1]),
              '#define EN3D_BADGER_TURN %d' % TURN, '#define EN3D_BADGER_ROLL %d' % ROLL,
              '#define EN3D_BADGER_A0 %d' % CHECK['a'][0], '#define EN3D_BADGER_A1 %d' % CHECK['a'][1],
              '#define EN3D_BADGER_B0 %d' % CHECK['b'][0][0], '#define EN3D_BADGER_B1 %d' % CHECK['b'][0][1],
              '#define EN3D_BADGER_B2 %d' % CHECK['b'][1][1],
              '#define EN3D_BADGER_C0 %d' % CHECK['c'][0], '#define EN3D_BADGER_C1 %d' % CHECK['c'][1],
              '#define EN3D_BADGER_DRUM_H_R %d' % DRUM_H['radius'],
              '#define EN3D_BADGER_DRUM_H_X %d' % (DRUM_H['middle'] - CROP[0]),
              '#define EN3D_BADGER_DRUM_H_Y %d' % (DRUM_H['offset'] - CROP[1]),
              '#define EN3D_BADGER_DRUM_V_R %d' % DRUM_V['radius'],
              '#define EN3D_BADGER_DRUM_V_Y %d' % (DRUM_V['middle'] - CROP[1]),
              '#define EN3D_BADGER_DRUM_V_X %d' % (DRUM_V['offset'] - CROP[0]),
              'static const u8 sEn3dBadgerBowH[80] = { %s };' % ', '.join(map(str, H)),
              'static const u8 sEn3dBadgerBowV[48] = { %s };' % ', '.join(map(str, V)),
              'static const u16 sEn3dBadgerTicksH[16] = { %s };' % ', '.join(map(str, TICKS_H)),
              'static const u16 sEn3dBadgerTicksV[12] = { %s };' % ', '.join(map(str, TICKS_V))]
    lines.append('static const u16 sEn3dBadgerPalette[%d] = { %s };' % (
        len(colours), ', '.join('0x%04X' % rgb5(c) for c in colours)))
    lines.append('static const u16 sEn3dBadgerGridPal[4] = { 0, 0x%04X, 0x%04X, 0x%04X };' % (
        rgb5(GRID_BG), rgb5(GRID_LINE), rgb5(GRID_CROSS)))
    lines.append('static const u16 sEn3dBadgerRingPal[16] = { %s };' % ', '.join('0x%04X' % (c & 0x7FFF) for c in rpal))
    lines.append('static const u16 sEn3dBadgerTickPal[16] = { 0, %s };' % ', '.join('0x%04X' % rgb5(c) for c in TICK))
    return lines


def preview(path):
    """the GBA's screen at rest: the panel, the grid, the ring's ticks, the drums' (no jar)"""
    from PIL import Image
    a = screen().astype(np.uint8)
    cx, cy = middle()
    gx, gy = circle_tiles()
    yy, xx = np.mgrid[0:160, 0:240]
    rr = np.hypot(xx + CROP[0] + 0.5 - cx, yy + CROP[1] + 0.5 - cy)
    ox, oy = (cx - CROP[0]) % 16, (cy - CROP[1]) % 16
    grid = np.where(((xx % 16) == ox) & ((yy % 16) == oy), 3, np.where(((xx % 16) == ox) | ((yy % 16) == oy), 2, 1))
    G = np.array([(0, 0, 0), GRID_BG, GRID_LINE, GRID_CROSS], np.uint8)
    inside = rr < RING_R0
    a[inside] = G[grid[inside]]
    rpx, rpal = ring_ticks()
    P = np.array([((c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3) for c in rpal], np.uint8)
    x0, y0 = cx - 64 - CROP[0], cy - 64 - CROP[1]
    m = rpx > 0
    sub = a[y0:y0 + 128, x0:x0 + 128]
    sub[m] = P[rpx[m]]
    H, V = bows()
    h, v = tick_sprites()
    T = np.array([(0, 0, 0)] + TICK, np.uint8)
    for ang in TICKS_H:
        s = int(DRUM_H['radius'] * math.sin(math.radians(ang)))
        x = DRUM_H['middle'] + s - CROP[0]
        y = H[DRUM_H['radius'] - abs(s)] + DRUM_H['offset'] - CROP[1]
        mm = h > 0
        if 0 <= y and y + 8 <= 160 and 0 <= x and x + 8 <= 240:
            a[y:y + 8, x:x + 8][mm] = T[h[mm]]
    for ang in TICKS_V:
        s = int(DRUM_V['radius'] * math.sin(math.radians(ang)))
        y = DRUM_V['middle'] + s - CROP[1]
        x = V[DRUM_V['radius'] - abs(s)] + DRUM_V['offset'] - CROP[0]
        mm = v > 0
        if 0 <= y and y + 8 <= 160 and 0 <= x and x + 8 <= 240:
            a[y:y + 8, x:x + 8][mm] = T[v[mm]]
    Image.fromarray(a).resize((720, 480), 0).save(path)


if __name__ == '__main__':
    preview(sys.argv[1] if len(sys.argv) > 1 else 'badger_preview.png')
