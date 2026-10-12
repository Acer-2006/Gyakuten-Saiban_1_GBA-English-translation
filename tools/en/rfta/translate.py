#!/usr/bin/env python3
"""The fifth episode's scripts for the GBA, from the DS scripts alone.

Episodes 1-4 were ported by laying the DS script over the GBA's and taking
the GBA's own commands wherever the two match (port_script.py). Rise from
the Ashes has no GBA script, so every command is translated here:

  * text, line breaks, pages, colours and the commands both games share
    pass through as they are (the DS kept the GBA's script format);
  * the DS's own commands become what the GBA has for them (waits, the
    plate hide, the gavel, the centring command, the game-over check, a
    chapter continuation) or, for what the GBA does not have yet (the
    partner portrait, the movies, the bottom-screen panels, the second
    fade system), nothing, counted in the report;
  * the six new people are stood in for by people the GBA has (PLACEHOLDER)
    until their sprites are converted; the DS poses of the others are
    mapped the way episodes 1-4 map them (anim_looks.json);
  * the seven new songs play stand-ins (PLACEHOLDER_BGM) until they are
    converted; the DS's new sound effects are left out until then.

Section numbers are the DS's, so choices, jumps and testimony records keep
their targets; the jump descriptors in the section table are rewritten to
the translated positions.

usage: translate.py [OUT_DIR]      (default script_rfta/; writes
       scenario_5_00..5_18_script.phscr and translate_report.txt)"""
import os, sys, struct, collections, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import ds_script
from ds_script import DS_ARGS, FIRST_RFTA_FILE, LAST_RFTA_FILE
from phscr import GBA_ARGS, load, section_bounds, tokens, parse
import port_script
from port_script import ds_text_speed, SE_MAP, GAVEL_GBA, DS_GAVELS, DS_PLATE_HIDE, load_looks, ds_look
from arm9_tables import room

ROOT = os.path.join(HERE, '..', '..', '..')
GAMEOVER_CHECK = 0x5F       # the GBA's command for the DS's 7A
CONTINUE_CHAPTER = 0x60     # new GBA command: go on in chapter file n (the DS's 6A)
MAX_MARKER = 0x0C           # map marker sprites the GBA has (sMapMarkerSprites)
# people the GBA has, standing in for the fifth episode's until their sprites exist
# (Gumshoe is in the fifth episode himself, in the same rooms as Marshall, so
# Marshall's stand-in is Will Powers). The talk and present tables name the
# stand-ins too (stand_in), as the game finds a room's topics by the person
# on screen.
PLACEHOLDER = {0x2C: 0x04, 0x2D: 0x07, 0x2E: 0x1B, 0x2F: 0x19, 0x31: 0x21, 0x32: 0x16}
PLACEHOLDER_NAMES = {0x2C: 'Ema -> Maya', 0x2D: 'Lana -> Mia', 0x2E: 'Marshall -> Will Powers',
                     0x2F: 'Meekins -> Larry', 0x31: 'Gant -> von Karma', 0x32: 'Angel Starr -> April May'}
def stand_in(person):
    return PLACEHOLDER.get(person, person)
# the DS's seven new songs (SDAT sequence numbers) -> GBA songs standing in
PLACEHOLDER_BGM = {0x17C: 12, 0x17D: 25, 0x17E: 18, 0x17F: 22, 0x180: 2, 0x181: 4, 0x182: 15}
GBA_SONGS = 42 + 70         # BGM000-041 and SE000-045 (plus SE04F/SE050 at 111/112): the GBA song table
def gba_anim(v):
    """the GBA's number for a DS animation (command 2F), None where the GBA has
    none yet. Measured on episodes 1-4: the speech bubbles keep their numbers,
    the DS's 0x90-0x94 are the GBA's 0x1F-0x23 and 0x97-0xB0 its 0x24-0x3D
    (the wide shots of the courtroom); 0x95, 0x96 and 0xB1 on are the DS's own
    (the fifth episode's people seen from the gallery), as are the fifth
    episode's opening pictures"""
    if v in (1, 2, 3, 4, 0xA, 0xB):
        return v
    if 0x90 <= v <= 0x94:
        return v - 0x71
    if 0x97 <= v <= 0xB0:
        return v - 0x73
    return None
DROP = {0x4D, 0x55, 0x65, 0x68, 0x6B, 0x6F, 0x74, 0x75, 0x76, 0x78, 0x7B, 0x5F}

