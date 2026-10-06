#!/usr/bin/env python3
"""
Port the English DS (Phoenix Wright: Ace Attorney) script into a GBA
Gyakuten Saiban script file, section by section.

For each GBA section we find the matching DS section, then walk the DS
token stream: English text and DS-compatible inline commands come from
the DS side; every command that has a GBA counterpart is emitted with
the GBA arguments (so backgrounds, animations, evidence, flags and flow
use GBA ids). GBA-only commands are kept in order. Jump offsets (cmd 35
and header jump descriptors) are remapped to the new token positions.

usage: port_script.py GBA.phscr DS.bin OUT.phscr [report.txt]
"""
import sys, collections, struct, json, difflib, os, glob
sys.path.insert(0, os.path.dirname(__file__))
from phscr import GBA_ARGS, load, section_bounds, tokens, parse

DS_ARGS = {int(k, 16): v for k, v in json.load(open(os.path.join(os.path.dirname(__file__), 'ds_args.json'))).items()}
DS_ONLY = {0x69, 0x6b, 0x74, 0x5d, 0x75, 0x4d, 0x4e, 0x65, 0x6f, 0x78, 0x7a}
# Commands whose DS arguments can be used directly on GBA when unmatched
DS_KEEP = {0x01, 0x02, 0x03, 0x07, 0x0B, 0x0C, 0x0D, 0x0E, 0x11, 0x14, 0x16, 0x1F,
           0x21, 0x24, 0x27, 0x2B, 0x2D, 0x2E, 0x30, 0x40, 0x41, 0x49, 0x4C}
TEXT_CMDS = {0x01, 0x02, 0x03, 0x07, 0x0B, 0x0C, 0x2D, 0x30}  # never matched from GBA: DS owns text flow
KEYED_OPS = {0x05, 0x0E, 0x1B, 0x1E}  # align on (op, first arg): music, speaker, background, person
DS_ARGS_WIN = {0x0E}
# Commands taken from the DS as they are, at the DS's places, with the GBA's own
# ones left out: the text box being shown / hidden (1C), screen shakes (27),
# sound effects (06) and white flashes (12 with blend mode 3). The text is the
# DS's, so these follow its flow; taking them from the GBA put text in a hidden
# text box and doubled shakes and sounds where the two scripts differ.
DS_AUTH = {0x06, 0x1C, 0x27}
def ds_auth(op, args):
    return op in DS_AUTH or (op == 0x12 and args and args[0] >> 8 == 3)
# sound effects the DS added (SE04F, SE050: sounds from the GBA sequels) are
# added to the GBA song table after its last entry (data/en_sound.s)
SE_MAP = {121: 111, 122: 112}
CENTRE = 0x5D      # DS: centre the following lines (1) / stop (0); en_text in vwf.c
DS_WAIT = 0x4E     # DS: hold for n frames -> GBA wait (0C)
ANIM_MAP = {}   # 'scenario_x:person:dsval' -> gba value (learn_anim_map.py)
CHAPTER_POSES, CHAPTER_USUAL = {}, {}
ANIM_TAG = ''  # matched for alignment, but the DS arguments are used (speaker nametag)
JUMP_IN_SECTION = 0x35
GBA_BG_COUNT = 0x70  # entries in gBackgroundTable


def sig(toks):
    return (any(t >= 0x80 for t in toks), tuple(toks[:3]))


# ---------------------------------------------------------------- section pairing
# Sections are paired by a global, order-preserving alignment (the DS inserted
# and split some sections). The similarity of two sections uses only things
# that don't depend on the language: the command sequence, and the speaker /
# music / background / sound / jump sequence.
SIG_OPS = (0x0E, 0x05, 0x1B, 0x06, 0x35, 0x36, 0x08, 0x09, 0x0A, 0x0F, 0x10, 0x19, 0x1A, 0x40, 0x41, 0x1E, 0x07)
def feats(b, x, ds):
    ops, sig = [], []
    for pos, kind, op, a in parse(tokens(b, *x), DS_ARGS if ds else GBA_ARGS)[0]:
        if kind != 'cmd': continue
        if ds and op in DS_ONLY: continue
        ops.append(op)
        if op in SIG_OPS:
            if op == 0x06 and ds: a = [((a[0] & 0xFF) << 8) | (a[1] & 0xFF)] if len(a) > 1 else a
            if op == 0x1E: a = a[:1]
            sig.append((op,) + tuple(a[:1]))
    return ops, sig
def score(fg, fd):
    r1 = difflib.SequenceMatcher(None, fg[0], fd[0], autojunk=False).ratio()
    if not fg[1] and not fd[1]: r2 = r1
    else: r2 = difflib.SequenceMatcher(None, fg[1], fd[1], autojunk=False).ratio()
    return 0.5 * r1 + 0.5 * r2
def align(gb, G, db, D, band=30, thresh=0.45):
    gi_list = [i for i, x in enumerate(G) if x]
    dj_list = [j for j, x in enumerate(D) if x]
    FG = {i: feats(gb, G[i], False) for i in gi_list}
    FD = {j: feats(db, D[j], True) for j in dj_list}
    n, m = len(gi_list), len(dj_list)
    NEG = -1e9
    dp = [[NEG] * (m + 1) for _ in range(n + 1)]
    bt = [[None] * (m + 1) for _ in range(n + 1)]
    for a in range(n + 1): dp[a][0] = 0
    for c in range(m + 1): dp[0][c] = 0
    cache = {}
    for a in range(1, n + 1):
        gi = gi_list[a - 1]
        for c in range(1, m + 1):
            dj = dj_list[c - 1]
            best, arg = dp[a - 1][c], 'up'
            if dp[a][c - 1] > best: best, arg = dp[a][c - 1], 'left'
            if abs(dj - gi) <= band:
                s = score(FG[gi], FD[dj]); cache[(gi, dj)] = s
                v = dp[a - 1][c - 1] + (s - thresh)
                if s >= thresh and v > best: best, arg = v, 'diag'
            dp[a][c] = best; bt[a][c] = arg
    pairs = {}
    a, c = n, m
    while a > 0 and c > 0:
        arg = bt[a][c]
        if arg == 'diag':
            pairs[gi_list[a - 1]] = (dj_list[c - 1], cache[(gi_list[a - 1], dj_list[c - 1])]); a -= 1; c -= 1
        elif arg == 'up': a -= 1
        else: c -= 1
    return pairs


def pair_sections(gb, G, db, D):
    """Return dict gba_section_index -> ds_section_index."""
    pairs = {gi: dj for gi, (dj, sc) in align(gb, G, db, D).items()}
    fill_gaps(gb, G, db, D, pairs)
    return pairs


