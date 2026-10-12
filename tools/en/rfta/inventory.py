"""What the fifth episode's scripts use, against episodes 1-4: backgrounds,
people and their animations, evidence, music, sound effects, name tags,
rooms, map markers, and the commands only it uses. Prints the counts the
report quotes (docs/rise_from_the_ashes.md).
usage: inventory.py [out.json]"""
import sys, os, collections, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds_script
from ds_script import sections, FIRST_RFTA_FILE, LAST_RFTA_FILE

class Inv:
    def __init__(s):
        for f in ('bg', 'person', 'anim', 'evidence', 'bgm', 'se', 'name', 'room', 'ops', 'bad', 'scroll', 'marker'):
            setattr(s, f, collections.Counter())
        s.sections = s.text = s.choices = s.files = 0

def scan(files):
    inv = Inv()
    for k in files:
        inv.files += 1
        for si, items in sections(k):
            inv.sections += 1
            for p, kind, op, a in items:
                if kind == 'text': inv.text += 1; continue
                if kind == 'bad': inv.bad[op] += 1; continue
                inv.ops[op] += 1
                if op == 0x1B: inv.bg[a[0] & 0x7FFF] += 1
                elif op == 0x1E: inv.person[a[0]] += 1; inv.anim[(a[0], a[1])] += 1; inv.anim[(a[0], a[2])] += 1
                elif op in (0x13, 0x17): inv.evidence[a[0] & 0x80FF] += 1
                elif op == 0x19: inv.evidence[a[0] & 0x80FF] += 1; inv.evidence[a[1] & 0x80FF] += 1
                elif op == 0x05: inv.bgm[a[0]] += 1
                elif op == 0x06: inv.se[a[0]] += 1
                elif op == 0x0E: inv.name[a[0]] += 1
                elif op in (0x33, 0x34): inv.room[a[0]] += 1
                elif op in (0x08, 0x09): inv.choices += 1
                elif op == 0x1A: inv.scroll[a[0]] += 1
                elif op == 0x39: inv.marker[a[0]] += 1
    return inv

def main():
    old = scan(range(0, FIRST_RFTA_FILE)); new = scan(range(FIRST_RFTA_FILE, LAST_RFTA_FILE + 1))
    rep = {}
    for f in ('bg', 'person', 'evidence', 'bgm', 'se', 'name', 'room', 'scroll', 'marker'):
        o, n = getattr(old, f), getattr(new, f)
        nn = sorted(set(n) - set(o))
        rep[f] = {'ep1_4': len(o), 'rfta': len(n), 'new': len(nn), 'new_ids': nn}
        print('%-9s ep1-4 %4d  rfta %4d  new in rfta %4d' % (f, len(o), len(n), len(nn)))
    pa_old, pa_new = collections.defaultdict(set), collections.defaultdict(set)
    for p, an in old.anim: pa_old[p].add(an)
    for p, an in new.anim: pa_new[p].add(an)
    tot = tot_new = 0
    for p in sorted(pa_new):
        nn = pa_new[p] - pa_old.get(p, set()); tot += len(pa_new[p]); tot_new += len(nn)
        print('person %4x: animation numbers in rfta %3d, new %3d%s' % (p, len(pa_new[p]), len(nn), '  (new person)' if p not in pa_old else ''))
    print('animation numbers in rfta %d, new %d' % (tot, tot_new))
    for name, inv in (('rfta', new), ('ep1-4', old)):
        print('%s: files %d sections %d letters %d choices %d' % (name, inv.files, inv.sections, inv.text, inv.choices))
    print('unparsed tokens', dict(new.bad))
    print('commands only the fifth episode uses:', {'%x' % k: v for k, v in sorted(new.ops.items()) if k not in old.ops})
    print('every command the fifth episode uses:', ' '.join('%x:%d' % kv for kv in sorted(new.ops.items())))
    if len(sys.argv) > 1:
        json.dump({'rep': rep, 'anims': {str(p): sorted(v) for p, v in pa_new.items()}, 'anims_ep1_4': {str(p): sorted(v) for p, v in pa_old.items()}}, open(sys.argv[1], 'w'))

if __name__ == '__main__':
    main()
