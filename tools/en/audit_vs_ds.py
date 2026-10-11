#!/usr/bin/env python3
"""Compare every English section with the DS section it was ported from.

usage: audit_vs_ds.py DS_MES_DIR DS_MES_ALL
  DS_MES_DIR: the DS English scenario scripts (01.bin, 03.bin ... 33.bin, as
  port_all.py takes them); DS_MES_ALL: the DS mes_all.bin (common script).

For each section pair (script_en/*.report.txt; port_std.PAIRS for the common
script):
- the text: letters, line and page breaks;
- the commands the port takes from the DS as they are: sound effects, shakes,
  white flashes and fades to white, the evidence plate, the text box shown /
  hidden, name tags, music, penalties;
- who is shown at each line (1E: both games number the people alike);
- the Objection! / Hold it! / Take that! bubbles;
- each choice: the section every answer leads to, in the DS's answer order
  (the answer labels are the DS's).

The differences the port makes on purpose are listed below and reported as
expected; anything else is printed and the exit status is 1. This found the
double penalty after "Oh. Whoops. Wrong evidence.", the fades to white a page
late (April May, the "Pink Princess"), the file answers in the chief's
office leading to each other's files, and the missing white flashes and text
box hides in the wrong-evidence penalties."""
import os, sys, re, struct, difflib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
import port_script as P
from phscr import load, section_bounds, tokens, parse, GBA_ARGS
from pdump import ch

NAMES = ['scenario_0'] + ['scenario_1_%d' % i for i in range(4)] + ['scenario_2_%d' % i for i in range(6)] + \
        ['scenario_3_%d' % i for i in range(6)]
GAVEL = ('se', 0x3A)          # the GBA's gavel (sound and shake) where the DS draws its own (69 62 111)

# Text the port changes on purpose
EXPECTED_TEXT = {
    ('scenario_0', 0x86), ('scenario_0', 0x88), ('scenario_0', 0x89), ('scenario_0', 0x8C),
    ('scenario_0', 0x8E), ('scenario_0', 0xA4), ('scenario_0', 0xB0),   # "Press R", not "touch the button"
    ('scenario_1_0', 0xDF),                                            # a stray DS label ("{BGM}...") left out
    ('scenario_2_1', 0xBF), ('scenario_2_1', 0xC3),                    # DS typo "the/the Steel Samurai"
    ('scenario_3_4', 0xB4),                                            # ported against two DS sections joined
    ('std', 0x02), ('std', 0x05),                                      # centred in the episode menu
}
# Other DS commands the port changes on purpose
EXPECTED_CMDS = {
    ('scenario_2_2', 0x13D), ('scenario_2_2', 0x13E), ('scenario_2_2', 0x13F),   # the GBA's end of a talk
    ('scenario_3_0', 0xF7),                                                       # the GBA's jump back from a talk
    ('scenario_2_5', 0xB0),        # a text box kept hidden over a background change (fix_box_flash)
    ('scenario_3_4', 0xB4),        # joined DS sections
}


def text_of(items):
    s = []
    for p, k, op, a in items:
        if k == 'text':
            s.append(ch(op))
        elif k == 'cmd' and op == 0x01:
            s.append('/')
        elif k == 'cmd' and op in (0x02, 0x2D):
            s.append('|')
    return ''.join(s)


def ds_cmds(items, ds):
    out = []
    for p, k, op, a in items:
        if k != 'cmd':
            continue
        if op == 0x06:
            out.append(('se', P.SE_MAP.get(a[0], a[0]) if ds else a[0] >> 8))
        elif op == 0x27:
            out.append(('shake',))
        elif op == 0x12 and a and a[0] >> 8 == 3:
            if not (ds and len(a) >= 2 and a[1] == 0):      # a DS flash of step 0 is left out on purpose
                out.append(('flash',))
        elif op == 0x12 and a and a[0] >> 8 == 4:
            out.append(('white',))
        elif op == 0x13:
            out.append(('plate',))
        elif op == 0x14:
            out.append(('plate_off',))
        elif op == 0x1C and a:
            out.append(('box', a[0]))
        elif op == 0x0E and a:
            out.append(('tag', a[0] >> 8))
        elif op == 0x05:
            out.append(('music',) + tuple(a[:1]))
        elif op == 0x2B:
            out.append(('penalty',))
    return out


def expected_insert(seq):
    """GBA gavels (sound + shake, once or three times) and plate hides (14 for the DS's 69 62 243)"""
    if seq == [('plate_off',)]:
        return True
    return len(seq) in (2, 6) and all(seq[k] == (GAVEL if k % 2 == 0 else ('shake',)) for k in range(len(seq)))


def people(items):
    person, res, intext = None, [], False
    for p, k, op, a in items:
        if k == 'text':
            if not intext:
                res.append(person)
            intext = True
            continue
        if not (k == 'cmd' and op in (0x01, 0x03, 0x0B, 0x0C)):
            intext = False
        if k == 'cmd' and op == 0x1E and a:
            person = a[0] or None
    return res


def bubbles(items):
    return [a[0] for p, k, op, a in items if k == 'cmd' and op == 0x2F and a and a[0] in P.SPEECH_BUBBLES]


def records(b, S):
    d = set()
    for x in S:
        if x:
            for p, k, op, a in parse(tokens(b, *x), GBA_ARGS)[0]:
                if k == 'cmd' and op == 0x35 and a[0] & 0x80:
                    d.add(a[1])
                if k == 'cmd' and op == 0x36:
                    d.add(a[0])
    return d


