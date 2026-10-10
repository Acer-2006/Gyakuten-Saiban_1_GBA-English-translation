#!/usr/bin/env python3
"""Simulate background, person and fade state at every line of the ported
scripts and compare with the GBA scripts: lines printed while the screen is
faded to black (black screens) and person/background pairs the GBA never
shows a line with. Run from the repository root."""
import sys,re,collections,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from phscr import *; from pdump import pdump; import port_script as P
names=['scenario_0']+['scenario_1_%d'%i for i in range(4)]+['scenario_2_%d'%i for i in range(6)]+['scenario_3_%d'%i for i in range(6)]
def sim(toks, start=False):
    """per text run: (dark, white, bg, person, boxshown)"""
    dark=start; white=False; bg=None; person=None; box=True; res=[]; intext=False
    for p,k,op,a in parse(toks,GBA_ARGS)[0]:
        if k=='text':
            if not intext: res.append((dark,white,bg,person,box)); intext=True
            continue
        intext = intext and op in (0x0b,0x0c,0x03,0x01)
        if op==0x12:
            m=a[0]>>8
            if m==2: dark=True
            elif m==1: dark=False
            elif m==4: white=True
            elif m==3: white=False
        elif op==0x1b: bg=a[0]
        elif op==0x1e: person=a[0]
        elif op==0x1c and a[0] in (0,1): box=(a[0]==0)
    return res
def secs(nm):
    f=nm+'_script.phscr'
    gb,gn,go=load('script/'+f); G=section_bounds(gb,go)
    ob,on,oo=load('script_en/'+f); real=sorted(set(o for i,o in enumerate(oo) if G[i] is not None))+[len(ob)]
    for i,x in enumerate(G):
        if not x: continue
        yield i, tokens(gb,*x), tokens(ob,oo[i],real[real.index(oo[i])+1])
if __name__=='__main__':
    gpairs=collections.Counter(); opairs=collections.Counter(); where=collections.defaultdict(list)
    darkg=darko=0; dl=[]
    for nm in names:
        for i,gt,ot in secs(nm):
            st=P.starts_dark(gt); gs=sim(gt,st); os_=sim(ot,st)
            for d,w,bg,pe,bx in gs: gpairs[(bg,pe)]+=1
            for d,w,bg,pe,bx in os_: opairs[(bg,pe)]+=1; where[(bg,pe)].append('%s:%x'%(nm,i+0x80))
            gd=sum(1 for s in gs if s[0]); od=sum(1 for s in os_ if s[0])
            if od>gd: dl.append((nm,hex(i+0x80),gd,od))
    print('text runs while faded to black: sections where port has more than GBA:',len(dl)); print(dl[:30])
    bad=[(k,v) for k,v in opairs.items() if k not in gpairs and k[0] is not None and k[1] is not None]
    print('bg/person pairs at text in port never seen in GBA:',len(bad))
    for k,v in sorted(bad,key=lambda t:-t[1])[:40]: print('  bg %s person %s'%(hex(k[0]),hex(k[1])),v,where[k][:4])
