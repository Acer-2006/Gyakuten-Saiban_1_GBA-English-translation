import struct,difflib,glob
from phscr import *
def sig(toks):
    n=sum(1 for t in toks if t>=0x80)
    return (n>0, tuple(toks[:3]))
def aligned_pairs(gfile, dfile):
    gb,gn,go=load(gfile); db,dn,do=load(dfile)
    G=section_bounds(gb,go); D=section_bounds(db,do)
    Gs=[sig(tokens(gb,*x)) if x else None for x in G]
    Ds=[sig(tokens(db,*x)) if x else None for x in D]
    sm=difflib.SequenceMatcher(None,[str(x) for x in Gs],[str(x) for x in Ds],autojunk=False)
    pairs=[]
    for op,i1,i2,j1,j2 in sm.get_opcodes():
        if op=='equal' or (op=='replace' and i2-i1==j2-j1):
            for k in range(i2-i1): pairs.append((i1+k,j1+k))
    return gb,G,db,D,pairs
