#!/usr/bin/env python3
"""Fire Pro Wrestling D's text: dump it into translation/text/, write the English back (build steps).

  fpdtext.py dump        (re)write ui.csv, fixed.csv, wrestlers.csv, moves.csv (English kept)
  fpdtext.py check       every build step on the original's data: no English = identical bytes,
                         and the English fits (the same checks the build makes)

Where the text is (verified 2026-10-27, docs/TECHNICAL.md "Text"):

- ui.csv: 1ST_READ.BIN 0xB2800-0xBBC00 holds the program's strings (menus, help lines, messages,
  match text), Shift-JIS with half-width katakana, NUL-terminated, each start reached by 32-bit
  pointers (code literal pools and pointer tables). Every string the table lists has pointers, so
  the build repacks them: English that fits stays in its slot, longer English goes into the room
  shorter strings leave, and every pointer is updated. Left out: pure-ASCII strings (debug, file
  names), the name-entry keyboard rows (0xB762C-0xB97EC), the save-file labels (fixed.csv).
- fixed.csv: strings written in place, never moved (no pointers, or copied into fixed fields):
  save-file labels (VMU 16 / file manager 32 bytes), referees, the built-in names in 1ST_READ.
- wrestlers.csv: the roster - 220 records of 504 bytes, SBL.BIN entry 2 (LZSS) and the same
  records again in entry 1 at +0x14 (both written). Fields: +1 order/separator flags, +2 name1
  (14 bytes), +0x10 name2 (20), +0x24 nickname (26).
- moves.csv: the move names - the last section of SBL entry 1 (from header word 3 * 4): 1536
  u16 offsets (move id -> name, from the section start), then the names, NUL-terminated. The build
  rewrites the names and the offsets and the header's end word.

English is printable ASCII: the font draws every character but '#' (measured, FONT below). The
game draws text at about 24 px a kanji, 12 a half-width kana; English ~14 px a lowercase letter,
~18 a capital, 16 a space - width() estimates it.
"""
import csv
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lzss  # noqa: E402
import paths  # noqa: E402
import sbl  # noqa: E402

BASE = 0x8C010000
CODEC = 'cp932'
UI_LO, UI_HI = 0xB2800, 0xBBC00
KEYBOARD = (0xB762C, 0xB97EC)
# save-file labels: offset -> hard byte limit (VMU display 16, BIOS file manager 32)
VMU = {0xB36CC: 16, 0xB36D8: 32, 0xB36F4: 16, 0xB3700: 32, 0xB3720: 16, 0xB372C: 32, 0xB3748: 16,
       0xB3754: 32, 0xB3774: 16, 0xB3780: 32, 0xB37A0: 16, 0xB37A8: 32, 0xB37C4: 16, 0xB37D0: 32}
REFEREES = (0x11920C, 0x9E, 8, 2, 18)          # first record, stride, count, name offset, field
FIXED_MORE = [(0x11D672, 14, 'built-in edit wrestler: name1'), (0x11D680, 20, 'built-in edit wrestler: name2'),
              (0x11D694, 26, 'built-in edit wrestler: nickname'), (0x11D8BC, 18, 'ヴァイル record (unknown use)'),
              (0x11D8F8, 18, 'ヴァイル record, referee-like (unknown use)'),
              (0x130A9C, 26, 'game title in a save header (unknown use)'),
              # ring names already in English in the original (Ring setting); real names by token
              (0xB2974, 12, 'ring name'), (0xB2980, 12, 'ring name'), (0xB298C, 16, 'ring name'),
              (0xB29B8, 12, 'ring name'), (0xB29E8, 8, 'ring name'), (0xB2A24, 4, 'ring name')]
PROMOTIONS = ((0x1188D8, 0x1A, 18, 26, 'promotion name (header box ~11 letters, uppercase like the originals)'),
              (0x118AAC, 0x0E, 18, 14, 'promotion short name (3-6 letters)'))
ROSTER_ENTRIES = ((2, 0), (1, 0x14))            # (SBL entry, offset of record 0 in its data)
ROSTER = (504, 220)                             # stride, count
FIELDS = (('name1', 2, 14), ('name2', 0x10, 20), ('nick', 0x24, 26))
MOVE_ENTRY = 1

