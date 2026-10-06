#!/usr/bin/env python3
"""Save / Load screens laid out as on the DS English release.

Everything is taken from the DS: the plates ("SAVE" / "LOAD"), the Yes / No /
Saving... / From save point. / From chapter start. buttons with their normal
and pressed palettes, the orange selection brackets and the "Press START..."
hint are the DS images (data.bin); the grey courtroom behind them is the DS
bottom-screen background (assets/ds_menu_courtroom.png, the background layer
captured from the DS) and the plate lettering uses the DS menu font
(assets/ds_plate_font.json: every glyph, its advance and offset, measured from
text the DS itself drew on the save plate).

The DS screen is 256x192 and the GBA one 240x160: everything keeps its DS size
and horizontal place (8 px cut on each side); vertically the save screen pulls
the plate up 8 px and the buttons / hint up 20 / 28 px, the load screen keeps
the DS layout.

usage: make_menus.py [preview.png]
writes graphics/en/menu/*, include/en_menu_gfx.h, data/en_menu.s and
graphics/striped_images/courtroom_background.png"""
import os, sys, json, struct, shutil
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from dsdata import data
from dsfont import PUNCT

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
OUT = os.path.join(ROOT, 'graphics/en/menu')
os.makedirs(OUT, exist_ok=True)

# DS images (offsets of the 0x14-byte image headers in the US data.bin)
IMG = {'plate_save': 0x2577498, 'plate_load': 0x257b4cc, 'hint': 0x254d57c,
       'yes': 0x2573eec, 'no': 0x2575014, 'saving': 0x2576370,
       'savept': 0x256c468, 'chstart': 0x256e590, 'bracket': 0x25758a8}

