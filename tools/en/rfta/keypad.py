#!/usr/bin/env python3
"""The safe's keypad (the DS's 74 8 34: Chief Gant's safe on Day 3, the code
7777777), from the DS, for src/en_keypad.c.

What the DS does (its code at 0x020791dc-0x0207b200, the LCD's at
0x0206c4f8-0x0206cbd0; its state at 0x02318f68-0x02319070):
- the device: its top (the LCD, a 256 x 192 bitmap at data.bin 0x2f3e418,
  256 colours at 0x2f3e1f8) on the top screen, its keypad on the touch
  screen (background 0xdc's lower half); the keys are sprites, the US
  build's textures (0x2f3bd88, 0x2b4 bytes a key, 1-9 and 0; the Back
  Space key 0x2f3dd44): 32 x 32 (64 x 32), five palettes, of which the
  first three are the key dark, lit and pressed;
- the LCD's pictures (a table at 0x0206d1c0: data.bin offsets): the
  digits (1-9, 0), the cursor, a blank, the six of the segment that runs
  round a digit as it is checked (22 x 33: 0 clear, 1 and 2 the ink, 99
  the LCD's green), the bars over and under it (20 x 4), the messages
  (154 x 16: the US build's "Input code.", "Code confirmed. Access
  granted.", "Code input error."), the LED (8 x 8: off, in the bitmap's
  colours; red and green in 16 at 0x2f3e3f8);
- the code (0x020c91e8): seven key numbers, 6 ("7");
- what it does (frames): "Input code." blinks (20 shown, 20 not) for 60,
  then the keys light one by one, four frames apart (SE 0x1ae); then the
  player's turn: the cursor under the next digit (shown while the LCD's
  60-frame clock is under 40), a key pressed (orange while it is held, SE
  0x1af; Back Space 0x1b0) puts its digit in; at the seventh the keys go
  dark and, 60 frames on, the check: a digit every 21 frames (SE 0x1b1),
  the segment running round it (a picture every 10 frames of the clock)
  between its bars, the LED green while the clock is under 50, then the
  seven blinking (shown under 50) for six steps more; then the code
  compared: at the clock's 0 the message ("Code confirmed..." with the LED
  red, or "Code input error."), 30 frames in SE 0x1b3 (or 0x1b2), 120 in
  the fade; the right code shows the safe (background 0xe1) and its
  handle turning a quarter about the dial (64 frames; a sprite at 0x1ab12b4,
  colours 0x1ab1294), 60 frames more, the fade; Gant's office (0x74), the
  section after (11E; the wrong code 11D).

On the GBA (src/en_keypad.c) the device is one screen: its top (the LCD,
at the DS's size) over its keypad, the keys in two rows (1-6, 7-9 0 and
Back Space) at the DS's size; the + pad moves a cursor over the keys, A
presses one, B is Back Space.

Writes graphics/en/rfta/keypad.bin, data/rfta/keypad.s (section rfta_low)
and src/data/en_rfta_keypad.h. usage: keypad.py [--preview FILE]"""
import os, sys, struct, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import dsbin
from dsdata import data
ROOT = os.path.join(HERE, '..', '..', '..')

LCD_BITMAP, LCD_COLOURS, LED_COLOURS = 0x2f3e418, 0x2f3e1f8, 0x2f3e3f8
PICTURES = 0x0206d1c4             # (data.bin offset, sheet offset) pairs: the LCD's 22 x 33 pictures
GLYPH_W, GLYPH_H = 22, 33
GLYPH_BYTES = GLYPH_W * GLYPH_H
GLYPHS = 18                       # 1-9, 0, the cursor, the blank, the segment's six
BLANK = 11
BARS = (0x2f4d808, 0x2f4d858)     # 20 x 4: over a digit, under it (and a blank: 99s)
MESSAGES = (0x2f4f588, 0x2f4ff28, 0x2f508c8)   # 154 x 16, the US build's
MESSAGE_W, MESSAGE_H = 154, 16
LEDS = (0x2f4c638, 0x2f4c678, 0x2f4c6b8)       # off (the bitmap's colours), red, green (LED_COLOURS)
KEYS = [0x2f3bd88 + 0x2b4 * k for k in range(10)] + [0x2f3dd44]
KEY_DARK, KEY_LIT, KEY_PRESSED = 0, 1, 2
CODE = 0x020c91e8
HANDLE, HANDLE_COLOURS = 0x1ab12b4, 0x1ab1294  # 16 x 32 4bpp
HANDLE_PIVOT, HANDLE_RADIUS = (201, 79), 29     # the dial, on the DS's top screen; the handle's middle from it
# the safe's own light, red while the handle turns (the DS draws it over the
# background's corner of the safe's display: read off its screen, 8 x 8 at
# (128, 60) on the top screen)
SAFE_LIGHT_AT = (128, 60)
SAFE_LIGHT = ['.8......', '.b66643.', '.a999521', '.a9ac5..', '.a9c957.', 'da55547.', '..22217.', '........']
SAFE_LIGHT_COLOURS = [(16, 0, 0), (48, 0, 0), (48, 24, 24), (80, 16, 16), (128, 0, 0), (144, 24, 24), (152, 176, 128),
                      (160, 144, 144), (192, 0, 0), (192, 144, 144), (192, 168, 168), (208, 40, 48), (208, 192, 200)]
