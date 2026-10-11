"""The animation format shared by the GBA game and the DS port.

A block of frame data ("seq"): u32 flags, u32 offset of the graphics block
(from the start of the graphics file), then 8-byte frames
{u16 spriteDataOffset, u8 duration, u8 flags, u8 songId, u8 action, u16 pad}.
spriteDataOffset points (from the start of the seq block) to u16 count and
count x {s8 x, s8 y, u16 data}; data: bits 0-10 tile (0-8 when frame flag 1),
9-11 palette (flag 1) / bit 11 palette, 12-15 size index (shape<<2|size).
A graphics block: u32 palette count (bit 31 = compressed tiles), the 16-colour
palettes, then tiles: plain 4bpp tiles, or with bit 31 a u32 offset table
indexed by tile number pointing to RLE streams of u16 words
(0x8000|n: n copies of the next word; else n literal words)."""
import struct
import numpy as np

SIZES = {0: (8, 8), 1: (16, 8), 2: (8, 16), 4: (16, 16), 5: (32, 8), 6: (8, 32),
         8: (32, 32), 9: (32, 16), 10: (16, 32), 12: (64, 64), 13: (64, 32), 14: (32, 64)}  # (w, h)

def frames(seq):
    """-> list of (spriteDataOffset, duration, flags, songId, action) until the terminator"""
    out = []
    o = 8
    while o + 8 <= len(seq):
        sd, dur, fl, song, act = struct.unpack_from('<HBBBB', seq, o)
        out.append((sd, dur, fl, song, act))
        o += 8
        if dur == 0 or o >= min(f[0] for f in out):
            break
    return out

def sprites(seq, sd):
    n = struct.unpack_from('<H', seq, sd)[0]
    return [struct.unpack_from('<bbH', seq, sd + 4 + 4 * k) for k in range(n)]  # header is one 4-byte slot

def palettes(gfx):
    n = struct.unpack_from('<I', gfx, 0)[0] & 0x7FFFFFFF
    pals = []
    for p in range(n):
        cols = struct.unpack_from('<16H', gfx, 4 + 32 * p)
        pals.append([((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in cols])
    return pals

def sprite_tiles(gfx, data, frame_flags):
    """4bpp tile bytes of one sprite"""
    raw = struct.unpack_from('<I', gfx, 0)[0]
    npal = raw & 0x7FFFFFFF
    tiles = 4 + 32 * npal
    w, h = SIZES[data >> 12]
    size = w * h // 2
    if raw & 0x80000000:
        tn = data & 0x1FF
        off = struct.unpack_from('<I', gfx, tiles + 4 * tn)[0]
        p = tiles + off
        out = bytearray()
        while len(out) < size:
            v = struct.unpack_from('<H', gfx, p)[0]
            if v & 0x8000:
                n = v & 0x7FFF; word = gfx[p + 2:p + 4]; out += word * n; p += 4
            else:
                out += gfx[p + 2:p + 2 + 2 * v]; p += 2 + 2 * v
        return bytes(out[:size])
    mask = 0x1FF if frame_flags & 1 else 0x7FF
    start = tiles + (data & mask) * 32
    return gfx[start:start + size]

def render(gfx, seq, frame_index, canvas=(256, 192), origin=(128, 96), bg=(255, 0, 255)):
    """draw one frame (1D sprite tile mapping) -> HxWx3 array"""
    pals = palettes(gfx)
    fr = frames(seq)[frame_index]
    img = np.zeros((canvas[1], canvas[0], 3), np.uint8); img[:] = bg
    for x, y, data in sprites(seq, fr[0]):
        w, h = SIZES[data >> 12]
        t = np.frombuffer(sprite_tiles(gfx, data, fr[2]), np.uint8)
        nib = np.stack([t & 15, t >> 4], 1).reshape(-1)
        tl = nib.reshape(-1, 8, 8)
        pal = pals[((data >> 9) & 7) if fr[2] & 1 else ((data >> 11) & 1)] if pals else None
        for k in range(len(tl)):
            tx, ty = (k % (w // 8)) * 8, (k // (w // 8)) * 8
            for yy in range(8):
                for xx in range(8):
                    v = tl[k][yy][xx]
                    if v:
                        px, py = origin[0] + x + tx + xx, origin[1] + y + ty + yy
                        if 0 <= px < canvas[0] and 0 <= py < canvas[1]:
                            img[py, px] = pal[v] if pal else (v * 16,) * 3
    return img
