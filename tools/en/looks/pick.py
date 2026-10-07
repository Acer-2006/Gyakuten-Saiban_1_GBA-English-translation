"""DS anim -> GBA anim it shows: prefer exact timing (frame changes on the same frames), then looks."""
import json, collections
sm=json.load(open('seqmatch.json'))
fam=json.load(open('families.json'))
out={}; how=collections.Counter()
for k,sc in sm.items():
    if not sc: continue
    timed=[x for x in sc if (x[3]>=0.8 or x[3]==-1.0) and x[2]<300]
    if timed:
        b=min(timed,key=lambda x:x[2]); h='timing'
    elif sc[0][2]<20:
        b=sc[0]; h='looks'
    else:
        b=sc[0]; h='weak'
    how[h]+=1
    out[k]=dict(off=b[1],how=h,sd=b[2],f1=b[3],alt=[x[1] for x in sc[1:4]])
print(how)
json.dump(out,open('dsmap.json','w'),indent=0)
for k,v in out.items():
    if v['how']=='weak': print(k,v)