# advance in pixels per character at the menu size (measured in game, 2026-10-27)
FONT = {'!': 20.9, '"': 11.6, '$': 21.6, '%': 22.9, '&': 22.9, "'": 11.6, '(': 10.9, ')': 10.9, '*': 21.9,
        '+': 22.6, ',': 15.6, '-': 22.2, '.': 15.2, '/': 23.2, '0': 18.6, '1': 16.9, '2': 18.2, '3': 18.2,
        '4': 18.6, '5': 18.2, '6': 18.6, '7': 18.2, '8': 18.6, '9': 18.6, ':': 10.2, ';': 10.2, '<': 22.2,
        '=': 22.2, '>': 22.6, '?': 21.9, '@': 22.2, 'A': 19.6, 'B': 18.6, 'C': 17.6, 'D': 17.6, 'E': 17.6,
        'F': 16.6, 'G': 16.6, 'H': 18.6, 'I': 7.0, 'J': 16.6, 'K': 17.6, 'L': 15.6, 'M': 20.6, 'N': 17.6,
        'O': 17.6, 'P': 17.6, 'Q': 17.6, 'R': 17.6, 'S': 15.6, 'T': 17.6, 'U': 17.6, 'V': 18.6, 'W': 22.0,
        'X': 19.6, 'Y': 17.6, 'Z': 16.6, '[': 11.2, '\\': 22.6, ']': 10.9, '^': 10.2, '`': 11.6, 'a': 14.6,
        'b': 14.6, 'c': 13.6, 'd': 15.6, 'e': 14.6, 'f': 13.6, 'g': 15.6, 'h': 15.6, 'i': 6.6, 'j': 10.6,
        'k': 16.6, 'l': 6.6, 'm': 21.6, 'n': 17.6, 'o': 15.6, 'p': 16.6, 'q': 16.6, 'r': 14.6, 's': 14.6,
        't': 13.6, 'u': 14.6, 'v': 16.6, 'w': 20.6, 'x': 15.6, 'y': 16.6, 'z': 13.6, '{': 10.2, '|': 20.2,
        '}': 10.2, '~': 23.9, ' ': 16.0}


def width(text):
    """Estimated pixel width at the menu size (Japanese: 24 a full-width character, 12 a half)."""
    w = 0.0
    for c in text:
        if c in FONT:
            w += FONT[c]
        elif '｡' <= c <= 'ﾟ':
            w += 12
        elif c == '\n':
            continue
        else:
            w += 24
    return round(w)


SYMBOLS = '○×△▲□■●★☆・→←↑↓％\u3000'      # full-width symbols the font has, allowed in English (Shift-JIS)


def bad_chars(text):
    """Characters English may not use: anything but printable ASCII, \\n, SYMBOLS and #xN codes
    (an HTML page, the upload form, goes to the browser: its tags are left alone)."""
    if text.startswith('<HTML>'):
        text = re.sub(r'<[^<>]*>', '', text)
    return sorted({c for c in re.sub(r'#x\d+', '', text)
                   if not (0x20 <= ord(c) < 0x7F or c == '\n' or c in SYMBOLS) or c == '#'})


def encode(text, where=''):
    """English (printable ASCII, \\n, SYMBOLS, #xN codes) -> bytes; anything else stops the build."""
    bad = bad_chars(text)
    if bad:
        sys.exit(f'{where}: {text!r}: {"".join(bad)!r} - the font has no such character '
                 '(printable ASCII, no #, and ' + SYMBOLS + ')')
    return text.encode(CODEC)


def _csv_rows(name):
    p = paths.TEXT / name
    if not p.exists():
        return []
    with open(p, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(ln for ln in f if not ln.startswith('#')))


def _write_csv(name, header, fields, rows):
    p = paths.TEXT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='') as f:
        for h in header:
            f.write(f'# {h}\n')
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    print(f'{paths.show(p)}: {len(rows)} rows')


# ---------------------------------------------------------------- 1ST_READ strings

def pointer_map(d):
    """{file offset of a target: [file offsets of aligned words pointing at it]}."""
    out = {}
    for i in range(0, len(d) - 3, 4):
        v = struct.unpack_from('<I', d, i)[0] - BASE
        if UI_LO <= v < UI_HI:
            out.setdefault(v, []).append(i)
    return out


