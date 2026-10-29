#!/usr/bin/env python3
"""The staff roll (the DS's 74 c 0, 74 d n, 74 8 40 / 41 / 2e: the ending of
Rise from the Ashes, chapter file 34's sections 85 and 88), from the DS, for
src/en_credits.c.

What the DS does (its process 26: 0x02072494, its steps 0x02072290 (set up)
and 0x02071d14 (the frames); the powder's code is the fingerprints',
0x0206bd34-0x0206f588, its state 0x02318dd4-0x02318e48):
- while the epilogue plays on the top screen, the touch screen is the
  fingerprints' green grid; 74 d n picks a page and 74 8 40 shows it: a
  256 x 192 picture (a table at 0x020c2e88, 16 bytes a page: the record of
  its data.bin offset (RLE), and whether the player dusts it; pages 0-0x14
  the Japanese build's credits, 0x15-0x1e sketches of the people whose
  scene is up, 0x1f-0x35 the US build's credits) becomes the mask (its
  levels shifted up a nibble: the credits' white is 0xF0);
- a credits page (and Ema's sketch, 0x1e) is dusted by itself
  (0x0207b6fc): a brush crosses the screen three times, at y 64, 96 and 128
  (0x020c9218; jittered by -10 to 9, then -5 to 4 each step), left to right,
  back, and again, a step of 32 every four frames from x 32 to 224, dropping
  one of the fingerprints' four stamps (128 x 128) each frame (each of its
  dots rand(96) x 4 more powder, saturating); 30 frames on, the powder is
  blown off but where the mask is (0x0206ec90 at level 0x18 for 46 frames:
  a quarter of the rows a frame; off the mask the level and rand(24) are
  taken off, on it the powder never goes under the mask's level, so the
  credits stand out) and sparks fly off as it goes (one pixel in 20 of the
  mask's, one in 10 of the rest);
- the sketches the player can dust are left blank until touched;
- 74 8 41 blows the page away (0x0206ec90 with the mask off, level 0x40,
  61 frames: the powder goes, a pixel in four throwing two sparks, the
  first 12 frames' sparks flying less far); 74 8 2e ends it;
- each frame a quarter of the rows is drawn (0x0206f168): powder w as the
  colour min(w / 16 + 1, 14) of the texture's 16 (data.bin 0x2e72a3c; 0
  clear, the grid under it), a spark as colour 1 or 15 at random, moved
  up k rows and (x / 16 - 8) across (k: 8 + x / 16, or after the first 12
  frames of a blowing away 24 + 3 (x / 16)).

On the GBA (src/en_credits.c, script command 6A: translate.py) the credits
pages take the screen while the epilogue's is black (between its scenes:
the GBA has one screen), the picture cut as the backgrounds are (x - 8, y -
16: all the US build's credits are inside); the sketches the DS leaves to
the player's touch and Ema's, shown while her scene is up, are left out.
The sparks are thrown at random (one in 8, one in 16 of the page's: near the
DS's fixed patterns' 10 and 20).

Writes graphics/en/rfta/credits.bin, data/rfta/credits.s (section rfta_low)
and src/data/en_rfta_credits.h. usage: credits.py [--preview FILE]"""
import os, sys, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import dsbin
from dsdata import data
ROOT = os.path.join(HERE, '..', '..', '..')

PAGES = 0x020c2e88                       # 16 bytes a page: the record, the player's flag
PAGE_COUNT = 0x36
FIRST_CREDITS, LAST_CREDITS = 0x1F, 0x35  # the US build's credits
ROWS = 0x020c9218                         # the brush's rows (the first three)
TEXTURE_PAL = 0x2e72a3c                   # the powder's 16 colours (data.bin)
STAMP_PTR = 0x0206c028                    # the stamps (data.bin offset, literal)
STAMP_SIZE = 128
GRID = [(0, 128, 24), (32, 168, 64), (40, 176, 80)]   # the green, a line, a crossing (every 16 at 7)
CROP = (8, 16)
GBA_W, GBA_H = 240, 160
BRUSH = dict(x0=32, x1=224, step=32, frames=4, rows=3)
JITTER_FIRST, JITTER_STEP = (20, 10), (10, 5)        # rand(a) - b
WAIT_FRAMES, REVEAL_FRAMES, REVEAL_LEVEL = 30, 46, 0x18
BLOW_FRAMES, BLOW_LEVEL, BLOW_NEAR_FRAMES = 61, 0x40, 12


