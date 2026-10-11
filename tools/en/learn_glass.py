#!/usr/bin/env python3
"""Learn which GBA poses are drawn behind the detention center glass.

usage: learn_glass.py GBA_SCRIPT_DIR DS_MES_DIR  ->  writes glass_poses.json

The visitor's room (background 1E) shows the detainee behind the glass and the
visitor (Maya with Phoenix in Turnabout Samurai and Turnabout Goodbyes) in
front of it. The Japanese game draws the two with different animations of the
same expression: Maya held in Turnabout Sisters and Turnabout Goodbyes sits at
the counter behind the glass, Maya visiting stands on Phoenix's side. The DS
draws the glass as a layer of its own and says which side the person is on
with 4D 1E 0 (in front) / 4D 1E 1 (behind).

A pose is "glass only" when the Japanese game shows it in the visitor's room
only in sections whose DS section never puts that person in front of the glass
(port_script.py keeps those poses away from a person the DS puts in front)."""
import sys, os, glob, json, collections
sys.path.insert(0, os.path.dirname(__file__))
from phscr import load, section_bounds, tokens, parse, GBA_ARGS
import port_script as P

VISITORS_ROOM = 0x1E


def ds_front_people(db, x):
    """people the DS puts in front of the glass in this section (4D 1E 0 after their 1E)"""
    front, who = set(), None
    for pos, kind, op, a in parse(tokens(db, *x), P.DS_ARGS)[0]:
        if kind != 'cmd':
            continue
        if op == 0x1E and a:
            who = a[0] & 0xFF
        elif op == 0x4D and len(a) >= 2 and a[0] == VISITORS_ROOM and a[1] == 0 and who:
            front.add(who)
    return front


def main(gdir, ddir):
    gfiles = sorted(glob.glob(os.path.join(gdir, 'scenario_*.phscr')))
    dfiles = [os.path.join(ddir, '%02d.bin' % i) for i in range(1, 35, 2)]
    front, other = collections.defaultdict(set), collections.defaultdict(set)
    for gf, df in zip(gfiles, dfiles):
        gb, gn, go = load(gf)
        db, dn, do = load(df)
        G, D = section_bounds(gb, go), section_bounds(db, do)
        pairs = P.pair_sections(gb, G, db, D)
        items = pairs.items() if isinstance(pairs, dict) else enumerate(pairs)
        for gi, di in items:
            if di is None or not G[gi] or not D[di]:
                continue
            fr = ds_front_people(db, D[di])
            bg = None
            for pos, kind, op, a in parse(tokens(gb, *G[gi]), GBA_ARGS)[0]:
                if kind != 'cmd':
                    continue
                if op == 0x1B and a:
                    bg = a[0] & 0x7FFF
                elif op == 0x1E and a and a[0] and bg == VISITORS_ROOM:
                    (front if (a[0] & 0xFF) in fr else other)[a[0] & 0xFF].update(a[1:3])
    glass = {'%x' % p: sorted('%x' % v for v in other[p] - front[p])
             for p in sorted(other) if front[p] and other[p] - front[p]}
    out = os.path.join(os.path.dirname(__file__), 'glass_poses.json')
    json.dump({'_about': 'person -> GBA poses drawn behind the visitor\'s room glass (learn_glass.py)',
               'glass': glass}, open(out, 'w'), indent=1)
    for p, v in glass.items():
        print('person %s: %d poses behind the glass' % (p, len(v)))


if __name__ == '__main__':
    main(*sys.argv[1:3])
