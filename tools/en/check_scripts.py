#!/usr/bin/env python3
"""Check the English scripts against the Japanese ones before they are built.

Every section of every English script is compared with the same section of
the Japanese script (the English scripts keep the Japanese sections):

- No line on a black screen. On the GBA a fade to black (12, mode 2) darkens
  every layer, the text box and its letters included, so a line printed before
  the fade back in (12, mode 1) is read on a black screen. One of the
  wrong-evidence penalty scenes did this ("(Ugh. I must be on the wrong
  track?)", common script section 1B). The rule is port_script.fix_dark's: a
  line printed while faded to black is an error when the Japanese section
  never prints one in the dark, or when no fade-in comes before the reader
  has to press on (page break, wait for A, end).
- The same penalties (2B). "Oh. Whoops. Wrong evidence." (Turnabout Goodbyes,
  day 2) took two marks: the DS's penalty and the Japanese one were both kept.
- The same branches: a choice (08 / 09) offers the same answers' sections (in
  any order: the DS orders some answers differently), and the jumps that end
  a section (0A, 2C, 20, 2A) go to the same sections.
- Jumps that land: a jump in the section (35) on a command, a jump record
  (35 / 36) on a command of an existing section, a section number on an
  existing section.
- Lines that fit: no line wider than the 224 pixels of the text box, no page
  whose text reaches a fourth line (the engine draws it into the third: the
  Gourd Lake map scene had "searchingfor something." when a DS command's
  second argument was read as a line break), no third line reaching the
  "next" arrow at the line's right end (the DS's, from 227 px: a third line
  may be 217 px wide; the widest is 188).
- No wait for A with the text box hidden (nothing to read, no arrow) where
  the Japanese section has none: after "(Maybe I should just listen to the
  testimony again.)" the Japanese wait-and-jump had been kept after the DS's
  box hide and fade.
- No pose drawn further down the screen than the Japanese section draws that
  person there (pose_bottoms.json), where all of those end above the bottom
  (a desk, the witness stand, the visitor's room counter): Maya's sad
  talking pose came down over the counter in Turnabout Sisters (issue 5).
  A pose the Japanese game shows with those on the same background
  elsewhere is fine (Phoenix's desk slam at the defense bench).
- Every fade to black (12, mode 2) followed by its wait, as all 878 of the
  Japanese script's are (port_script.fix_fade_waits): without it the next
  background showed before the fade (Phoenix over the floor plans).
- No thought (blue text) typed while the person shown is talking where the
  Japanese section has none (port_script.thought_mouths): Phoenix's mouth
  moved through "(For once...)".

The Makefile runs this before the scripts are built into the ROM.
usage: check_scripts.py [JAPANESE_DIR ENGLISH_DIR]"""
import os, sys, glob, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phscr import load, section_bounds, tokens, parse, GBA_ARGS
from pdump import ch
from port_script import FADE_OUT_WAITS, thought_mouths

FADE_IN, FADE_OUT = 1, 2
PRESS_ON = (0x02, 0x2D, 0x0D)          # page break, wait for A, end of section
TEXT_KEEPS = (0x01, 0x03, 0x0B, 0x0C)  # new line, colour, speed, wait: still the same line
CHOICES = {0x08: 2, 0x09: 3}           # answers' sections: the first 2 / 3 arguments
JUMPS = {0x0A: (0,), 0x2C: (0,), 0x20: (0,), 0x2A: (1, 2)}   # section arguments
LINE_PIXELS = 224                      # vwf.h: 8 x 32 px blocks, 224 px used
THIRD_LINE_PIXELS = 217                # the "next" arrow (bg.c TextboxNextArrow) starts 227 px in, the text 9 px in
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
WIDTHS = open(os.path.join(ROOT, 'graphics', 'vwf', 'font_widths.bin'), 'rb').read()     # columns with pixels
ADVANCE = open(os.path.join(ROOT, 'graphics', 'vwf', 'font_advance.bin'), 'rb').read()   # the pen's move


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


