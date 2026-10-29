#!/usr/bin/env python3
"""Check the translation text: python3 tools/lint.py [--missing] [--warnings] [file...]

Errors (check.py and the build fail on these):
  source       source-language characters (kana, kanji) left in the English (not in a block with
               a `# keep: why` comment - text kept as the original on purpose, e.g. staff credits:
               copy the source into the English line so the entry counts as done)
  codes        control codes in the source missing from the English, or extra ones (CODE)
  lines        more lines than a block file's `# limit lines=N`
  chars        a line longer than `# limit chars=N` (characters; pixel widths need the game's
               own layout check)
  bytes        English longer than a fixed table string's max_bytes (refs == 0), as encoded by
               encoded_length() - adjust it to how the build stores English
  room         more than the string's measured room (translation/text/rooms.csv, below): counted
               by count() (characters - or the game's glyphs/tiles), and pixels by width() if the
               game provides it; and any string over MAX_COUNT (a hard per-string limit, e.g.
               the glyph records of one text object) when it is set
Deliberate layout changes: a block whose comment holds `# layout:` may change its position codes
(LAYOUT_CODE, e.g. pen moves) - the other codes must still match.

rooms.csv - room measured in the game (a debugger or emulator: which text area the string is drawn
into and how much it holds), one row per string, address range or table column:
  id,count,px,screen,measured
  text/menus.txt|2ND:060BDB54,15,,Mode Select title,2026-10-27 emulator
  text/menus.txt|2ND:060B3634-060B3838,16,96,Moves categories,...   (a range of block ids)
  moves.csv:japanese,20,150,Wrestler Select finisher,...             (every row of a table column)
Warnings (shown with --warnings; counted by status.py):
  glossary     the source contains a glossary term but the English doesn't use its translation
               (translation/glossary.csv: japanese, english, notes; several accepted English forms
               separated by ' | '; put [glossary-ok] in a block comment or row note to silence)
  spacing      trailing spaces or double spaces in the English (leading spaces are left alone:
               continuation lines are often indented)
--missing also lists untranslated entries (status.py counts them).
"""
import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import textdb  # noqa: E402

SOURCE_CHARS = re.compile(r'[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ]')
CODE = re.compile(r'%[-0-9.]*[sdx]')  # Fire Pro D: printf formats only (< > are plain text)
NAME_TOKEN = re.compile(r'<[A-Za-z][^<>]*>')   # <Name> tokens resolved per build (tools/names.py)


LAYOUT_CODE = None    # e.g. re.compile(r'\{[xy]-?\d+,\}'): codes a `# layout:` block may change
MAX_COUNT = None      # a hard limit for every string, in count() units (None: no limit)


def encoded_length(text):
    """Bytes the build will store for `text`: name tokens resolved, the longer of the two builds."""
    import fpdtext
    if fpdtext.TOKEN.search(text):
        try:
            return max(len(fpdtext.resolve(text, v, tokens=_tokens()).encode('ascii', 'replace'))
                       for v in ('real', 'parody'))
        except SystemExit:
            pass
    return len(text.encode('ascii', 'replace'))


def count(text):
    """What a text area holds, for rooms.csv and MAX_COUNT: characters without codes - change to the
    game's unit (glyphs drawn, tiles) when that differs."""
    return len(CODE.sub('', text).replace('\n', ''))


def width(text):
    """Pixel width of `text` for rooms.csv `px`: the widest line, at the menu font's size."""
    import fpdtext
    out = 0
    for names in ('real', 'parody'):        # name tokens: the wider of the two builds
        t = fpdtext.TOKEN.sub(lambda m: fpdtext.resolve(m.group(0), names, tokens=_tokens())
                              if m.group(1) in _tokens() else m.group(0), text)
        out = max(out, max(fpdtext.width(ln) for ln in t.split('\n')))
    return out


_ROOMS = None


