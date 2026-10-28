#!/usr/bin/env python3
"""The network mode's DreamPassport 3 browser text: dump it, write the English back (build step).

  dpnet.py dump        (re)write translation/text/dpmsg.csv and dpmisc.csv (English kept)

- dpmsg.csv: /DPETC/MESSAGE.INI, the browser's messages: lines `N="text"` in Shift-JIS, one per
  message id (797 live, commented ones `#N=` left alone). Text may hold HTML (<br>, <font ...>) and
  %s / %d. The file is rewritten whole, so English may be longer than the Japanese.
- dpmisc.csv: Japanese pieces of other small files (NTP.DPS labels, the local start/help pages),
  replaced as exact substrings.
- dpbin.csv: the browser program's own strings (/2_DP.BIN 0x150000-0x156000: chat page titles,
  download progress, the history page, date pieces...), written in place: the English may use
  the Japanese string's bytes and no more (the rest is filled with zero bytes). The kana key map,
  the digit tables and the sample registration data (0x1525B0-0x152650) are left out, and so is
  the input method's dictionary after 0x16D000.

English is Shift-JIS-safe ASCII; a double quote inside a message would end it - use ' instead
(the quotes inside HTML tags, <font color="...">, are the original's and stay).
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

CODEC = 'cp932'
INI = '/DPETC/MESSAGE.INI'
BIN = '/2_DP.BIN'
BIN_RANGE = (0x150000, 0x156000)
BIN_SKIP = [(0x1525B0, 0x152650), (0x154D94, 0x154F5C), (0x154DBC, 0x154DEA), (0x156100, 0x156140)]
ENTRY = re.compile(r'^(\d+)="(.*)"(\s*)$')
JP = re.compile(r'[　-ヿ一-鿿＀-￯]')
MISC = {   # file -> Japanese pieces to translate
    '/DPETC/NTP.DPS': ['現在の時刻', '接続経過時間'],
    '/DPWWW/INDEX.HTML': ['ファイヤープロレスリングD ホームページ'],
    '/DPWWW/HELP/INDEX.HTML': ['ファイヤープロレスリングD ホームページ',
                               'Lトリガーを押してメニューにあるホームを選択してください。',
                               '１０秒後に自動的にホームに戻ります。'],
}


def _rows(name):
    p = paths.TEXT / name
    if not p.exists():
        return []
    with open(p, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(ln for ln in f if not ln.startswith('#')))


def _write(name, header, fields, rows):
    p = paths.TEXT / name
    with open(p, 'w', encoding='utf-8', newline='') as f:
        for h in header:
            f.write(f'# {h}\n')
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    print(f'{paths.show(p)}: {len(rows)} rows')


def messages(data):
    """[(id, text)] of the live entries of MESSAGE.INI (bytes)."""
    out = []
    for ln in data.decode(CODEC).split('\r\n'):
        m = ENTRY.match(ln)
        if m and JP.search(m.group(2)):
            out.append((m.group(1), m.group(2)))
    return out


def bin_strings(data):
    """[(offset, room in bytes, text)] of the browser program's Japanese strings: NUL-bounded,
    in BIN_RANGE, not in BIN_SKIP. room = the string's bytes (the NUL after it stays)."""
    out = []
    lo, hi = BIN_RANGE
    for m in re.finditer(rb'(?<=\x00)[^\x00]{2,600}(?=\x00)', data[lo:hi]):
        o = lo + m.start()
        if any(a <= o < b for a, b in BIN_SKIP):
            continue
        try:
            t = m.group(0).decode(CODEC)
        except UnicodeDecodeError:
            continue
        if JP.search(t) and all(c.isprintable() or c in '\r\n\t' for c in t):
            out.append((o, len(m.group(0)), t))
    return out


