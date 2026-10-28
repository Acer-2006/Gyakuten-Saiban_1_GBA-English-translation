#!/usr/bin/env python3
"""The fifth episode's movies, from the DS, for the RFTA build's movie player
(src/en_movie.c).

The DS keeps four frame sequences in data.bin (its table at 0x020c096c,
16 bytes an entry; script command 75 plays them): archives whose entries are
256-wide 4bpp frames, a 16-colour palette first, RLE (0x30) or LZ (0x10)
compressed. It shows them at 30 frames a second.

  0  the Blue Badger's dance  450 frames 256x160
  1  the opening (silhouettes) 329 frames 256x192
  2  the security footage    1420 frames 256x192, a camera panning to and fro
  3  the ending montage       270 frames 256x192

Every frame is kept. Each movie is cut as the backgrounds are (240x160 at
x 8, y 16; the dance's 256x160 at x 8) and shown on BG3 in 16 colours, its
600 tiles in as many slots (VRAM 0x06004000, row by row). A frame is stored
as the change from the one before: a bitmap of the slots that change (80 bytes),
then their tiles, either as they are or XORed with what the slot held (the
smaller; XOR runs both ways, so a movie of XOR changes can play backwards,
as the security footage does in court). Each change is packed with LZ77
(movlz.c, optimally parsed), in bytes (the BIOS's format) or in whole
words: the player unpacks bytes into EWRAM and words straight into VRAM,
about three times as fast (src/en_movie_lz.s). Words pack about 15% larger,
so they are used where a frame changes so much that bytes would not unpack
in time (DECODE_BUDGET: most of the ending).
Keyframes (every KEY_EVERY frames, and the frames the scripts jump to) hold
whole pictures, for jumps, loops and loading a save.

The security footage pans across a scene wider than the screen: it is
stored as a world picture that 32x20 slots hold 32 columns of (BG3's
horizontal scroll follows the camera; a column coming into view is written
over the one that went out of it), a tile changing only where the blurred
picture (3x3) differs from what the slot shows by more than PAN_THRESHOLD
on average, or a few of its pixels by a lot (PAN_EDGE: thin edges; bits of
an edge left behind go after PAN_STALE frames), in 16 fixed greys (the footage's grain alone would change every tile every
frame; it is left still where the picture is).
Its keyframes are the frames the scripts jump to. Its time stamp, which
stays put on the screen while the picture moves under it, is taken out of
the picture and drawn by the player over it (each second's, from the DS's
frames).

Blob layout (graphics/en/rfta/movies/NAME.bin), all offsets from its start:
  0x00 u16 frames, u16 flags (1: pan, 2: overlay), u16 keyframes, u16 palettes
  0x08 u32 the change table: u32[frames]: offset | 1 (XOR) | 2 (words); 0: none
  0x0C u32 the keyframes: {u16 frame, u16 2 (words) or 0, u32 offset}[keyframes]
  0x10 u32 u16[frames]: each frame's palette
  0x14 u32 the palettes: u16[16][palettes]
  0x18 u32 s16[frames]: the world x of the screen's left edge (pan), or 0
  0x1C u32 the overlay (pan), or 0: see overlay()

usage: movies.py                       writes the four blobs and data/rfta/movies.s
       movies.py ARCHIVE FRAME out.png  one DS frame"""
import os, sys, struct, subprocess, tempfile, shutil
import numpy as np
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
from dsdata import data, lz10, tiles_to_array          # noqa: E402
ROOT = os.path.join(HERE, '..', '..', '..')
OUT = os.path.join(ROOT, 'graphics', 'en', 'rfta', 'movies')

MOVIES = {0x0: 'Blue Badger dance, 450 frames 256x160, RLE',
          0x1bd418: 'opening (silhouettes, skyline), 329 frames 256x192, RLE',
          0x28d93c: 'security camera footage, 1420 frames 256x192, LZ',
          0x18187b8: 'ending montage, 270 frames 256x192, LZ'}
