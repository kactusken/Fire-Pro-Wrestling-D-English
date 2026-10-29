#!/usr/bin/env python3
"""Decode a wrestler record (504 bytes: SBL.BIN entry 2, and the head of an edit record) into an
English profile: Skill/Param Edit values, the 78 move slots with their marks, CPU Logic.

  python3 tools/fprecord.py [NAME|INDEX ...]   print profiles (default: Riki Choshu)

    import fprecord
    p = fprecord.profile(rec, move_name)      # move_name(id) -> English move name
    p = fprecord.profile(rec, move_name, names='parody')

Everything is read from the original program (extracted/1ST_READ.BIN: Skill Edit descriptors,
Move Edit slot/button tables, CPU Logic tables) with the English of translation/text/ui.csv, so
labels are what the patched game shows. Used by tools/guidedata.py (the guide's wrestler profiles);
the record layout is in docs/TECHNICAL.md, Wrestler records.
"""
import csv
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import fpdtext  # noqa: E402
import lzss  # noqa: E402
import sbl  # noqa: E402

BASE = 0x8C010000
REC = 504
EDIT_BUF = 0x8C12D670          # editor copy of the record: value ptr - EDIT_BUF = record offset
SKILL_DESC = 0x8C12DD28        # 30 descriptors x 24 bytes (Promotion ... Voice 2 Type)
VOICE_RANGES = 0x8C12E05C      # 11 x (u16 first, u16 last) sample ids per voice tone
PARAM_LABELS = 0x8C12E0B8      # 22 label pointers, record +0x5D..+0x72
SLOT_LABELS = 0x8C12ED34       # 78 label pointers by record slot
SLOT_ORDER = 0x8C12EE6C        # 78 bytes: Move Edit row -> record slot
SLOT_ICONS = 0x8C12F640        # 78 x 10 bytes by Move Edit row: (x, icon1, x, icon2, x)
CPU_SITUATIONS = 0x8C1302B0    # 20 x (label ptr, conditions ptr, u8 n conditions, u8 id, u16 0)
STYLE_ACTIONS = 0x8C1303A0     # 16 styles x 3 label ptrs: CPU actions 0x201/0x202/0x203
STANCES = 0x8C1307AC           # Appearance stance labels (12)
SIZES = ['Men S', 'Men M', 'Men L', 'Women']
ICONS = {0: 'X', 1: 'A', 2: 'B', 4: 'Up', 5: 'Down', 6: 'Left/Right', 7: 'Up',
         11: 'Dir', 12: 'Stick Up', 13: 'Stick Down', 14: 'Stick Left', 15: 'Stick Right'}
BUTTONS = [''] * 78            # filled by slot_labels(): the button glyphs of each record slot
# CPU Logic glyphs that differ from Move Edit (seen): Whip = Y, the style's grapple/counter reply = R,
# Run Out / Apron Out show B (Move Edit shows no glyph on those slots)
CPU_BUTTONS = {0x201: 'Y', 0x202: 'R', 0x203: 'R', 9: 'B', 10: 'B'}
MOVE_FLAGS = {0x1000: 'Signature', 0x2000: 'Finisher', 0x4000: 'Voice 1', 0x8000: 'Voice 2'}

_prog = None
_ui = None


def prog():
    global _prog
    if _prog is None:
        _prog = (paths.EXTRACTED / '1ST_READ.BIN').read_bytes()
    return _prog


def u32(a):
    return struct.unpack_from('<I', prog(), a - BASE)[0]


def ui(a, names='real'):
    global _ui
    if _ui is None:
        with open(paths.TEXT / 'ui.csv', encoding='utf-8', newline='') as f:
            _ui = {int(r['ram'], 16): r['english']
                   for r in csv.DictReader(ln for ln in f if not ln.startswith('#'))}
    if a not in _ui:
        return None
    return fpdtext.resolve(_ui[a], names) if '<' in _ui[a] else _ui[a]


def promotions(names='real'):
    with open(paths.TEXT / 'fixed.csv', encoding='utf-8', newline='') as f:
        fixed = {r['offset']: r['english'] for r in csv.DictReader(ln for ln in f if not ln.startswith('#'))}
    return [fpdtext.resolve(fixed[f'0x{0x1188D8 + k * 26:x}'], names) for k in range(18)]


