"""The jar puzzle (the DS's 74 8 32: the Unstable Jar's pieces put back
together in the evidence room on Day 2, the last piece fitted in Gant's
office on Day 3), from the DS, for evidence3d.py (which carries its meshes
and writes its data with the viewer's).

What the DS does (its code at 0x02072a6c-0x020767a0, the puzzle's state at
0x02318f58-0x023190c0):
- the jar is the object records 0x2f (the base, the DS's itm05a3) to 0x38
  (the nine pieces, itm05a4-itm05ac, each in the jar's own frame: put
  together they are the jar), drawn under the 3D viewer's camera on the top
  screen (the viewer's projection over the whole 256 x 192 screen);
- a step table (0x020c9794, 16 bytes a step): the jar shown (the records
  0x2f up to it), the piece that fits next, the jar's turn about y (degrees),
  the angle the piece must be at (0 for all), the jar's offset (y, z: floats
  at +8, +12); the point the next piece goes (0x020c96b0, 12 bytes: x, y,
  z; the crosshair over it, the point (x, -y, 0) projected);
- the fragments to pick from (Day 2: eight, in the order of 0x020c92d0;
  Day 3, flag 0x1d set: the ninth alone, the jar whole to its step 8), each
  shown in the circle on the bottom screen as a picture (0x020c9518: the US
  build's set the second nine, 256 colours of which 16 used, a 16 x 16 map,
  8bpp tiles), at a random angle (90, 180 or 270) the L and R buttons turn
  by 90 (6 degrees a frame, SE 0x1AD); left and right pick (SE 0x36), X
  (Combine, SE 0x34) sends it: the right piece at 0 fits (it rises into its
  place, SE 0x1AC, the jar flashes white, waits, turns to the next step's
  view in 30 frames), any other comes back;
- the red edges where the next piece goes are pictures (guide01-guide09,
  128 x 128, colour 1 red, at (64, 32) of the screen), the crosshair over
  the point another ("grid", 64 x 64); both pulse through six palettes
  (5 4 3 2 1 0 0 1 2 3 4 5, six frames each);
- at the start the base rises into place (30 frames) and turns once round
  (60); when the last piece fits the jar turns to the next step's view, the
  screens fade out and the jar's picture (background 0xc0, Day 3 0xc1) shows
  as section 0x136 (Day 3 0x133) starts; Back leaves with the room's
  background (0x75, Day 3 0x74) and section 0x135 (Day 3 0x132).

On the GBA (en_evidence3d.c, the viewer's renderer and screen) the top
screen's view is drawn at 2/3 of its size into the viewport's left 144
columns, the circle and its picture (a 64 x 64 affine sprite, the DS's at
half its size) in a panel on the right."""
import os, sys, struct, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import dsbin
from dsdata import data

JAR_FIRST, JAR_LAST = 0x2F, 0x38          # the object records (the base and the nine pieces)
STEPS, STEP_COUNT = 0x020c9794, 10
POINTS = 0x020c96b0
ORDER = 0x020c92d0                        # 8 u16: the Day 2 list of fragments
FRAGMENTS, FRAGMENT_SIZES = 0x020c9518, 0x020c9560     # 2 sets x 9: data.bin offsets, sizes
FRAGMENT_SET = 1                          # (the US build's: gMain + 4)
TEXTURE_POOL = (0x0207557c, 0x020755d0)   # the puzzle's 2D textures: a literal pool, each name followed by its data.bin offset
GUIDE_NAMES = ['guide%02d' % k for k in range(1, 10)]
GUIDE_AT = (64, 32)                       # where the DS draws them (128 x 128)
PULSE = [5, 4, 3, 2, 1, 0, 0, 1, 2, 3, 4, 5]
PULSE_FRAMES = 6
BACKGROUNDS = (0xC0, 0xC1)                # the jar as the puzzle leaves it (Day 2, Day 3)
# where the puzzle goes on, Day 2 and Day 3: (background, section) after
# Back (the DS's try-again) and after the last piece fits
EXITS = [dict(back=(0x75, 0x135), done=(0xC0, 0x136)), dict(back=(0x74, 0x132), done=(0xC1, 0x133))]
SE_FIT, SE_TURN, SE_DONE = 0x1AC, 0x1AD, 0x1A0   # the DS's sequences (sfx.py: the GBA's songs); Day 3's last piece: SE0C0

