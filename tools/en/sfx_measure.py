#!/usr/bin/env python3
"""Levels of the sound effects for port_sfx.py (tools/en/sfx_levels.json).

Each sound was recorded on its own, from silence, in both games: the English DS
game (DeSmuME's core sound output, 44100 Hz) playing sequence N through its sound
effect function, and this build (mGBA, 32768 Hz) playing song N with every
converted song at track volume port_sfx.REF_VOL. The level of a sound is the RMS
of its mono mix from where it starts to where it falls 40 dB below its peak
(at most 3 s), the same stretch in both recordings.

usage: sfx_measure.py DS_DIR GBA_DIR [OUT.json]
DS_DIR holds d_N.wav (N = GBA song number; 121 and 122 for songs 111 and 112),
GBA_DIR holds g_N.wav."""
import sys, os, json, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import port_sfx

BGM_OFFSET_DB = 4.8    # DS music minus GBA music, median of songs 0-13, 16, 18-30 played alone


def read(fn):
    w = wave.open(fn)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(float).reshape(-1, 2).mean(1) / 32768
    return x, w.getframerate()


def window(x, r):
    h = max(1, r // 100)
    e = np.sqrt(np.convolve(x ** 2, np.ones(h) / h, 'same'))
    if e.max() < 1e-4:
        return None
    act = np.where(e > e.max() * 0.01)[0]
    return act[0] / r, min((act[-1] - act[0]) / r, 3.0)


def level(x, r, start, dur):
    seg = x[int(start * r):int((start + dur) * r) + 1]
    return 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12)


def main():
    ds_dir, gba_dir = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sfx_levels.json')
    res = {'bgm_offset_db': BGM_OFFSET_DB, 'ref_vol': port_sfx.REF_VOL, 'songs': {}}
    for g, d in sorted(port_sfx.SONGS.items()):
        dn = {111: 121, 112: 122}.get(g, g)
        a, ra = read(os.path.join(ds_dir, 'd_%d.wav' % dn))
        b, rb = read(os.path.join(gba_dir, 'g_%d.wav' % g))
        wa, wb = window(a, ra), window(b, rb)
        if wa is None or wb is None:
            print('song %d: silent' % g); continue
        dur = wa[1]
        la, lb = level(a, ra, wa[0], dur), level(b, rb, wb[0], dur)
        res['songs'][str(g)] = {'ds': round(la, 2), 'gba': round(lb, 2)}
        print('song %3d: DS %6.1f dB  GBA %6.1f dB  -> %+5.1f dB' % (g, la, lb, la - BGM_OFFSET_DB - lb))
    json.dump(res, open(out, 'w'), indent=1)


if __name__ == '__main__':
    main()