def _candidates(d, ptrs):
    """[(offset, slot, raw, text)] of every pointer target in the region that reads as a string up
    to its NUL. A target need not follow a NUL (a string can sit right after other data - the Edit
    Army 決定 at 0xBACF0 does). The slot runs to the next nonzero byte after the NUL, or the next
    target, whichever comes first."""
    starts = sorted(o for o in ptrs if UI_LO <= o < UI_HI and d[o] != 0)
    out = []
    for k, i in enumerate(starts):
        e = d.index(b'\0', i)
        if k + 1 < len(starts) and starts[k + 1] <= e:
            continue                                # another target inside: not a plain string
        raw = d[i:e]
        try:
            text = raw.decode(CODEC)
        except UnicodeDecodeError:
            continue
        if not all(c.isprintable() or c in '\n\u3000' for c in text):
            continue
        if KEYBOARD[0] <= i < KEYBOARD[1] or i in VMU:
            continue
        if i > 0 and d[i - 1] != 0 and not any(ord(c) > 0x7F for c in text):
            continue                                # ASCII glued to data: leave it alone
        j = e
        while j < UI_HI and d[j] == 0:
            j += 1
        if k + 1 < len(starts):
            j = min(j, starts[k + 1])
        out.append((i, j - i, raw, text))
    return out


def ui_strings(d, ptrs=None):
    """[(offset, slot bytes, raw bytes, text, pointers)] of the pool strings (ui.csv)."""
    ptrs = pointer_map(d) if ptrs is None else ptrs
    return [(i, slot, raw, text, ptrs[i]) for i, slot, raw, text in _candidates(d, ptrs)
            if any(ord(c) > 0x7F for c in text)]


def pool_slots(d, ptrs=None):
    """Every pointer-referenced string in the region (any content, not only ui.csv's): the space
    the build may pack strings into. [(offset, slot)]"""
    ptrs = pointer_map(d) if ptrs is None else ptrs
    return [(i, slot) for i, slot, raw, text in _candidates(d, ptrs)]


def fixed_strings(d):
    """[(offset, room in bytes incl. NUL, text, note)] of in-place strings (fixed.csv)."""
    out = []
    for o, lim in VMU.items():
        e = d.index(b'\0', o)
        j = e
        while d[j] == 0:
            j += 1
        lim = min(lim, j - o)                     # the label's own slot may be smaller
        out.append((o, lim, d[o:e].decode(CODEC), 'save-file label (VMU display / BIOS file manager)'))
    first, stride, count, at, size = REFEREES
    for k in range(count):
        o = first + k * stride + at
        out.append((o, size, d[o:o + size].split(b'\0')[0].decode(CODEC), f'referee {k}'))
    for first, stride, count, size, note in PROMOTIONS:
        for k in range(count):
            o = first + k * stride
            out.append((o, size, d[o:o + size].split(b'\0')[0].decode(CODEC), f'{note} {k}'))
    for o, size, note in FIXED_MORE:
        out.append((o, size, d[o:o + size].split(b'\0')[0].decode(CODEC), note))
    return out


# ---------------------------------------------------------------- SBL text

def roster_records(data, start):
    R, n = ROSTER
    for k in range(n):
        yield k, data[start + k * R:start + (k + 1) * R]


def field(rec, name):
    for f, o, size in FIELDS:
        if f == name:
            return rec[o:o + size].split(b'\0')[0].decode(CODEC)
    raise KeyError(name)


def move_section(data):
    """(section start, section end, table entries, names start) of the move names in entry 1."""
    hdr = struct.unpack_from('<5I', data, 0)
    start, end = hdr[3] * 4, hdr[4] * 4
    return start, end, 1536, start + 1536 * 2


def move_names(data):
    """[(index, offset from section start, text)] in file order, plus the id->offset table."""
    start, end, n, names = move_section(data)
    table = struct.unpack_from(f'<{n}H', data, start)
    out = []
    p = names
    k = 0
    while p < end:
        e = data.index(b'\0', p)
        if e == p and all(b == 0 for b in data[p:end]):
            break
        out.append((k, p - start, data[p:e].decode(CODEC)))
        k += 1
        p = e + 1
    return out, list(table)


# ---------------------------------------------------------------- dump

