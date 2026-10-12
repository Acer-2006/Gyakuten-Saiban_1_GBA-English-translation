#!/usr/bin/env python3
"""The fifth episode's investigation setup code, decompiled from the DS ARM9.

Each investigation chapter has three functions on the GBA (case_data.c):
the segment setup (copies the chapter's room and talk tables, picks the
starting room), the room setup (run on entering a room: which examine
hotspots, who is there, which conversation starts, what music) and a room
update. The DS compiled the same C, so the ARM code is a plain sequence of
calls to known helpers with if/else on flags and a switch on the room.
This turns it back into C, as gotos (exact, if not pretty), resolving the
helpers to the GBA's names and pulling the data tables the code copies
(room data, talk data, examine hotspots) out of the binary.

Writes src/en_rfta_rooms.c; the tables it needs are read from the pointer
tables arm9_tables.py documents. Rooms are renumbered as arm9_tables.ROOMS.
usage: rooms.py"""
import os, sys, struct, re, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dsbin
from dsbin import u32, BASE
import arm9_tables
from arm9_tables import room, SEG_SETUP, ROOM_SETUP, ROOM_UPDATE, FIRST, LAST
ROOT = os.path.join(HERE, '..', '..', '..')
GMAIN = 0x020ceb08
EXAM_DATA, ROOM_DATA, TALK_DATA = 0x020ce888, 0x020cec10, 0x020ce608
EXAM_SIZE, TALK_SIZE = 20, 20
# DS helper -> (GBA name, argument count, returns a value)
FUNCS = {
    0x201a144: ('GetFlag', 2, True),
    0x201a170: ('ChangeFlag', 3, False),
    0x2028878: ('InvestigationSetScriptSectionAndFlag', 2, False),
    0x202884c: ('EnSetScriptSectionAndFlagKeepBgm', 2, False),
    0x20288a8: ('InvestigationSetPersonAnimation', 3, False),
    0x2025874: ('PlayBGM', 1, False),
    0x2025788: ('PauseBGM', 0, False),
    0x2022328: ('PlayAnimation', 1, False),
    0x202395c: ('EnLoadChapter', 1, False),
    0x2007498: ('DmaCopy', 3, False),
    0x200744c: ('DmaFill', 3, False),
    0x20250cc: ('EnScriptContextPtr', 0, True),
    0x201ec30: ('EnDecompressBackground', 2, False),
    0x201e164: ('EnShowBackground', 2, False),
    0x201cf0c: ('EnScrollBackgroundEnd', 2, False),
}
# DS gMain byte fields (the DS struct is the GBA's shifted by -0x24 here)
MAIN_BYTES = {0x68: 'currentRoomId', 0x69: 'scenarioIdx', 0x6a: 'caseEnabledFlags', 0x6b: 'health', 0x25: 'unk25'}
COND = {'eq': '==', 'ne': '!=', 'lt': '<', 'ge': '>=', 'gt': '>', 'le': '<=', 'ls': '<=', 'hi': '>', 'lo': '<', 'hs': '>=', 'cc': '<', 'cs': '>=', 'mi': '<', 'pl': '>='}
# people of the fifth episode -> stand-ins (translate.PLACEHOLDER) while their sprites are missing
import translate, port_script
port_script.load_looks()
PLACEHOLDER = translate.PLACEHOLDER
USUAL = None
def usual():
    global USUAL
    if USUAL is None:
        USUAL = translate.usual_poses()
    return USUAL