def rooms():
    """{id: (count, px, screen)} from translation/text/rooms.csv."""
    global _ROOMS
    if _ROOMS is None:
        _ROOMS = {}
        p = paths.TEXT / 'rooms.csv'
        if p.exists():
            with open(p, encoding='utf-8', newline='') as f:
                for r in csv.DictReader(ln for ln in f if not ln.startswith('#')):
                    _ROOMS[r['id']] = (int(r['count']) if r.get('count') else None,
                                       int(r['px']) if r.get('px') else None, r.get('screen', ''))
    return _ROOMS


def room_for(e):
    """The rooms.csv row for an entry: its block id, a range holding it, or its table column."""
    rel = f'{e.file.parent.name}/{e.file.name}'
    if f'{rel}|{e.key}' in rooms():
        return rooms()[f'{rel}|{e.key}']
    if e.file.suffix == '.csv':
        col = e.key.partition(':')[2] or textdb.SOURCE_COLUMN
        if f'{e.file.name}:{col}' in rooms():
            return rooms()[f'{e.file.name}:{col}']
    m = re.match(r'(\w+):([0-9A-Fa-f]+)$', e.key)
    if m:
        for k, v in rooms().items():
            r = re.match(rf'{re.escape(rel)}\|(\w+):([0-9A-Fa-f]+)-([0-9A-Fa-f]+)$', k)
            if r and r.group(1) == m.group(1) and int(r.group(2), 16) <= int(m.group(2), 16) <= int(r.group(3), 16):
                return v
    return None


def glossary():
    if not paths.GLOSSARY.exists():
        return []
    with open(paths.GLOSSARY, encoding='utf-8', newline='') as f:
        return [(r['japanese'].strip(), [e.strip() for e in r['english'].split(' | ') if e.strip()])
                for r in csv.DictReader(f) if (r.get('japanese') or '').strip() and (r.get('english') or '').strip()]


_TOKENS = None


def _tokens():
    global _TOKENS
    if _TOKENS is None:
        import fpdtext
        _TOKENS = fpdtext.name_tokens()
    return _TOKENS