def rle(d, o):
    hdr = struct.unpack_from('<I', d, o)[0]
    assert hdr & 0xFF == 0x30
    n = hdr >> 8; o += 4; out = bytearray()
    while len(out) < n:
        f = d[o]; o += 1
        if f & 0x80:
            out += bytes([d[o]]) * ((f & 0x7F) + 3); o += 1
        else:
            k = (f & 0x7F) + 1; out += d[o:o + k]; o += k
    return bytes(out[:n])


def pages():
    """[(levels 192 x 256, the player dusts it)]"""
    arm = dsbin.data()
    d = data()
    out = []
    for i in range(PAGE_COUNT):
        rec, _, touch, _ = struct.unpack_from('<4I', arm, PAGES - dsbin.BASE + 16 * i)
        off, size = struct.unpack_from('<2I', arm, rec - dsbin.BASE + 0x20)
        out.append((np.frombuffer(rle(d, off), np.uint8).reshape(192, 256), touch == 1))
    return out


def rows():
    return list(struct.unpack_from('<3H', dsbin.data(), ROWS - dsbin.BASE))


def stamps():
    base = dsbin.u32(STAMP_PTR)
    d = data()
    return [np.frombuffer(d[base + k * STAMP_SIZE ** 2:base + (k + 1) * STAMP_SIZE ** 2], np.uint8)
            .reshape(STAMP_SIZE, STAMP_SIZE) for k in range(4)]


