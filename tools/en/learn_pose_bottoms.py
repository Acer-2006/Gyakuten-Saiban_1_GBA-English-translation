#!/usr/bin/env python3
"""Measure how far down the screen each GBA person animation is drawn.

usage: learn_pose_bottoms.py RUNNER ROM STATE  ->  writes pose_bottoms.json

RUNNER is the mGBA script runner used for the other measurements (load:,
memload:, poke32:, wait:, shot: commands), STATE an emulator savestate in a
court scene. For every GBA animation in anim_looks.json and every pose the
Japanese scripts show, a tiny script is run in place of the game's (person on
background 5 with the text box hidden) and the screen is compared with the
same background alone over 80 frames: the lowest row that changes is where
the animation ends.

The Japanese game draws a person at the witness stand, the counsel benches
and the judge's bench with animations that end at the top of the desk (rows
136-140); the same expressions drawn for other places go down to the bottom
of the screen (159), and on those backgrounds they cover the desk."""
import sys, os, glob, json, struct, subprocess
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from phscr import load, section_bounds, tokens, parse, GBA_ARGS

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = '/tmp/pose_bottoms'
BG = 5
SHOTS = 4


def poses():
    want = set()
    looks = json.load(open(os.path.join(HERE, 'anim_looks.json')))['cls']
    for k in looks:
        p, a = k.split(':')
        want.add((int(p, 16), int(a, 16)))
    for f in glob.glob(os.path.join(HERE, '..', '..', 'script', 'scenario_*.phscr')):
        b, n, offs = load(f)
        for x in section_bounds(b, offs):
            if x:
                for pos, kind, op, a in parse(tokens(b, *x), GBA_ARGS)[0]:
                    if kind == 'cmd' and op == 0x1E and a and a[0] & 0xFF:
                        want.add((a[0] & 0xFF, a[1]))
                        want.add((a[0] & 0xFF, a[2]))
    return want


def measure(runner, rom, state, person, anims):
    args = [runner, rom, 'load:' + state]
    for k, a in enumerate([None] + anims):
        toks = [0x1C, 1, 0x1E, 0 if a is None else person, a or 0, a or 0, 0x1B, BG, 0x0C, 0x7FFF]
        fn = '%s/t%d.bin' % (TMP, k)
        open(fn, 'wb').write(struct.pack('<%dH' % len(toks), *toks))
        args += ['memload:0x02020000:' + fn, 'poke32:0x03003a78:0x02020000', 'poke32:0x03003a74:0x02020000', 'wait:40']
        for j in range(SHOTS):
            args += ['shot:%s/s%d_%d.ppm' % (TMP, k, j), 'wait:20']
    subprocess.run(args, capture_output=True, cwd=os.path.dirname(runner))
    shot = lambda k, j: np.asarray(Image.open('%s/s%d_%d.ppm' % (TMP, k, j)).convert('RGB'), dtype=int)
    base = [shot(0, j) for j in range(SHOTS)]
    res = {}
    for k, a in enumerate(anims, 1):
        m = np.zeros(base[0].shape[:2], bool)
        for j in range(SHOTS):
            m |= np.abs(shot(k, j) - base[j]).sum(2) > 30
        rows = np.nonzero(m.any(1))[0]
        if len(rows):
            res['%x' % a] = [int(rows.min()), int(rows.max())]
    return res


def main(runner, rom, state):
    os.makedirs(TMP, exist_ok=True)
    by = {}
    for p, a in poses():
        by.setdefault(p, set()).add(a)
    out = {}
    for p in sorted(by):
        out['%x' % p] = measure(os.path.abspath(runner), os.path.abspath(rom), os.path.abspath(state), p, sorted(by[p]))
        print('%x: %d animations' % (p, len(out['%x' % p])))
    json.dump({'_about': 'person -> GBA animation -> [top row, bottom row] drawn (learn_pose_bottoms.py)',
               'bottoms': out}, open(os.path.join(HERE, 'pose_bottoms.json'), 'w'), indent=0, sort_keys=True)


if __name__ == '__main__':
    main(*sys.argv[1:4])
