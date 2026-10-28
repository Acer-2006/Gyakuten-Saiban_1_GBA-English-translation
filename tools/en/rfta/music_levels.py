#!/usr/bin/env python3
"""Levels of Rise from the Ashes' songs beside the GBA's own music (music.py).

Takes recordings of the DS game (the DS song n: DS_DIR/d_n.wav) and of the
RFTA build (the GBA song n: GBA_DIR/g_n.wav), each the song on its own from
silence, 30 seconds. The DS plays its music louder than the GBA: the offset is
the median difference over the reference songs (GBA songs 0-41, which the DS
numbers the same). Each new song is then set so that it stands to the GBA's
music as it stands to the DS's: its gain (music_levels.json, dB, used by
music.py) changes by what its recording is off by.

usage: music_levels.py DS_DIR GBA_DIR"""
import sys, os, json
import numpy as np
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = os.path.join(HERE, 'music_levels.json')
NEW = {113 + i: (0x17C + i, 'BGM%d' % (150 + i)) for i in range(7)}


def level_db(fn):
    rate, x = wavfile.read(fn)
    x = x.astype(float)
    if x.ndim > 1:
        x = x.mean(axis=1)
    x = x / 32768.0
    # the DS recordings (from one saved state) have another sound 3.5-7.5 s in: left out of both
    x = np.concatenate([x[int(rate * 0.5):int(rate * 3.5)], x[int(rate * 7.5):]])
    # loudness: the mean power of 400 ms blocks above a gate (silence between phrases not counted)
    n = int(rate * 0.4)
    blocks = np.array([np.mean(x[i:i + n] ** 2) for i in range(0, len(x) - n, n)])
    blocks = blocks[blocks > 1e-7]
    if not len(blocks):
        return -120.0
    gate = np.mean(blocks) * 0.1
    return 10 * np.log10(np.mean(blocks[blocks >= gate]))


def main():
    ds_dir, gba_dir = sys.argv[1:3]
    levels = json.load(open(LEVELS)) if os.path.exists(LEVELS) else {}
    ref = []
    for n in range(42):
        d, g = os.path.join(ds_dir, 'd_%d.wav' % n), os.path.join(gba_dir, 'g_%d.wav' % n)
        if os.path.exists(d) and os.path.exists(g):
            ref.append((n, level_db(d) - level_db(g)))
    offset = float(np.median([x for _, x in ref]))
    print('reference songs (DS - GBA, dB):', ', '.join('%d %+.1f' % r for r in ref), '-> offset %.1f' % offset)
    for g, (dseq, name) in sorted(NEW.items()):
        d, gf = os.path.join(ds_dir, 'd_%d.wav' % dseq), os.path.join(gba_dir, 'g_%d.wav' % g)
        if not (os.path.exists(d) and os.path.exists(gf)):
            continue
        ld, lg = level_db(d), level_db(gf)
        want = ld - offset
        old = levels.get(name, {}).get('gain_db', 0.0)
        new = round(old + want - lg, 1)
        levels[name] = {'gain_db': new, 'ds_db': round(ld, 1), 'gba_db': round(lg, 1)}
        print('%s: DS %.1f dB, GBA %.1f dB, wanted %.1f: gain %+.1f -> %+.1f dB' % (name, ld, lg, want, old, new))
    levels['offset_db'] = round(offset, 1)
    json.dump(levels, open(LEVELS, 'w'), indent=1, sort_keys=True)


if __name__ == '__main__':
    main()
