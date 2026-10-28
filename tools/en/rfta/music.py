#!/usr/bin/env python3
"""The seven songs Rise from the Ashes added, from the DS's sound archive.

The DS episode brought seven new pieces of music (BGM150-BGM156: the sequences
0x17C-0x182 its script plays). They are DS sequences in the GBA game's style:
the same 48 ticks to a quarter note, the GBA's own samples and square waves for
programs 0-30 and the drums (program 127), and new recordings (programs 31 and
up, IMA-ADPCM at 30-64 kHz). This makes m4a songs of them for the RFTA build
(songs RFTA_SONG_BASE and up):

- Sequences: every track is followed through its calls (95/FD) and jumps (94);
  the jump back that loops it becomes the m4a GOTO. Ticks carry over one to one
  (the tempo byte is the DS's bpm: the DS counts 240 a tick at 192 Hz, the GBA
  150 a tick at 59.73 Hz with the byte doubled, the same rate within 0.4%).
- Levels: the DS squares volume, expression and velocity (its decibel table
  is 40 log10(x/127)); here each note's velocity is its squared velocity and
  the track volume the squared volume times the squared expression, each track
  scaled so its loudest note has velocity 127. MUSIC_GAIN_DB (per song) sets
  the songs' level beside the GBA's own music: made by tools/en/rfta/music_levels.py
  from recordings of both games.
- Envelopes: each track sets attack, decay, sustain and release (D0-D3),
  overriding the instrument's; every combination becomes a voice of its own.
  Decay and release take the DS's rate off the envelope each update (0.1771 dB
  a second a unit, measured: tools/en/port_sfx.py); m4a multiplies by n/256
  each frame. Sustain is squared like the volumes. The attack is matched at
  half amplitude.
- Samples: decoded (ADPCM too), and resampled where the notes play them
  faster than the mixer's 15768 Hz would carry: an instrument whose notes span
  more than an octave is split by key range (an m4a key split), each range
  with its own copy filtered for its highest note. Quiet samples are scaled up
  to use the 8 bits, and the note velocities make up for it.
- The DS's square waves (PSG, programs 9-15) play on the GBA's square and wave
  channels (the GBA's own music has them there; the mixer is spared): each
  square track gets one of the three, chosen so that the fewest notes fall on
  a channel already playing (cgb_channels), with the envelope in the GBA's
  steps and the level measured against the samples (CGB_GAIN).
- Vibrato and tremolo (CA-CD, E0): m4a's LFO is a triangle stepped once a tick,
  the DS's a sine at 192 Hz; speed, depth and delay are converted for the song's
  tempo.

The m4a player for the music gets 16 tracks in the RFTA build (the songs have up
to 16), and the mixer 12 sample channels (the main build's 8; the songs play up
to 14 sampled notes at once). Their voices are of type 0x10, which the RFTA
build's mixer plays without interpolation, the nearest source sample for each
output sample, as the DS's sound hardware does (src/m4a_1.s): a channel then
takes about 5 scanlines a frame to mix, against 7 interpolated. When the
channels are all taken, a note takes one from a quieter track (track priorities
by loudness).

usage: music.py DS_sound_data.sdat
writes data/rfta/music.s and sound/direct_sound_samples/rfta/*.bin"""
import sys, os, struct, hashlib, json, math, itertools
from fractions import Fraction
import numpy as np
from scipy.signal import resample_poly, resample
import ndspy.soundArchive as sa

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, os.path.join(HERE, '..'))
from port_sfx import varlen, waits, LEN, ds_release_to_gba   # noqa: E402

MIX_RATE = 15768
FIRST_SEQ = 0x17C               # BGM150
SONGS = 7
RFTA_SONG_BASE = 113            # the GBA song number of BGM150 (after the 113 songs of the main game)
REVERB = 0x80 | 10              # the GBA's own music's (song headers: 138)
HEADROOM = 2 ** (6 / 12)        # resampled copies may play up to 6 semitones above the mixer's band
BAND = 6                        # keys a resampled copy covers (its lowest note keeps the mixer's full band)
ENV_HZ = 0.1771 * 1280          # DS envelope updates a second (1 unit = 1/1280 dB; see ds_release_to_gba)
LFO_HZ = 191.97                 # DS sound updates a second (LFO counter, LFO delay)
GBA_FPS = 59.7275
LEVELS = os.path.join(HERE, 'music_levels.json')

