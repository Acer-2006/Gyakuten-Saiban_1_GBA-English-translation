#!/usr/bin/env python3
"""The DS's sound effects on the GBA.

Every sound effect song the game plays (the realization and evidence stings, the
text blips, the menu sounds, the gavel, the voices and all the others) is rebuilt
from the English DS release's sound archive: the DS sequence (notes, timing,
stereo, pitch bends), the DS samples and the DS's volumes.

The DS numbers its sequences like the GBA numbers its songs (SE000 is song 42),
so song N becomes DS sequence N. The voices are the English ones the DS plays in
their place (its function at 0x02025900: 0x51 -> SE0B0, 0x47 -> SE0B1,
0x39 -> SE0B2, 0x38 -> SE0B3, 0x41 -> SE0B4, 0x37 -> SE0B5), and songs 111 and
112 are the two sounds the English DS script added (SE04F and SE050).

Samples are resampled to the GBA mixer's rate (15768 Hz) at the pitch the DS
plays them and played one to one (no resampling by the engine), so they sound
at the DS's pitch (the English voices, 16364 Hz recordings, had played 3.6%
slow); looped samples keep their loops. A sample the DS plays slower than that
(the crowd, at 6258 Hz) is held from step to step, as the DS's sound hardware
does. Release rates follow the DS's (measured in the DS game). The DS's PSG
notes (the telephone) become GBA square-wave notes at the DS's pitches. A DS
sequence with more tracks than the GBA music player has (SE015, four) has them
paired by side.
Every song sets the reverb to none, as the Japanese text blips did on every
line (the DS has no reverb; some Japanese sound effects turned it up for the
music until the next line).

Volumes: tools/en/sfx_levels.json holds, for each song, the DS's level (the DS
game playing the sound on its own) and this build's level at track volume
REF_VOL; the volume is set so that the sound stands to the music as on the DS
(the DS plays its music 4.8 dB louder than the GBA: median of 28 songs). Made
by tools/en/sfx_measure.py.

usage: port_sfx.py DS_sound_data.sdat
writes sound/direct_sound_samples/en_sfx/*.bin and data/en_sound.s, and points
the song table in data/sound_data.s at the new songs."""
import sys, os, re, json, struct, hashlib
from fractions import Fraction
import numpy as np
from scipy.signal import resample_poly, resample
import ndspy.soundArchive as sa

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
MIX_RATE = 15768                      # SOUND_MODE_FREQ_15768 (m4aSoundInit)
REF_VOL = 100                         # track volume of the reference build in sfx_levels.json
PLAYER_TRACKS = {0: 7, 1: 2, 2: 1, 3: 1}   # gMPlayTrack_BGM/SE1/SE2/SE3

# GBA song -> DS sequence
SONGS = {14: 14, 15: 15, 17: 17, 32: 32, 33: 33}
SONGS.update({n: n for n in range(42, 106) if n != 50})
SONGS.update({0x51: 400, 0x47: 401, 0x39: 402, 0x38: 403, 0x41: 404, 0x37: 405})   # English voices
SONGS.update({111: 121, 112: 122})                                                # English-only sounds

# ---------------------------------------------------------------- DS sequences
ONE = {0xC0: 'pan', 0xC1: 'vol', 0xC2: 'mastervol', 0xC3: 'transpose', 0xC4: 'bend', 0xC5: 'bendrange',
       0xC6: 'prio', 0xC7: 'monopoly', 0xC8: 'tie', 0xC9: 'portakey', 0xCA: 'moddepth', 0xCB: 'modspeed',
       0xCC: 'modtype', 0xCD: 'modrange', 0xCE: 'portaon', 0xCF: 'portatime', 0xD0: 'attack', 0xD1: 'decay',
       0xD2: 'sustain', 0xD3: 'release', 0xD4: 'loopstart', 0xD5: 'expr', 0xD6: 'print'}
TWO = {0xE0: 'moddelay', 0xE1: 'tempo', 0xE3: 'sweep'}


def varlen(b, p):
    v = 0
    while True:
        c = b[p]; p += 1; v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, p