# the DS's sequence numbers, in order
SEQS = [dict(name='badger', base=0x0, y0=0, keys=()),
        dict(name='opening', base=0x1bd418, y0=16, keys=()),
        # the frames the court scripts jump to (75 2 n): files 25-27
        dict(name='security', base=0x28d93c, y0=16, pan=True,
             keys=(0xBE, 0x1D9, 0x30C, 0x35C, 0x35E, 0x4A1, 0x51E, 0x569)),
        dict(name='ending', base=0x18187b8, y0=16, keys=())]
KEY_EVERY = 128
SLOTS = 30 * 20                 # a movie's slots, row by row (VRAM 0x06004000)
RING = 32 * 20                  # the panning movie's: 32 columns of the scene
# the panning movie's tiles in VRAM: the ring, a blank tile, 64 for the time
# stamp drawn over two rows; then room for a change packed in words
SCRATCH_PAN = 0x0600E000 - (0x06004000 + (RING + 1 + 64) * 32)
# unpacking, cycles an unpacked byte (src/en_movie_lz.s, measured): a change must
# unpack within DECODE_BUDGET (the two frames a movie frame lasts leave about
# that beside the game and the sound); bytes pack smaller, words unpack faster
CYCLES_BYTE, CYCLES_WORD = 14, 4.5
DECODE_BUDGET = 110000
PAN_THRESHOLD = 4 / 3           # the security footage: mean blurred luminance (0-31) change that rewrites a tile
PAN_BLUR = 3
PAN_MATCH_BLUR = 5              # (finding the camera's moves)
PAN_EDGE, PAN_EDGE_PIXELS = 6, 5  # ... or that many pixels by that much
PAN_STALE, PAN_STALE_EDGE = 8, 3.5  # ... or, this many frames on, a line of three by that much


def line_diff(d):
    """the largest mean change along a line of three pixels through each pixel"""
    from scipy.ndimage import convolve
    ks = (np.ones((1, 3)) / 3, np.ones((3, 1)) / 3, np.eye(3) / 3, np.fliplr(np.eye(3)) / 3)
    return np.max([np.abs(convolve(d, k, mode='nearest')) for k in ks], 0)


def rle(src, i=0):
    size = src[i + 1] | src[i + 2] << 8 | src[i + 3] << 16; i += 4; out = bytearray()
    while len(out) < size:
        f = src[i]; i += 1
        if f & 0x80: n = (f & 0x7f) + 3; out += bytes([src[i]]) * n; i += 1
        else: n = f + 1; out += src[i:i + n]; i += n
    return bytes(out)


def entries(base):
    d = data(); n = struct.unpack_from('<I', d, base)[0]
    return [struct.unpack_from('<II', d, base + 4 + 8 * k) for k in range(n)]


def frame(base, k):
    d = data(); o, s = entries(base)[k]; a = base + o
    raw = lz10(d, a) if d[a] == 0x10 else rle(d[a:a + s])
    pal = struct.unpack_from('<16H', raw, 0); px = raw[32:]
    ht = len(px) // (32 * 32)
    cols = [((v & 31) * 8, ((v >> 5) & 31) * 8, ((v >> 10) & 31) * 8) for v in pal]
    from PIL import Image
    arr = tiles_to_array(px, 32, ht)
    im = Image.new('RGB', (256, ht * 8))
    im.putdata([cols[v] for row in arr for v in row])
    return im


def frames(base):
    """all of a sequence's frames: pixels (n, h, 256) and palettes (n, 16)"""
    d = data(); pix, pals = [], []
    for o, s in entries(base):
        a = base + o
        raw = lz10(d, a) if d[a] == 0x10 else rle(d[a:a + s])
        pals.append(np.frombuffer(raw[:32], '<u2'))
        b = np.frombuffer(raw[32:], np.uint8)
        ht = len(b) // 1024
        t = b.reshape(ht, 32, 8, 4)
        p = np.stack([t & 15, t >> 4], -1).reshape(ht, 32, 8, 8).transpose(0, 2, 1, 3).reshape(ht * 8, 256)
        pix.append(p)
    return np.array(pix), np.array(pals)


