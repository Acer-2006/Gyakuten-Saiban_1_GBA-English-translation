import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from phscr import *
SPECIAL={0x17f:' ',0x161:'.',0x16f:',',0x173:"'",0x16d:':',0x1be:'!',0x1bf:'?',0x180:'-',0x181:'"',0x165:'(',0x166:')',0x172:'*',0xbe:'!',0xbf:'?'}
def ch(v):
    if v in SPECIAL: return SPECIAL[v]
    c=v-0x80
    if 0<=c<10: return chr(48+c)
    if 10<=c<36: return chr(65+c-10)
    if 36<=c<62: return chr(97+c-36)
    return '{%x}'%v
def pdump(toks, args=GBA_ARGS):
    out,_=parse(toks,args); s=''
    for p,k,op,a in out:
        if k=='text': s+=ch(op)
        elif op==1: s+='/\n'
        elif op==2: s+='<P>\n'
        else: s+='<%x%s>'%(op,''.join(' %x'%v for v in a))
    return s
