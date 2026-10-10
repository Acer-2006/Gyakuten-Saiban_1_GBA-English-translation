"""Shared helpers for porting the DS English effect animations (speech bubbles,
testimony banners, verdict) into the GBA animation format."""
import os, sys, struct
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import animfmt
from dsdata import archive, data

ARC_EFFECTS = 0x2202220          # DS data.bin archive: gfx/seq pairs (effects, case 5)

def ds_entry(i):
    o, s = archive(ARC_EFFECTS)[i]
    return data()[o:o + s]

def render_indexed(gfx, seq, frame_index, canvas, origin):
    """one frame as palette indices (0 = transparent) and the palette number per pixel"""
    fr = animfmt.frames(seq)[frame_index]
    idx = np.zeros((canvas[1], canvas[0]), np.uint8)
    pal = np.zeros((canvas[1], canvas[0]), np.uint8)
    for x, y, d in animfmt.sprites(seq, fr[0]):
        w, h = animfmt.SIZES[d >> 12]
        t = np.frombuffer(animfmt.sprite_tiles(gfx, d, fr[2]), np.uint8)
        nib = np.stack([t & 15, t >> 4], 1).reshape(-1, 8, 8)
        p = ((d >> 9) & 7) if fr[2] & 1 else ((d >> 11) & 1)
        for k in range(len(nib)):
            tx, ty = origin[0] + x + (k % (w // 8)) * 8, origin[1] + y + (k // (w // 8)) * 8
            for yy in range(8):
                for xx in range(8):
                    v = nib[k][yy][xx]
                    if v and 0 <= tx + xx < canvas[0] and 0 <= ty + yy < canvas[1]:
                        idx[ty + yy, tx + xx] = v; pal[ty + yy, tx + xx] = p
    return idx, pal

def scale_indexed(idx, colors, factor, usable):
    """Downscale an indexed image: average the colours over each target pixel
    (alpha-weighted), keep pixels at least half covered, and map each back to
    the nearest of the usable palette entries."""
    h, w = idx.shape
    rgb = np.array(colors, np.float64)[idx]
    a = (idx > 0).astype(np.float64)
    tw, th = int(round(w * factor)), int(round(h * factor))
    def rs(ch):
        return np.array(Image.fromarray(ch.astype(np.float32), 'F').resize((tw, th), Image.BOX))
    A = rs(a)
    P = np.stack([rs(rgb[:, :, c] * a) for c in range(3)], 2)
    out = np.zeros((th, tw), np.uint8)
    keep = A >= 0.5
    col = P[keep] / A[keep][:, None]
    cand = np.array([colors[u] for u in usable], np.float64)
    dist = ((col[:, None, :] - cand[None, :, :]) ** 2).sum(2)
    out[keep] = np.array(usable)[dist.argmin(1)]
    return out

# GBA sprite sizes: (w, h) in tiles -> size index (size << 2 | shape)
SIZE_INDEX = {(1, 1): 0, (2, 1): 1, (1, 2): 2, (2, 2): 4, (4, 1): 5, (1, 4): 6,
              (4, 4): 8, (4, 2): 9, (2, 4): 10, (8, 8): 12, (8, 4): 13, (4, 8): 14}

def cover(filled, waste_cost=1.0):
    """Cover the non-empty tiles (bool grid, tiles) with GBA sprite rectangles.
    Greedy: take the rectangle with the best (new tiles - waste_cost * other
    tiles) until everything is covered. -> list of (tx, ty, tw, th)"""
    H, W = filled.shape
    todo = filled.copy()
    rects = []
    while todo.any():
        best = None
        for (tw, th) in SIZE_INDEX:
            for ty in range(-th + 1, H):
                for tx in range(-tw + 1, W):
                    y0, y1, x0, x1 = max(ty, 0), min(ty + th, H), max(tx, 0), min(tx + tw, W)
                    if y0 >= y1 or x0 >= x1:
                        continue
                    new = todo[y0:y1, x0:x1].sum()
                    if not new:
                        continue
                    score = new - waste_cost * (tw * th - new)
                    if best is None or score > best[0]:
                        best = (score, tx, ty, tw, th)
        _, tx, ty, tw, th = best
        rects.append((tx, ty, tw, th))
        todo[max(ty, 0):ty + th, max(tx, 0):tx + tw] = False
    return rects
