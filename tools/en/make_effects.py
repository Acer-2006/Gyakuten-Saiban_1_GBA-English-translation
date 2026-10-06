#!/usr/bin/env python3
"""English effect graphics for the GBA court, taken from the English DS release.

  Testimony / cross-examination banners  DS data.bin archive 0x2202220,
      graphics 312 and the six sequences packed in 313 (full banner with its
      shine for each, and the two halves that slide in). The GBA animation
      engine reads this format as it is (compressed tiles, 8 palettes), so the
      DS bytes are used unchanged.
  Objection! / Hold it! / Take that!     DS entries 316, 322, 328. The DS
      bubbles fill the 256x192 screen; they are drawn at 60% (154x115) so they
      fit the GBA sprite memory the original bubbles used, re-tiled into GBA
      sprites, same 16-colour palette.
  Guilty / Not Guilty                    the DS English letter sprites
      (data.bin 0x1aadb94..) and their placement table from the DS program
      (arm9 0x020b45b0 / 0x020b4640): one sprite per letter, each zooming from
      2x to 1x after its own delay. Drawn at 90% so "Not Guilty" fits 240 px.

Writes graphics/en/effects/* and include/en_effects.h."""
import os, sys, struct
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import animfmt
from dsdata import data
from effects_common import ds_entry, render_indexed, scale_indexed, cover, SIZE_INDEX

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
OUT = os.path.join(ROOT, 'graphics', 'en', 'effects')
ARM9 = os.environ.get('DS_ARM9', os.path.join(ROOT, '..', 'ds_arm9.bin'))

def write(name, b):
    with open(os.path.join(OUT, name), 'wb') as f:
        f.write(b)

