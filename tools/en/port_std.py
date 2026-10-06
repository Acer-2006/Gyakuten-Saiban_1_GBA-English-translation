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
# those lines are centred here.
WIDTHS = open(os.path.join(os.path.dirname(__file__), '..', '..', 'graphics/vwf/font_widths.bin'), 'rb').read()
BOX_CENTRE, TEXT_X, SPACE = 121, 9, 4

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
            new, line_start, width = [], None, 0
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
                    width += SPACE if c == 0xFF else WIDTHS[c] + 1
                    new.append(op)
                else:
                    if op == 0x01:
                        flush(); width = 0
                        new.append(op); new.extend(args)
                        line_start = None
                        continue
                    new.append(op); new.extend(args)
            flush()
            toks = new
        out_secs.append(toks)
    body = bytearray(); newoffs = []
    base = 4 + 4 * n
    for t in out_secs:
        newoffs.append(base + len(body))
        body += struct.pack('<%dH' % len(t), *t)
        if len(body) % 4: body += b'\0\0'
    return struct.pack('<I', n) + struct.pack('<%dI' % n, *newoffs) + bytes(body)

if __name__ == '__main__':
    gfile, mes_all, out = sys.argv[1:4]
    tmp = out + '.ds'
    open(tmp, 'wb').write(centre(ds_std(mes_all), {2, 5}))
    t, k = port_script.port(gfile, tmp, out, out + '.report.txt', None, PAIRS)
    os.remove(tmp)
    print('std: %d sections, %d left in Japanese' % (t, k))