def penalties(items):
    return sum(1 for p, k, op, a in items if k == 'cmd' and op == 0x2B)


def branches(items):
    """(answers' sections of each choice, as sets; sections the section's jumps go to)"""
    ch_, jm = [], collections.Counter()
    for p, k, op, a in items:
        if k != 'cmd':
            continue
        if op in CHOICES:
            ch_.append(tuple(sorted(a[:CHOICES[op]])))
        elif op in JUMPS:
            for j in JUMPS[op]:
                jm[a[j]] += 1
    return sorted(ch_), jm


def wide_lines(items):
    """[(pixels, text, limit)] for lines wider than the text box, and third
    lines (of a page the arrow waits on) reaching the "next" arrow"""
    res, pen, w, s, y = [], 0, 0, '', 0
    for p, k, op, a in items + [(None, 'cmd', 0x01, ())]:
        if k == 'text':
            c = op - 0x80
            if c >= len(WIDTHS):
                w = pen + 99
            elif c != 0xFF:
                w = max(w, pen + WIDTHS[c])     # where the line's pixels end
            pen += ADVANCE[c] if c < len(ADVANCE) else 99
            s += ch(op)
        elif k == 'cmd' and op in (0x01, 0x02, 0x07, 0x08, 0x09, 0x0A, 0x0D, 0x2D, 0x2E):
            limit = THIRD_LINE_PIXELS if y == 2 and op in (0x02, 0x0A, 0x2D) else LINE_PIXELS
            if w > limit:
                res.append((w, s, limit))
            pen, w, s = 0, 0, ''
            y = y + 1 if op == 0x01 else 0
    return res


def fourth_lines(items):
    """[text] of pages whose text reaches a fourth line"""
    res, y, intext, s = [], 0, False, ''
    for p, k, op, a in items:
        if k == 'text':
            if y >= 3 and not intext:
                res.append(s[-40:])
            intext = True; s += ch(op); continue
        intext = False
        if k == 'cmd' and op == 0x01:
            y += 1; s += '/'
        elif k == 'cmd' and op in PRESS_ON + (0x07, 0x0A, 0x2C, 0x2E, 0x08, 0x09, 0x00):
            y = 0; s = ''
    return res


def hidden_waits(items):
    """waits for A (02/07/0A/2D) reached with the text box hidden"""
    res, box, s = [], True, ''
    for p, k, op, a in items:
        if k == 'text':
            s = (s + ch(op))[-40:]; continue
        if k != 'cmd':
            continue
        if op == 0x1C and a and a[0] in (0, 1):
            box = a[0] == 0
        if op in (0x02, 0x07, 0x0A, 0x2D):
            if not box:
                res.append(s)
            s = ''
    return res


POSE_SHOWN = (0x02, 0x2D, 0x2E, 0x15, 0x0C)   # text starts, waits: the pose is on screen
DESK_ROW = 150                                 # poses that end above this stop at something in front
POSE_SLACK = 4
_BOTTOMS = None


def bottoms():
    """(person, animation) -> the lowest row it draws (pose_bottoms.json)"""
    global _BOTTOMS
    if _BOTTOMS is None:
        import json
        d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pose_bottoms.json')))['bottoms']
        _BOTTOMS = {(int(p, 16), int(a, 16)): v[1] for p, x in d.items() for a, v in x.items()}
    return _BOTTOMS


def pose_events(items):
    """(background or None, person, talking, idle) each time a pose is shown"""
    bg = cur = None
    intext = False
    for pos, kind, op, a in items:
        shown = (kind == 'text' and not intext) or (kind == 'cmd' and op in POSE_SHOWN)
        if shown and cur and cur[0]:
            yield bg, cur[0], cur[1], cur[2]
        if kind == 'text':
            intext = True
            continue
        if op not in TEXT_KEEPS:
            intext = False
        if op == 0x1B and a:
            bg = a[0] & 0x7FFF
        elif op == 0x1E and a:
            cur = (a[0] & 0xFF, a[1], a[2])


