"""The DS's frame sequences (the fifth episode's "movies"): archives of
data.bin whose entries are 256-wide 4bpp frames, 32-byte palette first,
RLE (0x30) or LZ (0x10) compressed. movies.py lists them; movies.py ARCHIVE
FRAME out.png decodes one frame."""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from dsdata import data, lz10, tiles_to_array
MOVIES = {0x0: 'Blue Badger dance, 450 frames 256x160, RLE',
          0x1bd418: 'opening (silhouettes, skyline), 329 frames 256x192, RLE',
          0x28d93c: 'security camera footage, 1420 frames 256x192, LZ',
          0x18187b8: 'ending montage, 270 frames 256x192, LZ'}
def rle(src, i=0):
    size = src[i + 1] | src[i + 2] << 8 | src[i + 3] << 16; i += 4; out = bytearray()
    while len(out) < size:
        f = src[i]; i += 1
        if f & 0x80: n = (f & 0x7f) + 3; out += bytes([src[i]]) * n; i += 1
        else: n = f + 1; out += src[i:i + n]; i += n
    return bytes(out)
def entries(base):
    d = data(); n = struct.unpack_from('<I', d, base)[0]
    return [struct.unpack_from('<II', d, base + 4 + 8 * k) for k in range(n)]
def frame(base, k):
    d = data(); o, s = entries(base)[k]; a = base + o
    raw = lz10(d, a) if d[a] == 0x10 else rle(d[a:a + s])
    pal = struct.unpack_from('<16H', raw, 0); px = raw[32:]
    ht = len(px) // (32 * 32)
    cols = [((v & 31) * 8, ((v >> 5) & 31) * 8, ((v >> 10) & 31) * 8) for v in pal]
    from PIL import Image
    arr = tiles_to_array(px, 32, ht)
    im = Image.new('RGB', (256, ht * 8))
    im.putdata([cols[v] for row in arr for v in row])
    return im
if __name__ == '__main__':
    if len(sys.argv) == 1:
        for base, what in MOVIES.items():
            ents = entries(base)
            print('%08x: %s; %d entries, %d bytes compressed' % (base, what, len(ents), sum(s for o, s in ents)))
    else:
        frame(int(sys.argv[1], 16), int(sys.argv[2])).save(sys.argv[3])
