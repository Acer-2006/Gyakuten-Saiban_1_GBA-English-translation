#!/usr/bin/env python3
"""Build the English evidence/profile description images (160x64) for the GBA
Court Record from the English DS release.

  - name line: the DS English name plate (its own pixels), plus the age for
    profiles, as the GBA original shows it ("Mia Fey (27)")
  - description: the DS English description text, read exactly out of the DS
    description bitmaps (ds_text.py), re-wrapped to the GBA width and drawn
    with the DS dialogue font (the same font as the text box)

Writes the PNGs in place under graphics/evidence_profile_descriptions/
(keeping the Japanese originals as *.png.orig). Run relocate_assets.py after."""
import os, re, sys, hashlib
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from dsdata import name_plate
import ds_text, dsfont

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
src = open(os.path.join(ROOT, 'src/court_record.c')).read()
table = re.findall(r'\.descriptionTiles = (\w+),', src)
gs = open(os.path.join(ROOT, 'data/graphics.s')).read()
sym2file = {k: v.replace('graphics_orig/', 'graphics/', 1) for k, v in
            re.findall(r'\.global (gGfx\w+_description)\n\w+:\n\s*\.incbin "([^"]+)\.4bpp\.lz"', gs)}

BG, TEXT, NAME = 9, 8, 15
DS_NAME_TEXT = 2
DUMMY = {41, 70, 107}            # unused entries ("ダミー" in both versions)
AREA_W = 152                     # columns 152-159 are transparent in the originals
TEXT_X, TEXT_W = 2, 149
NAME_SHIFT = -1                  # name plate ink rows 2..14 -> 1..13
# glyph origin of the first line and line pitch: three lines use the original
# 16-pixel rows; text that needs a fourth line is set on 12-pixel rows (the
# DS font's descenders reach the cell's row 14, so a fourth line's start one
# row higher than the Japanese font allowed)
LAYOUTS = {3: (16, 16), 4: (13, 12)}
# The DS sets these texts in its dialogue font at its own spacing, three
# lines across a 256-pixel panel; the GBA's panel is 149 pixels. Tried in
# turn, the first that fits: the text box's spacing (dsfont: the DS's widths,
# a pixel less) on three lines, then the letters one pixel apart (and word
# spaces of 4, then 3) on three lines, then the same on four.
# (space advance or None for the font's, added to every other advance, tight)
SPACINGS = ((None, 0, False), (4, 0, True), (3, 0, True))
NBSP = ' '

def name_order():
    """The DS English name plates are stored once per distinct name, in order of
    first appearance in this table. Recover that order from the original
    (Japanese) name lines, which repeat for every variant of an entry."""
    seen, out = {}, []
    for sym in table:
        path = os.path.join(ROOT, sym2file[sym] + '.png')
        orig = path + '.orig' if os.path.exists(path + '.orig') else path
        top = np.array(Image.open(orig).convert('RGB'))[0:16].tobytes()
        h = hashlib.md5(top).hexdigest()
        if h not in seen:
            seen[h] = len(seen)
        out.append(seen[h])
    return out

def ages(order):
    """table index -> age text for profiles (from the DS info panels)"""
    out = {}
    for i, sym in enumerate(table):
        if not sym.startswith('gGfxProfiles') or i in DUMMY:
            continue
        m = re.match(r'Age: ?(.*)$', ds_text.info_line(i))
        if m:
            out[i] = m.group(1)
    for i, sym in enumerate(table):      # a profile variant without an info panel
        if sym.startswith('gGfxProfiles') and i not in out and i not in DUMMY:
            same = [out[j] for j in out if order[j] == order[i]]
            if same:
                out[i] = same[0]
    return {i: a for i, a in out.items() if a and a != 'deceased'}

def join(lines):
    s = ''
    for l in lines:
        if not s:
            s = l
        elif s.endswith('-') and s[-2:-1].isalpha() and l[:1].islower():
            s += l                       # word hyphenated across DS lines
        else:
            s += ' ' + l
    # The GBA has no touch screen: the Check button is the L button there
    # (the Japanese GBA text says "Lボタンで…").
    s = re.sub(r'Touch (the )?Check( Button)?', 'Press L', s)
    # keep "2:00 PM" and "Exhibit A" together
    s = re.sub(r'(\d) (AM|PM)\b', r'\1' + NBSP + r'\2', s)
    s = re.sub(r'\b(Oct|Dec) (\d)', r'\1' + NBSP + r'\2', s)
    s = s.replace('Photo #', 'Photo' + NBSP + '#')
    return re.sub(r'Exhibit ([A-Z])\b', 'Exhibit' + NBSP + r'\1', s)