def section_poses(items):
    """(background, person) -> the poses the section shows"""
    res = collections.defaultdict(set)
    for bg, p, t, i in pose_events(items):
        res[(bg, p)].update((t, i))
    return res


def low_poses(ei, gi, together):
    """poses drawn lower than any the Japanese section shows the person in
    there, where those all end above the bottom of the screen (together:
    (background, person, pose) -> the poses the Japanese game shows with it)"""
    b, ref, res = bottoms(), section_poses(gi), []
    for bg, p, t, i in pose_events(ei):
        r = ref.get((bg, p))
        rb = [b[(p, x)] for x in r or () if (p, x) in b]
        if not rb or max(rb) >= DESK_ROW:
            continue
        for g in (t, i):
            if g in r or (p, g) not in b or b[(p, g)] <= max(rb) + POSE_SLACK:
                continue
            if bg is not None and together.get((bg, p, g), set()) & r:
                continue
            res.append('person %X pose %X drawn to row %d, the Japanese here to %d' % (p, g, b[(p, g)], max(rb)))
    return sorted(set(res))


def fades_without_wait(items):
    """fades to black (12, mode 2) not followed by their wait"""
    res = 0
    for k, (pos, kind, op, a) in enumerate(items):
        if kind == 'cmd' and op == 0x12 and a and a[0] >> 8 == FADE_OUT and a[1] and (a[0] & 0xFF) in FADE_OUT_WAITS:
            nxt = items[k + 1] if k + 1 < len(items) else None
            if nxt is None or nxt[1] != 'cmd' or nxt[2] != 0x0C:
                res += 1
    return res


