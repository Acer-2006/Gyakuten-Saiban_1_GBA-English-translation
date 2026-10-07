"""-> ../gs1en/tools/en/anim_looks.json
 ds:  "person:dsanim" -> GBA animation that shows what the DS animation shows
      (same frames on the same frame counts; found by recording every DS animation)
 cls: "person:gbaanim" -> look class: GBA animations with the same timing and the
      same picture (versions of one pose drawn for different places)"""
import json, pickle, collections
from equiv import equiv, G
dm=json.load(open('dsmap.json'))
byp=collections.defaultdict(list)
for k in G:
    p,o=k.split('_'); byp[int(p,16)].append(int(o,16))
par={}
def find(x):
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
for p,offs in byp.items():
    offs.sort()
    for o in offs: par[(p,o)]=(p,o)
    for a in range(len(offs)):
        for b in range(a+1,len(offs)):
            if equiv(p,offs[a],offs[b]): par[find((p,offs[a]))]=find((p,offs[b]))
cls={}; ids={}
for (p,o) in par:
    r=find((p,o)); ids.setdefault(r,len(ids)); cls['%x:%x'%(p,o)]=ids[r]
ds={k:int(v['off'],16) for k,v in dm.items()}
json.dump({'ds':ds,'cls':cls},open('../gs1en/tools/en/anim_looks.json','w'),indent=0,sort_keys=True)
sizes=collections.Counter(collections.Counter(cls.values()).values())
print('anims',len(cls),'classes',len(ids),'class sizes',sorted(sizes.items()))
