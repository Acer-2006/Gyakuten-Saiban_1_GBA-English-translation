#!/usr/bin/env python3
"""The release patches: one BPS for each version of the Japanese ROM.

usage: make_patches.py ENGLISH.gba OUT_DIR VERSION [REV0.gba] [REV1.gba]

REV0 is the first Japanese release (8 MB, CRC32 c88f0952, No-Intro's
"Gyakuten Saiban (Japan)", what `make` builds from the unpatched
decompilation), REV1 the later "Rev 1" (CRC32 a0f4801f, No-Intro's
"Gyakuten Saiban (Japan) (Rev 1)"); a million bytes of Rev 1 are laid out
differently, so it needs a patch of its own.

REV1 may also be what the decompilation's `make rev1` builds (CRC32
33f29c07). That is not a dump anyone has: the decompilation leaves out 16
bytes of the cartridge (its "Notes about game.txt", item 5). Rev 1's code
is 8 bytes shorter than the first release's, and after two of its function
tables (the last data before the padding, at 0x11daac and 0x11e00c) the
cartridge still has the first release's last two entries, the same
functions 8 bytes on; the decompilation has padding there. They are put
back here from REV0, which has those bytes at the same addresses, and the
result checked against Rev 1's CRC32. (v0.7.54 shipped a Rev 1 patch made
from the decompilation's build, which patchers refused for real Rev 1.) The third patch is for the copy of the
first release that has "DUMPED BY AAA" written over its last 13 bytes
(CRC32 0d9f9697): the patch is made from REV0 with 13 other bytes at the
end (the patch's actions never read them, the target has padding there)
and its source checksum set to that copy's, as bps.py's linear patches
let one do; it has worked for that copy since v0.7.45.

A BPS patch fits only the exact ROM it was made for. Flips refuses any
other and names the checksum it wanted; Rom Patcher JS warns and writes
a file anyway; mGBA's "Load patch" quietly loads the game unpatched, in
Japanese. The README lists the three CRC32s for that reason."""
import os, sys, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bps

TAGGED_CRC = 0x0d9f9697
TAG = b'DUMPED BY AAA'
REV0_CRC, REV1_CRC = 0xc88f0952, 0xa0f4801f
DECOMP_REV1_CRC = 0x33f29c07
REV1_LEFTOVERS = (0x11daac, 0x11e00c)       # 8 bytes each, as REV0 has them


def real_rev1(rev1, rev0):
    """Rev 1 as the cartridge has it, from the decompilation's build"""
    if zlib.crc32(rev1) == DECOMP_REV1_CRC:
        assert rev0 is not None, 'the decompilation\'s Rev 1 needs REV0 for its 16 missing bytes'
        rev1 = bytearray(rev1)
        for p in REV1_LEFTOVERS:
            assert rev1[p:p + 8] == b'\xff' * 8
            rev1[p:p + 8] = rev0[p:p + 8]
        rev1 = bytes(rev1)
    assert zlib.crc32(rev1) == REV1_CRC, 'REV1 is not Rev 1 (CRC32 %08x)' % zlib.crc32(rev1)
    return rev1


def written(f, p):
    print('wrote %s: %d bytes, for a ROM with CRC32 %08x, makes CRC32 %08x'
          % (f, len(p), int.from_bytes(p[-12:-8], 'little'), int.from_bytes(p[-8:-4], 'little')))


def footer(p, source_crc):
    p = bytearray(p)
    p[-12:-8] = source_crc.to_bytes(4, 'little')
    p[-4:] = zlib.crc32(p[:-4]).to_bytes(4, 'little')
    return bytes(p)


def main():
    eng, out, ver = sys.argv[1:4]
    rev0 = open(sys.argv[4], 'rb').read() if len(sys.argv) > 4 else None
    rev1 = open(sys.argv[5], 'rb').read() if len(sys.argv) > 5 else None
    tgt = open(eng, 'rb').read()
    os.makedirs(out, exist_ok=True)
    print('English ROM: %d bytes, CRC32 %08x' % (len(tgt), zlib.crc32(tgt)))
    if rev0 is not None:
        assert zlib.crc32(rev0) == REV0_CRC, 'REV0 is not the first release (CRC32 %08x)' % zlib.crc32(rev0)
        p = bps.create(rev0, tgt)
        assert bps.apply(rev0, p) == tgt
        f = os.path.join(out, 'GS1_English_%s.bps' % ver)
        open(f, 'wb').write(p); written(f, p)
        fake = rev0[:-len(TAG)] + TAG
        q = footer(bps.create(fake, tgt), TAGGED_CRC)
        assert bps.apply(fake, footer(q, zlib.crc32(fake))) == tgt
        f = os.path.join(out, 'GS1_English_%s_tagged-dump.bps' % ver)
        open(f, 'wb').write(q); written(f, q)
    if rev1 is not None:
        rev1 = real_rev1(rev1, rev0)
        p = bps.create(rev1, tgt)
        assert bps.apply(rev1, p) == tgt
        f = os.path.join(out, 'GS1_English_%s_rev1.bps' % ver)
        open(f, 'wb').write(p); written(f, p)


if __name__ == '__main__':
    main()