def skill_items(names='real'):
    """[(label, kind, record offset, lo, hi, choices or None)] in Skill Edit order."""
    out = []
    for k in range(30):
        t, _, lo, hi, ch, _, lab, val = struct.unpack_from('<HHHHIIII', prog(), SKILL_DESC - BASE + 24 * k)
        choices = [ui(u32(ch + 4 * j), names) for j in range(hi + 1)] if ch and (t & 15) in (1, 4) else None
        out.append((ui(lab, names), t & 15, val - EDIT_BUF, lo, hi, choices))
    return out


def slot_labels():
    """78 Move Edit labels by record slot, e.g. 'Grapple A+Up'; and the Move Edit row of each slot."""
    p = prog()
    order = list(p[SLOT_ORDER - BASE:SLOT_ORDER - BASE + 78])
    labels, row_of = [None] * 78, [None] * 78
    for row, slot in enumerate(order):
        _, i1, _, i2, _ = struct.unpack_from('<5h', p, SLOT_ICONS - BASE + 10 * row)
        btn = '+'.join(ICONS[i] for i in (i1, i2) if i >= 0)
        BUTTONS[slot] = btn
        labels[slot] = (ui(u32(SLOT_LABELS + 4 * slot)) + (' ' + btn if btn else ''))
        row_of[slot] = row
    return labels, row_of


def cpu_tables(names='real'):
    """[(situation, [(condition, record offset, [action code...], [action label...])])]."""
    labels, _ = slot_labels()
    out = []
    for s in range(20):
        lab, conds, n, _, _ = struct.unpack_from('<IIBBH', prog(), CPU_SITUATIONS - BASE + 12 * s)
        cl = []
        for c in range(n):
            clab, acts, na, data = struct.unpack_from('<IIII', prog(), conds - BASE + 16 * c)
            codes, alabs = [], []
            for a in range(na):
                alab, code = struct.unpack_from('<II', prog(), acts - BASE + 8 * a)
                codes.append(code)
                lab_ = ui(alab, names)          # CPU Logic shows its own label + the slot's buttons
                btn = CPU_BUTTONS.get(code) or (BUTTONS[code] if code < 0x100 else '')
                alabs.append(lab_ + (' ' + btn if btn else ''))
            cl.append((ui(clab, names), data - EDIT_BUF, codes, alabs))
        out.append((ui(lab, names), cl))
    return out


def _voice(v):
    for k in range(11):
        lo, hi = struct.unpack_from('<HH', prog(), VOICE_RANGES - BASE + 4 * k)
        if lo <= v <= hi:
            return ui(u32(0x8C12DCFC + 4 * k)), v - lo + 1
    return None, None


