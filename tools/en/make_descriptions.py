#!/usr/bin/env python3
"""Build the English evidence/profile description images for the GBA Court
Record from the English DS release.

  - name line: the DS English name plate (its own pixels), plus the age for
    profiles, as the GBA original shows it ("Mia Fey (27)")
  - description: the DS English description text, read exactly out of the DS
    description bitmaps (ds_text.py), re-wrapped to the GBA width and drawn
    with the DS dialogue font (the same font as the text box)

The pictures are 160x72, eight rows more than the Japanese ones (160x64):
the panel's red runs five rows below where the Japanese pictures end, and
four lines of the DS font need them to keep clear of each other. The last
three rows are the panel's bottom border (desc_tiles.py, court_record.c).

Writes the PNGs in place under graphics/evidence_profile_descriptions/
(keeping the Japanese originals as *.png.orig). Run relocate_assets.py after."""
import os, re, sys, hashlib, itertools, functools
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
# The picture: 160x72. Rows 0-68 are the panel's red (the Japanese pictures
# had 0-63), rows 69-71 its bottom border (the BG2 tile 0x4C's last three
# rows), drawn here so the sprites that show them match the panel.
IMAGE_H = 72
HEIGHT = 69                      # rows the text may use
BORDER_ROWS = (10, 11, 1)        # rows 69, 70, 71
# glyph origin of the first line and line pitch: three lines use the original
# 16-pixel rows; text that needs a fourth line is set on 14-pixel rows. The DS
# font's glyphs reach from the cell's row 1 (quotes, apostrophes, brackets)
# to its row 14 (descenders, commas): on 14-pixel rows the next line's capitals
# and tall letters keep a clear row from the descenders, and only a quote or
# bracket right under a descender could touch it.
LAYOUTS = {3: (16, 16), 4: (12, 14)}
# No two lines (nor the name and the first line) may touch, not even corner
# to corner. Where the plain line breaks would, the lines sit on rows of 13
# to 15 pixels instead (the first from row 11 to 14, all of them within the
# red), the evenest first; then the lines break elsewhere (layout()).
FLEX_TOP = (12, 13, 11, 14)
FLEX_PITCH = (14, 13, 15)
# The DS sets these texts in its dialogue font, three lines across a
# 256-pixel panel; the GBA's panel is 149 pixels. Set at the text box's
# spacing (each letter a pixel after the last), with word spaces of 4, then
# of 3, on three lines, then the same on four: the first that fits.
# (space advance, added to every other advance)
SPACINGS = ((4, 0), (3, 0))
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
    # keep "2:00 PM", "Exhibit A" and "ID# 5842189" together
    s = re.sub(r'(\d) (AM|PM)\b', r'\1' + NBSP + r'\2', s)
    s = re.sub(r'\b(Oct|Dec) (\d)', r'\1' + NBSP + r'\2', s)
    s = s.replace('Photo #', 'Photo' + NBSP + '#')
    s = s.replace('ID# ', 'ID#' + NBSP)
    return re.sub(r'Exhibit ([A-Z])\b', 'Exhibit' + NBSP + r'\1', s)

@functools.lru_cache(None)
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

def rows(n):
    """where the n lines go (their glyph origins): the plain layout first,
    then (four lines) the others that stay within the red, the evenest first"""
    y0, pitch = LAYOUTS[n]
    plain = [y0 + pitch * k for k in range(n)]
    yield plain
    if n < 4:
        return
    flex = []
    for top in FLEX_TOP:
        for steps in itertools.product(FLEX_PITCH, repeat=n - 1):
            ys = [top + sum(steps[:k]) for k in range(n)]
            if ys != plain and ys[-1] + dsfont.ROWS - 2 < HEIGHT:
                flex.append(((len(set(steps)) > 1, sum(abs(p - pitch) for p in steps),
                              abs(top - y0)), ys))
    for _, ys in sorted(flex):
        yield ys

def _shift(m, dy, dx):
    p = np.pad(m, 1)
    return p[1 + dy:1 + dy + m.shape[0], 1 + dx:1 + dx + m.shape[1]]

