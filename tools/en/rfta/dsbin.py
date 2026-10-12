"""The DS ARM9 binary: where to find it, and a small disassembler on top of
capstone (ARM mode; the game is compiled to ARM, not Thumb).

DS_ARM9 points at the decrypted arm9.bin of your own dump (the ROM header
says where it is: offset 0x4000, 0xccef8 bytes, loaded at 0x02000000);
it is not kept in the repository."""
import os, re, sys
ARM9 = os.environ.get('DS_ARM9', os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'ds_fs', 'arm9.bin'))
BASE = 0x02000000
CMD_TABLE = 0x020b3f98       # 128 script command handlers (US release)
GMAIN = 0x020ceb08           # the DS's gMain
SCRIPT_CTX = 0x020cf4b4      # the DS's gScriptContext (scriptPtr at +0xc)
EVIDENCE_TABLE = 0x020ab048  # 209 entries of 0x18 bytes (the GBA's gEvidenceProfileData layout)
COURT_PRESENT_TABLE = 0x020b42a8  # 35 pointers, one per chapter
_d = None
def data():
    global _d
    if _d is None:
        _d = open(ARM9, 'rb').read()
    return _d

def u32(addr):
    return int.from_bytes(data()[addr - BASE:addr - BASE + 4], 'little')

def handlers():
    """opcode -> handler address"""
    return {op: u32(CMD_TABLE + 4 * op) for op in range(128)}

def disasm(addr, n=200, stop=True):
    """(address, mnemonic, operands) up to the first return"""
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM); md.skipdata = not stop
    d = data(); off = addr - BASE; out = []
    for ins in md.disasm(d[off:off + n * 4], addr):
        ops = ins.op_str
        if ins.mnemonic == 'ldr' and '[pc' in ops:
            m = re.search(r'#(-?0x[0-9a-f]+|-?\d+)', ops)
            k = int(m.group(1), 0) if m else 0
            ops += '   ; =%08x' % u32((ins.address + 8 + k) & ~3)
        out.append((ins.address, ins.mnemonic, ops))
        if stop and ((ins.mnemonic == 'bx' and ins.op_str == 'lr') or (ins.mnemonic.startswith('ldm') and 'pc' in ins.op_str) or (ins.mnemonic == 'pop' and 'pc' in ins.op_str)):
            break
    return out

def sweep(pattern):
    """every instruction in the binary whose text matches the regex"""
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM); md.skipdata = True
    pat = re.compile(pattern)
    for ins in md.disasm(data()[:0xccef8], BASE):
        s = ins.mnemonic + ' ' + ins.op_str
        if pat.search(s):
            yield ins.address, s

if __name__ == '__main__':
    if sys.argv[1] == 'table':
        import collections
        h = handlers(); cnt = collections.Counter(h.values())
        for op, a in h.items():
            print('%02x %08x%s' % (op, a, ' (x%d)' % cnt[a] if cnt[a] > 1 else ''))
    elif sys.argv[1] == 'dis':
        for a in sys.argv[2:]:
            print('---', a)
            for addr, mn, ops in disasm(int(a, 16)):
                print('%08x  %-8s %s' % (addr, mn, ops))
    elif sys.argv[1] == 'sweep':
        for addr, s in sweep(sys.argv[2]):
            print('%08x  %s' % (addr, s))
