#!/usr/bin/env python3
"""The text box's line layout: which lines of a page move a pixel or two.

The text box's lines are 14 pixels apart, and the DS font's glyphs reach from
row 1 of their 16-row cell (quotes, apostrophes, brackets) to row 14
(descenders, commas): where a descender or comma sits right above a quote,
apostrophe or bracket of the line below, the two touch ("girl" over
"where'd"). Each page's lines are looked at, and a line moves a pixel or two
so that no two lines touch, not even corner to corner:

- offsets tried: the first line 0 or -1, the middle line 0, +1, -1, +2, -2
  (0, +1, +2 when it is the last line), the third line 0 or +1, in that order;
- the first that touches nowhere and is cheapest: first the fewest lines
  against the box's frame (a pixel above row 1 of the first line or below row
  14 of the third, the rows the text keeps clear of the frame), then the
  fewest pixels moved, then the fewest lines moved;
- nothing touches without moving: nothing moves (99% of the pages); nothing
  works: nothing moves either.

A page is looked at from the character that starts its first line (when no
line above it shows) to its end: a page break, a choice, the end of the
section, a jump; a centring command (5D) applies to the lines started after
it. The pages with a line to move are listed by where they start, with the
moves for the page started with the centring off and with it on
(graphics/vwf/page_moves.bin, the Makefile makes it with this), and the game
gives a page that starts there its lines' moves (vwf.c VwfLineStarts);
check_scripts.py checks that no page's lines touch.

usage: text_gaps.py OUT.bin SCRIPT.phscr..."""
import os, sys, struct, itertools
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
_G = open(os.path.join(ROOT, 'graphics', 'vwf', 'font_glyphs.bin'), 'rb').read()
WIDTHS = open(os.path.join(ROOT, 'graphics', 'vwf', 'font_widths.bin'), 'rb').read()
ADVANCE = open(os.path.join(ROOT, 'graphics', 'vwf', 'font_advance.bin'), 'rb').read()
GLYPH_COUNT = len(WIDTHS)            # VWF_GLYPH_COUNT
SPACE = 0xFF                         # VWF_SPACE
ROWS = 16                            # VWF_GLYPH_ROWS
LINE_HEIGHT = 14                     # VWF_LINE_HEIGHT
LINES = 3                            # VWF_LINES
LINE_PIXELS = 256                    # VWF_LINE_PIXELS (the buffer; the text uses 224)
TEXT_X = 9                           # VWF_TEXT_X
TOP_ROW, BOTTOM_ROW = 1, 14          # the rows the text keeps clear of the frame
# script commands' arguments (tools/en/phscr.py)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phscr import GBA_ARGS, load, section_bounds, tokens
# vwf.c sCmdArgs (VwfCentredLineStart): the arguments of 00-5F (0 for the unused 4D-5C)
SCRIPT_ARGS = [GBA_ARGS.get(t, 0) for t in range(0x60)]
# what ends a page: a page break, a choice, the end of the section, a jump
# (a command not known ends it too)
PAGE_ENDS = {0x00, 0x02, 0x07, 0x08, 0x09, 0x0A, 0x0D, 0x2C, 0x2D, 0x2E, 0x15, 0x35, 0x36}
CENTRE = 0x5D
OFFSETS_FIRST = (0, -1)
OFFSETS_MIDDLE = (0, 1, -1, 2, -2)
OFFSETS_MIDDLE_LAST = (0, 1, 2)
OFFSETS_LAST = (0, 1)

_glyphs = {}
def glyph(c):
    """the code's pixels, 16 x 16 (False where nothing is drawn)"""
    if c not in _glyphs:
        a = np.zeros((ROWS, 16), bool)
        if c != SPACE and c < GLYPH_COUNT:
            for y in range(ROWS):
                for x in range(WIDTHS[c]):
                    v = _G[c * 128 + y * 8 + (x >> 1)]
                    if (v >> 4) if x & 1 else (v & 15):
                        a[y, x] = True
        _glyphs[c] = a
    return _glyphs[c]

def code(token):
    c = token - 0x80
    return c if c < GLYPH_COUNT else SPACE

CENTRE_STOPS = {0x00, 0x01, 0x02, 0x07, 0x08, 0x09, 0x0A, 0x0D, 0x15, 0x2D, 0x2E, 0x35, 0x36}