def sseq_tracks(b):
    """{track number: start offset} from the FE/93 header"""
    starts = {}; p = 0
    if b[0] == 0xFE:
        p = 3
    while p < len(b) and b[p] == 0x93:
        starts[b[p + 1]] = b[p + 2] | (b[p + 3] << 8) | (b[p + 4] << 16); p += 5
    starts[0] = p
    return dict(sorted(starts.items()))


def sseq_events(b, p):
    """events of one track: (tick, kind, value). Poly mode: notes take no time, rests do.
    An endless loop puts ('loopstart', None) where it starts and ends with ('loopend', None)"""
    t = 0; ev = []; calls = []; loops = []; poly = True
    while True:
        c = b[p]; p += 1
        if c < 0x80:
            vel = b[p]; p += 1; dur, p = varlen(b, p)
            ev.append((t, 'note', (c, vel, dur)))
            if not poly:
                t += dur
        elif c == 0x80:
            d, p = varlen(b, p); t += d
        elif c == 0x81:
            v, p = varlen(b, p); ev.append((t, 'prog', v))
        elif c == 0x95:
            calls.append(p + 3); p = b[p] | (b[p + 1] << 8) | (b[p + 2] << 16)
        elif c == 0xFD:
            if not calls:
                break
            p = calls.pop()
        elif c in ONE:
            v = b[p]; p += 1; name = ONE[c]
            if name in ('bend', 'transpose'):
                v = v - 256 if v > 127 else v
            if name == 'monopoly':
                poly = v == 0
            elif name == 'loopstart':
                loops.append([p, v])
                if v == 0:
                    ev.append((t, 'loopstart', None))
            elif name in ('tie', 'portaon', 'sweep', 'mastervol'):
                raise ValueError('SSEQ %s not handled' % name)
            else:
                ev.append((t, name, v))
        elif c in TWO:
            v = struct.unpack_from('<h' if c == 0xE3 else '<H', b, p)[0]; p += 2
            ev.append((t, TWO[c], v))
        elif c == 0xFC:
            lp = loops[-1]
            if lp[1] == 0:
                ev.append((t, 'loopend', None))
                break
            lp[1] -= 1
            if lp[1] > 0:
                p = lp[0]
            else:
                loops.pop()
        elif c == 0xFE:
            p += 2
        elif c == 0xFF:
            break
        else:
            raise ValueError('SSEQ command %02x not handled' % c)
    return ev


def note_definition(inst, key):
    t = type(inst).__name__
    if t == 'SingleNoteInstrument':
        return inst.noteDefinition
    if t == 'RangeInstrument':
        return inst.noteDefinitions[key - inst.firstPitch]
    for r in inst.regions:
        if key <= r.lastPitch:
            return r.noteDefinition
    raise ValueError('no region for key %d' % key)


def wave_pcm(w):
    if w.waveType == 0:
        return np.frombuffer(bytes(w.data), dtype=np.int8).astype(float) / 128.0
    if w.waveType == 1:
        return np.frombuffer(bytes(w.data), dtype='<i2').astype(float) / 32768.0
    raise ValueError('ADPCM wave not handled')


def ds_release_to_gba(r):
    """DS release rate -> m4a DirectSound release (envelope *= r/256 each frame). The DS's
    release takes 0x1E00/(126-r) (2r+1 below 50, 0x3C00 at 126) off the envelope each update; measured
    from the DS game, that is 0.1771 dB a second for each unit (SE013, release 92: 40 dB
    a second; SE03B, release 117: 151)"""
    if r >= 127:
        return 0
    rate = 0x3C00 if r == 126 else 0x1E00 / (126 - r) if r >= 50 else 2 * r + 1
    db_per_frame = rate * 0.1771 / 59.7275
    return max(1, min(255, round(256 * 10 ** (-db_per_frame / 20))))


# ---------------------------------------------------------------- m4a
LEN = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24,
       28, 30, 32, 36, 40, 42, 44, 48, 52, 54, 56, 60, 64, 66, 68, 72, 76, 78, 80, 84, 88, 90, 92, 96]
CGB_FREQ = [-2004, -1891, -1785, -1685, -1591, -1501, -1417, -1337, -1262, -1192, -1125, -1062]