def ds_image(name):
    """-> (pixels HxW uint8, list of 16-colour palettes as (r,g,b))"""
    off = IMG[name]
    d = data()
    h = d[off:off + 0x14]
    assert h[0] == 3 and h[4] == 0x14, name
    w, ht = 1 << (h[1] + 3), 1 << (h[2] + 3)
    size, poff, psize = struct.unpack_from('<III', h, 8)
    assert size == w * ht // 2
    raw = np.frombuffer(d[off + 0x14:off + 0x14 + size], np.uint8)
    a = np.zeros(size * 2, np.uint8)
    a[0::2] = raw & 15
    a[1::2] = raw >> 4
    cols = struct.unpack_from('<%dH' % (psize // 2), d, off + poff)
    rgb = [((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in cols]
    return a.reshape(ht, w), [rgb[i:i + 16] for i in range(0, len(rgb), 16)]

def bgr555(c):
    r, g, b = c
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)

def pal_bytes(cols):
    cols = list(cols) + [(0, 0, 0)] * (16 - len(cols))
    return struct.pack('<16H', *[bgr555(c) for c in cols])

def tiles_4bpp(a):
    """HxW (multiples of 8) -> 4bpp tile bytes, row-major tiles"""
    out = bytearray()
    for ty in range(a.shape[0] // 8):
        for tx in range(a.shape[1] // 8):
            t = a[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]
            for y in range(8):
                for x in range(0, 8, 2):
                    out.append(int(t[y, x]) | (int(t[y, x + 1]) << 4))
    return bytes(out)

def obj_sprites(a, x0, widths):
    """cut a 32-row strip into sprites of the given widths starting at x0 ->
    4bpp bytes in 1D-mapping order"""
    out = b''
    for w in widths:
        out += tiles_4bpp(a[:, x0:x0 + w])
        x0 += w
    return out

# ---------------------------------------------------------------------------
# background: the DS grey courtroom, centred crop
BG_CROP = (8, 16)          # x, y of the 240x160 window in the 256x192 DS picture
src = Image.open(os.path.join(HERE, 'assets/ds_menu_courtroom.png')).convert('RGB')
crop = np.array(src)[BG_CROP[1]:BG_CROP[1] + 160, BG_CROP[0]:BG_CROP[0] + 240]
cols = sorted(set(map(tuple, crop.reshape(-1, 3).tolist())))
assert len(cols) <= 15, len(cols)
lut = {c: i + 1 for i, c in enumerate(cols)}     # index 0 (transparent) unused
idx = np.array([[lut[tuple(p)] for p in row] for row in crop.tolist()], np.uint8)
bgpath = os.path.join(ROOT, 'graphics/striped_images/courtroom_background.png')
if not os.path.exists(bgpath + '.orig'):
    shutil.copy(bgpath, bgpath + '.orig')
im = Image.fromarray(idx, 'P')
flat = [0, 0, 0]
for c in cols:
    flat += list(c)
flat += [0, 0, 0] * (16 - 1 - len(cols))
im.putpalette(flat)
im.save(bgpath)

# ---------------------------------------------------------------------------
# BG layer: plates, hint, stripe tile. One BG palette (EN_MENU_BG_PAL).
plate_s, ppal = ds_image('plate_save')
plate_l, ppal2 = ds_image('plate_load')
hint, hpal = ds_image('hint')
assert ppal == ppal2
bgcols = [(0, 0, 0)] + ppal[0][1:9]                # plate colours 1..8
def colour(c):
    if c not in bgcols:
        bgcols.append(c)
    return bgcols.index(c)
hint_map = {0: 0}
for i in range(1, 4):
    hint_map[i] = colour(hpal[0][i])
STRIPE = colour((112, 112, 112))
assert len(bgcols) <= 16, bgcols
hint = np.vectorize(hint_map.get)(hint).astype(np.uint8)

BG_TILE_BASE = 128         # BG VRAM 0x1000 (charblock 0, after the common tiles)
tiles = [bytes(32)]        # tile 0 of the block: blank
stripe = np.zeros((8, 8), np.uint8)
stripe[2, :] = STRIPE
stripe[6, :] = STRIPE
tiles.append(tiles_4bpp(stripe))
tile_ids = {tiles[0]: 0, tiles[1]: 1}

def flips(t):
    """the four flipped versions of an 8x8 tile, with their map flip bits"""
    return [(t, 0), (t[:, ::-1], 0x400), (t[::-1, :], 0x800), (t[::-1, ::-1], 0xC00)]

def add_tile(t):
    for v, bits in flips(t):
        b = tiles_4bpp(v)
        if b in tile_ids:
            return tile_ids[b] | bits
    b = tiles_4bpp(t)
    tile_ids[b] = len(tiles)
    tiles.append(b)
    return tile_ids[b]

EN_MENU_BG_PAL = 3
def put(mapbuf, img, mx, my, rows, cols_):
    """copy tiles of img (tile rows / cols given) to map position (mx, my)"""
    for r in rows:
        for c in cols_:
            t = img[r * 8:r * 8 + 8, c * 8:c * 8 + 8]
            if not t.any():
                continue
            v = add_tile(t)
            mapbuf[(my + r - rows[0]) * 32 + mx + c - cols_[0]] = (v + BG_TILE_BASE) | (EN_MENU_BG_PAL << 12)

# BG2 is scrolled 8 px left (hofs 8), so map x == DS screen x. The plates are
# placed with their DS image origin at map (0, 0): plate at y 5..90.
maps = {}
for name, plate, with_hint in (('save', plate_s, True), ('load', plate_l, False), ('clear', plate_s, False)):
    m = [0] * (32 * 20)
    put(m, plate, 0, 0, range(0, 12), range(0, 32))
    if with_hint:
        # DS hint image origin (32, 156); here at (32, 128): text at y 129..156
        put(m, hint, 4, 16, range(0, 4), range(0, 32 - 4))
    maps[name] = m
assert len(tiles) <= 320, len(tiles)
open(os.path.join(OUT, 'menu_bg.4bpp'), 'wb').write(b''.join(tiles))
open(os.path.join(OUT, 'menu_bg.gbapal'), 'wb').write(pal_bytes(bgcols))
for name, m in maps.items():
    open(os.path.join(OUT, 'map_%s.bin' % name), 'wb').write(struct.pack('<%dH' % len(m), *m))

# ---------------------------------------------------------------------------
# OBJ: buttons (normal, pressed and greyed-out palettes), brackets, plate-text colour
yes, bpal = ds_image('yes')
no, _ = ds_image('no')
saving, _ = ds_image('saving')
savept, _ = ds_image('savept')
chstart, _ = ds_image('chstart')
bracket, kpal = ds_image('bracket')
short = b''.join(obj_sprites(b, 0, (64, 32)) for b in (yes, no, saving))     # 3 x 48 tiles
long_ = b''.join(obj_sprites(b, 32, (64, 64, 64)) for b in (savept, chstart))  # 2 x 96 tiles
br = b''.join(tiles_4bpp(bracket[y:y + 16, x:x + 16]) for y, x in ((0, 0), (0, 16), (16, 0), (16, 16)))
open(os.path.join(OUT, 'buttons_short.4bpp'), 'wb').write(short)
open(os.path.join(OUT, 'buttons_long.4bpp'), 'wb').write(long_)
open(os.path.join(OUT, 'bracket.4bpp'), 'wb').write(br)
TEXT_COLOUR = (240, 240, 240)
open(os.path.join(OUT, 'menu_obj.gbapal'), 'wb').write(
    pal_bytes(bpal[0]) + pal_bytes(bpal[1]) + pal_bytes(bpal[2]) + pal_bytes(kpal[0]) + pal_bytes([(0, 0, 0), TEXT_COLOUR]))

# the bracket image's corners, measured: where its quadrants sit around a box
# 2 px larger than the button face (DS: Yes face x 23..114, y 119..144 ->
# brackets from (21, 117) to (116, 146))
qs = [bracket[y:y + 16, x:x + 16] for y, x in ((0, 0), (0, 16), (16, 0), (16, 16))]

# ---------------------------------------------------------------------------
# plate font: 14 rows (cell rows 2..15) x 16 px per glyph, 4bpp, value 1
font = json.load(open(os.path.join(HERE, 'assets/ds_plate_font.json')))
def code(ch):
    if ch.isdigit(): return ord(ch) - 48
    if 'A' <= ch <= 'Z': return 10 + ord(ch) - 65
    if 'a' <= ch <= 'z': return 36 + ord(ch) - 97
    if ch == ' ': return 0xFF
    return PUNCT[ch]
PLATE_CODES = 0x110
PLATE_ROWS = 14
glyphs = bytearray(PLATE_CODES * PLATE_ROWS * 8)
adv = bytearray(PLATE_CODES)
off = bytearray(PLATE_CODES)
for ch, g in font.items():
    c = code(ch)
    assert c < PLATE_CODES, ch
    adv[c] = g['adv']
    off[c] = g['off'] & 0xFF
    rows = g['rows']
    assert not rows or len(rows) == 16
    for y in range(2, 16 if rows else 2):
        assert '#' not in ''.join(rows[:2]), ch
        for x, p in enumerate(rows[y]):
            if p == '#':
                o = (c * PLATE_ROWS + y - 2) * 8 + x // 2
                glyphs[o] |= 1 << (4 * (x & 1))
open(os.path.join(OUT, 'plate_font.bin'), 'wb').write(bytes(glyphs))
open(os.path.join(OUT, 'plate_font_adv.bin'), 'wb').write(bytes(adv))
open(os.path.join(OUT, 'plate_font_off.bin'), 'wb').write(bytes(off))

# ---------------------------------------------------------------------------
SYMS = [('gEnMenuBgTiles', 'menu_bg.4bpp'), ('gEnMenuBgPal', 'menu_bg.gbapal'),
        ('gEnMenuMapSave', 'map_save.bin'), ('gEnMenuMapLoad', 'map_load.bin'),
        ('gEnMenuMapClear', 'map_clear.bin'),
        ('gEnMenuButtonsShort', 'buttons_short.4bpp'), ('gEnMenuButtonsLong', 'buttons_long.4bpp'),
        ('gEnMenuBracket', 'bracket.4bpp'), ('gEnMenuObjPal', 'menu_obj.gbapal'),
        ('gEnPlateFont', 'plate_font.bin'), ('gEnPlateFontAdv', 'plate_font_adv.bin'),
        ('gEnPlateFontOff', 'plate_font_off.bin')]
with open(os.path.join(ROOT, 'data/en_menu.s'), 'w') as f:
    f.write('@ generated by tools/en/make_menus.py\n\t.section en_data, "a"\n')
    for sym, fn in SYMS:
        f.write('\n\t.align 2\n\t.global %s\n%s:\n\t.incbin "graphics/en/menu/%s"\n' % (sym, sym, fn))
with open(os.path.join(ROOT, 'include/en_menu_gfx.h'), 'w') as f:
    f.write('// generated by tools/en/make_menus.py\n#ifndef GUARD_EN_MENU_GFX_H\n#define GUARD_EN_MENU_GFX_H\n\n')
    for sym, fn in SYMS:
        t = 'u16' if fn.endswith(('.bin', '.gbapal')) and 'font' not in fn else 'u8'
        f.write('extern const %s %s[];\n' % (t, sym))
    f.write('\n#define EN_MENU_BG_TILE_BASE %d\n#define EN_MENU_BG_TILE_COUNT %d\n' % (BG_TILE_BASE, len(tiles)))
    f.write('#define EN_MENU_BG_PAL %d\n#define EN_MENU_STRIPE_TILE %d\n' % (EN_MENU_BG_PAL, BG_TILE_BASE + 1))
    f.write('#define EN_MENU_SHORT_BUTTON_BYTES %d\n#define EN_MENU_LONG_BUTTON_BYTES %d\n' % (len(short) // 3, len(long_) // 2))
    f.write('#define EN_PLATE_FONT_CODES %d\n#define EN_PLATE_FONT_ROWS %d\n' % (PLATE_CODES, PLATE_ROWS))
    f.write('\n#endif // GUARD_EN_MENU_GFX_H\n')
print('menus: %d BG tiles, %d BG colours, %d glyphs' % (len(tiles), len(bgcols), len(font)))

# ---------------------------------------------------------------------------
# preview: the GBA save / load screens composed from the generated data, next
# to the DS screens they are taken from
if len(sys.argv) > 1:
    def rgb(img, pal):
        return np.array(pal, np.uint8)[img]
    def compose(kind):
        scr = np.array(src)[BG_CROP[1]:BG_CROP[1] + 160, BG_CROP[0]:BG_CROP[0] + 240].copy()
        def blit(img, pal, x, y):
            for yy in range(img.shape[0]):
                for xx in range(img.shape[1]):
                    v = img[yy, xx]
                    if v and 0 <= y + yy < 160 and 0 <= x + xx < 240:
                        scr[y + yy, x + xx] = pal[v]
        if kind == 'save':
            blit(plate_s, ppal[0], -8, 0)
            hp = {hint_map[i]: hpal[0][i] for i in range(1, 4)}
            for yy in range(32):
                for xx in range(256):
                    v = hint[yy, xx]
                    if v and 0 <= 128 + yy < 160 and 0 <= 24 + xx < 240:
                        scr[128 + yy, 24 + xx] = hp[v]
            blit(yes[:, :96], bpal[0], 11, 96)
            blit(no[:, :96], bpal[0], 128, 96)
            bx0, by0, bx1, by1 = 128 + 4 - 2, 96 + 3 - 2, 128 + 95 + 2, 96 + 28 + 2
        else:
            blit(plate_l, ppal[0], -8, 0)
            blit(savept[:, 32:224], bpal[0], 24, 96)
            blit(chstart[:, 32:224], bpal[0], 24, 128)
            bx0, by0, bx1, by1 = 24 - 2, 96 + 3 - 2, 24 + 191 + 2, 96 + 28 + 2
        blit(qs[0], kpal[0], bx0, by0)
        blit(qs[1], kpal[0], bx1 - 15, by0)
        blit(qs[2], kpal[0], bx0, by1 - 15)
        blit(qs[3], kpal[0], bx1 - 15, by1 - 15)
        for y in range(2, 160, 4):
            scr[y] = np.minimum(248, scr[y].astype(int) + 24 * (scr[y] > 0)).astype(np.uint8)
        return Image.fromarray(scr)
    a, b = compose('save'), compose('load')
    sheet = Image.new('RGB', (2 * 256 + 8, 2 * 192 + 8), 'white')
    sheet.paste(a, (8, 16)); sheet.paste(b, (8, 192 + 8 + 16))
    ds = os.path.join(HERE, '..', '..', '..', 'dsh')
    for k, f in enumerate(('sv_all.png', 'lo_Lall.png')):
        p = os.path.join(ds, f)
        if os.path.exists(p):
            sheet.paste(Image.open(p).convert('RGB'), (264, k * 200))
    sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
    sheet.save(sys.argv[1])
