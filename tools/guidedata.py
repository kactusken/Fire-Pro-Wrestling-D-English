#!/usr/bin/env python3
"""The guide's data block (docs/guide/index.html): roster, moves and the All Unlocked extras.

  python3 tools/guidedata.py [--check]

Reads the original's tables (extracted/SBL.BIN entries 1 and 2, 1ST_READ.BIN's promotion names)
with the English of translation/text/ - wrestlers.csv, moves.csv, fixed.csv, ui.csv - so the
page always shows the patch's names, in both name versions (real, parody). The All Unlocked
extras (the downloadable moves and the downloadable wrestlers) come from the memory card images in
rom/dlc/ (tools/dlc.py) with their English (dlc_moves.csv, dlc_roster.csv, dlc.ROSTER_FIXES).

Each wrestler (and each downloadable wrestler) also gets a full profile from tools/fprecord.py: Skill
and Param Edit values, the 78 move slots in Move Edit order with the finisher and signature
marks, and the CPU Logic percentages. Record layout used (docs/TECHNICAL.md): height +0x3E (cm), weight +0x3F (kg), origin +0x40,
year-1900 +0x41, month +0x42, day +0x43, promotion +0x44, style +0x45, critical +0x54, skill
+0x5C, 78 move slots u16 at +0x74 (bits 0-11 move id, bit 13 = the finisher). The choice lists
for origin/style/critical/skill are the Skill Edit lists (descriptors before 0x8C12DF80).
The move categories are Move Edit's own lists (MOVE_LISTS, SLOT_LIST; docs/TECHNICAL.md "Move Edit
lists"): each move id sits in one list, and a slot's list may also offer a lighter one.
"""
import argparse
import csv
import struct
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpdtext  # noqa: E402
import fprecord  # noqa: E402
import lzss  # noqa: E402
import pagedata  # noqa: E402
import paths  # noqa: E402
import sbl  # noqa: E402

BASE = 0x8C010000
REC = 504
SKILL_ITEMS = {'origin': -18, 'style': -17, 'critical': -15, 'skill': -14}   # descriptor index from Theme
THEME_DESC = 0x8C12DF80
PROMO_NAMES = (0x1188D8, 26, 18)          # file offset, stride, count (fixed.csv rows)
VERSIONS = ('real', 'parody')
MOVE_LISTS = (0x8C12EB8C, 43)             # (u32 pointer to u16 move ids, u16 count, u16 also-offered list or 0xFFFF)
SLOT_LIST = 0x8C12ECE4                    # 78 bytes by record slot: the list Move Edit offers there
MOVE_BLOCK = 0x8C1346C4                   # u16 by move id: its first block in SBL entry 150
MOVE_DATA = 150                           # SBL entry: (offset, size) pairs, then one 'GS' block per move
GS_TYPES = 0x1A                           # in a GS block: main attack type << 4 | sub attack type
DL_GS = 0x34                              # a downloadable move: u16 list, u16 slot, name, then its GS block
# The lists' names in the guide, by list index (what the moves in each list are)
ATTACK_TYPES = ['Punch', 'Kick', 'Throw', 'Lock', 'Choke', 'Power', 'Agility', 'Strength', 'Atk Tech', 'Rough', 'MMA Atk']   # ui.csv 0xb43e0..
LIST_TITLES = [
    'Standing strikes: weak', 'Standing strikes: medium', 'Standing strikes: strong', 'Running attacks',
    'Counters to a running opponent', 'Diagonal run', 'Dives to the outside', 'From the apron to the outside',
    'From the apron into the ring', 'Off the top rope', 'Grapples: weak', 'Grapples: medium', 'Grapples: strong',
    'From behind: weak', 'From behind: medium', 'From behind: strong', 'Reversals from behind (X)',
    'Reversals from behind (A)', 'Downed opponent: face up, at the head', 'Downed opponent: face up, at the legs',
    'Downed opponent: face down, at the head', 'Downed opponent: face down, at the legs',
    'Running attacks on a downed opponent', 'Opponent in the corner', 'Taunts', 'Double-team: in front',
    'Triple-team: in front', 'Double-team: from behind', 'Triple-team: from behind', 'Double-team: in the corner',
    'Triple-team: in the corner', 'Mount: attacks', 'Mount: reversals', 'Front headlock: attacks',
    'Front headlock: reversals', 'Back mount: attacks', 'Back mount: reversals',
    'Corner dives: standing opponent', 'Corner dives: downed opponent', 'Apron grapples: from inside the ring',
    'Apron grapples: from the apron', 'Top-rope reversals: in front', 'Top-rope reversals: from behind']


