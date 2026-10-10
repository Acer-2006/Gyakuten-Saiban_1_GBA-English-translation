"""dsseq.py OUTDIR person:id,id,... : record each DS person animation for NF frames.
Saves OUTDIR/PP_ID.npz with imgs (distinct consecutive crops, GBA-sized 160x240x3) and durs."""
import os, sys, struct
import numpy as np
os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
from desmume.emulator import DeSmuME
emu = DeSmuME(); emu.open('/mnt/user-data/uploads/0127_-_Phoenix_Wright_-_Ace_Attorney__USA_.nds'); emu.volume_set(0)
out=sys.argv[1]; os.makedirs(out,exist_ok=True)
spec=sys.argv[2]; NF=int(os.environ.get('NF','160'))
person=int(spec.split(':')[0],16); ids=[int(x,16) for x in spec.split(':')[1].split(',')]
B=0x0211e1c0; CTX=0x020cf4bc; m=emu.memory
def w32(a,v): m.unsigned[a:a+4:4]=[v]
def w16(a,v): m.unsigned[a:a+2:2]=[v]
for i in ids:
    emu.savestate.load_file(os.path.join(os.path.dirname(os.path.abspath(__file__)),'c40.dst'))
    toks=[0x1C,1,0x1B,0xFFF,0x0C,30,0x1E,person,i,i,0x0C,0x7fff]
    base=B+0x2C000
    m.unsigned[base:base+2*len(toks):1]=b''.join(struct.pack('<H',t) for t in toks)
    w16(CTX,0); w16(CTX+2,0); w32(CTX+4,base); w32(CTX+8,base)
    for _ in range(34): emu.cycle(with_joystick=False)
    imgs=[]; durs=[]; prev=None
    for f in range(NF):
        emu.cycle(with_joystick=False)
        a=np.array(emu.screenshot().crop((0,0,256,192)).convert('RGB'))[16:176,8:248]
        if prev is not None and np.array_equal(a,prev): durs[-1]+=1
        else: imgs.append(a); durs.append(1); prev=a
    np.savez_compressed('%s/%02x_%x.npz'%(out,person,i),imgs=np.array(imgs),durs=np.array(durs))
