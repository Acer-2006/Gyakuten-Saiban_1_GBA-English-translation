#!/usr/bin/env python3
"""Learn DS->GBA person animation id mapping (script command 0x1E) from aligned sections.
usage: learn_anim_map.py GBA_SCRIPT_DIR DS_MES_DIR OUT.json"""
import sys, os, glob, json, difflib, collections
sys.path.insert(0, os.path.dirname(__file__))
from phscr import GBA_ARGS, parse, tokens
from align import aligned_pairs
DS = {int(k, 16): v for k, v in json.load(open(os.path.join(os.path.dirname(__file__), 'ds_args.json'))).items()}
gdir, ddir, outp = sys.argv[1:4]
gfiles = sorted(glob.glob(os.path.join(gdir, 'scenario_*.phscr')))
dfiles = [os.path.join(ddir, '%02d.bin' % i) for i in range(1, 35, 2)]
votes = collections.defaultdict(collections.Counter)
for gf, df in zip(gfiles, dfiles):
    tag = os.path.basename(gf).split('_script')[0]
    gb, G, db, D, pairs = aligned_pairs(gf, df)
    for gi, di in pairs:
        if not (G[gi] and D[di]):
            continue
        g = [x for x in parse(tokens(gb, *G[gi]), GBA_ARGS)[0] if x[1] == 'cmd' and x[2] == 0x1E]
        d = [x for x in parse(tokens(db, *D[di]), DS)[0] if x[1] == 'cmd' and x[2] == 0x1E]
        gk = [(x[3][0],) for x in g]; dk = [(x[3][0],) for x in d]
        if len(g) == len(d) and gk == dk:   # only trust sections with identical person sequences
            for a, b in zip(g, d):
                person = a[3][0]
                votes[(tag, person, b[3][1])][a[3][1]] += 1
                votes[(tag, person, b[3][2])][a[3][2]] += 1
mapping = {}
conflicts = 0
for (tag, person, dsv), c in votes.items():
    (gv, n), = c.most_common(1)
    tot = sum(c.values())
    if n / tot < 0.6:
        conflicts += 1
    mapping['%s:%x:%x' % (tag, person, dsv)] = gv
json.dump(mapping, open(outp, 'w'), indent=0, sort_keys=True)
print('anim map entries', len(mapping), 'low-confidence', conflicts)
