#!/usr/bin/env python3
"""Port the common script (save prompts, chapter titles, generic courtroom
penalties) from the English DS common script (last entry of mes_all.bin).

The DS added one section ("Load failed", 7) and the fifth episode's titles
(25-42), so the sections are paired explicitly.
usage: port_std.py GBA_std_scripts.phscr DS_mes_all.bin OUT.phscr"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(__file__))
import port_script
from dsdata import lz10

def ds_std(mes_all):
    d = open(mes_all, 'rb').read()
    n = struct.unpack_from('<I', d, 0)[0]
    o, s = struct.unpack_from('<II', d, 4 + 8 * (n - 1))   # English common script
    return lz10(d, o)

PAIRS = {i: i for i in range(7)}
PAIRS.update({i: i + 1 for i in range(7, 24)})     # chapter titles
PAIRS.update({24: 43, 25: 44, 26: 45, 27: 46, 28: 47, 29: 48, 30: 49})

# The Japanese text was centred with leading spaces. The save, erase and
# load messages are now drawn on the DS plate, which centres each line itself
# (en_menu.c / vwf.c); "Select an episode." and the new-episode notice
# (sections 2 and 5) are still drawn at x=9 in a box spanning x=27..216, so
# those lines are centred here. The DS's own centre command (5D) is left
# out of every section: the plates centre without it, and with it the
# padded lines would be centred twice.
WIDTHS = open(os.path.join(os.path.dirname(__file__), '..', '..', 'graphics/vwf/font_widths.bin'), 'rb').read()
ADVANCE = open(os.path.join(os.path.dirname(__file__), '..', '..', 'graphics/vwf/font_advance.bin'), 'rb').read()
BOX_CENTRE, TEXT_X = 121, 9
SPACE = ADVANCE[0xFF]
CENTRE = 0x5D                      # the DS's centre command (port_script.CENTRE)

def centre(ds, sections):
    from phscr import section_bounds, tokens, parse
    ds_args = port_script.DS_ARGS
    n = struct.unpack_from('<I', ds, 0)[0]
    offs = list(struct.unpack_from('<%dI' % n, ds, 4))
    S = section_bounds(ds, offs)
    out_secs = []
    for i, x in enumerate(S):
        toks = list(tokens(ds, *x)) if x else []
        if x and i in sections:
            items, _ = parse(toks, ds_args)
            new, line_start, width, pen = [], None, 0, 0
            def flush():
                if line_start is not None and width:
                    # the line starts at its first character
                    pad = max(0, round((BOX_CENTRE - TEXT_X - width / 2) / SPACE))
                    new[line_start:line_start] = [0x17F] * pad
            line_start = None
            for pos, kind, op, args in items:
                if kind == 'text':
                    if line_start is None:
                        line_start = len(new)
                    c = op - 0x80
                    if c != 0xFF:
                        width = max(width, pen + WIDTHS[c])
                    pen += ADVANCE[c]
                    new.append(op)
                else:
                    if op == 0x01:
                        flush(); width = pen = 0
                        new.append(op); new.extend(args)
                        line_start = None
                        continue
                    if op == CENTRE:
                        continue
                    new.append(op); new.extend(args)
            flush()
            toks = new
        elif x:
            # the DS centres its plate lines with 5D; the plates here centre
            # each line themselves (en_menu.c EnMenuLineStart), and the box
            # lines above are centred with spaces, which 5D would centre again
            items, _ = parse(toks, ds_args)
            new = []
            for pos, kind, op, args in items:
                if kind == 'text':
                    new.append(op)
                elif op != CENTRE:
                    new.append(op); new.extend(args)
            toks = new
        out_secs.append(toks)
    body = bytearray(); newoffs = []
    base = 4 + 4 * n
    for t in out_secs:
        newoffs.append(base + len(body))
        body += struct.pack('<%dH' % len(t), *t)
        if len(body) % 4: body += b'\0\0'
    return struct.pack('<I', n) + struct.pack('<%dI' % n, *newoffs) + bytes(body)

# The GBA colours a word or two of the plate messages blue (command 03, 2): the
# DS Japanese kept them, the DS English dropped them. Put them back on the
# English words that say the same (the Japanese words in brackets).
BLUE = {0: ['Save'],                              # 保存
        1: ['Save', 'suspend'],                   # 保存, 中断
        4: ['Erase', 'default settings'],         # 消去, 初期状態
        6: ['Suspending']}                        # 中断
COLOUR, BLUE_COLOUR, NO_COLOUR = 0x03, 2, 0

def encode(word):
    out = []
    for ch in word:
        if 'A' <= ch <= 'Z': out.append(0x8A + ord(ch) - 65)
        elif 'a' <= ch <= 'z': out.append(0xA4 + ord(ch) - 97)
        elif ch == ' ': out.append(0x17F)
        else: raise ValueError(ch)
    return out

def colour_words(path, spec):
    from phscr import section_bounds, tokens, parse, GBA_ARGS
    b = open(path, 'rb').read()
    n = struct.unpack_from('<I', b, 0)[0]
    offs = list(struct.unpack_from('<%dI' % n, b, 4))
    S = section_bounds(b, offs)
    out_secs = []
    for i, x in enumerate(S):
        toks = tokens(b, *x) if x else []
        for word in spec.get(i, []):
            w = encode(word)
            # find the word as text (not inside a command's arguments)
            items, _ = parse(toks, GBA_ARGS)
            starts = [pos for pos, kind, op, a in items if kind == 'text']
            hits = [k for k in starts if toks[k:k + len(w)] == w]
            assert len(hits) == 1, (i, word, hits)
            k = hits[0]
            toks = toks[:k] + [COLOUR, BLUE_COLOUR] + w + [COLOUR, NO_COLOUR] + toks[k + len(w):]
        out_secs.append(toks)
    body = bytearray(); newoffs = []
    base = 4 + 4 * n
    for t in out_secs:
        newoffs.append(base + len(body))
        body += struct.pack('<%dH' % len(t), *t)
        if len(body) % 4: body += b'\0\0'
    open(path, 'wb').write(struct.pack('<I', n) + struct.pack('<%dI' % n, *newoffs) + bytes(body))

if __name__ == '__main__':
    gfile, mes_all, out = sys.argv[1:4]
    tmp = out + '.ds'
    open(tmp, 'wb').write(centre(ds_std(mes_all), {2, 5}))
    t, k = port_script.port(gfile, tmp, out, out + '.report.txt', None, PAIRS)
    os.remove(tmp)
    colour_words(out, BLUE)
    print('std: %d sections, %d left in Japanese' % (t, k))