def tiles(a):
    """(8r, 8c) pixel indices -> (r * c, 32) GBA 4bpp tiles, row-major"""
    r, c = a.shape[0] // 8, a.shape[1] // 8
    t = a.reshape(r, 8, c, 8).transpose(0, 2, 1, 3).reshape(r * c, 8, 8)
    return (t[:, :, 0::2] | (t[:, :, 1::2] << 4)).reshape(r * c, 32).astype(np.uint8)


def bitmap(m):
    """80 bytes, slot i at bit i & 7 of byte i >> 3"""
    return np.packbits(np.concatenate([m, np.zeros(RING - len(m), bool)]), bitorder='little').tobytes()


# ---------------------------------------------------------------- packing
class Packer:
    def __init__(self):
        self.dir = tempfile.mkdtemp()
        self.exe = os.path.join(self.dir, 'movlz')
        subprocess.run(['cc', '-O2', '-o', self.exe, os.path.join(HERE, 'movlz.c')], check=True)

    def pack(self, b, unit):
        with tempfile.TemporaryDirectory(dir=self.dir) as d:
            open(d + '/i', 'wb').write(b)
            subprocess.run([self.exe, str(unit), d + '/i', d + '/o'], check=True)
            return open(d + '/o', 'rb').read()

    def close(self):
        shutil.rmtree(self.dir)


def change(old, new, xor_only):
    """the change from slots old to new: (bitmap + tiles as they are, bitmap + XOR) or None"""
    m = np.any(old != new, axis=1)
    if not m.any():
        return None
    bm = bitmap(m)
    x = bm + (old[m] ^ new[m]).tobytes()
    return (None if xor_only else bm + new[m].tobytes()), x


def keyframe(slots):
    m = np.any(slots != 0, axis=1)
    return bitmap(m) + slots[m].tobytes()


# ---------------------------------------------------------------- the plain movies
def plain(seq, pix, pals):
    n = len(pix); y0 = seq['y0']
    crop = pix[:, y0:y0 + 160, 8:248]
    keys = sorted(set(range(0, n, KEY_EVERY)) | set(seq['keys']))
    shown = np.zeros((SLOTS, 32), np.uint8)
    changes, keyrecs = [None] * n, {}
    for k in range(n):
        new = tiles(crop[k])
        if k in keys:
            keyrecs[k] = keyframe(new)
        if k:
            changes[k] = change(shown, new, False)
        shown = new
    # palettes (colour 0 is the backdrop's)
    uniq, idx = {}, []
    for p in pals:
        t = tuple(int(v) & 0x7FFF for v in p)
        idx.append(uniq.setdefault(t, len(uniq)))
    return dict(changes=changes, keys=keyrecs, palidx=idx, pals=list(uniq), scroll=None, overlay=None)


# ---------------------------------------------------------------- the security footage
def luminance(pals, pix):
    p = pals.astype(np.int32)
    lum = ((p & 31) * 0.299 + ((p >> 5) & 31) * 0.587 + ((p >> 10) & 31) * 0.114).astype(np.float32)
    return np.take_along_axis(lum[:, None, :], pix.reshape(len(pix), 1, -1).astype(np.intp), 2).reshape(pix.shape)


def pan_offsets(L):
    """the camera's x in each frame (integer pixels): the shift that best
    matches the blurred frame to the one before (rows 16-176)"""
    from scipy.ndimage import uniform_filter
    B = np.array([uniform_filter(f, PAN_MATCH_BLUR) for f in L[:, 16:176]])
    off = [0]
    for k in range(1, len(B)):
        a, b = B[k - 1], B[k]
        best = min(range(-6, 7), key=lambda dx: np.abs(np.roll(a, dx, 1)[:, 16:-16] - b[:, 16:-16]).mean())
        off.append(off[-1] - best)
    return np.array(off)