def dump():
    d = (paths.EXTRACTED / '1ST_READ.BIN').read_bytes()
    s = sbl.Sbl((paths.EXTRACTED / 'SBL.BIN').read_bytes())
    ptrs = pointer_map(d)

    old = {r['offset']: r for r in _csv_rows('ui.csv')}
    rows = []
    for o, slot, raw, text, refs in ui_strings(d, ptrs):
        key = f'0x{o:05x}'
        prev = old.get(key, {})
        rows.append({'offset': key, 'ram': f'0x{BASE + o:08x}', 'refs': len(refs), 'max_bytes': slot - 1,
                     'jp_px': width(text), 'japanese': text, 'english': prev.get('english', ''),
                     'notes': prev.get('notes', '')})
    _write_csv('ui.csv', [
        'The program\'s strings (1ST_READ.BIN 0xB2800-0xBBC00): menus, help lines, messages, match text.',
        'refs > 0: the build repacks these strings, so English may be longer than max_bytes (the room in',
        'place) as long as the whole pool fits - keep it about as long as the Japanese. jp_px: the',
        'Japanese width on screen in pixels (24 a kanji); English ~14 a lowercase letter, 18 a capital,',
        '16 a space (tools/fpdtext.py width). Lint warns when the English is much wider.',
        'Keep %d %s %02d ... in order, and \\n (a line break) where the Japanese has one.',
        'Printable ASCII only, no # (the font has none).'],
        ['offset', 'ram', 'refs', 'max_bytes', 'jp_px', 'japanese', 'english', 'notes'], rows)

    old = {r['offset']: r for r in _csv_rows('fixed.csv')}
    rows = []
    for o, lim, text, note in fixed_strings(d):
        key = f'0x{o:05x}'
        prev = old.get(key, {})
        rows.append({'offset': key, 'ram': f'0x{BASE + o:08x}', 'refs': 0, 'max_bytes': lim - 1,
                     'japanese': text, 'english': prev.get('english', ''), 'notes': prev.get('notes') or note})
    _write_csv('fixed.csv', [
        'Strings written in place in 1ST_READ.BIN (fixed fields): max_bytes is a hard limit.',
        'Printable ASCII only, no #.'],
        ['offset', 'ram', 'refs', 'max_bytes', 'japanese', 'english', 'notes'], rows)

    roster = lzss.decompress(s.get(2))
    old = {r['idx']: r for r in _csv_rows('wrestlers.csv')}
    rows = []
    for k, rec in roster_records(roster, 0):
        prev = old.get(str(k), {})
        flags = rec[1]
        rows.append({'idx': k, 'flags': f'0x{flags:02x}', 'name1': field(rec, 'name1'), 'name2': field(rec, 'name2'),
                     'nick': field(rec, 'nick'),
                     'jp_full': full_jp(field(rec, 'name1'), field(rec, 'name2'), flags),
                     **{c: prev.get(c, '') for c in ('en_name1', 'en_name2', 'en_order', 'parody_name1', 'parody_name2',
                                                     'parody_order', 'en_nick', 'parody_nick', 'notes')}})
    _write_csv('wrestlers.csv', [
        'The roster: 220 wrestlers (SBL.BIN entry 2, and again in entry 1). Fields: name1 13 bytes (the short',
        'name the game shows alone), name2 19 bytes, nick 25 bytes. flags: bit 7 = name2 comes first in the',
        'full name, bits 0-1 = the separator (0 a space, 1 "・", 2 "=", 3 none) - verified in game.',
        'Two English versions of every name: en_* the real wrestler (default build), parody_* the game\'s own',
        'name romanized (build.py --names parody); en_nick is used by both. *_order: 1-2 (name1 name2) or',
        '2-1 (name2 name1), joined with a space; empty = 1-2. jp_full: the name as the game shows it.',
        'Nicknames (25 bytes): en_nick in the real build (the real wrestler\'s own nickname), parody_nick',
        'in the parody build (the game\'s nickname translated; empty = en_nick).'],
        ['idx', 'flags', 'name1', 'name2', 'nick', 'jp_full', 'en_name1', 'en_name2', 'en_order', 'parody_name1',
         'parody_name2', 'parody_order', 'en_nick', 'parody_nick', 'notes'], rows)

    data1 = lzss.decompress(s.get(MOVE_ENTRY))
    names, table = move_names(data1)
    used = {}
    start = move_section(data1)[0]
    for mid, off in enumerate(table):
        used.setdefault(off, []).append(mid)
    old = {r['index']: r for r in _csv_rows('moves.csv')}
    rows = []
    for k, off, text in names:
        prev = old.get(str(k), {})
        ids = used.get(off, [])
        rows.append({'index': k, 'ids': ' '.join(str(i) for i in ids[:6]) + (' ...' if len(ids) > 6 else ''),
                     'jp_px': width(text), 'japanese': text, 'english': prev.get('english', ''),
                     'notes': prev.get('notes', '')})
    _write_csv('moves.csv', [
        'Move names (SBL.BIN entry 1, last section): the build repacks the list, any length - but the move',
        'lists on screen are narrow: keep about the Japanese width (jp_px; English ~14 px a lowercase',
        'letter). ids: the move numbers that use the name. Printable ASCII only, no #.'],
        ['index', 'ids', 'jp_px', 'japanese', 'english', 'notes'], rows)


