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
    movies, the bottom-screen panels, the second fade system), nothing,
    counted in the report; the partner portrait (76) is the evidence plate
    with the portrait's picture (commands 62 and 63); the DS's 5F, its
    monochrome filter for flashbacks, is command 64;
  * the six new people are the DS's, converted (characters.py: their
    animation numbers become offsets in their GBA files, as Edgeworth's two
    new looks do); the DS poses of the others are mapped the way episodes 1-4
    map them (anim_looks.json);
  * the seven new songs are the GBA songs 113-119 (NEW_SONGS; converted by
    music.py), its 25 new sound effects songs 120-144 (NEW_SES, sfx.py).

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
from sfx import NEW_SES
from port_script import ds_text_speed, SE_MAP, GAVEL_GBA, DS_GAVELS, DS_PLATE_HIDE, load_looks, ds_look
from arm9_tables import room

ROOT = os.path.join(HERE, '..', '..', '..')
GAMEOVER_CHECK = 0x5F       # the GBA's command for the DS's 7A
CONTINUE_CHAPTER = 0x60     # new GBA command: go on in chapter file n (the DS's 6A)
GOTO_SECTION = 0x61         # new GBA command: go on in section n
PORTRAIT_SHOW = 0x62        # new GBA command: the partner's portrait on the plate (the DS's 76 0/1 n)
PORTRAIT_HIDE = 0x63        # new GBA command: the portrait away (the DS's 76 2 0)
GREY = 0x64                 # new GBA command: the monochrome filter (the DS's 5F mode step level)
GREY_MODES = (3, 4, 7)      # (its mode 0x15 shows nothing on the DS's screen: left out)
MOVIE = 0x65                # new GBA command: the movies (the DS's 75 sub x y z: 65 sub value flags; src/en_movie.c)
# the DS's 69 405 starts the opening's frames (its effect 0x02068b7c, case 5): sequence 1,
# kept on screen at the end (0x4000)
MOVIE_OPENING = (0x405, 0x100)
TAPE = 0x66                 # new GBA command: the security tape shown to point out a moment (src/en_movie.c)
# Day 3 trial: where the DS hands over to its tape viewer (74 8 35, 79), the
# question it asks (its 0x020ced54; tools/en/rfta/movies.py: the spots): the
# locker light, the cloth falling out; Marshall in the video, what Meekins did
TAPE_QUESTIONS = {(25, 0x9C): 0, (25, 0xA3): 1, (26, 0x9D): 2, (26, 0xA7): 3}
TAPE_HINT = 'Hold L/R: rewind/fast-forward\nSTART: pause  A: point it out'


def gba_text(s):
    """text tokens (the DS's and the GBA's: ds_script.letter)"""
    import ds_script
    inv = {'/': 0x171}      # ("2/21 SL-9")
    for code, ch in sorted(ds_script.SPECIAL.items(), reverse=True):
        inv[ch] = code
    out = []
    for ch in s:
        if ch == '\n':
            out.append(0x01)
        elif '0' <= ch <= '9':
            out.append(0x80 + ord(ch) - 48)
        elif 'A' <= ch <= 'Z':
            out.append(0x8A + ord(ch) - 65)
        elif 'a' <= ch <= 'z':
            out.append(0xA4 + ord(ch) - 97)
        else:
            out.append(inv[ch])
    return out
