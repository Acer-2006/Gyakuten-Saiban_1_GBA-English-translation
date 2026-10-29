#!/usr/bin/env python3
"""The fifth episode's evidence in 3D (the DS's Court Record "Check" on the
badge, the wallet, the phone, the knife, the jar... and the scenes that turn
evidence over), from the DS.

The DS's models are its own format, not Nitro's: a resource table in the
ARM9 (0x020b6574, 12 bytes a record: name, data.bin offset, size; the US
build's, whose meshes name the English textures, "u" at the end) gives each
mesh and the texture table (0x020b8df8) each texture. A mesh: offsets of its
vertices (s16 x, y, z, the GX's 1.3.12), its normals (unused), its texture
coordinates (s16 s, t: texels of a 64 x 64 texture, 1.11.4; the texture
matrix scales them to the texture's size), its parts (16 bytes: the texture's
name, the first triangle, the count) and its triangles (three vertex /
coordinate index pairs), then the counts. A texture: format 3 (16 colours,
4 bits a texel, low nibble first), the size as 8 << n, the data, the
palette. The DS draws the triangles textured, one side (the back culled),
in the colour 0x739c (the textures at 29/32), with the edges marked.

Its viewer (the Court Record's state 8, 0x0208b3c0) draws the models of an
object record (0x020b91b8, 0x1c bytes, 66 of them: the mesh, a second mesh
(with the one the link table 0x020b8834 gives for it), the hotspots' ids,
their count, the blockers' count, the hotspots, the blockers) under a camera
20 units back (0x02312ff0), fovy 53 degrees (the projection's 0x143c,
0x2009), in a 192 x 120 viewport at (32, 16) of the touch screen. A hotspot
or blocker is a quad (0x40 bytes: a word, the normal, four corners, floats);
the test (0x0203cc1c) projects the corners as the GX's POS_TEST would and
asks whether the touch point is inside, for a quad whose normal faces the
camera; inside a facing blocker means nothing. The evidence's record is the
evidence table's +0xC less one (0x020ab048).

Examining a hotspot calls its id's handler (0x020c046c): the section to run
(0x0231603c: file 35's lines, or the chapter's for the scenes' own), the
pose the camera moves to (rotations about x, y and z in degrees, applied
z, x, y; a translation, z toward the camera) and, for a few, a model
change with an animation (the wallet opening, the phone flipping, the
knife's switch, the book's pages) and flags.

On the GBA (src/en_evidence3d.c, en_evidence3d_arm.s) the models are drawn
in real time, as the DS draws them: the meshes and the textures (4 bits a
texel) read from ROM as they are, each texture in a 16-colour slot of BG3's
256; the viewport is 192 x 128 at (24, 8), in the DS's frame (its wood, the
zoom's slider, the turning bar, the grid; drawn here in the DS's colours)
with the GBA's tabs and the keys' hints.

Writes graphics/en/rfta/evidence3d.bin, data/rfta/evidence3d.s (section
rfta_low) and src/data/en_rfta_evidence3d.h.
usage: evidence3d.py [--preview DIR]"""
import os, sys, struct, re, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import dsbin
from dsdata import data
ROOT = os.path.join(HERE, '..', '..', '..')

RESOURCES = 0x020b6574          # the US build's meshes (and the courtroom's textures)
TEXTURES = 0x020b8df8
LINKS = 0x020b8834
RECORDS = 0x020b91b8
HANDLERS, HANDLER_COUNT = 0x020c046c, 40
EVIDENCE_TABLE = 0x020ab048     # 0x18 bytes an entry; +0xC: the object record + 1
EVIDENCE_COUNT = 209
CLOSEUPS = 0x020b4740           # 7B's pictures: 12 bytes each (one a language), 0x20 of palette, 6 x 64 x 64 4bpp
CLOSEUP_COUNT = 3
VERTEX_COLOUR = 29 / 32         # 0x739c

# the camera
DISTANCE = 20
PROJ_X, PROJ_Y = 0x143c / 4096, 0x2009 / 4096
VIEW_W, VIEW_H = 192, 128       # the GBA's viewport (the DS's is 120 high)
VIEW_X, VIEW_Y = 24, 8
FOCAL_X, FOCAL_Y = PROJ_X * 96, PROJ_Y * 60    # pixels (the DS's)

# The handlers that do more than a section and a pose (read from their code):
# the meshes their animation shows (object records), the record it ends on,
# the section in the chapter's own script, and the flag they test and set.
SPECIAL = {
    3: dict(anim=(0x22, 0x23), to=9, chapter_section=0xFB, flag=1, else_section=0),   # the phone opens
    4: dict(anim=(0x24, 0x25), to=13, chapter_section=0xAB),                         # the knife's switch
    5: dict(anim=(0x1E, 0x1F, 0x20, 0x21), to=3, chapter_section=0xC2),              # the wallet: the ID card
    6: dict(anim=(0x26, 0x27, 0x28), to=28, chapter_section=0),                       # the book's pages: the picture
    17: dict(chapter_section=0xFC, flag=0, else_section=0x8F),                        # the redial button
    22: dict(chapter_section=0xAC),                                                   # the knife's tag (the trial)
}
# The DS's handler for the muffler's bloodstain (id 21) names file 35's 80,
# the badge's lines, and leaves the muffler's own (99) to nothing: its lines
FIXED_SECTIONS = {21: 0x99}