def _rows(name):
    with open(paths.TEXT / name, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(ln for ln in f if not ln.startswith('#')))


def _ui():
    return {int(r['ram'], 16): r['english'] for r in _rows('ui.csv')}


def _both(text, tokens, where):
    return [fpdtext.resolve(text, v, where, tokens) for v in VERSIONS]


def choice_lists(prog, ui):
    out = {}
    for key, k in SKILL_ITEMS.items():
        _, _, lo, hi, ch, _, _, _ = struct.unpack_from('<HHHHIIII', prog, THEME_DESC - BASE + 24 * k)
        out[key] = [ui[struct.unpack_from('<I', prog, ch - BASE + 4 * j)[0]] for j in range(lo, hi + 1)]
    return out


def promotions(tokens):
    fixed = {r['offset']: r['english'] for r in _rows('fixed.csv')}
    off, stride, n = PROMO_NAMES
    return [_both(fixed[f'0x{off + k * stride:x}'], tokens, f'promotion {k}') for k in range(n)]


def move_lookup(entry1, tokens):
    """move id -> [real, parody] English name, and [jp] Japanese."""
    names, table = fpdtext.move_names(entry1)
    off2idx = {o: k for k, o, _ in names}
    en = {int(r['index']): r for r in _rows('moves.csv')}

    def name(i):
        r = en.get(off2idx.get(table[i])) if i < len(table) else None
        return (_both(r['english'], tokens, f'move {i}'), r['japanese']) if r else (None, None)
    return name


def move_categories(prog, move_index, slot_label, data, dl, dl_base):
    """Move Edit's lists: [{t: title, s: [slot labels], inc: list or -1, m: [move name index],
    ty: [main << 4 | sub attack type, per move]}], the downloadable moves (name index >= dl_base)
    at the end of their list as in the game; and the list of each Move Edit row."""
    table, n = MOVE_LISTS
    by_slot = prog[SLOT_LIST - BASE:SLOT_LIST - BASE + 78]
    first = struct.unpack_from('<1600H', prog, MOVE_BLOCK - BASE)

    def types(i):
        off, size = struct.unpack_from('<II', data, 8 * first[i])
        assert data[off:off + 2] == b'GS', f'move {i}: no GS block'
        return data[off + GS_TYPES]
    out = []
    for k in range(n):
        ptr, cnt = struct.unpack_from('<II', prog, table - BASE + 8 * k)
        ids = struct.unpack_from(f'<{cnt & 0xFFFF}H', prog, ptr - BASE)
        names, ty = [], []
        for i in ids:
            m = move_index(i) if i else -1
            if m >= 0 and m not in names:
                names.append(m)
                ty.append(types(i))
        for j, d in enumerate(dl):
            if d['list'] == k:
                names.append(dl_base + j)
                ty.append(d['ty'])
        out.append({'t': LIST_TITLES[k], 's': [slot_label[sl] for sl in range(78) if by_slot[sl] == k],
                    'inc': -1 if cnt >> 16 == 0xFFFF else cnt >> 16, 'm': names, 'ty': ty, 'k': k})
    merged = []                                 # the same moves twice (Back Rev X and A): one category
    for c in out:
        if merged and merged[-1]['m'] == c['m'] and merged[-1]['inc'] == c['inc'] and merged[-1]['t'].startswith('Reversals'):
            merged[-1]['s'] += c['s']
            merged[-1]['t'] = merged[-1]['t'].split(' (')[0]
        else:
            merged.append(c)
    at = {c['k']: i for i, c in enumerate(merged)}
    for c in merged:
        c['inc'] = at.get(c['inc'], -1)
        c['k'] = at[c['k']]
    order = fprecord.slot_labels()[1]                           # Move Edit row of each record slot
    rows = [0] * 78
    for sl in range(78):
        rows[order[sl]] = at[by_slot[sl]]
    return merged, rows


