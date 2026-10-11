import numpy as np, pickle, collections, json
G=pickle.load(open('gframes.pkl','rb'))
def look2(p,a,b):
    """best alignment: (mean abs diff over pixels both draw, fraction of such pixels differing >60, IoU)"""
    x=G['%02x_%x'%(p,a)][0][0].astype(int); y=G['%02x_%x'%(p,b)][0][0].astype(int)
    mx=x.sum(2)>24
    best=None
    for dx in range(-8,9):
        for dy in range(-16,17):
            ys=np.roll(np.roll(y,dy,0),dx,1); my=ys.sum(2)>24; both=mx&my
            if both.sum()<50: continue
            d=np.abs(x-ys).sum(2)[both]
            r=(float(d.mean()), float((d>60).mean()), float(both.sum()/(mx|my).sum()), dx, dy)
            if best is None or r[0]<best[0]: best=r
    return best
if __name__=='__main__':
    byp=collections.defaultdict(list)
    for k,(gi,gd,t) in G.items():
        p,o=k.split('_'); byp[int(p,16)].append((int(o,16),tuple(gd)))
    res=[]
    for p,l in byp.items():
        for i in range(len(l)):
            for j in range(i+1,len(l)):
                if l[i][1]==l[j][1]:
                    r=look2(p,l[i][0],l[j][0])
                    if r: res.append(('%x'%p,'%x'%l[i][0],'%x'%l[j][0])+tuple(round(v,3) for v in r))
    json.dump(res,open('pairs2.json','w'))
    res.sort(key=lambda r:r[3])
    for r in res[:400]: print(r)