# Where the DS hands over to a system of its own that the GBA does not have
# yet (the evidence turned over in 3D, the luminol, the fingerprints, the
# security footage) and that system then starts the section that follows, the
# GBA goes on in that section straight away: (DS file, section) -> the
# sections to go on in, in order. Each is entered where the source section
# would have handed over (its last "1C 3 / 15": back to the menu), the
# DS's tutorial sections for the system itself are left out.
BYPASS = {
    # Day 1: the wallet turned over (C0, C1: how to turn evidence over) -> the ID card inside, then it replaces the wallet
    (18, 0xBF): 0xC2, (18, 0xC2): 0xC3,
    # Day 1: Ms. Skye's phone looked over: the redial display, the call, the patrolman
    (18, 0xF9): 0xFB, (18, 0xFB): 0xFC, (18, 0xFC): 0xFD,
    # Day 2: the luminol in the parking lot (its luminol screen: src/en_luminol.c): the
    # tutorial after Ema's lines, the stain's question after its lines
    (22, 0x92): 0x93, (22, 0x95): 0x96,
    # Day 2 trial: the knife opened in 3D (its switch) -> the knife added to the record
    (21, 0x81): 0x82,
    # Day 2: the jar pieces put together (135 is the DS's try-again)
    (24, 0x134): 0x136,
    # Day 3: the locker's number (11D: the wrong one), the last piece of the jar
    # (132: it does not fit)
    (30, 0x11C): 0x11E, (30, 0x131): 0x133,
    # Final day: the jar turned to the Badger's angle (BC: not yet), the dots
    # joined into the name (C6: wrong, C8: the game over)
    (31, 0xBB): 0xBD, (31, 0xC5): 0xC7,
    # Final day: the picture found on the back of the list
    (33, 0xAC): 0xAD,
    # The end: after the staff roll, "The End" (86 the first time, 87 the replay)
    (34, 0x85): 0x86, (34, 0x88): 0x87,
}
# The DS's "74 A n": the Court Record opened for a person's profile (the
# question's answer in its table at 0x020b1324, arm9_tables.PROMPTS): the
# GBA's 21, its answers in the court present data (arm9_tables.py)
PROMPT_PRESENT = 0x21
# The luminol (src/en_luminol.c, tools/en/rfta/luminol.py): a stain it finds
# runs its lines from the shared file 35 (C2-C8), which every chapter it can
# be used in carries as sections of its own after its last (the luminol's
# table, LUMINOL_SECTIONS_H, gives the first); the flag is the luminol's to
# set, when the stain is found. Its tutorial (chapter 22) hands over to the
# player (the DS's 74 5 0 there), and leaves after the stain's question.
LUMINOL = 0x67              # new GBA command: the luminol (0 start, 1 Ema's spray, 2 the player's turn, 3 back to the red room, 4 leave)
LUMINOL_CHAPTERS = (22, 23, 24, 28, 29, 30)
LUMINOL_SHARED = range(0xC2, 0xCB)      # (C9, CA: the fingerprints', below)
LUMINOL_SECTIONS_H = os.path.join(ROOT, 'src', 'data', 'en_rfta_luminol_sections.h')
# the DS's 74 in the luminol's sections: (file, section or None for the shared
# ones, sub, value) -> GBA tokens (the DS's 74 6 0 / 74 6 1 everywhere)
LUMINOL_74 = {(22, 0x93, 5, 0): [LUMINOL, 2], (22, 0x95, 5, 0): [], (22, 0x97, 5, 0): [LUMINOL, 4],
              (22, 0x98, 5, 0): [LUMINOL, 4], (35, None, 5, 0): [LUMINOL, 3]}
# the evidence room's findings, all of them (the DS's 74 8 3f in C5-C7): the
# luminol leaves and the day goes on (the jump through descriptor D2, as the
# room's other findings take it: file 24's 11D, 127-129, 131, 136 -> 10E)
LUMINOL_ALL_FOUND = {24: [LUMINOL, 4, 0x36, 0xD2]}
# The fingerprints (src/en_fingerprint.c, tools/en/rfta/fingerprint.py): the
# DS hands over with 74 9 n (n the case), and in the fingerprints' sections
# (they run from its screens) 74 5 0 gives the player the screen back and
# 74 8 37-3D are the screens' own steps: the GBA's 68 (sub << 8 | n). File
# 35's C9 and CA (back from the dusting, a print that cannot be compared)
# come in with the luminol's stain lines, in the chapters that have both.
FINGERPRINT = 0x68
FP_SECTIONS = {24: range(0x13A, 0x146), 30: (0x129, 0x12A), 35: (0xC9, 0xCA)}
FP_74_8 = {0x37: 2 << 8, 0x38: 3 << 8, 0x39: 4 << 8, 0x3A: 5 << 8, 0x3B: (5 << 8) | 1,
           0x3C: (6 << 8) | 0xBA, 0x3D: 7 << 8}
