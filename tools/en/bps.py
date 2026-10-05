#!/usr/bin/env python3
"""Minimal BPS patch creator/applier (linear: SourceRead + TargetRead).
create: bps.py create SOURCE TARGET OUT.bps
apply:  bps.py apply SOURCE PATCH.bps OUT"""
import sys, zlib
def enc(n):
    out = bytearray()
    while True:
        x = n & 0x7f; n >>= 7
        if n == 0:
            out.append(0x80 | x); break
        out.append(x); n -= 1
    return out
def dec(b, i):
    data, shift = 0, 1
    while True:
        x = b[i]; i += 1
        data += (x & 0x7f) * shift
        if x & 0x80: break
        shift <<= 7; data += shift
    return data, i
def create(src, tgt, meta=b''):
    out = bytearray(b'BPS1') + enc(len(src)) + enc(len(tgt)) + enc(len(meta)) + meta
    i = 0; n = len(tgt)
    while i < n:
        # SourceRead run
        j = i
        while j < n and j < len(src) and src[j] == tgt[j]: j += 1
        if j - i >= 4 or (j == n and j > i):
            out += enc(((j - i - 1) << 2) | 0); i = j; continue
        # TargetRead run until a source match of >= 8 bytes
        j = i
        while j < n:
            k = j
            while k < n and k < len(src) and src[k] == tgt[k] and k - j < 8: k += 1
            if k - j >= 8: break
            j += 1
        out += enc(((j - i - 1) << 2) | 1) + tgt[i:j]; i = j
    out += zlib.crc32(src).to_bytes(4, 'little') + zlib.crc32(tgt).to_bytes(4, 'little')
    out += zlib.crc32(out).to_bytes(4, 'little')
    return bytes(out)
def apply(src, p):
    assert p[:4] == b'BPS1'
    i = 4
    ss, i = dec(p, i); ts, i = dec(p, i); ms, i = dec(p, i); i += ms
    assert zlib.crc32(src) == int.from_bytes(p[-12:-8], 'little'), 'source CRC mismatch (wrong ROM?)'
    out = bytearray(); end = len(p) - 12; srel = trel = 0
    while i < end:
        d, i = dec(p, i); cmd, ln = d & 3, (d >> 2) + 1
        if cmd == 0: out += src[len(out):len(out) + ln]
        elif cmd == 1: out += p[i:i + ln]; i += ln
        elif cmd == 2:
            o, i = dec(p, i); srel += (-1 if o & 1 else 1) * (o >> 1); out += src[srel:srel + ln]; srel += ln
        else:
            o, i = dec(p, i); trel += (-1 if o & 1 else 1) * (o >> 1)
            for _ in range(ln): out.append(out[trel]); trel += 1
    assert zlib.crc32(out) == int.from_bytes(p[-8:-4], 'little'), 'target CRC mismatch'
    return bytes(out)
if __name__ == '__main__':
    if sys.argv[1] == 'create':
        p = create(open(sys.argv[2], 'rb').read(), open(sys.argv[3], 'rb').read())
        open(sys.argv[4], 'wb').write(p); print('patch bytes', len(p))
    else:
        open(sys.argv[4], 'wb').write(apply(open(sys.argv[2], 'rb').read(), open(sys.argv[3], 'rb').read()))
        print('ok')