# ---------------------------------------------------------------- name tokens

TOKEN = re.compile(r'<([A-Za-z][^<>%]*)>')
# HTML in the network-mode strings (the upload form, the browser's messages): not name tokens
HTML_TAG = re.compile(r'(?i)/?(html|head|title|body|br|font|b|i|p|hr|form|input|img|select|option|textarea|'
                      r'table|tr|td|th|center|div|a|blink)\b')


def _full(r, pre):
    n1, n2 = r.get(pre + 'name1', ''), r.get(pre + 'name2', '')
    parts = [n2, n1] if (r.get(pre + 'order') or '1-2') == '2-1' else [n1, n2]
    return ' '.join(x for x in parts if x)


def name_tokens():
    """{token: (real, parody)}: every wrestler's parody short and full name (wrestlers.csv), and
    translation/text/name_tokens.csv (token, real, parody - empty parody = the token itself)."""
    out = {}
    for r in _csv_rows('wrestlers.csv'):
        if r.get('parody_name1') and r.get('en_name1'):
            out.setdefault(r['parody_name1'], (r['en_name1'], r['parody_name1']))
            out.setdefault(_full(r, 'parody_'), (_full(r, 'en_'), _full(r, 'parody_')))
    for r in _csv_rows('name_tokens.csv'):
        out[r['token']] = (r['real'], r.get('parody') or r['token'].rstrip('*'))
    return out


def resolve(text, names, where='', tokens=None):
    """`text` with every <Token> replaced by its real (names='real') or parody name."""
    tokens = name_tokens() if tokens is None else tokens

    def sub(m):
        if m.group(1) not in tokens and HTML_TAG.match(m.group(1)):
            return m.group(0)
        if m.group(1) not in tokens:
            sys.exit(f'{where}: unknown name token <{m.group(1)}> (wrestlers.csv parody names, name_tokens.csv)')
        return tokens[m.group(1)][0 if names == 'real' else 1]
    return TOKEN.sub(sub, text)


# ---------------------------------------------------------------- build steps

def english_rows(name, key):
    """{key: english} of the rows of a CSV that have English."""
    return {r[key]: r['english'] for r in _csv_rows(name) if r.get('english')}


def pack_pool(d, english):
    """Repack the 1ST_READ string pool with `english` ({offset: text}); returns the new bytes.
    Strings keep their order; every pointer to a moved string is updated."""
    d = bytearray(d)
    ptrs = pointer_map(d)
    slots = pool_slots(d, ptrs)
    content = []
    for o, slot in slots:
        e = d.index(b'\0', o)
        content.append((o, encode(english[o], f'ui.csv 0x{o:05x}') if o in english else bytes(d[o:e])))
    ranges = []                                    # merged free space: adjacent slots join
    for o, slot in slots:
        if ranges and ranges[-1][1] == o:
            ranges[-1][1] = o + slot
        else:
            ranges.append([o, o + slot])
    # Pointers into zero bytes are empty strings or small buffers the code writes (e.g. the belt
    # screen's values): they stay where they are, zero - packing text over them showed "tmpbuf".
    reserved = []
    for t in ptrs:
        if UI_LO <= t < UI_HI and d[t] == 0:
            e = t
            while e < UI_HI and d[e] == 0:
                e += 1
            reserved.append((t, e))
    for a, b in reserved:
        cut = []
        for lo, hi in ranges:
            if b <= lo or a >= hi:
                cut.append([lo, hi])
                continue
            if lo < a:
                cut.append([lo, a])
            if b < hi:
                cut.append([b, hi])
        ranges = cut
    need = sum(len(c) + 1 for _, c in content)
    room = sum(b - a for a, b in ranges)
    for align in (4, 2, 1):
        placed, ok = {}, True
        ri, pos = 0, ranges[0][0]
        for o, c in content:
            while True:
                pos = (pos + align - 1) // align * align
                if pos + len(c) + 1 <= ranges[ri][1]:
                    break
                ri += 1
                if ri == len(ranges):
                    ok = False
                    break
                pos = ranges[ri][0]
            if not ok:
                break
            placed[o] = pos
            pos += len(c) + 1
        if ok:
            break
    else:
        sys.exit(f'1ST_READ.BIN string pool: the strings need {need} bytes, the pool holds {room} - '
                 f'shorten the English in ui.csv by about {need - room} bytes')
    for a, b in ranges:
        d[a:b] = bytes(b - a)
    for o, c in content:
        n = placed[o]
        d[n:n + len(c)] = c
        for at in ptrs[o]:
            struct.pack_into('<I', d, at, BASE + n)
    return bytes(d), need, room, align


