#!/usr/bin/env python3
"""Joining the dots (the DS's 74 8 3e: the final day's trial, the blood
traces the victim left joined into the murderer's name), from the DS, for
src/en_dots.c.

What the DS does (its process 18: 0x02077208, its steps 0x02076d80 (set
up), 0x02076cf0 (the player's turn), 0x02076a14 (Present: the result),
0x0207678c (the Court Record and back), 0x020763c4 (the panel sliding in);
the traces' code 0x0206d294-0x0206e5dc, their state 0x02318dc4-0x02318e48):
- the touch screen slides in with the picture (background 0x8e) and the
  traces drawn over it in a dark red (sprites: the US build's twelve, their
  places, sizes and masks in a table at 0x020c231c (32 bytes a trace: x, y,
  w, h, the mask's data.bin offset and size, the middle), their boxes at
  0x020c17d4; the Japanese build's fifteen at 0x020c249c and 0x020c1834),
  under a bar "Connect the blood traces" and Present and Court Record
  buttons, Back at the bottom;
- a touch on a trace (in its box, and a pixel of a mask under the touch's
  8 x 8 brush: 0x020c1654, a disc, but read 256 bytes a row, so its rows
  1-7 are the bytes 256, 512... on) starts a line from its middle; the line
  follows the touch, blue (its shades 2, 3, 4, 4, 3, 2 of the colour table,
  a step every 15 frames), white while the touch is on another trace; both
  traces lit (bright red); lifted there, the two are joined (SE 0x34),
  unless they already are. A line is a rectangle 8 wide from middle to
  middle (0x0203f290: 8.0 / 2 either side) with an 8 x 8 round end at each
  (texture 0x94); the joined lines dark red (colour 0) under the traces,
  the one being drawn over them and under the lit ones;
- Back (B, the button) takes the last line away (white for a frame, then
  gone; SE 0x33); R (Court Record) opens the record (SE 0x31) and comes back
  to the traces as they were; X (Present) checks them (0x0206d294, the US
  build's): every line one of the name's, and 0-1, 0-5, 5-6 (the E), 2-3,
  2-9 (the M, with the picture's own strokes) and 7-8 all there, the A's
  legs whole: 4-10 (or 4-7 and 7-10) and 4-11 (or 4-8 and 8-11); then both
  screens white, "Take that!" as the Blue Badger's, and section C7 (right)
  or C6 (not: and from there the traces again, the lines gone).

On the GBA (src/en_dots.c, on the 3D viewer's machinery as the keypad) the
picture is the GBA's background 0x8e in 256 colours (its 16, then the
lines' and the traces'), the lines and traces drawn into its tiles as the
DS draws them; the examine pointer is the touch (the + pad moves it, A held
is the stylus down); B is Back, L Present, R the Court Record, as tabs under
the DS's bar.

Writes graphics/en/rfta/dots.bin, data/rfta/dots.s (section rfta_low) and
src/data/en_rfta_dots.h. usage: dots.py [--preview FILE]"""
import os, sys, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import dsbin
from dsdata import data
ROOT = os.path.join(HERE, '..', '..', '..')

LANG = 1                                  # the US build's set (gMain + 4: 0 Japanese, 1 English)
COUNTS = 0x020c0a58                       # traces a set
BOXES = 0x020c0a68                        # their boxes: x, y, w, h (s16)
TRACES = 0x020c0a78                       # their sprites: x, y, w, h, mask offset, size, middle x, y (u32)
BRUSH = 0x020c1654                        # 8 x 8, read 256 bytes a row (0x0206d9d0)
COLOURS = (0x020c0a38, 0x020c0a48, 0x020c0a40)    # red, green, blue (5 bits) of colours 0-6
CYCLE = 0x020c0a30                        # the line's shades as it is drawn (6)
CYCLE_FRAMES = 15
HALF_WIDTH = 4                            # 8.0 / 2.0 (0x0203f290)
CAP = np.array([[0, 0, 1, 1, 1, 1, 0, 0], [0, 1, 1, 1, 1, 1, 1, 0]] + [[1] * 8] * 4 +
               [[0, 1, 1, 1, 1, 1, 1, 0], [0, 0, 1, 1, 1, 1, 0, 0]], np.uint8)