def waits(d):
    out = []
    while d > 0:
        k = max(i for i, l in enumerate(LEN) if l <= d)
        out.append(0x80 + k); d -= LEN[k]
    return out


def note_cmd(key, vel, d):
    """N command for d ticks (1..99): the longest table length plus up to 3 ticks of gate"""
    k = max(i for i, l in enumerate(LEN) if l <= min(d, 96))
    ext = d - LEN[k]
    return [0xCF + k, key, vel] + ([ext] if ext else [])


def cgb_square_hz(key, pit):
    """m4a MidiKeyToCgbFreq for the square channels: key and fine pitch (1/256 semitone)"""
    k = key - 36
    if k < 0:
        k, pit = 0, 0
    def reg(i):
        s = (i // 12) * 16 + i % 12
        return CGB_FREQ[s & 0xF] >> (s >> 4)
    v1, v2 = reg(k), reg(k + 1)
    n = v1 + ((pit * (v2 - v1)) >> 8) + 2048
    return 131072.0 / (2048 - n)


def square_note(ds_key, ds_bends):
    """GBA key and BEND values (range 2) giving the DS square's pitch with each DS bend"""
    best = None
    for gk in range(ds_key - 2, ds_key + 3):
        err = 0; bends = []
        for db in ds_bends:
            target = 440 * 2 ** ((ds_key + db / 64.0 - 69) / 12)    # DS bend range 2: 64 = a semitone
            cand = []
            for gb in range(-64, 64):
                x = gb * 2 * 4                  # (tune + bend * range) * 4
                cand.append((abs(np.log2(cgb_square_hz(gk + (x >> 8), x & 0xFF) / target)), gb))
            e, gb = min(cand)
            err += e; bends.append(gb)
        if best is None or err < best[0]:
            best = (err, gk, bends)
    return best[1], best[2]


def resample_to(x, rate, loop=None):
    """x played at `rate` -> MIX_RATE, a loop resampled as a period of its own. A sample
    the DS plays slower than the mixer's rate is held from step to step as the DS's sound
    hardware does (it has no interpolation), so its images above the sample's own band
    come out as on the DS; a faster one is filtered down to the mixer's band"""
    up = rate < MIX_RATE * 0.98
    f = Fraction(MIX_RATE / rate).limit_denominator(4096)
    def hold(seg, n):
        return seg[np.minimum((np.arange(n) * len(seg) / n).astype(int), len(seg) - 1)] if n else np.zeros(0)
    if loop is None:
        if up:
            return hold(x, round(len(x) * MIX_RATE / rate)), None
        return resample_poly(x, f.numerator, f.denominator), None
    head, body = x[:loop], x[loop:]
    nb = max(1, round(len(body) * MIX_RATE / rate))
    nh = round(len(head) * MIX_RATE / rate)
    if up:
        return np.concatenate([hold(head, nh), hold(body, nb)]), nh
    body2 = resample(body, nb)
    head2 = resample_poly(np.concatenate([head, body, body]), f.numerator, f.denominator)[:nh] if nh else np.zeros(0)
    return np.concatenate([head2, body2]), nh


class Port:
    def __init__(self, sdat):
        self.sdat = sdat
        self.samples = {}

    def sample(self, w, rate):
        x = wave_pcm(w)
        loop = w.loopOffset * (4 if w.waveType == 0 else 2) if w.isLooped else None   # offset in words
        y, l2 = resample_to(x, rate, loop)
        data = np.clip(np.round(y * 128), -128, 127).astype(np.int8).tobytes()
        hdr = struct.pack('<HHIII', 0, 0x4000 if l2 is not None else 0, MIX_RATE * 1024, l2 or 0, len(data))
        blob = hdr + data + (data[l2:l2 + 1] if l2 is not None else b'\0')
        h = hashlib.sha1(blob).hexdigest()[:10]
        self.samples.setdefault(h, ('gEnSfxSample_%s' % h, blob, 'en_sfx/%s.bin' % h))
        return self.samples[h][0]

    def song(self, dseq, player):
        """-> (name, tones, tracks): tracks are lists of (tick, order, kind, value)"""
        name, seq = self.sdat.sequences[dseq]
        bank = self.sdat.banks[seq.bankID][1]
        raw = bytes(seq.eventsData)
        sq = lambda v: (v / 127.0) ** 2          # the DS's volume and velocity curves are squared
        tones = []
        def tone(t):
            if t not in tones:
                tones.append(t)
            return tones.index(t)
        tracks = []
        for start in sseq_tracks(raw).values():
            ev = sseq_events(raw, start)
            if not any(e[1] == 'note' for e in ev):
                continue
            st = dict(vol=127, expr=127, prog=0, transpose=0, bend=0, bendrange=2, release=None, pan=64)
            out = []
            for t, kind, v in ev:
                if kind == 'note':
                    key, vel, dur = v
                    nd = note_definition(bank.instruments[st['prog']], key)
                    rel = st['release'] if st['release'] is not None else nd.release
                    level = sq(st['vol']) * sq(st['expr'])
                    if int(nd.type) == 1:
                        w = self.sdat.waveArchives[bank.waveArchiveIDs[nd.waveArchiveIDID]][1].waves[nd.waveID]
                        semis = key + st['transpose'] - nd.pitch + st['bend'] / 128.0 * st['bendrange']
                        smp = self.sample(w, w.sampleRate * 2 ** (semis / 12))
                        out.append([t, 1, 'note', dict(tone=tone(('pcm', smp, ds_release_to_gba(rel))), key=60,
                                                      velsq=sq(vel), level=level, dur=dur)])
                    elif int(nd.type) == 2:
                        duty = {0: 0, 1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3}[nd.waveID]   # (n+1)/8 -> 12.5/25/50/75 %
                        out.append([t, 1, 'note', dict(tone=tone(('square', duty)), key=key + st['transpose'],
                                                      velsq=sq(vel), level=level, dur=dur, psg=True)])
                    else:
                        raise ValueError('%s: note type %s' % (name, nd.type))
                elif kind in ('vol', 'expr'):
                    st[kind] = v
                    out.append([t, 0, 'level', sq(st['vol']) * sq(st['expr'])])
                elif kind in ('prog', 'transpose', 'release'):
                    st[kind] = v
                elif kind == 'bendrange':
                    st[kind] = v
                elif kind == 'bend':
                    st['bend'] = v
                    out.append([t, 0, 'bend', v])
                elif kind == 'pan':
                    st['pan'] = v
                    out.append([t, 0, 'pan', v])
                elif kind in ('moddepth', 'modspeed', 'modtype', 'moddelay'):
                    out.append([t, 0, kind, v])
                elif kind in ('loopstart', 'loopend'):
                    out.append([t, 2 if kind == 'loopend' else 0, kind, None])
            tracks.append(out)
        maxt = PLAYER_TRACKS[player]
        if len(tracks) > maxt:
            # pair the DS tracks by side; each note keeps its level, the pair sits at its side
            first = lambda tr: min(e[0] for e in tr if e[2] == 'note')
            assert maxt == 2 and all(not any(e[2] in ('bend', 'loopstart') or (e[2] == 'level' and e[0] > first(tr))
                                             for e in tr) for tr in tracks), name
            side = lambda tr: next(e[3] for e in tr if e[2] == 'pan')
            pairs = [[tr for tr in tracks if side(tr) < 64], [tr for tr in tracks if side(tr) >= 64]]
            tracks = []
            for grp, pan in zip(pairs, (16, 112)):
                notes = sorted([e for tr in grp for e in tr if e[2] == 'note'], key=lambda e: e[0])
                for k, e in enumerate(notes):
                    e[3] = dict(e[3], key=60 + k)
                tracks.append([[0, 0, 'pan', pan]] + notes)
        return name, tones, tracks


def note_peaks(tracks):
    """each note's loudest level while it sounds (DS volume changes under it included)"""
    for tr in tracks:
        ev = sorted(tr, key=lambda e: (e[0], e[1]))
        for i, e in enumerate(ev):
            if e[2] != 'note':
                continue
            v = e[3]; end = e[0] + v['dur']; lv = v['level']
            for f in ev[i + 1:]:
                if f[0] >= end or f[2] == 'note':
                    break
                if f[2] == 'level':
                    lv = max(lv, f[3])
            v['peak'] = v['velsq'] * lv


def emit_track(events, first, tempo, vol, peak):
    """m4a bytes of one track. A note gets the velocity of its loudest moment; DS volume
    changes under a sounding note become track volume changes. Notes over 99 ticks are
    tied and ended with EOT. A square note gets the GBA key and bends that give the DS's
    pitch under each DS bend."""
    events = sorted(events, key=lambda e: (e[0], e[1]))
    b = [0xBC, 0x00] + ([0xBB, tempo] if first else []) + [0xBE, vol]
    now = 0; ends = []; cur = dict(tone=None, pan=None, bend=0, vol=vol); loop_at = None
    sounding = None          # (velocity part, peak) of the sounding note
    last_end = 0
    psg_map = {}
    bl = sorted(set([0] + [e[3] for e in events if e[2] == 'bend']))
    for e in events:
        if e[2] == 'note' and e[3].get('psg') and e[3]['key'] not in psg_map:
            gk, gb = square_note(e[3]['key'], bl)
            psg_map[e[3]['key']] = (gk, dict(zip(bl, gb)))
    def until(t):
        nonlocal now
        while ends and ends[0][0] <= t:
            te, k = ends.pop(0)
            b.extend(waits(te - now)); now = te
            b.extend([0xCE, k])
        b.extend(waits(t - now)); now = t
    def set_vol(nv):
        nv = max(0, min(127, round(nv)))
        if nv != cur['vol']:
            b.extend([0xBE, nv]); cur['vol'] = nv
    cur_psg = None
    for t, order, kind, v in events:
        until(t)
        if kind == 'note':
            if cur['tone'] != v['tone']:
                b.extend([0xBD, v['tone']]); cur['tone'] = v['tone']
            set_vol(vol * v['velsq'] * v['level'] / v['peak'])
            key = v['key']
            if v.get('psg'):
                key, cur_psg = psg_map[v['key']]
                b.extend([0xC0, 64 + cur_psg[cur['bend']]])
            vel = max(1, min(127, round(127 * v['peak'] / peak)))
            sounding = (v['velsq'], v['peak'])
            last_end = max(last_end, t + v['dur'])
            if v['dur'] <= 99:
                b.extend(note_cmd(key, vel, v['dur']))
            else:
                b.extend([0xCF, key, vel])
                ends.append((t + v['dur'], key)); ends.sort()
        elif kind == 'level':
            if sounding and t < last_end:
                set_vol(vol * sounding[0] * v / sounding[1])
        elif kind == 'pan':
            if cur['pan'] != v:
                b.extend([0xBF, v]); cur['pan'] = v
        elif kind == 'bend':
            cur['bend'] = v
            if cur_psg is not None:
                b.extend([0xC0, 64 + cur_psg[v]])
        elif kind == 'moddepth':
            b.extend([0xC4, v])
        elif kind == 'modspeed':
            b.extend([0xC2, v])
        elif kind == 'modtype':
            b.extend([0xC5, v])
        elif kind == 'moddelay':
            b.extend([0xC3, min(v, 255)])
        elif kind == 'loopstart':
            loop_at = len(b)
        elif kind == 'loopend':
            return b, loop_at
    until(max([last_end] + [e[0] for e in ends]))   # FINE would cut a note still sounding
    b.append(0xB1)
    return b, None


def song_headers():
    """label -> priority byte of every song header in the sound data"""
    pr = {}
    for fn in ('data/sound_data.s', 'data/sound_data2.s'):
        lines = open(os.path.join(ROOT, fn)).read().split('\n')
        for i, l in enumerate(lines):
            m = re.match(r'(gUnknown_\w+):', l)
            if m and i + 3 < len(lines) and 'priority' in lines[i + 3]:
                pr[m.group(1)] = int(re.search(r'\.byte\s+(\d+)', lines[i + 3]).group(1))
    return pr


def main():
    sdat = sa.SDAT.fromFile(sys.argv[1])
    lv_path = os.path.join(ROOT, 'tools/en/sfx_levels.json')
    levels = json.load(open(lv_path)) if os.path.exists(lv_path) else {'songs': {}}
    offset = levels.get('bgm_offset_db', 4.8)
    prio = song_headers()
    sd_path = os.path.join(ROOT, 'data/sound_data.s')
    sd = open(sd_path).read().split('\n')
    t0 = next(i for i, l in enumerate(sd) if l.startswith('gSongTable:'))
    rows = []
    i = t0 + 1
    while sd[i].strip().startswith('song '):
        rows.append(i); i += 1
    P = Port(sdat)
    asm = ['@ generated by tools/en/port_sfx.py: the DS sound effects', '\t.include "asm/macros.inc"',
           '\t.section en_data, "a"', '']
    report = []
    for g, d in sorted(SONGS.items()):
        m = re.match(r'\s*song (\w+), (\d+), (\d+)(.*)', sd[rows[g]])
        player = int(m.group(2))
        orig = m.group(1)
        mo = re.search(r'\(was (\w+)\)', m.group(4))
        if mo:
            orig = mo.group(1)
        name, tones, tracks = P.song(d, player)
        vol = REF_VOL
        lv = levels['songs'].get(str(g))
        if lv:
            vol = round(REF_VOL * 10 ** (((lv['ds'] - offset) - lv['gba']) / 20))
        if vol > 127:
            report.append('song %d (%s) wants volume %d: 127' % (g, name, vol))
            vol = 127
        note_peaks(tracks)
        peak = max(e[3]['peak'] for tr in tracks for e in tr if e[2] == 'note')
        raw = bytes(sdat.sequences[d][1].eventsData)
        tempo = next((v for t, k, v in sseq_events(raw, sseq_tracks(raw)[0]) if k == 'tempo'), 120)
        sym = 'gEnSfx%03d' % g
        p = prio.get(orig, 127) if orig.startswith('gUnknown') else 127
        asm.append('@ song %d: DS %s, volume %d' % (g, name, vol))
        asm.append('\t.align 2')
        asm.append('%s_voices:' % sym)
        for t in tones:
            if t[0] == 'pcm':
                asm.append('\tvoice_directsound_no_resample 60, 0, %s, 255, 0, 255, %d' % (t[1], t[2]))
            else:
                asm.append('\tvoice_square_2_alt %d, 0, 0, 15, 0' % t[1])
        for k, tr in enumerate(tracks):
            b, loop_at = emit_track(tr, k == 0, tempo, vol, peak)
            asm.append('%s_track%d:' % (sym, k))
            if loop_at is None:
                asm.append('\t.byte ' + ', '.join('0x%02X' % x for x in b))
            else:
                if loop_at:
                    asm.append('\t.byte ' + ', '.join('0x%02X' % x for x in b[:loop_at]))
                asm.append('%s_track%d_loop:' % (sym, k))
                asm.append('\t.byte ' + ', '.join('0x%02X' % x for x in b[loop_at:]) + ', 0xB2')
                asm.append('\t.word %s_track%d_loop' % (sym, k))
        asm += ['\t.align 2', '\t.global %s' % sym, '%s:' % sym,
                '\t.byte %d, 0, %d, 0x80' % (len(tracks), p), '\t.word %s_voices' % sym]
        asm += ['\t.word %s_track%d' % (sym, k) for k in range(len(tracks))]
        asm.append('')
        sd[rows[g]] = '\tsong %s, %d, %d @ English patch: DS %s (was %s)' % (sym, player, int(m.group(3)), name, orig)
    os.makedirs(os.path.join(ROOT, 'sound/direct_sound_samples/en_sfx'), exist_ok=True)
    for h, (symb, blob, fn) in sorted(P.samples.items()):
        open(os.path.join(ROOT, 'sound/direct_sound_samples', fn), 'wb').write(blob)
        asm += ['\t.align 2', '%s:' % symb, '\t.incbin "sound/direct_sound_samples/%s"' % fn]
    open(os.path.join(ROOT, 'data/en_sound.s'), 'w').write('\n'.join(asm) + '\n')
    open(sd_path, 'w').write('\n'.join(sd))
    for r in report:
        print(r)
    print('%d songs, %d samples, %d bytes' % (len(SONGS), len(P.samples), sum(len(v[1]) for v in P.samples.values())))


if __name__ == '__main__':
    main()
