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
call, the DL-6 case file) are pages of text: the DS English lines replace the
Japanese ones, re-set in the Japanese page's layout (line pitch, page number
and page-turn arrow), so the B / L / Back prompts stay clear of the text. The
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
    ('gGfx_BG045_EvidenceMayaPhoneCall1', 'phone call 1/3', 'phone'),
    ('gGfx_BG046_EvidenceMayaPhoneCall2', 'phone call 2/3', 'phone'),
    ('gGfx_BG048_EvidenceMayaPhoneCall3', 'phone call 3/3', 'phone'),
    ('gGfx_BG082_EvidenceDL6CaseFile1', 'DL-6 case summary', 'dl6'),
    ('gGfx_BG083_EvidenceDL6CaseFile2', 'DL-6 victim data', 'dl6'),
    ('gGfx_BG084_EvidenceDL6CaseFile3', 'DL-6 suspect data', 'dl6'),
]
# redrawn for the DS English release as a whole: fitted to the GBA screen
WHOLE = [
    ('gGfx_BG089_Case4Newspaper', 'newspaper page, English layout', 'top'),
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
        j = jp[y0:y1, x0:x1] if s == 1 else \
            cv2.resize(jp[y0:y1, x0:x1], (w, h), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
        # Writing the English picture adds where the Japanese one has none (a
        # label with its leader line beside a building, not over the Japanese
        # one) is moved into the picture when the GBA frame cuts it: the GBA
        # pictures show less above and below than the DS ones, and the map of
        # Global Studios cut the top off "Main Gate". Writing that replaces
        # Japanese writing stays where it is (it has to cover it).
        H, W = out.shape
        lab, n = ndimage.label(m, structure=np.ones((3, 3)))
        painted, moved = 0, []
        for k in range(1, n + 1):
            c = lab == k
            ys, xs = np.nonzero(c)
            dy = max(0, -(gy + ys.min())) - max(0, gy + ys.max() + 1 - H)
            dx = max(0, -(gx + xs.min())) - max(0, gx + xs.max() + 1 - W)
            if dy or dx:
                jc = j[c].reshape(-1, 3).astype(int)
                vals, counts = np.unique(jc, axis=0, return_counts=True)
                plain = (np.abs(jc - vals[np.argmax(counts)]).sum(1) > DIFF).mean() < 0.02
                if plain:
                    dy += 1 if dy > 0 else -1 if dy < 0 else 0      # a pixel clear of the edge
                    dx += 1 if dx > 0 else -1 if dx < 0 else 0
                    moved.append('%+d,%+d' % (dx, dy))
                else:
                    dy = dx = 0
            Y, X = gy + ys + dy, gx + xs + dx
            ok = (Y >= 0) & (Y < H) & (X >= 0) & (X < W)
            out[Y[ok], X[ok]] = nearest(e[ys[ok], xs[ok]], pal, usable)
            painted += int(ok.sum())
        report.append('  patch DS (%d,%d)-(%d,%d) -> GBA (%d,%d) scale %.3f match %.0f, %d px%s'
                      % (x0, y0, x1, y1, gx, gy, s, score, painted,
                         (', moved into the picture ' + ' '.join(moved)) if moved else ''))
    save_gba(path, out, rawpal)

# ------------------------------------------------------------------ documents
# The page layout of the Japanese GBA pages: text from y 6 down to y 136,
# 15 px from one line to the next; the page number (bottom left) and the
# page-turn arrow (bottom centre) on the rows below; the B / L / Back
# prompts are sprites over the bottom right corner (x 176-239, y 144-159),
# which the Japanese pages leave empty.
DOC_TOP, DOC_BOTTOM = 6, 136
DOC_FOOT = 140          # rows from here down come from the Japanese page
DOC_PITCH = 15          # line to line, as on the GBA (and within a DS block)
DOC_RIGHT = 238         # last column the text may use

def doc_lines(ink):
    """the DS page's text lines (row bands), without its page number (the DS
    puts it at the bottom right; the GBA one is used instead)"""
    ink = ink.copy()
    ink[155:, 210:] = False
    rows = np.nonzero(ink.any(1))[0]
    bands, s0, prev = [], rows[0], rows[0]
    for r in rows[1:]:
        if r != prev + 1:
            bands.append((s0, prev + 1))
            s0 = r
        prev = r
    bands.append((s0, prev + 1))
    return ink, bands

def port_document(label, en_base, report, layout=None):
    """The DS English text page (white on black), re-set in the Japanese GBA
    page's layout. Each DS line keeps its pixels and its place across the
    page; the lines are stacked 15 px apart as on the GBA page (the DS pitch
    within a paragraph), with the gaps between paragraphs (speakers) kept as
    far as the page allows, so the text ends above the GBA page number and
    arrow, which are the Japanese page's own, and the B / L / Back prompts
    in the bottom right corner have nothing under them."""
    path, idx, pal, rawpal = load_gba(label)
    en = ds_rgb(en_base)
    ink, bands = doc_lines(en.astype(int).sum(2) > 300)
    H, W = idx.shape
    black = int(np.bincount(idx.ravel()).argmax())
    white = int(max(set(np.unique(idx)), key=lambda i: int(pal[i].astype(int).sum())))
    # paragraphs: lines further apart than a line pitch (plus a little) on the DS
    gaps = [bands[i + 1][0] - bands[i][0] - DOC_PITCH for i in range(len(bands) - 1)]
    para = [g > 4 for g in gaps]
    def height(gap, pitch):
        y = 0
        for i, g in enumerate(gaps):
            y += pitch + (min(g, gap) if para[i] else 0)
        return y + bands[-1][1] - bands[-1][0]
    xs = np.nonzero(ink.any(0))[0]
    dx = min((W - 256) // 2, DOC_RIGHT - int(xs.max()))
    assert xs.min() + dx >= 1, label
    # the text may go on below DOC_BOTTOM, down to 2 px above the footer
    # rows, where nothing of the footer (page number, arrow) is under it
    foot = np.nonzero((idx[DOC_FOOT:] != black).any(0))[0]
    foot_top = DOC_FOOT + int(np.nonzero((idx[DOC_FOOT:] != black).any(1))[0].min())
    def fits(gap, pitch):
        y = DOC_TOP
        for i, (a, b) in enumerate(bands):
            bottom = y + b - a
            if bottom > foot_top - 2:
                return False
            if bottom > DOC_BOTTOM:
                cols = np.nonzero(ink[a:b].any(0))[0] + dx
                if np.any(np.abs(cols[:, None] - foot[None, :]) <= 3):
                    return False
            if i < len(gaps):
                y += pitch + (min(gaps[i], gap) if para[i] else 0)
        return True
    # the GBA pitch with a visible gap between speakers if possible, else a
    # pixel less from line to line, else whatever fits
    best = None
    for pitch in (DOC_PITCH, DOC_PITCH - 1, DOC_PITCH - 2):
        gap = max(gaps) if gaps else 0
        while gap > 0 and not fits(gap, pitch):
            gap -= 1
        if fits(gap, pitch) and (gap >= min(4, max(gaps) if gaps else 0) or not any(para)):
            best = (pitch, gap)
            break
        if best is None and fits(gap, pitch):
            best = (pitch, gap)
    assert best, label
    if layout:
        # the same spacing on every page of the document (the tightest page's)
        assert fits(*layout), label
        best = layout
    pitch, gap = best
    out = np.full_like(idx, black)
    y = DOC_TOP
    for i, (a, b) in enumerate(bands):
        strip = ink[a:b, :]
        ys_, xs_ = np.nonzero(strip)
        out[y + ys_, xs_ + dx] = white
        if i < len(gaps):
            y += pitch + (min(gaps[i], gap) if para[i] else 0)
    # page number and page-turn arrow: the Japanese page's
    out[DOC_FOOT:] = idx[DOC_FOOT:]
    save_gba(path, out, rawpal)
    report.append('  %d DS lines re-set: pitch %d, paragraph gap %d (DS %s), x shift %d, last line ends y %d'
                  % (len(bands), pitch, gap, max(gaps) if gaps else 0, dx, y + bands[-1][1] - bands[-1][0]))
    return best

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
    overhang is cut evenly, from the top for anchor='bottom', or from the
    bottom for anchor='top'). The newspaper is cut from the bottom: cut evenly,
    the top of "HOT NEWS!" and of the headline bar went (the bottom has the
    photo caption and the ends of the columns, in type too small to read on
    the GBA screen either way)"""
    path, idx, pal, rawpal = load_gba(label)
    en = ds_rgb(en_base)
    H, W = idx.shape
    s = max(W / en.shape[1], H / en.shape[0])
    w, h = int(round(en.shape[1] * s)), int(round(en.shape[0] * s))
    r = cv2.resize(en, (w, h), interpolation=cv2.INTER_AREA)
    x0, y0 = (w - W) // 2, (h - H) // 2
    if anchor == 'bottom':
        y0 = h - H
    elif anchor == 'top':
        y0 = 0
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
    for doc in sorted(set(d for l, w, d in DOCUMENTS)):
        pages = [(l, w) for l, w, d in DOCUMENTS if d == doc]
        sizes = [port_document(l, int(table[l][1], 16), []) for l, w in pages]
        layout = (min(p for p, g in sizes), min(g for p, g in sizes if p == min(p for p, g in sizes)))
        for label, what in pages:
            report.append('%s (%s)' % (label, what))
            port_document(label, int(table[label][1], 16), report, layout)
    for label, what, anchor in WHOLE:
        report.append('%s (%s)' % (label, what))
        port_whole(label, int(table[label][1], 16), report, anchor)
    print('\n'.join(report))

if __name__ == '__main__':
    main()
