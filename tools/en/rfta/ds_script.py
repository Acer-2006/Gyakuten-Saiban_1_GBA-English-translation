"""The DS scripts of Rise from the Ashes (mes_all.bin entries 35..71, the odd
ones; 17..35 counted as chapter files) and the argument counts of the
commands the fifth episode adds. MES_ALL points at mes_all.bin of your own
dump."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from dsdata import lz10
from phscr import load, section_bounds, tokens, parse
import port_script
MES_ALL = os.environ.get('MES_ALL', os.path.join(HERE, '..', '..', '..', '..', 'ds_fs', 'mes_all.bin'))
# Read off the ARM9 handlers (dsbin.py) and checked against every section of
# the fifth episode (no token left over, no command landing in text).
RFTA_ARGS = {0x55: 2, 0x5C: 3, 0x5F: 3, 0x68: 0, 0x6A: 1, 0x76: 2, 0x77: 2, 0x79: 0, 0x7B: 2}
DS_ARGS = dict(port_script.DS_ARGS); DS_ARGS.update(RFTA_ARGS)
FIRST_RFTA_FILE, LAST_RFTA_FILE = 17, 35     # 35 is the shared evidence-examination script
TITLES = {17: 'Day 1 - Investigation (1/2)', 18: 'Day 1 - Investigation (2/2)', 19: 'Day 2 - Trial Former (1/2)',
          20: 'Day 2 - Trial Former (2/2)', 21: 'Day 2 - Trial Latter', 22: 'Day 2 - Investigation (1/3)',
          23: 'Day 2 - Investigation (2/3)', 24: 'Day 2 - Investigation (3/3)', 25: 'Day 3 - Trial Former',
          26: 'Day 3 - Trial Latter (1/2)', 27: 'Day 3 - Trial Latter (2/2)', 28: 'Day 3 - Investigation (1/3)',
          29: 'Day 3 - Investigation (2/3)', 30: 'Day 3 - Investigation (3/3)', 31: 'Final Day - Trial Former',
          32: 'Final Day - Trial Latter', 33: 'Final Day - Trial Latter2 (1/2)', 34: 'Final Day - Trial Latter2 (2/2)',
          35: 'evidence examination lines (shared)'}
_d = None
def entries():
    global _d
    if _d is None:
        _d = open(MES_ALL, 'rb').read()
    n = struct.unpack_from('<I', _d, 0)[0]
    return _d, [struct.unpack_from('<II', _d, 4 + 8 * k) for k in range(n)]

def chapter(k):
    """decompressed script of chapter file k (0-16 the first four episodes, 17-35 the fifth)"""
    d, ents = entries()
    o, s = ents[2 * k + 1]
    return lz10(d, o)

def sections(k):
    """(index, parsed commands) of every section of chapter file k"""
    b, n, offs = load(chapter(k))
    for si, bd in enumerate(section_bounds(b, offs)):
        if bd:
            yield si, parse(tokens(b, *bd), DS_ARGS)[0]

SPECIAL = {0x17f: ' ', 0x161: '.', 0x16f: ',', 0x173: "'", 0x16d: ':', 0x1be: '!', 0x1bf: '?', 0x180: '-', 0x181: '"', 0x165: '(', 0x166: ')', 0x172: '*', 0xbe: '!', 0xbf: '?'}
def letter(v):
    if v in SPECIAL: return SPECIAL[v]
    c = v - 0x80
    if 0 <= c < 10: return chr(48 + c)
    if 10 <= c < 36: return chr(65 + c - 10)
    if 36 <= c < 62: return chr(97 + c - 36)
    return '{%x}' % v

def text(items):
    """a section (or part of one) as text with <commands>"""
    s = ''
    for p, k, op, a in items:
        if k == 'text': s += letter(op)
        elif k == 'bad': s += '<BAD %x>' % op
        elif op == 1: s += '/'
        elif op == 2: s += '<P>'
        else: s += '<%x%s>' % (op, ''.join(' %x' % v for v in a))
    return s

if __name__ == '__main__':
    # ds_script.py OPCODE_HEX [context] [max]: where the fifth episode uses a command
    want = int(sys.argv[1], 16); ctx = int(sys.argv[2]) if len(sys.argv) > 2 else 10; mx = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    shown = 0
    for k in range(FIRST_RFTA_FILE, LAST_RFTA_FILE + 1):
        for si, items in sections(k):
            for i, (p, kind, op, a) in enumerate(items):
                if kind == 'cmd' and op == want:
                    print('file %d sec %d: %s' % (k, si, text(items[max(0, i - ctx):i + ctx]).replace('\n', ' ')))
                    shown += 1
                    if shown >= mx: sys.exit()
