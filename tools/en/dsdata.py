"""Access to the English DS (Phoenix Wright: Ace Attorney, USA) data.bin assets.
Point DS_DATA at the extracted data.bin of your own DS dump."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
DS_DATA = os.environ.get('DS_DATA', os.path.join(os.path.dirname(__file__), '..', '..', '..', 'ds_fs', 'data.bin'))
_d = None
def data():
    global _d
    if _d is None:
        _d = open(DS_DATA, 'rb').read()
    return _d

def lz10(src, i=0):
    assert src[i] == 0x10
    size = src[i+1] | src[i+2] << 8 | src[i+3] << 16
    out = bytearray(); i += 4
    while len(out) < size:
        flags = src[i]; i += 1
        for b in range(8):
            if len(out) >= size: break
            if flags & (0x80 >> b):
                x = src[i] << 8 | src[i+1]; i += 2
                ln = (x >> 12) + 3; disp = (x & 0xfff) + 1
                for _ in range(ln): out.append(out[-disp])
            else:
                out.append(src[i]); i += 1
    return bytes(out)

def archive(base):
    d = data(); n = struct.unpack_from('<I', d, base)[0]
    return [(base + o, s) for o, s in (struct.unpack_from('<II', d, base + 4 + 8 * k) for k in range(n))]

def entry(base, i):
    o, s = archive(base)[i]
    d = data()
    return lz10(d, o) if d[o] == 0x10 else d[o:o+s]

# archives (offsets in the US data.bin)
JP_DESC = 0x1ab13d4   # 177 x 128x64 Japanese descriptions
EN_INFO = 0x1ae2ea4   # 177 x 128x64 English info panels
JP_NAME = 0x1b0b10c   # 143 x 128x16 Japanese names
EN_NAME = 0x1b14878   # 143 x 128x16 English names
CHARSET = 0x1bcb374   # 16x16 font

def tiles_to_array(raw, wt, ht):
    """4bpp tiles (row-major) -> 2D list of pixel values"""
    a = [[0] * (wt * 8) for _ in range(ht * 8)]
    for t in range(wt * ht):
        tx, ty = t % wt, t // wt
        for y in range(8):
            for x in range(8):
                b = raw[t * 32 + y * 4 + x // 2]
                a[ty * 8 + y][tx * 8 + x] = (b >> 4) if x & 1 else (b & 15)
    return a

def info_panel(i):
    """English info panel i -> 64 rows x 128 cols of pixel values"""
    raw = entry(EN_INFO, i)
    img = [[0] * 128 for _ in range(64)]
    for m, (x0, y0) in enumerate([(0, 0), (0, 32), (64, 0), (64, 32)]):
        sub = tiles_to_array(raw[m * 1024:(m + 1) * 1024], 8, 4)
        for y in range(32):
            img[y0 + y][x0:x0 + 64] = sub[y]
    return img

def name_plate(i, base=EN_NAME):
    """English name i -> 16 rows x 128 cols"""
    raw = entry(base, i)
    img = [[0] * 128 for _ in range(16)]
    for m in range(4):
        sub = tiles_to_array(raw[m * 256:(m + 1) * 256], 4, 2)
        for y in range(16):
            img[y][m * 32:(m + 1) * 32] = sub[y]
    return img