def tiles_of(img, x0, y0, w, h):
    """4bpp tiles of a w x h pixel region, row-major (1D sprite mapping)"""
    out = bytearray()
    for ty in range(h // 8):
        for tx in range(w // 8):
            t = img[y0 + ty * 8:y0 + ty * 8 + 8, x0 + tx * 8:x0 + tx * 8 + 8]
            for row in t:
                for k in range(0, 8, 2):
                    out.append(int(row[k]) | int(row[k + 1]) << 4)
    return bytes(out)

# ------------------------------------------------------------------ banners
BANNER_GFX, BANNER_SEQ = 312, 313
BANNER_SUBS = [('testimony', 0x000), ('cross', 0x234), ('testimony_left', 0x434),
               ('testimony_right', 0x468), ('cross_left', 0x49c), ('cross_right', 0x4c8)]

def sub_seq(seq, start):
    q = seq[start:]
    fr = animfmt.frames(q)
    end = max(sd + 4 + 4 * struct.unpack_from('<H', q, sd)[0] for sd, *_ in fr)
    assert struct.unpack_from('<I', q, 4)[0] == 0          # graphics at offset 0
    return q[:end], fr

def vram_need(seq, fr):
    best = 0
    for f in fr:
        sp = animfmt.sprites(seq, f[0])
        best = max(best, sum(animfmt.SIZES[d >> 12][0] * animfmt.SIZES[d >> 12][1] // 2 for _, _, d in sp))
    return best, max(len(animfmt.sprites(seq, f[0])) for f in fr)

def banners(report):
    gfx = ds_entry(BANNER_GFX)
    write('banner.gfx', gfx + b'\0' * (-len(gfx) % 4))
    seq = ds_entry(BANNER_SEQ)
    for name, start in BANNER_SUBS:
        q, fr = sub_seq(seq, start)
        write('banner_%s.seq' % name, q)
        report.append('banner %-16s %2d frames, %5d bytes VRAM, %2d sprites' % ((name, len(fr)) + vram_need(q, fr)))

# ------------------------------------------------------------------ bubbles
BUBBLES = [('objection', 316), ('holdit', 322), ('takethat', 328)]
BUBBLE_SCALE = 0.6
BUBBLE_TILES = 256                 # OBJ_VRAM0+0x3800 .. +0x57FF
BUBBLE_MAX_SPRITES = 28

def bubble(name, entry, report):
    g, q = ds_entry(entry), ds_entry(entry + 1)
    fr = animfmt.frames(q)
    idx, _ = render_indexed(g, q, 0, (256, 192), (128, 96))
    for k in range(1, len(fr)):
        assert (render_indexed(g, q, k, (256, 192), (128, 96))[0] == idx).all()
    colors = animfmt.palettes(g)[0]
    used = sorted(set(np.unique(idx)) - {0})
    s = scale_indexed(idx, colors, BUBBLE_SCALE, used)
    # tile alignment with the fewest non-empty tiles
    best = None
    for oy in range(8):
        for ox in range(8):
            H, W = (s.shape[0] + oy + 7) // 8, (s.shape[1] + ox + 7) // 8
            pad = np.zeros((H * 8, W * 8), np.uint8)
            pad[oy:oy + s.shape[0], ox:ox + s.shape[1]] = s
            filled = pad.reshape(H, 8, W, 8).any(3).any(1)
            if best is None or filled.sum() < best[0]:
                best = (filled.sum(), ox, oy, pad, filled)
    _, ox, oy, pad, filled = best
    # fewest sprites that still fit the sprite memory
    options = []
    for wc in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0):
        r = cover(filled, wc)
        options.append((sum(w * h for _, _, w, h in r), len(r), wc, r))
    fit = [o for o in options if o[0] <= BUBBLE_TILES and o[1] <= BUBBLE_MAX_SPRITES]
    assert fit, (name, [(o[0], o[1]) for o in options])
    tiles_used, nspr, wc, rects = min(fit, key=lambda o: (o[1], o[0]))
    # bubble centre (DS screen centre, scaled) -> animation origin
    cx = ox + 128 * BUBBLE_SCALE
    cy = oy + 96 * BUBBLE_SCALE
    gfx = bytearray(struct.pack('<I', 1))
    gfx += g[4:4 + 32]                                      # the DS palette as is
    tmpl = bytearray(struct.pack('<HH', len(rects), 0))
    tile = 0
    M = 64                                                  # rects may hang over the edge
    big = np.zeros((pad.shape[0] + 2 * M, pad.shape[1] + 2 * M), np.uint8)
    big[M:M + pad.shape[0], M:M + pad.shape[1]] = pad
    for tx, ty, tw, th in rects:
        gfx += tiles_of(big, M + tx * 8, M + ty * 8, tw * 8, th * 8)
        x = int(round(tx * 8 - cx)); y = int(round(ty * 8 - cy))
        assert -128 <= x and x + tw * 8 <= 127 and -128 <= y and y + th * 8 <= 127
        tmpl += struct.pack('<bbH', x, y, SIZE_INDEX[(tw, th)] << 12 | tile)
        tile += tw * th
    seq = bytearray(q[:8])                                  # header: frame count, graphics offset 0
    assert struct.unpack_from('<I', q, 4)[0] == 0
    for sd, dur, fl, song, act in fr:
        seq += struct.pack('<HBBBBH', 8 + 8 * len(fr), dur, 0, song, act, 0)
    seq += tmpl
    write('bubble_%s.gfx' % name, bytes(gfx))
    write('bubble_%s.seq' % name, bytes(seq))
    report.append('bubble %-9s %dx%d, %d tiles in %d sprites, frames %s'
                  % (name, s.shape[1], s.shape[0], tiles_used, nspr, [f[1] for f in fr]))
    return nspr

# ------------------------------------------------------------------ verdict
VERDICT_SCALE = 0.9
GUILTY_TABLE, NOT_GUILTY_TABLE = 0x20b45b0, 0x20b4640       # arm9 addresses
GUILTY_PAL, NOT_GUILTY_PAL = 0x1ab10b4, 0x1ab10d4           # data.bin
VERDICT_VRAM_END = 0x5800                                   # person sprites start there
# the DS letters sit just above the DS text box; on the GBA they go where the
# Japanese verdict kanji were, clear of the name tag and text box
VERDICT_CENTRE_Y = 57

def ds_letters(addr, n):
    a = open(ARM9, 'rb').read()
    out = []
    for k in range(n):
        delay, sx, sy, ex, ey, s0, s1, off, size = struct.unpack_from('<I6hII', a, addr - 0x2000000 + 0x18 * k)
        assert (sx, sy, s0, s1) == (ex, ey, 512, 256)       # letters zoom in place, 2x -> 1x
        out.append(dict(delay=delay, x=ex, y=ey, off=off, size=size))
    return out

def letter_image(off, size):
    w, h = (64, 64) if size == 0x800 else (32, 64)
    raw = np.frombuffer(data()[off:off + size], np.uint8)
    nib = np.stack([raw & 15, raw >> 4], 1).reshape(-1, 8, 8)
    img = np.zeros((h, w), np.uint8)
    for k in range(len(nib)):
        img[(k // (w // 8)) * 8:(k // (w // 8)) * 8 + 8, (k % (w // 8)) * 8:(k % (w // 8)) * 8 + 8] = nib[k]
    return img

def verdict(report):
    pal = struct.unpack_from('<16H', data(), GUILTY_PAL)
    colors = [((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in pal]
    guilty = ds_letters(GUILTY_TABLE, 6)
    not_guilty = ds_letters(NOT_GUILTY_TABLE, 9)
    # "Guilty" uses the same six letter images in both verdicts
    assert [l['off'] for l in guilty] == [l['off'] for l in not_guilty[3:]]
    tiles = bytearray()
    sprites = []                                             # per letter image: (src, size, tall, dx, dy)
    for l in not_guilty:
        img = letter_image(l['off'], l['size'])
        h, w = img.shape
        s = scale_indexed(img, colors, VERDICT_SCALE, list(range(1, 7)))
        ys, xs = np.nonzero(s)
        tall = xs.max() - xs.min() + 1 <= 32 - 2
        W, H = (32, 64) if tall else (64, 64)
        out = np.zeros((H, W), np.uint8)
        # keep the letter's centre on the sprite centre (the zoom pivots there)
        oy = int(round(H / 2 - s.shape[0] / 2)); ox = int(round(W / 2 - s.shape[1] / 2))
        for y in range(s.shape[0]):
            for x in range(s.shape[1]):
                if s[y, x] and 0 <= y + oy < H and 0 <= x + ox < W:
                    out[y + oy, x + ox] = s[y, x]
        assert np.count_nonzero(out) == np.count_nonzero(s), 'letter clipped'
        sprites.append((len(tiles), W * H // 2, tall))
        tiles += tiles_of(out, 0, 0, W, H)
    write('verdict_letters.4bpp', bytes(tiles))
    write('verdict_guilty.gbapal', data()[GUILTY_PAL:GUILTY_PAL + 32])
    write('verdict_not_guilty.gbapal', data()[NOT_GUILTY_PAL:NOT_GUILTY_PAL + 32])
    lines = []
    for name, letters, first in (('gVerdictLettersGuilty', guilty, 3), ('gVerdictLettersNotGuilty', not_guilty, 0)):
        vram = VERDICT_VRAM_END
        rows = []
        for k, l in enumerate(letters):
            src, size, tall = sprites[first + k]
            w = 64 if l['size'] == 0x800 else 32               # DS sprite size (height 64)
            W = 32 if tall else 64                             # GBA sprite size (height 64)
            vram -= size
            # DS centre of the double-size box -> GBA centre, scaled about the
            # screen centre -> top-left of the GBA double-size box
            cx = (l['x'] + w - 128) * VERDICT_SCALE + 120
            cy = (l['y'] + 64 - 96) * VERDICT_SCALE + VERDICT_CENTRE_Y
            x = int(round(cx - W)); y = int(round(cy - 64))
            rows.append('    { 0x%04X, 0x%04X, 0x%03X, %d, %2d, %4d, %4d },' % (vram, src, size, tall, l['delay'], x, y))
        assert vram >= 0x2C00, 'verdict letters overflow the sprite memory'
        lines.append('static const struct VerdictLetter %s[] = {\n%s\n};' % (name, '\n'.join(rows)))
        report.append('verdict %-26s %d letters, sprite memory 0x%04X-0x57FF' % (name, len(letters), vram))
    return lines

def main():
    os.makedirs(OUT, exist_ok=True)
    report = []
    banners(report)
    counts = {name: bubble(name, e, report) for name, e in BUBBLES}
    verdict_tables = verdict(report)
    h = ['// generated by tools/en/make_effects.py',
         '#ifndef GUARD_EN_EFFECTS_H', '#define GUARD_EN_EFFECTS_H', '',
         'extern u8 gEnBannerGfx[];']
    for name, _ in BANNER_SUBS:
        h.append('extern u8 gEnBannerSeq_%s[];' % name)
    for name, _ in BUBBLES:
        h += ['extern u8 gEnBubbleGfx_%s[];' % name, 'extern u8 gEnBubbleSeq_%s[];' % name,
              '#define EN_BUBBLE_SPRITES_%s %d' % (name.upper(), counts[name])]
    h += ['', 'extern const u8 gEnVerdictLetterTiles[];', 'extern const u16 gEnVerdictPalGuilty[];',
          'extern const u16 gEnVerdictPalNotGuilty[];', '',
          '// one sprite per letter; vram is an offset into OBJ_VRAM0, (x, y) the',
          '// top-left of the double-size affine box, delay in frames',
          'struct VerdictLetter { u16 vram; u16 src; u16 size; u8 tall; u8 delay; s16 x; s16 y; };',
          '#ifdef EN_VERDICT_TABLES'] + verdict_tables + ['#endif', '', '#endif']
    open(os.path.join(ROOT, 'include', 'en_effects.h'), 'w').write('\n'.join(h) + '\n')
    s = ['@ generated by tools/en/make_effects.py', '\t.section en_data, "a"']
    def inc(label, f):
        s.extend(['', '\t.align 2', '\t.global %s' % label, '%s:' % label, '\t.incbin "graphics/en/effects/%s"' % f])
    inc('gEnBannerGfx', 'banner.gfx')
    for name, _ in BANNER_SUBS:
        inc('gEnBannerSeq_%s' % name, 'banner_%s.seq' % name)
    for name, _ in BUBBLES:
        inc('gEnBubbleGfx_%s' % name, 'bubble_%s.gfx' % name)
        inc('gEnBubbleSeq_%s' % name, 'bubble_%s.seq' % name)
    inc('gEnVerdictLetterTiles', 'verdict_letters.4bpp')
    inc('gEnVerdictPalGuilty', 'verdict_guilty.gbapal')
    inc('gEnVerdictPalNotGuilty', 'verdict_not_guilty.gbapal')
    open(os.path.join(ROOT, 'data', 'en_effects.s'), 'w').write('\n'.join(s) + '\n')
    print('\n'.join(report))

if __name__ == '__main__':
    main()