def bad_jumps(b, n, offs, sec_items, here):
    """jumps of section `here` that land nowhere"""
    res = []
    def lands(sec, tok):
        it = sec_items.get(sec)
        return it is not None and any(p == tok for p, k, op, a in it)
    for p, k, op, a in sec_items[here]:
        if k == 'bad':
            res.append('unknown command %X' % op)
        if k != 'cmd':
            continue
        if op == 0x35 and not a[0] & 0x80 and not lands(here, a[1] // 2):
            res.append('jump (35) to token %d, not a command' % (a[1] // 2))
        if (op == 0x35 and a[0] & 0x80) or op == 0x36:
            r = a[1] if op == 0x35 else a[0]
            if 4 + 4 * r + 4 > len(b):
                res.append('jump record %d missing' % r)
                continue
            off, sec = struct.unpack_from('<HH', b, 4 + 4 * r)
            if not lands(sec, off // 2):
                res.append('jump record %d to section %X token %d, not a command' % (r, sec + 0x80, off // 2))
        for j in list(JUMPS.get(op, ())) + list(range(CHOICES.get(op, 0))):
            v = a[j]
            if 0x80 <= v < 0xFFFF and (v - 0x80) not in sec_items:
                res.append('%X to section %X, which does not exist' % (op, v))
    return res


def check_file(jp_path, en_path, together):
    gb, gn, go = load(jp_path)
    G = section_bounds(gb, go)
    eb, en, eo = load(en_path)
    name = os.path.basename(en_path)
    if en != gn:
        return ['%s: %d sections, the Japanese has %d' % (name, en, gn)]
    skip = jump_records(gb, G)
    real = sorted(set(eo[i] for i in range(gn) if G[i] and i not in skip and eo[i] < len(eb))) + [len(eb)]
    std = name.startswith('std')
    errors = []
    en_items, en_toks = {}, {}
    for i in range(gn):
        if G[i] and i not in skip and eo[i] < len(eb):
            en_toks[i] = tokens(eb, eo[i], real[real.index(eo[i]) + 1])
            en_items[i] = parse(en_toks[i], GBA_ARGS)[0]
    for i in range(gn):
        if i not in en_items:
            continue
        where = '%s section 0x%X' % (name, i if std else i + 0x80)
        gi = parse(tokens(gb, *G[i]), GBA_ARGS)[0]
        ei = en_items[i]
        start = starts_dark(gi)
        jp_dark = dark_lines(gi, start)
        for pos, bad in dark_lines(ei, start):
            if bad or not jp_dark:
                errors.append('%s: line shown on a black screen: "%s"' % (where, line_text(ei, pos)))
        if penalties(ei) != penalties(gi):
            errors.append('%s: %d penalties, the Japanese has %d' % (where, penalties(ei), penalties(gi)))
        ec, ej = branches(ei)
        gc, gj = branches(gi)
        if ec != gc:
            errors.append('%s: choices lead to %s, the Japanese to %s' % (where, [[hex(x) for x in c] for c in ec],
                                                                         [[hex(x) for x in c] for c in gc]))
        if ej != gj:
            errors.append('%s: jumps to %s, the Japanese to %s' % (where, sorted(hex(x) for x in ej.elements()),
                                                                 sorted(hex(x) for x in gj.elements())))
        for e in bad_jumps(eb, gn, eo, en_items, i):
            errors.append('%s: %s' % (where, e))
        for w, s, limit in wide_lines(ei):
            errors.append('%s: line %d pixels wide (%s): "%s"' % (where, w, 'the box has %d' % limit if limit == LINE_PIXELS
                                                                 else 'a third line has %d before the arrow' % limit, s))
        for s in fourth_lines(ei):
            errors.append('%s: text on a fourth line: "%s"' % (where, s))
        eh, gh = hidden_waits(ei), hidden_waits(gi)
        if len(eh) > len(gh):
            errors.append('%s: wait for A with the text box hidden (the Japanese has %d such): after "%s"' % (where, len(gh), eh[-1]))
        for e in low_poses(ei, gi, together):
            errors.append('%s: %s' % (where, e))
        n = fades_without_wait(ei)
        if n > fades_without_wait(gi):
            errors.append('%s: %d fades to black without their wait' % (where, n))
        if thought_mouths(en_toks[i]) and not thought_mouths(tokens(gb, *G[i])):
            errors.append('%s: a thought typed while the person shown is talking' % where)
    return errors


def poses_together(jp_dir):
    """(background, person, pose) -> the poses the Japanese game shows with
    that pose in a section, on that background"""
    res = collections.defaultdict(set)
    for path in glob.glob(os.path.join(jp_dir, '*.phscr')):
        b, n, offs = load(path)
        for x in section_bounds(b, offs):
            if x:
                for (bg, p), poses in section_poses(parse(tokens(b, *x), GBA_ARGS)[0]).items():
                    if bg is not None:
                        for g in poses:
                            res[(bg, p, g)] |= poses
    return res


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    jp_dir, en_dir = sys.argv[1:3] if len(sys.argv) > 2 else (os.path.join(root, 'script'), os.path.join(root, 'script_en'))
    errors, n = [], 0
    together = poses_together(jp_dir)
    for en_path in sorted(glob.glob(os.path.join(en_dir, '*.phscr'))):
        jp_path = os.path.join(jp_dir, os.path.basename(en_path))
        if not os.path.exists(jp_path):
            continue
        errors += check_file(jp_path, en_path, together)
        n += 1
    if not n:
        errors.append('no scripts found in %s' % en_dir)
    for e in errors:
        print('error: ' + e, file=sys.stderr)
    if errors:
        print('script check failed: %d problem(s)' % len(errors), file=sys.stderr)
        return 1
    print('script check: %d scripts: no line on a black screen, penalties and branches as in the '
          'Japanese game, every jump lands, every line fits (third lines clear of the arrow), no fourth line, '
          'no wait on a hidden box, no pose over a desk, every fade with its wait, no mouth moving through a '
          'thought' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