# the GBA's view: the DS's top screen at 2/3, its middle at the viewport's (72, 64)
K = 2 / 3
PROJ_X, PROJ_Y = 0x143c / 4096, 0x2009 / 4096
FOCAL_X, FOCAL_Y = PROJ_X * 128 * K, PROJ_Y * 96 * K
CENTRE = (72, 64)
VIS_W = 144                               # the viewport's columns shown (of 192)
DISTANCE = 20

# the fit's flight (the DS's, frames 0-41 after the 2D send): y, z off the
# piece's place (it rises from below and in front, overshoots, settles)
def flight():
    out = []
    z = 3.5
    for k in range(42):
        y = -6.418 + 0.564 * k - 0.009 * k * (k - 1)
        if k >= 41:
            y = 2.0
        if k >= 25:
            z = max(2.0, 3.5 - 0.1 * (k - 24))
        out.append((y - 2.0, z - 2.0))
    return out


def u32(a):
    return dsbin.u32(a)


def cstr(a):
    d = dsbin.data(); o = a - dsbin.BASE
    return d[o:d.index(b'\0', o)].decode('latin1')


def steps():
    out = []
    d = dsbin.data()
    for k in range(STEP_COUNT):
        b = d[STEPS - dsbin.BASE + 16 * k:STEPS - dsbin.BASE + 16 * k + 16]
        jar, piece = b[0], b[1]
        yaw, h4, angle = struct.unpack_from('<3h', b, 2)
        ty, tz = struct.unpack_from('<2f', b, 8)
        px, py, pz = struct.unpack_from('<3f', d, POINTS - dsbin.BASE + 12 * k)
        out.append(dict(jar=jar, piece=piece, yaw=yaw, angle=angle, ty=ty, tz=tz, point=(px, -py, 0.0)))
    return out


def order():
    return list(struct.unpack_from('<8H', dsbin.data(), ORDER - dsbin.BASE))


def textures2d():
    """the puzzle's 2D textures by name: data.bin offsets"""
    out = {}
    for a in range(TEXTURE_POOL[0], TEXTURE_POOL[1], 4):
        nm, off = u32(a), u32(a + 4)
        if 0x02000000 <= nm < 0x02100000 and 0x01000000 <= off < 0x04000000:
            out[cstr(nm)] = off
    return out


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


def rgb(c):
    return ((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31)


def fragment(k):
    """piece k's picture (the circle's): 128 x 128 indices, 16 colours (0 clear)"""
    d = data()
    off = u32(FRAGMENTS + 4 * (9 * FRAGMENT_SET + k))
    size = u32(FRAGMENT_SIZES + 4 * (9 * FRAGMENT_SET + k))
    pal = list(struct.unpack_from('<256H', d, off))
    mp = struct.unpack_from('<256H', d, off + 0x200)
    t = np.frombuffer(d[off + 0x400:off + size], np.uint8)
    img = np.zeros((128, 128), np.uint8)
    for i, e in enumerate(mp):
        ty, tx = divmod(i, 16)
        n = e & 0x3FF
        tl = t[n * 64:(n + 1) * 64].reshape(8, 8)
        if e & 0x400: tl = tl[:, ::-1]
        if e & 0x800: tl = tl[::-1]
        img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8] = tl
    assert img.max() < 16
    return img, pal[:16]


