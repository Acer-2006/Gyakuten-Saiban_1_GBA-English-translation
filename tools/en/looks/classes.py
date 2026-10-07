"""-> ../gs1en/tools/en/anim_looks.json
 ds:  "person:dsanim" -> GBA animation that shows what the DS animation shows
      (same frames on the same frame counts; found by recording every DS animation)
 cls: "person:gbaanim" -> look class: GBA animations with the same timing and the
      same picture (versions of one pose drawn for different places)

 Two animations are one look only if, lined up, no frame differs by more than a
 few pixels: a talking animation and its idle pose (only the mouth moves) or two
 expressions (only the eyes or the mouth differ) are different looks. A talking
 animation is also a different look from another whose idle partner (in the
 Japanese scripts) is a different look."""
import json, pickle, collections, sys, os
import numpy as np
from equiv import equiv, G
sys.path.insert(0, '../gs1en/tools/en')
import port_script as P
dm=json.load(open('dsmap.json'))
byp=collections.defaultdict(list)
for k in G:
    p,o=k.split('_'); byp[int(p,16)].append(int(o,16))

def _strong(x,y):
    mx=x.sum(2)>24; my=y.sum(2)>24; both=mx&my
    d=np.abs(x-y).sum(2)
    return int(((d>90)&both).sum()), int(both.sum()), int(mx.sum()), int(my.sum())
def strict(p,a,b,same_length=True):
    """most pixels any frame differs by, lined up as frame 0 lines up best"""
    if '%02x_%x'%(p,a) not in G or '%02x_%x'%(p,b) not in G: return 999
    A=G['%02x_%x'%(p,a)][0]; B=G['%02x_%x'%(p,b)][0]
    if same_length and len(A)!=len(B): return 999
    x0=A[0].astype(int); y0=B[0].astype(int)
    best=None
    for dx in range(-8,9):
        for dy in range(-24,25):
            c,n,nx,ny=_strong(x0,np.roll(np.roll(y0,dy,0),dx,1))
            if n<0.5*min(nx,ny): continue
            if best is None or c<best[0]: best=(c,dx,dy)
    if best is None: return 999
    _,dx,dy=best
    return max(_strong(x.astype(int),np.roll(np.roll(y.astype(int),dy,0),dx,1))[0] for x,y in zip(A,B))
STRICT_MAX=6

pairs,_,_=P.jp_pairs()
partner=collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
for person,c in pairs.items():
    for (t,i),k in c.items():
        if t!=i: partner[person&0xFF][t][i]+=k
partner={p:{t:v.most_common(1)[0][0] for t,v in d.items()} for p,d in partner.items()}

def classes(edge):
    par={}
    def find(x):
        while par[x]!=x: par[x]=par[par[x]]; x=par[x]
        return x
    for p,offs in byp.items():
        offs.sort()
        for o in offs: par[(p,o)]=(p,o)
        for a in range(len(offs)):
            for b in range(a+1,len(offs)):
                if edge(p,offs[a],offs[b]): par[find((p,offs[a]))]=find((p,offs[b]))
    return {k:find(k) for k in par}
_st={}
def ok1(p,a,b):
    if not equiv(p,a,b): return False
    if (p,a,b) not in _st: _st[(p,a,b)]=strict(p,a,b)
    return _st[(p,a,b)]<=STRICT_MAX
c1=classes(ok1)
def ok2(p,a,b):
    if not ok1(p,a,b): return False
    pa,pb=partner.get(p,{}).get(a),partner.get(p,{}).get(b)
    if pa is not None and pb is not None and c1.get((p,pa))!=c1.get((p,pb)) and strict(p,pa,pb,False)>STRICT_MAX:
        return False
    return True
c2=classes(ok2)
cls={}; ids={}
for (p,o),r in sorted(c2.items()):
    ids.setdefault(r,len(ids)); cls['%x:%x'%(p,o)]=ids[r]
ds={k:int(v['off'],16) for k,v in dm.items()}
json.dump({'ds':ds,'cls':cls},open('../gs1en/tools/en/anim_looks.json','w'),indent=0,sort_keys=True)
sizes=collections.Counter(collections.Counter(cls.values()).values())
print('anims',len(cls),'classes',len(ids),'class sizes',sorted(sizes.items()))
cut=[(p,a,b,v) for (p,a,b),v in _st.items() if v>STRICT_MAX]
print('pairs split by pixels:',' '.join('%x:%x/%x(%d)'%x for x in sorted(cut)))
