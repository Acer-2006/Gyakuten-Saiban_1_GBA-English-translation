"""Ace Attorney GBA/DS script (.phscr) parsing helpers."""
import struct
GBA_ARGS = {
 0x00:0,0x01:0,0x02:0,0x03:1,0x04:1,0x05:2,0x06:1,0x07:0,0x08:2,0x09:3,0x0A:1,0x0B:1,0x0C:1,0x0D:0,0x0E:1,0x0F:2,
 0x10:1,0x11:0,0x12:3,0x13:1,0x14:0,0x15:0,0x16:0,0x17:1,0x18:1,0x19:2,0x1A:4,0x1B:1,0x1C:1,0x1D:1,0x1E:3,0x1F:0,
 0x20:1,0x21:0,0x22:2,0x23:2,0x24:0,0x25:1,0x26:1,0x27:2,0x28:1,0x29:1,0x2A:3,0x2B:0,0x2C:1,0x2D:0,0x2E:0,0x2F:2,
 0x30:1,0x31:2,0x32:2,0x33:5,0x34:1,0x35:2,0x36:1,0x37:2,0x38:1,0x39:1,0x3A:2,0x3B:2,0x3C:1,0x3D:1,0x3E:1,0x3F:0,
 0x40:0,0x41:0,0x42:1,0x43:1,0x44:1,0x45:0,0x46:1,0x47:2,0x48:2,0x49:0,0x4A:1,0x4B:1,0x4C:0,
 0x5D:1,  # English patch: centre the following lines (1) / stop (0), as the DS
 0x5E:3,  # English patch: show DS choice labels
}
def load(path_or_bytes):
    b = path_or_bytes if isinstance(path_or_bytes,(bytes,bytearray)) else open(path_or_bytes,'rb').read()
    n = struct.unpack_from('<I',b,0)[0]
    offs = list(struct.unpack_from('<%dI'%n,b,4))
    return b,n,offs
def section_bounds(b,offs):
    srt = sorted(set(o for o in offs if o < len(b))) + [len(b)]
    res=[]
    for o in offs:
        if o>=len(b): res.append(None); continue
        res.append((o, srt[srt.index(o)+1]))
    return res
def tokens(b,o,e):
    return list(struct.unpack_from('<%dH'%((e-o)//2),b,o))
def parse(toks, args):
    """yield (pos, kind, op, argtokens); kind 'cmd'|'text'|'bad'"""
    i=0; out=[]
    while i < len(toks):
        t=toks[i]
        if t >= 0x80:
            out.append((i,'text',t,())); i+=1; continue
        if t not in args:
            out.append((i,'bad',t,())); i+=1; continue
        k=args[t]
        out.append((i,'cmd',t,tuple(toks[i+1:i+1+k]))); i+=1+k
    return out, i