def centred_start(tokens, p, xoff):
    """where a centred line starting at tokens[p] starts (VwfCentredLineStart):
    the pen's moves to the line's end, but for the last character only its
    pixels; codes past the font count as nothing; the line ends at a line or
    page break, a jump or any command from 5D on"""
    w = tail = 0
    while p < len(tokens):
        t = tokens[p]
        if t >= 0x80:
            c = t - 0x80
            if c < GLYPH_COUNT:
                w += tail
                tail = ADVANCE[c]
                if c != SPACE:
                    w += WIDTHS[c]
                    tail -= WIDTHS[c]
            p += 1
            continue
        if t in CENTRE_STOPS or t >= 0x5D:
            break
        p += 1 + SCRIPT_ARGS[t]
    x = (120 - xoff) - w // 2
    return x if x > 0 else 0

def page_ahead(tokens, start, line, centre, xoff):
    """the page from tokens[start] (a character starting line `line`) to its
    end: {line: (codes, start pen)}"""
    lines = {}
    cur = line
    p = start
    while p < len(tokens):
        t = tokens[p]
        if t >= 0x80:
            if cur >= LINES:
                break
            if cur not in lines:
                lines[cur] = ([], centred_start(tokens, p, xoff) if centre else 0)
            lines[cur][0].append(code(t))
            p += 1
            continue
        if t in PAGE_ENDS or t not in GBA_ARGS:
            break
        if t == 0x01:
            cur += 1
        elif t == CENTRE:
            centre = 1 if tokens[p + 1] else 0
        elif t == 0x48:
            xoff = TEXT_X if tokens[p + 1] == 0xFFFF else tokens[p + 1]
        p += 1 + GBA_ARGS[t]
    return lines

def pixels(codes, pen):
    """the line as drawn from pen (VwfDrawChar): a ROWS x LINE_PIXELS mask"""
    a = np.zeros((ROWS, LINE_PIXELS + 16), bool)
    for c in codes:
        if c == SPACE:
            pen += ADVANCE[c]
            continue
        w = WIDTHS[c]
        if pen + w > LINE_PIXELS:
            continue                         # (the game drops it)
        a[:, pen:pen + 16] |= glyph(c)
        pen += ADVANCE[c]
    return a[:, :LINE_PIXELS]

def _near(a):
    p = np.pad(a, 1)
    o = np.zeros_like(a)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            o |= p[1 + dy:1 + dy + a.shape[0], 1 + dx:1 + dx + a.shape[1]]
    return o

def touch(upper, lower, d):
    """does `lower`, drawn d rows below `upper`, touch it (8 neighbours)"""
    if d >= ROWS + 1:
        return False
    h = ROWS + d + 1
    a = np.zeros((h, upper.shape[1]), bool); b = np.zeros_like(a)
    a[:ROWS] = upper
    b[d:d + ROWS] = lower
    return bool((_near(a) & b).any())

def offsets(lines):
    """{line: offset} for the page ahead (page_ahead)"""
    masks = {l: pixels(*lines[l]) for l in lines}
    masks = {l: m for l, m in masks.items() if m.any()}
    if len(masks) < 2:
        return {l: 0 for l in range(LINES)}
    if not any(k in masks and k + 1 in masks and touch(masks[k], masks[k + 1], LINE_HEIGHT)
               for k in range(LINES - 1)):
        return {l: 0 for l in range(LINES)}      # (nothing touches: as the cheapest would be)
    last = max(masks)
    choices = [OFFSETS_FIRST, OFFSETS_MIDDLE_LAST if last == 1 else OFFSETS_MIDDLE, OFFSETS_LAST]
    best = None
    for o in itertools.product(*choices):
        bad = False
        for k in range(LINES - 1):
            if k in masks and k + 1 in masks and \
               touch(masks[k], masks[k + 1], LINE_HEIGHT + o[k + 1] - o[k]):
                bad = True
                break
        if bad:
            continue
        frame = 0
        if 0 in masks and np.nonzero(masks[0].any(1))[0].min() + o[0] < TOP_ROW:
            frame += 1
        if 2 in masks and np.nonzero(masks[2].any(1))[0].max() + o[2] > BOTTOM_ROW:
            frame += 1
        cost = (frame, sum(abs(x) for x in o), sum(1 for x in o if x))
        if best is None or cost < best[0]:
            best = (cost, o)
    if best is None or best[1] == (0, 0, 0):
        return {l: 0 for l in range(LINES)}
    return dict(enumerate(best[1]))