def _ops_ratio(gb, g, db, d):
    gops = [x[2] for x in parse(tokens(gb, *g), GBA_ARGS)[0] if x[1] == 'cmd']
    dops = [x[2] for x in parse(tokens(db, *d), DS_ARGS)[0] if x[1] == 'cmd' and x[2] not in DS_ONLY]
    return difflib.SequenceMatcher(None, gops, dops, autojunk=False).ratio()


def fill_gaps(gb, G, db, D, pairs):
    """Sections the DS rewrote (longer TV show intro, merged lines...) don't
    align by signature. Pair a leftover GBA section with the unpaired DS
    section that sits between its neighbours' partners, or failing that with
    a very similar DS section close by (a DS section may serve two GBA ones)."""
    for gi in range(len(G)):
        if gi in pairs or not G[gi]:
            continue
        lo = max([pairs[k] for k in pairs if k < gi] or [-1])
        hi = min([pairs[k] for k in pairs if k > gi] or [len(D)])
        used = set(pairs.values())
        free = [dj for dj in range(lo + 1, hi) if D[dj] and dj not in used]
        best = max(((_ops_ratio(gb, G[gi], db, D[dj]), dj) for dj in free), default=(0, None))
        # a single leftover DS section between the neighbours' partners is the
        # counterpart even when the DS reworked it heavily
        if best[1] is not None and (best[0] >= 0.3 or (len(free) == 1 and best[0] >= 0.1)):
            pairs[gi] = best[1]
            continue
        near = [dj for dj in range(max(0, lo - 2), min(len(D), hi + 3)) if D[dj]]
        best = max(((_ops_ratio(gb, G[gi], db, D[dj]), dj) for dj in near), default=(0, None))
        if best[1] is not None and best[0] >= 0.75:
            pairs[gi] = best[1]


# What the Japanese GBA scripts do with each person's animations (script
# command 1E person, talking, idle): the text engine plays "talking" while a
# page is typed and "idle" once it waits, whoever is speaking, so the GBA
# gives a talking animation its own idle partner, and shows a person who is
# not speaking with an idle pose in both places. A DS pose mapped value by
# value can break that (a talking animation as the idle one: the mouth goes
# on moving after the line ends, or while someone else talks).
JP_PAIRS = None

def jp_pairs():
    global JP_PAIRS
    if JP_PAIRS is None:
        d = os.path.join(os.path.dirname(__file__), '..', '..', 'script')
        pairs = collections.defaultdict(collections.Counter)
        for f in sorted(os.listdir(d)):
            if f.startswith('scenario_') and f.endswith('.phscr'):
                b, n, offs = load(os.path.join(d, f))
                for x in section_bounds(b, offs):
                    if x:
                        for pos, kind, op, a in parse(tokens(b, *x), GBA_ARGS)[0]:
                            if kind == 'cmd' and op == 0x1E and a and a[0]:
                                pairs[a[0]][(a[1], a[2])] += 1
        partner, talker = {}, {}
        for person, c in pairs.items():
            pc, tc = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
            for (t, i), k in c.items():
                if t != i:
                    pc[t][i] += k
                    tc[i][t] += k
            partner[person] = {t: v.most_common(1)[0][0] for t, v in pc.items()}
            talker[person] = {i: v.most_common(1)[0][0] for i, v in tc.items()}
        JP_PAIRS = (pairs, partner, talker)
    return JP_PAIRS

def fix_pose_pair(person, t, i, ds_silent):
    """(talking, idle) as the GBA would have it. ds_silent: the DS gives the
    person the same pose twice (they are not the one speaking)."""
    pairs, partner, talker = jp_pairs()
    if (t, i) in pairs.get(person, ()):
        return t, i
    pt, tk = partner.get(person, {}), talker.get(person, {})
    if ds_silent:
        v = pt.get(t, t)            # a talking animation -> its idle pose
        return v, v
    if t not in pt and t in tk:     # an idle pose given as the talking one
        t = tk[t]
    if t in pt:
        return t, pt[t]
    return t, (t if i in pt else i)

def cmd_bgs(cmds, ds=False):
    """token pos -> background in force, along a command list"""
    res, bg = {}, None
    for x in cmds:
        if x[2] == 0x1B and x[3]:
            bg = 0xFF if (ds and x[3][0] == 0xFFF) else x[3][0] & 0x7FFF
        res[x[0]] = bg
    return res

def align_poses(gcmds, dcmds):
    """DS token pos -> GBA pose arguments, for the DS poses that line up"""
    g1 = [x for x in gcmds if x[2] == 0x1E and x[3]]
    d1 = [x for x in dcmds if x[2] == 0x1E and x[3]]
    gbg, dbg = cmd_bgs(gcmds), cmd_bgs(dcmds, True)
    res = {}
    if [x[3][0] for x in g1] == [x[3][0] for x in d1]:
        for a, b in zip(g1, d1):
            res[b[0]] = a[3]
        return res
    def ok(a, b):
        person, dv, gv = b[3][0], b[3][1], a[3][1]
        if a[3][0] != person:
            return False
        # the same place: a GBA pose for another background is drawn elsewhere
        if gbg.get(a[0]) is not None and dbg.get(b[0]) is not None and gbg[a[0]] != dbg[b[0]]:
            return False
        known = ANIM_VOTES.get((person, dv))
        return person == 0 or not known or gv in known
    # longest run of compatible pairs, in order (dynamic programming)
    n, m = len(g1), len(d1)
    L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            L[i][j] = max(L[i + 1][j], L[i][j + 1], L[i + 1][j + 1] + 1 if ok(g1[i], d1[j]) else 0)
    i = j = 0
    while i < n and j < m:
        if ok(g1[i], d1[j]) and L[i][j] == L[i + 1][j + 1] + 1:
            res[d1[j][0]] = g1[i][3]
            i += 1
            j += 1
        elif L[i + 1][j] >= L[i][j + 1]:
            i += 1
        else:
            j += 1
    return res

ANIM_VOTES = {}
POSES_BG = {}     # (background, person) -> poses the Japanese game shows there