# ---------------------------------------------------------------- sequences
ONE = {0xC0: 'pan', 0xC1: 'vol', 0xC2: 'mastervol', 0xC3: 'transpose', 0xC4: 'bend', 0xC5: 'bendrange',
       0xC6: 'prio', 0xC7: 'mono', 0xC8: 'tie', 0xC9: 'portakey', 0xCA: 'moddepth', 0xCB: 'modspeed',
       0xCC: 'modtype', 0xCD: 'modrange', 0xCE: 'portaon', 0xCF: 'portatime', 0xD0: 'attack', 0xD1: 'decay',
       0xD2: 'sustain', 0xD3: 'release', 0xD4: 'loopstart', 0xD5: 'expr', 0xD6: 'print'}
TWO = {0xE0: 'moddelay', 0xE1: 'tempo', 0xE3: 'sweep'}
SIGNED = {'bend', 'transpose'}


def seq_tracks(b):
    starts = {}; p = 0
    if b[0] == 0xFE:
        p = 3
    while b[p] == 0x93:
        starts[b[p + 1]] = b[p + 2] | (b[p + 3] << 8) | (b[p + 4] << 16); p += 5
    starts[0] = p
    return dict(sorted(starts.items()))


def seq_events(b, p):
    """one track followed through calls and jumps -> (events, end tick, loop tick or None).
    events: (tick, kind, value); notes take no time (every track is in poly mode)"""
    t = 0; ev = []; seen = {}; calls = []; loops = []
    while True:
        if not calls and p not in seen:
            seen[p] = t
        c = b[p]; q = p + 1
        if c < 0x80:
            vel = b[q]; dur, q = varlen(b, q + 1)
            ev.append((t, 'note', (c, vel, dur)))
        elif c == 0x80:
            d, q = varlen(b, q); t += d
        elif c == 0x81:
            v, q = varlen(b, q); ev.append((t, 'prog', v))
        elif c == 0x94:
            tg = b[q] | (b[q + 1] << 8) | (b[q + 2] << 16)
            if tg in seen:
                return ev, t, seen[tg]
            p = tg; continue
        elif c == 0x95:
            calls.append(q + 3); p = b[q] | (b[q + 1] << 8) | (b[q + 2] << 16); continue
        elif c == 0xFD:
            p = calls.pop(); continue
        elif c in ONE:
            v = b[q]; q += 1; name = ONE[c]
            if name in SIGNED and v > 127:
                v -= 256
            if name == 'mono':
                assert v == 0, 'mono mode'
            elif name == 'loopstart':
                loops.append([q, v])
            elif name in ('tie', 'portakey', 'portaon', 'portatime', 'mastervol', 'print'):
                raise ValueError('SSEQ %s not handled' % name)
            else:
                ev.append((t, name, v))
        elif c in TWO:
            v = struct.unpack_from('<h' if c == 0xE3 else '<H', b, q)[0]; q += 2
            if TWO[c] == 'sweep':
                raise ValueError('SSEQ sweep not handled')
            ev.append((t, TWO[c], v))
        elif c == 0xFC:
            lp = loops[-1]
            assert lp[1] != 0, 'endless D4 loop'
            lp[1] -= 1
            if lp[1] > 0:
                p = lp[0]; continue
            loops.pop()
        elif c == 0xFE:
            q += 2
        elif c == 0xFF:
            return ev, t, None
        else:
            raise ValueError('SSEQ command %02x not handled' % c)
        p = q


# ---------------------------------------------------------------- DS samples and envelopes
IMA_STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80,
            88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544,
            598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749,
            3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487,
            12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767]
IMA_INDEX = [-1, -1, -1, -1, 2, 4, 6, 8]


def adpcm_decode(d):
    pred, idx = struct.unpack_from('<hB', d, 0)
    out = np.empty((len(d) - 4) * 2)
    k = 0
    for byte in d[4:]:
        for n in (byte & 15, byte >> 4):
            step = IMA_STEP[idx]
            diff = step >> 3
            if n & 1: diff += step >> 2
            if n & 2: diff += step >> 1
            if n & 4: diff += step
            pred = max(-0x7FFF, pred - diff) if n & 8 else min(0x7FFF, pred + diff)
            idx = min(88, max(0, idx + IMA_INDEX[n & 7]))
            out[k] = pred; k += 1
    return out / 32768.0


def wave_pcm(w):
    """-> (samples as floats, full scale 1.0; loop start or None)"""
    d = bytes(w.data)
    if w.waveType == 0:
        x = np.frombuffer(d, dtype=np.int8).astype(float) / 128.0; per = 4; head = 0
    elif w.waveType == 1:
        x = np.frombuffer(d, dtype='<i2').astype(float) / 32768.0; per = 2; head = 0
    else:
        x = adpcm_decode(d); per = 8; head = 1
    return x, ((w.loopOffset - head) * per if w.isLooped else None)