def half(img, pal):
    """a 128 x 128 picture at half its size (64 x 64): a pixel clear where
    most of its four are, else the colour of the image nearest their mean"""
    out = np.zeros((64, 64), np.uint8)
    P = np.array([rgb(c) for c in pal], float)
    for y in range(64):
        for x in range(64):
            q = img[2 * y:2 * y + 2, 2 * x:2 * x + 2].reshape(-1)
            solid = q[q != 0]
            if len(solid) < 2:
                continue
            m = P[solid].mean(0)
            out[y, x] = 1 + int(np.argmin(((P[1:] - m) ** 2).sum(1)))
    return out


def to_gba(x, y):
    """a DS top-screen pixel -> the GBA's viewport (the picture's buffer)"""
    return (x - 128) * K + CENTRE[0], (y - 96) * K + CENTRE[1]


def guide_offsets(px):
    """the red of a guide picture (drawn at GUIDE_AT) -> the picture
    buffer's byte offsets (24 x 16 tiles of 64 bytes): every GBA pixel some
    of whose DS pixels are red"""
    red = px == 1
    hits = set()
    ys, xs = np.nonzero(red)
    for y, x in zip(ys, xs):
        dx, dy = x + GUIDE_AT[0], y + GUIDE_AT[1]
        x0, y0 = to_gba(dx, dy)
        x1, y1 = to_gba(dx + 1, dy + 1)
        for gy in range(int(math.floor(y0)), int(math.ceil(y1))):
            for gx in range(int(math.floor(x0)), int(math.ceil(x1))):
                if 0 <= gx < VIS_W and 0 <= gy < 128:
                    hits.add((gy, gx))
    offs = sorted(((gy >> 3) * 24 + (gx >> 3)) * 64 + (gy & 7) * 8 + (gx & 7) for gy, gx in hits)
    box = (min(gx for _, gx in hits) >> 3, min(gy for gy, _ in hits) >> 3,
           (max(gx for _, gx in hits) >> 3) + 1, (max(gy for gy, _ in hits) >> 3) + 1) if hits else (0, 0, 0, 0)
    return offs, box


def project(p, yaw, ty, tz):
    """a point of the jar's frame -> the GBA's viewport (the DS's row vectors: v R + t)"""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    x, y, z = p
    X, Y, Z = x * c + z * s, y, -x * s + z * c
    Y += ty; Z += tz
    d = DISTANCE - Z
    return CENTRE[0] + FOCAL_X * X / d, CENTRE[1] - FOCAL_Y * Y / d


def cross_image():
    """the DS's crosshair ("grid", 64 x 64) at 2/3, in a 64 x 64 sprite: its
    middle at (32, 32); its six palettes"""
    px, pals = tex2d(textures2d()['grid'])
    out = np.zeros((64, 64), np.uint8)
    for y in range(64):
        for x in range(64):
            sx = int(math.floor((x - 32 + 0.5) / K + 32))
            sy = int(math.floor((y - 32 + 0.5) / K + 32))
            if 0 <= sx < 64 and 0 <= sy < 64:
                out[y, x] = px[sy, sx]
    return out, pals[:6]


def guides():
    t = textures2d()
    out = []
    for name in GUIDE_NAMES:
        px, pals = tex2d(t[name])
        out.append(guide_offsets(px))
    reds = [tex2d(t[GUIDE_NAMES[0]])[1][p][1] for p in range(6)]
    return out, reds


# ---------------------------------------------------------------- the GBA's screen
VIEW_X, VIEW_Y = 8, 8                     # the viewport's top left on the screen (its first 144 columns shown)
PANEL_X = VIEW_X + VIS_W                  # the panel on the right: 152-239
CIRCLE = (196, 72, 32)                    # the circle: its middle, its ring's outer radius
DISC_R = 28                               # the grid inside
LABEL_Y = (6, 20)                         # "Fragment", "No." (the number a sprite after it)
CROSS_R = 24                              # the red cross over the circle: its arms
ICON_Y = 112                              # the L and R buttons that turn the piece
ARROW_X, ARROW_Y = (PANEL_X + 2, 232), CIRCLE[1] - 8     # the arrows: more pieces that way
RING, RING_LIGHT, RING_EDGE = (248, 248, 248), (200, 200, 200), (64, 64, 64)
GUIDE_INDEX = 96                          # BG3's colour for the red guide (after the jar's four texture slots)