# Code that writes Japanese text byte by byte (no string to translate): (address, original word,
# new word, what). Applied with the text (part of the translation, not an --unlocks group).
# The match time "N分NN秒" (result screen, two copies of the routine): mov #imm,r3 writes each
# byte - 分 (95 AA) becomes "m " and 秒 (95 62) "s" + NUL, so the screen shows "3m 23s".
TEXT_CODE = [
    (0x8C09D45E, 0xE395, 0xE36D, 'result time: 分 byte 1 -> m'),
    (0x8C09D46C, 0xE3AA, 0xE320, 'result time: 分 byte 2 -> space'),
    (0x8C09D4A0, 0xE395, 0xE373, 'result time: 秒 byte 1 -> s'),
    (0x8C09D4AE, 0xE362, 0xE300, 'result time: 秒 byte 2 -> NUL'),
    (0x8C09E9A2, 0xE395, 0xE36D, 'result time (2): 分 byte 1 -> m'),
    (0x8C09E9AE, 0xE3AA, 0xE320, 'result time (2): 分 byte 2 -> space'),
    (0x8C09E9E4, 0xE395, 0xE373, 'result time (2): 秒 byte 1 -> s'),
    (0x8C09E9F2, 0xE362, 0xE300, 'result time (2): 秒 byte 2 -> NUL'),
]


def text_code(d):
    """TEXT_CODE into 1ST_READ.BIN data (bytearray), each checked against the original."""
    for addr, old, new, what in TEXT_CODE:
        o = addr - BASE
        if struct.unpack_from('<H', d, o)[0] != old:
            sys.exit(f'1ST_READ.BIN 0x{addr:08X} ({what}): found {struct.unpack_from("<H", d, o)[0]:04x}, '
                     f'expected {old:04x}')
        struct.pack_into('<H', d, o, new)


# Screens that place button icons at fixed positions after a label sized for the Japanese
# (verified in game 2026-10-28): the build moves the icons to fit the English.
SLOT_LAYOUT = (0x8C12F640, 78)      # Move Edit: 10-byte records (text x, icon, icon x, icon2, icon2 x)
SLOT_LABELS = (0x8C12EE6C, 0x8C12ED34)   # record -> label index (bytes) -> label pointers
CPU_ICONS = (0x8C12FC1C, 0x8C12FC64, 18)  # CPU Logic: per situation a pointer to 3-byte records
                                          # (icon, row, x/2) and a u16 record count
TEXT_X0, TEXT_MIN, ICON_X0 = 97, 80, 30   # Move Edit: screen x = field + these (measured)


def _english_width(d_orig, eng, ptr):
    o = ptr - BASE
    text = eng.get(o)
    if text is None:
        text = d_orig[o:d_orig.index(b'\0', o)].decode(CODEC)
    return width(text)