def dump():
    data = (paths.EXTRACTED / INI.lstrip('/')).read_bytes()
    old = {r['id']: r for r in _rows('dpmsg.csv')}
    rows = [{'id': k, 'japanese': t, 'english': old.get(k, {}).get('english', ''), 'notes': old.get(k, {}).get('notes', '')}
            for k, t in messages(data)]
    _write('dpmsg.csv', [
        'Network mode (DreamPassport 3 browser) messages: /DPETC/MESSAGE.INI, one row per message id.',
        'Keep HTML tags (<br>, <font ...>, </font>) and %s %d in the same places; <br> is a line break.',
        'No double quotes (") in the English - use single quotes. Printable ASCII. Length is free, but',
        'dialog boxes are ~30 full-width characters wide: keep lines (between <br>) under ~45 letters.'],
        ['id', 'japanese', 'english', 'notes'], rows)
    old = {(r['file'], r['japanese']): r for r in _rows('dpmisc.csv')}
    rows = []
    for f, pieces in MISC.items():
        for jp in pieces:
            rows.append({'file': f, 'japanese': jp, 'english': old.get((f, jp), {}).get('english', ''),
                         'notes': old.get((f, jp), {}).get('notes', '')})
    old_bin = {r['offset']: r for r in _rows('dpbin.csv')}
    brows = [{'offset': f'{o:06X}', 'bytes': n, 'japanese': t.replace('\n', '\\n'),
             'english': old_bin.get(f'{o:06X}', {}).get('english', ''),
             'notes': old_bin.get(f'{o:06X}', {}).get('notes', '')}
            for o, n, t in bin_strings((paths.EXTRACTED / BIN.lstrip('/')).read_bytes())]
    _write('dpbin.csv', [
        'The browser program\'s strings (/2_DP.BIN), written in place: English up to `bytes` bytes',
        '(ASCII: one byte a letter). \\n is a line break. Keep %s %d %02d and HTML tags. Empty = unchanged.'],
        ['offset', 'bytes', 'japanese', 'english', 'notes'], brows)
    _write('dpmisc.csv', [
        'Small network-mode texts (NTP.DPS labels, the local start and help pages): exact pieces of',
        'each file, replaced in the build. Printable ASCII.'], ['file', 'japanese', 'english', 'notes'], rows)


def _encode(text, where):
    try:
        return text.encode(CODEC)
    except UnicodeEncodeError as e:
        sys.exit(f'{where}: {text!r}: {e.reason}')


def step(files):
    """dpmsg.csv into MESSAGE.INI, dpmisc.csv into its files."""
    eng = {r['id']: r['english'] for r in _rows('dpmsg.csv') if r.get('english')}
    n = 0
    if eng:
        lines = bytes(files.get(INI)).decode(CODEC).split('\r\n')
        for i, ln in enumerate(lines):
            m = ENTRY.match(ln)
            if m and m.group(1) in eng:
                e = eng[m.group(1)]
                if '"' in re.sub(r'<[^<>]*>', '', e):    # quotes inside tags are the original's
                    sys.exit(f'dpmsg.csv {m.group(1)}: a double quote ends the message - use \' instead')
                lines[i] = f'{m.group(1)}="{e}"{m.group(3)}'
                n += 1
        files.put(INI, _encode('\r\n'.join(lines), INI))
    m = 0
    for r in _rows('dpmisc.csv'):
        if not r.get('english'):
            continue
        data = bytes(files.get(r['file']))
        jp = _encode(r['japanese'], r['file'])
        if jp not in data:
            sys.exit(f'dpmisc.csv: {r["japanese"]!r} not found in {r["file"]}')
        files.put(r['file'], data.replace(jp, _encode(r['english'], r['file'])))
        m += 1
    k = 0
    rows = [r for r in _rows('dpbin.csv') if r.get('english')]
    if rows:
        data = bytearray(files.get(BIN))
        for r in rows:
            o, room = int(r['offset'], 16), int(r['bytes'])
            jp = _encode(r['japanese'].replace('\\n', '\n'), BIN)
            if bytes(data[o:o + room]) != jp:
                sys.exit(f'dpbin.csv {r["offset"]}: the Japanese is not at that offset of {BIN}')
            en = _encode(r['english'].replace('\\n', '\n'), BIN)
            if len(en) > room:
                sys.exit(f'dpbin.csv {r["offset"]}: {r["english"]!r} is {len(en)} bytes, room for {room}')
            data[o:o + room] = en + bytes(room - len(en))
            k += 1
        files.put(BIN, bytes(data))
    if n or m or k:
        print(f'text: network mode {n} messages, {m} other pieces, {k} browser strings')


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
