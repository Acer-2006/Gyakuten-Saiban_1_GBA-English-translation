#!/usr/bin/env python3
"""English versions of the GBA backgrounds that carry Japanese writing, taken
from the English DS release.

The DS backgrounds of cases 1-4 are the GBA paintings at 256x192 (8 px more
on each side, 16 more above and below), and the DS keeps a Japanese and an
English copy of every background with writing on it. For each one:

  1. the places where the DS English copy differs from the DS Japanese copy
     are the writing (signs, logos, labels);
  2. each of those patches is found in the GBA picture by matching the DS
     Japanese patch against it (position and scale: a few DS backgrounds are
     reframed, e.g. the Steel Samurai title card);
  3. only those pixels are replaced, with the DS English pixels, in the GBA
     picture's own palette.

Everything else stays the GBA original. The evidence documents (Maya's phone
call, the DL-6 case file) are pages of text: the DS English page replaces the
whole page, set on the GBA page (the GBA page-turn arrow is kept). The
Gourd Lake newspaper has a different English layout on the DS and is fitted
to the GBA screen as a whole, and so is the Steel Samurai title card (its
English logo is larger and runs to the edge of the DS picture).

DS backgrounds: the 7-entry archives in data.bin (palette + 6 LZ chunks).
The Japanese originals are kept as *.png.orig. Run relocate_assets.py after."""
import os, sys, struct, json, shutil
import numpy as np
from PIL import Image
import cv2
from scipy import ndimage
sys.path.insert(0, os.path.dirname(__file__))
from dsdata import data, lz10

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
BG_DIR = os.path.join(ROOT, 'graphics', 'striped_images', 'backgrounds')