ATTACK_SLOW = [0, 1, 5, 14, 26, 38, 51, 63, 73, 84, 92, 100, 109, 116, 123, 127, 132, 137, 143]


def gba_attack(a):
    """DS attack (the attenuation, from -72.3 dB, times m/255 each update) -> m4a attack
    (amplitude + n/255 a frame), matched at half amplitude"""
    if a >= 127:
        return 255
    m = 255 - a if a < 109 else ATTACK_SLOW[127 - a]
    n = math.log(6.02 / 72.3) / math.log(m / 255.0)
    frames = n / ENV_HZ * GBA_FPS
    return max(1, min(255, round(128 / max(frames, 0.5))))


def gba_sustain(s):
    return round(255 * (s / 127.0) ** 2)


def ds_rate_db(v):
    """dB a second the DS takes off for a decay or release value (None: at once)"""
    if v >= 127:
        return None
    rate = 0x3C00 if v == 126 else 0x1E00 / (126 - v) if v >= 50 else 2 * v + 1
    return rate * 0.1771


def _m4a_times(r):
    """m4a's integer envelope from 255 times r/256 a frame: frames to reach -6, -12, ... -36 dB"""
    e = 255; n = 0; out = []
    marks = [255 * 10 ** (-k / 20) for k in (6, 12, 18, 24, 30, 36)]
    while marks and n < 4000:
        e = e * r >> 8; n += 1
        while marks and e <= marks[0]:
            out.append(n); marks.pop(0)
    out += [4000] * len(marks)
    return out
_M4A_TIMES = {r: _m4a_times(r) for r in range(1, 256)}


def gba_fall(v):
    """a DS decay or release value -> the m4a multiplier whose integer envelope falls most like it
    (the frames to -6 ... -36 dB matched: m4a's truncation speeds up its fall at low levels)"""
    db = ds_rate_db(v)
    if db is None:
        return 0
    want = [k / db * GBA_FPS for k in (6, 12, 18, 24, 30, 36)]
    return min(range(1, 256), key=lambda r: sum(abs(math.log((a + 0.5) / (b + 0.5))) for a, b in zip(_M4A_TIMES[r], want)))


def gba_adsr(adsr):
    a, d, s, r = adsr
    return gba_attack(a), gba_fall(d), gba_sustain(s), gba_fall(r)


# The DS's squares on the GBA's square and wave channels (CGB): one note at a time each,
# envelopes in steps of 1/15 every n/64 s, levels measured in mGBA: a square at
# envelope 15 has half the amplitude of a sample at full scale and volume and velocity
# 127 (fundamental 0.49, RMS 0.52), the wave channel the same
CGB_GAIN = 1 / 0.51
DUTY_GBA = {0: 0, 1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 0}     # DS duty (n+1)/8 -> GBA 12.5/25/50/75 % (inverted the same)


def cgb_adsr(adsr):
    """DS attack, decay, sustain, release -> m4a CGB envelope (attack, decay, release: 1/64 s a
    step of 15, 0-7; sustain 0-15), matched for a note at full volume"""
    a, d, s, r = adsr
    s_lin = (s / 127.0) ** 2
    if a >= 127:
        ga = 0
    else:
        m = 255 - a if a < 109 else ATTACK_SLOW[127 - a]
        t_half = math.log(6.02 / 72.3) / math.log(m / 255.0) / ENV_HZ
        ga = max(1, min(7, round(t_half * 64 / 7.5)))
    rd = ds_rate_db(d)
    if rd is None or s >= 127:
        gd = 0
    else:
        target = 40 * math.log10(s / 127.0) if s else -40.0
        steps = 15 * (1 - s_lin) if s else 15
        gd = max(1, min(7, round(-max(target, -40.0) / rd * 64 / max(steps, 1))))
    gs = round(15 * s_lin)
    rr = ds_rate_db(r)
    if rr is None:
        gr = 0
    else:
        steps = 15 * max(s_lin, 0.3) if gd else 15
        gr = max(0, min(7, round(40.0 / rr * 64 / steps)))
    return ga, gd, gs, gr