# the traces' colours (texture palettes 0 and 1, read off the DS's screen)
TRACE, TRACE_LIT = (136, 24, 24), (248, 24, 24)
# the US build's check (0x0206d294): the lines it takes, by kind: 1 counted
# (all six needed), 2-7 the A's legs (4-7, 4-8, 4-10, 4-11, 7-10, 8-11)
KINDS = {(0, 1): 1, (0, 5): 1, (2, 3): 1, (2, 9): 1, (5, 6): 1, (7, 8): 1,
         (4, 7): 2, (4, 8): 3, (4, 10): 4, (4, 11): 5, (7, 10): 6, (8, 11): 7}
COUNTED = 6
PICTURE_BG = 0x8E
SECTION_RIGHT, SECTION_WRONG = 0xC7, 0xC6
SE_JOIN, SE_BACK, SE_RECORD = 0x34, 0x33, 0x31     # (the DS's numbers are the GBA's songs: SE00A, SE009, SE007)
BANNER = 'Connect the blood traces'
CROP = (8, 16)                            # the GBA's screen: the touch screen from here (as the background)
GBA_W, GBA_H = 240, 160
# the picture's colours: its 16 at 32-47, then these
PAL_LINE, PAL_TRACE, PAL_LIT, PAL_WHITE, PAL_BAND = 48, 49, 50, 51, 52


def u32(a):
    return dsbin.u32(a)


def traces():
    """the US build's traces: [{x, y, w, h, mask, cx, cy, box}] (the DS's screen)"""
    n = u32(COUNTS + 4 * LANG)
    bt, tt = u32(BOXES + 4 * LANG), u32(TRACES + 4 * LANG)
    arm = dsbin.data()
    d = data()
    out = []
    for i in range(n):
        x, y, w, h, off, size, cx, cy = struct.unpack_from('<8I', arm, tt - dsbin.BASE + 32 * i)
        box = struct.unpack_from('<4h', arm, bt - dsbin.BASE + 8 * i)
        assert size == w * h
        m = np.frombuffer(d[off:off + size], np.uint8).reshape(h, w)
        out.append(dict(x=x, y=y, w=w, h=h, mask=(m > 0).astype(np.uint8), cx=cx, cy=cy, box=box))
    return out


def brush():
    """the brush as the DS reads it"""
    arm = dsbin.data()
    return np.array([[arm[BRUSH - dsbin.BASE + r * 256 + c] for c in range(8)] for r in range(8)]) > 0


def colours():
    arm = dsbin.data()
    r, g, b = ([arm[t - dsbin.BASE + k] for k in range(7)] for t in COLOURS)
    return [(r[k], g[k], b[k]) for k in range(7)]


def cycle():
    arm = dsbin.data()
    return [arm[CYCLE - dsbin.BASE + k] for k in range(6)]


def rgb5(c):
    return (c[0] >> 3) | (c[1] >> 3) << 5 | (c[2] >> 3) << 10


def c5(c):
    return c[0] | c[1] << 5 | c[2] << 10


def tab(label, letter):
    """the fingerprints' tab (fingerprint.tab) with a shoulder button's
    picture for L and R (the jar puzzle's, evidence3d.shoulder)"""
    import fingerprint as fp
    import evidence3d as e3
    if letter in ('A', 'B'):
        return fp.tab([label], [letter])
    m = fp.text(label)[2:15]
    w = (3 + 13 + 2 + m.shape[1] + 3 + 7) // 8 * 8
    a = np.zeros((16, w), np.uint8)
    a[1:15, :] = fp.C_BAR_DARK; a[2:14, 1:w - 1] = fp.C_BAR
    a[1, 0] = a[1, w - 1] = a[14, 0] = a[14, w - 1] = 0
    ic = e3.shoulder(letter)
    a[3:14, 3:16] = np.where(ic > 0, ic, a[3:14, 3:16])
    fp.put(a, m, 18, 2, fp.C_WHITE)
    return a


