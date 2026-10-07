"""Match each recorded DS animation to the GBA animation it was converted from:
image similarity along the timeline + agreement of frame-change times."""
import pickle, glob, os, json, sys
import numpy as np
G=pickle.load(open('gframes.pkl','rb'))
SRC=sys.argv[1] if len(sys.argv)>1 else '/tmp/lv/dseq'
OUT=sys.argv[2] if len(sys.argv)>2 else 'seqmatch.json'
def ds4(a): return a[:,::2,::2].astype(np.int16)   # gframes are already half-res
byp={}
for k,(gi,gd,term) in G.items():
    p,o=k.split('_')
    same=np.array([[np.array_equal(gi[a],gi[b]) for b in range(len(gi))] for a in range(len(gi))])
    byp.setdefault(int(p,16),[]).append((int(o,16),ds4(gi),gd,term,same))
def expand(durs, n, term):
    t=[]
    while len(t)<n:
        for i,d in enumerate(durs): t+= [i]*int(d)
        if term!=0xFF: t+=[len(durs)-1]*n
    return np.array(t[:n])
def diffs(a, B):
    """a: hxwx3, B: Nxhxwx3 -> mean abs diff over union of non-black"""
    ma=a.sum(2)>24; mb=B.sum(3)>24; u=ma[None]|mb
    d=np.abs(B-a[None]).sum(3)
    return (d*u).sum((1,2))/np.maximum(u.sum((1,2)),1)
def changes(t):
    return np.nonzero(t[1:]!=t[:-1])[0]+1
res={}
for f in sorted(glob.glob(SRC+'/*.npz')):
    p,i=[int(x,16) for x in os.path.basename(f)[:-4].split('_')]
    z=np.load(f); D=z['imgs'][:,::2,::2]; D=ds4(D); dd=z['durs']
    Dt=expand(dd,int(dd.sum()),0xFE)
    nonempty=[j for j in range(len(D)) if (D[j].sum(2)>24).sum()>30]
    if not nonempty or p not in byp: res['%x:%x'%(p,i)]=None; continue
    first=min(np.nonzero(np.isin(Dt,nonempty))[0])
    Dt=Dt[first:]; T=min(len(Dt),150); Dt=Dt[:T]
    # DS changes that are visible (distinct images differ noticeably)
    cand=byp[p]
    allG=np.concatenate([c[1] for c in cand]); idx=np.cumsum([0]+[len(c[1]) for c in cand])
    Mall=np.array([diffs(D[a],allG) for a in range(len(D))])
    Dd=np.array([[float(np.abs(D[a]-D[b]).sum(2).mean()) for b in range(len(D))] for a in range(len(D))])
    dch=set(int(c) for c in changes(Dt))   # every change of the full-size DS picture
    sc=[]
    for n,(o,gi,gd,term,same) in enumerate(cand):
        M=Mall[:,idx[n]:idx[n+1]]
        Gt=expand(gd,T+4,term)
        best=None
        for s in range(0,4):
            g=Gt[s:s+T]
            sd=float(M[Dt,g].mean())
            gch=set(int(c) for c in changes(g) if not same[g[c],g[c-1]])
            inter=len(dch&gch); f1=2*inter/max(len(dch)+len(gch),1) if (dch or gch) else -1.0
            key=(sd-15*max(f1,0))
            if best is None or key<best[0]: best=(key,sd,f1,s)
        sc.append((round(best[0],2),'%x'%o,round(best[1],2),round(best[2],2),best[3],round(float(M[Dt[0]].min()),2)))
    sc.sort()
    res["%x:%x"%(p,i)]=sc
    print('%x:%x'%(p,i),sc[:2],flush=True)
json.dump(res,open(OUT,'w'),indent=0)