def usual_poses():
    """each GBA person's most used (talk, idle) pair in the episode 1-4 ports"""
    import glob
    cnt = collections.defaultdict(collections.Counter)
    for f in glob.glob(os.path.join(ROOT, 'script_en', 'scenario_[0-3]*_script.phscr')):
        b, n, offs = load(f)
        for bd in section_bounds(b, offs):
            if not bd:
                continue
            for p, k, op, a in parse(tokens(b, *bd), GBA_ARGS)[0]:
                if k == 'cmd' and op == 0x1E and a and a[0]:
                    cnt[a[0] & 0xFF][(a[1], a[2])] += 1
    return {p: c.most_common(1)[0][0] for p, c in cnt.items()}

class Translator:
    def __init__(self):
        load_looks()
        self.usual = usual_poses()
        votes = collections.defaultdict(collections.Counter)
        mp = os.path.join(HERE, '..', 'anim_map.json')
        for k, gv in json.load(open(mp)).items():
            tag, person, dv = k.split(':')
            votes[(int(person, 16) & 0xFF, int(dv, 16))][gv] += 1
        self.anim_any = {k: c.most_common(1)[0][0] for k, c in votes.items()}
        self.stats = collections.Counter()
        self.notes = []

    # -------------------------------------------------------------- people
    def person(self, args, where):
        who, talk, idle = args[0], args[1], args[2]
        p = who & 0xFF
        if p == 0:
            return [0x1E] + list(args)
        if p in PLACEHOLDER:
            g = PLACEHOLDER[p]
            t, i = self.usual.get(g, (0, 0))
            self.stats['placeholder person'] += 1
            return [0x1E, (who & 0xFF00) | g, t, i]
        out = [0x1E, who]
        for v in (talk, idle):
            m = ds_look(p, v)
            gv = m[0] if m else self.anim_any.get((p, v))
            if gv is None:
                gv = self.usual.get(p, (0, 0))[0]
                self.stats['pose unknown, usual pose'] += 1
                self.notes.append('%s: person %x DS pose %x unknown' % (where, p, v))
            out.append(gv)
        return out

    # -------------------------------------------------------------- one section
    def section(self, items, where):
        out = []
        pos_map = {}          # DS token position -> output token position
        for p, kind, op, a in items:
            pos_map[p] = len(out)
            if kind == 'text':
                out.append(op); continue
            if kind == 'bad':
                self.stats['bad token'] += 1; continue
            if op == 0x0B:
                out += [0x0B, ds_text_speed(a[0])]
            elif op == 0x06:
                snd, flag = a[0], a[1] & 1
                snd = SE_MAP.get(snd, snd)
                if snd >= GBA_SONGS and snd not in SE_MAP.values():
                    self.stats['new sound effect left out'] += 1
                else:
                    out += [0x06, (snd << 8) | flag]
            elif op == 0x05:
                song = a[0]
                if song in PLACEHOLDER_BGM:
                    song = PLACEHOLDER_BGM[song]; self.stats['placeholder song'] += 1
                elif song >= GBA_SONGS and song != 0xFF:     # 0xFF: the song that was playing
                    self.stats['unknown song left out'] += 1; continue
                out += [0x05, song, a[1]]
            elif op == 0x1E:
                out += self.person(a, where)
            elif op == 0x1A:
                # a pan across the courtroom with a person on it: the person and
                # the pose as for 1E
                if a[2]:
                    p = self.person([a[2], a[3], a[3]], where)
                    out += [0x1A, a[0], a[1], p[1], p[2]]
                else:
                    out += [0x1A] + list(a)
            elif op == 0x1B:
                bg = a[0]
                if bg == 0xFFF:
                    out += [0x1B, 0xFF]
                else:
                    out += [0x1B, bg]
            elif op == 0x4E:
                out += [0x0C, 0x8000 | (a[0] & 0x7FFF)]
            elif op == 0x12 and not 1 <= (a[0] >> 8) <= 4:
                # the DS's blend mode 5 (three flashes in the opening): the GBA
                # has modes 1-4, and its script waits for a blend to end
                self.stats['blend mode %d left out' % (a[0] >> 8)] += 1
            elif op == 0x2F:
                g = gba_anim(a[0])
                if g is None:
                    self.stats['animation %x left out' % a[0]] += 1
                else:
                    out += [0x2F, g, a[1]]
            elif op == 0x34:
                out += [0x34, room(a[0])]
            elif op == 0x33:
                # a room's four Move destinations (rooms renumbered, arm9_tables.ROOMS)
                out += [0x33, room(a[0])] + [room(v) if v != 0xFF else 0xFF for v in a[1:5]]
            elif op == 0x7A:
                out += [GAMEOVER_CHECK, a[0]]
            elif op == 0x6A:
                out += [CONTINUE_CHAPTER, a[0]]
                self.stats['chapter continuation'] += 1
            elif op == 0x79:
                out += [0x15]
            elif op == 0x77:
                snd = a[0]
                if snd < GBA_SONGS:
                    out += [0x06, (snd << 8) | 1]
                else:
                    self.stats['new sound effect left out'] += 1
            elif op == 0x5C:
                # the DS's second fade, waited for: a hardware blend of the same
                # kind (1 from black, 2 to black), then the frames it takes
                mode, step, level = a
                out += [0x12, (mode << 8) | 0x04, max(step, 1), 0x1F, 0x0C, 16 * max(step, 1)]
                self.stats['5C fade as blend'] += 1
            elif op == 0x69:
                if tuple(a) == DS_PLATE_HIDE:
                    out += [0x14]
                elif len(a) == 2 and a[0] == 0x62 and a[1] in DS_GAVELS:
                    out += GAVEL_GBA[DS_GAVELS[a[1]]]
                    self.stats['gavel'] += 1
                else:
                    self.stats['69 %x %x left out' % tuple(a[:2])] += 1
            elif op in (0x39, 0x3A, 0x3B, 0x4B):
                mid = a[0] >> 8
                if mid > MAX_MARKER:
                    self.stats['map marker %x left out' % mid] += 1
                else:
                    if op == 0x3A:      # the DS has a third argument
                        out += [0x3A, a[0], a[1]]
                    elif op == 0x4B:
                        out += [0x4B, a[0]]
                    else:
                        out += [op] + list(a)
            elif op in DROP:
                self.stats['%02X left out' % op] += 1
            elif op in GBA_ARGS:
                n = GBA_ARGS[op]
                if len(a) != n:
                    self.notes.append('%s: %02X has %d DS arguments, GBA %d' % (where, op, len(a), n))
                out += [op] + list(a[:n])
            else:
                self.stats['unknown %02X left out' % op] += 1
        pos_map[len(items) and items[-1][0] + 1 + len(items[-1][3])] = len(out)
        return out, pos_map

    # -------------------------------------------------------------- one file
    def file(self, k):
        b, n, offs = load(ds_script.chapter(k))
        bounds = section_bounds(b, offs)
        secs, maps = {}, {}
        for si, bd in enumerate(bounds):
            if not bd:
                continue
            items, _ = parse(tokens(b, *bd), DS_ARGS)
            secs[si], maps[si] = self.section(items, 'file %d sec %d' % (k, si))
        # lay out: header, then sections on 4-byte boundaries
        body = bytearray(); new_offs = [0] * n
        head = 4 + 4 * n
        for si in range(n):
            if si in secs:
                while (head + len(body)) % 4:
                    body.append(0)
                new_offs[si] = head + len(body)
                body += struct.pack('<%dH' % len(secs[si]), *secs[si])
        for si in range(n):
            if si not in secs:
                desc = offs[si]
                sec, off = desc >> 16, (desc & 0xFFFF) // 2
                if sec in maps and off in maps[sec]:
                    new_offs[si] = (sec << 16) | (2 * maps[sec][off])
                elif sec in maps:
                    near = max([o for o in maps[sec] if o <= off] or [0])
                    new_offs[si] = (sec << 16) | (2 * maps[sec].get(near, 0))
                    self.notes.append('file %d: descriptor %d (%x:%x) moved to the command before' % (k, si, sec, off))
                else:
                    new_offs[si] = desc
                    self.notes.append('file %d: descriptor %d (%x) kept as is' % (k, si, desc))
        return bytes(struct.pack('<I', n) + struct.pack('<%dI' % n, *new_offs) + body)

def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'script_rfta')
    t = Translator()
    rep = []
    for k in range(FIRST_RFTA_FILE, LAST_RFTA_FILE + 1):
        before = collections.Counter(t.stats)
        data = t.file(k)
        f = os.path.join(out_dir, 'scenario_5_%02d_script.phscr' % (k - FIRST_RFTA_FILE))
        open(f, 'wb').write(data)
        delta = {key: v - before[key] for key, v in t.stats.items() if v - before[key]}
        rep.append('file %d (%s) -> %s: %d bytes %s' % (k, ds_script.TITLES.get(k, ''), os.path.basename(f), len(data), dict(sorted(delta.items()))))
        print(rep[-1])
    with open(os.path.join(out_dir, 'translate_report.txt'), 'w') as o:
        o.write('\n'.join(rep) + '\n\ntotals: %s\n\n' % dict(sorted(t.stats.items())))
        o.write('stand-ins: %s\nsongs: %s\n\n' % (PLACEHOLDER_NAMES, PLACEHOLDER_BGM))
        o.write('\n'.join(t.notes[:400]) + '\n')
    print('totals', dict(sorted(t.stats.items())))

if __name__ == '__main__':
    main()