def greys(L):
    """16 grey levels (0-31) for the footage: k-means on its pixels"""
    v = np.round(L).astype(int).ravel()
    h = np.bincount(v, minlength=32).astype(float)
    lv = np.linspace(v.min(), v.max(), 16)
    x = np.arange(32)
    for _ in range(50):
        a = np.argmin(np.abs(x[:, None] - lv[None, :]), 1)
        for j in range(16):
            w = h[a == j]
            if w.sum():
                lv[j] = (x[a == j] * w).sum() / w.sum()
    return np.unique(np.round(lv).astype(int))


# the time stamp: DS pixels y 153-165, x 0-159, white; it reads 17:14:26 at frame 0 and
# goes on a second every 30 frames from frame 10. Its font is proportional (a
# digit's place depends on the ones before it), so each second's stamp is kept whole.
STAMP_Y, STAMP_H, STAMP_W = 153, 13, 160
STAMP_PHASE = 20


def stamp_second(k):
    return (k + STAMP_PHASE) // 30


def stamp(L):
    """each second's stamp (STAMP_H x STAMP_W bool): the pixels white in nearly
    every frame of the second (the picture moves under it)"""
    n = len(L)
    W = L[:, STAMP_Y:STAMP_Y + STAMP_H, :STAMP_W] >= 29.5
    sec = np.array([stamp_second(k) for k in range(n)])
    return np.array([W[sec == s].mean(0) > 0.9 for s in range(sec.max() + 1)])


def stamp_mask(k, stamps):
    """the stamp's pixels in DS frame k (192 x 256 bool)"""
    m = np.zeros((192, 256), bool)
    m[STAMP_Y:STAMP_Y + STAMP_H, :STAMP_W] = stamps[stamp_second(k)]
    return m


