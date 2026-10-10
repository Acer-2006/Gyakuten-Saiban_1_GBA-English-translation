#!/usr/bin/env python3
"""Court Record pictures (evidence and profiles) from the DS English release.

The DS data.bin holds the 64x64 Court Record pictures four times over: the
Japanese set, the English set (same order, 147 Japanese pictures plus the
fifth episode's additions), and the small versions of both. Each GBA picture
is found in the Japanese DS set (they are the same drawings), and replaced
with the English DS picture at the same place in the English set. Most are
identical to the GBA ones; the ones with writing on them (the passport, the
notes, the script, the scrapbook...) get the DS English lettering.

usage: port_evidence_pics.py [report.png]
keeps each changed picture's original as *.png.orig"""
import os, sys, re, struct, shutil, glob
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from dsdata import data

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
HEADER = bytes([3, 3, 3, 0, 0x14, 0, 0, 0, 0, 8, 0, 0, 0x14, 8, 0, 0, 0x20, 0, 0, 0])   # 64x64, 16 colours
JP_COUNT = 147          # the English set follows the Japanese one, same order

def ds_pictures():
    d = data()
    out = []
    for m in re.finditer(re.escape(HEADER), d):
        o = m.start()
        raw = np.frombuffer(d[o + 0x14:o + 0x814], np.uint8)
        a = np.zeros(4096, np.uint8)
        a[0::2] = raw & 15
        a[1::2] = raw >> 4
        pal = struct.unpack_from('<16H', d, o + 0x814)
        rgb = np.array([((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in pal], np.uint8)
        out.append((o, a.reshape(64, 64), rgb))
    return out

def rgb5(idx, pal):
    return np.asarray(pal, int)[idx] >> 3

def same(a, b):
    return (np.abs(a - b).max(2) == 0).mean()

def same_drawing(a, b):
    """share of the picture's own pixels (not its plain background) that match"""
    flat = a.reshape(-1, 3)
    vals, counts = np.unique(flat, axis=0, return_counts=True)
    bg = vals[np.argmax(counts)]
    fg = np.abs(a - bg).max(2) > 0
    return (np.abs(a - b).max(2) == 0)[fg].mean()

pics = ds_pictures()
jp = pics[:JP_COUNT]
en = pics[JP_COUNT:2 * JP_COUNT]
assert len(en) == JP_COUNT

files = sorted(glob.glob(os.path.join(ROOT, 'graphics/evidence_profile_pictures/*/*.png')))
changed, report = [], []
for f in files:
    src = f + '.orig' if os.path.exists(f + '.orig') else f
    im = Image.open(src)
    g = rgb5(np.array(im), np.array(im.getpalette()[:48]).reshape(16, 3))
    scores = [same_drawing(g, rgb5(a, p)) for o, a, p in jp]
    k = int(np.argmax(scores))
    # the DS set has a few pictures twice; fine when their English versions agree
    twins = [j for j, v in enumerate(scores) if j != k and v == scores[k]]
    for j in twins:
        if same(rgb5(en[j][1], en[j][2]), rgb5(en[k][1], en[k][2])) < 1.0:
            raise SystemExit('%s: DS pictures %d and %d both match but differ in English' % (f, k, j))
    second = max([v for j, v in enumerate(scores) if j != k and j not in twins] or [0])
    # the same drawing: nearly every pixel equal, far above any other picture
    # (a few GBA pictures differ from the DS ones by a handful of pixels)
    if scores[k] < 0.8 or scores[k] - second < 0.3:
        raise SystemExit('%s: no Japanese DS picture matches (best %d, %.3f; next %.3f)' % (f, k, scores[k], second))
    o, a, p = en[k]
    s = same(g, rgb5(a, p))
    name = os.path.relpath(f, ROOT)
    if s < 1.0:
        if not os.path.exists(f + '.orig'):
            shutil.copy(f, f + '.orig')
        out = Image.fromarray(a, 'P')
        out.putpalette([int(v) for v in p.reshape(-1)])
        out.save(f)
        changed.append(name)
        report.append((name, im.convert('RGB'), out.convert('RGB')))
    print('%-70s DS jp %3d (%.3f) en %3d @%#x %s' % (name, k, scores[k], k + JP_COUNT, o, 'replaced' if s < 1 else 'same'))
print('%d pictures, %d replaced with the DS English ones' % (len(files), len(changed)))

if len(sys.argv) > 1 and report:
    sheet = Image.new('RGB', (len(report) * 140, 150), 'white')
    for i, (n, a, b) in enumerate(report):
        sheet.paste(a, (i * 140, 0))
        sheet.paste(b, (i * 140 + 68, 0))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(sys.argv[1])