# the touch screen and the microphone in the lines, for the GBA's buttons
TEXT_FOR_BUTTONS = {
    (22, 0x93): [('Touch the screen to spray\nit on.', 'Press the A Button to\nspray it on.')],
    (24, 0x13C): [('touch the screen...', 'press the A Button...'),
                  ('You just blow.', 'Just hold the R Button.'),
                  ('With your breath.', 'Like blowing with your breath.')]}
MAX_MARKER = 0x0C           # map marker sprites the GBA has (sMapMarkerSprites)
# The fifth episode's people (and Edgeworth's two new looks), converted from
# the DS by characters.py: DS person -> DS animation number -> offset in the
# person's GBA frame file. They keep their DS person numbers (0x2C-0x32).
CHARACTERS = {int(p, 16): {int(n, 16): o for n, o in m.items()}
              for p, m in json.load(open(os.path.join(HERE, 'characters.json'))).items()}
def character_pose(person, v):
    return CHARACTERS.get(person & 0xFF, {}).get(v)
# the fifth episode's own animations (command 2F), converted by effects.py:
# DS number -> GBA number (the wide shot's people, Angel Starr's box lunches)
EFFECTS = {int(a, 16): g for a, g in json.load(open(os.path.join(HERE, 'effects.json'))).items()}
LUNCHES = range(0x27, 0x3C)             # characters.LUNCHES
LUNCH_POSES = {0x32: (0x1CA, 0x1CB)}     # characters.LUNCH_POSES: the poses a lunch is held out in
LUNCH_VARIANT = 0x10000                 # characters.LUNCH_VARIANT: their versions that leave the lunch room
# people standing in for others whose sprites are missing (none left: stage 3
# converted them); the talk and present tables would name the stand-ins too
PLACEHOLDER = {}
PLACEHOLDER_NAMES = {}
def stand_in(person):
    return PLACEHOLDER.get(person, person)
# the DS's seven new songs (SDAT sequence numbers, BGM150-156) -> their GBA songs (music.py)
NEW_SONGS = {0x17C + i: 113 + i for i in range(7)}
GBA_SONGS = 42 + 70         # BGM000-041 and SE000-045 (plus SE04F/SE050 at 111/112): the GBA song table
def gba_anim(v):
    """the GBA's number for a DS animation (command 2F), None where the GBA has
    none yet. Measured on episodes 1-4: the speech bubbles keep their numbers,
    the DS's 0x90-0x94 are the GBA's 0x1F-0x23 and 0x97-0xB0 its 0x24-0x3D
    (the wide shots of the courtroom). The DS's own: 0xB1-0xB7, the fifth
    episode's people in the wide shot, and 0x27-0x3B, Angel Starr's box
    lunches, are converted (effects.py); 0x95 and 0x96 (the gavel, which the
    gavel commands draw the GBA's way), the fifth episode's opening pictures
    and a few one-off pictures are not"""
    if v in (1, 2, 3, 4, 0xA, 0xB):
        return v
    if 0x90 <= v <= 0x94:
        return v - 0x71
    if 0x97 <= v <= 0xB0:
        return v - 0x73
    return EFFECTS.get(v)