def pan(seq, pix, pals):
    from scipy.ndimage import uniform_filter, binary_dilation
    n = len(pix); y0 = seq['y0']
    L = luminance(pals, pix)
    off = pan_offsets(L)
    stamps = stamp(L)
    lv = greys(L)
    lut = np.argmin(np.abs(np.arange(32)[:, None] - lv[None, :]), 1).astype(np.uint8)
    Q = lut[np.clip(np.round(L), 0, 31).astype(np.intp)]                           # (n, 192, 256) indices
    x0 = int(off.min())
    # the scene as the frames show it away from the stamp (the mean of each world pixel)
    W = int(off.max()) - x0 + 256
    acc = np.zeros((192, W)); cnt = np.zeros((192, W))
    for k in range(n):
        ok = ~binary_dilation(stamp_mask(k, stamps), iterations=2)
        xs = int(off[k]) - x0
        acc[:, xs:xs + 256] += np.where(ok, L[k], 0); cnt[:, xs:xs + 256] += ok
    pano = (acc / np.maximum(cnt, 1)).astype(np.float32)
    panoQ = lut[np.clip(np.round(pano), 0, 31).astype(np.intp)]
    panoB = uniform_filter(pano, PAN_BLUR)
    keys = sorted({0} | set(seq['keys']))                  # (XOR runs both ways from them)
    ringcol = [None] * 32
    ringQ = np.zeros((RING, 8, 8), np.uint8)
    ringB = np.zeros((RING, 8, 8), np.float32)
    ringL = np.zeros((RING, 8, 8), np.float32)
    age = np.zeros(RING, int)
    shown = np.zeros((RING, 32), np.uint8)
    changes, keyrecs, scroll = [None] * n, {}, []
    counts = []
    for k in range(n):
        mask = binary_dilation(stamp_mask(k, stamps), iterations=1)
        near = binary_dilation(mask, iterations=PAN_BLUR // 2 + 1)
        B = uniform_filter(L[k], PAN_BLUR)
        age += 1
        sx = int(off[k]) - x0 + 8                          # world x of the screen's left edge
        scroll.append(sx)
        upd = 0
        for tx in range(sx // 8, (sx + 239) // 8 + 1):
            c = tx & 31
            fx = tx * 8 - (int(off[k]) - x0)               # the tile's x in the DS frame
            assert 0 <= fx <= 248
            fresh = ringcol[c] != tx
            for ty in range(20):
                s = ty * 32 + c
                fy = y0 + ty * 8
                q = Q[k, fy:fy + 8, fx:fx + 8]; b = B[fy:fy + 8, fx:fx + 8]; l = L[k, fy:fy + 8, fx:fx + 8]
                mk = mask[fy:fy + 8, fx:fx + 8]; nr = near[fy:fy + 8, fx:fx + 8]
                if not fresh:
                    # rewritten where the blurred picture moved on the whole, or a few
                    # pixels moved a lot (thin edges the blur hides)
                    d = np.abs(b - ringB[s])[~nr]
                    if not d.size:
                        continue
                    if d.mean() <= PAN_THRESHOLD and (np.abs(l - ringL[s])[~mk] >= PAN_EDGE).sum() < PAN_EDGE_PIXELS:
                        # (and bits of an edge that moved on, left behind: after a while)
                        if age[s] < PAN_STALE or not (line_diff(l - ringL[s])[~mk] >= PAN_STALE_EDGE).any():
                            continue
                    q = np.where(mk, ringQ[s], q); b = np.where(nr, ringB[s], b); l = np.where(mk, ringL[s], l)
                else:                                      # (under the stamp: the scene as other frames show it)
                    q = np.where(mk, panoQ[fy:fy + 8, tx * 8:tx * 8 + 8], q)
                    b = np.where(nr, panoB[fy:fy + 8, tx * 8:tx * 8 + 8], b)
                    l = np.where(mk, pano[fy:fy + 8, tx * 8:tx * 8 + 8], l)
                ringQ[s] = q; ringB[s] = b; ringL[s] = l; age[s] = 0; upd += 1
            ringcol[c] = tx
        counts.append(upd)
        new = tiles(ringQ.reshape(20, 32, 8, 8).transpose(0, 2, 1, 3).reshape(160, 256))
        if k in keys:
            keyrecs[k] = keyframe(new)
        if k:
            changes[k] = change(shown, new, True)
        shown = new
    pal = tuple(int(g) | int(g) << 5 | int(g) << 10 for g in lv) + (0,) * (16 - len(lv))
    white = int(np.argmax(lv))
    print('  pan: world %d px, %d greys, tiles rewritten a frame: mean %.0f, max %d' % (
        int(off.max()) - x0 + 256, len(lv), np.mean(counts[1:]), max(counts[1:])))
    return dict(changes=changes, keys=keyrecs, palidx=[0] * n, pals=[pal], scroll=scroll,
                overlay=overlay(stamps, white))


def overlay(stamps, colour):
    """the time stamp for the player: u8 x, y (on the screen), u8 height, u8 colour
    index, u16 seconds, u16 phase (the second of frame k is (k + phase) / 30), then
    each second's rows (24 bytes a row, bit x & 7 of byte x >> 3). The DS shows it
    5 px from its screen's left edge: here 5 px from the GBA's (not cut off
    with the picture's margin)."""
    out = struct.pack('<4BHH', 0, STAMP_Y - 16, STAMP_H, colour, len(stamps), STAMP_PHASE)
    for st in stamps:
        for row in st:
            out += np.packbits(row, bitorder='little').tobytes() + bytes(24 - STAMP_W // 8)
    return out


# ---------------------------------------------------------------- the blob
def unpack_cycles(raw, unit):
    return raw * (CYCLES_BYTE if unit == 1 else CYCLES_WORD)


def blob(m, packer):
    """the change table's entries: offset | 1 (XOR) | 2 (packed in words); the
    smallest packing whose unpacking fits DECODE_BUDGET"""
    n = len(m['changes'])
    jobs = []
    for k, ch in enumerate(m['changes']):
        if ch:
            for kind, rec in (('rep', ch[0]), ('xor', ch[1])):
                if rec is not None:
                    jobs += [(k, kind, rec, u) for u in (1, 4) if u == 4 or unpack_cycles(len(rec), u) <= DECODE_BUDGET]
    for k, r in m['keys'].items():          # (a keyframe is unpacked once, on a jump: bytes are fine)
        jobs += [(('key', k), 'rep', r, u) for u in (1, 4)]
    if m['scroll'] is not None:     # (words unpack into VRAM after the slots: room for less)
        every = set(j[0] for j in jobs)
        jobs = [j for j in jobs if j[3] == 1 or len(j[2]) <= SCRATCH_PAN]
        assert every == set(j[0] for j in jobs), 'a change too large to unpack'
    with ThreadPoolExecutor(os.cpu_count() or 4) as ex:
        packed = list(ex.map(lambda j: packer.pack(j[2], j[3]), jobs))
    best = {}
    for (k, kind, _, u), p in zip(jobs, packed):
        if k not in best or len(p) < len(best[k][1]):
            best[k] = ((1 if kind == 'xor' else 0) | (2 if u == 4 else 0), p)
    pals = m['pals']
    head = 0x20
    t_changes = head
    t_keys = t_changes + 4 * n
    t_palidx = t_keys + 8 * len(m['keys'])
    t_pals = t_palidx + 2 * n + (2 * n) % 4
    t_scroll = t_pals + 32 * len(pals)
    t_overlay = t_scroll + (2 * n + (2 * n) % 4 if m['scroll'] is not None else 0)
    t_data = t_overlay + (len(m['overlay']) + 3) // 4 * 4 if m['overlay'] else t_overlay
    body = bytearray(); offs = [0] * n; koffs = []
    for k in range(n):
        if k in best:
            xor, p = best[k]
            offs[k] = (t_data + len(body)) | xor
            body += p
    for k in sorted(m['keys']):
        koffs.append((k, best[('key', k)][0], t_data + len(body)))
        body += best[('key', k)][1]
    flags = (1 if m['scroll'] is not None else 0) | (2 if m['overlay'] else 0)
    out = bytearray(struct.pack('<4H6I', n, flags, len(koffs), len(pals), t_changes, t_keys, t_palidx, t_pals,
                                t_scroll if m['scroll'] is not None else 0, t_overlay if m['overlay'] else 0))
    out += struct.pack('<%dI' % n, *offs)
    for k, f, o in koffs:
        out += struct.pack('<HHI', k, f, o)
    out += struct.pack('<%dH' % n, *m['palidx']) + b'\0' * ((2 * n) % 4)
    for p in pals:
        out += struct.pack('<16H', *p)
    if m['scroll'] is not None:
        out += struct.pack('<%dh' % n, *m['scroll']) + b'\0' * ((2 * n) % 4)
    if m['overlay']:
        out += m['overlay'] + b'\0' * ((4 - len(m['overlay']) % 4) % 4)
    assert len(out) == t_data, (len(out), t_data)
    out += body
    nx = sum(1 for k, v in best.items() if isinstance(k, int) and v[0] & 1)
    nw = sum(1 for k, v in best.items() if isinstance(k, int) and v[0] & 2)
    return bytes(out), dict(changes=sum(1 for o in offs if o), xor=nx, words=nw, keys=len(koffs),
                            key_bytes=sum(len(best[('key', k)][1]) for k in m['keys']))


# ---------------------------------------------------------------- the tape in court
# Day 3: the security footage is shown to point out a moment (four questions,
# the DS's 0x020ced54); the DS's 0x0206a294 checks the frame and the touch:
# its table at 0x020c09bc holds four spots, each a run of frames with a mask
# a frame (data.bin, RLE, 256x192 1bpp) and the section each question goes
# to when the 16x16 box round the touch meets the mask; then the sections
# for no spot (0x020c0a18). The masks are small blobs: here their rectangles.
TAPE_SPOTS, TAPE_DEFAULTS = 0x020c09bc, 0x020c0a18


def tape_spots():
    import dsbin
    d = data(); ar = dsbin.data()
    asm = ['\t.align 2', '\t.global gRftaTapeSpots',
           'gRftaTapeSpots: @ the sections with no spot pointed out, by question; the four spots (en_movie.c)',
           '\t.2byte ' + ', '.join('0x%X' % v for v in struct.unpack_from('<4H', ar, TAPE_DEFAULTS - dsbin.BASE))]
    boxes = []
    for i in range(4):
        f0, f1, ptr = struct.unpack_from('<HHI', ar, TAPE_SPOTS - dsbin.BASE + 20 * i)
        secs = struct.unpack_from('<4H', ar, TAPE_SPOTS - dsbin.BASE + 20 * i + 12)
        n = struct.unpack_from('<I', d, ptr)[0]
        assert n == f1 - f0 + 1
        bx = []
        for k in range(n):
            o, sz = struct.unpack_from('<II', d, ptr + 4 + 8 * k)
            a = np.unpackbits(np.frombuffer(rle(d[ptr + o:ptr + o + sz + 4]), np.uint8), bitorder='little').reshape(192, 256)
            ys, xs = np.where(a)
            bx.append((xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else (255, 255, 0, 0))
        asm += ['\t.2byte %d, %d, %s' % (f0, f1, ', '.join('0x%X' % v for v in secs)), '\t.word gRftaTapeBoxes%d' % i]
        boxes += ['gRftaTapeBoxes%d: @ frames %d-%d: x0, y0, x1, y1 (the DS\'s pixels; 255: none)' % (i, f0, f1)]
        boxes += ['\t.byte ' + ', '.join('%d, %d, %d, %d' % b for b in bx[j:j + 8]) for j in range(0, n, 8)]
    return asm + boxes + ['']


def main():
    os.makedirs(OUT, exist_ok=True)
    packer = Packer()
    asm = ['@ generated by tools/en/rfta/movies.py: the fifth episode\'s movies (src/en_movie.c)',
           '\t.section rfta_data, "a"', '']
    total = 0
    try:
        for i, seq in enumerate(SEQS):
            cache = os.environ.get('MOVIES_NPZ')      # (a folder of NAME.npz: pix, pals, to skip unpacking)
            if cache and os.path.exists(os.path.join(cache, seq['name'] + '.npz')):
                z = np.load(os.path.join(cache, seq['name'] + '.npz')); pix, pals = z['pix'], z['pals']
            else:
                pix, pals = frames(seq['base'])
            print('%s: %d frames %dx%d' % (seq['name'], len(pix), pix.shape[2], pix.shape[1]))
            m = pan(seq, pix, pals) if seq.get('pan') else plain(seq, pix, pals)
            b, st = blob(m, packer)
            open(os.path.join(OUT, seq['name'] + '.bin'), 'wb').write(b)
            total += len(b)
            print('  %d bytes (%.2f MB): %d changes (%d XOR, %d packed in words), %d keyframes (%d bytes)' % (
                len(b), len(b) / 2**20, st['changes'], st['xor'], st['words'], st['keys'], st['key_bytes']))
            asm += ['\t.align 2', '\t.global gRftaMovie_%s' % seq['name'], 'gRftaMovie_%s:' % seq['name'],
                    '\t.incbin "graphics/en/rfta/movies/%s.bin"' % seq['name'], '']
    finally:
        packer.close()
    asm += ['\t.align 2', '\t.global gRftaMovies', 'gRftaMovies: @ by the DS\'s sequence number']
    asm += ['\t.word gRftaMovie_%s' % s['name'] for s in SEQS]
    asm += [''] + tape_spots()
    open(os.path.join(ROOT, 'data', 'rfta', 'movies.s'), 'w').write('\n'.join(asm) + '\n')
    print('%d bytes (%.2f MB) in all' % (total, total / 2**20))


if __name__ == '__main__':
    if len(sys.argv) == 4:
        frame(int(sys.argv[1], 16), int(sys.argv[2])).save(sys.argv[3])
    elif len(sys.argv) == 2 and sys.argv[1] == 'list':
        for base, what in MOVIES.items():
            ents = entries(base)
            print('%08x: %s; %d entries, %d bytes compressed' % (base, what, len(ents), sum(s for o, s in ents)))
    else:
        main()
