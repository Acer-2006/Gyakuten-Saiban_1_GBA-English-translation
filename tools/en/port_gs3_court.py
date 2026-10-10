#!/usr/bin/env python3
"""The courtroom of Gyakuten Saiban 3 (GBA) in place of the first game's.

usage: port_gs3_court.py GS3_ROM      (Gyakuten Saiban 3, Japan, CRC32 51b6cf22)

Writes (all generated; run again after changing anything here):
  graphics/en/court/*.png        the six court backgrounds (256 colours)
  graphics/en/court/court_pan.bin  the 48 frames of the pans between the
                                 benches (3 pans x 16 frames, 256 colours)
  include/en_court_pan.h         where the camera is on each pan frame
  data/en_court.s                the labels (gEnCourt*) the game uses

The lobby and the gavel close-ups stay the first game's.

How GS3 draws its courtroom, and what changes for the first game's engine:

* Backgrounds. GS3's background table has the same format as GS1's (the
  same "striped" pictures: ten LZ77 stripes and a palette). Defense bench,
  prosecution bench, witness stand, judge, co-counsel and the wide
  courtroom are entries 1 to 6.
* Desks. GS3 draws the benches and the witness stand as sprites in front
  of the people (four 64x32 / 32x32 / 16x32 pieces, one 16-colour palette;
  the prosecution bench is the defense bench mirrored). GS1 has them in
  the background and cuts every pose off at the top of the desk. Here the
  desk is put into the picture, as in GS1, so the GS1 poses keep fitting:
  measured over every pose the Japanese scripts show at each desk (each
  rendered in the game), the GS3 benches start one row below where the
  GS1 poses end, exactly as the GS1 benches do; the GS3 witness stand is
  two rows higher than the GS1 one, so it is put two rows lower. Its rim
  is also rounder than the GS1 stand's: towards the ends it drops below
  where the poses end, so there its top edge is drawn up to the GS1 line
  (STAND_LINE).
  With the desk the bench pictures have 30 colours, so the three become
  256-colour backgrounds like GS1's judge (palette 0-31 is the game's own
  user interface colours, as in every GS1 256-colour background).
* Pans. GS1 plays 16 ready-made frames for each pan (defense <-> witness,
  prosecution <-> defense, prosecution <-> witness). GS3 scrolls one
  picture instead: the defense bench at 0, the witness stand at 520 (its
  right half is the left half mirrored) and the prosecution bench at 1040
  (the whole picture mirrored), with the desk sprites moving along, at
  the camera positions of two 16-step tables (one per pan length). Each
  GS1 frame here is that picture at GS3's camera position for that step,
  with the desks in it. The people move with the picture (the C side,
  src/animation.c, reads the camera positions from en_court_pan.h); the
  person coming in appears when both are off screen."""
import os, sys, struct, zlib
import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
OUT = os.path.join(ROOT, 'graphics', 'en', 'court')
GS3_CRC = 0x51b6cf22

# ---------------------------------------------------------------- GS3 data
BG_TABLE = 0x3b334                 # {u8 *data, u32 flags} per background
BG_INDEX = {'defense_bench': 1, 'prosecution_bench': 2, 'witness_stand': 3,
            'judge_seat': 4, 'co_counsel': 5, 'court_room': 6}
BENCH_TILES, STAND_TILES = 0x18f720, 0x18f120   # desk sprite tiles (4bpp, 1D)
DESK_PAL = 0x198cf0                # their palette (OBJ palette 10)
# sprite pieces (x, y, first tile, w, h, hflip), as GS3 sets them up
DESKS = {
    'defense_bench': (BENCH_TILES, [(0, 128, 0, 64, 32, 0), (64, 128, 32, 64, 32, 0),
                                    (128, 128, 64, 64, 32, 0), (192, 128, 96, 16, 32, 0)]),
    'prosecution_bench': (BENCH_TILES, [(32, 128, 96, 16, 32, 1), (48, 128, 64, 64, 32, 1),
                                        (112, 128, 32, 64, 32, 1), (176, 128, 0, 64, 32, 1)]),
    'witness_stand': (STAND_TILES, [(24, 128, 0, 64, 32, 0), (88, 128, 32, 32, 32, 0),
                                    (120, 128, 32, 32, 32, 1), (152, 128, 0, 64, 32, 1)]),
}
DESK_DY = {'defense_bench': 0, 'prosecution_bench': 0, 'witness_stand': 2}
# The top of the GS1 witness stand: the row just below where the GS1 poses at
# the stand end, column by column (x from, x to, row), measured over the 180
# poses the Japanese scripts show there (each rendered in the game). GS3's
# stand is rounder: lowered by two rows it meets this line in the middle, but
# towards the ends its rim drops one to three rows below it, and the wall
# showed between the rim and the people (Larry's jacket, Redd White's sleeve,
# ...). Where the rim is lower, its top edge is drawn up to this line.
STAND_LINE = [(36, 44, 140), (45, 51, 139), (52, 65, 138), (66, 85, 137), (86, 159, 136),
              (160, 172, 137), (173, 186, 138), (187, 195, 139), (196, 204, 140)]