def cgb_channels(psg):
    """PSG tracks ({track: [(tick, ticks, key)]}) -> {track: 1, 2 or 3} (square 1, square 2,
    wave): the fewest notes sounding over each other on a channel; a track with keys below
    36 (the squares' lowest) on the wave channel, an octave up and its pattern one cycle"""
    tr = sorted(psg)
    clash = {}
    for i, a in enumerate(tr):
        for b in tr[i + 1:]:
            n = 0
            for t0, d0, _ in psg[a]:
                for t1, d1, _ in psg[b]:
                    if t0 < t1 + d1 and t1 < t0 + d0:
                        n += 1
            clash[(a, b)] = n
    low = {a for a in tr if min(k for _, _, k in psg[a]) < 36}
    best = None
    for combo in itertools.product((1, 2, 3), repeat=len(tr)):
        m = dict(zip(tr, combo))
        if any(m[a] != 3 for a in low):
            continue
        cost = sum(n for (a, b), n in clash.items() if m[a] == m[b])
        if best is None or cost < best[0]:
            best = (cost, m)
    if best is None:                  # (more low tracks than the wave channel: all there)
        best = (None, {a: 3 for a in tr})
    return best[1], best[0], low


def resample_loop(x, ratio, loop):
    """x at ratio times its rate (ratio <= 1); a loop resampled as a period of its own"""
    f = Fraction(ratio).limit_denominator(1024)
    if loop is None:
        return resample_poly(x, f.numerator, f.denominator), None
    head, body = x[:loop], x[loop:]
    nb = max(8, round(len(body) * ratio))
    nh = round(len(head) * ratio)
    body2 = resample(body, nb)
    head2 = resample_poly(np.concatenate([head, body, body]), f.numerator, f.denominator)[:nh] if nh else np.zeros(0)
    return np.concatenate([head2, body2]), nh


# ---------------------------------------------------------------- m4a output
def note_bytes(key, vel, d):
    """N command lasting d ticks (1..223): a length from the clock table and a gate extension"""
    k = max(i for i, l in enumerate(LEN) if l <= min(d, 96))
    ext = d - LEN[k]
    assert 0 <= ext < 128
    return [0xCF + k, key, vel] + ([ext] if ext else [])