def touching(lines, spacing, ys, name):
    """(pixels where a line meets the one above it, side by side or overlapping;
    pixels where they meet only corner to corner). The name is the line above
    the first. Text past the bottom counts as touching."""
    layers = [name]
    for l, y in zip(lines, ys):
        m = np.zeros(name.shape, bool)
        gy, gx = np.nonzero(render_line(l, spacing))
        if len(gy) and (gy + y).max() >= HEIGHT:
            return (1000, 0)
        m[gy + y, gx + TEXT_X] = True
        layers.append(m)
    edge = corner = 0
    for a, b in zip(layers, layers[1:]):
        e = a | _shift(a, 1, 0) | _shift(a, -1, 0) | _shift(a, 0, 1) | _shift(a, 0, -1)
        c = _shift(a, 1, 1) | _shift(a, 1, -1) | _shift(a, -1, 1) | _shift(a, -1, -1)
        edge += int((e & b).sum())
        corner += int((c & b & ~e).sum())
    return (edge, corner)

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

def layout(lines, name):
    """-> (lines, spacing, the lines' rows): the fewest lines, then the widest
    spacing, with nothing touching (touching(): not even corner to corner).
    The plain line breaks on the plain rows, else on the evenest other rows
    (rows()); else the evenest other line breaks, a pixel moved off the plain
    rows counting as 15 pixels short on a line"""
    text = join(lines)
    for n in sorted(LAYOUTS):    # the plain line breaks first
        for spacing in SPACINGS:
            out = wrap(text, spacing)
            if len(out) <= n and all(width(l, spacing) <= TEXT_W for l in out):
                for k, ys in enumerate(rows(n)):
                    if k > 0 and len(out) != n:
                        break
                    if touching(out, spacing, ys[:len(out)], name) == (0, 0):
                        return out, spacing, ys[:len(out)]
    def ragged(out, spacing):
        return sum((TEXT_W - width(l, spacing)) ** 2 for l in out[:-1])
    for n in sorted(LAYOUTS):
        plain = next(rows(n))
        for spacing in SPACINGS:
            good = []
            for out in wraps(text.split(' '), spacing, n):
                for k, ys in enumerate(rows(n)):
                    if k > 0 and len(out) != n:
                        break
                    ys = ys[:len(out)]
                    if touching(out, spacing, ys, name) == (0, 0):
                        moved = sum(abs(a - b) for a, b in zip(ys, plain))
                        good.append((ragged(out, spacing) + 225 * moved, out, ys))
            if good:
                _, out, ys = min(good)
                return out, spacing, ys
    raise ValueError('no layout without touching lines: ' + text)

def draw_text(a, lines, spacing, ys):
    for l, y in zip(lines, ys):
        put(a, render_line(l, spacing), TEXT_X, y, TEXT)

def put(a, mask, x0, y0, color):
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return
    assert (ys + y0).min() >= 0 and (ys + y0).max() < a.shape[0] and (xs + x0).max() < AREA_W
    a[ys + y0, xs + x0] = color

def canvas(base):
    """the 160x72 picture to draw on, from a Japanese one (160x64): the red
    down to row 68, then the panel's border; columns 152-159 stay as the
    Japanese pictures have them (transparent)"""
    a = np.zeros((IMAGE_H, base.width), np.uint8)
    a[:base.height] = np.array(base)
    a[base.height:, AREA_W:] = 0
    a[:HEIGHT, :AREA_W] = BG
    for k, c in enumerate(BORDER_ROWS):
        a[HEIGHT + k, :AREA_W] = c
    return a

def build(i, name_idx, age):
    path = os.path.join(ROOT, sym2file[table[i]] + '.png')
    if not os.path.exists(path + '.orig'):
        os.rename(path, path + '.orig')
    base = Image.open(path + '.orig')
    a = canvas(base)
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
        lines, spacing, ys = layout(ds_text.description(i), a == NAME)
        draw_text(a, lines, spacing, ys)
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