STAND_CORNER = 1                   # beyond the line the rim falls a row a column, as GS3's does
PAN = 0x484490                     # palette, then 80x20 tiles (640x160, 4bpp)
PAN_STEPS_SHORT, PAN_STEPS_LONG = 0x161618, 0x161638   # 16 x u16, in tiles
VIEW = {'defense_bench': 0, 'witness_stand': 520, 'prosecution_bench': 1040}
# GS1's three pans (gCourtScrollGfxPointers), forward direction
PANS = [('defense_bench', 'witness_stand', PAN_STEPS_SHORT),
        ('prosecution_bench', 'defense_bench', PAN_STEPS_LONG),
        ('prosecution_bench', 'witness_stand', PAN_STEPS_SHORT)]
SWAP_FRAME = 9                     # both people are off screen on this frame

def rgb555(c):
    return ((c & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, ((c >> 10) & 31) * 255 // 31)

def lz77(d, o):
    assert d[o] == 0x10, hex(o)
    size = d[o + 1] | d[o + 2] << 8 | d[o + 3] << 16
    out = bytearray(); i = o + 4
    while len(out) < size:
        fl = d[i]; i += 1
        for b in range(8):
            if len(out) >= size:
                break
            if fl & (0x80 >> b):
                x = d[i] << 8 | d[i + 1]; i += 2
                for _ in range((x >> 12) + 3):
                    out.append(out[-(x & 0xfff) - 1])
            else:
                out.append(d[i]); i += 1
    return bytes(out)

def tiles(raw, bpp, w):
    """tile data (row-major, w tiles wide) -> index array"""
    if bpp == 4:
        a = np.frombuffer(raw, np.uint8); px = np.stack([a & 15, a >> 4], 1).reshape(-1)
    else:
        px = np.frombuffer(raw, np.uint8)
    n = len(px) // 64
    h = n // w
    return px[:h * w * 64].reshape(h, w, 8, 8).transpose(0, 2, 1, 3).reshape(h * 8, w * 8).astype(int)

def background(d, k):
    """GS3 background k -> (indices, 16 or 256 RGB colours)"""
    ptr, flags = struct.unpack_from('<II', d, BG_TABLE + 8 * k)
    assert flags & 0xF == 0, 'only 240x160 backgrounds here'
    o = ptr - 0x08000000
    bpp = 4 if flags >> 31 else 8
    offs = struct.unpack_from('<10I', d, o)
    npal = 16 if bpp == 4 else 256
    pal = [rgb555(c) for c in struct.unpack_from('<%dH' % npal, d, o + offs[0])]
    starts = [offs[0] + npal * 2] + list(offs[1:])
    return tiles(b''.join(lz77(d, o + s) for s in starts), bpp, 30), pal

def desk(d, name):
    """the desk sprites of a bench -> index layer 160x240 (0 = none)"""
    base, pieces = DESKS[name]
    lay = np.zeros((160, 240), int)
    for x, y, t, w, h, hf in pieces:
        s = tiles(d[base + t * 32:base + (t + w * h // 64) * 32], 4, w // 8)
        if hf:
            s = s[:, ::-1]
        ys, xs = np.nonzero(s)
        ok = (x + xs >= 0) & (x + xs < 240) & (y + ys < 160)
        lay[y + ys[ok], x + xs[ok]] = s[ys[ok], xs[ok]]
    dy = DESK_DY[name]
    if dy:
        lay = np.vstack([np.zeros((dy, 240), int), lay[:-dy]])
    if name == 'witness_stand':
        lay = raise_rim(lay)
    return lay

def raise_rim(lay):
    """draw the stand's top edge up to the GS1 line (STAND_LINE) where it is
    lower: the outline moves up, the band under it gets taller; the rest of
    the stand stays where it is"""
    line = {x: r for a, b, r in STAND_LINE for x in range(a, b + 1)}
    first, last = STAND_LINE[0], STAND_LINE[-1]
    for x in range(first[0] - 8, first[0]):
        line[x] = first[2] + (first[0] - x) * STAND_CORNER
    for x in range(last[1] + 1, last[1] + 9):
        line[x] = last[2] + (x - last[1]) * STAND_CORNER
    out = lay.copy()
    for x, g in line.items():
        col = lay[:, x]
        if not col.any():
            continue
        t = int(np.nonzero(col)[0].min())
        if t > g:
            out[g, x] = col[t]
            out[g + 1:t + 1, x] = col[t + 1]
    return out

# --------------------------------------------------------------- output
def gs1_ui_palette():
    """palette entries 0-31 of GS1's 256-colour backgrounds (text box etc.)"""
    p = Image.open(os.path.join(ROOT, 'graphics/striped_images/backgrounds/court/judge_seat.png')).getpalette()
    return [tuple(p[3 * i:3 * i + 3]) for i in range(32)]

def save_png(path, idx, pal):
    pal = list(pal) + [(0, 0, 0)] * (256 - len(pal))
    im = Image.fromarray(idx.astype(np.uint8), 'P')
    im.putpalette([v for c in pal for v in c])
    im.save(path)

def gba_pal(pal):
    out = b''
    for r, g, b in list(pal) + [(0, 0, 0)] * (256 - len(pal)):
        out += struct.pack('<H', (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10)
    return out

def tile_bytes(idx):
    """index array (multiple of 8x8) -> 8bpp tiles, row-major"""
    h, w = idx.shape
    return idx.reshape(h // 8, 8, w // 8, 8).transpose(0, 2, 1, 3).astype(np.uint8).tobytes()

def main(gs3):
    d = open(gs3, 'rb').read()
    assert zlib.crc32(d) == GS3_CRC, 'not Gyakuten Saiban 3 (Japan), CRC32 51b6cf22'
    os.makedirs(OUT, exist_ok=True)
    ui = gs1_ui_palette()
    desk_pal = [rgb555(c) for c in struct.unpack_from('<16H', d, DESK_PAL)]

    # backgrounds: a 16-colour bench at 32-47, its desk at 48-63; the
    # 256-colour ones keep GS3's colours 32-255
    for name, k in BG_INDEX.items():
        idx, pal = background(d, k)
        if len(pal) == 16:
            assert idx.min() > 0
            idx = idx + 32
            if name in DESKS:
                lay = desk(d, name)
                idx[lay > 0] = 48 + lay[lay > 0]
            pal = ui + pal + desk_pal
        else:
            assert idx.min() >= 32
            pal = ui + pal[32:]
        save_png(os.path.join(OUT, name + '.png'), idx, pal)

    # the pans: GS3's picture and its mirror, the desks at their places
    pal_idx = tiles(d[PAN + 0x20:PAN + 0x20 + 80 * 20 * 32], 4, 80)
    pan_pal = [rgb555(c) for c in struct.unpack_from('<16H', d, PAN)]
    strip = np.hstack([pal_idx, pal_idx[:, ::-1]]) + 32        # 1280 px wide
    assert pal_idx.min() > 0
    desks = {name: desk(d, name) for name in DESKS}
    frame_pal = gba_pal(ui + pan_pal + desk_pal)
    blob = b''
    cams = []
    preview = []
    for start, end, table in PANS:
        steps = struct.unpack_from('<16H', d, table)
        span = abs(VIEW[end] - VIEW[start])
        assert steps[-1] * 8 == span, (start, end, steps)
        cam = [VIEW[start] + (8 * s if VIEW[end] > VIEW[start] else -8 * s) for s in steps]
        cams.append(cam)
        for x in cam:
            f = strip[:, x:x + 240].copy()
            for name, lay in desks.items():
                sx = VIEW[name] - x                      # where that view's screen is
                if -240 < sx < 240:
                    src = lay[:, max(0, -sx):240 - max(0, sx)]
                    dst = f[:, max(0, sx):max(0, sx) + src.shape[1]]
                    dst[src > 0] = 48 + src[src > 0]
            blob += frame_pal + tile_bytes(f)
            preview.append(f)
    for k, f in enumerate(preview):
        assert len(tile_bytes(f)) == 0x9600
    open(os.path.join(OUT, 'court_pan.bin'), 'wb').write(blob)
    with open(os.path.join(ROOT, 'include', 'en_court_pan.h'), 'w') as h:
        h.write('// generated by tools/en/port_gs3_court.py: the courtroom pans of\n'
                '// Gyakuten Saiban 3 (camera position on each of the 16 frames of each pan,\n'
                '// in pixels along the picture: defense bench 0, witness stand 520,\n'
                '// prosecution bench 1040)\n')
        h.write('#define EN_PAN_FRAME_SIZE 0x%X\n' % (0x200 + 0x9600))
        h.write('#define EN_PAN_SWAP_FRAME %d\n' % SWAP_FRAME)
        h.write('static const s16 sEnPanCamera[3][16] = {\n')
        for c in cams:
            h.write('    {' + ', '.join(str(x) for x in c) + '},\n')
        h.write('};\n')
        h.write('static const s16 sEnPanView[3][2] = {\n')
        for start, end, table in PANS:
            h.write('    {%d, %d}, // %s -> %s\n' % (VIEW[start], VIEW[end], start, end))
        h.write('};\n')
    with open(os.path.join(ROOT, 'data', 'en_court.s'), 'w') as o:
        o.write('@ generated by tools/en/port_gs3_court.py: the courtroom of Gyakuten Saiban 3\n'
                '\t.section en_data, "a"\n')
        for name in BG_INDEX:
            label = 'gEnCourt' + ''.join(w.title() for w in name.split('_'))
            o.write('\n\t.align 2\n\t.global %s\n%s:\n\t.incbin "graphics/en/court/%s.8bpp.striped"\n' % (label, label, name))
        o.write('\n\t.align 2\n\t.global gEnCourtPan\ngEnCourtPan:\n\t.incbin "graphics/en/court/court_pan.bin"\n')
    print('court backgrounds and %d pan frames written' % len(preview))
    return preview, ui + pan_pal + desk_pal

if __name__ == '__main__':
    main(sys.argv[1])
