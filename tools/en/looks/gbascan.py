"""Find every person animation in the JP GBA ROM by scanning for valid anim headers."""
import struct, json, sys
JP='/root/.claude/uploads/4a34da0e-f987-5fdb-8edb-9cabaaa698fc/e4d8aefb-GS1.gba'
rom=open(JP,'rb').read()
TAB=0x18dd4
SIZES={0,1,2,4,5,6,8,9,10,12,13,14}
def r32(a): return struct.unpack_from('<I',rom,a)[0]
def valid(b, lim):
    h0,nf,go=struct.unpack_from('<HHI',rom,b)
    if h0!=0 or not 1<=nf<=120: return None
    hdr=8+8*nf
    end=hdr
    for k in range(nf):
        sd,dur,fl,song,act=struct.unpack_from('<HBBBB',rom,b+8+8*k)
        if sd<hdr or sd&3 or sd>=lim: return None
        last=(k==nf-1)
        if last and dur not in (0xFF,0xFE,0xFD): return None
        if not last and (dur in (0xFF,0xFE,0xFD) or dur==0): return None
        n=struct.unpack_from('<H',rom,b+sd)[0]
        if not 1<=n<=128: return None
        for j in range(n):
            x,y,dat=struct.unpack_from('<bbH',rom,b+sd+4+4*j)
            if dat>>12 not in SIZES: return None
        end=max(end,sd+4+4*n)
    return (nf,go,end)
res={}
ents=[]
for pid in range(0x40):
    gfx,fd,cnt=struct.unpack_from('<3I',rom,TAB+12*pid)
    if 0x08000000<=fd<0x0a000000 and 0x08000000<=gfx<0x0a000000: ents.append((pid,gfx,fd,cnt))
fds=sorted(set(e[2] for e in ents)|set(e[1] for e in ents))
for pid,gfx,fd,cnt in ents:
    nxt=[f for f in fds if f>fd]; lim=(nxt[0]-fd) if nxt else 0x10000
    lim=min(lim,0x20000)
    anims=[]
    o=0
    while o<lim:
        v=valid(fd-0x08000000+o, lim-o)
        if v:
            anims.append([o,v[0],v[1],v[2]])
        o+=4
    res[pid]=dict(gfx=gfx,fd=fd,cnt=cnt,lim=lim,anims=anims)
    print(pid,hex(fd),hex(lim),len(anims))
json.dump(res,open('gba_anims.json','w'))