class Music:
    def __init__(self, sdat):
        self.sdat = sdat
        self.blobs = {}           # hash -> (symbol, bytes)
        self.waves = {}           # wave channel patterns: symbol -> 16 bytes
        self.report = []

    def sample(self, x, loop, rate_at_60):
        """8-bit m4a sample of x (floats) playing at rate_at_60 for key 60 -> (symbol, gain): x is scaled
        to full 8 bits, so 127 stands for `gain` (DS full scale 1.0)"""
        peak = max(1e-9, float(np.max(np.abs(x))))
        y = np.clip(np.round(x / peak * 127), -128, 127).astype(np.int8).tobytes()
        size = len(y)
        if loop is not None:
            hdr = struct.pack('<HHIII', 0, 0x4000, round(rate_at_60 * 1024), loop, size)
            blob = hdr + y + y[loop:loop + 1]
        else:
            hdr = struct.pack('<HHIII', 0, 0, round(rate_at_60 * 1024), 0, size)
            blob = hdr + y + b'\0'
        h = hashlib.sha1(blob).hexdigest()[:10]
        sym = 'gRftaSample_%s' % h
        self.blobs.setdefault(h, (sym, blob))
        return sym, peak

    def note_def(self, bank, prog, key):
        inst = bank.instruments[prog]
        t = type(inst).__name__
        if t == 'SingleNoteInstrument':
            return inst.noteDefinition, ('single', prog)
        if t == 'RangeInstrument':
            return inst.noteDefinitions[key - inst.firstPitch], ('range', prog)
        for i, r in enumerate(inst.regions):
            if key <= r.lastPitch:
                return r.noteDefinition, ('region', prog)
        raise ValueError('no region for key %d' % key)

    def wave(self, bank, nd):
        wa = self.sdat.waveArchives[bank.waveArchiveIDs[nd.waveArchiveIDID]]
        return wa[0], nd.waveID, wa[1].waves[nd.waveID]

    def wave_pattern(self, duty, cycles):
        """the wave channel's 32 samples (4 bits): `cycles` periods of a square of duty (n+1)/8"""
        per = 32 // cycles
        high = round(per * (duty + 1) / 8)
        nib = ([15] * high + [0] * (per - high)) * cycles
        sym = 'gRftaWave_%d_%d' % (duty, cycles)
        self.waves[sym] = bytes((nib[i] << 4) | nib[i + 1] for i in range(0, 32, 2))
        return sym

    def bands(self, keys):
        """used keys -> key ranges of at most BAND keys"""
        keys = sorted(set(keys)); out = []
        for k in keys:
            if out and k - out[-1][0] < BAND:
                out[-1][1] = k
            else:
                out.append([k, k])
        return out

    def pcm_voices(self, bank, nd, keys):
        """sub-voices for a DS note definition played at `keys`: [(lo, hi, sample symbol, gain)]"""
        name, wid, w = self.wave(bank, nd)
        x, loop = wave_pcm(w)
        out = []
        for lo, hi in self.bands(keys):
            # the note's rate at the band's top key; above the mixer's (with headroom): filtered down
            top_rate = w.sampleRate * 2 ** ((hi - nd.pitch) / 12)
            ratio = min(1.0, MIX_RATE * HEADROOM / top_rate)
            if ratio < 0.97:
                y, l2 = resample_loop(x, ratio, loop)
            else:
                ratio = 1.0; y, l2 = x, loop
            rate60 = w.sampleRate * ratio * 2 ** ((60 - nd.pitch) / 12)
            sym, gain = self.sample(y, l2, rate60)
            out.append((lo, hi, sym, gain))
        return out

    def song(self, k):
        seqno = FIRST_SEQ + k
        name, seq = self.sdat.sequences[seqno]
        bank = self.sdat.banks[seq.bankID][1]
        raw = bytes(seq.eventsData)
        tracks = []
        for tn, start in seq_tracks(raw).items():
            ev, end, loop = seq_events(raw, start)
            if any(e[1] == 'note' for e in ev):
                tracks.append((tn, ev, end, loop))
        ends = set(e for _, _, e, _ in tracks)
        loops = set(l for _, _, _, l in tracks)
        assert len(loops) == 1, (name, loops)
        song_end = max(ends)
        song_loop = loops.pop()
        tempo0 = next(v for _, ev, _, _ in tracks for t, kind, v in ev if kind == 'tempo')

        # the squares: which GBA channel each square track plays on
        psg = {}
        for ti, (tn, ev, end, loop) in enumerate(tracks):
            st = dict(prog=0, transpose=0)
            for t, kind, v in ev:
                if kind in st:
                    st[kind] = v
                elif kind == 'note':
                    key = v[0] + st['transpose']
                    nd, _ = self.note_def(bank, st['prog'], key)
                    if int(nd.type) == 2:
                        psg.setdefault(ti, []).append((t, v[2], key))
        cgb, clashes, low = cgb_channels(psg) if psg else ({}, 0, set())
        self.report.append('%s: square tracks %s on %s (%s notes over each other)' % (
            name, sorted(psg), {k: ('sq1', 'sq2', 'wave')[c - 1] for k, c in sorted(cgb.items())}, clashes))

        # pass 1: each note's DS state -> voice keys
        notes_by_voice = {}       # voice key -> set of played keys
        track_notes = []
        self.key_shift = {}
        for ti, (tn, ev, end, loop) in enumerate(tracks):
            st = dict(prog=0, transpose=0, attack=None, decay=None, sustain=None, release=None)
            nn = []
            for t, kind, v in ev:
                if kind in st:
                    st[kind] = v
                elif kind == 'note':
                    key = v[0] + st['transpose']
                    nd, (itype, prog) = self.note_def(bank, st['prog'], key)
                    over = tuple(st[x] for x in ('attack', 'decay', 'sustain', 'release'))
                    if int(nd.type) == 2:
                        adsr = tuple(o if o is not None and o != 255 else d for o, d in
                                     zip(over, (nd.attack, nd.decay, nd.sustain, nd.release)))
                        vk = ('cgb', cgb[ti], nd.waveID, adsr, ti in low)
                        self.key_shift[vk] = 12 if ti in low else 0
                    else:
                        vk = (prog, itype, over)
                    notes_by_voice.setdefault(vk, set()).add(key)
                    nn.append((t, vk, key))
            track_notes.append(nn)

        # voices
        voices = []               # asm lines for the voicegroup
        extra = []                # sub-voicegroups and key split tables
        vindex = {}
        vgain = {}                # (voice key, key) -> gain of the sample that note plays
        sym = 'gRftaSong%d' % (150 + k)
        for vi, (vk, keys) in enumerate(sorted(notes_by_voice.items(), key=lambda kv: str(kv[0]))):
            vindex[vk] = vi
            if vk[0] == 'cgb':
                _, ch, duty, adsr, lowtrack = vk
                a, d, su, r = cgb_adsr(adsr)
                for x in keys:
                    vgain[(vk, x)] = CGB_GAIN
                if ch == 1:
                    voices.append('\tvoice_square_1 0, %d, %d, %d, %d, %d @ square %d/8' % (DUTY_GBA[duty], a, d, su, r, duty + 1))
                elif ch == 2:
                    voices.append('\tvoice_square_2 %d, %d, %d, %d, %d @ square %d/8' % (DUTY_GBA[duty], a, d, su, r, duty + 1))
                else:
                    voices.append('\tvoice_programmable_wave %s, %d, %d, %d, %d @ square %d/8%s' % (
                        self.wave_pattern(duty, 1 if lowtrack else 2), a, d, su, r, duty + 1, ', an octave up' if lowtrack else ''))
                continue
            prog, itype, over = vk
            inst = bank.instruments[prog]

            def env(nd):
                adsr = tuple(o if o is not None and o != 255 else d for o, d in
                             zip(over, (nd.attack, nd.decay, nd.sustain, nd.release)))
                return gba_adsr(adsr)
            if itype == 'range':
                # drums: an m4a key split for every key (keysplit_all), each sub-voice its key
                lo = min(keys); hi = max(keys)
                sub = '%s_v%d_keys' % (sym, vi)
                extra += ['\t.align 2', '%s:' % sub]
                for key in range(lo, hi + 1):
                    nd = inst.noteDefinitions[key - inst.firstPitch]
                    if key not in keys or int(nd.type) != 1:
                        extra.append('\tvoice_square_1 0, 2, 0, 0, 15, 0')   # (not played)
                        continue
                    (l2, h2, smp, g), = self.pcm_voices(bank, nd, [key])
                    vgain[(vk, key)] = g
                    a, d, s, r = env(nd)
                    pan = 0 if nd.pan == 64 else max(1, min(127, nd.pan))     # (macro: 0x80 | pan, a drum's own pan)
                    extra.append('\t.byte 0x10\n\t_voice_directsound %d, %d, %s, %d, %d, %d, %d' % (key, pan, smp, a, d, s, r))
                voices.append('\tvoice_keysplit_all %s-%d @ program %d, drums' % (sub, 12 * lo, prog))
                continue
            # melodic: sub-voices per (note definition, band)
            subs = []             # (lo, hi, line)
            if itype == 'single':
                regions = [(0, 127, inst.noteDefinition)]
            else:
                regions = []; lo = 0
                for r in inst.regions:
                    regions.append((lo, r.lastPitch, r.noteDefinition)); lo = r.lastPitch + 1
            for rlo, rhi, nd in regions:
                ks = [x for x in keys if rlo <= x <= rhi]
                if not ks:
                    continue
                a, d, s, r = env(nd)
                if int(nd.type) == 1:
                    parts = self.pcm_voices(bank, nd, ks)
                else:
                    raise ValueError('%s: program %d note type %d' % (name, prog, int(nd.type)))
                for plo, phi, smp, g in parts:
                    for x in ks:
                        if plo <= x <= phi:
                            vgain[(vk, x)] = g
                    subs.append((plo, phi, '\t.byte 0x10\n\t_voice_directsound 60, 0, %s, %d, %d, %d, %d' % (smp, a, d, s, r)))
            if len(subs) == 1:
                voices.append(subs[0][2] + ' @ program %d' % prog)
                continue
            sub = '%s_v%d_split' % (sym, vi)
            tab = '%s_v%d_table' % (sym, vi)
            extra += ['\t.align 2', '%s:' % sub] + [l for _, _, l in subs]
            table = [0] * 128
            for i, (plo, phi, _) in enumerate(subs):
                # keys between ranges go to the nearer one (none is played)
                for x in range(128):
                    if x >= plo:
                        table[x] = i
            extra += ['%s:' % tab] + ['\t.byte ' + ', '.join(str(v) for v in table[i:i + 16]) for i in range(0, 128, 16)]
            voices.append('\tvoice_keysplit %s, %s @ program %d, %d ranges' % (sub, tab, prog, len(subs)))

        # pass 2: tracks -> m4a
        self.cur_vindex = vindex
        levels = json.load(open(LEVELS)) if os.path.exists(LEVELS) else {}
        gain_db = levels.get(name, {}).get('gain_db', 0.0)
        G = (seq.volume / 127.0) ** 2 * 10 ** (gain_db / 20)
        sq = lambda v: (v / 127.0) ** 2
        # track priorities: when the 10 sample channels are taken, a note takes one from a
        # quieter track (the loudest track 40, then down by one; m4a's own rule, equal
        # priorities, would favour the first tracks); sound effects (80 and up) stay above
        mean = []
        for tn, ev, end, loop in tracks:
            st = dict(vol=127, expr=127); lv = []
            for t, kind, v in ev:
                if kind in st:
                    st[kind] = v
                elif kind == 'note':
                    lv.append(sq(st['vol']) * sq(st['expr']) * sq(v[1]))
            mean.append(sum(lv) / len(lv))
        order = sorted(range(len(tracks)), key=lambda i: -mean[i])
        prio = {i: 40 - r for r, i in enumerate(order)}
        out_tracks = []
        clipped = 0
        for ti, ((tn, ev, end, loop), nn) in enumerate(zip(tracks, track_notes)):
            self.cur_prio = prio[ti]
            # the track's loudest note (squared velocity times its sample's gain) gets velocity 127
            gains = {}
            for (t, vk, key) in nn:
                gains[(t, key)] = vgain[(vk, key)]
            K = max(sq(v[1]) * gains[(t, v[0] + tr)] for t, kind, v, tr in self.with_transpose(ev) if kind == 'note')
            b, nclip = self.emit(ev, nn, gains, K, G, end, loop, tempo0 if tn == tracks[0][0] else None)
            clipped += nclip
            out_tracks.append(b)
        if clipped:
            self.report.append('%s: %d volume settings over 127' % (name, clipped))
        lines = ['@ %s (DS sequence 0x%X), song %d' % (name, seqno, RFTA_SONG_BASE + k), '\t.align 2',
                 '%s_voices:' % sym] + voices + extra
        for i, b in enumerate(out_tracks):
            lines += self.track_asm('%s_track%d' % (sym, i), b)
        lines += ['\t.align 2', '\t.global %s' % sym, '%s:' % sym,
                  '\t.byte %d, 0, 0, %d' % (len(out_tracks), REVERB), '\t.word %s_voices' % sym]
        lines += ['\t.word %s_track%d' % (sym, i) for i in range(len(out_tracks))]
        lines.append('')
        return name, lines, dict(tracks=len(out_tracks), voices=len(voices), loop=song_loop, end=song_end)

    @staticmethod
    def with_transpose(ev):
        tr = 0
        for t, kind, v in ev:
            if kind == 'transpose':
                tr = v
            yield t, kind, v, tr

    def emit(self, ev, nn, gains, K, G, end, loop, tempo):
        """m4a bytes of one track; ('LOOP',) marks where the GOTO goes back to"""
        b = [0xBC, 0x00, 0xBA, self.cur_prio]
        if tempo:
            b += [0xBB, tempo]
        cur = {}
        nclip = 0
        st = dict(vol=127, expr=127)
        sq = lambda v: (v / 127.0) ** 2
        now = 0
        ties = []                 # (end tick, key)
        notes = iter(nn)
        tempo_now = tempo or 0

        def put(cmd, v):
            if cur.get(cmd) != v:
                b.extend([cmd, v]); cur[cmd] = v

        def until(t):
            nonlocal now
            while ties and ties[0][0] <= t:
                te, key = ties.pop(0)
                b.extend(waits(te - now)); now = te
                b.extend([0xCE, key])
            b.extend(waits(t - now)); now = t

        def set_vol():
            nonlocal nclip
            v = 127 * G * sq(st['vol']) * sq(st['expr']) * K
            if v > 127.5:
                nclip += 1
            put(0xBE, max(0, min(127, round(v))))

        evs = sorted(ev, key=lambda e: (e[0], e[1] == 'note'))
        looped = False
        for t, kind, v, tr in self.with_transpose(evs):
            if loop is not None and not looped and loop <= t:
                until(loop)
                b.append('LOOP'); looped = True
                cur.clear()           # after the GOTO the state is the loop end's: set everything again
                set_vol()
            until(t)
            if kind == 'note':
                key, vel, dur = v
                key += tr
                tt, vk, key2 = next(notes)
                assert (tt, key2) == (t, key)
                put(0xBD, self.cur_vindex[vk])
                set_vol()
                g = gains[(t, key)]
                velo = max(1, min(127, round(127 * sq(vel) * g / K)))
                key += self.key_shift.get(vk, 0)
                if dur <= 223:
                    b.extend(note_bytes(key, velo, dur))
                else:
                    if loop is not None and t < end < t + dur:
                        dur = end - t
                        self.report.append('a tied note cut at the loop')
                    b.extend([0xCF, key, velo])
                    ties.append((t + dur, key)); ties.sort()
            elif kind in ('vol', 'expr'):
                st[kind] = v; set_vol()
            elif kind == 'pan':
                put(0xBF, max(0, min(127, v)))
            elif kind == 'bend':
                put(0xC0, max(0, min(127, 64 + round(v / 2))))
            elif kind == 'bendrange':
                put(0xC1, v)
            elif kind == 'tempo':
                if v != tempo_now:
                    b.extend([0xBB, v]); tempo_now = v
            elif kind == 'moddepth':
                st['moddepth'] = v; self.put_mod(put, st)
            elif kind == 'modtype':
                st['modtype'] = v; self.put_mod(put, st)
            elif kind == 'modrange':
                st['modrange'] = v; self.put_mod(put, st)
            elif kind == 'modspeed':
                st['modspeed'] = v; self.put_mod(put, st)
            elif kind == 'moddelay':
                st['moddelay'] = v; self.put_mod(put, st)
            elif kind == 'prio':
                pass                  # (two tracks of BGM154; m4a's own allocation does)
            elif kind in ('prog', 'transpose', 'attack', 'decay', 'sustain', 'release'):
                pass                  # in the voice
            else:
                raise ValueError(kind)
        if loop is not None and not looped:
            until(loop); b.append('LOOP'); cur.clear()
        until(end)
        return b, nclip

    def put_mod(self, put, st):
        depth = st.get('moddepth', 0); typ = st.get('modtype', 0); rng = st.get('modrange', 1)
        speed = st.get('modspeed', 16); delay = st.get('moddelay', 10)
        bpm = self.cur_tempo
        if typ == 0:              # pitch: DS +-depth*range/129 semitones, m4a +-mod/16
            mod = depth * rng * 16 / 129.0
        elif typ == 1:            # volume: DS +-0.0465*depth*range dB, m4a x(1 +- mod/128)
            mod = 128 * (10 ** (0.0465 * depth * rng / 20) - 1)
        else:                     # pan: DS +-depth*range/2 (of 128), m4a +-mod (of 256)
            mod = depth * rng
        put(0xC5, min(typ, 2))
        put(0xC4, max(0, min(127, round(mod))))
        # DS: a sine of 512/speed updates; m4a: a triangle of 256/lfos ticks (0.8 * bpm ticks a second)
        if speed:
            put(0xC2, max(1, min(255, round(256 * speed * LFO_HZ / 512 / (0.8 * bpm)))))
        put(0xC3, max(0, min(255, round(delay / LFO_HZ * 0.8 * bpm))))

    @staticmethod
    def track_asm(label, b):
        lines = ['%s:' % label]
        if 'LOOP' in b:
            i = b.index('LOOP')
            if i:
                lines += Music.byte_lines(b[:i])
            lines.append('%s_loop:' % label)
            lines += Music.byte_lines(b[i + 1:] + [0xB2])
            lines.append('\t.word %s_loop' % label)
        else:
            lines += Music.byte_lines(b + [0xB1])
        return lines

    @staticmethod
    def byte_lines(b):
        return ['\t.byte ' + ', '.join('0x%02X' % x for x in b[i:i + 16]) for i in range(0, len(b), 16)]