def texture_colours():
    return [((c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3)
            for c in struct.unpack_from('<16H', data(), TEXTURE_PAL)]


def bits(plane):
    """160 x 240 bools -> 30 bytes a row, pixel x in bit x & 7 of byte x >> 3"""
    out = bytearray()
    for row in plane:
        for x in range(0, GBA_W, 8):
            out.append(sum(1 << k for k in range(8) if row[x + k]))
    return bytes(out)


def rgb5(c):
    return (c[0] >> 3) | (c[1] >> 3) << 5 | (c[2] >> 3) << 10


def main():
    preview = sys.argv[sys.argv.index('--preview') + 1] if '--preview' in sys.argv else None
    pg = pages()
    blob = bytearray()
    defs = []
    def add(name, b, align=4):
        while len(blob) % align:
            blob.append(0)
        defs.append('#define CREDITS_GFX_%s 0x%X' % (name, len(blob)))
        blob.extend(b)
    planes = bytearray()
    for i in range(FIRST_CREDITS, LAST_CREDITS + 1):
        a, touch = pg[i]
        assert not touch or i == LAST_CREDITS, i
        cut = a[CROP[1]:CROP[1] + GBA_H, CROP[0]:CROP[0] + GBA_W]
        assert (a > 0).sum() == (cut > 0).sum(), ('a page beyond the GBA\'s screen', hex(i))
        planes += bits(cut > 0)
    add('PAGES', planes)
    st = stamps()
    counts = []
    pts = bytearray()
    for s in st:
        ys, xs = np.nonzero(s)
        counts.append((len(pts) // 2, len(xs)))
        for x, y in zip(xs, ys):
            pts += struct.pack('<bb', int(x) - STAMP_SIZE // 2, int(y) - STAMP_SIZE // 2)
    add('STAMPS', pts)
    os.makedirs(os.path.join(ROOT, 'graphics', 'en', 'rfta'), exist_ok=True)
    open(os.path.join(ROOT, 'graphics', 'en', 'rfta', 'credits.bin'), 'wb').write(blob)
    asm = ['@ generated by tools/en/rfta/credits.py: the staff roll\'s pages and stamps',
           '\t.section rfta_low, "a"', '\t.align 2', '\t.global gEnCreditsData', 'gEnCreditsData:',
           '\t.incbin "graphics/en/rfta/credits.bin"']
    open(os.path.join(ROOT, 'data', 'rfta', 'credits.s'), 'w').write('\n'.join(asm) + '\n')
    tc = texture_colours()
    h = ['// generated by tools/en/rfta/credits.py: the staff roll, from the DS',
         '// (its pages as the GBA cuts the touch screen: from (%d, %d), a bit a pixel)' % CROP]
    h += defs
    h.append('#define CREDITS_FIRST_PAGE 0x%X     // the US build\'s credits: these are shown' % FIRST_CREDITS)
    h.append('#define CREDITS_LAST_PAGE 0x%X' % LAST_CREDITS)
    h.append('#define CREDITS_PAGE_BYTES %d' % (GBA_W * GBA_H // 8))
    h.append('#define CREDITS_CROP_X %d' % CROP[0])
    h.append('#define CREDITS_CROP_Y %d' % CROP[1])
    for k, v in BRUSH.items():
        h.append('#define CREDITS_BRUSH_%s %d' % (k.upper(), v))
    h.append('static const s16 sEnCreditsRows[%d] = { %s };     // the brush\'s (the DS\'s screen)' %
             (BRUSH['rows'], ', '.join(str(v) for v in rows())))
    h.append('#define CREDITS_JITTER_FIRST %d, %d     // rand(a) - b' % JITTER_FIRST)
    h.append('#define CREDITS_JITTER_STEP %d, %d' % JITTER_STEP)
    for name in ('WAIT_FRAMES', 'REVEAL_FRAMES', 'REVEAL_LEVEL', 'BLOW_FRAMES', 'BLOW_LEVEL', 'BLOW_NEAR_FRAMES'):
        h.append('#define CREDITS_%s %d' % (name, globals()[name]))
    h.append('struct EnCreditsStamp { u16 first, count; };     // dots (dx, dy from its middle)')
    h.append('static const struct EnCreditsStamp sEnCreditsStamps[4] = { %s };' %
             ', '.join('{ %d, %d }' % c for c in counts))
    h.append('// BG3\'s 256 colours while the pages are up: the powder\'s 1-15 at 48, the grid at 64')
    h.append('#define CREDITS_PAL_POWDER 48')
    h.append('#define CREDITS_PAL_GRID 64')
    h.append('static const u16 sEnCreditsPowderPal[16] = { %s };' % ', '.join('0x%04X' % rgb5(c) for c in tc))
    h.append('static const u16 sEnCreditsGridPal[3] = { %s };' % ', '.join('0x%04X' % rgb5(c) for c in GRID))
    open(os.path.join(ROOT, 'src', 'data', 'en_rfta_credits.h'), 'w').write('\n'.join(h) + '\n')
    if preview:
        from PIL import Image
        S = Image.new('RGB', (GBA_W * 4, GBA_H * 6))
        for k, i in enumerate(range(FIRST_CREDITS, LAST_CREDITS + 1)):
            a = pg[i][0][CROP[1]:CROP[1] + GBA_H, CROP[0]:CROP[0] + GBA_W]
            img = np.zeros((GBA_H, GBA_W, 3), np.uint8)
            img[:] = GRID[0]
            yy, xx = np.mgrid[0:GBA_H, 0:GBA_W]
            gx, gy = (xx + CROP[0]) % 16 == 7, (yy + CROP[1]) % 16 == 7
            img[gx | gy] = GRID[1]; img[gx & gy] = GRID[2]
            img[a > 0] = tc[14]
            S.paste(Image.fromarray(img), ((k % 4) * GBA_W, (k // 4) * GBA_H))
        S.save(preview)


if __name__ == '__main__':
    main()
