#!/usr/bin/env python3
"""Replace the Japanese voice clips with the English ones from the DS sound archive.
The DS picks these English sounds in English mode (function at 0x02025900 in the
US arm9): GBA SE 0x51->SE0B0, 0x47->SE0B1, 0x39->SE0B2, 0x38->SE0B3, 0x41->SE0B4, 0x37->SE0B5.
usage: port_voices.py DS_sound_data.sdat"""
import sys, os, struct, shutil
import ndspy.soundArchive as sa
ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
VOICES = [  # GBA sample file, DS wave archive, what it is
    ('08071100', 'WAVE_SE0B0', 'Phoenix: Objection!'),
    ('0807F398', 'WAVE_SE0B1', 'Phoenix: Hold it!'),
    ('080BAB20', 'WAVE_SE0B2', 'Payne: Objection!'),
    ('080B5928', 'WAVE_SE0B3', 'Edgeworth: Objection!'),
    ('080BF52C', 'WAVE_SE0B4', 'von Karma: Objection!'),
    ('080B0730', 'WAVE_SE0B5', 'Phoenix: Take that!'),
]
sdat = sa.SDAT.fromFile(sys.argv[1])
wars = dict(sdat.waveArchives)
for gba, ds, what in VOICES:
    w = wars[ds].waves[0]
    assert w.waveType == 0, 'expected 8-bit PCM'
    pcm = bytes(w.data)
    path = os.path.join(ROOT, 'sound/direct_sound_samples/%s.bin' % gba)
    if not os.path.exists(path + '.orig'):
        shutil.copy(path, path + '.orig')
    hdr = struct.pack('<HHIII', 0, 0, w.sampleRate * 1024, 0, len(pcm))
    open(path, 'wb').write(hdr + pcm + b'\0')
    print('%-24s %s  %d Hz  %.2fs' % (what, ds, w.sampleRate, len(pcm) / w.sampleRate))