def main():
    sdat = sa.SDAT.fromFile(sys.argv[1])
    M = Music(sdat)
    asm = ['@ generated by tools/en/rfta/music.py: the songs Rise from the Ashes added (DS BGM150-156)',
           '\t.include "asm/macros.inc"', '\t.section rfta_data, "a"', '']
    info = []
    for k in range(SONGS):
        name, seq = sdat.sequences[FIRST_SEQ + k]
        M.cur_tempo = next(v for t, kind, v in seq_events(bytes(seq.eventsData), seq_tracks(bytes(seq.eventsData))[0])[0]
                           if kind == 'tempo')
        name, lines, inf = M.song(k)
        asm += lines
        info.append('%s: %s' % (name, inf))
    for sym, pat in sorted(M.waves.items()):
        asm += ['\t.align 2', '%s:' % sym, '\t.byte ' + ', '.join('0x%02X' % x for x in pat)]
    os.makedirs(os.path.join(ROOT, 'sound/direct_sound_samples/rfta'), exist_ok=True)
    for h, (sym, blob) in sorted(M.blobs.items()):
        fn = 'sound/direct_sound_samples/rfta/%s.bin' % h
        open(os.path.join(ROOT, fn), 'wb').write(blob)
        asm += ['\t.align 2', '%s:' % sym, '\t.incbin "%s"' % fn]
    open(os.path.join(ROOT, 'data/rfta/music.s'), 'w').write('\n'.join(asm) + '\n')
    for l in info + M.report:
        print(l)
    print('%d samples, %d bytes' % (len(M.blobs), sum(len(b) for _, b in M.blobs.values())))


if __name__ == '__main__':
    main()
