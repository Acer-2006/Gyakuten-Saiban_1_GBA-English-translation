"""Fast renderer for every GBA person animation frame -> gframes.npz"""
import struct, json, sys
import numpy as np
sys.path.insert(0,'../gs1en/tools/en')
import animfmt
from grender import rom, A, seq_gfx
def render_frame(seq, gfx, k, pals):
    fr=animfmt.frames(seq)[k]
    img=np.zeros((160,240,3),np.uint8)
    for x,y,data in animfmt.sprites(seq, fr[0]):
        w,h=animfmt.SIZES[data>>12]
        t=np.frombuffer(animfmt.sprite_tiles(gfx,data,fr[2]),np.uint8)
        nib=np.stack([t&15,t>>4],1).reshape(-1).reshape(-1,8,8)
        tw=w//8
        blk=nib.reshape(h//8,tw,8,8).transpose(0,2,1,3).reshape(h,w)
        pal=np.array(pals[((data>>9)&7) if fr[2]&1 else ((data>>11)&1)],np.uint8)
        x0,y0=120+x,80+y
        ys,xs=np.nonzero(blk)
        py,px=ys+y0,xs+x0
        ok=(px>=0)&(px<240)&(py>=0)&(py<160)
        img[py[ok],px[ok]]=pal[blk[ys[ok],xs[ok]]]
    return img
def timeline(pid,off):
    seq,gfx=seq_gfx(pid,off)
    gfx=gfx[:0x40000]
    fr=animfmt.frames(seq)
    pals=animfmt.palettes(gfx)
    imgs=[]; durs=[]; term=None
    for k,(sd,dur,fl,song,act) in enumerate(fr):
        if dur in (0xFF,0xFE,0xFD):
            term=dur; break
        imgs.append(render_frame(seq,gfx,k,pals)); durs.append(dur)
    if not imgs:   # single terminator frame: show it
        imgs.append(render_frame(seq,gfx,0,pals)); durs.append(1); term=0xFE
    return imgs,durs,term
if __name__=='__main__':
    out={}
    for pid,e in A.items():
        for a in e['anims']:
            try:
                imgs,durs,term=timeline(int(pid),a[0])
            except Exception as ex:
                print('fail',pid,hex(a[0]),ex); continue
            out['%02x_%x'%(int(pid),a[0])]=(np.array(imgs)[:,::2,::2],np.array(durs),term)
        print(pid,len(e['anims']),flush=True)
    import pickle; pickle.dump(out,open('gframes.pkl','wb'))