# The scenes (the DS's 74 8 2e, 74 b 0: the Court Record opened for the
# evidence to be checked, the GBA's command 69 0 n): the evidence, the
# section the viewer opens on and the first hover's (the wallet's how-to),
# the id that ends the scene, the section after it and the section after
# Back (none: no Back; Back ends the scene: the phone put away, the knife
# added to the record and the trial on).
SCENES = [
    dict(name='WALLET', chapter=18, ev=0x7D, open_section=0xC0, hover_section=0xC1, final=5, after=0xC3, back=0),
    dict(name='PHONE', chapter=18, ev=0xD0, final=17, after=0xFD, back=0xFA),
    dict(name='KNIFE', chapter=21, ev=0xC4, final=0, after=0, back=0x82),
    dict(name='PICTURE', chapter=33, ev=0xC6, final=6, after=0xAD, back=0),
]
# the GBA's screen: BG3's 256 colours (0-31 the text box's, then the
# textures' 16-colour slots, the close-up's, the frame's), the frame's tiles
# after the viewport's 384 (the picture drawn), its map 30 x 20
PAL_TEXTURES = 32               # 5 slots (a record has at most 5 textures)
TEXTURE_SLOTS = 5
PAL_CLOSEUP = 112
PAL_FRAME = 128
GBA_W, GBA_H = 240, 160
VIEW_TILES = (VIEW_W // 8) * (VIEW_H // 8)
WOOD, WOOD_LIGHT = (96, 88, 72), (128, 112, 88)        # the DS's frame: a lighter row in three
EDGE_DARK, EDGE_LIGHT, EDGE_SIDE = (80, 72, 56), (168, 144, 120), (144, 128, 104)
GRID_BG, GRID_LINE = (120, 120, 120), (152, 152, 152)   # a line every 16 pixels, at 8
ARROW_FILL, ARROW_LIGHT, ARROW_DARK, ARROW_SHADE = (120, 48, 0), (136, 72, 24), (96, 32, 0), (104, 40, 0)
WHITE, OUTLINE, TRACK, TRACK_IN, TRACK_EDGE = (248, 248, 248), (64, 64, 64), (16, 16, 16), (48, 48, 48), (144, 144, 144)
WEDGE, WEDGE_EDGE = (232, 232, 232), (184, 184, 176)
BAR, BAR_LIGHT, BAR_LIGHTER, BAR_TICK = (192, 192, 192), (208, 208, 208), (216, 216, 216), (240, 240, 240)
ZOOM_TRACK = (33, 109)          # the slider's track (y): the knob's top from 101 (out) to 33 (in)
TAB_Y = 142                     # the tabs (sprites), the hints between them


def u32(a):
    return dsbin.u32(a)


def cstr(a):
    d = dsbin.data(); o = a - dsbin.BASE
    return d[o:d.index(b'\0', o)].decode('latin1')


def table(a):
    out = {}
    while True:
        nm, off, sz = struct.unpack_from('<3I', dsbin.data(), a - dsbin.BASE)
        if not nm:
            break
        out.setdefault(cstr(nm), (off, sz))
        a += 12
    return out


_res = _tex = None
def resources():
    global _res, _tex
    if _res is None:
        _res, _tex = table(RESOURCES), table(TEXTURES)
    return _res, _tex


def texname(part):
    """the texture a part draws with (the English one where there is one;
    a few US meshes name a "u" texture that only exists without the u)"""
    tex = resources()[1]
    for n in (part + 'u', part, part[:-1] if part.endswith('u') else None):
        if n and n in tex:
            return n
    raise KeyError(part)


def mesh(name):
    off = resources()[0][name][0]
    d = data()
    ov, on, ot, op, otr, nv, nt, npart, ntri = struct.unpack_from('<5I4H', d, off)
    V = np.array(struct.unpack_from('<%dh' % (3 * nv), d, off + ov), np.int32).reshape(nv, 3)
    T = np.array(struct.unpack_from('<%dh' % (2 * nt), d, off + ot), np.int32).reshape(nt, 2)
    parts = []
    for k in range(npart):
        nm = d[off + op + 16 * k:off + op + 16 * k + 12].split(b'\0')[0].decode()
        first, cnt = struct.unpack_from('<2H', d, off + op + 16 * k + 12)
        parts.append((texname(nm), first, cnt))
    tris = np.array(struct.unpack_from('<%dh' % (6 * ntri), d, off + otr), np.int32).reshape(ntri, 3, 2)
    return dict(V=V, T=T, parts=parts, tris=tris)


def rgb555(v):
    return ((v & 31) * 255 // 31, (v >> 5 & 31) * 255 // 31, (v >> 10 & 31) * 255 // 31)


def texture(name):
    """-> (w, h, 4bpp bytes as the DS has them, 16 BGR555 colours)"""
    off = resources()[1][name][0]
    d = data()
    fmt, wl, hl, flags, doff, dsz, poff, psz = struct.unpack_from('<4B4I', d, off)
    assert fmt == 3 and psz >= 32 and flags == 0, (name, fmt, psz, flags)   # (a few carry 32 colours: the first 16 are used)
    w, h = 8 << wl, 8 << hl
    return w, h, d[off + doff:off + doff + dsz], list(struct.unpack_from('<16H', d, off + poff))


def links():
    out = {}
    a = LINKS
    while u32(a):
        out[cstr(u32(a))] = cstr(u32(a + 4))
        a += 0x1c
    return out


def quads(a, n):
    out = []
    for k in range(n):
        w = struct.unpack_from('<I15f', dsbin.data(), a - dsbin.BASE + 0x40 * k)
        out.append(dict(word=w[0], normal=np.array(w[1:4]), pts=np.array(w[4:16]).reshape(4, 3)))
    return out


def records():
    out = []
    lk = links()
    a = RECORDS
    while 0x02000000 <= u32(a) < 0x02100000:
        w = struct.unpack_from('<7I', dsbin.data(), a - dsbin.BASE)
        r = dict(index=len(out), meshes=[cstr(w[0])])
        if w[1]:
            r['meshes'].append(cstr(w[1]))
            if cstr(w[1]) in lk:
                r['meshes'].append(lk[cstr(w[1])])
        ids = struct.unpack_from('<%dI' % w[3], dsbin.data(), w[2] - dsbin.BASE) if w[2] else ()
        r['hot'] = quads(w[5], w[3]) if w[5] else []
        for q, k in zip(r['hot'], ids):
            q['id'] = k
        r['block'] = quads(w[6], w[4]) if w[6] else []
        out.append(r)
        a += 0x1c
    return out


def evidence_records():
    out = {}
    for ev in range(EVIDENCE_COUNT):
        m = struct.unpack_from('<H', dsbin.data(), EVIDENCE_TABLE - dsbin.BASE + 0x18 * ev + 0xC)[0]
        if m:
            out[ev] = m - 1
    return out


def handler(i):
    """an id's handler read as straight-line code: the section and the pose
    it stores (0x0231603c; 0x02315ff0, fd0, fc8 the rotations about x, y, z,
    ff8 and fd8 the x and y offsets, fe0 toward the camera)"""
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM); md.skipdata = True
    a = u32(HANDLERS + 4 * i)
    regs, st = {}, {}
    if not a:
        return None
    for ins in md.disasm(dsbin.data()[a - dsbin.BASE:a - dsbin.BASE + 0x400], a):
        mn, ops = ins.mnemonic, ins.op_str
        m = re.match(r'(\w+), #(-?0x[0-9a-f]+|-?\d+)$', ops)
        if mn in ('mov', 'mvn') and m:
            v = int(m.group(2), 0)
            regs[m.group(1)] = (~v & 0xFFFFFFFF) if mn == 'mvn' else v
        elif mn == 'ldr' and '[pc' in ops:
            k = int(re.search(r'#(-?0x[0-9a-f]+|-?\d+)', ops).group(1), 0)
            regs[ops.split(',')[0]] = u32((ins.address + 8 + k) & ~3)
        elif mn in ('str', 'strh', 'strb'):
            m2 = re.match(r'(\w+), \[(\w+)\]$', ops)
            if m2 and m2.group(2) in regs and m2.group(1) in regs:
                v = regs[m2.group(1)]
                if mn == 'strh':
                    v = v & 0xFFFF
                    v = v - 0x10000 if v & 0x8000 else v
                st.setdefault(regs[m2.group(2)], v)
        elif mn == 'bl':
            for r in ('r0', 'r1', 'r2', 'r3', 'ip', 'lr'):
                regs.pop(r, None)
        if mn == 'bx' or (mn == 'pop' and 'pc' in ops):
            break
    return dict(section=st.get(0x0231603c, 0), rx=st.get(0x02315ff0, 0), ry=st.get(0x02315fd0, 0),
                rz=st.get(0x02315fc8, 0), tx=st.get(0x02315ff8, 0), ty=st.get(0x02315fd8, 0), tz=st.get(0x02315fe0, 0))


# ---------------------------------------------------------------- rotations
def rot(ax, deg):
    """a DS rotation matrix (row vectors: v' = v M)"""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    if ax == 'x':
        return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
    if ax == 'y':
        return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
    return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])