def layout(d, d_orig, eng):
    """Move the button icons of Move Edit and CPU Logic to fit the English labels (data patch)."""
    tab, n = SLOT_LAYOUT
    lab_idx, lab_ptr = SLOT_LABELS
    for k in range(n):
        o = tab - BASE + 10 * k
        tx, i1, ix, i2, ix2 = struct.unpack_from('<5h', d_orig, o)
        if tx < 0:
            continue
        li = d_orig[lab_idx - BASE + k]
        w = _english_width(d_orig, eng, struct.unpack_from('<I', d_orig, lab_ptr - BASE + 4 * li)[0])
        icons = 1 if i2 < 0 else 2
        icon_abs = ix + ICON_X0
        cap = 278 - 24 - 28 * (icons - 1)
        icon_abs = min(max(icon_abs, tx + TEXT_X0 + w + 6), cap)
        text_abs = max(TEXT_MIN, min(tx + TEXT_X0, icon_abs - 6 - w))
        nix = icon_abs - ICON_X0
        struct.pack_into('<5h', d, o, text_abs - TEXT_X0, i1, nix, i2, nix + (ix2 - ix) if i2 >= 0 else ix2)
    # CPU Logic: each row's label starts at a fixed x (~27 px into the panel); its icons go right
    # after the English. Row labels per situation (records 0x8C12FC1C; seen in game 2026-10-28):
    st, gr, bk, rn, ct, cl, dv = 0xB44B8, 0xB44C0, 0xB44C8, 0xB44D0, 0xB44D8, 0xB44EC, 0xB44F4
    hd, lg = 0xB453C, 0xB4540
    rows = {0: {r: st for r in range(3, 8)}, 1: {r: gr for r in range(15)}, 2: {r: bk for r in range(7)},
            3: {0: rn, 1: rn, 2: ct, 3: ct, 4: ct}, 4: {0: rn, 1: gr, 2: gr, 3: gr},
            5: {1: cl, 2: cl, 3: cl, 4: cl, 5: dv}, 6: {1: 0xB451C},
            7: {2: hd, 3: lg, 4: hd, 5: lg}, 8: {2: hd, 3: lg, 4: hd, 5: lg},
            9: {1: cl, 2: cl, 3: cl, 4: cl, 5: dv, 6: 0xB4500}, 10: {1: rn, 2: rn},
            11: {1: 0xB4560, 2: 0xB4560, 3: 0xB4560}, 12: {0: 0xB4568, 1: 0xB4568},
            13: {r: 0xB45B4 for r in range(4)},
            14: {1: 0xB4580, 2: 0xB4590, 3: 0xB459C, 4: 0xB459C, 5: 0xB459C, 6: 0xB459C},
            15: {r: 0xB45D8 for r in range(3)}, 16: {r: 0xB45E0 for r in range(3)}, 17: {r: 0xB45E8 for r in range(3)}}
    ptrs_at, cnt_at, sits = CPU_ICONS
    for s in range(sits):
        po = struct.unpack_from('<I', d_orig, ptrs_at - BASE + 4 * s)[0] - BASE
        c = struct.unpack_from('<H', d_orig, cnt_at - BASE + 2 * s)[0]
        recs = [po + 3 * i for i in range(c)]
        first = {}
        for r in recs:
            first[d_orig[r + 1]] = min(first.get(d_orig[r + 1], 255), d_orig[r + 2])
        for r in recs:
            row = d_orig[r + 1]
            lab = rows.get(s, {}).get(row)
            if lab is None:
                continue
            x0 = (_english_width(d_orig, eng, BASE + lab) + 13) // 2      # icon px = 2x + 23 = 27 + w + 9
            d[r + 2] = min(x0 + d_orig[r + 2] - first[row], 110)


def step_ui(files, names='real'):
    """ui.csv and fixed.csv into 1ST_READ.BIN."""
    name = '/1ST_READ.BIN'
    d = bytes(files.get(name))
    orig = d
    tokens = name_tokens()
    eng = {int(k, 16): resolve(v, names, f'ui.csv {k}', tokens) for k, v in english_rows('ui.csv', 'offset').items()}
    if eng:
        d, need, room, align = pack_pool(d, eng)
        print(f'text: ui.csv {len(eng)} strings; pool {need}/{room} bytes, aligned to {align}')
    d = bytearray(d)
    fixed = {int(r['offset'], 16): r for r in _csv_rows('fixed.csv')}
    n = 0
    for o, r in fixed.items():
        if not r.get('english'):
            continue
        b = encode(resolve(r['english'], names, f'fixed.csv {r["offset"]}', tokens), f'fixed.csv {r["offset"]}')
        room = int(r['max_bytes'])
        if len(b) > room:
            sys.exit(f'fixed.csv {r["offset"]}: {r["english"]!r} is {len(b)} bytes, room for {room}')
        d[o:o + room + 1] = b.ljust(room + 1, b'\0')
        n += 1
    if n:
        print(f'text: fixed.csv {n} strings')
    text_code(d)
    layout(d, orig, eng)
    files.put(name, d)


