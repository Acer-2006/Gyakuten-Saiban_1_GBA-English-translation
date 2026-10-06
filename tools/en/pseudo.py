"""Section tokens <-> readable pseudo-text, for small wording fixes.
Text is plain characters; every command is written as <op:arg:arg> and a
newline (command 01) as \\n."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from phscr import parse
import dsfont

SPECIAL = {0x161: '.', 0x16f: ',', 0x173: "'", 0x17c: '&', 0x180: '-', 0x16d: ':', 0x1bf - 0x80 + 0x80: '?'}
def tok2ch(t):
    c = t - 0x80
    if 0 <= c < 10: return chr(48 + c)
    if 10 <= c < 36: return chr(65 + c - 10)
    if 36 <= c < 62: return chr(97 + c - 36)
    if t == 0x17F: return ' '
    for ch, code in dsfont.PUNCT.items():
        if code == c: return ch
    return None

def to_pseudo(toks, args_table):
    items, _ = parse(toks, args_table)
    out = []
    for pos, kind, op, args in items:
        if kind == 'text':
            ch = tok2ch(op)
            out.append(ch if ch and ch not in '<>\\' else '{%x}' % op)
        elif op == 1:
            out.append('\\n')
        else:
            out.append('<' + ':'.join('%x' % v for v in [op] + list(args)) + '>')
    return ''.join(out)

def from_pseudo(s):
    toks, i = [], 0
    while i < len(s):
        if s.startswith('\\n', i):
            toks.append(1); i += 2
        elif s[i] == '<':
            j = s.index('>', i); toks.extend(int(v, 16) for v in s[i + 1:j].split(':')); i = j + 1
        elif s[i] == '{':
            j = s.index('}', i); toks.append(int(s[i + 1:j], 16)); i = j + 1
        else:
            toks.append(dsfont.code(s[i]) + 0x80); i += 1
    return toks
