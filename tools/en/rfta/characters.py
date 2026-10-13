#!/usr/bin/env python3
"""The fifth episode's people, from the DS: Ema Skye, Lana Skye, Jake
Marshall, Mike Meekins, Damon Gant and Angel Starr, and Edgeworth's two new
looks.

The DS keeps the fifth episode's animations in one data.bin archive
(0x2202220) in the GBA's own format (animfmt.py): a graphics block (palettes,
then RLE tiles behind an offset table) and a frame block (several animations)
for each pair of entries. Its table at ARM9 0x020a8d4c gives every animation
number (the script's 1E arguments) its pair and its offset in the pair's frame
block. A GBA person is one graphics file and one frame file
(gPersonAnimData), each animation naming its graphics block by an offset into
the graphics file (animation.c), so the pairs join up as they are: a person's
graphics blocks one after the other, their animations likewise, each
pointing at its block.

What the GBA has no room for. A person's tiles are copied to OBJ VRAM for
every frame, into the 0x2800 bytes (320 tiles) above OBJ_VRAM0+0x5800; the
rest of OBJ VRAM is the interface's (the evidence plate, the speech bubbles,
the testimony banners, the menus). The DS had more: Gant, Marshall and
Meekins have frames of up to 466 tiles. For each frame:
  * the sprites wholly off the GBA's screen go (beyond the DS screen's
    width, which the courtroom pans can still bring in, or above or below);
  * a frame still over 0x2800 bytes, or over 39 sprites, is drawn again with
    sprites fitted to its pixels (8-pixel cells, each palette apart), the
    rows behind the text box going first from the bottom until it fits.
The redrawn sprites' tiles go into the pair's graphics block as new entries
(identical ones once); the frames that fit keep the DS's sprites. The frame
sound effects the GBA does not have are left out (frame flag 2).

Edgeworth's two looks the GBA lacks (DS 0x82, 0x83) are added after his own
animations in a copy of his files (the plain build keeps the GBA's).

Writes graphics/en/rfta/characters/<name>.{pix,seq}, data/rfta/characters.s,
include/en_rfta_characters.h and tools/en/rfta/characters.json (DS person ->
DS animation -> GBA offset, for translate.py and rooms.py).
usage: characters.py [--sheets DIR]  (contact sheets of every frame, DS and GBA)"""
import os, sys, struct, json, hashlib, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import animfmt
from dsdata import archive, data
import dsbin
ROOT = os.path.join(HERE, '..', '..', '..')
ARCHIVE = 0x2202220
ANIM_TABLE = 0x020a8d4c            # DS animation number -> (u16 pair, u16 offset in the pair's frame block)
BUDGET = 0x2800                    # bytes of tiles a person may use in a frame (OBJ_VRAM0+0x5800 to the end)
MAX_SPRITES = 39                   # the court allocates a person 0x27 sprites (animation.c)
# the GBA's screen around the person's origin, and the DS screen's width
WIN_X0, WIN_X1, WIN_Y0, WIN_Y1 = -128, 128, -80, 80
TEXTBOX_TOP = 32                   # the first row behind the text box (screen row 112)
GBA_SOUNDS = 112                   # the GBA's song table (SE ids below this play the same sound)
SE_MAP = {121: 111, 122: 112}      # port_script.SE_MAP
# DS person: (name, GBA person id, DS animation numbers)
PEOPLE = [
    (0x2C, 'ema', range(0x178, 0x198)),
    (0x2D, 'lana', range(0x198, 0x1AD)),
    (0x2E, 'marshall', range(0x1CD, 0x1E5)),
    (0x2F, 'meekins', range(0x1AD, 0x1BD)),
    (0x31, 'gant', range(0x1E5, 0x1F9)),
    (0x32, 'angel', range(0x1BD, 0x1CD)),
]
# looks of a GBA person the GBA lacks: (DS person, name, GBA files, DS animations)
EXTRA = [(0x09, 'edgeworth', 'graphics/animations/characters/animation06', (0x82, 0x83))]
SIZE_INDEX = {wh: k for k, wh in animfmt.SIZES.items()}          # (w, h) -> size index
CELL_SIZES = sorted({(w // 8, h // 8) for w, h in animfmt.SIZES.values()}, key=lambda s: -s[0] * s[1])

_arc = None
def entry(i):
    global _arc
    if _arc is None:
        _arc = archive(ARCHIVE)
    o, s = _arc[i]
    return data()[o:o + s]

def anim_entry(n):
    return struct.unpack_from('<HH', dsbin.data(), ANIM_TABLE - dsbin.BASE + 4 * n)

# ------------------------------------------------------------------ blocks
def parse_anim(seq, o):
    """-> (frames [(sd, dur, flags, song, act)], end) of the animation at o"""
    h0, nf = struct.unpack_from('<HH', seq, o)
    frames = [struct.unpack_from('<HBBBB', seq, o + 8 + 8 * k) for k in range(nf)]
    end = o + 8 + 8 * nf
    for sd, *_ in frames:
        n = struct.unpack_from('<H', seq, o + sd)[0]
        end = max(end, o + sd + 4 + 4 * n)
    return frames, end

class Graphics:
    """a graphics block (compressed: offset table + RLE streams) that can take new entries"""
    def __init__(self, raw):
        head = struct.unpack_from('<I', raw, 0)[0]
        assert head & 0x80000000, 'uncompressed graphics block'
        self.npal = head & 0x7FFFFFFF
        self.pals = raw[4:4 + 32 * self.npal]
        t0 = 4 + 32 * self.npal
        n = struct.unpack_from('<I', raw, t0)[0] // 4
        offs = list(struct.unpack_from('<%dI' % n, raw, t0)) + [len(raw) - t0]
        self.streams = [raw[t0 + offs[i]:t0 + offs[i + 1]] for i in range(n)]
        self.raw = raw
        self.added = {}

    def tiles(self, tile, size):
        """the 4bpp bytes of entry `tile`, `size` bytes"""
        s = self.streams[tile]; out = bytearray(); p = 0
        while len(out) < size:
            v = struct.unpack_from('<H', s, p)[0]
            if v & 0x8000:
                out += s[p + 2:p + 4] * (v & 0x7FFF); p += 4
            else:
                out += s[p + 2:p + 2 + 2 * v]; p += 2 + 2 * v
        return bytes(out[:size])

    def add(self, tile_bytes):
        key = hashlib.md5(tile_bytes).digest()
        if key not in self.added:
            self.added[key] = len(self.streams)
            self.streams.append(rle(tile_bytes))
            assert len(self.streams) <= 0x200, 'more than 512 graphics entries'
        return self.added[key]

    def build(self):
        if not self.added:
            return self.raw
        n = len(self.streams)
        table, body = [], bytearray()
        for s in self.streams:
            table.append(4 * n + len(body)); body += s
        return struct.pack('<I', 0x80000000 | self.npal) + self.pals + struct.pack('<%dI' % n, *table) + bytes(body)

def rle(b):
    """the GBA's tile RLE (animation.c): 0x8000|n: n times the next word; n: n words"""
    w = list(struct.unpack('<%dH' % (len(b) // 2), b))
    out = []; lit = []; i = 0
    def flush():
        while lit:
            chunk = lit[:0x7FFF]; del lit[:0x7FFF]
            out.append(len(chunk)); out.extend(chunk)
    while i < len(w):
        j = i
        while j < len(w) and w[j] == w[i] and j - i < 0x7FFF:
            j += 1
        if j - i >= 3:
            flush(); out += [0x8000 | (j - i), w[i]]; i = j
        else:
            lit.append(w[i]); i += 1
    flush()
    return struct.pack('<%dH' % len(out), *out)

def sprite_rect(x, y, d):
    w, h = animfmt.SIZES[d >> 12]
    return x, y, w, h

def on_screen(x, y, d):
    x, y, w, h = sprite_rect(x, y, d)
    return x < WIN_X1 and x + w > WIN_X0 and y < WIN_Y1 and y + h > WIN_Y0

# ------------------------------------------------------------------ drawing
def draw(gfx, sprites):
    """the frame inside the window: (palette index, palette number) per pixel;
    the first sprite on top, as the GBA draws OAM"""
    H, W = WIN_Y1 - WIN_Y0, WIN_X1 - WIN_X0
    idx = np.zeros((H, W), np.uint8); pal = np.zeros((H, W), np.uint8)
    for x, y, d in reversed(sprites):
        w, h = animfmt.SIZES[d >> 12]
        t = np.frombuffer(gfx.tiles(d & 0x1FF, w * h // 2), np.uint8)
        nib = np.stack([t & 15, t >> 4], 1).reshape(-1).reshape(h // 8, w // 8, 8, 8)
        blk = nib.transpose(0, 2, 1, 3).reshape(h, w)
        ys, xs = np.nonzero(blk)
        py, px = ys + y - WIN_Y0, xs + x - WIN_X0
        ok = (py >= 0) & (py < H) & (px >= 0) & (px < W)
        idx[py[ok], px[ok]] = blk[ys[ok], xs[ok]]
        pal[py[ok], px[ok]] = (d >> 11) & 1
    return idx, pal

def cover(filled, waste):
    """GBA sprite rectangles (cells) covering the filled cells: greedily the
    one with the most new cells less `waste` times its empty ones"""
    H, W = filled.shape
    todo = filled.copy(); rects = []
    while todo.any():
        # cells still to cover in every rectangle at once (a summed-area table;
        # a rectangle stays inside the frame)
        S = np.zeros((H + 1, W + 1), np.int32)
        S[1:, 1:] = todo.astype(np.int32).cumsum(0).cumsum(1)
        best = None
        for tw, th in CELL_SIZES:
            if th > H or tw > W:
                continue
            new = S[th:, tw:] - S[:H - th + 1, tw:] - S[th:, :W - tw + 1] + S[:H - th + 1, :W - tw + 1]
            score = np.where(new > 0, new - waste * (tw * th - new), -1e9)
            k = int(np.argmax(score))
            ty, tx = divmod(k, score.shape[1])
            if best is None or score[ty, tx] > best[0]:
                best = (score[ty, tx], tx, ty, tw, th)
        _, tx, ty, tw, th = best
        rects.append((tx, ty, tw, th))
        todo[ty:ty + th, tx:tx + tw] = False
    return rects

WASTES = (4.0, 2.5, 1.6, 1.0, 0.6, 0.35)

def fit(cells):
    """the tightest cover of the cells (per palette) within the sprite count,
    None if none fits the budget"""
    best = None
    for waste in WASTES:
        out = []
        for pn, c in cells.items():
            if c.any():
                out += [(pn,) + r for r in cover(c, waste)]
        size = sum(tw * th * 32 for _, _, _, tw, th in out)
        if size <= BUDGET and len(out) <= MAX_SPRITES and (best is None or size < best[0]):
            best = (size, out)
    return best and best[1]

def redraw(gfx, sprites):
    """sprites fitted to the frame's pixels within the budget. When even that
    does not fit, 8-pixel cells go from the bottom (behind the text box), the
    outermost of the lowest row first -> (sprites, cells left out, the highest
    row of them)"""
    idx, pal = draw(gfx, sprites)
    H, W = idx.shape
    cells = {}
    for pn in (0, 1):
        m = (idx > 0) & (pal == pn)
        cells[pn] = m.reshape(H // 8, 8, W // 8, 8).any(axis=(1, 3))
    order = sorted({(r, c) for pn in cells for r, c in zip(*np.nonzero(cells[pn]))},
                   key=lambda rc: (-rc[0], -abs(rc[1] * 8 + 4 - W // 2)))
    def without(k):
        cut = {pn: c.copy() for pn, c in cells.items()}
        for r, c in order[:k]:
            for pn in cut:
                cut[pn][r, c] = False
        return cut
    out = fit(cells); k = 0
    if out is None:
        lo, hi = 0, len(order)          # (the fewest cells to leave out: a bisection)
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if fit(without(mid)) is None:
                lo = mid
            else:
                hi = mid
        k = hi; out = fit(without(k))
        idx = idx.copy()
        for r, c in order[:k]:
            idx[r * 8:r * 8 + 8, c * 8:c * 8 + 8] = 0
    res = []
    for pn, tx, ty, tw, th in out:
        w, h = tw * 8, th * 8
        y0, x0 = ty * 8, tx * 8
        blk = np.where(pal[y0:y0 + h, x0:x0 + w] == pn, idx[y0:y0 + h, x0:x0 + w], 0)
        tiles = blk.reshape(th, 8, tw, 8).transpose(0, 2, 1, 3).reshape(-1, 64)
        b = bytes((tiles[:, 0::2] | (tiles[:, 1::2] << 4)).astype(np.uint8).reshape(-1))
        t = gfx.add(b)
        res.append((x0 + WIN_X0, y0 + WIN_Y0, t | (pn << 11) | (SIZE_INDEX[(w, h)] << 12)))
    top = min((r for r, c in order[:k]), default=None)
    return res, k, (top * 8 + WIN_Y0 if top is not None else None)

# ------------------------------------------------------------------ a person
def convert(name, anims, base=None, report=None):
    """anims: DS animation numbers. base: the GBA files (pix, seq) to add to.
    -> (pix, seq, {DS animation: GBA offset}, sprites used at most)"""
    pix = bytearray(base[0]) if base else bytearray()
    seq = bytearray(base[1]) if base else bytearray()
    pairs = collections.OrderedDict()
    for n in anims:
        p, off = anim_entry(n)
        pairs.setdefault(p, []).append((n, off))
    offsets = {}; most = 0; stats = collections.Counter()
    for p, members in pairs.items():
        gfx = Graphics(entry(2 * p)); ds_seq = entry(2 * p + 1)
        blocks = []; redrawn = {}
        for n, off in members:
            frames, end = parse_anim(ds_seq, off)
            new_frames = []
            for sd, dur, fl, song, act in frames:
                sprites = animfmt.sprites(ds_seq[off:end], sd)
                kept = [s for s in sprites if on_screen(*s)]
                size = sum(animfmt.SIZES[d >> 12][0] * animfmt.SIZES[d >> 12][1] // 2 for _, _, d in kept)
                if size <= BUDGET and len(kept) <= MAX_SPRITES:
                    out = kept; stats['frames as the DS has them'] += 1
                else:
                    key = tuple(kept)
                    if key not in redrawn:
                        redrawn[key] = redraw(gfx, kept)
                    out, lost, top = redrawn[key]
                    stats['frames redrawn'] += 1
                    if lost:
                        stats['frames short of cells at the bottom'] += 1
                        if top < TEXTBOX_TOP:
                            stats['... of them above the text box'] += 1
                        if report is not None:
                            report.append('%s %x frame %d: %d cells left out, from row %d' % (name, n, len(new_frames), lost, top))
                if fl & 2:
                    song = SE_MAP.get(song, song)
                    if song >= GBA_SOUNDS and song not in SE_MAP.values():
                        fl &= ~2; song = 0; stats['frame sounds left out'] += 1
                most = max(most, len(out))
                new_frames.append((out, dur, fl, song, act))
            blocks.append((n, new_frames))
        # the pair's graphics block (with the redrawn sprites' entries)
        while len(pix) % 4:
            pix.append(0)
        gfx_off = len(pix)
        pix += gfx.build()
        for n, new_frames in blocks:
            while len(seq) % 4:
                seq.append(0)
            o = len(seq); offsets[n] = o
            nf = len(new_frames)
            head = 8 + 8 * nf
            lists = collections.OrderedDict()
            for out, *_ in new_frames:
                key = tuple(out)
                if key not in lists:
                    lists[key] = None
            body = bytearray(); at = {}
            for key in lists:
                at[key] = head + len(body)
                body += struct.pack('<HH', len(key), 0) + b''.join(struct.pack('<bbH', x, y, d) for x, y, d in key)
            b = bytearray(struct.pack('<HHI', 0, nf, gfx_off))
            for out, dur, fl, song, act in new_frames:
                b += struct.pack('<HBBBBH', at[tuple(out)], dur, fl, song, act, 0)
            seq += b + body
    return bytes(pix), bytes(seq), offsets, most, stats

def main():
    out_dir = os.path.join(ROOT, 'graphics', 'en', 'rfta', 'characters')
    os.makedirs(out_dir, exist_ok=True)
    mapping = {}; asm = ['@ The fifth episode\'s people and Edgeworth\'s new looks (tools/en/rfta/characters.py)',
                         '\t.section rfta_data, "a"', '']
    hdr = ['// generated by tools/en/rfta/characters.py: the fifth episode\'s people',
           '#ifndef GUARD_EN_RFTA_CHARACTERS_H', '#define GUARD_EN_RFTA_CHARACTERS_H', '']
    init = []; report = []
    jobs = [(p, name, None, list(rng)) for p, name, rng in PEOPLE] + \
           [(p, name, files, list(anims)) for p, name, files, anims in EXTRA]
    for person, name, files, anims in jobs:
        base = None
        if files:
            base = (open(os.path.join(ROOT, files + '.pix'), 'rb').read(), open(os.path.join(ROOT, files + '.seq'), 'rb').read())
        pix, seq, offsets, most, stats = convert(name, anims, base, report)
        open(os.path.join(out_dir, name + '.pix'), 'wb').write(pix)
        open(os.path.join(out_dir, name + '.seq'), 'wb').write(seq)
        mapping['%x' % person] = {'%x' % n: o for n, o in sorted(offsets.items())}
        sym = name.capitalize()
        asm += ['\t.align 2', '\t.global gRftaPix%s' % sym, 'gRftaPix%s:' % sym,
                '\t.incbin "graphics/en/rfta/characters/%s.pix"' % name,
                '\t.align 2', '\t.global gRftaSeq%s' % sym, 'gRftaSeq%s:' % sym,
                '\t.incbin "graphics/en/rfta/characters/%s.seq"' % name, '']
        hdr += ['extern u8 gRftaPix%s[];' % sym, 'extern u8 gRftaSeq%s[];' % sym]
        if base:
            sprites = max(most, 38)
            hdr.append('#define RFTA_SPRITES_%s %d' % (name.upper(), sprites))
        else:
            init.append('    [0x%X] = { .gfxData = gRftaPix%s, .frameData = gRftaSeq%s, .spriteCount = %d, .unkA = 0 }, \\'
                        % (person, sym, sym, most))
        print('%-10s %3d animations: pix %6d bytes, seq %5d bytes, at most %d sprites; %s'
              % (name, len(offsets), len(pix) - (len(base[0]) if base else 0), len(seq) - (len(base[1]) if base else 0), most, dict(stats)))
    hdr += ['', '// gPersonAnimData entries of the fifth episode\'s people (DS person numbers)',
            '#define RFTA_PERSON_ANIM_DATA \\'] + init + ['', '#endif']
    open(os.path.join(ROOT, 'data', 'rfta', 'characters.s'), 'w').write('\n'.join(asm) + '\n')
    open(os.path.join(ROOT, 'include', 'en_rfta_characters.h'), 'w').write('\n'.join(hdr) + '\n')
    json.dump(mapping, open(os.path.join(HERE, 'characters.json'), 'w'), indent=1, sort_keys=True)
    open(os.path.join(out_dir, 'report.txt'), 'w').write('\n'.join(report) + '\n')
    print('%d frames short of cells at the bottom (report.txt)' % len(report))

if __name__ == '__main__':
    main()