def roster(entry2, move, promos, lists, tokens):
    by_idx = {int(r['idx']): r for r in _rows('wrestlers.csv')}
    out = []
    for k in range(len(entry2) // REC):
        rec = entry2[k * REC:(k + 1) * REC]
        r = by_idx[k]
        full = [fpdtext._full(r, 'en_'), fpdtext._full(r, 'parody_')]
        short = [r['en_name1'], r['parody_name1']]
        nick = [r['en_nick'], r.get('parody_nick') or r['en_nick']]
        slots = struct.unpack_from('<78H', rec, 0x74)
        fin = next((s & 0xFFF for s in slots if s & 0x2000), None)
        fin_name = move(fin)[0] if fin is not None else None
        out.append({
            'n': [fpdtext.resolve(x, v, f'wrestler {k}', tokens) for x, v in zip(full, VERSIONS)],
            's': [fpdtext.resolve(x, v, f'wrestler {k}', tokens) for x, v in zip(short, VERSIONS)],
            'k': [fpdtext.resolve(x, v, f'wrestler {k}', tokens) for x, v in zip(nick, VERSIONS)],
            'p': rec[0x44], 'h': rec[0x3E], 'w': rec[0x3F],
            'b': 'Unknown' if rec[0x41] == 0xFF else f'{1900 + rec[0x41]}/{rec[0x42]}/{rec[0x43]}',
            'o': lists['origin'][rec[0x40]], 'st': _both(lists['style'][rec[0x45]], tokens, 'style'),
            'cr': lists['critical'][rec[0x54]], 'sk': lists['skill'][rec[0x5C]],
            'f': fin_name or ['', ''],
        })
    return out


def move_names_all(tokens):
    """[[real, parody], japanese] by name index (the index moves.csv and the move slots use)."""
    rows = {int(r['index']): r for r in _rows('moves.csv')}
    return [[_both(rows[k]['english'], tokens, f'moves.csv {k}'), rows[k]['japanese']] if k in rows else [['', ''], '']
            for k in range(max(rows) + 1)]


def extras(promos):
    """The All Unlocked extras: [{slot, name, kind}], [{name, nick, promo, finisher}]."""
    import dlc
    moves_, roster_ = dlc.sources()
    eng = dlc.english_names()
    dl = []
    for slot in sorted(moves_):
        raw = moves_[slot][8:0x34].split(b'\0')[0].decode('cp932').replace('\u3002', '. ')   # full-width period
        nm = eng.get(slot) or ' '.join(unicodedata.normalize('NFKC', raw).split())
        p = moves_[slot]
        dl.append({'n': slot, 'e': nm, 'src': 'official' if slot <= 56 else 'FPZ',
                   'list': struct.unpack_from('<H', p, 0)[0], 'ty': p[DL_GS + GS_TYPES]})
    ros = []
    if roster_:
        fixed = dlc.roster_fixed(roster_)
        fins = {int(r['index']): r['english'] for r in _rows('dlc_roster.csv')}
        for i in range(50):
            r = fixed[50 + i * dlc.RECORD:50 + (i + 1) * dlc.RECORD]
            txt = lambda a, b: unicodedata.normalize('NFKC', r[a:b].split(b'\0')[0].decode('cp932')).strip()
            n1, n2 = txt(2, 0x10), txt(0x10, 0x24)
            full = ' '.join(x for x in ([n2, n1] if r[1] & 0x80 else [n1, n2]) if x)
            ros.append({'n': full, 'k': txt(0x24, 0x3E), 'p': r[0x44], 'f': fins.get(i, txt(0x24C, 0x276))})
    return dl, ros


def full_profile(rec, move_index):
    """{sk, pa, mv, ai} for the page, in both name versions where they differ (move_index(id) -> mn index)."""
    pr = {v: fprecord.profile(rec[:fprecord.REC], move_index, names=v) for v in VERSIONS}
    r, q = pr['real'], pr['parody']
    val = lambda a, b: a if a == b else [a, b]
    keep = [k for k in r['skill'] if k not in ('Height', 'Weight', 'Year', 'Month', 'Day', 'Promotion')]
    sk = [val(r['skill'][k], q['skill'][k]) for k in keep] + list(r['appearance'].values())
    mv = []
    for m in r['moves']:
        i = m['move']
        mv.append(-1 if i is None or i < 0 else i * 4 + ('Finisher' in m['flags']) * 2 + ('Signature' in m['flags']))
    ai = []                                     # flat, in the order of the shared shape: [pct, detail]
    for sit, sq in zip(r['cpu_logic'], q['cpu_logic']):
        for c, cq in zip(sit['conditions'], sq['conditions']):
            for a, aq in zip(c['actions'], cq['actions']):
                d = a['move'] if isinstance(a['move'], int) else val(a['move'], aq['move']) if a['move'] else -1
                ai.append(a['pct'] if d == -1 else [a['pct'], d])
    shape = {'sk': keep + list(r['appearance']), 'pa': list(r['params']),
             'ai': [{'s': x['situation'], 'c': [{'n': c['condition'], 'a': [a['action'] for a in c['actions']]}
                                               for c in x['conditions']]} for x in r['cpu_logic']]}
    return {'sk': sk, 'pa': list(r['params'].values()), 'mv': mv, 'ai': ai}, shape


def build():
    prog = (paths.EXTRACTED / '1ST_READ.BIN').read_bytes()
    s = sbl.Sbl((paths.EXTRACTED / 'SBL.BIN').read_bytes())
    e1, e2 = lzss.decompress(s.get(1)), lzss.decompress(s.get(2))
    tokens = fpdtext.name_tokens()
    lists = choice_lists(prog, _ui())
    promos = promotions(tokens)
    move = move_lookup(e1, tokens)
    dl, dl_roster = extras(promos)
    ros = roster(e2, move, promos, lists, tokens)
    names, table = fpdtext.move_names(e1)
    off2idx = {o: k for k, o, _ in names}
    mn = move_names_all(tokens)
    none = {k for k, (en, jp) in enumerate(mn) if jp == '使わない'}
    dl_base = len(mn)
    for m in dl:
        mn.append([[m['e'], m['e']], 'W%02d' % m['n']])

    def move_index(i):
        if i & 0x800:                                    # a downloadable move: its slot number
            return dl_base + (i & 0x7FF) if (i & 0x7FF) < len(dl) else -1
        k = off2idx.get(table[i]) if i < len(table) else None
        return -1 if k is None or k in none else k
    shape = None
    for k, r in enumerate(ros):
        r['pr'], shape = full_profile(e2[k * REC:(k + 1) * REC], move_index)
    import dlc
    _, roster_ = dlc.sources()
    if roster_:
        fixed = dlc.roster_english(dlc.roster_fixed(roster_), 'real')
        for i, r in enumerate(dl_roster):
            r['pr'], _ = full_profile(fixed[50 + i * dlc.RECORD:50 + i * dlc.RECORD + REC], move_index)
            rec = fixed[50 + i * dlc.RECORD:50 + (i + 1) * dlc.RECORD]
            r.update({'h': rec[0x3E], 'w': rec[0x3F], 'b': 'Unknown' if rec[0x41] == 0xFF else f'{1900 + rec[0x41]}/{rec[0x42]}/{rec[0x43]}',
                      'o': lists['origin'][rec[0x40]] if rec[0x40] < len(lists['origin']) else ''})
    mcat, mcat_rows = move_categories(prog, move_index, fprecord.slot_labels()[0], lzss.decompress(s.get(MOVE_DATA)), dl, dl_base)
    entries = [{'id': f'w{k}', 'name': r['n'][0] if r['n'][0] == r['n'][1] else f'{r["n"][0]} / {r["n"][1]}',
                'group': 'Wrestler', 'text': f'{promos[r["p"]][0]} - finisher {r["f"][0]}'}
               for k, r in enumerate(ros)]
    prose = {'ring1': '<VIEW JAPAN>', 'ring2': '<OLIVE JAPAN>', 'ring3': '<SUPER NOVA>', 'ref0': '<Tottori>',
             'bgm0': '<Musashi> Dynamic Ver', 'panther': '<Panther*>'}     # names in the guide's text
    return {
        'names': {k: _both(v, tokens, f'names {k}') for k, v in prose.items()},
        'entries': entries,
        'promotions': promos,
        'roster': ros,
        'mn': mn,
        'slots': [m['label'] for m in fprecord.profile(e2[:REC], lambda i: 0)['moves']],
        'mcat': mcat,
        'mcatRow': mcat_rows,
        'dlBase': dl_base,
        'atk': [fpdtext.ui_text(prog, a) if hasattr(fpdtext, 'ui_text') else a for a in ATTACK_TYPES],
        'shape': shape,
        'dlMoves': dl,
        'dlRoster': dl_roster,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='only check that the page is up to date')
    args = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    page = paths.DOCS / 'guide' / 'index.html'
    if pagedata.write(page, build(), args.check) and args.check:
        print(f'{paths.show(page)}: up to date')
    return 0


if __name__ == '__main__':
    sys.exit(main())
