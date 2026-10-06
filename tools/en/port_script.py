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
import sys, struct, json, difflib, os
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
ANIM_MAP = {}   # 'scenario_x:person:dsval' -> gba value (learn_anim_map.py)
ANIM_TAG = ''  # matched for alignment, but the DS arguments are used (speaker nametag)
JUMP_IN_SECTION = 0x35


def sig(toks):
    return (any(t >= 0x80 for t in toks), tuple(toks[:3]))


def pair_sections(gb, G, db, D):
    """Return dict gba_section_index -> ds_section_index."""
    Gs = [str(sig(tokens(gb, *x))) if x else 'none%d' % i for i, x in enumerate(G)]
    Ds = [str(sig(tokens(db, *x))) if x else 'dnone%d' % i for i, x in enumerate(D)]
    sm = difflib.SequenceMatcher(None, Gs, Ds, autojunk=False)
    pairs = {}
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            for k in range(i2 - i1):
                pairs[i1 + k] = j1 + k
        elif op == 'replace':
            # fuzzy: pair by command-op similarity within the replaced window
            for gi in range(i1, i2):
                if not G[gi]:
                    continue
                gops = [x[2] for x in parse(tokens(gb, *G[gi]), GBA_ARGS)[0] if x[1] == 'cmd']
                best, bj = 0.0, None
                for dj in range(j1, j2):
                    if not D[dj]:
                        continue
                    dops = [x[2] for x in parse(tokens(db, *D[dj]), DS_ARGS)[0] if x[1] == 'cmd' and x[2] not in DS_ONLY]
                    r = difflib.SequenceMatcher(None, gops, dops, autojunk=False).ratio()
                    if r > best:
                        best, bj = r, dj
                if bj is not None and best >= 0.6:
                    pairs[gi] = bj
    return pairs


def merge_section(gtoks, dtoks, choice_ids=None):
    """Return (out_tokens, gpos_to_out, patches, stats)."""
    g, _ = parse(gtoks, GBA_ARGS)
    d, _ = parse(dtoks, DS_ARGS)
    gcmds = [x for x in g if x[1] == 'cmd' and x[2] not in TEXT_CMDS]
    dcmds = [x for x in d if x[1] == 'cmd' and x[2] not in DS_ONLY and x[2] not in TEXT_CMDS]
    def key(x):
        op, args = x[2], x[3]
        if op in KEYED_OPS and args:
            return (op, args[0])
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

    def emit_g(j):
        pos, kind, op, args = gcmds[j]
        gpos_to_out[pos] = len(out)
        out.append(op)
        if op == JUMP_IN_SECTION and not (args[0] & 0x80):
            patches.append((len(out) + 1, args[1] // 2))
        out.extend(args)
        emitted.add(j)

    def conv_anim(args):
        person = args[0]
        try:
            return [0x1E, person] + [ANIM_MAP['%s:%x:%x' % (ANIM_TAG, person, v)] for v in args[1:3]]
        except KeyError:
            return None

    nextg = 0
    for pos, kind, op, args in d:
        if kind == 'text':
            out.append(op)
            continue
        if op == 0x1E:
            conv = conv_anim(args)
            if conv is not None:
                if pos in d2g:
                    j = d2g[pos]
                    while nextg < j:
                        if nextg not in emitted and gcmds[nextg][2] != 0x1E:
                            emit_g(nextg)
                            stats['inserted_gba'] += 1
                        nextg += 1
                    emitted.add(j)
                    nextg = j + 1
                out.extend(conv)
                stats['anim_ds'] = stats.get('anim_ds', 0) + 1
                continue
        if pos in d2g:
            j = d2g[pos]
            while nextg < j:  # GBA-only commands that come before this one
                if nextg not in emitted and gcmds[nextg][2] != 0x1E:
                    emit_g(nextg)
                    stats['inserted_gba'] += 1
                nextg += 1
            if op in DS_ARGS_WIN:
                out.append(op)
                out.extend(args)
                emitted.add(j)
            else:
                emit_g(j)
            nextg = j + 1
            continue
        if op == 0x07 and choice_ids:          # English answer labels for this choice
            out.extend([0x5E] + list(choice_ids))
            stats['choice_labels'] = 1
        if op in TEXT_CMDS or op in DS_KEEP:
            out.append(op)
            out.extend(args)
            stats['unmatched_kept'] += 1
        elif op == 0x06:  # sound effect: DS uses (id, flag), GBA packs id<<8 | flag
            out.extend([0x06, ((args[0] & 0xFF) << 8) | (args[1] & 0xFF)])
            stats['unmatched_kept'] += 1
        else:
            stats['dropped_ds'] += 1
    # leftovers: insert before the final terminator if there is one
    tail = [j for j in range(len(gcmds)) if j not in emitted and gcmds[j][2] != 0x1E]
    if tail:
        term = None
        if out and out[-1] == 0x0D:
            term = out.pop()
        for j in tail:
            emit_g(j)
            stats['inserted_gba'] += 1
        if term is not None:
            out.append(term)
    return out, gpos_to_out, patches, stats


def map_pos(gpos_to_out, target):
    keys = sorted(gpos_to_out)
    for k in keys:
        if k >= target:
            return gpos_to_out[k]
    return gpos_to_out[keys[-1]] if keys else 0


def port(gfile, dfile, outfile, report=None, scenario_idx=None, pairs=None):
    global ANIM_MAP, ANIM_TAG
    mp = os.path.join(os.path.dirname(__file__), 'anim_map.json')
    ANIM_MAP = json.load(open(mp)) if os.path.exists(mp) else {}
    ANIM_TAG = os.path.basename(gfile).split('_script')[0]
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
    for gi, x in enumerate(G):
        if not x or gi in desc_idx:
            continue
        gt = tokens(gb, *x)
        if gi in pairs and D[pairs[gi]]:
            out, m, patches, st = merge_section(gt, tokens(db, *D[pairs[gi]]), choices.get(pairs[gi]))
            for idx, tgt in patches:
                out[idx] = map_pos(m, tgt) * 2
            lines.append('sec %3d <- ds %3d  %s' % (gi, pairs[gi], st))
        else:
            out = gt
            m = {p: p for p in range(len(gt))}
            lines.append('sec %3d   KEPT JAPANESE (no DS match)' % gi)
        sec_out[gi] = out
        maps[gi] = m
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
