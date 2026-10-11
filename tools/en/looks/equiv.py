import json, pickle, functools
import numpy as np
from look2 import look2
G=pickle.load(open('/tmp/claude-0/-home-claude/4a34da0e-f987-5fdb-8edb-9cabaaa698fc/scratchpad/amap/gframes.pkl','rb'))
fam=json.load(open('/tmp/claude-0/-home-claude/4a34da0e-f987-5fdb-8edb-9cabaaa698fc/scratchpad/amap/families.json'))
def look(p,a,b):
    A=G.get('%02x_%x'%(p,a)); B=G.get('%02x_%x'%(p,b))
    if A is None or B is None: return 999
    x=A[0][0].astype(int); y=B[0][0].astype(int)
    best=9e9
    for dx in range(-8,9,1):
        for dy in range(-8,9,1):
            ys=np.roll(np.roll(y,dy,0),dx,1)
            mx=x.sum(2)>24; my=ys.sum(2)>24; both=mx&my
            if both.sum()<50: continue
            d=np.abs(x-ys).sum(2)[both].mean()*(1+(1-both.sum()/(mx|my).sum()))
            best=min(best,d)
    return best
@functools.lru_cache(None)
def equiv(p,a,b):
    if a==b: return True
    if fam.get('%x:%x'%(p,a))==fam.get('%x:%x'%(p,b)) and fam.get('%x:%x'%(p,a)) is not None: return True
    A=G.get('%02x_%x'%(p,a)); B=G.get('%02x_%x'%(p,b))
    if A is None or B is None: return False
    if len(A[1])!=len(B[1]) or max(abs(int(x)-int(y)) for x,y in zip(A[1],B[1]))>1: return False
    r=look2(p,a,b)
    return r is not None and r[0]<10 and r[2]>0.6
