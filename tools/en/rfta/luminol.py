#!/usr/bin/env python3
"""The fifth episode's luminol (the DS's luminol screen, its 0x020809xx-0x02082fxx),
from the DS.

The DS's luminol shows the room it is used in, tinted red (the colour's luma
in red alone: R' = 0.307 R + 0.552 G + 0.113 B, G' = B' = 0, measured), on
the touch screen; each touch sprays a puff of mist there. Its scenes
(0x020c971c, 12 bytes each: the room's background, a pointer to three
pictures) pick the room by its background, a wide room's right half being
the next scene; their stains ([0x020c0a70], 16 bytes a scene: a count and a
pointer to records of 0x28 bytes: state, x, y, w, h, a threshold, the flag,
the section, the stain's mask (w x h bytes: 1 inside, 2 the outline) and its
size) are in the screen's coordinates of that half. A spray whose 32 x 32
square meets a stain's rectangle starts the stain glowing: the glow (one
state for the whole stain, 0x02070364) climbs a step every second frame and
stops at 63 and at 103 (the table at 0x020c1c1c), so it takes three sprays,
each after the last has run its course, to reach 134: the stain is found
(0x02070dac: more of its pixels at 134 than the threshold, which with one
state is all of them). Its colour follows the state (0x020c1e1c, the
colours measured off the screen). Then corner marks round it for 32 frames,
a white flash, the stain's three pictures (24 frames each, a flash before
each, 0x02081320), and the stain's lines: the section of the chapter
(0x94 in the parking lot's tutorial) or one of file 35's C2-C8, which every
chapter that has the luminol carries (translate.py, LUMINOL_SHARED). The
flag is set then; finding 0x13 in chapter 22 also sets 0xD and finding 0x17
in chapter 29 sets 0xE (0x02081460). The pictures of a scene's stains are
the scene's, the second stain of the evidence room's right half (section C6)
taking the next scene's (0x020817c8).

Here the room is the GBA's background, cut from the DS's as backgrounds.py
cuts it (8 across for a 256-wide picture, 16 for a 512-wide one, 16 down),
so a stain's place in the GBA's picture is the DS's x plus the half's scroll
(0 or 256) less that margin, and y less 16.

Writes graphics/en/rfta/luminol.bin (each stain's mask as a 64 x 32 sprite,
the mist, the nozzle, the corner mark and the cross, 4bpp), data/rfta/
luminol.s (section rfta_low) and src/data/en_rfta_luminol.h (gEnStains,
the colours). usage: luminol.py"""
import os, sys, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import dsbin
from dsdata import data
from sfx import NEW_SES
ROOT = os.path.join(HERE, '..', '..', '..')
SCENES, SCENE_COUNT = 0x020c971c, 10
STAIN_TABLE_PTR = 0x020c0a70
SHARED_FIRST, SHARED_LAST = 0xC2, 0xC8          # file 35's stain sections
LUMINOL_EVIDENCE = 0x90
SPRAY_SEQ = 0x1A4                               # the DS's SE0C4, each spray (0x020805b0)
# a stain's mask sprite: 64 x 32 (the largest stain, the Chief's office floor, is 48 x 24)
SPRITE_W, SPRITE_H = 64, 32
# the glow's colour by state (the DS's 0x020c1e1c: 0, 1-31, then 8 states a colour),
# measured off the DS's screen (6, 7, 11 and 12 between their neighbours)
GLOW = [None, (200, 0, 96), (248, 0, 128), (240, 16, 104), (240, 32, 72), (224, 64, 104),
        (222, 104, 139), (219, 144, 173), (216, 184, 208), (200, 168, 208), (184, 160, 200),
        (181, 184, 216), (179, 208, 232), (176, 232, 248), (144, 216, 248), (144, 216, 248)]
FOUND_INSIDE, FOUND_OUTLINE = (144, 216, 248), (40, 96, 248)
# the sprites' palette (OBJ palette 8 while the luminol is up): the mist's
# eight shades (added to the picture under it), the nozzle, the corner marks, the cross
MIST = (248, 192, 192)
NOZZLE, NOZZLE_EDGE = (248, 216, 216), (96, 0, 32)
MARK_OUT, MARK_IN = (96, 224, 248), (200, 232, 248)
CROSS = (240, 240, 240)

def scenes():
    d = dsbin.data(); B = dsbin.BASE
    out = []
    for s in range(SCENE_COUNT):
        bg, n, p = struct.unpack_from('<3I', d, SCENES - B + 12 * s)
        out.append((bg, struct.unpack_from('<3I', d, p - B)))
    return out

def stains():
    """(scene, index in the scene, record) for every stain, records as dicts"""
    d = dsbin.data(); B = dsbin.BASE
    base = dsbin.u32(STAIN_TABLE_PTR)
    out = []
    for s in range(SCENE_COUNT):
        cnt, _, _, p = struct.unpack_from('<4I', d, base - B + 16 * s)
        for k in range(cnt):
            r = struct.unpack_from('<10I', d, p - B + 0x28 * k)
            out.append((s, k, dict(x=r[1], y=r[2], w=r[3], h=r[4], threshold=r[5], flag=r[6], section=r[7], gfx=r[8], size=r[9])))
    return out