ORDER_FLAGS = {'1-2': 0x00, '2-1': 0x80}
SPACE = 0                                          # separator code for a space (flags bits 0-1)


def roster_patch(data, start, rows, names):
    """Write the English names into the 220 records at `start` of `data` (bytearray)."""
    R, n = ROSTER
    for r in rows:
        k = int(r['idx'])
        pre = 'en_' if names == 'real' else 'parody_'
        n1, n2 = r.get(pre + 'name1') or r.get('en_name1'), r.get(pre + 'name2', '')
        if not n1 and not r.get('en_nick'):
            continue
        rec = start + k * R
        if n1:
            if not r.get(pre + 'name1'):
                n2 = r.get('en_name2', '')
            order = r.get(pre + 'order') or r.get('en_order') or '1-2'
            for fname, text in (('name1', n1), ('name2', n2)):
                _, o, size = next(f for f in FIELDS if f[0] == fname)
                b = encode(text, f'wrestlers.csv row {k} {pre}{fname}')
                if len(b) >= size:
                    sys.exit(f'wrestlers.csv row {k}: {pre}{fname} {text!r} is {len(b)} bytes, room for {size - 1}')
                data[rec + o:rec + o + size] = b.ljust(size, b'\0')
            sep = SPACE
            data[rec + 1] = (data[rec + 1] & ~0x83 & 0xFF) | ORDER_FLAGS[order] | sep
        nick_col = 'en_nick' if names == 'real' or not r.get('parody_nick') else 'parody_nick'
        if r.get(nick_col):
            _, o, size = next(f for f in FIELDS if f[0] == 'nick')
            b = encode(r[nick_col], f'wrestlers.csv row {k} {nick_col}')
            if len(b) >= size:
                sys.exit(f'wrestlers.csv row {k}: {nick_col} {r[nick_col]!r} is {len(b)} bytes, room for {size - 1}')
            data[rec + o:rec + o + size] = b.ljust(size, b'\0')


def moves_patch(data, english):
    """Rewrite the move-name section of entry 1's data with `english` ({index: text})."""
    names, table = move_names(data)
    start, end, n, nstart = move_section(data)
    off_of = {}                                    # old offset -> new offset
    blob = bytearray()
    base = nstart - start
    for k, off, text in names:
        b = encode(english[k], f'moves.csv {k}') if k in english else text.encode(CODEC)
        off_of[off] = base + len(blob)
        blob += b + b'\0'
    new_table = [off_of.get(v, v) for v in table]
    if max(new_table) > 0xFFFF:
        sys.exit('moves.csv: the move names outgrow the 16-bit offsets - shorten them')
    section = struct.pack(f'<{n}H', *new_table) + bytes(blob)
    section += bytes(-len(section) % 4)
    out = bytearray(data[:start]) + section
    struct.pack_into('<I', out, 16, len(out) // 4)
    return bytes(out)


def step_sbl(files, names='real'):
    """wrestlers.csv into SBL entries 1 and 2, moves.csv into entry 1."""
    rows = _csv_rows('wrestlers.csv')
    tokens = name_tokens()
    moves = {int(k): resolve(v, names, f'moves.csv {k}', tokens) for k, v in english_rows('moves.csv', 'index').items()}
    has_roster = any(r.get('en_name1') or r.get('en_nick') for r in rows)
    if not has_roster and not moves:
        return
    s = sbl.Sbl(files.get('/SBL.BIN'))
    for entry, start in ROSTER_ENTRIES:
        data = bytearray(lzss.decompress(s.get(entry)))
        if has_roster:
            roster_patch(data, start, rows, names)
        if entry == MOVE_ENTRY and moves:
            data = bytearray(moves_patch(bytes(data), moves))
        s.put(entry, lzss.compress(data))
    print(f'text: roster ({names} names) and {len(moves)} move names into SBL.BIN entries 1 and 2')
    files.put('/SBL.BIN', s.bytes())


def full_jp(n1, n2, flags):
    sep = {0: ' ', 1: '・', 2: '＝', 3: ''}[flags & 3]
    parts = [n2, n1] if flags & 0x80 else [n1, n2]
    return sep.join(p for p in parts if p)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['dump']:
        dump()
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
