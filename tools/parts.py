#!/usr/bin/env python3
"""Split the text into part files for parallel translators, check them, merge them back.

  python3 tools/parts.py split [FILE...] [--size 200 | --parts N] [--all] [--out DIR] [--force]
  python3 tools/parts.py check PART...          what a translator runs until it reports 0 errors
  python3 tools/parts.py status [--out DIR]     every part: blocks, translated, errors, warnings
  python3 tools/parts.py merge PART... [--overwrite] [--force]

split takes every untranslated entry (--all: every entry, for a revision pass) of the given text
files (default: all of translation/), in file order, and cuts it into parts of about --size blocks,
preferring to cut where a file ends. Each part is a message block file (tools/blocks.py) whose
block ids are `<file>|<key>` - the entry's file under translation/ and its key - with the limits,
notes and duplicates as # comments:

    @ script/ch01.txt|012
    # limit lines=3 chars=28
    # same JP: 2 more (script/ch05.txt|044, text/menus.csv|0x1a40) - they get this English too
    JP 「俺は・・・勝ったのか・・・
    EN "I... won...?

Identical source text appears once; merge gives every copy its English. Parts go to
private/work/tr/ (partNN.txt and parts.json).

check runs tools/lint.py's checks on every block of a part against the real entry's limits (and
every duplicate's), plus: unknown ids, JP lines changed, blocks without English. A game's own
checks belong in lint.py, so they apply here too. Exit status 1 on any error.

merge writes the English of checked blocks into the text files - blocks with errors are skipped
(--force merges them anyway), entries that already have English are kept (--overwrite replaces
them). Run tools/lint.py and a build afterwards.
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blocks  # noqa: E402
import lint  # noqa: E402
import paths  # noqa: E402
import textdb  # noqa: E402

SEP = '|'
OUT = paths.ROOT / 'private' / 'work' / 'tr'


def entry_id(e, _root=[]):
    # string prefix, not resolve() per entry: that is slow on /mnt drives
    if not _root:
        _root.append(paths.TRANSLATION.resolve().as_posix() + '/')
    f = Path(e.file).absolute().as_posix()
    return f'{f[len(_root[0]):] if f.startswith(_root[0]) else f}{SEP}{e.key}'


def all_entries():
    """{id: entry} for every entry, in file order."""
    return {entry_id(e): e for e in textdb.entries()}


def limit_text(limits):
    return ' '.join(f'{k}={v}' for k, v in limits.items())


def wanted(e, files):
    if not files:
        return True
    rel = entry_id(e).split(SEP)[0]
    return any(rel == f or rel.startswith(f.rstrip('/') + '/') for f in files)


# --- split -------------------------------------------------------------------------------------

def split(files, size, parts, include_done, out, force):
    out.mkdir(parents=True, exist_ok=True)
    old = sorted(out.glob('part[0-9][0-9].txt'))
    if old and not force:
        sys.exit(f'{paths.show(out)} already has {len(old)} part files (--force replaces them, after merging)')
    for p in old:
        p.unlink()
    # one block per distinct source text, in order of first appearance
    groups = {}
    for i, e in all_entries().items():
        if not wanted(e, files) or not e.source.strip() or (e.english and not include_done):
            continue
        groups.setdefault(e.source, []).append((i, e))
    if not groups:
        sys.exit('nothing to translate in those files')
    items = list(groups.values())
    if parts:
        size = -(-len(items) // parts)
    cuts, start = [], 0
    while start < len(items):
        end = min(start + size, len(items))
        if end < len(items):    # cut where a file ends, if one is near (within the last quarter)
            for j in range(end, max(start + size * 3 // 4, start + 1) - 1, -1):
                if items[j - 1][0][1].file != items[j][0][1].file:
                    end = j
                    break
        cuts.append((start, end))
        start = end
    manifest = {}
    for n, (a, b) in enumerate(cuts):
        name = f'part{n:02d}.txt'
        chunk = items[a:b]
        srcs = sorted({entry_id(g[0][1]).split(SEP)[0] for g in chunk})
        lines = [f'# {name}: {len(chunk)} blocks of {len(items)} ({len(cuts)} parts), from {", ".join(srcs)}',
                 '# Add EN lines under the JP lines of every block (one EN line per line on screen). Keep the',
                 '# JP lines, the @ lines and the # comments; add or remove no blocks. Check with:',
                 f'#   python3 tools/parts.py check {paths.show(out / name)}',
                 '# The brief (style, codes, names, limits) is BRIEF.md next to this file.', '']
        for group in chunk:
            i, e = group[0]
            lines.append(f'@ {i}')
            if e.limits:
                lines.append(f'# limit {limit_text(e.limits)}')
            room = lint.room_for(e)
            if room and (room[0] or room[1]):
                lines.append('# room ' + ', '.join(x for x in (room[0] and f'{room[0]} glyphs', room[1] and f'{room[1]} px') if x)
                             + (f' ({room[2]})' if room[2] else '') + ' - measured in the game')
            if len(group) > 1:
                more = [g[0] for g in group[1:]]
                lines.append(f'# same JP: {len(more)} more ({", ".join(more[:4])}{", ..." if len(more) > 4 else ""})'
                             ' - they get this English too')
            for note in e.notes.splitlines():
                lines.append(note if note.startswith('#') else f'# note: {note}')
            lines += [f'JP {t}' for t in e.source.split('\n')]
            if e.english:
                lines += [f'EN {t}' for t in e.english.split('\n')]
            lines.append('')
        (out / name).write_text('\n'.join(lines), encoding='utf-8', newline='\n')
        manifest[name] = [g[0][0] for g in chunk]
    (out / 'parts.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    print(f'{len(items)} blocks ({sum(len(g) for g in items)} entries) in {len(cuts)} parts in {paths.show(out)}: '
          + ', '.join(str(b - a) for a, b in cuts))


# --- check -------------------------------------------------------------------------------------

def duplicates(entries):
    by_source = defaultdict(list)
    for i, e in entries.items():
        by_source[e.source].append(i)
    return by_source


def check_part(path, entries, by_source, terms):
    """(blocks, translated, [(id, severity, kind, message)])."""
    bf = blocks.BlockFile(path)
    problems, done = [], 0
    for b in bf.blocks:
        target = entries.get(b.id)
        if target is None:
            problems.append((b.id, 'error', 'id', 'no such entry (ids are <file>|<key>; was the block renamed?)'))
            continue
        if '\n'.join(bf.source(b)) != target.source:
            problems.append((b.id, 'error', 'source', 'JP lines differ from the text file - keep them as they are'))
        en = '\n'.join(b.english)
        if not en:
            problems.append((b.id, 'warning', 'missing', 'no English yet'))
            continue
        done += 1
        seen = set()
        for other in by_source.get(target.source, [b.id]):
            e = entries[other]
            use = [] if '[glossary-ok]' in e.notes or '[glossary-ok]' in '\n'.join(b.tagged('#')) else terms
            probe = textdb.Entry(e.file, e.key, e.source, en, e.limits, e.line, e.notes)
            for sev, kind, msg in lint.check_entry(probe, use):
                if (kind, msg) not in seen:
                    seen.add((kind, msg))
                    problems.append((b.id + ('' if other == b.id else f' (as {other})'), sev, kind, msg))
    return len(bf.blocks), done, problems


def check(parts, quiet=False):
    entries = all_entries()
    by_source, terms = duplicates(entries), lint.glossary()
    errors = 0
    rows = []
    for p in parts:
        n, done, problems = check_part(p, entries, by_source, terms)
        errs = [x for x in problems if x[1] == 'error']
        warns = [x for x in problems if x[1] == 'warning' and x[2] != 'missing']
        errors += len(errs)
        rows.append((p, n, done, len(errs), len(warns)))
        if not quiet:
            for i, sev, kind, msg in errs + warns:
                print(f'{paths.show(p)} @ {i}: {sev.upper()} {kind}: {msg}')
            print(f'{paths.show(p)}: {done}/{n} blocks have English, {len(errs)} error(s), {len(warns)} warning(s)')
    return errors, rows


# --- merge -------------------------------------------------------------------------------------

def merge(parts, overwrite, force):
    entries = all_entries()
    by_source, terms = duplicates(entries), lint.glossary()
    todo = {}           # entry id -> English
    skipped = defaultdict(int)
    for p in parts:
        _, _, problems = check_part(p, entries, by_source, terms)
        bad = {x[0].split(' (as ')[0] for x in problems if x[1] == 'error'}
        for b in blocks.BlockFile(p).blocks:
            en = '\n'.join(b.english)
            if b.id not in entries or not en:
                skipped['no English' if b.id in entries else 'unknown id'] += 1
                continue
            if b.id in bad and not force:
                skipped['errors (fix, or --force)'] += 1
                continue
            for other in by_source[entries[b.id].source]:
                if entries[other].english and not overwrite:
                    skipped['already English (--overwrite)'] += 1
                elif entries[other].english != en:
                    todo[other] = en
    by_file = defaultdict(dict)
    for i, en in todo.items():
        by_file[entries[i].file][entries[i].key] = en
    for f, keys in by_file.items():
        if f.suffix == '.txt':
            bf = blocks.BlockFile(f)
            for key, en in keys.items():
                bf.get(key).english = en.split('\n')
            bf.save()
        else:
            write_csv(f, keys)
    print(f'merged {len(todo)} entries into {len(by_file)} file(s)'
          + ''.join(f'; skipped {n}: {why}' for why, n in skipped.items()))


def write_csv(f, keys):
    with open(f, encoding='utf-8', newline='') as fh:
        text = fh.read().splitlines(keepends=True)
    head = [ln for ln in text[:next((i for i, ln in enumerate(text) if not ln.startswith('#')), len(text))]]
    r = csv.DictReader(text[len(head):])
    fields, rows = r.fieldnames, list(r)
    for n, row in enumerate(rows, len(head) + 2):     # file line numbers, as textdb.read_file keys them
        for src, en in textdb.column_pairs(fields):
            key = (row.get('id') or row.get('offset') or str(n)) + (f':{src}' if src != textdb.SOURCE_COLUMN else '')
            if key in keys:
                row[en] = keys[key]
    with open(f, 'w', encoding='utf-8', newline='') as fh:
        fh.writelines(head)                     # the leading # comment lines stay
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def part_files(names, out):
    files = [Path(n) for n in names] or sorted(out.glob('part[0-9][0-9].txt'))
    if not files:
        sys.exit(f'no part files (looked in {paths.show(out)})')
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('split', help='cut the untranslated text into part files')
    s.add_argument('files', nargs='*', help='text files or folders, relative to translation/ (default: all)')
    s.add_argument('--size', type=int, default=200, help='blocks per part (default 200)')
    s.add_argument('--parts', type=int, help='this many parts instead of --size')
    s.add_argument('--all', action='store_true', help='also entries that have English (a revision pass)')
    s.add_argument('--force', action='store_true', help='replace existing part files')
    c = sub.add_parser('check', help="check part files (a translator's loop)")
    c.add_argument('parts', nargs='+', type=Path)
    st = sub.add_parser('status', help='a line per part')
    m = sub.add_parser('merge', help='write the English of part files into translation/')
    m.add_argument('parts', nargs='*', help='part files (default: every part in --out)')
    m.add_argument('--overwrite', action='store_true', help='replace English that is already there')
    m.add_argument('--force', action='store_true', help='merge blocks that have errors too')
    for p in (s, st, m):
        p.add_argument('--out', type=Path, default=OUT, help=f'the parts folder (default {paths.show(OUT)})')
    args = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    if args.cmd == 'split':
        split(args.files, args.size, args.parts, args.all, args.out, args.force)
    elif args.cmd == 'check':
        errors, _ = check(args.parts)
        sys.exit(1 if errors else 0)
    elif args.cmd == 'status':
        errors, rows = check(part_files([], args.out), quiet=True)
        for p, n, done, e, w in rows:
            print(f'{p.name}  {done:5}/{n:<5} {"done" if done == n else "    "}  {e} error(s)  {w} warning(s)')
        total, done = sum(r[1] for r in rows), sum(r[2] for r in rows)
        print(f'total  {done}/{total} blocks, {errors} error(s)')
    else:
        merge(part_files(args.parts, args.out), args.overwrite, args.force)


if __name__ == '__main__':
    main()
