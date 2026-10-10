#!/usr/bin/env python3
"""Check the English scripts for lines shown on a black screen.

On the GBA a fade to black (12, mode 2) darkens every layer, the text box and
its letters included, so a line printed before the fade back in (12, mode 1)
is read on a black screen. One of the wrong-evidence penalty scenes did this
("(Ugh. I must be on the wrong track?)", common script section 1B): an early
merge put the Japanese fade-out where the DS has a white flash, before the
line instead of after it.

Every section of every English script is compared with the same section of
the Japanese script, with the rule port_script.fix_dark uses when it ports a
section: a line printed while the screen is faded to black is an error when
the Japanese section never prints one in the dark, or when no fade-in comes
before the reader has to press on (page break, wait for A, end).

The Makefile runs this before the scripts are built into the ROM.
usage: check_scripts.py [JAPANESE_DIR ENGLISH_DIR]"""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phscr import load, section_bounds, tokens, parse, GBA_ARGS
from pdump import ch

FADE_IN, FADE_OUT = 1, 2
PRESS_ON = (0x02, 0x2D, 0x0D)          # page break, wait for A, end of section
TEXT_KEEPS = (0x01, 0x03, 0x0B, 0x0C)  # new line, colour, speed, wait: still the same line


def fades(items):
    return [(pos, a[0] >> 8) for pos, kind, op, a in items
            if kind == 'cmd' and op == 0x12 and a and a[0] >> 8 in (FADE_IN, FADE_OUT)]


def starts_dark(items):
    """the section fades in before its first line: it begins on a black screen"""
    for pos, kind, op, a in items:
        if kind == 'text':
            return False
        if kind == 'cmd' and op == 0x12 and a and a[0] >> 8 in (FADE_IN, FADE_OUT):
            return a[0] >> 8 == FADE_IN
    return False


def dark_lines(items, dark):
    """[(position, bad)] for each line that starts while faded to black; bad:
    the reader has to press on before the screen fades back in"""
    res, prev_text = [], False
    for q, (pos, kind, op, a) in enumerate(items):
        if kind == 'text':
            if dark and not prev_text:
                bad = True
                for pos2, kind2, op2, a2 in items[q:]:
                    if kind2 == 'cmd' and op2 in PRESS_ON:
                        break
                    if kind2 == 'cmd' and op2 == 0x12 and a2 and a2[0] >> 8 == FADE_IN:
                        bad = False
                        break
                res.append((pos, bad))
            prev_text = True
            continue
        if kind == 'cmd' and op == 0x12 and a:
            dark = {FADE_IN: False, FADE_OUT: True}.get(a[0] >> 8, dark)
        if not (kind == 'cmd' and op in TEXT_KEEPS):
            prev_text = False
    return res


def jump_records(b, S):
    """header entries used as jump records (by 35 and 36), not sections"""
    res = set()
    for x in S:
        if not x:
            continue
        for pos, kind, op, a in parse(tokens(b, *x), GBA_ARGS)[0]:
            if kind == 'cmd' and op == 0x35 and a[0] & 0x80:
                res.add(a[1])
            if kind == 'cmd' and op == 0x36:
                res.add(a[0])
    return res


def line_text(items, pos):
    out = []
    for p, kind, op, a in items:
        if p < pos:
            continue
        if kind != 'text':
            if kind == 'cmd' and op in PRESS_ON + (0x01,):
                break
            continue
        out.append(ch(op))
    return ''.join(out)[:40]


def check_file(jp_path, en_path):
    gb, gn, go = load(jp_path)
    G = section_bounds(gb, go)
    eb, en, eo = load(en_path)
    if en != gn:
        return ['%s: %d sections, the Japanese has %d' % (en_path, en, gn)]
    skip = jump_records(gb, G)
    real = sorted(set(eo[i] for i in range(gn) if G[i] and i not in skip and eo[i] < len(eb))) + [len(eb)]
    errors = []
    for i in range(gn):
        if not G[i] or i in skip or eo[i] >= len(eb):
            continue
        gi = parse(tokens(gb, *G[i]), GBA_ARGS)[0]
        ei = parse(tokens(eb, eo[i], real[real.index(eo[i]) + 1]), GBA_ARGS)[0]
        start = starts_dark(gi)
        jp_dark = dark_lines(gi, start)
        for pos, bad in dark_lines(ei, start):
            if bad or not jp_dark:
                errors.append('%s section %d (0x%X): line shown on a black screen: "%s"'
                              % (os.path.basename(en_path), i, i, line_text(ei, pos)))
    return errors


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    jp_dir, en_dir = sys.argv[1:3] if len(sys.argv) > 2 else (os.path.join(root, 'script'), os.path.join(root, 'script_en'))
    errors, n = [], 0
    for en_path in sorted(glob.glob(os.path.join(en_dir, '*.phscr'))):
        jp_path = os.path.join(jp_dir, os.path.basename(en_path))
        if not os.path.exists(jp_path):
            continue
        errors += check_file(jp_path, en_path)
        n += 1
    if not n:
        errors.append('no scripts found in %s' % en_dir)
    for e in errors:
        print('error: ' + e, file=sys.stderr)
    if errors:
        print('script check failed: %d problem(s)' % len(errors), file=sys.stderr)
        return 1
    print('script check: %d scripts, no line shown on a black screen' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