def profile(rec, move_name, names='real'):
    """The record as a dict of English values (labels as the game shows them)."""
    assert len(rec) == REC
    p = {}
    promos = promotions(names)
    skill = {}
    for label, kind, off, lo, hi, choices in skill_items(names):
        v = rec[off]
        if label == 'Promotion':
            skill[label] = promos[v] if v < len(promos) else v
        elif kind == 1:                      # list (Class, Origin, ..., Theme)
            skill[label] = str(v + 1) if label == 'Theme' else choices[v]
        elif kind == 2:                      # number
            skill[label] = v
        elif kind == 3:                      # year
            skill[label] = 'Unknown' if v == 0xFF else 1900 + v
        elif kind in (4, 5):                 # voice: u16 sample id, tone = its range
            tone, typ = _voice(struct.unpack_from('<H', rec, off)[0])
            skill[label] = tone if kind == 4 else typ
    p['skill'] = skill
    p['height_cm'], p['weight_kg'] = rec[0x3E], rec[0x3F]
    p['birthday'] = 'Unknown' if rec[0x41] == 0xFF else f'{1900 + rec[0x41]}/{rec[0x42]}/{rec[0x43]}'
    labs = [ui(u32(PARAM_LABELS + 4 * k), names) for k in range(22)]
    p['params'] = {labs[k]: rec[0x5D + k] - 2 for k in range(22)}           # stored 3..12 = 1..10
    p['appearance'] = {'Stance': ui(u32(STANCES + 4 * rec[0x5A])), 'Size': SIZES[rec[0x5B]]}
    labels, row_of = slot_labels()
    slots = struct.unpack_from('<78H', rec, 0x74)
    moves = []
    for slot in sorted(range(78), key=lambda s: row_of[s]):        # Move Edit order
        v = slots[slot]
        moves.append({'slot': slot, 'row': row_of[slot], 'label': labels[slot], 'id': v & 0xFFF,
                      'move': move_name(v & 0xFFF),
                      'flags': [n for b, n in MOVE_FLAGS.items() if v & b]})
    p['moves'] = moves
    p['finisher'] = next((m['move'] for m in moves if 'Finisher' in m['flags']), None)
    p['signature'] = [m['move'] for m in moves if 'Signature' in m['flags']]
    style = rec[0x45]
    logic = []
    for sit, conds in cpu_tables(names):
        cl = []
        for cond, off, codes, alabs in conds:
            n = len(codes)
            cum = list(rec[off:off + n - 1]) + [100]
            pct = [cum[0]] + [cum[i] - cum[i - 1] for i in range(1, n)]
            acts = []
            for code, lab, pc in zip(codes, alabs, pct):
                if code < 0x100:
                    detail = move_name(slots[code] & 0xFFF)
                elif code in (0x201, 0x202, 0x203):
                    detail = ui(u32(STYLE_ACTIONS + 12 * style + 4 * (code - 0x201)), names)
                else:
                    detail = None
                acts.append({'action': lab, 'move': detail, 'pct': pc})
            cl.append({'condition': cond, 'actions': acts})
        logic.append({'situation': sit, 'conditions': cl})
    p['cpu_logic'] = logic
    return p


def _load():
    s = sbl.Sbl((paths.EXTRACTED / 'SBL.BIN').read_bytes())
    e1, e2 = lzss.decompress(s.get(1)), lzss.decompress(s.get(2))
    names, table = fpdtext.move_names(e1)
    off2idx = {o: k for k, o, _ in names}
    with open(paths.TEXT / 'moves.csv', encoding='utf-8', newline='') as f:
        en = {int(r['index']): r['english'] for r in csv.DictReader(ln for ln in f if not ln.startswith('#'))}

    def move_name(i):
        e = en.get(off2idx.get(table[i])) if i < len(table) else None
        return fpdtext.resolve(e, 'real') if e and '<' in e else e
    with open(paths.TEXT / 'wrestlers.csv', encoding='utf-8', newline='') as f:
        roster = {int(r['idx']): r for r in csv.DictReader(ln for ln in f if not ln.startswith('#'))}
    return e2, move_name, roster


def show(k, e2, move_name, roster):
    r = roster[k]
    p = profile(e2[k * REC:(k + 1) * REC], move_name)
    print(f"#{k} {fpdtext._full(r, 'en_')} - \"{r['en_nick']}\"")
    for a, v in p['skill'].items():
        print(f'  {a}: {v}')
    print('  Appearance:', p['appearance'])
    print('  Params:', ', '.join(f'{a} {v}' for a, v in p['params'].items()))
    print('  Finisher:', p['finisher'], '| Signature:', ', '.join(p['signature']))
    for m in p['moves']:
        print(f"  {m['row'] + 1:2d} {m['label']:<22} {m['move'] or '-'}{' [' + ', '.join(m['flags']) + ']' if m['flags'] else ''}")
    for s in p['cpu_logic']:
        for c in s['conditions']:
            acts = '; '.join(f"{a['action']}{' (' + a['move'] + ')' if a['move'] else ''} {a['pct']}%" for a in c['actions'])
            print(f"  [{s['situation']} / {c['condition']}] {acts}")


def main(argv=None):
    argv = paths.configure(sys.argv[1:] if argv is None else argv)
    e2, move_name, roster = _load()
    want = argv or ['Choshu']
    for w in want:
        ks = [int(w)] if w.isdigit() else [k for k, r in roster.items()
                                             if w.lower() in fpdtext._full(r, 'en_').lower()]
        if not ks:
            sys.exit(f'no wrestler matches {w!r} (English names in translation/text/wrestlers.csv)')
        for k in ks:
            show(k, e2, move_name, roster)
    return 0


if __name__ == '__main__':
    sys.exit(main())