DS_GREEN, DS_INK = 99, (1, 2)
INK = [(56, 56, 56), (120, 152, 120)]           # the ink's two as the DS shows them
SAFE_BG, OFFICE_BG = 0xE1, 0x74
SECTION_RIGHT, SECTION_WRONG = 0x11E, 0x11D
SES = (0x1AE, 0x1AF, 0x1B0, 0x1B1, 0x1B2, 0x1B3)   # light, key, Back Space, check, wrong, right

# the GBA's screen: the DS's top screen from (8, 58), its LCD where it is
DX, DY = 8, 58
LCD_TILES = (5, 1, 25, 8)         # the LCD's tiles (x0, y0, x1, y1): drawn into as it changes
TOP_ROWS = 76                     # the top's rows on the GBA (the DS's 58-134)
KEY_X, KEY_Y = 24, 86             # the keys: two rows of six cells (32 x 32), the Back Space key two
CURSOR = (248, 216, 32), (176, 112, 0)


def u32(a):
    return dsbin.u32(a)


def rgb(c):
    return ((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31)


def rgb5(c):
    r, g, b = (int(v) for v in c)       # (numpy's bytes would overflow)
    return (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10


def colours(off, n):
    return [rgb(c) for c in struct.unpack_from('<%dH' % n, data(), off)]


def lcd_bitmap():
    d = data()
    return np.frombuffer(d[LCD_BITMAP:LCD_BITMAP + 256 * 192], np.uint8).reshape(192, 256), colours(LCD_COLOURS, 256)


def pictures():
    """the LCD's sheet: the 22 x 33 pictures by number (the blank: all green)"""
    d = data()
    out = [np.full((GLYPH_H, GLYPH_W), DS_GREEN, np.uint8) for _ in range(GLYPHS)]
    a = PICTURES
    src = u32(a)
    out[0] = np.frombuffer(d[src:src + GLYPH_BYTES], np.uint8).reshape(GLYPH_H, GLYPH_W)
    a += 4
    while True:
        dst, src = u32(a), u32(a + 4)
        if not (0 < dst < GLYPH_BYTES * GLYPHS and dst % GLYPH_BYTES == 0 and 0x2f00000 <= src < 0x3000000):
            break
        out[dst // GLYPH_BYTES] = np.frombuffer(d[src:src + GLYPH_BYTES], np.uint8).reshape(GLYPH_H, GLYPH_W)
        a += 8
    assert not (out[BLANK] != DS_GREEN).any()
    return out


def bars():
    d = data()
    out = [np.frombuffer(d[o:o + 80], np.uint8).reshape(4, 20) for o in BARS]
    return out + [np.full((4, 20), DS_GREEN, np.uint8)]


def messages():
    d = data()
    return [np.frombuffer(d[o:o + MESSAGE_W * MESSAGE_H], np.uint8).reshape(MESSAGE_H, MESSAGE_W) for o in MESSAGES]


def tex2d(off):
    """a 4bpp texture: (indices h x w, palettes: lists of 16 BGR555)"""
    d = data()
    fmt, wl, hl, fl, doff, dsz, poff, psz = struct.unpack_from('<4B4I', d, off)
    assert fmt == 3
    w, h = 8 << wl, 8 << hl
    idx = np.frombuffer(d[off + doff:off + doff + dsz], np.uint8)
    px = np.stack([idx & 15, idx >> 4], 1).reshape(h, w)
    pals = [list(struct.unpack_from('<16H', d, off + poff + 32 * p)) for p in range(psz // 32)]
    return px, pals


def keys():
    out = [tex2d(o) for o in KEYS]
    assert all(p == out[0][1] for _, p in out)
    return [px for px, _ in out], out[0][1]


def code():
    return list(dsbin.data()[CODE - dsbin.BASE:CODE - dsbin.BASE + 7])


def handle():
    d = data()
    t = np.frombuffer(d[HANDLE:HANDLE + 256], np.uint8)
    return bytes(t), list(struct.unpack_from('<16H', d, HANDLE_COLOURS))


def key_at(k):
    """key k's cell on the GBA (its top left)"""
    return KEY_X + 32 * (k % 6), KEY_Y + 32 * (k // 6)


def screen():
    """the GBA's picture (RGB): the device's top (the LCD) over the
    keypad's two rows in their frame, on the device's metal"""
    bmp, pal = lcd_bitmap()
    top = np.array(pal, np.uint8)[bmp]
    a = np.zeros((160, 240, 3), np.uint8)
    a[:TOP_ROWS] = top[DY:DY + TOP_ROWS, DX:DX + 240]
    rows = list(range(DY + TOP_ROWS, 192))
    rows += list(range(DY + TOP_ROWS + 6, DY + TOP_ROWS + 6 + 160 - TOP_ROWS - len(rows)))
    a[TOP_ROWS:] = top[rows, DX:DX + 240]
    # the keypad's frame (the DS's: a sunken panel round a black one)
    kx0, ky0, kx1, ky1 = KEY_X, KEY_Y, KEY_X + 192, KEY_Y + 64
    ix0, iy0, ix1, iy1 = kx0 - 18, ky0 - 8, kx1 + 18, ky1 + 7
    a[iy0, ix0:ix1] = (160, 160, 160); a[iy0 + 1, ix0 + 1:ix1] = (136, 136, 136)
    a[iy0:iy1, ix0] = (176, 176, 176); a[iy0 + 1:iy1, ix0 + 1] = (152, 152, 152)
    a[iy1 - 2, ix0 + 1:ix1] = (248, 248, 248); a[iy1 - 1, ix0:ix1] = (240, 240, 240)
    a[iy0:iy1, ix1 - 2] = (248, 248, 248); a[iy0:iy1, ix1 - 1] = (248, 248, 248)
    a[ky0 - 3, kx0 - 3:kx1 + 2] = (96, 96, 96)
    a[ky0 - 3:ky1 + 2, kx0 - 3] = (112, 112, 112)
    a[ky0 - 2:ky1 + 2, kx0 - 2:kx1 + 2] = (16, 16, 16)
    a[ky1 + 2, kx0 - 3:kx1 + 3] = (248, 248, 248)
    a[ky0 - 3:ky1 + 3, kx1 + 2] = (248, 248, 248)
    return a


def build(a):
    """the picture as 8bpp tiles: the LCD's (first, in its rows), the rest
    (each once); the colours (0: the backdrop; the LCD's green and ink kept
    exact); the 30 x 20 map"""
    bmp, pal = lcd_bitmap()
    keep = [tuple(pal[DS_GREEN])] + INK
    cols = keep + sorted(set(map(tuple, a.reshape(-1, 3))) - set(keep))
    while len(cols) > 255:
        # (the two nearest colours, past the kept, made one)
        P = np.array(cols[len(keep):], float)
        dd = ((P[:, None] - P[None]) ** 2).sum(2); np.fill_diagonal(dd, 1e9)
        i, j = np.unravel_index(np.argmin(dd), dd.shape)
        drop = cols[len(keep) + max(i, j)]
        into = cols[len(keep) + min(i, j)]
        a[(a == drop).all(2)] = into
        cols.remove(drop)
    index = {c: k + 1 for k, c in enumerate(cols)}
    img = np.zeros((160, 240), np.uint8)
    for c, k in index.items():
        img[(a == c).all(2)] = k
    tiles, seen, tmap = [], {}, [0] * 600
    x0, y0, x1, y1 = LCD_TILES
    for ty in range(y0, y1):
        for tx in range(x0, x1):
            tmap[ty * 30 + tx] = len(tiles); tiles.append(img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].copy())
    for ty in range(20):
        for tx in range(30):
            if x0 <= tx < x1 and y0 <= ty < y1:
                continue
            t = img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].copy()
            key = t.tobytes()
            if key not in seen:
                seen[key] = len(tiles); tiles.append(t)
            tmap[ty * 30 + tx] = seen[key]
    return tiles, tmap, [(0, 0, 0)] + cols, index


def tiles4(img):
    h, w = img.shape
    out = bytearray()
    for ty in range(h // 8):
        for tx in range(w // 8):
            for row in img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]:
                for x in range(0, 8, 2):
                    out.append(int(row[x]) | int(row[x + 1]) << 4)
    return bytes(out)


def cursor(w):
    img = np.zeros((32, w), np.uint8)
    img[0, :] = img[-1, :] = 2; img[:, 0] = img[:, -1] = 2
    img[1, 1:-1] = img[-2, 1:-1] = 1; img[1:-1, 1] = img[1:-1, -2] = 1
    return img


def main():
    preview = sys.argv[sys.argv.index('--preview') + 1] if '--preview' in sys.argv else None
    from sfx import NEW_SES
    a = screen()
    tiles, tmap, cols, index = build(a)
    _, pal = lcd_bitmap()
    green, dark, mid = index[tuple(pal[DS_GREEN])], index[INK[0]], index[INK[1]]
    def ink(img):
        out = np.zeros(img.shape, np.uint8)
        out[img == DS_GREEN] = green; out[img == 1] = dark; out[img == 2] = mid
        return out
    blob = bytearray()
    defs = []
    def add(name, b, note=''):
        while len(blob) % 4:
            blob.append(0)
        defs.append('#define KEYPAD_GFX_%s 0x%X%s' % (name, len(blob), ('  // ' + note) if note else ''))
        blob.extend(b)
    add('TILES', b''.join(bytes(t.reshape(-1)) for t in tiles), '8bpp: the LCD\'s first')
    add('MAP', struct.pack('<600H', *tmap), '30 x 20')
    add('PICTURES', b''.join(bytes(ink(g).reshape(-1)) for g in pictures()), '22 x 33 each: 0 clear, else the colour')
    add('BARS', b''.join(bytes(ink(b).reshape(-1)) for b in bars()), '20 x 4: over, under, blank')
    add('MESSAGES', b''.join(bytes(ink(m).reshape(-1)) for m in messages()), '154 x 16')
    kpx, kpals = keys()
    add('KEYS', b''.join(tiles4(px) for px in kpx), '4bpp: ten 32 x 32, Back Space 64 x 32')
    leds = []
    d = data()
    for o in LEDS[1:]:
        leds.append(np.frombuffer(d[o:o + 64], np.uint8).reshape(8, 8))
    add('LEDS', b''.join(tiles4(l) for l in leds), '8 x 8: red, green')
    add('CURSOR', tiles4(cursor(32)) + tiles4(cursor(64)), '32 x 32, 64 x 32')
    htiles, hpal = handle()
    add('HANDLE', htiles, '16 x 32')
    light = np.array([[0 if c == '.' else int(c, 16) for c in row] for row in SAFE_LIGHT], np.uint8)
    add('SAFE_LIGHT', tiles4(light), '8 x 8')
    h = ['// generated by tools/en/rfta/keypad.py: the safe\'s keypad, from the DS']
    h += defs
    h += ['#define KEYPAD_TILE_COUNT %d' % len(tiles),
          '#define KEYPAD_COLOURS %d' % len(cols),
          '#define KEYPAD_LCD_X0 %d' % LCD_TILES[0], '#define KEYPAD_LCD_Y0 %d' % LCD_TILES[1],
          '#define KEYPAD_LCD_W %d       // tiles' % (LCD_TILES[2] - LCD_TILES[0]),
          '#define KEYPAD_LCD_H %d' % (LCD_TILES[3] - LCD_TILES[1]),
          '#define KEYPAD_DIGIT_X %d     // the first digit (each 22 on), on the screen' % (0x33 - DX),
          '#define KEYPAD_DIGIT_Y %d' % (0x50 - DY),
          '#define KEYPAD_BAR_X %d' % (0x34 - DX),
          '#define KEYPAD_BAR_TOP %d' % (0x4C - DY), '#define KEYPAD_BAR_BOTTOM %d' % (0x70 - DY),
          '#define KEYPAD_MESSAGE_X %d' % (0x33 - DX), '#define KEYPAD_MESSAGE_Y %d' % (0x58 - DY),
          '#define KEYPAD_LED_X %d' % (0x24 - DX), '#define KEYPAD_LED_Y %d' % (0x47 - DY),
          '#define KEYPAD_KEY_X %d' % KEY_X, '#define KEYPAD_KEY_Y %d' % KEY_Y,
          '#define KEYPAD_GLYPH_W %d' % GLYPH_W, '#define KEYPAD_GLYPH_H %d' % GLYPH_H,
          '#define KEYPAD_MESSAGE_W %d' % MESSAGE_W, '#define KEYPAD_MESSAGE_H %d' % MESSAGE_H,
          '#define KEYPAD_GLYPH_CURSOR 10', '#define KEYPAD_GLYPH_BLANK %d' % BLANK, '#define KEYPAD_GLYPH_SEGMENT 12',
          '#define KEYPAD_HANDLE_X %d     // the dial, on the GBA\'s safe (the background as the GBA cuts it)' % (HANDLE_PIVOT[0] - 8),
          '#define KEYPAD_HANDLE_Y %d' % (HANDLE_PIVOT[1] - 16),
          '#define KEYPAD_HANDLE_R %d' % HANDLE_RADIUS,
          '#define KEYPAD_SAFE_LIGHT_X %d' % (SAFE_LIGHT_AT[0] - 8), '#define KEYPAD_SAFE_LIGHT_Y %d' % (SAFE_LIGHT_AT[1] - 16),
          '#define KEYPAD_SAFE_BG 0x%02X' % SAFE_BG, '#define KEYPAD_OFFICE_BG 0x%02X' % OFFICE_BG,
          '#define KEYPAD_SECTION_RIGHT 0x%03X' % SECTION_RIGHT, '#define KEYPAD_SECTION_WRONG 0x%03X' % SECTION_WRONG]
    for name, s in zip(('LIGHT', 'KEY', 'BACK', 'CHECK', 'WRONG', 'RIGHT'), SES):
        h.append('#define KEYPAD_SE_%s %d     // the DS\'s SE0%X' % (name, NEW_SES[s], s - 0xE0))
    h.append('static const u8 sKeypadCode[7] = { %s };' % ', '.join(map(str, code())))
    h.append('static const u16 sKeypadPalette[%d] = {' % len(cols))
    for i in range(0, len(cols), 12):
        h.append('    ' + ', '.join('0x%04X' % rgb5(c) for c in cols[i:i + 12]) + ',')
    h.append('};')
    h.append('static const u16 sKeypadKeyPals[3][16] = {')
    for p in (KEY_DARK, KEY_LIT, KEY_PRESSED):
        h.append('    { %s },' % ', '.join('0x%04X' % (c & 0x7FFF) for c in kpals[p]))
    h.append('};')
    h.append('static const u16 sKeypadLedPal[16] = { %s };' % ', '.join(
        '0x%04X' % (c & 0x7FFF) for c in struct.unpack_from('<16H', d, LED_COLOURS)))
    h.append('static const u16 sKeypadCursorPal[16] = { 0, 0x%04X, 0x%04X };' % (rgb5(CURSOR[0]), rgb5(CURSOR[1])))
    h.append('static const u16 sKeypadHandlePal[16] = { %s };' % ', '.join('0x%04X' % (c & 0x7FFF) for c in hpal))
    h.append('static const u16 sKeypadSafeLightPal[16] = { 0, %s };' % ', '.join('0x%04X' % rgb5(c) for c in SAFE_LIGHT_COLOURS))
    open(os.path.join(ROOT, 'graphics', 'en', 'rfta', 'keypad.bin'), 'wb').write(blob)
    asm = ['@ generated by tools/en/rfta/keypad.py: the safe\'s keypad', '\t.section rfta_low, "a"', '\t.align 2',
           '\t.global gEnKeypadData', 'gEnKeypadData:', '\t.incbin "graphics/en/rfta/keypad.bin"']
    open(os.path.join(ROOT, 'data', 'rfta', 'keypad.s'), 'w').write('\n'.join(asm) + '\n')
    open(os.path.join(ROOT, 'src', 'data', 'en_rfta_keypad.h'), 'w').write('\n'.join(h) + '\n')
    print('%d bytes, %d tiles, %d colours' % (len(blob), len(tiles), len(cols)))
    if preview:
        from PIL import Image
        P = np.array(cols, np.uint8)
        img = np.zeros((160, 240), np.uint8)
        for ty in range(20):
            for tx in range(30):
                img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8] = tiles[tmap[ty * 30 + tx]]
        out = P[img]
        KP = np.array([rgb(c) for c in kpals[KEY_LIT]], np.uint8)
        for k in range(11):
            x, y = key_at(k)
            px = kpx[k]
            out[y:y + 32, x:x + px.shape[1]] = KP[px]
        g = ink(pictures()[6])
        for i in range(7):
            x, y = 0x33 - DX + 22 * i, 0x50 - DY
            m = g != 0
            out[y:y + GLYPH_H, x:x + GLYPH_W][m] = P[g[m]]
        Image.fromarray(out).resize((720, 480), 0).save(preview)


if __name__ == '__main__':
    main()
