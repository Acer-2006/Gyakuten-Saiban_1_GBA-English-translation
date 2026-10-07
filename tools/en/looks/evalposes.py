"""How often does the port show the DS's expression? For every DS pose command
(1E person, talking, idle) compare with the aligned pose in the ported section."""
import sys, os, json, re, glob, difflib, collections
sys.path.insert(0,'../gs1en/tools/en')
from phscr import GBA_ARGS, load, section_bounds, tokens, parse
import port_script
DS_ARGS=port_script.DS_ARGS
fam=json.load(open('families.json'))
dm=json.load(open('dsmap.json'))
from equiv import equiv
SDIR=sys.argv[1] if len(sys.argv)>1 else '../gs1en/script_en'
VERB=len(sys.argv)>2
def vis(p,dv):
    v=dm.get('%x:%x'%(p,dv))
    return int(v['off'],16) if v else None
def F(p,g): return fam.get('%x:%x'%(p,g),('raw',p,g))
tot=collections.Counter(); bad=[]
for gf in sorted(glob.glob(SDIR+'/scenario_*_script.phscr')):
    tag=os.path.basename(gf).split('_script')[0]
    idx=sorted(glob.glob(SDIR+'/scenario_*_script.phscr')).index(gf)
    df='../ds_mes/%02d.bin'%(2*idx+1)
    pairs={}
    for l in open(gf+'.report.txt'):
        m=re.match(r'sec\s+(\d+) <- ds\s+(\d+)',l)
        if m: pairs[int(m.group(1))]=int(m.group(2))
    ob,on,oo=load(gf); db,dn,do=load(df)
    O=section_bounds(ob,oo); D=section_bounds(db,do)
    for gi,di in pairs.items():
        if not O[gi] or not D[di]: continue
        ot=parse(tokens(ob,*O[gi]),GBA_ARGS)[0]; dt=parse(tokens(db,*D[di]),DS_ARGS)[0]
        o1=[a for pos,k,op,a in ot if k=='cmd' and op==0x1E and a and a[0]]
        d1=[a for pos,k,op,a in dt if k=='cmd' and op==0x1E and a and a[0]]
        s=difflib.SequenceMatcher(None,[a[0] for a in o1],[a[0] for a in d1],autojunk=False)
        matched=set()
        for bl in s.get_matching_blocks():
            for k in range(bl.size):
                g=o1[bl.a+k]; d=d1[bl.b+k]; p=d[0]; matched.add(bl.b+k)
                for slot,(gv,dv) in enumerate(zip(g[1:3],d[1:3])):
                    v=vis(p,dv)
                    if v is None: tot['unknown']+=1; continue
                    ok=equiv(p,gv,v)
                    tot['ok' if ok else 'diff']+=1
                    if not ok: bad.append((tag,gi,di,p,['talk','idle'][slot],'ds %x->%x'%(dv,v),'port %x'%gv))
        tot['ds_pose_unaligned']+=len(d1)-len(matched)
print(tot)
c=collections.Counter((b[3],b[5],b[6]) for b in bad)
for k,n in c.most_common(60): print(n,k)
json.dump(bad,open('evalbad.json','w'))
