"""Run the fifth episode in DeSmuME (python-desmume) and log the script.

dsrun.py STATE CHAPTER_FILE SEC OUT NFRAMES [opcode_hex ...]
  loads a savestate, puts CHAPTER_FILE (a decompressed chapter script,
  ds_script.chapter) into the DS's script buffer and runs section SEC (hex;
  -1 keeps the state's own script), pressing A every PI frames (env, 60);
  writes OUT.log (frame, opcode, arguments of every command run), OUT.dst
  (the state at the end), and both-screen shots 1, 20, 60 and 120 frames
  after each watched opcode. SHOTS=f1,f2 adds shots at given frames;
  PRESS=0 stops the A presses; SCN=n sets the scenario byte. DS_ROM points
  at the .nds file.

To unlock every episode at the title screen, set gMain+0x6a (and the save
buffer's copy at 0x022735f4) to 0x50: the high nibble is how many episodes
the episode select shows."""
import os, sys, struct
os.environ['SDL_VIDEODRIVER'] = 'dummy'; os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ds_script import DS_ARGS
from desmume.emulator import DeSmuME
from desmume.controls import keymask, Keys
ROM = os.environ.get('DS_ROM', 'Phoenix Wright - Ace Attorney (USA).nds')
B = 0x0211e1c0; BASE = 0x020cf4b4; SCN_BYTE = 0x020ceb71
state, mes, sec, out, nframes = sys.argv[1], sys.argv[2], int(sys.argv[3], 16), sys.argv[4], int(sys.argv[5])
watch = set(int(x, 16) for x in sys.argv[6:])
extra = set(int(x) for x in os.environ.get('SHOTS', '').split(',') if x)
emu = DeSmuME(); emu.open(ROM); emu.volume_set(0)
emu.savestate.load_file(os.path.abspath(state))
m = emu.memory
def r32(a): return m.unsigned[a:a + 4:4][0]
def w32(a, v): m.unsigned[a:a + 4:4] = [v]
def w16(a, v): m.unsigned[a:a + 2:2] = [v]
b = open(mes, 'rb').read(); n = struct.unpack_from('<I', b, 0)[0]; offs = struct.unpack_from('<%dI' % n, b, 4)
if sec >= 0:
    m.unsigned[B:B + len(b):1] = b
    p = B + offs[sec]
    w16(BASE + 8, 0); w16(BASE + 0xa, 0); w32(BASE + 0xc, p); w32(BASE + 0x10, p); w16(BASE + 0x4a, sec + 0x80); w16(BASE + 0x4c, sec + 0x81)
    if os.environ.get('SCN'): m.unsigned[SCN_BYTE] = int(os.environ['SCN'])
A = keymask(Keys.KEY_A); PI = int(os.environ.get('PI', '60')); press = os.environ.get('PRESS', '1') != '0'
last = None; pend = []; log = open(out + '.log', 'w')
for f in range(1, nframes + 1):
    if press and (f - 1) % PI == 0: emu.input.keypad_add_key(A)
    if press and (f - 1) % PI == 3: emu.input.keypad_rm_key(A)
    emu.cycle(with_joystick=False)
    sp = r32(BASE + 0xc)
    if sp != last and B <= sp < B + len(b):
        tok = b[sp - B] | b[sp - B + 1] << 8
        if tok < 0x80:
            na = DS_ARGS.get(tok, 0); args = [b[sp - B + 2 + 2 * k] | b[sp - B + 3 + 2 * k] << 8 for k in range(na)]
            log.write('%d %x %s\n' % (f, tok, ' '.join('%x' % a for a in args)))
            if tok in watch:
                pend += [(f + dt, '%s_f%05d_%02x_%s' % (out, f, tok, tag)) for dt, tag in ((1, 'a'), (20, 'b'), (60, 'c'), (120, 'd'))]
        last = sp
    for pf, name in [x for x in pend if x[0] == f]:
        emu.screenshot().save(name + '.png'); pend = [x for x in pend if x[0] != f]
    if f in extra: emu.screenshot().save('%s_s%05d.png' % (out, f))
emu.savestate.save_file(os.path.abspath(out + '.dst'))
log.close()