def disasm(start, end):
    return [x for x in dsbin.disasm(start, (end - start) // 4 + 4, stop=False) if x[0] < end]

def parse_ops(ops):
    return [o.strip() for o in ops.split(',')] if ops else []

def imm(s):
    s = s.strip().lstrip('#')
    return int(s, 0) if s.startswith('0x') or s.startswith('-0x') else int(s)

class Decompiler:
    """Lifts one ARM function to C at register level: every instruction the
    entry can reach (branches, jump tables, conditional returns followed) in
    address order, registers as locals, compares into cA / cB, calls to the
    known helpers by name. Exact rather than pretty; what it cannot place is
    left as a /* TODO */ comment and counted."""
    def __init__(self, tables):
        self.tables = tables      # (kind, addr, size) -> C name
        self.todo = 0

    def insmap(self, start):
        return {a: (m, o) for a, m, o in dsbin.disasm(start, 0x1000, stop=False)}

    def reach(self, start, im):
        seen, work, jt = set(), [start], {}
        while work:
            a = work.pop()
            if a in seen or a not in im:
                continue
            seen.add(a)
            m, o = im[a]
            base, cond = split(m)
            ops = parse_ops(o)
            if base in ('pop', 'ldm') and 'pc' in o or (base == 'bx' and ops == ['lr']):
                if cond: work.append(a + 4)
                continue
            if base == 'b' and o.startswith('#'):
                work.append(imm(o))
                if cond: work.append(a + 4)
                continue
            if base == 'add' and ops[:2] == ['pc', 'pc']:
                # cmp rX, #n-1 ; addls pc, pc, rX, lsl #2 ; b default ; b case0 ...
                k = a - 4
                while split(im[k][0])[0] != 'cmp':
                    k -= 4
                n = imm(parse_ops(im[k][1])[1]) + 1
                jt[a] = (ops[2], [a + 8 + 4 * j for j in range(n)])
                work += [a + 4] + jt[a][1]
                continue
            work.append(a + 4)
        return sorted(seen), jt

    def function(self, name, start):
        im = self.insmap(start)
        order, jt = self.reach(start, im)
        labels = set()
        for a in order:
            m, o = im[a]
            base, cond = split(m)
            if base == 'b' and o.startswith('#'):
                labels.add(imm(o))
        for a, (r, slots) in jt.items():
            labels.update(slots); labels.add(a + 4)
        # a label wherever the instruction before is not its fall-through predecessor
        prev = None
        for a in order:
            if prev is not None and a != prev + 4:
                labels.add(a)
            prev = a
        self.main_regs = set()
        lines = ['void %s(struct Main *main)' % name, '{',
                 '    u32 r0 = (u32)main, r1 = 0, r2 = 0, r3 = 0, r4 = 0, r5 = 0, r6 = 0, r7 = 0, r8 = 0, r9 = 0, r10 = 0, r11 = 0, r12 = 0;',
                 '    u32 cA = 0, cB = 0, sp0 = 0;']
        consts = {}
        main_regs = {'r0'}
        for a in order:
            m, o = im[a]
            if a in labels:
                lines.append('L_%x: ;' % a)
                consts = {}
                main_regs = {r for r in main_regs if r in self.entry_main}
            st, consts, main_regs = self.insn(a, m, o, consts, main_regs, jt)
            lines += ['    ' + x for x in st]
        lines.append('}')
        used = set(re.findall(r'goto (L_[0-9a-f]+)', '\n'.join(lines)))
        lines = [l for l in lines if not (l.startswith('L_') and l.split(':')[0] not in used)]
        return lines, len(order)

    def insn(self, a, m, o, consts, main_regs, jt):
        base, cond = split(m)
        ops = parse_ops(o)
        g = guard(cond)
        out = []
        def R(x):
            return REG.get(x, x)
        def setreg(rd, expr, value=None, is_main=False):
            out.append('%s%s = %s;' % (g, R(rd), expr))
            if cond:
                consts.pop(rd, None); main_regs.discard(rd)
            else:
                if value is None: consts.pop(rd, None)
                else: consts[rd] = value
                if is_main: main_regs.add(rd)
                else: main_regs.discard(rd)
        def op2(x):
            if x.startswith('#'):
                return '0x%X' % (imm(x) & 0xFFFFFFFF), imm(x) & 0xFFFFFFFF
            mm = re.match(r'(\w+), (lsl|lsr|asr) #(\w+)', x)
            if mm:
                return '(%s %s %d)' % (R(mm.group(1)), {'lsl': '<<', 'lsr': '>>', 'asr': '>>'}[mm.group(2)], imm(mm.group(3))), None
            return R(x), consts.get(x)
        if base in ('push', 'stmdb'):
            return out, consts, main_regs
        if base in ('pop', 'ldm'):
            if 'pc' in o:
                out.append('%sreturn;' % g)
            return out, consts, main_regs
        if base in ('add', 'sub') and ops[0] == 'sp':
            return out, consts, main_regs
        if base == 'bx' and ops == ['lr']:
            out.append('%sreturn;' % g); return out, consts, main_regs
        if base in ('mov', 'mvn') and len(ops) == 2:
            e, v = op2(ops[1])
            if base == 'mvn':
                e, v = ('0x%X' % ((~v) & 0xFFFFFFFF), (~v) & 0xFFFFFFFF) if v is not None else ('~' + e, None)
            setreg(ops[0], e, v, ops[1] in main_regs)
            return out, consts, main_regs
        if base == 'ldr' and '[pc' in o and '=' in o:
            v = int(o.split('=')[-1].strip(), 16)
            setreg(ops[0], '0x%X' % v, v, v == GMAIN)
            return out, consts, main_regs
        if base in ('ldr', 'str') and ops[1:] == ['[sp]']:
            if base == 'str':
                out.append('%ssp0 = %s;' % (g, R(ops[0])))
                if ops[0] in consts: consts['sp0'] = consts[ops[0]]
            else:
                setreg(ops[0], 'sp0', consts.get('sp0'))
            return out, consts, main_regs
        mm = re.match(r'(\w+), \[(\w+)(?:, #(-?0x[0-9a-f]+|-?\d+))?\]$', o)
        if base in ('ldrb', 'ldrh', 'ldr', 'ldrsb', 'ldrsh', 'strb', 'strh', 'str') and mm:
            rd, rb, off = mm.group(1), mm.group(2), imm(mm.group(3) or '0')
            if rb in main_regs:
                if base.startswith('ld'):
                    if off == 0x68: setreg(rd, 'EnDsRoom(main->currentRoomId)')
                    elif off == 0x69: setreg(rd, 'main->scenarioIdx')
                    elif off == 0x04: setreg(rd, '1 /* DS language: English */', 1)
                    else:
                        self.todo += 1; setreg(rd, '0 /* TODO: DS gMain+0x%x */' % off)
                else:
                    if off == 0x68: out.append('%smain->currentRoomId = EnGbaRoom(%s);' % (g, R(rd)))
                    elif off == 0x69: out.append('%smain->scenarioIdx = %s;' % (g, R(rd)))
                    else:
                        self.todo += 1; out.append('/* TODO: %s DS gMain+0x%x = %s */' % (m, off, R(rd)))
            else:
                self.todo += 1
                where = '0x%X' % consts[rb] if rb in consts else R(rb)
                if base.startswith('ld'): setreg(rd, '0 /* TODO: %s [%s + 0x%x] */' % (m, where, off))
                else: out.append('/* TODO: %s [%s + 0x%x] = %s */' % (m, where, off, R(rd)))
            return out, consts, main_regs
        if base in ('cmp', 'tst'):
            e, v = op2(ops[1])
            if base == 'cmp':
                out.append('cA = %s; cB = %s;' % (R(ops[0]), e))
            else:
                out.append('cA = %s & %s; cB = 0;' % (R(ops[0]), e))
            return out, consts, main_regs
        if base == 'add' and ops[:2] == ['pc', 'pc']:
            r, slots = jt[a]
            out.append('%sswitch (%s) {' % (g, R(r)))
            for j, t in enumerate(slots):
                out.append('    case %d: goto L_%x;' % (j, t))
            out.append('}')
            return out, consts, main_regs
        if base in ('and', 'ands', 'orr', 'orrs', 'eor', 'bic', 'add', 'adds', 'sub', 'subs', 'rsb', 'lsl', 'lsr', 'asr', 'lsls', 'lsrs'):
            rd, rn = ops[0], ops[1]
            e, v = op2(', '.join(ops[2:]))
            sym = {'and': '&', 'orr': '|', 'eor': '^', 'bic': '& ~', 'add': '+', 'sub': '-', 'lsl': '<<', 'lsr': '>>', 'asr': '>>'}
            b0 = base.rstrip('s') if base not in ('subs', 'adds', 'ands', 'orrs', 'lsls', 'lsrs') else base[:-1]
            if b0 == 'rsb':
                expr = '(%s - %s)' % (e, R(rn))
            else:
                expr = '(%s %s %s)' % (R(rn), sym[b0], e)
            cv = None
            if rn in consts and v is not None:
                x = consts[rn]
                cv = {'&': x & v, '|': x | v, '^': x ^ v, '& ~': x & ~v, '+': x + v, '-': x - v, '<<': x << v, '>>': x >> v}.get(sym.get(b0), None)
                cv = cv & 0xFFFFFFFF if cv is not None else None
            setreg(rd, expr, cv)
            if base.endswith('s') and base not in ('ands',) or base == 'ands':
                out.append('cA = %s; cB = 0;' % R(rd))
            return out, consts, main_regs
        if base == 'b' and o.startswith('#'):
            out.append('%sgoto L_%x;' % (g, imm(o))); return out, consts, main_regs
        if base == 'bl':
            out += self.call(imm(o), consts, g)
            for r in ('r0', 'r1', 'r2', 'r3', 'ip'):
                consts.pop(r, None); main_regs.discard(r)
            return out, consts, main_regs
        self.todo += 1
        out.append('/* TODO: %08x %s %s */' % (a, m, o))
        return out, consts, main_regs

    def call(self, t, consts, g):
        c = lambda r: consts.get(r)
        name = FUNCS.get(t, (None,))[0]
        if name == 'GetFlag': return ['%sr0 = GetFlag(r0, r1);' % g]
        if name == 'ChangeFlag': return ['%sChangeFlag(r0, r1, r2);' % g]
        if name in ('InvestigationSetScriptSectionAndFlag', 'EnSetScriptSectionAndFlagKeepBgm'):
            return ['%s%s(r0, r1);' % (g, name)]
        if name == 'PauseBGM': return ['%sPauseBGM();' % g]
        if name == 'EnLoadChapter': return ['%sEnLoadChapter(r0);' % g]
        if name == 'EnScriptContextPtr': return ['%sr0 = 0; /* the DS script context */' % g]
        if name == 'PlayBGM':
            s = c('r0')
            if s in translate.PLACEHOLDER_BGM:
                return ['%sPlayBGM(%d); /* stand-in for the DS song 0x%x */' % (g, translate.PLACEHOLDER_BGM[s], s)]
            return ['%sPlayBGM(r0);' % g]
        if name == 'PlayAnimation':
            self.todo += 1
            return ['/* TODO: %sPlayAnimation(DS animation %s) */' % (g, '0x%x' % c('r0') if c('r0') is not None else 'r0')]
        if name == 'InvestigationSetPersonAnimation':
            p, t1, t2 = c('r0'), c('r1'), c('r2')
            if None in (p, t1, t2):
                self.todo += 1
                return ['/* TODO: %sInvestigationSetPersonAnimation(r0, r1, r2) with DS poses */' % g]
            pp = p & 0xFF
            if pp in PLACEHOLDER:
                gt, gi = usual().get(PLACEHOLDER[pp], (0, 0))
                return ['%sInvestigationSetPersonAnimation(0x%X, 0x%X, 0x%X); /* %s; DS 0x%x 0x%x 0x%x */' %
                        (g, (p & 0xFF00) | PLACEHOLDER[pp], gt, gi, translate.PLACEHOLDER_NAMES[pp], p, t1, t2)]
            res = []
            for v in (t1, t2):
                m = port_script.ds_look(pp, v)
                gv = m[0] if m else ANIM_ANY().get((pp, v))
                if gv is None:
                    gv = usual().get(pp, (0, 0))[0]
                res.append(gv)
            return ['%sInvestigationSetPersonAnimation(0x%X, 0x%X, 0x%X); /* DS poses 0x%x 0x%x */' % (g, p, res[0], res[1], t1, t2)]
        if name == 'DmaCopy':
            src, dst, n = c('r0'), c('r1'), c('r2')
            kind = {EXAM_DATA: 'exam', ROOM_DATA: 'room', TALK_DATA: 'talk'}.get(dst)
            if None in (src, n) or kind is None:
                self.todo += 1
                return ['/* TODO: DmaCopy(%s, %s, %s) */' % tuple('0x%x' % x if x is not None else '?' for x in (src, dst, n))]
            cname = self.tables.setdefault((kind, src, n), '%s_%x' % ({'exam': 'gExaminationData_5', 'room': 'gRoomData_5', 'talk': 'gTalkData_5'}[kind], src))
            if kind == 'exam': return ['%sLOADEXAMDATA(%s);' % (g, cname)]
            if kind == 'room': return ['%sDmaCopy16(3, %s, gMain.roomData, sizeof(%s));' % (g, cname, cname)]
            return ['%sDmaCopy16(3, %s, gTalkData, sizeof(%s));' % (g, cname, cname)]
        if name == 'DmaFill':
            dst = c('r1')
            if dst == EXAM_DATA:
                return ['%sDmaFill16(3, 0xFFFF, gExaminationData, sizeof(gExaminationData));' % g]
            self.todo += 1
            return ['/* TODO: DmaFill(%s) */' % ('0x%x' % dst if dst is not None else '?')]
        if name in ('EnDecompressBackground', 'EnShowBackground', 'EnScrollBackgroundEnd'):
            return ['%s%s(r1);' % (g, name)]
        if name in ('EnRftaDay1RoomHook', 'EnRftaDay2RoomHook', 'EnRftaDay3RoomHook'):
            return ['%s%s(main);' % (g, name)]
        self.todo += 1
        return ['/* TODO: %scall DS 0x%x */' % (g, t)]

    def run(self, name, start):
        # registers that hold gMain from the prologue on (mov rX, r0 before any call)
        self.entry_main = set()
        for a, m, o in dsbin.disasm(start, 12, stop=False):
            ops = parse_ops(o)
            if m == 'mov' and len(ops) == 2 and ops[1] == 'r0':
                self.entry_main.add(ops[0])
            if m == 'ldr' and '=%08x' % GMAIN in o and ops[0] in ('r4', 'r5', 'r6', 'r7', 'r8'):
                self.entry_main.add(ops[0])
            if m.startswith('b') and m not in ('bic', 'bics'):
                break
        return self.function(name, start)

REG = {'sb': 'r9', 'sl': 'r10', 'fp': 'r11', 'ip': 'r12'}
def split(m):
    for c in ('eq', 'ne', 'lt', 'ge', 'gt', 'le', 'ls', 'hi', 'lo', 'hs', 'cc', 'cs', 'mi', 'pl'):
        if m.endswith(c) and m[:-2] in ('b', 'mov', 'mvn', 'add', 'sub', 'ldr', 'str', 'ldrb', 'strb', 'ldrh', 'strh', 'pop', 'ldm', 'bx', 'bl', 'cmp', 'orr', 'and', 'adds', 'subs'):
            return m[:-2], c
    return m, ''
COND_C = {'eq': '==', 'ne': '!=', 'hs': '>=', 'cs': '>=', 'lo': '<', 'cc': '<', 'hi': '>', 'ls': '<='}
def guard(cond):
    if not cond:
        return ''
    if cond in COND_C:
        return 'if (cA %s cB) ' % COND_C[cond]
    if cond in ('lt', 'ge', 'gt', 'le'):
        return 'if ((s32)cA %s (s32)cB) ' % {'lt': '<', 'ge': '>=', 'gt': '>', 'le': '<='}[cond]
    return 'if ((s32)(cA - cB) %s 0) ' % ('<' if cond == 'mi' else '>=')
_ANY = None
def ANIM_ANY():
    global _ANY
    if _ANY is None:
        import json
        votes = collections.defaultdict(collections.Counter)
        for k, gv in json.load(open(os.path.join(HERE, '..', 'anim_map.json'))).items():
            tag, person, dv = k.split(':')
            votes[(int(person, 16) & 0xFF, int(dv, 16))][gv] += 1
        _ANY = {k: c.most_common(1)[0][0] for k, c in votes.items()}
    return _ANY

def table_c(kind, addr, size, name):
    d = dsbin.data(); raw = d[addr - BASE:addr - BASE + size]
    lines = []
    if kind == 'exam':
        n = size // EXAM_SIZE
        lines.append('const struct ExaminationData %s[%d] = {' % (name, n))
        for i in range(n):
            sec, typ, anim = struct.unpack_from('<HBB', raw, i * EXAM_SIZE)
            pts = struct.unpack_from('<8H', raw, i * EXAM_SIZE + 4)
            lines.append('    { .examinationSection = 0x%X, .type = 0x%X, .animId = 0x%X, .area = { .points = { {%d, %d}, {%d, %d}, {%d, %d}, {%d, %d} } } },' % ((sec, typ, anim) + pts))
        lines.append('};')
    elif kind == 'room':
        n = size // 8
        rows = [list(raw[i * 8:(i + 1) * 8]) for i in range(n)]
        # renumber: row r of the DS -> row room(r); the move targets in [4..7] are rooms too
        new = [[0xFF] * 8 for _ in range(max(room(r) for r in range(n)) + 1)]
        for r, row in enumerate(rows):
            row = row[:4] + [room(v) if v != 0xFF else 0xFF for v in row[4:]]
            new[room(r)] = row
        lines.append('const u8 %s[%d][8] = {' % (name, len(new)))
        for row in new:
            lines.append('    { %s },' % ', '.join('0x%02X' % v for v in row))
        lines.append('};')
    else:
        n = size // TALK_SIZE
        lines.append('const struct TalkData %s[%d] = {' % (name, n))
        for i in range(n):
            r, p, dm, en = struct.unpack_from('<BBBB', raw, i * TALK_SIZE)
            icons = struct.unpack_from('<4B', raw, i * TALK_SIZE + 4)
            flags = struct.unpack_from('<4B', raw, i * TALK_SIZE + 8)
            secs = struct.unpack_from('<4H', raw, i * TALK_SIZE + 12)
            lines.append('    { .roomId = 0x%X, .personId = 0x%X, .unk2 = 0x%X, .enableFlag = 0x%X, .iconId = {%s}, .talkFlagId = {%s}, .talkSection = {%s} },' %
                         (room(r), p, dm, en, ', '.join('0x%X' % v for v in icons), ', '.join('0x%X' % v for v in flags), ', '.join('0x%X' % v for v in secs)))
        lines.append('};')
    return lines

def main():
    tables = {}
    dec = Decompiler(tables)
    funcs = []
    seen = {}
    for k in range(FIRST, LAST + 1):
        for kind, table in (('SegmentSetup', SEG_SETUP), ('RoomSetup', ROOM_SETUP), ('RoomUpdate', ROOM_UPDATE)):
            addr = u32(table + 4 * k)
            if addr == 0x02028848:   # InvestigationDummy
                continue
            if addr in seen:
                continue
            seen[addr] = 'Investigation%s_5_%02d' % (kind, k - FIRST)
            funcs.append((seen[addr], addr))
    # the fifth episode's own helpers these call
    extra = [(0x206845c, 'EnRftaDay1RoomHook'), (0x2096868, 'EnRftaDay2RoomHook'), (0x20971ac, 'EnRftaDay3RoomHook')]
    for addr, name in extra:
        funcs.append((name, addr))
        FUNCS[addr] = (name, 0, False)
    funcs.sort(key=lambda x: x[1])
    body = []
    for name, addr in funcs:
        f, n = dec.run(name, addr)
        body += ['// DS %08x, %d instructions' % (addr, n)] + f + ['']
    lines = ['// generated by tools/en/rfta/rooms.py from the DS ARM9: the fifth episode\'s',
             '// investigation setup code and its tables (see that file)',
             '#include "global.h"', '#include "main.h"', '#include "case_data.h"', '#include "investigation.h"',
             '#include "sound.h"', '#include "animation.h"', '#include "background.h"', '#include "script.h"', '#include "en_rfta.h"', '']
    for (kind, addr, size), name in sorted(tables.items(), key=lambda kv: kv[0][1]):
        lines += table_c(kind, addr, size, name) + ['']
    lines += body
    hdr = ['// generated by tools/en/rfta/rooms.py: the fifth episode\'s entries of the',
           '// investigation function tables in case_data.c (chapters 17-34)', '#ifndef GUARD_EN_RFTA_ROOMS_H', '#define GUARD_EN_RFTA_ROOMS_H', '']
    for kind, table, macro in (('SegmentSetup', SEG_SETUP, 'RFTA_SEGMENT_SETUP'), ('RoomSetup', ROOM_SETUP, 'RFTA_ROOM_SETUP'), ('RoomUpdate', ROOM_UPDATE, 'RFTA_ROOM_UPDATE')):
        names = []
        for k in range(FIRST, LAST + 1):
            addr = u32(table + 4 * k)
            names.append('InvestigationDummy' if addr == 0x02028848 else seen[addr])
        hdr.append('#define %s %s' % (macro, ', '.join(names)))
    for n, a in funcs:
        hdr.append('void %s(struct Main *main);' % n)
    hdr += ['', '#endif']
    open(os.path.join(ROOT, 'include', 'en_rfta_rooms.h'), 'w').write('\n'.join(hdr) + '\n')
    lines.insert(lines.index('#include "en_rfta.h"') + 1, '#include "en_rfta_rooms.h"')
    lines.insert(lines.index('#include "en_rfta_rooms.h"') + 1, '#if RFTA')
    lines.append('#endif // RFTA')
    out = os.path.join(ROOT, 'src', 'en_rfta_rooms.c')
    open(out, 'w').write('\n'.join(lines) + '\n')
    print('wrote', out, len(lines), 'lines;', len(tables), 'tables;', dec.todo, 'TODO;', [n for n, a in funcs])

if __name__ == '__main__':
    main()