def rgb5(c):
    return (c[0] >> 3) | (c[1] >> 3) << 5 | (c[2] >> 3) << 10

def tiles(img):
    """a (h, w) array of 4-bit pixels -> 4bpp tiles, row by row (1D mapping)"""
    h, w = img.shape
    out = bytearray()
    for ty in range(h // 8):
        for tx in range(w // 8):
            t = img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]
            for row in t:
                for x in range(0, 8, 2):
                    out.append(int(row[x]) | int(row[x + 1]) << 4)
    return bytes(out)

def mist():
    """64 x 64: a soft disc about 48 across in blocks of 4 x 4 pixels, as the
    DS draws its mist, shades 1-8 (8 the brightest)"""
    rng = np.random.RandomState(5)
    y, x = np.mgrid[0:16, 0:16] + 0.5
    r = np.hypot(x - 8, y - 8)
    ang = np.arctan2(y - 8, x - 8)
    edge = 6.2 + 0.4 * np.sin(5 * ang + 1.0) + 0.3 * np.sin(9 * ang + 2.0)
    v = np.clip(1.1 - (r / edge) ** 2, 0, 1) + rng.uniform(-0.05, 0.05, r.shape)
    q = np.round(np.clip(v, 0, 1) * 8).astype(np.uint8)
    q[v <= 0.06] = 0
    return np.kron(q, np.ones((4, 4), np.uint8))

def nozzle():
    """32 x 32: the spray's aim (centre at 16, 16), a ring as wide as the
    spray's square and a small cross, light with a dark edge"""
    y, x = np.mgrid[0:32, 0:32] + 0.5
    r = np.hypot(x - 16, y - 16)
    img = np.zeros((32, 32), np.uint8)
    ring = (r >= 13) & (r < 14.4)
    edge = ((r >= 12) & (r < 13)) | ((r >= 14.4) & (r < 15.4))
    img[edge] = 10
    img[ring] = 9
    for k in range(13, 20):
        if k != 16:
            img[16, k] = img[k, 16] = 9
    for yy, xx in ((15, 13), (17, 13), (15, 19), (17, 19), (13, 15), (13, 17), (19, 15), (19, 17)):
        img[yy, xx] = 10
    return img

def mark():
    """16 x 16: the top-left corner mark (the others flipped): two lines of 2,
    arms of 12 by 11"""
    img = np.zeros((16, 16), np.uint8)
    img[0, 0:12] = 11; img[0:11, 0] = 11
    img[1, 1:12] = 12; img[1:11, 1] = 12
    return img

def cross():
    img = np.zeros((16, 16), np.uint8)
    img[7, 3:12] = 13; img[3:12, 7] = 13
    return img

def spray_label():
    """the Court Record's "Spray" (the DS's button), in the labels' style
    (tools/en/make_ui_text.py: the DS font outlined, ink 12, edge 10): 64 x 16,
    its descenders in (the font's two empty top rows left out)"""
    from dsfont import render, outline
    m = render('Spray')[2:16]
    p = np.zeros((16, 64), np.uint8)
    p[1:1 + m.shape[0], 1:1 + m.shape[1]] = m
    img = np.zeros((16, 64), np.uint8)
    img[outline(p) > 0] = 10
    img[p > 0] = 12
    return img

def entries():
    """the stains as the GBA has them (dicts: bg, flag, shared, section, x, y,
    w, h, zoom, mask, scene); tools that play the game read them here too"""
    d = data()
    sc = scenes()
    bg_w = {}                       # background -> the DS picture's width
    import backgrounds
    for bg, _ in sc[1:]:
        ctrl = backgrounds.entry(bg)[2]
        bg_w[bg] = 512 if ctrl & 1 else 384 if ctrl & 2 else 256
    first_scene = {}
    for s, (bg, _) in enumerate(sc):
        if s and bg not in first_scene:
            first_scene[bg] = s
    out = []
    for s, k, r in stains():
        bg, pics = sc[s]
        half = s - first_scene[bg]
        assert half in (0, 1), (s, bg)
        scroll = {512: 256, 384: 128}.get(bg_w[bg], 0) * half
        margin = {512: 16, 384: 12, 256: 8}[bg_w[bg]]
        gx, gy = r['x'] + scroll - margin, r['y'] - 16
        mask = np.frombuffer(d[r['gfx']:r['gfx'] + r['w'] * r['h']], np.uint8).reshape(r['h'], r['w'])
        assert r['size'] == r['w'] * r['h'] and set(np.unique(mask)) <= {0, 1, 2}
        # (one state for the whole stain: found once it reaches 134, if the
        # stain has more pixels than its threshold)
        assert (mask > 0).sum() > r['threshold'], (s, k, (mask > 0).sum(), r['threshold'])
        zoom = sc[s + k][1]
        if r['section'] >= SHARED_FIRST:
            shared, section = r['section'] - SHARED_FIRST + 1, 0
            assert r['section'] <= SHARED_LAST
        else:
            shared, section = 0, r['section']
        out.append(dict(bg=bg, flag=r['flag'], shared=shared, section=section, x=gx, y=gy, w=r['w'], h=r['h'],
                        zoom=zoom, mask=mask, scene=s))
    return out

def main():
    blob = bytearray(); entries_ = entries()
    for e in entries_:
        spr = np.zeros((SPRITE_H, SPRITE_W), np.uint8); spr[:e['h'], :e['w']] = e['mask']
        e['offset'] = len(blob)
        blob += tiles(spr)
    off_mist = len(blob); blob += tiles(mist())
    off_nozzle = len(blob); blob += tiles(nozzle())
    off_mark = len(blob); blob += tiles(mark())
    off_cross = len(blob); blob += tiles(cross())
    label = spray_label()
    off_label = len(blob); blob += tiles(label[:, :32]) + tiles(label[:, 32:])
    os.makedirs(os.path.join(ROOT, 'graphics', 'en', 'rfta'), exist_ok=True)
    open(os.path.join(ROOT, 'graphics', 'en', 'rfta', 'luminol.bin'), 'wb').write(blob)
    asm = ['@ generated by tools/en/rfta/luminol.py: the luminol\'s sprites (4bpp)',
           '\t.section rfta_low, "a"', '\t.align 2', '\t.global gEnLuminolGfx', 'gEnLuminolGfx:',
           '\t.incbin "graphics/en/rfta/luminol.bin"']
    open(os.path.join(ROOT, 'data', 'rfta', 'luminol.s'), 'w').write('\n'.join(asm) + '\n')
    pal = [0] * 16
    for i in range(1, 9):
        pal[i] = rgb5(tuple(int(round(c * i / 8)) for c in MIST))
    pal[9], pal[10], pal[11], pal[12], pal[13] = rgb5(NOZZLE), rgb5(NOZZLE_EDGE), rgb5(MARK_OUT), rgb5(MARK_IN), rgb5(CROSS)
    h = ['// generated by tools/en/rfta/luminol.py: the luminol\'s stains, from the DS',
         '// (x, y: in the room\'s picture; tiles: the stain\'s mask, 64 x 32, 1 inside and 2 the',
         '// outline; shared: file 35\'s C2-C8 as 1-7, else the chapter\'s own section)',
         '#define EN_LUMINOL_EVIDENCE 0x%02X' % LUMINOL_EVIDENCE,
         '#define EN_LUMINOL_GFX_MIST 0x%X' % off_mist, '#define EN_LUMINOL_GFX_NOZZLE 0x%X' % off_nozzle,
         '#define EN_LUMINOL_GFX_MARK 0x%X' % off_mark, '#define EN_LUMINOL_GFX_CROSS 0x%X' % off_cross,
         '#define EN_LUMINOL_GFX_SPRAY 0x%X     // "Spray": two 32 x 16 halves' % off_label,
         '#define EN_STAIN_COUNT %d' % len(entries_),
         '#define EN_LUMINOL_SE_SPRAY %d    // the DS\'s SE0C4 (sfx.py)' % NEW_SES[SPRAY_SEQ],
         'static const struct EnStain sEnStains[EN_STAIN_COUNT] = {']
    for e in entries_:
        h.append('    { .bg = 0x%02X, .flag = 0x%02X, .shared = %d, .section = 0x%X, .x = %d, .y = %d, .w = %d, .h = %d, '
                 '.zoom = { 0x%02X, 0x%02X, 0x%02X }, .gfx = 0x%X }, // DS scene %d' %
                 (e['bg'], e['flag'], e['shared'], e['section'], e['x'], e['y'], e['w'], e['h'], *e['zoom'], e['offset'], e['scene']))
    h.append('};')
    h.append('static const u16 sEnLuminolPalette[16] = { %s };' % ', '.join('0x%04X' % c for c in pal))
    h.append('// the glow by state / 8 (states 1-31: 1; 32 on: 2 + (state - 32) / 8)')
    h.append('static const u16 sEnGlowColors[16] = { 0, %s };' % ', '.join('0x%04X' % rgb5(c) for c in GLOW[1:]))
    h.append('#define EN_GLOW_FOUND_INSIDE 0x%04X' % rgb5(FOUND_INSIDE))
    h.append('#define EN_GLOW_FOUND_OUTLINE 0x%04X' % rgb5(FOUND_OUTLINE))
    open(os.path.join(ROOT, 'src', 'data', 'en_rfta_luminol.h'), 'w').write('\n'.join(h) + '\n')
    
    print('%d stains, %d bytes of sprites' % (len(entries_), len(blob)))
    pics = sorted(set(p for e in entries_ for p in e['zoom']))
    print('pictures', ' '.join('%02x' % p for p in pics))

if __name__ == '__main__':
    main()