# ------------------------------------------------------------------ DS side
def decode_bg(base):
    """DS background archive at data.bin offset base -> (indices, palette RGB)"""
    d = data()
    n = struct.unpack_from('<I', d, base)[0]
    assert n == 7
    ents = [struct.unpack_from('<II', d, base + 4 + 8 * k) for k in range(n)]
    raw_pal = struct.unpack_from('<256H', d, base + ents[0][0])
    pal = np.array([((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in raw_pal], np.uint8)
    a = np.frombuffer(b''.join(lz10(d, base + o) for o, s in ents[1:]), np.uint8)
    if len(a) in (24576, 36864):                       # 4bpp
        a = np.stack([a & 15, a >> 4], 1).reshape(-1)
    t = a.reshape(-1, 8, 8)
    def lay(wt):
        ht = len(t) // wt
        return t[:ht * wt].reshape(ht, wt, 8, 8).transpose(0, 2, 1, 3).reshape(ht * 8, wt * 8)
    img = lay(32)
    if img.shape[0] > 192:
        if img[192:].any():
            w = lay(64)
            if not w[192:].any():
                img = w[:192]
        else:
            img = img[:192]
    return img, pal

def ds_rgb(base):
    img, pal = decode_bg(base)
    return pal[img]

# GBA backgrounds with writing; tools/en/ds_backgrounds.json gives the DS
# Japanese and English archive (data.bin offset) of each
SIGNS = [
    ('gGfx_BG011_GlobalStudiosStudioPath',      'おいでませ -> WELCOME'),
    ('gGfx_BG012_GlobalStudiosStaffArea',       'door plate -> WILL POWERS'),
    ('gGfx_BG031_BlueCorpCeoOffice',            'globe ribbon -> BLUECORP'),
    ('gGfx_BG059_Case3PinkPrincess',            'title logo -> PINK PRINCESS'),
    ('gGfx_BG061_EvidenceGlobalStudiosDiagram', 'map labels'),
    ('gGfx_BG070_GourdLakeEntrance',            'park sign -> Gourd Lake Nature Park'),
    ('gGfx_BG071_GourdLakePark',                'stall banner -> Samurai Dogs'),
    ('gGfx_BG072_GourdLakeParkNoBalloon',       'stall banner -> Samurai Dogs'),
    ('gGfx_BG077_GourdLakeBoatRental',          'roof sign -> BOAT RENTALS'),
    ('gGfx_BG105_TrialWon',                     '勝訴 -> Victory!'),
]
DOCUMENTS = [
    ('gGfx_BG045_EvidenceMayaPhoneCall1', 'phone call 1/3'),
    ('gGfx_BG046_EvidenceMayaPhoneCall2', 'phone call 2/3'),
    ('gGfx_BG048_EvidenceMayaPhoneCall3', 'phone call 3/3'),
    ('gGfx_BG082_EvidenceDL6CaseFile1', 'DL-6 case summary'),
    ('gGfx_BG083_EvidenceDL6CaseFile2', 'DL-6 victim data'),
    ('gGfx_BG084_EvidenceDL6CaseFile3', 'DL-6 suspect data'),
]
# redrawn for the DS English release as a whole: fitted to the GBA screen
WHOLE = [
    ('gGfx_BG089_Case4Newspaper', 'newspaper page, English layout', 'centre'),
    ('gGfx_BG063_Case3SteelSamurai', 'title card -> STEEL SAMURAI (logo at the bottom edge)', 'bottom'),
]

def ds_table():
    return json.load(open(os.path.join(os.path.dirname(__file__), 'ds_backgrounds.json')))

# ------------------------------------------------------------------ GBA side
def gba_png(label):
    import re
    gs = open(os.path.join(ROOT, 'data', 'graphics.s')).read()
    f = re.search(r'\.global %s\n%s:\n\s*\.incbin "([^"]+)"' % (label, label), gs).group(1)
    f = re.sub(r'\.(4|8)bpp\.striped$', '.png', f).replace('graphics_orig/', 'graphics/', 1)
    return os.path.join(ROOT, f)

def load_gba(label):
    path = gba_png(label)
    if not os.path.exists(path + '.orig'):
        shutil.copy(path, path + '.orig')
    im = Image.open(path + '.orig')
    assert im.mode == 'P'
    idx = np.array(im)
    pal = np.array(im.getpalette()[:768], np.uint8).reshape(-1, 3)
    return path, idx, pal, im.getpalette()

def save_gba(path, idx, rawpal):
    out = Image.fromarray(idx.astype(np.uint8), 'P')
    out.putpalette(rawpal)
    out.save(path)

def nearest(rgb, pal, usable):
    """RGB pixels (N,3) -> nearest palette index among usable"""
    cand = pal[usable].astype(np.int32)
    p = rgb.astype(np.int32)
    # weighted distance (green counts most)
    w = np.array([3, 4, 2])
    dist = (((p[:, None, :] - cand[None, :, :]) ** 2) * w).sum(2)
    return np.array(usable)[dist.argmin(1)]

# ------------------------------------------------------------------ signs
DIFF = 48            # colour difference (sum of RGB) that counts as writing
MIN_PATCH = 30       # pixels

def text_regions(jp, en):
    diff = np.abs(jp.astype(int) - en.astype(int)).sum(2) > DIFF
    lab, n = ndimage.label(diff)
    sizes = ndimage.sum(diff, lab, range(1, n + 1))
    keep = np.isin(lab, [k + 1 for k, s in enumerate(sizes) if s >= 4])
    grown = ndimage.binary_dilation(keep, iterations=6)
    lab, n = ndimage.label(grown)
    regions = []
    for k in range(1, n + 1):
        m = (lab == k) & keep
        if m.sum() < MIN_PATCH:
            continue
        ys, xs = np.nonzero(lab == k)
        regions.append((ys.min(), ys.max() + 1, xs.min(), xs.max() + 1, ndimage.binary_dilation(m, iterations=2)))
    return regions

PAD = 40             # patches may hang over the edge of the GBA picture

def overlap_score(g, p, x, y):
    """mean squared difference over the part of patch p (at x, y) inside g"""
    H, W = g.shape[:2]
    h, w = p.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if (x1 - x0) * (y1 - y0) < 0.6 * w * h:
        return None
    d = g[y0:y1, x0:x1] - p[y0 - y:y1 - y, x0 - x:x1 - x]
    return float((d * d).sum(2).mean())

def scaled(img, s):
    h, w = int(round(img.shape[0] * s)), int(round(img.shape[1] * s))
    if s == 1:
        return img.astype(np.float32)
    return cv2.resize(img.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)

def locate(gba_rgb, patch, scales, prior=None):
    """best (score, scale, x, y) of patch (DS Japanese) in the GBA picture;
    prior = (x, y) where the plain 256x192 -> 240x160 framing puts it"""
    g = gba_rgb.astype(np.float32)
    gp = cv2.copyMakeBorder(g, PAD, PAD, PAD, PAD, cv2.BORDER_REPLICATE)
    best = None
    if prior is not None:
        sc = overlap_score(g, scaled(patch, 1), *prior)
        if sc is not None:
            best = (sc, 1.0) + tuple(prior)
    for s in scales:
        p = scaled(patch, s)
        if p.shape[0] > gp.shape[0] or p.shape[1] > gp.shape[1] or min(p.shape[:2]) < 4:
            continue
        r = cv2.matchTemplate(gp, p, cv2.TM_SQDIFF)
        _, _, loc, _ = cv2.minMaxLoc(r)
        x, y = loc[0] - PAD, loc[1] - PAD
        sc = overlap_score(g, p, x, y)
        if sc is not None and (best is None or sc < best[0]):
            best = (sc, float(s), x, y)
    return best

def port_signs(label, jp_base, en_base, report):
    path, idx, pal, rawpal = load_gba(label)
    gba_rgb = pal[idx]
    jp, en = ds_rgb(jp_base), ds_rgb(en_base)
    usable = sorted(set(np.unique(idx)))
    out = idx.copy()
    for y0, y1, x0, x1, mask in text_regions(jp, en):
        M = 10
        y0, x0 = max(0, y0 - M), max(0, x0 - M)
        y1, x1 = min(jp.shape[0], y1 + M), min(jp.shape[1], x1 + M)
        mx = (jp.shape[1] - gba_rgb.shape[1]) // 2        # 8 (16 for the wide pictures)
        prior = (x0 - mx, y0 - 16)
        coarse = locate(gba_rgb, jp[y0:y1, x0:x1], np.arange(0.85, 1.155, 0.01), prior)
        fine = locate(gba_rgb, jp[y0:y1, x0:x1], np.arange(coarse[1] - 0.01, coarse[1] + 0.0101, 0.0025))
        score, s, gx, gy = min(coarse, fine) if fine else coarse
        h, w = int(round((y1 - y0) * s)), int(round((x1 - x0) * s))
        m = cv2.resize(mask[y0:y1, x0:x1].astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
        if s == 1:
            e = en[y0:y1, x0:x1]
        else:
            e = cv2.resize(en[y0:y1, x0:x1], (w, h), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
        # clip to the picture
        H, W = out.shape
        yy0, xx0 = max(0, gy), max(0, gx)
        yy1, xx1 = min(H, gy + h), min(W, gx + w)
        m = m[yy0 - gy:yy1 - gy, xx0 - gx:xx1 - gx]
        e = e[yy0 - gy:yy1 - gy, xx0 - gx:xx1 - gx]
        region = out[yy0:yy1, xx0:xx1]
        region[m] = nearest(e[m], pal, usable)
        report.append('  patch DS (%d,%d)-(%d,%d) -> GBA (%d,%d) scale %.3f match %.0f, %d px'
                      % (x0, y0, x1, y1, gx, gy, s, score, m.sum()))
    save_gba(path, out, rawpal)

# ------------------------------------------------------------------ documents
def port_document(label, en_base, report):
    """DS English text page (white on black) set on the GBA page"""
    path, idx, pal, rawpal = load_gba(label)
    en = ds_rgb(en_base)
    lum = en.astype(int).sum(2)
    ink = lum > 300
    ys, xs = np.nonzero(ink)
    H, W = idx.shape
    # GBA page: black background, white text, the page-turn arrow at the bottom
    black = int(np.bincount(idx.ravel()).argmax())
    white = int(max(set(np.unique(idx)), key=lambda i: int(pal[i].astype(int).sum())))
    out = np.full_like(idx, black)
    arrow = locate_arrow(idx, pal, black)
    # DS page content box -> centred in the GBA page
    cx0, cx1, cy0, cy1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    dx = (W - (cx1 - cx0)) // 2 - cx0
    dy = min((H - (cy1 - cy0)) // 2, 2) - cy0                # top, as on the DS
    page = np.zeros((H, W), bool)
    for y, x in zip(ys, xs):
        if 0 <= y + dy < H and 0 <= x + dx < W:
            page[y + dy, x + dx] = True
    assert page.sum() == ink.sum(), 'document does not fit'
    out[page] = white
    if arrow is not None:
        # the GBA page-turn arrow, at the bottom centre or as near it as the
        # English text allows
        ay0, ay1, ax0, ax1 = arrow
        shape = idx[ay0:ay1, ax0:ax1]
        for shift in sorted(range(-80, 81), key=abs):
            x0, x1 = ax0 + shift, ax1 + shift
            if x0 >= 1 and x1 < W - 1 and not page[ay0 - 2:min(H, ay1 + 2), x0 - 2:x1 + 2].any():
                region = out[ay0:ay1, x0:x1]
                region[shape != black] = shape[shape != black]
                if shift:
                    report.append('  page-turn arrow moved %d px' % shift)
                break
        else:
            report.append('  page-turn arrow left out (no room)')
    save_gba(path, out, rawpal)
    report.append('  DS page content %dx%d placed at (%d,%d)' % (cx1 - cx0, cy1 - cy0, cx0 + dx, cy0 + dy))

def locate_arrow(idx, pal, black):
    """the page-turn arrow (a small down-pointing triangle at the bottom centre)"""
    H, W = idx.shape
    zone = idx[H - 16:, W // 2 - 24:W // 2 + 24] != black
    if not zone.any():
        return None
    ys, xs = np.nonzero(zone)
    return (H - 16 + ys.min(), H - 16 + ys.max() + 1, W // 2 - 24 + xs.min(), W // 2 - 24 + xs.max() + 1)

# ------------------------------------------------------------------ newspaper
def port_whole(label, en_base, report, anchor='centre'):
    """the DS English picture fitted to the GBA screen (uniform scale; the
    overhang is cut evenly, or from the top for anchor='bottom')"""
    path, idx, pal, rawpal = load_gba(label)
    en = ds_rgb(en_base)
    H, W = idx.shape
    s = max(W / en.shape[1], H / en.shape[0])
    w, h = int(round(en.shape[1] * s)), int(round(en.shape[0] * s))
    r = cv2.resize(en, (w, h), interpolation=cv2.INTER_AREA)
    x0, y0 = (w - W) // 2, (h - H) // 2
    if anchor == 'bottom':
        y0 = h - H
    r = r[y0:y0 + H, x0:x0 + W]
    usable = sorted(set(np.unique(idx)))
    out = nearest(r.reshape(-1, 3), pal, usable).reshape(H, W)
    save_gba(path, out, rawpal)
    report.append('  scaled %.3f, cropped %d px left/right, %d px top/bottom' % (s, x0, y0))

def main():
    table = ds_table()
    report = []
    for label, what in SIGNS:
        jp, en = table[label]
        report.append('%s (%s)' % (label, what))
        port_signs(label, int(jp, 16), int(en, 16), report)
    for label, what in DOCUMENTS:
        report.append('%s (%s)' % (label, what))
        port_document(label, int(table[label][1], 16), report)
    for label, what, anchor in WHOLE:
        report.append('%s (%s)' % (label, what))
        port_whole(label, int(table[label][1], 16), report, anchor)
    print('\n'.join(report))

if __name__ == '__main__':
    main()