def screen():
    """the frame (BG3, 256 colours from evidence3d.PAL_FRAME): the viewer's
    wood and sunken edge round the viewport's shown columns, the panel with
    the circle (its grid and ring), "Fragment" / "No." and the L and R
    buttons with their turns; the tabs (sprites) under it all. Returns the
    picture, its colours and where the number goes (x, y)"""
    import evidence3d as e3
    import fingerprint as fp
    a = np.zeros((e3.GBA_H, e3.GBA_W, 3), np.uint8)
    for y in range(e3.GBA_H):
        a[y] = e3.WOOD_LIGHT if y % 3 == 1 else e3.WOOD
    x0, y0, x1, y1 = VIEW_X, VIEW_Y, VIEW_X + VIS_W, VIEW_Y + 128
    a[y0 - 1, x0 - 1:x1 + 1] = e3.EDGE_DARK; a[y0 - 1:y1, x0 - 1] = e3.EDGE_DARK
    a[y1, x0 - 1:x1 + 1] = e3.EDGE_LIGHT; a[y0:y1, x1] = e3.EDGE_SIDE
    # the circle
    cx, cy, r = CIRCLE
    yy, xx = np.mgrid[0:e3.GBA_H, 0:e3.GBA_W]
    d = np.hypot(xx - cx + 0.5, yy - cy + 0.5)
    disc = d < DISC_R + 0.5
    a[disc] = e3.GRID_BG
    gl = disc & ((((xx - cx) % 8) == 0) | (((yy - cy) % 8) == 0))
    a[gl] = e3.GRID_LINE
    a[(d >= DISC_R + 0.5) & (d < DISC_R + 1.5)] = RING_LIGHT
    a[(d >= DISC_R + 1.5) & (d < r - 0.5)] = RING
    a[(d >= r - 0.5) & (d < r + 0.5)] = RING_EDGE
    # "Fragment" / "No." (the number: DIGIT sprites)
    def label(txt, x, y):
        m = fp.text(txt)[1:15]
        img = np.zeros((m.shape[0] + 2, m.shape[1] + 2), np.uint8)
        fp.put(img, m, 1, 1, 1, edge=2)
        ys, xs = np.nonzero(img)
        a[ys + y - 1, xs + x - 1] = np.array([(0, 0, 0), e3.WHITE, (24, 24, 24)], np.uint8)[img[ys, xs]]
        return x + m.shape[1]
    w = fp.text('Fragment')[1:15].shape[1]
    label('Fragment', cx - w // 2, LABEL_Y[0])
    dw = max(fp.text(str(n))[1:15].shape[1] for n in range(1, 10))
    w = fp.text('No.')[1:15].shape[1] + 1 + dw
    end = label('No.', cx - w // 2, LABEL_Y[1])
    # the L and R buttons, each with its turn
    ui = [(0, 0, 0)] + list(fp.UI[1:])
    def icon(letter, x, y):
        ic = e3.shoulder(letter)
        ys, xs = np.nonzero(ic)
        a[ys + y, xs + x] = np.array(ui, np.uint8)[ic[ys, xs]]
    def turn(x, y, clockwise):
        # three quarters of a circle with its arrowhead (the DS's buttons' turns)
        pts = []
        for t in np.linspace(0, math.pi * 1.25, 40):
            ang = t if clockwise else math.pi - t
            pts.append((x + 5 + 5 * math.cos(ang + math.pi), y + 5 - 5 * math.sin(ang + math.pi)))
        for px, py in pts:
            a[int(round(py)), int(round(px))] = e3.WHITE
        ex, ey = pts[-1]
        for k in range(3):
            a[int(round(ey)) - k, int(round(ex))] = e3.WHITE
            a[int(round(ey)), int(round(ex)) + (k if clockwise else -k)] = e3.WHITE
    icon('L', cx - 34, ICON_Y)
    turn(cx - 18, ICON_Y, False)
    icon('R', cx + 21, ICON_Y)
    turn(cx + 6, ICON_Y, True)
    colours = []
    for c in map(tuple, a.reshape(-1, 3)):
        if c not in colours:
            colours.append(c)
    assert len(colours) <= 256 - e3.PAL_FRAME, len(colours)
    idx = {c: e3.PAL_FRAME + k for k, c in enumerate(colours)}
    out = np.zeros((e3.GBA_H, e3.GBA_W), np.uint8)
    for y in range(e3.GBA_H):
        for x in range(e3.GBA_W):
            out[y, x] = idx[tuple(a[y, x])]
    return out, colours, (end + 1, LABEL_Y[1] - 1)


def frame_tiles(frame):
    """the frame's tiles (8bpp, after the picture's 384) and the map: the
    picture's tiles in the viewport's shown columns"""
    import evidence3d as e3
    tiles, seen, tmap = [], {}, []
    for ty in range(e3.GBA_H // 8):
        for tx in range(e3.GBA_W // 8):
            vx, vy = tx - VIEW_X // 8, ty - VIEW_Y // 8
            if 0 <= vx < VIS_W // 8 and 0 <= vy < 16:
                tmap.append(vy * 24 + vx)
                continue
            t = frame[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].copy()
            key = t.tobytes()
            if key not in seen:
                seen[key] = e3.VIEW_TILES + len(tiles); tiles.append(t)
            tmap.append(seen[key])
    assert len(tiles) <= 128, len(tiles)
    return tiles, tmap


def sprites():
    """the puzzle's sprites (4bpp, the fingerprints' UI colours in OBJ
    palette 8): the tabs, the number after "No.", the arrows by the circle
    (more pieces that way), the cross over the circle (the crosshair's
    colours, palette 11: colour 1 its red)"""
    import fingerprint as fp
    st = fp.SpriteSet('JAR')
    st.add('BACK', fp.tab(['Back'], ['B']))
    st.add('COMBINE', fp.tab(['Combine'], ['A']))
    for n in range(1, 10):
        m = fp.text(str(n))[1:15]
        img = np.zeros((16, 8), np.uint8)
        fp.put(img, m, 1, 1, fp.C_WHITE, edge=fp.C_BLACK)
        st.add('DIGIT%d' % n, img, [(0, 0, 8, 16)])
    for name, flip in (('LEFT', False), ('RIGHT', True)):
        img = np.zeros((16, 8), np.uint8)
        for i in range(6):
            x = 1 + i if not flip else 6 - i
            img[7 - i:9 + i, x] = fp.C_BAR
            img[6 - i, x] = img[9 + i, x] = fp.C_WHITE
        st.add(name, img, [(0, 0, 8, 16)])
    h = np.zeros((8, 32), np.uint8); h[0, :] = 1
    v = np.zeros((32, 8), np.uint8); v[:, 0] = 1
    st.add('HLINE', h, [(0, 0, 32, 8)])
    st.add('VLINE', v, [(0, 0, 8, 32)])
    names, n = [], 0
    for key, rec in st.sprites:
        names.append((key, n)); n += len(rec)
    return st, names


CACHE_MAX = 0x9600                        # en_evidence3d.c's sJarCache (the movies' buffer while the puzzle is up)


def cache_boxes(names):
    """each step's box (the picture buffer's tiles, x0 y0 x1 y1) round the jar
    and the piece's whole flight: the jar alone is kept there as the piece
    flies (its tiles and depth), so that only the piece is drawn again"""
    import evidence3d as e3
    V = [np.array(e3.mesh(n)['V'], float) / 4096 for n in names]
    st, fl, out = steps(), flight(), []
    def xy(P, yaw, ty, tz):
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        X, Y, Z = P[:, 0] * c + P[:, 2] * s, P[:, 1] + ty, -P[:, 0] * s + P[:, 2] * c + tz
        return CENTRE[0] + FOCAL_X * X / (DISTANCE - Z), CENTRE[1] - FOCAL_Y * Y / (DISTANCE - Z)
    for k in range(len(st) - 1):
        s = st[k]
        pts = [xy(V[i], s['yaw'], s['ty'], s['tz']) for i in range(k + 1)]
        pts += [xy(V[k + 1], s['yaw'], s['ty'] + dy, s['tz'] + dz) for dy, dz in fl]
        xs = np.concatenate([p[0] for p in pts]); ys = np.concatenate([p[1] for p in pts])
        box = (max(0, int(math.floor(xs.min())) - 3) >> 3, max(0, int(math.floor(ys.min())) - 3) >> 3,
               min(24, (int(math.ceil(xs.max())) + 3 + 7) >> 3), min(16, (int(math.ceil(ys.max())) + 3 + 7) >> 3))
        assert (box[2] - box[0]) * (box[3] - box[1]) * (64 + 128) <= CACHE_MAX, box
        out.append(box)
    return out + [(0, 0, 0, 0)]


def zshift(dmin):
    """the depth's shift (en_evidence3d.c's ZShift) for the nearest a vertex
    can come (W = 2^26 / depth, depth 1.19.12)"""
    w = int((1 << 26) / (dmin * 4096)) + 1
    zs = 1
    while ((w << 12) >> zs) >= 0x10000:
        zs += 1
    return zs


def export(blob, align, meshidx, texids, recs):
    """the puzzle's data (into blob, evidence3d.py's) and its header lines"""
    import evidence3d as e3
    import fingerprint as fp
    from sfx import NEW_SES
    st = steps()
    names = [recs[r]['meshes'][0] for r in range(JAR_FIRST, JAR_LAST + 1)]
    assert all(len(recs[r]['meshes']) == 1 for r in range(JAR_FIRST, JAR_LAST + 1))
    textures = []
    for m in names:
        for t, _, _ in e3.mesh(m)['parts']:
            if t not in textures:
                textures.append(t)
    assert len(textures) * 16 + e3.PAL_TEXTURES <= GUIDE_INDEX
    # the nearest a vertex comes: the jar's widest about its axis, at the
    # most the jar comes forward (a piece's flight 1.5 more than its place)
    R = 0
    for m in names:
        V = np.array(e3.mesh(m)['V'], float) / 4096
        R = max(R, np.hypot(V[:, 0], V[:, 2]).max())
    fl = flight()
    tz_max = max(max(s['tz'] for s in st), 2.0 + max(z for _, z in fl))
    zs = zshift(DISTANCE - tz_max - R - 0.5)
    # the steps: the jar's turn and place, the crosshair's middle on the
    # screen, the guide (the picture buffer's offsets, their tiles' box)
    G, reds = guides()
    caches = cache_boxes(names)
    lines, offs = [], []
    for k, s in enumerate(st):
        if k < len(G):
            x, y = project(s['point'], s['yaw'], s['ty'], s['tz'])
            cx, cy = int(math.floor(x)) + VIEW_X, int(math.floor(y)) + VIEW_Y
            o, box = G[k]
        else:
            cx = cy = 0
            o, box = [], (0, 0, 0, 0)
        lines.append('    { %d, %d, %d, %d, %d, %d, %d, { %d, %d, %d, %d }, { %d, %d, %d, %d } }, // step %d: piece %d' % (
            s['yaw'], cx, cy, e3.fx(s['ty']), e3.fx(s['tz']), len(offs), len(o), *box, *caches[k], k,
            s['piece'] - 0x30 if s['piece'] else -1))
        offs += o
    assert max(offs) < 0x10000
    # the fragments: the DS's pictures at half their size, 64 x 64 4bpp
    # sprites (colour 0 clear), and their colours
    align(); o_frag = len(blob)
    frag_pals = []
    for k in range(9):
        img, pal = fragment(k)
        blob += fp.tiles4(half(img, pal))
        frag_pals.append(pal)
    cimg, cpals = cross_image()
    align(); o_cross = len(blob); blob += fp.tiles4(cimg)
    # the screen: its frame (tiles and map), the sprites
    frame, colours, digit = screen()
    tiles, tmap = frame_tiles(frame)
    align(); o_frame = len(blob); blob += b''.join(bytes(t.reshape(-1)) for t in tiles)
    align(); o_map = len(blob); blob += struct.pack('<600H', *tmap)
    sset, pieces = sprites()
    align(); o_sprites = len(blob); blob += bytes(sset.tiles)
    assert len(sset.tiles) // 32 + 128 <= 0x2C0 - 0x1A0
    h = ['// the jar puzzle (jarpuzzle.py)',
         '#define EN3D_JAR_FX %d             // the DS\'s top screen at 2/3' % int(FOCAL_X * 16 + 0.5),
         '#define EN3D_JAR_FY %d' % int(FOCAL_Y * 16 + 0.5),
         '#define EN3D_JAR_OX %d             // its middle: the shown columns\' (1/16 pixel)' % (CENTRE[0] * 16),
         '#define EN3D_JAR_OY %d' % (CENTRE[1] * 16),
         '#define EN3D_JAR_ZSHIFT %d         // the depth\'s shift: the nearest a vertex comes %.2f' % (zs, DISTANCE - tz_max - R),
         '#define EN3D_JAR_STEPS %d' % len(st),
         '#define EN3D_JAR_TEXTURES %d' % len(textures),
         '#define EN3D_JAR_FLIGHT %d         // frames' % len(fl),
         '#define EN3D_JAR_PULSE_FRAMES %d' % PULSE_FRAMES,
         '#define EN3D_JAR_GUIDE_INDEX %d    // BG3\'s colour for the guide\'s red' % GUIDE_INDEX,
         '#define EN3D_JAR_VIEW_X %d' % VIEW_X, '#define EN3D_JAR_VIEW_Y %d' % VIEW_Y,
         '#define EN3D_JAR_VIS_W %d          // the viewport\'s columns shown' % VIS_W,
         '#define EN3D_JAR_CIRCLE_X %d' % CIRCLE[0], '#define EN3D_JAR_CIRCLE_Y %d' % CIRCLE[1],
         '#define EN3D_JAR_CROSS_R %d' % CROSS_R,
         '#define EN3D_JAR_DIGIT_X %d' % digit[0], '#define EN3D_JAR_DIGIT_Y %d' % digit[1],
         '#define EN3D_JAR_LEFT_X %d' % ARROW_X[0], '#define EN3D_JAR_RIGHT_X %d' % ARROW_X[1],
         '#define EN3D_JAR_ARROW_Y %d' % ARROW_Y,
         '#define EN3D_JAR_COMBINE_X %d     // the tab, at the right' % (e3.GBA_W - fp.tab(['Combine'], ['A']).shape[1]),
         '#define EN3D_JAR_SE_FIT %d         // the DS\'s SE0CC' % NEW_SES[SE_FIT],
         '#define EN3D_JAR_SE_TURN %d        // SE0CD' % NEW_SES[SE_TURN],
         '#define EN3D_JAR_SE_DONE %d        // SE0C0 (Day 3\'s last piece)' % NEW_SES[SE_DONE],
         '#define EN3D_JAR_GFX_FRAGMENTS 0x%X  // 9 x 64 x 64 4bpp' % o_frag,
         '#define EN3D_JAR_GFX_CROSS 0x%X      // 64 x 64 4bpp' % o_cross,
         '#define EN3D_JAR_GFX_FRAME 0x%X' % o_frame, '#define EN3D_JAR_GFX_MAP 0x%X      // 30 x 20' % o_map,
         '#define EN3D_JAR_FRAME_TILES %d' % len(tiles), '#define EN3D_JAR_FRAME_COLOURS %d' % len(colours),
         '#define EN3D_JAR_GFX_SPRITES 0x%X' % o_sprites,
         '#define EN3D_JAR_SPRITE_TILES %d' % (len(sset.tiles) // 32)]
    for key, rec in pieces:
        h.append('#define EN3D_JAR_SPRITE_%s %d' % (key, rec))
    h.append('static const struct En3dJarStep sEn3dJarSteps[] = {'); h += lines; h.append('};')
    h.append('static const u16 sEn3dJarGuides[%d] = {' % len(offs))
    for i in range(0, len(offs), 16):
        h.append('    ' + ', '.join(str(v) for v in offs[i:i + 16]) + ',')
    h.append('};')
    h.append('static const u8 sEn3dJarMeshes[%d] = { %s };   // the base, the pieces' % (len(names), ', '.join(str(meshidx[m]) for m in names)))
    h.append('static const u16 sEn3dJarTextures[%d] = { %s };' % (len(textures), ', '.join(str(texids[t]) for t in textures)))
    h.append('static const u8 sEn3dJarOrder[8] = { %s };   // Day 2\'s fragments, No. 1-8' % ', '.join(map(str, order())))
    h.append('static const s32 sEn3dJarFlight[%d][2] = {   // a piece\'s flight into place: y, z off it (1.19.12)' % len(fl))
    for i in range(0, len(fl), 6):
        h.append('    ' + ' '.join('{ %d, %d },' % (e3.fx(y), e3.fx(z)) for y, z in fl[i:i + 6]))
    h.append('};')
    h.append('static const s16 sEn3dSin[91] = {   // 0-90 degrees, 1.14')
    sins = [round(math.sin(math.radians(a)) * 16384) for a in range(91)]
    for i in range(0, 91, 16):
        h.append('    ' + ', '.join(map(str, sins[i:i + 16])) + ',')
    h.append('};')
    h.append('static const u16 sEn3dJarFragmentPal[9][16] = {')
    for pal in frag_pals:
        h.append('    { %s },' % ', '.join('0x%04X' % c for c in pal))
    h.append('};')
    h.append('static const u16 sEn3dJarCrossPal[6][16] = {')
    for pal in cpals:
        h.append('    { %s },' % ', '.join('0x%04X' % c for c in pal))
    h.append('};')
    h.append('static const u16 sEn3dJarGuideRed[6] = { %s };' % ', '.join('0x%04X' % c for c in reds))
    h.append('static const u8 sEn3dJarPulse[%d] = { %s };' % (len(PULSE), ', '.join(map(str, PULSE))))
    h.append('static const u16 sEn3dJarExits[2][2][2] = {   // Day 2, Day 3: after Back, after the last piece: background, section')
    for e in EXITS:
        h.append('    { { 0x%02X, 0x%03X }, { 0x%02X, 0x%03X } },' % (*e['back'], *e['done']))
    h.append('};')
    h.append('static const u16 sEn3dJarFramePalette[%d] = { %s };' % (len(colours), ', '.join('0x%04X' % e3.rgb5(c) for c in colours)))
    h.append('static const struct En3dPiece sEn3dJarPieces[] = {')
    for key, rec in sset.sprites:
        for k, (dx, dy, (shape, size), tile) in enumerate(rec):
            h.append('    { %d, %d, %d, %d, %d, %d },%s' % (dx, dy, shape, size, tile, k == len(rec) - 1, ' // ' + key if k == 0 else ''))
    h.append('};')
    return h
