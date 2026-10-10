import struct, sys, json
import numpy as np
sys.path.insert(0,'../gs1en/tools/en')
import animfmt
JP='/root/.claude/uploads/4a34da0e-f987-5fdb-8edb-9cabaaa698fc/e4d8aefb-GS1.gba'
rom=open(JP,'rb').read()
A=json.load(open('gba_anims.json'))
def seq_gfx(pid,off):
    e=A[str(pid)]
    fd=e['fd']-0x08000000+off
    end=[a for a in e['anims'] if a[0]==off][0][3]
    seq=rom[fd:fd+end]
    go=struct.unpack_from('<I',seq,4)[0]
    gfx=rom[e['gfx']-0x08000000+go:]
    return seq,gfx
def render(pid,off,k,origin=(120,80)):
    seq,gfx=seq_gfx(pid,off)
    return animfmt.render(gfx[:0x40000],seq,k,canvas=(240,160),origin=origin,bg=(0,0,0))
if __name__=='__main__':
    from PIL import Image
    pid,off=int(sys.argv[1],16),int(sys.argv[2],16)
    im=render(pid,off,0)
    Image.fromarray(im).save('r.png')
    h=np.array(Image.open('/tmp/ms_%02x_%x.ppm'%(pid,off)).convert('RGB'))
    Image.fromarray(np.hstack([im,h])).save('cmp.png')