TABS = (('PRESENT', 'Present', 'L'), ('RECORD', 'Court Record', 'R'), ('BACK', 'Back', 'B'))


def sprites():
    """the bar, the tabs (4bpp, the fingerprints' UI colours)"""
    import fingerprint as fp
    st = fp.SpriteSet('DOTS')
    st.add('BANNER', fp.banner(BANNER))
    for key, label, letter in TABS:
        st.add(key, tab(label, letter))
    return st


def layout():
    """where the GBA's bar and tabs go: the bar over the top (the DS's), the
    tabs under its right end, one over the other (clear of the traces), Back
    at the bottom left (as the DS's)"""
    import fingerprint as fp
    wp, wr, wb = (tab(label, letter).shape[1] for _, label, letter in TABS)
    return dict(BANNER=(-8, 0), PRESENT=(GBA_W - wp, 16), RECORD=(GBA_W - wr, 32), BACK=(0, GBA_H - 16))


def segment_mask(x0, y0, x1, y1, shape):
    """the DS's line (its rectangle and its round ends) on a grid of pixels
    (the pixels' corners: the closest to the DS's own)"""
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W]
    m = np.zeros(shape, bool)
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2:
        px, py = xx - x0, yy - y0
        t = px * dx + py * dy
        n = px * dy - py * dx
        m |= (t >= 0) & (t <= L2) & (n * n <= HALF_WIDTH * HALF_WIDTH * L2)
    for cx, cy in ((x0, y0), (x1, y1)):
        for r in range(8):
            for c in range(8):
                y, x = cy - 4 + r, cx - 4 + c
                if CAP[r, c] and 0 <= y < H and 0 <= x < W:
                    m[y, x] = True
    return m


def right(lines):
    """the US build's check"""
    k = [KINDS.get((min(a, b), max(a, b)), 0) for a, b in lines]
    if 0 in k or sum(1 for v in k if v == 1) != COUNTED:
        return False
    has = set(k)
    return (4 in has or (2 in has and 6 in has)) and (5 in has or (3 in has and 7 in has))