def pose_matrix(p):
    """the DS's 0x020677b4: z, then x, then y"""
    return rot('z', p['rz']) @ rot('x', p['rx']) @ rot('y', p['ry'])


def quat_from_matrix(M):
    """(w, x, y, z) of the column-vector rotation M^T (the GBA keeps
    quaternions and builds the DS's row-vector matrix from them)"""
    R = M.T
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0:
        s = 0.5 / math.sqrt(t + 1)
        q = (0.25 / s, (R[2, 1] - R[1, 2]) * s, (R[0, 2] - R[2, 0]) * s, (R[1, 0] - R[0, 1]) * s)
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2 * math.sqrt(1 + R[0, 0] - R[1, 1] - R[2, 2])
        q = ((R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s)
    elif R[1, 1] > R[2, 2]:
        s = 2 * math.sqrt(1 + R[1, 1] - R[0, 0] - R[2, 2])
        q = ((R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s)
    else:
        s = 2 * math.sqrt(1 + R[2, 2] - R[0, 0] - R[1, 1])
        q = ((R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s)
    q = np.array(q)
    q = q / np.linalg.norm(q)
    return q if q[0] >= 0 else -q


def matrix_from_quat(q):
    """the DS's row-vector matrix of quaternion q (as the GBA builds it)"""
    w, x, y, z = q
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                  [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                  [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
    return R.T


# ---------------------------------------------------------------- the GBA's data
Q14 = 1 << 14


def gba_mesh(name, texids):
    """the GBA's mesh: counts, then s16 vertices (x, y, z), then the
    triangles (u16 vertex indices, s16 texel coordinates in 1/16, each
    triangle's moved by whole textures so its smallest is in the first),
    then the parts (u16 first, count, the texture's number)"""
    me = mesh(name)
    tex = resources()[1]
    out = bytearray()
    V, T = me['V'], me['T']
    tris = bytearray()
    for tname, first, cnt in me['parts']:
        w, h = texture(tname)[:2]
        for t in me['tris'][first:first + cnt]:
            vi, ti = t[:, 0], t[:, 1]
            uv = T[ti] * np.array([w, h]) // 64      # 1.11.4 texels of this texture
            # (whole textures off, the texture repeats: the smallest coordinate in the first)
            uv[:, 0] -= (uv[:, 0].min() // (16 * w)) * 16 * w
            uv[:, 1] -= (uv[:, 1].min() // (16 * h)) * 16 * h
            assert np.abs(uv).max() < 32768
            tris += struct.pack('<3H6h', *vi.tolist(), *uv.reshape(-1).tolist())
    parts = b''.join(struct.pack('<3H', first, cnt, texids[tname]) for tname, first, cnt in me['parts'])
    out += struct.pack('<4H', len(V), len(me['tris']), len(me['parts']), 0)
    out += parts
    while len(out) % 4:
        out += b'\0'
    out += struct.pack('<%dh' % V.size, *V.reshape(-1).tolist())
    while len(out) % 4:
        out += b'\0'
    tri_off = len(out)
    out += tris
    return bytes(out), tri_off


def rgb5(c):
    r, g, b = (int(v) for v in c)
    return (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10


def screen():
    """the frame round the viewport, 160 x 240 RGB, and its colours (the
    DS's: its wood, the viewport's sunken edge, the zoom's slider on the
    left, the turning bar on the right; the GBA's hints between the tabs)"""
    import fingerprint as fp
    a = np.zeros((GBA_H, GBA_W, 3), np.uint8)
    for y in range(GBA_H):
        a[y] = WOOD_LIGHT if y % 3 == 1 else WOOD
    x0, y0, x1, y1 = VIEW_X, VIEW_Y, VIEW_X + VIEW_W, VIEW_Y + VIEW_H
    a[y0 - 1, x0 - 1:x1 + 1] = EDGE_DARK; a[y0 - 1:y1, x0 - 1] = EDGE_DARK
    a[y1, x0 - 1:x1 + 1] = EDGE_LIGHT; a[y0:y1, x1] = EDGE_SIDE
    # the slider: its arrows (brown, edged white and dark), the track, the wedge (+ to -)
    def arrow(top, up):
        for r in range(18):
            rr = r if up else 17 - r
            half = 1 + rr * 10 // 17
            y = top + r
            xl, xr = 12 - half, 12 + half
            a[y, xl - 2:xr + 2] = OUTLINE
            a[y, xl - 1:xr + 1] = WHITE
            if rr < 17:
                a[y, xl:xr] = ARROW_FILL
                a[y, xl:xl + 1] = ARROW_LIGHT; a[y, xr - 1:xr] = ARROW_LIGHT
        # the ornament: a chevron
        for k in range(5):
            yy = top + (6 + k if up else 11 - k)
            a[yy, 12 - 1 - k:12 - k] = ARROW_DARK; a[yy, 11 + k:12 + k] = ARROW_DARK
            a[yy, 12 - 2 - k:12 - 1 - k] = ARROW_SHADE
    arrow(9, True)
    arrow(117, False)
    a[29:114, 9] = TRACK_EDGE; a[29:114, 16] = TRACK_EDGE
    a[29:114, 10] = TRACK; a[29:114, 15] = TRACK
    a[29:114, 11:15] = TRACK_IN
    a[29, 9:17] = TRACK_EDGE; a[113, 9:17] = TRACK_EDGE
    for y in range(34, 110):
        w = max(1, 6 - (y - 34) * 6 // 76)
        a[y, 2:2 + w] = WEDGE
        a[y, 2] = WEDGE_EDGE
    a[30, 2:7] = WEDGE; a[28:33, 4] = WEDGE          # +
    a[112, 2:7] = TRACK_IN                           # -
    # the turning bar: a bow, its ticks
    for y in range(24, 121):
        t = (y - 72) / 48
        w = int(round(10 + 5 * (1 - t * t)))
        xa = 220
        a[y, xa] = TRACK_EDGE; a[y, xa + 1] = TRACK
        a[y, xa + 2:xa + w] = BAR
        a[y, xa + w - 4:xa + w - 2] = BAR_LIGHT; a[y, xa + w - 2] = BAR_LIGHTER
        a[y, xa + w] = TRACK_EDGE
        if (y - 24) % 12 == 6:
            a[y, xa + 3:xa + w - 1] = BAR_TICK
    a[23, 220:231] = TRACK_EDGE; a[121, 220:231] = TRACK_EDGE
    # the hints: R Point, L Zoom (with the + pad)
    ui = [(0, 0, 0)] + list(fp.UI[1:])
    def icon(letter, x, y):
        ic = shoulder(letter)
        ys, xs = np.nonzero(ic)
        a[ys + y, xs + x] = np.array(ui, np.uint8)[ic[ys, xs]]
    def label(txt, x, y):
        m = fp.text(txt)[1:15]
        img = np.zeros((m.shape[0] + 2, m.shape[1] + 2), np.uint8)
        fp.put(img, m, 1, 1, 1, edge=2)
        ys, xs = np.nonzero(img)
        a[ys + y - 1, xs + x - 1] = np.array([(0, 0, 0), WHITE, (24, 24, 24)], np.uint8)[img[ys, xs]]
        return x + m.shape[1]
    parts = [('R', 'Point'), ('L', 'Zoom')]
    widths = [13 + 3 + fp.text(t)[1:15].shape[1] for _, t in parts]
    gap = 8
    left, right = fp.tab(['Back'], ['B']).shape[1], GBA_W - fp.tab(['Examine'], ['A']).shape[1]
    x = (left + right) // 2 - (sum(widths) + gap) // 2
    assert x >= left + 2 and x + sum(widths) + gap <= right - 2
    for (letter, txt), w in zip(parts, widths):
        icon(letter, x, TAB_Y + 3)
        label(txt, x + 16, TAB_Y)
        x += w + gap
    colours = []
    for c in map(tuple, a.reshape(-1, 3)):
        if c not in colours:
            colours.append(c)
    assert len(colours) <= 256 - PAL_FRAME, len(colours)
    idx = {c: PAL_FRAME + k for k, c in enumerate(colours)}
    out = np.zeros((GBA_H, GBA_W), np.uint8)
    for y in range(GBA_H):
        for x in range(GBA_W):
            out[y, x] = idx[tuple(a[y, x])]
    return out, colours


GLYPHS = {'L': ['#....', '#....', '#....', '#....', '#....', '#....', '#####'],
          'R': ['####.', '#...#', '#...#', '####.', '#.#..', '#..#.', '#...#']}


def shoulder(letter):
    """a shoulder button (13 x 11, the fingerprints' colours) with its letter"""
    import fingerprint as fp
    a = np.zeros((11, 13), np.uint8)
    a[0, 1:12] = a[10, 1:12] = fp.C_DARK; a[1:10, 0] = a[1:10, 12] = fp.C_DARK
    a[1:10, 1:12] = fp.C_LIGHT
    for r, row in enumerate(GLYPHS[letter]):
        for c, ch in enumerate(row):
            if ch == '#':
                a[2 + r, 4 + c] = fp.C_BAR_DARK
    return a


def frame_tiles(frame):
    """the frame's 8bpp tiles (the same ones once) and the screen's map:
    the viewport's tiles 0-383, the frame's after"""
    tiles, seen, tmap = [], {}, []
    for ty in range(GBA_H // 8):
        for tx in range(GBA_W // 8):
            vx, vy = tx - VIEW_X // 8, ty - VIEW_Y // 8
            if 0 <= vx < VIEW_W // 8 and 0 <= vy < VIEW_H // 8:
                tmap.append(vy * (VIEW_W // 8) + vx)
                continue
            t = frame[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].copy()
            key = t.tobytes()
            if key not in seen:
                seen[key] = VIEW_TILES + len(tiles); tiles.append(t)
            tmap.append(seen[key])
    assert VIEW_TILES + len(tiles) <= 600
    return tiles, tmap


def grid_tiles():
    """the grid behind the models (BG2 under the picture, the backdrop its
    grey): four 4bpp tiles, colour 1 the line (at a tile's left in odd
    columns, at its top in odd rows: the DS's every 16 at 8)"""
    out = b''
    for k in range(4):
        t = np.zeros((8, 8), np.uint8)
        if k & 1:
            t[:, 0] = 1
        if k & 2:
            t[0, :] = 1
        out += bytes(int(row[x]) | int(row[x + 1]) << 4 for row in t for x in range(0, 8, 2))
    return out


def sprites():
    """the viewer's sprites (4bpp, the fingerprints' UI colours): the tabs,
    the touch's lines and square, the zoom's knob"""
    import fingerprint as fp
    st = fp.SpriteSet('VIEW')
    st.add('BACK', fp.tab(['Back'], ['B']))
    st.add('EXAMINE', fp.tab(['Examine'], ['A']))
    h = np.zeros((8, 32), np.uint8); h[0, :] = fp.C_BLUE
    v = np.zeros((32, 8), np.uint8); v[:, 0] = fp.C_BLUE
    st.add('HLINE', h, [(0, 0, 32, 8)])
    st.add('VLINE', v, [(0, 0, 8, 32)])
    st.add('SQUARE', fp.crosshair()[2], [(0, 0, 8, 8)])
    k = np.zeros((8, 16), np.uint8)
    k[0, 1:15] = fp.C_DARK; k[7, 1:15] = fp.C_DARK; k[1:7, 0] = fp.C_DARK; k[1:7, 15] = fp.C_DARK
    k[1, 1:15] = fp.C_WHITE; k[6, 1:15] = fp.C_WHITE; k[1:7, 1] = fp.C_WHITE; k[1:7, 14] = fp.C_WHITE
    k[2:6, 2:14] = fp.C_BAR; k[5, 2:14] = fp.C_BAR_DARK
    st.add('KNOB', k, [(0, 0, 16, 8)])
    names, n = [], 0
    for key, rec in st.sprites:
        names.append((key, n)); n += len(rec)
    assert len(st.tiles) // 32 <= 0x280 - 0x1A0
    return st, names


def check_label():
    """the Court Record's "Check" (beside its L button), in its labels'
    style (as the luminol's "Spray"): two 32 x 16 halves"""
    from dsfont import render, outline
    m = render('Check')[2:16]
    p = np.zeros((16, 64), np.uint8)
    p[1:1 + m.shape[0], 1:1 + m.shape[1]] = m
    img = np.zeros((16, 64), np.uint8)
    img[outline(p) > 0] = 10
    img[p > 0] = 12
    out = b''
    for half in (img[:, :32], img[:, 32:]):
        for ty in range(2):
            for tx in range(4):
                for row in half[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]:
                    out += bytes(int(row[x]) | int(row[x + 1]) << 4 for x in range(0, 8, 2))
    return out


def fx(v, bits=12):
    return int(round(v * (1 << bits)))


def main():
    preview = None
    if '--preview' in sys.argv:
        preview = sys.argv[sys.argv.index('--preview') + 1]
    recs = records()
    evrec = evidence_records()
    handlers = [handler(i) for i in range(HANDLER_COUNT)]
    # the records to carry: those evidence opens, those the handlers change
    # to, and the animations' meshes
    used = set(evrec.values())
    for i, sp in SPECIAL.items():
        used |= set(sp.get('anim', ())) | ({sp['to']} if 'to' in sp else set())
    import jarpuzzle                # (the jar puzzle's: the base and the nine pieces)
    used |= set(range(jarpuzzle.JAR_FIRST, jarpuzzle.JAR_LAST + 1))
    used = sorted(r for r in used if r < len(recs))
    meshes = []
    for r in used:
        for m in recs[r]['meshes']:
            if m not in meshes:
                meshes.append(m)
    textures = []
    for m in meshes:
        for t, _, _ in mesh(m)['parts']:
            if t not in textures:
                textures.append(t)
    texids = {t: k for k, t in enumerate(textures)}
    blob = bytearray()
    def align():
        while len(blob) % 4:
            blob.append(0)
    # the textures: the DS's 4bpp as they are (read from ROM as they are drawn)
    assert max(len(set(t for m in recs[r]['meshes'] for t, _, _ in mesh(m)['parts'])) for r in used) <= TEXTURE_SLOTS
    tex_lines = []
    for t in textures:
        w, h, raw, pal = texture(t)
        assert w >= 8 and h >= 8
        align(); off = len(blob); blob += raw
        cols = []
        for v in pal:
            r, g, b = v & 31, v >> 5 & 31, v >> 10 & 31
            cols.append(int(r * VERTEX_COLOUR + 0.5) | int(g * VERTEX_COLOUR + 0.5) << 5 | int(b * VERTEX_COLOUR + 0.5) << 10)
        tex_lines.append('    { 0x%06X, %d, %d, { %s } }, // %s' % (off, int(math.log2(w)), int(math.log2(h)), ', '.join('0x%04X' % c for c in cols), t))
    # the meshes
    mesh_lines = []
    for m in meshes:
        align(); off = len(blob)
        b, tri_off = gba_mesh(m, texids)
        blob += b
        me = mesh(m)
        mesh_lines.append('    { 0x%06X, 0x%06X }, // %s: %d vertices, %d triangles' % (off, off + tri_off, m, len(me['V']), len(me['tris'])))
    meshidx = {m: k for k, m in enumerate(meshes)}
    # the hotspots and blockers: s16 normal (1.14), corners (1.3.12), the id
    quad_lines = []
    def quad_line(q, ident):
        n = [fx(v, 14) for v in q['normal']]
        p = [fx(v) for v in q['pts'].reshape(-1)]
        return '    { %d, %d, { %s }, { %s } },' % (ident, q['word'], ', '.join(map(str, n)), ', '.join(map(str, p)))
    rec_lines = []
    recidx = {}
    for r in used:
        rec = recs[r]
        first = len(quad_lines)
        for q in rec['hot']:
            quad_lines.append(quad_line(q, q['id']))
        for q in rec['block']:
            quad_lines.append(quad_line(q, 0))
        ms = [meshidx[m] for m in rec['meshes']] + [0xFF] * (3 - len(rec['meshes']))
        recidx[r] = len(rec_lines)
        rec_lines.append('    { { %d, %d, %d }, %d, %d, %d }, // DS record %d: %s' % (
            ms[0], ms[1], ms[2], len(rec['hot']), len(rec['block']), first, r, ' + '.join(rec['meshes'])))
    # the ids: the section, the pose (a quaternion, 1.14, and the offsets),
    # the special ones' records
    id_lines = []
    for i in range(HANDLER_COUNT):
        hd = handlers[i] or dict(section=0, rx=0, ry=0, rz=0, tx=0, ty=0, tz=0)
        sp = SPECIAL.get(i, {})
        q = quat_from_matrix(pose_matrix(hd))
        anim = [recidx[a] for a in sp.get('anim', ())] + [0xFF] * (4 - len(sp.get('anim', ())))
        to = recidx[sp['to']] if 'to' in sp else 0xFF
        sec = sp.get('chapter_section', FIXED_SECTIONS.get(i, hd['section']))
        id_lines.append('    { 0x%03X, %d, %d, %d, { %s }, { %d, %d, %d }, { %s }, %d, 0x%03X }, // id %d%s' % (
            sec, 'chapter_section' in sp, sp.get('flag', 0xFF), to,
            ', '.join(str(fx(v, 14)) for v in q), fx(hd['tx']), fx(hd['ty']), fx(hd['tz']),
            ', '.join(map(str, anim)), sum(1 for a in sp.get('anim', ())), sp.get('else_section', 0), i,
            ' (special)' if sp else ''))
    # evidence -> record
    ev_lines = []
    for ev in range(EVIDENCE_COUNT):
        r = evrec.get(ev)
        ev_lines.append(recidx[r] + 1 if r is not None and r in recidx and recs[r]['hot'] else 0)
    # the scenes
    scene_lines = []
    for s in SCENES:
        scene_lines.append('    { 0x%02X, 0x%03X, 0x%03X, %d, 0x%03X, 0x%03X }, // %s (chapter %d)' % (
            s['ev'], s.get('open_section', 0), s.get('hover_section', 0), s['final'], s['after'], s['back'],
            s['name'], s['chapter']))
    # the close-ups (7B): 192 x 128, 16 colours, as BG3's tiles (24 x 16, 8bpp
    # in the close-up's slot: copied to VRAM as they are)
    d = data()
    close_lines = []
    for n in range(CLOSEUP_COUNT):
        off = struct.unpack_from('<3I', dsbin.data(), CLOSEUPS - dsbin.BASE + 12 * n)[1]   # (the English one)
        pal = list(struct.unpack_from('<16H', d, off))
        t = np.frombuffer(d[off + 0x20:off + 0x20 + 0x3000], np.uint8)
        px = np.stack([t & 15, t >> 4], 1).reshape(-1)
        blocks = px.reshape(6, 8, 8, 8, 8).transpose(0, 1, 3, 2, 4).reshape(6, 64, 64)
        img = np.zeros((128, 192), np.uint8)
        for b in range(6):
            img[(b // 3) * 64:(b // 3) * 64 + 64, (b % 3) * 64:(b % 3) * 64 + 64] = blocks[b]
        tiles = img.reshape(16, 8, 24, 8).transpose(0, 2, 1, 3).reshape(-1, 64)
        # (colour 0, the DS's green, clear: the grid shows round the picture)
        align(); o = len(blob); blob += bytes(np.where(tiles == 0, 0, tiles + PAL_CLOSEUP).astype(np.uint8).reshape(-1))
        close_lines.append('    { 0x%06X, { %s } },' % (o, ', '.join('0x%04X' % c for c in pal)))
    # the screen: the frame's tiles and map, the grid's four tiles, the
    # palette; the sprites; the Court Record's "Check"; 2^31 / n
    frame, colours = screen()
    tiles, tmap = frame_tiles(frame)
    align(); o_frame = len(blob); blob += b''.join(bytes(t.reshape(-1)) for t in tiles)
    align(); o_map = len(blob); blob += struct.pack('<600H', *tmap)
    align(); o_grid = len(blob); blob += grid_tiles()
    sset, pieces_ = sprites()
    align(); o_sprites = len(blob); blob += bytes(sset.tiles)
    align(); o_check = len(blob); blob += check_label()
    align(); o_r31 = len(blob)
    blob += struct.pack('<4098I', *([0x7FFFFFFF] + [min(0x7FFFFFFF, round((1 << 31) / n)) for n in range(1, 4098)]))
    jar_lines = jarpuzzle.export(blob, align, meshidx, texids, recs)
    # write
    os.makedirs(os.path.join(ROOT, 'graphics', 'en', 'rfta'), exist_ok=True)
    open(os.path.join(ROOT, 'graphics', 'en', 'rfta', 'evidence3d.bin'), 'wb').write(blob)
    asm = ['@ generated by tools/en/rfta/evidence3d.py: the evidence in 3D (meshes, textures, close-ups)',
           '\t.section rfta_low, "a"', '\t.align 2', '\t.global gEn3dData', 'gEn3dData:',
           '\t.incbin "graphics/en/rfta/evidence3d.bin"']
    open(os.path.join(ROOT, 'data', 'rfta', 'evidence3d.s'), 'w').write('\n'.join(asm) + '\n')
    h = ['// generated by tools/en/rfta/evidence3d.py: the evidence in 3D, from the DS',
         '// (offsets into gEn3dData; the DS\'s object records, its ids\' handlers, its scenes)',
         '#define EN3D_DISTANCE 0x%X      // the camera, 1.19.12' % (DISTANCE << 12),
         '#define EN3D_FOCAL_X %d         // pixels, 8.8' % fx(FOCAL_X, 8),
         '#define EN3D_FOCAL_Y %d' % fx(FOCAL_Y, 8),
         '#define EN3D_FX %d              // (the renderer\'s: 1/16 pixel)' % int(FOCAL_X * 16 + 0.5),
         '#define EN3D_FY %d' % int(FOCAL_Y * 16 + 0.5),
         '#define EN3D_VIEW_X %d' % VIEW_X, '#define EN3D_VIEW_Y %d' % VIEW_Y,
         '#define EN3D_VIEW_W %d' % VIEW_W, '#define EN3D_VIEW_H %d' % VIEW_H,
         '#define EN3D_TEXTURES %d' % len(textures), '#define EN3D_MESHES %d' % len(meshes),
         '#define EN3D_RECORDS %d' % len(rec_lines), '#define EN3D_IDS %d' % HANDLER_COUNT,
         '#define EN3D_CLOSEUPS %d' % CLOSEUP_COUNT, '#define EN3D_SCENES %d' % len(SCENES),
         '#define EN3D_PAL_TEXTURES %d     // BG3: the textures\' 16-colour slots' % PAL_TEXTURES,
         '#define EN3D_PAL_CLOSEUP %d' % PAL_CLOSEUP, '#define EN3D_PAL_FRAME %d' % PAL_FRAME,
         '#define EN3D_FRAME_COLOURS %d' % len(colours),
         '#define EN3D_VIEW_TILES %d       // the frame\'s tiles after these' % VIEW_TILES,
         '#define EN3D_FRAME_TILES %d' % len(tiles),
         '#define EN3D_GFX_FRAME 0x%X' % o_frame, '#define EN3D_GFX_MAP 0x%X        // 30 x 20' % o_map,
         '#define EN3D_GFX_GRID 0x%X       // 4 tiles (4bpp): no line, the column\'s, the row\'s, both' % o_grid,
         '#define EN3D_GRID_BG 0x%04X      // the backdrop' % rgb5(GRID_BG), '#define EN3D_GRID_LINE 0x%04X' % rgb5(GRID_LINE),
         '#define EN3D_GFX_SPRITES 0x%X' % o_sprites, '#define EN3D_SPRITE_TILES %d' % (len(sset.tiles) // 32),
         '#define EN3D_GFX_CHECK 0x%X      // "Check": two 32 x 16 halves (the Court Record\'s label)' % o_check,
         '#define EN3D_R31 0x%X            // 2^31 / n, n 0-4097' % o_r31,
         '#define EN3D_ZOOM_TOP %d         // the knob\'s y: zoomed in' % ZOOM_TRACK[0],
         '#define EN3D_ZOOM_BOTTOM %d' % (ZOOM_TRACK[1] - 8),
         '#define EN3D_TAB_Y %d' % TAB_Y]
    for k, (key, rec) in enumerate(pieces_):
        h.append('#define EN3D_SPRITE_%s %d' % (key, rec))
    for k, s in enumerate(SCENES):
        h.append('#define EN3D_SCENE_%s %d' % (s['name'], k))
    h.append('static const struct En3dTexture sEn3dTextures[] = {'); h += tex_lines; h.append('};')
    h.append('static const struct En3dMesh sEn3dMeshes[] = {'); h += mesh_lines; h.append('};')
    h.append('static const struct En3dQuad sEn3dQuads[] = {'); h += quad_lines; h.append('};')
    h.append('static const struct En3dRecord sEn3dRecords[] = {'); h += rec_lines; h.append('};')
    h.append('static const struct En3dId sEn3dIds[] = {'); h += id_lines; h.append('};')
    h.append('static const u8 sEn3dEvidence[%d] = {  // evidence -> record + 1' % EVIDENCE_COUNT)
    for i in range(0, EVIDENCE_COUNT, 16):
        h.append('    ' + ', '.join(str(v) for v in ev_lines[i:i + 16]) + ',')
    h.append('};')
    h.append('static const struct En3dScene sEn3dScenes[] = {'); h += scene_lines; h.append('};')
    h.append('static const struct En3dCloseup sEn3dCloseups[] = {'); h += close_lines; h.append('};')
    h.append('static const struct En3dPiece sEn3dPieces[] = {')
    for key, rec in sset.sprites:
        for k, (dx, dy, (shape, size), tile) in enumerate(rec):
            h.append('    { %d, %d, %d, %d, %d, %d },%s' % (dx, dy, shape, size, tile, k == len(rec) - 1, ' // ' + key if k == 0 else ''))
    h.append('};')
    h.append('static const u16 sEn3dFramePalette[%d] = { %s };' % (len(colours), ', '.join('0x%04X' % rgb5(c) for c in colours)))
    import fingerprint as fp
    h.append('static const u16 sEn3dUiPalette[16] = { %s };   // (the fingerprints\')' % ', '.join('0x%04X' % rgb5(c or (0, 0, 0)) for c in fp.UI))
    h += jar_lines
    open(os.path.join(ROOT, 'src', 'data', 'en_rfta_evidence3d.h'), 'w').write('\n'.join(h) + '\n')
    print('%d bytes: %d textures, %d meshes, %d records' % (len(blob), len(textures), len(meshes), len(rec_lines)))
    if preview:
        os.makedirs(preview, exist_ok=True)
        previews(preview, recs, used, handlers)


def previews(out, recs, used, handlers):
    """each record at rest and turned, as the GBA's viewport (numpy; the
    GBA's maths in floats)"""
    from PIL import Image
    for r in used:
        imgs = []
        for M in (np.eye(3), rot('y', 120) @ rot('x', 30)):
            imgs.append(render(recs[r]['meshes'], M))
        Image.fromarray(np.concatenate(imgs, 1)).save(os.path.join(out, 'rec%02d.png' % r))


def render(meshes, M, t=(0, 0, 0), bg=(80, 80, 96)):
    W, H = VIEW_W, VIEW_H
    img = np.zeros((H, W, 3), np.uint8); img[:] = bg
    zb = np.full((H, W), np.inf)
    for name in meshes:
        me = mesh(name)
        V = (me['V'] / 4096) @ M + np.array(t)
        z = DISTANCE - V[:, 2]
        sx = W / 2 + FOCAL_X * V[:, 0] / z
        sy = H / 2 - FOCAL_Y * V[:, 1] / z
        for tname, first, cnt in me['parts']:
            w, h, raw, pal = texture(tname)
            idx = np.frombuffer(raw, np.uint8)
            T = np.stack([idx & 15, idx >> 4], 1).reshape(h, w)
            P = np.array([rgb555(c) for c in pal], np.float32) * VERTEX_COLOUR
            for tr in me['tris'][first:first + cnt]:
                vi, ti = tr[:, 0], tr[:, 1]
                Px = np.stack([sx[vi], sy[vi]], 1); Z = z[vi]; UV = me['T'][ti] / 16 * np.array([w / 64, h / 64])
                area = (Px[1, 0] - Px[0, 0]) * (Px[2, 1] - Px[0, 1]) - (Px[2, 0] - Px[0, 0]) * (Px[1, 1] - Px[0, 1])
                if area <= 0:
                    continue
                x0, x1 = int(max(0, np.floor(Px[:, 0].min()))), int(min(W - 1, np.ceil(Px[:, 0].max())))
                y0, y1 = int(max(0, np.floor(Px[:, 1].min()))), int(min(H - 1, np.ceil(Px[:, 1].max())))
                if x1 < x0 or y1 < y0:
                    continue
                xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
                def edge(a, b):
                    return (Px[b, 0] - Px[a, 0]) * (ys - Px[a, 1]) - (Px[b, 1] - Px[a, 1]) * (xs - Px[a, 0])
                w0, w1, w2 = edge(1, 2) / area, edge(2, 0) / area, edge(0, 1) / area
                inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
                if not inside.any():
                    continue
                iz = w0 / Z[0] + w1 / Z[1] + w2 / Z[2]
                zz = 1 / iz
                u = (w0 * UV[0, 0] / Z[0] + w1 * UV[1, 0] / Z[1] + w2 * UV[2, 0] / Z[2]) * zz
                v = (w0 * UV[0, 1] / Z[0] + w1 * UV[1, 1] / Z[1] + w2 * UV[2, 1] / Z[2]) * zz
                col = P[T[np.floor(v).astype(int) % h, np.floor(u).astype(int) % w]]
                sub = zb[y0:y1 + 1, x0:x1 + 1]
                ok = inside & (zz < sub)
                sub[ok] = zz[ok]
                img[y0:y1 + 1, x0:x1 + 1][ok] = col[ok].astype(np.uint8)
    return img


if __name__ == '__main__':
    main()