def audit(name, gfile, efile, dsb, pairs, std=False):
    gb, gn, go = load(gfile); G = section_bounds(gb, go)
    eb, en, eo = load(efile)
    desc = records(gb, G)
    real = sorted(set(eo[i] for i in range(gn) if G[i] and i not in desc and eo[i] < len(eb))) + [len(eb)]
    dn = struct.unpack_from('<I', dsb, 0)[0]
    D = section_bounds(dsb, list(struct.unpack_from('<%dI' % dn, dsb, 4)))
    found, expected = [], 0
    for gi in range(gn):
        if not G[gi] or gi in desc or gi not in pairs or eo[gi] >= len(eb):
            continue
        dj = pairs[gi]
        if dj is None or dj >= len(D) or not D[dj]:
            continue
        sec = gi if std else gi + 0x80
        key = (name, sec)
        where = '%s:%X (DS %d)' % (name, sec, dj)
        ei = parse(tokens(eb, eo[gi], real[real.index(eo[gi]) + 1]), GBA_ARGS)[0]
        di = parse(tokens(dsb, *D[dj]), P.DS_ARGS)[0]
        if text_of(ei) != text_of(di):
            if key in EXPECTED_TEXT:
                expected += 1
            else:
                found.append('%s text differs' % where)
        ea, da = ds_cmds(ei, False), ds_cmds(di, True)
        if ea != da:
            sm = difflib.SequenceMatcher(None, da, ea, autojunk=False)
            odd = [(t, da[i1:i2], ea[j1:j2]) for t, i1, i2, j1, j2 in sm.get_opcodes()
                   if t != 'equal' and not (t == 'insert' and expected_insert(ea[j1:j2]))]
            if odd and key not in EXPECTED_CMDS:
                found += ['%s %s: DS %s, here %s' % (where, t, d, e) for t, d, e in odd]
            elif odd:
                expected += 1
        ep, dp = people(ei), people(di)
        if len(ep) == len(dp) and ep != dp:
            found += ['%s line %d shows person %s, the DS %s' % (where, k, x, y)
                      for k, (x, y) in enumerate(zip(ep, dp)) if x != y]
        if bubbles(ei) != bubbles(di):
            found.append('%s bubbles %s, the DS %s' % (where, bubbles(ei), bubbles(di)))
        ec = [(op, a) for p, k, op, a in ei if k == 'cmd' and op in (0x08, 0x09)]
        dc = [(op, a) for p, k, op, a in di if k == 'cmd' and op in (0x08, 0x09)]
        if len(ec) != len(dc):
            found.append('%s %d choices, the DS %d' % (where, len(ec), len(dc)))
        else:
            for (op, a), (dop, da_) in zip(ec, dc):
                n = 2 if op == 0x08 else 3
                got = [pairs.get(x - 0x80) for x in a[:n]]
                want = [x - 0x80 for x in da_[:n]]
                if op != dop or got != want:
                    found.append('%s answers lead to DS sections %s, the DS\'s answers to %s' % (where, got, want))
    return found, expected


def ds_parse_check(dsb, name):
    """The DS script must parse cleanly with ds_args.json: an unknown opcode, or a
    00 (section start) in the middle of a section, means a command's argument
    count is short and its last argument is being read as a command (4B's second
    argument came through as a line break and a page break, 6B's third as 1F)."""
    dn = struct.unpack_from('<I', dsb, 0)[0]
    D = section_bounds(dsb, list(struct.unpack_from('<%dI' % dn, dsb, 4)))
    found = []
    for j, x in enumerate(D):
        if not x:
            continue
        items = parse(tokens(dsb, *x), P.DS_ARGS)[0]
        for q, (p, k, op, a) in enumerate(items):
            if k == 'bad':
                found.append('%s DS %X: unknown opcode %X' % (name, j + 0x80, op))
            elif k == 'cmd' and op == 0x00 and p > 0:
                prev = items[q - 1]
                found.append('%s DS %X: 00 mid-section after %s (argument count short?)'
                             % (name, j + 0x80, ('%X' % prev[2]) if prev[1] == 'cmd' else 'text'))
    return found


def pairs_of(report):
    res = {}
    for l in open(report):
        m = re.match(r'sec\s+(\d+) <- ds\s+(\d+)', l)
        if m:
            res[int(m.group(1))] = int(m.group(2))
    return res


def main():
    ds_dir, mes_all = sys.argv[1:3]
    os.chdir(ROOT)
    found, expected = [], 0
    for idx, nm in enumerate(NAMES):
        f = nm + '_script.phscr'
        dsb = open(os.path.join(ds_dir, '%02d.bin' % (2 * idx + 1)), 'rb').read()
        found += ds_parse_check(dsb, nm)
        r, e = audit(nm, 'script/' + f, 'script_en/' + f, dsb, pairs_of('script_en/' + f + '.report.txt'))
        found += r; expected += e
    from port_std import ds_std, PAIRS
    found += ds_parse_check(ds_std(mes_all), 'std')
    r, e = audit('std', 'script/std_scripts.phscr', 'script_en/std_scripts.phscr', ds_std(mes_all), PAIRS, std=True)
    found += r; expected += e
    for x in found:
        print(x)
    print('%d unexpected differences from the DS (%d sections differ on purpose)' % (len(found), expected))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