def render_line(s, spacing):
    return dsfont.render(s.replace(NBSP, ' '), *spacing)

def width(s, spacing):
    return dsfont.width(s.replace(NBSP, ' '), *spacing)

def wrap(text, spacing):
    out, cur = [], ''
    for w in text.split(' '):
        t = cur + ' ' + w if cur else w
        if width(t, spacing) <= TEXT_W:
            cur = t
        else:
            out.append(cur); cur = w
    out.append(cur)
    return out

def touching(lines, spacing, y0, pitch):
    """pixels two lines would share (a descender on the capital below)"""
    a = np.zeros((y0 + pitch * len(lines) + dsfont.ROWS, AREA_W + 16), int)
    for k, l in enumerate(lines):
        ys, xs = np.nonzero(render_line(l, spacing))
        a[ys + y0 + pitch * k, xs + TEXT_X] += 1
    return int((a > 1).sum())

def wraps(words, spacing, n):
    """every way to set the words on at most n lines that fit, the fullest
    first lines first"""
    if not words:
        yield []
        return
    if n == 0:
        return
    for k in range(len(words), 0, -1):
        line = ' '.join(words[:k])
        if width(line, spacing) <= TEXT_W:
            for rest in wraps(words[k:], spacing, n - 1):
                yield [line] + rest

def layout(lines):
    """-> (lines, spacing, (first line's row, pitch)): the fewest lines, then
    the widest spacing, with no two lines touching (another line break where
    the first one's would)"""
    text = join(lines)
    for n in sorted(LAYOUTS):    # the plain line breaks first
        for spacing in SPACINGS:
            out = wrap(text, spacing)
            if len(out) <= n and all(width(l, spacing) <= TEXT_W for l in out) \
               and not touching(out, spacing, *LAYOUTS[n]):
                return out, spacing, LAYOUTS[n]
    def ragged(out, spacing):
        return sum((TEXT_W - width(l, spacing)) ** 2 for l in out[:-1])
    least = None                 # (pixels shared, layout): if every layout touches
    for n in sorted(LAYOUTS):    # then the evenest other breaks
        for spacing in SPACINGS:
            good = []
            for out in wraps(text.split(' '), spacing, n):
                t = touching(out, spacing, *LAYOUTS[n])
                if not t:
                    good.append((ragged(out, spacing), out))
                elif least is None or t < least[0]:
                    least = (t, (out, spacing, LAYOUTS[n]))
            if good:
                return min(good)[1], spacing, LAYOUTS[n]
    if least is not None and least[0] <= 2:
        return least[1]          # (one: a comma's tail on the P below, "[Oct 15," / "2:00 PM, Photo #2]")
    raise ValueError('does not fit: ' + text)

def draw_text(a, lines, spacing, y0, pitch):
    for k, l in enumerate(lines):
        put(a, render_line(l, spacing), TEXT_X, y0 + pitch * k, TEXT)

def put(a, mask, x0, y0, color):
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return
    assert (ys + y0).min() >= 0 and (ys + y0).max() < a.shape[0] and (xs + x0).max() < AREA_W
    a[ys + y0, xs + x0] = color

def build(i, name_idx, age):
    path = os.path.join(ROOT, sym2file[table[i]] + '.png')
    if not os.path.exists(path + '.orig'):
        os.rename(path, path + '.orig')
    base = Image.open(path + '.orig')
    a = np.array(base).copy()
    a[:, :AREA_W] = BG
    lines = []
    if i not in DUMMY:
        n = np.array(name_plate(name_idx)) == DS_NAME_TEXT
        cols = np.where(n.any(0))[0]
        n = n[:, cols[0]:cols[-1] + 1]
        suffix = dsfont.render(' (%s)' % age) if age else np.zeros((dsfont.ROWS, 0), np.uint8)
        w = n.shape[1] + suffix.shape[1]
        x0 = (AREA_W - w) // 2
        put(a, n, x0, NAME_SHIFT, NAME)
        put(a, suffix, x0 + n.shape[1], NAME_SHIFT, NAME)   # same baseline as the plate
        lines, spacing, (y0, pitch) = layout(ds_text.description(i))
        draw_text(a, lines, spacing, y0, pitch)
    out = Image.fromarray(a, 'P'); out.putpalette(base.getpalette())
    out.save(path)
    return lines

if __name__ == '__main__':
    order = name_order()
    age = ages(order)
    report = []
    for i in range(len(table)):
        lines = build(i, order[i], age.get(i))
        report.append('%3d %s' % (i, ' | '.join(lines)))
    if '-v' in sys.argv:
        print('\n'.join(report))
    print('built', len(table), 'descriptions;', len(set(order)), 'distinct names;', len(age), 'with age')