def merge_section(gtoks, dtoks, choice_ids=None):
    """Return (out_tokens, gpos_to_out, patches, stats)."""
    g, _ = parse(gtoks, GBA_ARGS)
    d, _ = parse(dtoks, DS_ARGS)
    gcmds = [x for x in g if x[1] == 'cmd' and x[2] not in TEXT_CMDS]
    dcmds = [x for x in d if x[1] == 'cmd' and x[2] not in DS_ONLY and x[2] not in TEXT_CMDS]
    def key(x):
        op, args = x[2], x[3]
        if op == 0x1B and args and args[0] == 0xFFF:   # DS "no background" is the GBA's FF
            return (op, 0xFF)
        if op in KEYED_OPS and args:
            return (op, args[0])
        if op == 0x12 and args:     # screen blends pair by kind: fades only with fades, flashes with flashes
            return (op, args[0] >> 8)
        return (op,)
    sm = difflib.SequenceMatcher(None, [key(x) for x in gcmds], [key(x) for x in dcmds], autojunk=False)
    d2g = {}
    for bl in sm.get_matching_blocks():
        for k in range(bl.size):
            d2g[dcmds[bl.b + k][0]] = bl.a + k  # ds token pos -> gcmd index
    out = []
    gpos_to_out = {}
    patches = []  # (out_index_of_arg, gba_target_token_pos)
    emitted = set()
    stats = {'dropped_ds': 0, 'inserted_gba': 0, 'unmatched_kept': 0}

    def gba_only_ok(j):
        """GBA-only commands are kept, except poses (the DS decides who is
        shown); a GBA "nobody" right before a GBA background change stays, so
        a picture the DS moved to its touch screen (a map) is not drawn over"""
        if gcmds[j][2] != 0x1E:
            return True
        return tuple(gcmds[j][3][:1]) == (0,) and j + 1 < len(gcmds) and gcmds[j + 1][2] == 0x1B

    def emit_ds(op, args):
        if op == 0x06:  # sound effect: DS uses (id, flag), GBA packs id<<8 | flag
            sid = SE_MAP.get(args[0], args[0])
            out.extend([0x06, ((sid & 0xFF) << 8) | (args[1] & 0xFF)])
        else:
            out.append(op)
            out.extend(args)

    def emit_g(j):
        pos, kind, op, args = gcmds[j]
        gpos_to_out[pos] = len(out)
        if ds_auth(op, args):
            emitted.add(j)
            return
        out.append(op)
        if op == JUMP_IN_SECTION and not (args[0] & 0x80):
            patches.append((len(out) + 1, args[1] // 2))
        out.extend(args)
        emitted.add(j)

    def current_bg():
        bg = None
        for pos, kind, op, a in parse(out, GBA_ARGS)[0]:
            if kind == 'cmd' and op == 0x1B and a:
                bg = a[0]
        return bg

    def emit_batch(js):
        """GBA-only commands that come between two DS ones. The GBA waits
        after each court pan (1A) are text-flow commands, which come from the
        DS, so pans inserted from the GBA lost theirs: several then started
        on the same frame and the person was left off-centre. Of pans with
        nothing between them only the last is kept (none if it ends where the
        camera already is), and it gets the GBA's wait back."""
        js = [j for j in js if j not in emitted and gba_only_ok(j)]
        pans = [k for k, j in enumerate(js) if gcmds[j][2] == 0x1A]
        drop = set()
        for a, b in zip(pans, pans[1:]):
            drop.update(k for k in range(a, b) if gcmds[js[k]][2] in (0x1A, 0x1B, 0x0E))
        if len(pans) > 1:
            last = pans[-1]
            after = [k for k in range(last + 1, len(js)) if gcmds[js[k]][2] == 0x1B]
            here = current_bg()
            if after and here is not None and gcmds[js[after[0]]][3][0] == here:
                end = after[0] + 1
                if end < len(js) and gcmds[js[end]][2] == 0x0E:   # its name tag
                    end += 1
                drop.update(k for k in range(last, end) if gcmds[js[k]][2] in (0x1A, 0x1B, 0x0E))
        for k, j in enumerate(js):
            if k in drop:
                gpos_to_out[gcmds[j][0]] = len(out)
                emitted.add(j)
                stats['pans_dropped'] = stats.get('pans_dropped', 0) + (gcmds[j][2] == 0x1A)
                continue
            emit_g(j)
            stats['inserted_gba'] += 1
            if gcmds[j][2] == 0x1A:
                out.extend([0x0C, PAN_WAIT])

    # Character poses (1E person, talking, idle). Where the DS command lines up
    # with a GBA one for the same person, the GBA's own pose is used: the same
    # DS pose can stand for different GBA animations in different scenes (Maya
    # in the dark office, behind the glass...), and those animations place the
    # sprite differently. Other DS poses use what that DS pose stood for in
    # this section, else the chapter-wide map (learn_anim_map.py).
    #
    # The poses are lined up on their own (the commands around them can throw
    # the general alignment off by one, which gave a person the pose of the
    # line before or after: Gumshoe's walk-in animation replayed while he
    # talks). Where the GBA and DS sections show the same people in the same
    # order, pose n goes with pose n; otherwise poses are matched by person,
    # and a match is only taken when that GBA pose is one the DS pose stands
    # for somewhere in the game.
    pose_g = align_poses(gcmds, dcmds)
    sec_poses = collections.defaultdict(set)
    for x in gcmds:
        if x[2] == 0x1E and x[3] and x[3][0]:
            sec_poses[x[3][0]].update(x[3][1:3])
    # the background in force at each DS command (the DS uses the GBA's
    # background numbers): the same DS pose stands for a different GBA pose
    # at the witness stand and at the bench, behind the glass and in front
    dbg, bgnow = {}, None
    for pos, kind, op, args in d:
        if kind == 'cmd' and op == 0x1B and args:
            bgnow = 0xFF if args[0] == 0xFFF else args[0] & 0x7FFF
        dbg[pos] = bgnow
    local, last = {}, {}
    for pos, kind, op, args in d:
        if kind == 'cmd' and op == 0x1E and pos in pose_g:
            ga = pose_g[pos]
            for dv, gv in zip(args[1:3], ga[1:3]):
                local.setdefault((dbg[pos], args[0], dv), gv)
                local.setdefault((args[0], dv), gv)

    def fits_bg(person, gv, bg):
        """the Japanese game shows this pose of the person on this background
        (or never shows the person there at all)"""
        k = (bg, person & 0xFF)
        return gv is None or k not in POSES_BG or gv in POSES_BG[k]

    def conv_anim(args, pos=None):
        res = conv_anim_raw(args, pos)
        if res is not None and len(res) >= 4 and res[1]:
            t, i = fix_pose_pair(res[1], res[2], res[3], args[1] == args[2])
            if (t, i) != (res[2], res[3]):
                stats['pose_pair_fixed'] = stats.get('pose_pair_fixed', 0) + 1
            res = [0x1E, res[1], t, i]
        return res

    def conv_anim_raw(args, pos=None):
        person = args[0]
        if pos in pose_g:
            return [0x1E] + list(pose_g[pos])
        if person == 0:
            return [0x1E] + list(args)
        res = [0x1E, person]
        bg = dbg.get(pos)
        for v in args[1:3]:
            # what the DS pose stands for on this background in this section,
            # else the version of it the game shows on this background (Maya
            # behind the glass, Edgeworth at the witness stand...), else what
            # it stands for in this section / this scene / the chapter
            chap = ANIM_MAP.get('%s:%x:%x' % (ANIM_TAG, person, v))
            votes = ANIM_VOTES.get((person, v), set())
            onbg = sorted(x for x in votes if bg is not None and (bg, person & 0xFF) in POSES_BG
                          and x in POSES_BG[(bg, person & 0xFF)])
            scene = sorted(votes & sec_poses.get(person, set()))
            gv = local.get((bg, person, v))
            if gv is None and onbg:
                gv = chap if chap in onbg else (local.get((person, v)) if local.get((person, v)) in onbg else onbg[0])
            if gv is None and local.get((person, v)) is not None and fits_bg(person, local[(person, v)], bg):
                gv = local[(person, v)]
            if gv is None and scene:
                scene_bg = [x for x in scene if fits_bg(person, x, bg)] or scene
                gv = chap if chap in scene_bg else scene_bg[0]
            if gv is None:
                gv = ANIM_MAP.get('%s:%x:%x' % (ANIM_TAG, person, v), ANIM_ANY.get((person, v)))
            if gv is None or (CHAPTER_POSES.get(person) and gv not in CHAPTER_POSES[person]):
                # never seen, or a pose of this person the chapter never uses (it
                # belongs to another setting): their last pose here, else their
                # most used pose in the chapter
                gv = last.get(person, CHAPTER_USUAL.get(person, ANIM_USUAL.get(person)))
            if gv is None:
                return None
            res.append(gv)
        stats['anim_guess'] = stats.get('anim_guess', 0) + (gv is not None and (person, v) not in local
                                                             and '%s:%x:%x' % (ANIM_TAG, person, v) not in ANIM_MAP)
        return res

    nextg = 0
    prev_ds_cmd, this_cmd = None, None
    for pos, kind, op, args in d:
        if kind == 'text':
            out.append(op)
            prev_ds_cmd = this_cmd = None
            continue
        prev_ds_cmd, this_cmd = this_cmd, (op, tuple(args))
        if op == 0x69 and len(args) == 2 and args[0] == 0x62 and args[1] in DS_GAVELS:
            out.extend([GAVEL_MARK, DS_GAVELS[args[1]]])   # fix_gavel puts the GBA gavel here
            stats['gavels'] = stats.get('gavels', 0) + 1
            continue
        if op == 0x1E:
            conv = conv_anim(args, pos)
            if conv is not None:
                if pos in d2g:
                    j = d2g[pos]
                    emit_batch(range(nextg, j))
                    nextg = max(nextg, j)
                    emitted.add(j)
                    nextg = j + 1
                out.extend(conv)
                if len(conv) >= 3:
                    last[conv[1]] = conv[2]
                stats['anim_ds'] = stats.get('anim_ds', 0) + 1
                continue
        if pos in d2g:
            j = d2g[pos]
            emit_batch(range(nextg, j))  # GBA-only commands that come before this one
            nextg = max(nextg, j)
            gop, gargs = gcmds[j][2], gcmds[j][3]
            if op in DS_ARGS_WIN:
                out.append(op)
                out.extend(args)
                emitted.add(j)
            elif ds_auth(op, args):
                if not ds_auth(gop, gargs):
                    emit_g(j)          # a GBA fade the DS flash was paired with
                else:
                    gpos_to_out[gcmds[j][0]] = len(out)
                    emitted.add(j)
                emit_ds(op, args)
                stats['ds_fx'] = stats.get('ds_fx', 0) + 1
            elif ds_auth(gop, gargs):
                gpos_to_out[gcmds[j][0]] = len(out)
                emitted.add(j)
                emit_ds(op, args)      # the DS command in place of a GBA flash
            else:
                emit_g(j)
            nextg = j + 1
            continue
        if op == 0x07 and choice_ids:          # English answer labels for this choice
            out.extend([0x5E] + list(choice_ids))
            stats['choice_labels'] = 1
        if ds_auth(op, args):
            emit_ds(op, args)
            stats['ds_fx'] = stats.get('ds_fx', 0) + 1
        elif op in TEXT_CMDS or op in DS_KEEP or op == CENTRE:
            out.append(op)
            out.extend(args)
            stats['unmatched_kept'] += 1
        elif op == DS_WAIT:
            out.extend([0x0C, args[0]])
            stats['unmatched_kept'] += 1
        elif op == 0x1B and args and args[0] == 0xFFF and prev_ds_cmd and prev_ds_cmd[0] == 0x1E \
                and prev_ds_cmd[1][:1] == (0,):
            # the DS hides the person and blanks the picture for this line
            out.extend([0x1B, 0xFF])
            stats['ds_bg'] = stats.get('ds_bg', 0) + 1
        elif op == 0x1B and args and args[0] != 0xFFF and (args[0] & 0x7FFF) < GBA_BG_COUNT:
            # a DS background change with no GBA one beside it: the DS
            # backgrounds have the GBA numbers, and the person the DS shows
            # next belongs on it (else e.g. the judge stood on the gavel)
            out.extend([0x1B, args[0]])
            stats['ds_bg'] = stats.get('ds_bg', 0) + 1
        else:
            stats['dropped_ds'] += 1
    # leftovers: insert before the final terminator if there is one
    tail = [j for j in range(len(gcmds)) if j not in emitted and gba_only_ok(j)]
    if tail:
        term = None
        if out and out[-1] == 0x0D:
            term = out.pop()
        emit_batch(tail)
        if term is not None:
            out.append(term)
    return out, gpos_to_out, patches, stats


def apply_fixups(dtoks, fixes):
    """DS wording that refers to the touch screen -> GBA controls (gba_fixups.json)"""
    if not fixes:
        return dtoks
    import pseudo
    s = pseudo.to_pseudo(list(dtoks), DS_ARGS)
    for old, new in fixes:
        if old not in s:
            raise ValueError('fixup not found: ' + old)
        s = s.replace(old, new)
    return pseudo.from_pseudo(s)


# The judge's gavel. The GBA shows it with three background pictures (raised,
# swinging, down) and plays the slam sound and the shake itself:
#   1B 2F, 0C 5, 1B 1B, 0C 1, 1B 1C, 06 3A01, 27 A 1, 0C 3C   (one bang)
# and a longer run for three bangs. The DS plays its gavel with its own
# animation command (69 62 111 for one bang, 69 62 113 for three), which
# brings the sound and the shake with it and is not ported. The merge marks
# where the DS bangs the gavel; each mark gets the GBA gavel exactly as the
# GBA plays it, and gavel pictures the merge placed anywhere else are taken
# out (they were matched to the wrong lines in places). Who is shown after
# the gavel then follows the DS, on the right background.
GAVEL_BGS = {0x2F, 0x1B, 0x1C}
GAVEL_PARTS = {0x0C, 0x06, 0x27}
GAVEL_MARK = 0x7F                        # placeholder command between merge and fix_gavel
DS_GAVELS = {0x111: 1, 0x113: 3}
GAVEL_GBA = {
    1: [0x1B, 0x2F, 0x0C, 5, 0x1B, 0x1B, 0x0C, 1, 0x1B, 0x1C, 0x06, 0x3A01, 0x27, 0xA, 1, 0x0C, 0x3C],
    3: [0x1B, 0x2F, 0x0C, 5, 0x1B, 0x1B, 0x0C, 1, 0x1B, 0x1C, 0x06, 0x3B01, 0x27, 0xE, 1, 0x0C, 0xF,
        0x1B, 0x1B, 0x1B, 0x1C, 0x27, 0xE, 1, 0x0C, 0xF, 0x1B, 0x1B, 0x1B, 0x1C, 0x27, 0xA, 1, 0x0C, 0x3C],
}
GAVEL_ARGS = {**GBA_ARGS, GAVEL_MARK: 1}


def gavel_runs(toks):
    """(start, end, background count) of each gavel in a GBA section"""
    items, _ = parse(toks, GBA_ARGS)
    runs, i = [], 0
    while i < len(items):
        pos, kind, op, a = items[i]
        if kind == 'cmd' and op == 0x1B and a[0] == 0x2F:
            j, n = i, 0
            while j < len(items) and items[j][1] == 'cmd' and (
                    (items[j][2] == 0x1B and items[j][3][0] in GAVEL_BGS) or items[j][2] in GAVEL_PARTS):
                n += items[j][2] == 0x1B
                j += 1
            end = items[j][0] if j < len(items) else len(toks)
            runs.append((pos, end, n))
            i = j
        else:
            i += 1
    return runs


def fix_gavel(out, gtoks):
    """GBA gavel at each DS gavel mark; returns (tokens, old->new position list, note)"""
    items, _ = parse(out, GAVEL_ARGS)
    edits, note = [], None
    for q, (pos, kind, op, a) in enumerate(items):
        if kind != 'cmd':
            continue
        if op == GAVEL_MARK:
            end = pos + 2
            # the DS holds on its gavel picture; the GBA gavel ends with its own hold
            if q + 1 < len(items) and items[q + 1][1] == 'cmd' and items[q + 1][2] == 0x0C:
                end = items[q + 1][0] + 2
            edits.append((pos, end, list(GAVEL_GBA[a[0]])))
        elif op == 0x1B and a[0] in GAVEL_BGS:
            if not edits or edits[-1][1] <= pos:
                edits.append((pos, pos + 2, []))
    marks = [a[0] for p, k, op, a in items if k == 'cmd' and op == GAVEL_MARK]
    gba = [3 if n > 3 else 1 for s, e, n in gavel_runs(gtoks)]
    if marks != gba:
        note = 'gavels: DS %s, GBA %s' % (marks, gba)
    new, f, last = [], [0] * (len(out) + 1), 0
    for start, end, rep in edits:
        for p in range(last, start):
            f[p] = len(new) + p - last
        new += out[last:start]
        for p in range(start, end):
            f[p] = len(new)
        new += rep
        last = end
    for p in range(last, len(out) + 1):
        f[p] = len(new) + p - last
    new += out[last:]
    return new, f, note


# Fades. On the GBA a fade to black (12, mode 2) darkens every layer, the
# text box and its letters included, so the GBA fades back in (mode 1)
# before a line is read. The DS darkens only the picture and sometimes fades
# back in only after a narration; merged in that order the narration ran on
# a black screen. A line printed in the dark is fine when the fade-in follows
# before the reader has to press on ("To be continued.") and the GBA does the
# same in that section; otherwise a fade-in goes just before it: the next one
# is moved there when the GBA section never shows text in the dark, else a
# new one is added.
FADE_IN = [0x12, 0x101, 1, 0x1F]


def starts_dark(toks):
    """the section fades in before its first line: it begins on a black screen"""
    for pos, kind, op, a in parse(toks, GBA_ARGS)[0]:
        if kind == 'text':
            return False
        if kind == 'cmd' and op == 0x12 and a and a[0] >> 8 in (1, 2):
            return a[0] >> 8 == 1
    return False


def dark_runs(toks, dark=False):
    """(position of the first text printed while faded to black, needs a fade-in)"""
    items, _ = parse(toks, GBA_ARGS)
    res, prev_text = [], False
    for q, (pos, kind, op, a) in enumerate(items):
        if kind == 'text':
            if dark and not prev_text:
                bad = True
                for pos2, kind2, op2, a2 in items[q:]:
                    if kind2 == 'cmd' and op2 in (0x02, 0x2D, 0x0D):   # page break / wait for A / end
                        break
                    if kind2 == 'cmd' and op2 == 0x12 and a2 and a2[0] >> 8 == 1:
                        bad = False
                        break
                res.append((pos, bad))
            prev_text = True
            continue
        if kind == 'cmd' and op == 0x12 and a:
            dark = {1: False, 2: True}.get(a[0] >> 8, dark)
        if not (kind == 'cmd' and op in (0x01, 0x03, 0x0B, 0x0C)):
            prev_text = False
    return res


def fix_dark(out, gtoks):
    f = list(range(len(out) + 1))
    start = starts_dark(gtoks)
    gba_dark = bool(dark_runs(gtoks, start))   # the GBA itself prints some line in the dark here
    notes = []
    while True:
        runs = [p for p, bad in dark_runs(out, start) if bad or not gba_dark]
        if not runs:
            break
        at = runs[0]
        items, _ = parse(out, GBA_ARGS)
        nxt = next((x for x in items if x[0] > at and x[1] == 'cmd' and x[2] == 0x12 and x[3] and x[3][0] >> 8 in (1, 2)), None)
        if not gba_dark and nxt is not None and nxt[3][0] >> 8 == 1:
            p = nxt[0]
            out = out[:at] + out[p:p + 4] + out[at:p] + out[p + 4:]
            f = [q + 4 if at <= q < p else (at if p <= q < p + 4 else q) for q in f]
            notes.append('moved')
        else:
            out = out[:at] + FADE_IN + out[at:]
            f = [q + 4 if q >= at else q for q in f]
            notes.append('added')
        if len(notes) > 20:
            return out, f, 'fade loop'
    # a fade-in on a bright screen starts from black: drop the ones the moves
    # above left behind (unless the GBA section has such a fade itself)
    if notes and not bright_fade_ins(gtoks):
        for p in reversed(bright_fade_ins(out, 'dark' if start else None)):
            out = out[:p] + out[p + 4:]
            f = [q - 4 if q >= p + 4 else (p if q >= p else q) for q in f]
            notes.append('dropped')
    return out, f, ('fade-in %s before lines in the dark' % ','.join(notes)) if notes else None


def bright_fade_ins(toks, start=None):
    """fade-ins (12, mode 1) run while the screen is known to be bright"""
    state, res = start, []
    for pos, kind, op, a in parse(toks, GBA_ARGS)[0]:
        if kind == 'cmd' and op == 0x12 and a:
            m = a[0] >> 8
            if m == 1:
                if state == 'bright':
                    res.append(pos)
                state = 'bright'
            elif m == 2:
                state = 'dark'
    return res


# Who is shown on which background. Every line is checked against the
# person / background pairs the GBA itself shows lines with; when a line
# would put someone on a background the GBA never shows them on, the GBA
# background changes merged in since the previous line (strays from GBA
# lines the DS words differently) are taken out, latest first, with their
# name tags (unless the tag names the person shown), until the pair is one
# the GBA uses.
SEEN_PAIRS = None


def text_states(toks):
    """(first text position, background, person, [(pos, op, args) commands since the previous text])"""
    bg = person = None
    res, since, intext = [], [], False
    for pos, kind, op, a in parse(toks, GBA_ARGS)[0]:
        if kind == 'text':
            if not intext:
                res.append((pos, bg, person, since))
                since = []
            intext = True
            continue
        if op not in (0x01, 0x03, 0x0B, 0x0C):
            intext = False
        since.append((pos, op, a))
        if op == 0x1B and a:
            bg = a[0]
        elif op == 0x1E and a:
            person = a[0]
    return res


def seen_pairs(gdir):
    global SEEN_PAIRS
    if SEEN_PAIRS is None:
        SEEN_PAIRS = set()
        for f in glob.glob(os.path.join(gdir, 'scenario_*.phscr')):
            b, n, offs = load(f)
            for x in section_bounds(b, offs):
                if x:
                    SEEN_PAIRS |= {(bg, pe) for p, bg, pe, c in text_states(tokens(b, *x))}
    return SEEN_PAIRS


def fix_pairs(out, seen):
    f = list(range(len(out) + 1))
    removed = 0
    for _ in range(50):
        bad = None
        prev_bg = None
        for pos, bg, pe, since in text_states(out):
            if bg is not None and pe not in (None, 0) and (bg, pe) not in seen:
                bad = (pos, bg, pe, since, prev_bg)
                break
            prev_bg = bg
        if bad is None:
            break
        pos, bg, pe, since, prev_bg = bad
        bgs = [q for q, (p, op, a) in enumerate(since) if op == 0x1B]
        # background in force before this run of commands
        cut = None
        for k in range(len(bgs) - 1, -1, -1):
            rest = [since[q][2][0] for q in bgs[:k]]
            now = rest[-1] if rest else prev_bg
            if now is not None and (now, pe) in seen:
                cut = bgs[k:]
                break
        if cut is None:
            break
        drop = []
        for q in cut:
            drop.append((since[q][0], 2))
            # its name tag goes too, unless it names the person shown
            if q + 1 < len(since) and since[q + 1][1] == 0x0E and (since[q + 1][2][0] >> 8) & 0x7F != pe:
                drop.append((since[q + 1][0], 2))
        for p, n in sorted(drop, reverse=True):
            out = out[:p] + out[p + n:]
            f = [x - n if x >= p + n else (p if x >= p else x) for x in f]
            removed += 1
    return out, f, ('%d stray background commands removed' % removed) if removed else None


# Each GBA pose is drawn for the place it is used in (behind the detention
# center glass, at the witness stand, at the prosecution bench...): the same
# person's poses for another place sit higher or lower or further across, so
# showing one there makes the character jump. A pose the Japanese game never
# shows on the background in force when the line is typed is replaced by the
# person's last pose on that background in the section (the DS's extra
# expression change is dropped), else by their usual pose there.
SEEN_POSES = None


def seen_poses(gdir):
    global SEEN_POSES
    if SEEN_POSES is None:
        SEEN_POSES = collections.defaultdict(collections.Counter)
        for f in glob.glob(os.path.join(gdir, 'scenario_*.phscr')):
            b, n, offs = load(f)
            for x in section_bounds(b, offs):
                if not x:
                    continue
                bg = pose = None
                intext = False
                for pos, kind, op, a in parse(tokens(b, *x), GBA_ARGS)[0]:
                    if kind == 'text':
                        if not intext and bg is not None and pose and pose[0]:
                            SEEN_POSES[(bg, pose[0])][pose[1:]] += 1
                        intext = True
                        continue
                    if op not in (0x01, 0x03, 0x0B, 0x0C):
                        intext = False
                    if op == 0x1B and a:
                        bg = a[0] & 0x7FFF
                    elif op == 0x1E and a:
                        pose = (a[0] & 0xFF, a[1], a[2])
    return SEEN_POSES


def fix_scene_poses(out, seen):
    out = list(out)
    vals = {k: set(v for pr in c for v in pr) for k, c in seen.items()}
    bg = cur = None
    good = {}
    fixed = 0
    intext = False
    for pos, kind, op, a in parse(out, GBA_ARGS)[0]:
        if kind == 'text':
            if not intext and bg is not None and cur and cur[0]:
                k = (bg, cur[0])
                if k in vals and (cur[1] not in vals[k] or cur[2] not in vals[k]):
                    t, i = good.get(k) or seen[k].most_common(1)[0][0]
                    out[cur[3] + 2], out[cur[3] + 3] = t, i
                    cur = (cur[0], t, i, cur[3])
                    fixed += 1
                if k in vals:
                    good[k] = (cur[1], cur[2])
            intext = True
            continue
        if op not in (0x01, 0x03, 0x0B, 0x0C):
            intext = False
        if op == 0x1B and a:
            bg = a[0] & 0x7FFF
        elif op == 0x1E and a:
            cur = (a[0] & 0xFF, a[1], a[2], pos)
    return out, ('%d poses from another place replaced' % fixed) if fixed else None


POSE_HEADS = None   # (person, animation) -> (head centre x, head top y), measured in the game
JP_TRANS = None


def pose_events(toks):
    """Each pose command with the one shown just before it (same person, no
    background change or pan in between) and whether that one was showing
    its idle animation by then: the engine switches to idle while it waits
    for a button (02, 07, 0A, 2D) and back to talking when a page break (02)
    goes on to the next page."""
    ev = []
    cur = None
    text = False   # True: the previous pose is on its idle animation
    bg = None
    reset = False
    for pos, kind, op, a in parse(toks, GBA_ARGS)[0]:
        if kind == 'text':
            continue
        if op in (0x07, 0x0A, 0x2D):
            text = True
        elif op == 0x02:
            text = False
        if op in (0x1B, 0x1A):
            cur = None
            reset = True
            if op == 0x1B and a:
                bg = a[0] & 0x7FFF
        elif op == 0x1E and a:
            e = [pos, a[0] & 0xFF, a[1], a[2], None, text, bg, not ev and bg is None and not reset]
            if a[0] & 0xFF and cur is not None and cur[1] == e[1]:
                e[4] = cur
            ev.append(e)
            cur = e if a[0] & 0xFF else None
            text = False
    return ev


def end_state(toks):
    """(person, talking, idle, on idle) shown when the section ends, if nobody
    was cleared and no background change or pan came after the last pose"""
    st = None
    for pos, kind, op, a in parse(toks, GBA_ARGS)[0]:
        if kind == 'text':
            continue
        if op in (0x07, 0x0A, 0x2D) and st:
            st = st[:3] + (True,)
        elif op == 0x02 and st:
            st = st[:3] + (False,)
        if op in (0x1B, 0x1A):
            st = None
        elif op == 0x1E and a:
            st = (a[0] & 0xFF, a[1], a[2], False) if a[0] & 0xFF else None
    return st


def jp_transitions(gdir):
    """Changes from one animation to another that the GBA script makes: the
    pose before (its idle one after text, else its talking one) to the new
    talking animation, and each talking animation to its idle partner."""
    global JP_TRANS
    if JP_TRANS is None:
        JP_TRANS = set()
        for f in glob.glob(os.path.join(gdir, 'scenario_*.phscr')):
            b, n, offs = load(f)
            carry = None
            for x in section_bounds(b, offs):
                if not x:
                    carry = None
                    continue
                toks = tokens(b, *x)
                for k, (pos, p, t, i, prev, text, bg, clean) in enumerate(pose_events(toks)):
                    if not p:
                        continue
                    JP_TRANS.add((p, t, i))
                    if prev:
                        JP_TRANS.add((p, prev[3] if text else prev[2], t))
                    elif clean and carry and carry[0] == p:   # on from the section before
                        JP_TRANS.add((p, carry[2] if (carry[3] or text) else carry[1], t))
                carry = end_state(toks)
    return JP_TRANS


def moves(p, a, b):
    """True when going from animation a to b moves the head 4 pixels or more"""
    global POSE_HEADS
    if POSE_HEADS is None:
        hp = os.path.join(os.path.dirname(__file__), 'pose_heads.json')
        POSE_HEADS = {tuple(int(v, 16) for v in k.split(':')): h for k, h in json.load(open(hp)).items()}
    ha, hb = POSE_HEADS.get((p, a)), POSE_HEADS.get((p, b))
    return bool(ha and hb and (abs(ha[0] - hb[0]) >= 4 or abs(ha[1] - hb[1]) >= 4))


def fix_moving_poses(out, gdir, carry=None):
    """A DS expression the GBA has no line for can put a character in a pose
    the GBA never goes to from the one before (or never leaves to the next
    one), and where the two are drawn with the head in another place the
    character jumps on screen. Such a pose is replaced by one of the
    person's GBA poses that the GBA itself goes to from the previous pose and
    on to the next (the same kind: talking or silent), if there is one."""
    out = list(out)
    jt = jp_transitions(gdir)
    pairs = jp_pairs()[0]
    def ok(p, a, b):
        return a == b or (p, a, b) in jt or not moves(p, a, b)
    ev = pose_events(out)
    if ev and ev[0][7] and carry and carry[0] == ev[0][1]:
        # the section goes on from the one before with the same person shown
        ev[0][4] = [None, carry[0], carry[1], carry[2], None, None, None, False]
        ev[0][5] = ev[0][5] or carry[3]
    fixed = 0
    for k, e in enumerate(ev):
        pos, p, t, i, prev, text, bg, clean = e
        if not p:
            continue
        here = POSES_BG.get((bg, p)) if bg is not None else None
        nxt = ev[k + 1] if k + 1 < len(ev) and ev[k + 1][4] is e else None
        def score(t2, i2):
            src = (prev[3] if text else prev[2]) if prev else None
            res = []
            if src is not None:
                res.append(ok(p, src, t2) + ((p, src, t2) in jt))
            if nxt is not None:
                n_src = i2 if nxt[5] else t2
                res.append(ok(p, n_src, nxt[2]) + ((p, n_src, nxt[2]) in jt))
            return res
        now = score(t, i)
        if not now or all(v >= 1 for v in now):
            continue
        best = None
        for (t2, i2), cnt in pairs.get(p, {}).items():
            if (t2 == i2) != (t == i):
                continue
            if here is not None and not (t2 in here and i2 in here):
                continue      # drawn for another place
            sc = score(t2, i2)
            if all(v >= (1 if here is not None else 2) for v in sc):
                key = (sum(sc), cnt)
                if best is None or key > best[0]:
                    best = (key, t2, i2)
        if best:
            out[pos + 2], out[pos + 3] = best[1], best[2]
            e[2], e[3] = best[1], best[2]
            fixed += 1
    return out, ('%d poses that jumped replaced' % fixed) if fixed else None


PAN_WAIT = 0x23   # frames the GBA script waits after a court pan (1A)


def fix_pan_waits(out):
    """The DS waits 30 frames after a court pan before showing the person;
    the GBA pan runs a little longer and the GBA script always waits 35. A
    pose set while the pan is still running gets moved by its last steps,
    which left the person off-centre (up to 22 pixels) until the next pose
    change snapped them back."""
    out = list(out)
    items = parse(out, GBA_ARGS)[0]
    n = 0
    for k, (pos, kind, op, a) in enumerate(items):
        if kind == 'cmd' and op == 0x1A and k + 1 < len(items):
            p2, k2, op2, a2 = items[k + 1]
            if k2 == 'cmd' and op2 == 0x0C and a2[0] < PAN_WAIT:
                out[p2 + 1] = PAN_WAIT
                n += 1
    return out, n


def map_pos(gpos_to_out, target):
    keys = sorted(gpos_to_out)
    for k in keys:
        if k >= target:
            return gpos_to_out[k]
    return gpos_to_out[keys[-1]] if keys else 0


def port(gfile, dfile, outfile, report=None, scenario_idx=None, pairs=None):
    global ANIM_MAP, ANIM_TAG, ANIM_ANY, ANIM_USUAL
    mp = os.path.join(os.path.dirname(__file__), 'anim_map.json')
    ANIM_MAP = json.load(open(mp)) if os.path.exists(mp) else {}
    ANIM_TAG = os.path.basename(gfile).split('_script')[0]
    # a person's animations are the same in every chapter: what a DS pose
    # stands for elsewhere, and each person's most used GBA pose
    votes, usual = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for k, gv in ANIM_MAP.items():
        tag, person, dv = k.split(':')
        votes[(int(person, 16), int(dv, 16))][gv] += 1
        usual[int(person, 16)][gv] += 1
    ANIM_ANY = {k: c.most_common(1)[0][0] for k, c in votes.items()}
    ANIM_USUAL = {k: c.most_common(1)[0][0] for k, c in usual.items()}
    global ANIM_VOTES, POSES_BG
    ANIM_VOTES = {k: set(c) for k, c in votes.items()}
    POSES_BG = {k: set(v for pr in c for v in pr) for k, c in seen_poses(os.path.dirname(gfile)).items()}
    global CHAPTER_POSES, CHAPTER_USUAL
    gb0, gn0, goffs0 = load(gfile)
    cp = collections.defaultdict(collections.Counter)
    for x in section_bounds(gb0, goffs0):
        if x:
            for pos, kind, op, a in parse(tokens(gb0, *x), GBA_ARGS)[0]:
                if kind == 'cmd' and op == 0x1E and a and a[0]:
                    cp[a[0]][a[1]] += 1
                    cp[a[0]][a[2]] += 1
    CHAPTER_POSES = {k: set(c) for k, c in cp.items()}
    CHAPTER_USUAL = {k: c.most_common(1)[0][0] for k, c in cp.items()}
    gb, gn, goffs = load(gfile)
    db, dn, doffs = load(dfile)
    G = section_bounds(gb, goffs)
    D = section_bounds(db, doffs)
    if pairs is None:
        pairs = pair_sections(gb, G, db, D)
    choices = {}
    cp = os.path.join(os.path.dirname(__file__), 'choice_table.json')
    if scenario_idx is not None and os.path.exists(cp):
        for c in json.load(open(cp)):
            if c['scenario'] == scenario_idx:
                choices[c['ds_section']] = c['ids']
    fp = os.path.join(os.path.dirname(__file__), 'gba_fixups.json')
    fixups = json.load(open(fp)).get(str(scenario_idx), {}) if scenario_idx is not None and os.path.exists(fp) else {}
    # find header entries used as jump descriptors
    desc_idx = set()
    for x in G:
        if not x:
            continue
        for pos, kind, op, args in parse(tokens(gb, *x), GBA_ARGS)[0]:
            if kind != 'cmd':
                continue
            if op == 0x35 and (args[0] & 0x80):
                desc_idx.add(args[1])
            if op == 0x36:
                desc_idx.add(args[0])
    sec_out = {}
    maps = {}
    lines = []
    carry = None    # who is shown at the end of the section before
    for gi, x in enumerate(G):
        if not x or gi in desc_idx:
            carry = None
            continue
        gt = tokens(gb, *x)
        if gi in pairs and D[pairs[gi]]:
            dt = apply_fixups(tokens(db, *D[pairs[gi]]), fixups.get(str(pairs[gi]), []))
            out, m, patches, st = merge_section(gt, dt, choices.get(pairs[gi]))
            out, f, note = fix_gavel(out, gt)
            m = {g: f[o] for g, o in m.items()}
            patches = [(f[idx], tgt) for idx, tgt in patches]
            if note:
                st = dict(st, gavel=note)
            out, f, note = fix_dark(out, gt)
            m = {g: f[o] for g, o in m.items()}
            patches = [(f[idx], tgt) for idx, tgt in patches]
            if note:
                st = dict(st, fade=note)
            out, f, note = fix_pairs(out, seen_pairs(os.path.dirname(gfile)))
            m = {g: f[o] for g, o in m.items()}
            patches = [(f[idx], tgt) for idx, tgt in patches]
            if note:
                st = dict(st, pairs=note)
            out, note = fix_scene_poses(out, seen_poses(os.path.dirname(gfile)))
            if note:
                st = dict(st, poses=note)
            out, note = fix_moving_poses(out, os.path.dirname(gfile), carry)
            if note:
                st = dict(st, moving=note)
            out, n = fix_pan_waits(out)
            if n:
                st = dict(st, pan_waits=n)
            for idx, tgt in patches:
                out[idx] = map_pos(m, tgt) * 2
            lines.append('sec %3d <- ds %3d  %s' % (gi, pairs[gi], st))
        else:
            out = gt
            m = {p: p for p in range(len(gt))}
            lines.append('sec %3d   KEPT JAPANESE (no DS match)' % gi)
        sec_out[gi] = out
        maps[gi] = m
        carry = end_state(out)
    # assemble
    n = gn
    header = bytearray(struct.pack('<I', n) + b'\0' * (4 * n))
    body = bytearray()
    start = len(header)
    placed = {}
    newoffs = [0] * n
    for gi, x in enumerate(G):
        if gi in desc_idx:
            continue
        if not x:
            newoffs[gi] = goffs[gi]
            continue
        key = x[0]
        if key not in placed:
            placed[key] = start + len(body)
            body += struct.pack('<%dH' % len(sec_out[gi]), *sec_out[gi])
            if len(body) % 4:
                body += b'\0\0'
        newoffs[gi] = placed[key]
    for idx in desc_idx:
        v = goffs[idx]
        off, sec = v & 0xFFFF, v >> 16
        newoff = map_pos(maps.get(sec, {0: 0}), off // 2) * 2 if sec in maps else off
        newoffs[idx] = (sec << 16) | newoff
    struct.pack_into('<%dI' % n, header, 4, *newoffs)
    open(outfile, 'wb').write(bytes(header + body))
    if report:
        open(report, 'w').write('\n'.join(lines) + '\n')
    kept = sum(1 for l in lines if 'KEPT' in l)
    return len(lines), kept


if __name__ == '__main__':
    total, kept = port(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    print('%s: %d sections, %d left in Japanese' % (os.path.basename(sys.argv[3]), total, kept))
