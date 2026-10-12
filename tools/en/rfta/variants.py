"""Argument patterns of the DS-only commands in the fifth episode, and which
of them episodes 1-4 never use (the ones the port has no model for yet)."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ds_script import sections, FIRST_RFTA_FILE, LAST_RFTA_FILE
OPS = (0x4D, 0x4E, 0x55, 0x5C, 0x5F, 0x65, 0x68, 0x69, 0x6A, 0x6B, 0x6F, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x7B)
def argsets(files):
    out = collections.defaultdict(collections.Counter)
    for k in files:
        for si, items in sections(k):
            for p, kind, op, a in items:
                if kind == 'cmd' and op in OPS:
                    out[op][tuple(a)] += 1
    return out
def fmt(k): return '(' + ' '.join('%x' % x for x in k) + ')'
old = argsets(range(0, FIRST_RFTA_FILE)); new = argsets(range(FIRST_RFTA_FILE, LAST_RFTA_FILE + 1))
for op in sorted(new):
    nn = {k: v for k, v in new[op].items() if k not in old[op]}
    print('%02x: %d uses, %d variants, %d variants new to the fifth episode (%d uses):' % (op, sum(new[op].values()), len(new[op]), len(nn), sum(nn.values())))
    print('    ' + ' '.join('%s x%d' % (fmt(k), v) for k, v in sorted(new[op].items(), key=lambda kv: -kv[1])[:30]))
