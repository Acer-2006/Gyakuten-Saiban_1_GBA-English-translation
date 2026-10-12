#!/usr/bin/env python3
"""The common script of the Rise from the Ashes build: the base patch's
(script_en/std_scripts.phscr) with the fifth episode's 18 chapter titles
(the DS common script's sections 25-42, its centring command left out as
port_std.py does: the load screen's plate centres each line) appended as
sections 31-48 (en_rfta.h RFTA_TITLE_SECTION). usage: std.py"""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
from phscr import load, section_bounds, tokens, parse
import port_std
from ds_script import DS_ARGS, MES_ALL
ROOT = os.path.join(HERE, '..', '..', '..')
FIRST_DS, LAST_DS = 25, 42

def main():
    b, n, offs = load(os.path.join(ROOT, 'script_en', 'std_scripts.phscr'))
    secs = [tokens(b, *x) if x else None for x in section_bounds(b, offs)]
    assert n == 31 and all(secs), n
    ds = port_std.ds_std(MES_ALL)
    db, dn, doffs = load(ds)
    D = section_bounds(db, doffs)
    for k in range(FIRST_DS, LAST_DS + 1):
        out = []
        for p, kind, op, a in parse(tokens(db, *D[k]), DS_ARGS)[0]:
            if kind == 'cmd' and op == 0x5D:
                continue
            out += [op] + list(a) if kind == 'cmd' else [op]
        secs.append(out)
    n = len(secs)
    body = bytearray(); new_offs = []
    head = 4 + 4 * n
    for t in secs:
        while (head + len(body)) % 4:
            body.append(0)
        new_offs.append(head + len(body))
        body += struct.pack('<%dH' % len(t), *t)
    out = struct.pack('<I', n) + struct.pack('<%dI' % n, *new_offs) + bytes(body)
    f = os.path.join(ROOT, 'script_rfta', 'std_scripts.phscr')
    open(f, 'wb').write(out)
    print('wrote', f, n, 'sections')

if __name__ == '__main__':
    main()
