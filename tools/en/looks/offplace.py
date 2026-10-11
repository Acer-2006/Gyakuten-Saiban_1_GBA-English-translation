"""Poses shown during text on a background where the Japanese game never shows
that animation: how far is the head from where the JP poses there put it?"""
import sys, glob, os, json, collections
sys.path.insert(0,'../gs1en/tools/en')
import port_script as P
from phscr import GBA_ARGS, load, section_bounds, tokens, parse
ph={tuple(int(x,16) for x in k.split(':')):v for k,v in json.load(open('../gs1en/tools/en/pose_heads.json')).items()}
seen=P.seen_poses('../gs1en/script')
vals={k:set(v for pr in c for v in pr) for k,c in seen.items()}
d=sys.argv[1]
res=collections.Counter(); far=collections.Counter()
for f in sorted(glob.glob(d+'/scenario_*.phscr')):
    b,n,o=load(f)
    for si,x in enumerate(section_bounds(b,o)):
        if not x: continue
        bg=cur=None; intext=False
        for pos,kind,op,a in parse(tokens(b,*x),GBA_ARGS)[0]:
            if kind=='text':
                if not intext and bg is not None and cur and cur[0]:
                    k=(bg,cur[0])
                    if k in vals:
                        for g in cur[1:3]:
                            if g in vals[k]: res['onbg']+=1; continue
                            h=ph.get((cur[0],g))
                            dist=min((max(abs(h[0]-ph[(cur[0],q)][0]),abs(h[1]-ph[(cur[0],q)][1])) for q in vals[k] if (cur[0],q) in ph), default=None) if h else None
                            if dist is None: res['nohead']+=1
                            elif dist<4: res['elsewhere_but_same_place']+=1
                            else: res['elsewhere_far']+=1; far[(os.path.basename(f)[:13],si,'%x'%bg,'%x'%cur[0],'%x'%g,dist)]+=1
                intext=True; continue
            if op not in (0x01,0x03,0x0B,0x0C): intext=False
            if op==0x1B and a: bg=a[0]&0x7FFF
            elif op==0x1E and a: cur=(a[0]&0xFF,a[1],a[2])
print(res)
for k,n in sorted(far.items(), key=lambda x:-x[0][5])[:60]: print(n,k)