def check_entry(e, terms):
    """[(severity, kind, message)] for one entry."""
    out = []
    en = e.english
    if not en:
        return out
    m = SOURCE_CHARS.search(en)
    if m and '# keep:' not in (e.notes or ''):     # `# keep:` = left as the original on purpose
        out.append(('error', 'source', f'source-language text left in the English: {m.group()!r}'))
    a, b = Counter(CODE.findall(e.source)), Counter(CODE.findall(en))
    if LAYOUT_CODE and '# layout:' in (e.notes or ''):     # deliberate English layout: positions may differ
        a, b = (Counter({k: v for k, v in c.items() if not LAYOUT_CODE.match(k)}) for c in (a, b))
    if a != b:
        miss, extra = list((a - b).elements()), list((b - a).elements())
        out.append(('error', 'codes', 'control codes ' + '; '.join(
            x for x in (f'missing {miss}' if miss else '', f'extra {extra}' if extra else '') if x)))
    lines = en.split('\n')
    if 'lines' in e.limits and len(lines) > e.limits['lines']:
        out.append(('error', 'lines', f'{len(lines)} lines, limit {e.limits["lines"]}'))
    if 'chars' in e.limits:
        for ln in lines:
            plain = CODE.sub('', ln)
            if len(plain) > e.limits['chars']:
                out.append(('error', 'chars', f'{len(plain)} characters, limit {e.limits["chars"]}: {ln!r}'))
    if 'max_bytes' in e.limits and e.limits.get('refs', 0) == 0 and encoded_length(en) > e.limits['max_bytes']:
        out.append(('error', 'bytes', f'{encoded_length(en)} bytes, room for {e.limits["max_bytes"]} (fixed string)'))
    n = count(en)
    if MAX_COUNT and n > MAX_COUNT:
        out.append(('error', 'room', f'{n} in one string: the game holds at most {MAX_COUNT}'))
    room = room_for(e)
    if room:
        if room[0] is not None and n > room[0]:
            out.append(('error', 'room', f'{n}, its text area holds {room[0]} ({room[2]})'))
        w = width(en)
        if room[1] is not None and w is not None and w > room[1]:
            out.append(('error', 'room', f'{w} px, room for {room[1]} ({room[2]})'))
    html = e.file.name in ('dpmsg.csv', 'dpmisc.csv', 'dpbin.csv') or '<HTML>' in e.source
    plain_en = re.sub(r'<[^<>]*>', '', en) if html else en     # tags are copied as they are
    if html:
        # a button without NAME isn't sent with the form: its VALUE is only the caption on screen
        caption = lambda g: re.sub(r'(?i)\bvalue="[^"]*"', 'value="..."', g) \
            if re.search(r'(?i)type="(submit|reset|button)"', g) and not re.search(r'(?i)\bname=', g) else g
        tags = lambda t: sorted(caption(g) for g in re.findall(r'<[^<>]*>', t.lower()))
        if tags(e.source) != tags(en):
            out.append(('error', 'tags', f'HTML tags differ from the Japanese: {tags(e.source)} vs {tags(en)}'))
        if '"' in plain_en and e.file.name == 'dpmsg.csv':
            out.append(('error', 'quote', 'a double quote ends the message - use single quotes'))
    import fpdtext
    unknown = [t for t in fpdtext.TOKEN.findall(en) if t not in _tokens()
               and not fpdtext.HTML_TAG.match(t)]
    if unknown:
        out.append(('error', 'token', f'unknown name token(s) {unknown}: a wrestler\'s parody name or name_tokens.csv'))
    bad = fpdtext.bad_chars(plain_en)
    if bad:
        out.append(('error', 'charset', f'the font has no {"".join(bad)!r}: printable ASCII, no #, '
                                        f'and {fpdtext.SYMBOLS}'))
    if en.count('\n') > e.source.count('\n'):
        out.append(('error', 'lines', f'{en.count(chr(10)) + 1} lines, the Japanese has {e.source.count(chr(10)) + 1}'))
    if e.file.name in ('ui.csv', 'moves.csv') and not room:
        jp = width(e.source)
        w = width(NAME_TOKEN.sub('Xxxxxxxxx', en))
        if w > max(jp * 1.6, jp + 48):
            out.append(('warning', 'width', f'~{w} px wide, the Japanese {jp} px: check it fits on screen'))
    if any(ln != ln.rstrip() or '  ' in ln.strip() for ln in lines):
        out.append(('warning', 'spacing', f'trailing or double spaces: {en!r}'))
    for jp, accepted in terms:
        if jp in e.source and not any(x.lower() in en.lower() for x in accepted):
            out.append(('warning', 'glossary', f'{jp} should be "{" | ".join(accepted)}"'))
    return out


def run(files=None, missing=False):
    """{'error': n, 'warning': n, 'missing': n, 'total': n} plus the printed lines."""
    terms = glossary()
    ents = []
    for p in files or textdb.text_files():
        ents += textdb.read_file(p)
    report, counts = [], Counter()
    for e in ents:
        counts['total'] += 1
        if not e.english:
            counts['missing'] += 1
            if missing:
                report.append(('missing', e, 'no English yet'))
            continue
        for sev, kind, msg in check_entry(e, [] if '[glossary-ok]' in e.notes else terms):
            counts[sev] += 1
            report.append((sev, e, f'{kind}: {msg}'))
    return counts, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='*', type=Path, help='only these text files (default: all)')
    ap.add_argument('--missing', action='store_true', help='also list untranslated entries')
    ap.add_argument('--warnings', action='store_true', help='also list warnings')
    args = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    counts, report = run(args.files or None, args.missing)
    for sev, e, msg in report:
        if sev == 'warning' and not args.warnings:
            continue
        print(f'{e.where}: {"! " if sev == "error" else ""}{msg}')
    print(f'{counts["total"]} entries, {counts["total"] - counts["missing"]} translated: '
          f'{counts["error"]} error(s), {counts["warning"]} warning(s)'
          + ('' if args.warnings or not counts['warning'] else ' (--warnings to list them)'))
    return 1 if counts['error'] else 0


if __name__ == '__main__':
    sys.exit(main())