DROP = {0x4D, 0x55, 0x65, 0x68, 0x6B, 0x6F, 0x74, 0x7B}

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
    def person(self, args, where, lunch=False):
        """lunch: a box lunch follows (its poses' versions that leave it room)"""
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
            gv = None
            if lunch and v in LUNCH_POSES.get(p, ()):
                gv = character_pose(p, LUNCH_VARIANT | v)
                assert gv is not None, 'no lunch version of %x' % v
            if gv is None:
                gv = character_pose(p, v)
            if gv is not None:
                out.append(gv); self.stats['person converted from the DS'] += 1
                continue
            m = ds_look(p, v)
            gv = m[0] if m else self.anim_any.get((p, v))
            if gv is None:
                gv = self.usual.get(p, (0, 0))[0]
                self.stats['pose unknown, usual pose'] += 1
                self.notes.append('%s: person %x DS pose %x unknown' % (where, p, v))
            out.append(gv)
        return out

    # -------------------------------------------------------------- one section
    luminol_base = {}

    def luminol_74(self, a):
        k, sec, src = self.cur
        if src is not None:
            return LUMINOL_74.get((src[0], None, a[0], a[1]))
        return LUMINOL_74.get((k, sec, a[0], a[1]))

    def fingerprint_section(self):
        k, sec, src = self.cur
        f, s = src if src is not None else (k, sec)
        return s in FP_SECTIONS.get(f, ())

    def section(self, items, where):
        out = []
        pos_map = {}          # DS token position -> output token position
        jumps = []            # (output index of a 35's offset, DS token it jumps to)
        cmds = [k for k, it in enumerate(items) if it[1] == 'cmd']
        lunch_after = set()       # the 1Es a box lunch follows
        for k, j in zip(cmds, cmds[1:]):
            if items[k][2] == 0x1E and items[j][2] == 0x2F and items[j][3][0] in LUNCHES and items[j][3][1]:
                lunch_after.add(k)
        for k, (p, kind, op, a) in enumerate(items):
            pos_map[p] = len(out)
            if kind == 'text':
                out.append(op); continue
            if kind == 'bad':
                self.stats['bad token'] += 1; continue
            if op == 0x0B:
                out += [0x0B, ds_text_speed(a[0])]
            elif op == 0x06:
                snd, flag = a[0], a[1] & 1
                if snd in NEW_SES:
                    out += [0x06, (NEW_SES[snd] << 8) | flag]; self.stats['new sound effect'] += 1
                    continue
                snd = SE_MAP.get(snd, snd)
                if snd >= GBA_SONGS and snd not in SE_MAP.values():
                    self.stats['new sound effect left out'] += 1
                else:
                    out += [0x06, (snd << 8) | flag]
            elif op == 0x05:
                song = a[0]
                if song in NEW_SONGS:
                    song = NEW_SONGS[song]; self.stats['new song'] += 1
                elif song >= GBA_SONGS and song != 0xFF:     # 0xFF: the song that was playing
                    self.stats['unknown song left out'] += 1; continue
                out += [0x05, song, a[1]]
            elif op == 0x1E:
                out += self.person(a, where, k in lunch_after)
                if k in lunch_after:
                    self.stats['box lunch'] += 1
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
            elif op == 0x35 and not a[0] & 0x80:
                # a flag test that jumps within the section: its offset is
                # the DS's, the section's commands have moved
                out += [0x35, a[0], 0]
                jumps.append((len(out) - 1, a[1] // 2))
                self.stats['jump within a section'] += 1
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
            elif op == 0x5F:
                # the DS's monochrome filter (flashbacks in grey): en_rfta.c, Command64
                if a[0] in GREY_MODES:
                    out += [GREY, (a[0] << 8) | a[1], a[2]]; self.stats['5F as the grey filter'] += 1
                else:
                    self.stats['5F %x left out' % a[0]] += 1
            elif op == 0x76:
                # the partner portrait: side (0 left, 1 right) and picture, or 2: away
                if a[0] in (0, 1):
                    out += [PORTRAIT_SHOW, (a[0] << 8) | a[1]]
                else:
                    out += [PORTRAIT_HIDE]
                self.stats['portrait'] += 1
            elif op == 0x74 and a[0] == 0xA:
                out += [PROMPT_PRESENT]
                self.stats['74 A as a present prompt'] += 1
            elif op == 0x74 and a[0] == 6 and a[1] in (0, 1):
                out += [LUMINOL, a[1]]
                self.stats['luminol'] += 1
            elif op == 0x74 and a[0] == 9:
                out += [FINGERPRINT, a[1]]
                self.stats['fingerprints'] += 1
            elif op == 0x74 and a[0] == 5 and a[1] == 0 and self.fingerprint_section():
                out += [FINGERPRINT, 1 << 8]
                self.stats['fingerprints'] += 1
            elif op == 0x74 and a[0] == 8 and a[1] in FP_74_8:
                out += [FINGERPRINT, FP_74_8[a[1]]]
                self.stats['fingerprints'] += 1
            elif op == 0x74 and a[0] == 5 and self.luminol_74(a) is not None:
                out += self.luminol_74(a)
                self.stats['luminol'] += 1
            elif op == 0x74 and a[0] == 8 and a[1] == 0x3F and self.cur[2] is not None:
                out += LUMINOL_ALL_FOUND.get(self.cur[0], [LUMINOL, 4])
                self.stats['luminol: all found'] += 1
            elif op == 0x78:
                # the DS's jump through a section-table record (its 0x02029474:
                # the GBA's 36, with the DS's note of sections already read)
                out += [0x36, a[0]]
                self.stats['78 as jump'] += 1
            elif op == 0x77:
                snd = NEW_SES.get(a[0], a[0])
                if snd < GBA_SONGS or a[0] in NEW_SES:
                    out += [0x06, (snd << 8) | 1]
                else:
                    self.stats['new sound effect left out'] += 1
            elif op == 0x5C:
                # the DS's second fade, waited for: a hardware blend of the same
                # kind (1 from black, 2 to black), then the frames it takes
                mode, step, level = a
                out += [0x12, (mode << 8) | 0x04, max(step, 1), 0x1F, 0x0C, 16 * max(step, 1)]
                self.stats['5C fade as blend'] += 1
            elif op == 0x75:
                # 0 set up (y: the sequence, z: the flags), 1 state and flags, 2 to a frame,
                # 3 speed, 4 start, 5 end, 6 wait for the end
                if a[0] == 0:
                    out += [MOVIE, 0, a[2], a[3]]
                else:
                    out += [MOVIE, a[0], a[1], 0]
                self.stats['movie command'] += 1
            elif op == 0x69 and tuple(a[:2]) == MOVIE_OPENING:
                out += [MOVIE, 0, 1, 0x4001]
                self.stats['movie command'] += 1
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
        for idx, target in jumps:
            to = pos_map.get(target)
            if to is None:      # (a command left out: the next one kept)
                to = pos_map[min(q for q in pos_map if q >= target)]
                self.notes.append('%s: a jump to a command left out goes to the next' % where)
            out[idx] = 2 * to
        return out, pos_map

    # -------------------------------------------------------------- one file
    @staticmethod
    def end_15(out):
        """where a translated section waits at its end: the first 15 after its
        last text (the DS's systems take over there; a 1C 3 / 15 after it is
        their way back to the menu)"""
        args = dict(GBA_ARGS); args.update({CONTINUE_CHAPTER: 1, GOTO_SECTION: 1, PORTRAIT_SHOW: 1, PORTRAIT_HIDE: 0})
        cmds, _ = parse(out, args)
        last_text = max([p for p, kind, op, a in cmds if kind == 'text'] + [0])
        return [p for p, kind, op, a in cmds if kind == 'cmd' and op == 0x15 and p > last_text][0]

    def file(self, k):
        b, n, offs = load(ds_script.chapter(k))
        bounds = section_bounds(b, offs)
        secs, maps = {}, {}
        for si, bd in enumerate(bounds):
            if not bd:
                continue
            items, _ = parse(tokens(b, *bd), DS_ARGS)
            self.cur = (k, 0x80 + si, None)
            secs[si], maps[si] = self.section(items, 'file %d sec %d' % (k, si))
        # the luminol's stains' lines (file 35's C2-C8), after the file's own
        if k in LUMINOL_CHAPTERS:
            self.luminol_base[k] = 0x80 + n
            sb, sn, soffs = load(ds_script.chapter(35))
            for src_sec in LUMINOL_SHARED:
                items, _ = parse(tokens(sb, *section_bounds(sb, soffs)[src_sec - 0x80]), DS_ARGS)
                self.cur = (k, 0x80 + n, (35, src_sec))
                secs[n], _ = self.section(items, 'file %d sec %d (file 35 sec %d)' % (k, n, src_sec - 0x80))
                offs = list(offs) + [0]; n += 1
                self.stats['luminol: section brought in'] += 1
        for si in sorted(secs):
            for old, new in TEXT_FOR_BUTTONS.get((k, 0x80 + si), ()):
                old, new = gba_text(old), gba_text(new)
                out = secs[si]
                at = [i for i in range(len(out) - len(old) + 1) if out[i:i + len(old)] == old]
                assert len(at) == 1, (k, hex(0x80 + si), 'text to replace')
                assert len(new) == len(old) or not [1 for p, kind, op, a in parse(out, dict(GBA_ARGS))[0] if kind == 'cmd' and op == 0x35]
                secs[si] = out[:at[0]] + new + out[at[0] + len(old):]
                self.stats['text for the buttons'] += 1
            if (k, 0x80 + si) in TAPE_QUESTIONS:
                # the tape: the last line read (a page), then what the keys do while it
                # is shown (the DS's "Select area via Touch Screen"); the tape command
                # goes on in the section the answer leads to
                out = secs[si]
                end = self.end_15(out)
                start = end - 2 if out[end - 2:end] == [0x1C, 3] else end
                ins = [0x02, 0x0E, 0] + gba_text(TAPE_HINT) + [TAPE, TAPE_QUESTIONS[(k, 0x80 + si)]]
                args = dict(GBA_ARGS); args.update({GOTO_SECTION: 1, TAPE: 1})
                assert not [a for p, kind, op, a in parse(out, args)[0] if kind == 'cmd' and op == 0x35 and a[-1] >= 2 * start], \
                    'a jump past the tape'
                secs[si] = out[:start] + ins + out[start:]
                self.stats['tape'] += 1
            if (k, 0x80 + si) in BYPASS:
                # where the section ends (its last 15, with the 1C 3 that slides
                # the text box away for the menu, if it has one), the GBA goes on
                # in the section the DS's system would have started
                out = secs[si]
                end = self.end_15(out)
                start = end - 2 if out[end - 2:end] == [0x1C, 3] else end
                # (as long as what it replaces where it can: jumps within the section keep their places)
                secs[si] = out[:start] + [GOTO_SECTION, BYPASS[(k, 0x80 + si)]] + [0x15] * (end + 1 - start - 2) + out[end + 1:]
                self.stats['bypass to a section'] += 1
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
    # the first of each luminol chapter's sections with the stains' lines (src/en_luminol.c)
    h = ['// generated by tools/en/rfta/translate.py: each chapter\'s first section with the',
         '// luminol\'s stains\' lines (file 35\'s C2-C8, in order), 0 where it has none',
         'static const u16 sEnLuminolShared[%d] = { %s };' % (LAST_RFTA_FILE - FIRST_RFTA_FILE,
         ', '.join('0x%X' % t.luminol_base.get(k, 0) for k in range(FIRST_RFTA_FILE, LAST_RFTA_FILE)))]
    open(LUMINOL_SECTIONS_H, 'w').write('\n'.join(h) + '\n')
    with open(os.path.join(out_dir, 'translate_report.txt'), 'w') as o:
        o.write('\n'.join(rep) + '\n\ntotals: %s\n\n' % dict(sorted(t.stats.items())))
        o.write('stand-ins: %s\nsongs: %s\n\n' % (PLACEHOLDER_NAMES, NEW_SONGS))
        o.write('\n'.join(t.notes[:400]) + '\n')
    print('totals', dict(sorted(t.stats.items())))

if __name__ == '__main__':
    main()
