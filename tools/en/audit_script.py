#!/usr/bin/env python3
"""Check the ported scripts against the DS ones.

- screen shakes (27), sound effects (06) and white flashes (12, mode 3) in each
  ported section against the DS section it came from (the DS decides these)
- text printed while the text box is hidden (1C 1 ... 1C 0)
- text characters outside the DS English character set

usage: audit_script.py [GBA_SCRIPT_DIR PORTED_DIR DS_MES_DIR]
Some section table entries are not offsets (they point past the end of the
Japanese script); they are skipped, also where the larger English script
reaches that far."""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phscr import load, section_bounds, tokens, parse, GBA_ARGS
import port_script
from pdump import SPECIAL

HERE = os.path.dirname(os.path.abspath(__file__))
gdir, odir, ddir = (sys.argv[1:4] if len(sys.argv) > 3 else
                    [os.path.join(HERE, '../../script'), os.path.join(HERE, '../../script_en'),
                     os.path.join(HERE, '../../../ds_mes')])
FX = {0x27: 'shake', 0x06: 'sound', 0x12: 'flash'}
LATIN = set(range(0x80, 0x80 + 62)) | set(SPECIAL) | set(range(0x16c, 0x190))


def effects(b, x, args):
    c = collections.Counter()
    for pos, kind, op, a in parse(tokens(b, *x), args)[0]:
        if kind == 'cmd' and op in FX and (op != 0x12 or a[0] >> 8 == 3):
            c[FX[op]] += 1
    return c


def hidden_text(b, x):
    vis, n = True, 0
    for pos, kind, op, a in parse(tokens(b, *x), GBA_ARGS)[0]:
        if kind == 'cmd' and op == 0x1c and a and a[0] in (0, 1):
            vis = a[0] == 0
        elif kind == 'text' and not vis:
            n += 1
    return n


tot = collections.Counter()
problems = []
files = sorted(f for f in os.listdir(odir) if f.startswith('scenario_') and f.endswith('.phscr'))
for idx, f in enumerate(files):
    rep = open(os.path.join(odir, f + '.report.txt')).read()
    pairs = {int(m.group(1)): int(m.group(2)) for m in re.finditer(r'sec +(\d+) <- ds +(\d+)', rep)}
    gb, gn, goffs = load(os.path.join(gdir, f)); G = section_bounds(gb, goffs)
    ob, on, ooffs = load(os.path.join(odir, f))
    real = sorted(set(o for i, o in enumerate(ooffs) if G[i] is not None)) + [len(ob)]
    O = [(o, real[real.index(o) + 1]) if G[i] is not None else None for i, o in enumerate(ooffs)]
    db, dn, doffs = load(os.path.join(ddir, '%02d.bin' % (2 * idx + 1))); D = section_bounds(db, doffs)
    for gi, dj in pairs.items():
        cd = effects(db, D[dj], port_script.DS_ARGS); co = effects(ob, O[gi], GBA_ARGS)
        for k in FX.values():
            tot[(k, 'ds')] += cd[k]; tot[(k, 'port')] += co[k]
            if cd[k] != co[k]:
                problems.append('%s section %#x: %s DS %d, port %d' % (f, gi + 0x80, k, cd[k], co[k]))
    for i, x in enumerate(O):
        if not x:
            continue
        n, ng = hidden_text(ob, x), hidden_text(gb, G[i])
        if n and (ng == 0 or n > 2 * ng + 20):
            problems.append('%s section %#x: %d characters printed in a hidden text box' % (f, i + 0x80, n))
        odd = [op for pos, kind, op, a in parse(tokens(ob, *x), GBA_ARGS)[0] if kind == 'text' and op not in LATIN]
        if odd:
            problems.append('%s section %#x: characters outside the English set %s' % (f, i + 0x80, ' '.join('%x' % v for v in odd)))
for k in FX.values():
    print('%-6s DS %5d  port %5d' % (k, tot[(k, 'ds')], tot[(k, 'port')]))
print('\n'.join(problems) or 'no problems')