def page_starts(tokens):
    """[(position, line, centre, text x offset)] of every character the game
    starts a page's layout on: the first character of a line when no line
    above it shows; and the centring left on at the section's end"""
    out = []
    shown = set()            # lines with something drawn on them this page
    x = 0; y = 0; centre = 0; xoff = TEXT_X
    p = 0
    while p < len(tokens):
        t = tokens[p]
        if t >= 0x80:
            if x == 0 and not any(l < y for l in shown):
                out.append((p, y, centre, xoff))
            if code(t) != SPACE:
                shown.add(min(y, LINES - 1))
            x += 1
            p += 1
            continue
        if t not in GBA_ARGS:
            p += 1
            continue
        if t == 0x01:
            x = 0; y += 1
        elif t in (0x00, 0x02, 0x07, 0x08, 0x09, 0x0A, 0x0D, 0x2C, 0x2D, 0x2E):
            x = 0; y = 0; shown = set()
        elif t == CENTRE:
            centre = 1 if tokens[p + 1] else 0
        elif t == 0x48:
            xoff = TEXT_X if tokens[p + 1] == 0xFFFF else tokens[p + 1]
        p += 1 + GBA_ARGS[t]
    return out, centre

def page_layouts(tokens):
    """[(position, line, lines ahead, offsets)] for a section's tokens"""
    res = []
    starts, _ = page_starts(tokens)
    for p, line, centre, xoff in starts:
        ahead = page_ahead(tokens, p, line, centre, xoff)
        res.append((p, line, ahead, offsets(ahead)))
    return res

def touching(ahead, offs):
    """pairs of lines still touching with these offsets"""
    masks = {l: pixels(*ahead[l]) for l in ahead}
    return [k for k in range(LINES - 1) if k in masks and k + 1 in masks and masks[k].any() and masks[k + 1].any()
            and touch(masks[k], masks[k + 1], LINE_HEIGHT + offs[k + 1] - offs[k])]

# the scripts' numbers in the list (vwf.c VwfScriptNumber): the chapters' in
# gScriptTable's order (script_main.c), then the fifth episode's (en_rfta.c
# gRftaScriptTable, chapters 17-35); the common script 62, the Rise from the
# Ashes build's 63
SCRIPTS = ['scenario_0_script'] + ['scenario_%d_%d_script' % (c, k) for c, n in ((1, 4), (2, 6), (3, 6)) for k in range(n)] + \
          ['scenario_5_%02d_script' % k for k in range(19)]
STD, STD_RFTA = 62, 63

def script_number(path):
    name = os.path.basename(path)[:-len('.phscr')]
    if name == 'std_scripts':
        return STD_RFTA if os.path.basename(os.path.dirname(os.path.abspath(path))) == 'script_rfta' else STD
    return SCRIPTS.index(name)

def page_moves(paths):
    """{script number << 20 | the byte a page's first character is at: its
    lines' moves with the centring off at the page's start, and on} for the
    pages with a line to move either way (the centring a section starts with
    is the one the section before left: a page that starts centred where the
    scripts would not have it still takes the moves that fit it)"""
    moves = {}
    for path in paths:
        n = script_number(path)
        b, _, offs = load(path)
        assert len(b) <= 1 << 20, path
        for x in section_bounds(b, offs):
            if not x:
                continue
            t = tokens(b, *x)
            starts, _ = page_starts(t)
            for p, line, centre, xoff in starts:
                m = []
                for c in (0, 1):
                    o = offsets(page_ahead(t, p, line, c, xoff))
                    m.append((o[0], o[1], o[2]))
                if any(m[0]) or any(m[1]):
                    at = n << 20 | (x[0] + 2 * p)
                    assert moves.setdefault(at, tuple(m)) == tuple(m)
    return moves

if __name__ == '__main__':
    moves = page_moves(sys.argv[2:])
    open(sys.argv[1], 'wb').write(b''.join(struct.pack('<I3b3bxx', at, *(moves[at][0] + moves[at][1])) for at in sorted(moves)))
    print('%s: %d pages with a line moved' % (sys.argv[1], len(moves)))