def main():
    preview = sys.argv[sys.argv.index('--preview') + 1] if '--preview' in sys.argv else None
    import fingerprint as fp
    tr = traces()
    cols = colours()
    blob = bytearray()
    defs = []
    def add(name, b, align=4):
        while len(blob) % align:
            blob.append(0)
        defs.append('#define DOTS_GFX_%s 0x%X' % (name, len(blob)))
        blob.extend(b)
    # the traces' masks, on the GBA's screen
    recs = []
    for t in tr:
        mx, my = t['x'] - CROP[0], t['y'] - CROP[1]
        assert 0 <= mx and mx + t['w'] <= GBA_W and 0 <= my and my + t['h'] <= GBA_H
        recs.append((t['cx'] - CROP[0], t['cy'] - CROP[1], t['box'][0] - CROP[0], t['box'][1] - CROP[1],
                     t['box'][2], t['box'][3], mx, my, t['w'], t['h']))
    masks = []
    for k, t in enumerate(tr):
        while len(blob) % 4:
            blob.append(0)
        masks.append(len(blob))
        blob.extend(bytes(t['mask'].reshape(-1)))
    st = sprites()
    add('SPRITES', bytes(st.tiles))
    os.makedirs(os.path.join(ROOT, 'graphics', 'en', 'rfta'), exist_ok=True)
    open(os.path.join(ROOT, 'graphics', 'en', 'rfta', 'dots.bin'), 'wb').write(blob)
    asm = ['@ generated by tools/en/rfta/dots.py: joining the dots',
           '\t.section rfta_low, "a"', '\t.align 2', '\t.global gEnDotsData', 'gEnDotsData:',
           '\t.incbin "graphics/en/rfta/dots.bin"']
    open(os.path.join(ROOT, 'data', 'rfta', 'dots.s'), 'w').write('\n'.join(asm) + '\n')
    lay = layout()
    br = brush()
    cyc = cycle()
    h = ['// generated by tools/en/rfta/dots.py: joining the dots, from the DS',
         '// (the touch screen as the GBA cuts the picture: from (%d, %d))' % CROP]
    h += defs
    h.append('#define DOTS_GFX_SPRITE_TILES %d' % (len(st.tiles) // 32))
    h.append('#define DOTS_TRACES %d' % len(tr))
    h.append('#define DOTS_PICTURE_BG 0x%X' % PICTURE_BG)
    h.append('#define DOTS_SECTION_RIGHT 0x%X' % SECTION_RIGHT)
    h.append('#define DOTS_SECTION_WRONG 0x%X' % SECTION_WRONG)
    h.append('#define DOTS_SE_JOIN %d' % SE_JOIN)
    h.append('#define DOTS_SE_BACK %d' % SE_BACK)
    h.append('#define DOTS_SE_RECORD %d' % SE_RECORD)
    h.append('#define DOTS_HALF_WIDTH %d' % HALF_WIDTH)
    h.append('#define DOTS_COUNTED %d' % COUNTED)
    h.append('#define DOTS_CYCLE_FRAMES %d' % CYCLE_FRAMES)
    h.append('#define DOTS_PAL_LINE %d' % PAL_LINE)
    h.append('#define DOTS_PAL_TRACE %d' % PAL_TRACE)
    h.append('#define DOTS_PAL_LIT %d' % PAL_LIT)
    h.append('#define DOTS_PAL_WHITE %d' % PAL_WHITE)
    h.append('#define DOTS_PAL_BAND %d' % PAL_BAND)
    for name, (x, y) in lay.items():
        h.append('#define DOTS_%s_X %d' % (name, x))
        h.append('#define DOTS_%s_Y %d' % (name, y))
    # the sprites' pieces
    h.append('struct EnDotsPiece { s16 dx, dy; u8 shape, size; u16 tile; u8 last; };')
    h.append('static const struct EnDotsPiece sEnDotsPieces[] = {')
    n = 0
    names = []
    for key, rec in st.sprites:
        names.append('#define DOTS_SPRITE_%s %d' % (key, n))
        for k, (dx, dy, (shape, size), tile) in enumerate(rec):
            h.append('    { %d, %d, %d, %d, %d, %d },' % (dx, dy, shape, size, tile, k == len(rec) - 1))
            n += 1
    h.append('};')
    h += names
    h.append('static const u16 sEnDotsUiPalette[16] = { 0, %s };' % ', '.join('0x%04X' % rgb5(c) for c in fp.UI[1:]))
    # the traces
    h.append('struct EnDotsTrace { s16 cx, cy, bx, by, bw, bh, mx, my; u8 mw, mh; u16 mask; };')
    h.append('// the middle; the box (the touch must be in it: x, y, w, h, the ends')
    h.append('// counted in); the mask\'s place and size, its offset')
    h.append('static const struct EnDotsTrace sEnDotsTraces[DOTS_TRACES] = {')
    for (cx, cy, bx, by, bw, bh, mx, my, mw, mh), off in zip(recs, masks):
        h.append('    { %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, 0x%X },' % (cx, cy, bx, by, bw, bh, mx, my, mw, mh, off))
    h.append('};')
    # the check: a line's kind, both ways
    h.append('// the lines the US build\'s check takes (0: none): 1 counted, 2-7 the')
    h.append('// A\'s legs, 4-7, 4-8, 4-10, 4-11, 7-10, 8-11')
    h.append('static const u8 sEnDotsKinds[DOTS_TRACES][DOTS_TRACES] = {')
    for a in range(len(tr)):
        h.append('    { %s },' % ', '.join(str(KINDS.get((min(a, b), max(a, b)), 0)) for b in range(len(tr))))
    h.append('};')
    h.append('// the brush under the touch, as the DS reads it (a bit a pixel, bit 7 the left)')
    h.append('static const u8 sEnDotsBrush[8] = { %s };' % ', '.join('0x%02X' % sum(int(br[r, c]) << (7 - c) for c in range(8)) for r in range(8)))
    h.append('// the line\'s round end, 8 x 8 (the same way)')
    h.append('static const u8 sEnDotsCap[8] = { %s };' % ', '.join('0x%02X' % sum(int(CAP[r, c]) << (7 - c) for c in range(8)) for r in range(8)))
    h.append('// the colours (the DS\'s table: 0 the lines, 5 white; the traces\' read off its screen)')
    h.append('#define DOTS_COLOUR_LINE 0x%04X' % c5(cols[0]))
    h.append('#define DOTS_COLOUR_WHITE 0x%04X' % c5(cols[5]))
    h.append('#define DOTS_COLOUR_TRACE 0x%04X' % rgb5(TRACE))
    h.append('#define DOTS_COLOUR_LIT 0x%04X' % rgb5(TRACE_LIT))
    h.append('static const u16 sEnDotsBandColours[6] = { %s };     // the line being drawn, a step every DOTS_CYCLE_FRAMES' %
             ', '.join('0x%04X' % c5(cols[k]) for k in cyc))
    open(os.path.join(ROOT, 'src', 'data', 'en_rfta_dots.h'), 'w').write('\n'.join(h) + '\n')
    if preview:
        draw_preview(preview, tr, st, lay)


def draw_preview(path, tr, st, lay):
    """the GBA's screen with the name joined (the line from 4 being drawn to the pointer)"""
    from PIL import Image
    import fingerprint as fp
    pic = np.array(Image.open(os.path.join(ROOT, 'graphics', 'en', 'rfta', 'bg', 'bg_%02x.png' % PICTURE_BG)).convert('RGB'))
    cols = colours()
    a = pic.copy()
    lines = [(0, 1), (0, 5), (5, 6), (2, 3), (2, 9), (7, 8), (4, 10)]
    m = np.zeros((GBA_H, GBA_W), bool)
    for p, q in lines:
        t0, t1 = tr[p], tr[q]
        m |= segment_mask(t0['cx'] - CROP[0], t0['cy'] - CROP[1], t1['cx'] - CROP[0], t1['cy'] - CROP[1], m.shape)
    a[m] = [v << 3 for v in cols[0]]
    for t in tr:
        sub = a[t['y'] - CROP[1]:t['y'] - CROP[1] + t['h'], t['x'] - CROP[0]:t['x'] - CROP[0] + t['w']]
        sub[t['mask'] > 0] = TRACE
    t4 = tr[4]
    px, py = 200, 140
    band = segment_mask(t4['cx'] - CROP[0], t4['cy'] - CROP[1], px, py, m.shape)
    a[band] = [v << 3 for v in cols[2]]
    sub = a[t4['y'] - CROP[1]:t4['y'] - CROP[1] + t4['h'], t4['x'] - CROP[0]:t4['x'] - CROP[0] + t4['w']]
    sub[t4['mask'] > 0] = TRACE_LIT
    P = np.array([(0, 0, 0)] + list(fp.UI[1:]), np.uint8)
    for key, img in [('BANNER', fp.banner(BANNER))] + [(key, tab(label, letter)) for key, label, letter in TABS]:
        x, y = lay[key]
        for r in range(img.shape[0]):
            for c in range(img.shape[1]):
                if img[r, c] and 0 <= x + c < GBA_W and 0 <= y + r < GBA_H:
                    a[y + r, x + c] = P[img[r, c]]
    Image.fromarray(a).resize((GBA_W * 3, GBA_H * 3), 0).save(path)


if __name__ == '__main__':
    main()
