#!/usr/bin/env python3
"""Message block files (translation/script/*.txt, translation/text/*.txt): read and write.

    # What this file holds, its limits and its control codes (read before editing).
    # limit lines=3 chars=28        <- optional: checked by tools/lint.py for every block
    # tag JP                        <- optional: the source-language tag (default JP)

    @ 012
    JP 「俺は・・・勝ったのか・・・
    JP 　手に入れたのか・・・・
    EN "I... won...?
    EN  Did I really get it...?"

`@` starts a block; the rest of the `@` line is its id and, in menu files, build metadata (address,
original length, ...) that isn't for editing. Source lines are reference only. EN lines are the
translation; a block with no EN lines keeps the original. One tag + one space, then the text
exactly (leading spaces count). `#` lines inside a block are kept as comments.

A dump tool that (re)writes a block file goes through merge(): it keeps the English and every
`#` line someone added by hand (layout notes, spacing, decisions) - a plain rewrite loses them.

  blocks.py show <file> [id...]      print blocks (all, or the given ids)
  blocks.py stats <file>...          blocks / translated per file
"""
import re
import sys
from pathlib import Path

DEFAULT_TAG = 'JP'
EN = 'EN'


class Block:
    def __init__(self, ident, meta, line):
        self.id, self.meta, self.line = ident, meta, line
        self.lines = []  # (tag, text) in file order: tag is the source tag, EN or '#'

    def tagged(self, tag):
        return [t for k, t in self.lines if k == tag]

    @property
    def english(self):
        return self.tagged(EN)

    @english.setter
    def english(self, lines):
        """Replace the EN lines (placed after the last non-EN line)."""
        rest = [(k, t) for k, t in self.lines if k != EN]
        self.lines = rest + [(EN, t) for t in lines]


class BlockFile:
    def __init__(self, path):
        self.path = Path(path)
        self.header, self.blocks, self.tag, self.limits = [], [], DEFAULT_TAG, {}
        cur = None
        for n, raw in enumerate(self.path.read_text(encoding='utf-8').splitlines(), 1):
            if raw.startswith('@'):
                ident, _, meta = raw[1:].strip().partition(' ')
                cur = Block(ident, meta.strip(), n)
                self.blocks.append(cur)
            elif cur is None:
                self.header.append(raw)
                m = re.match(r'#\s*limit\s+(.*)', raw)
                if m:
                    self.limits.update((k, int(v)) for k, v in re.findall(r'(\w+)=(\d+)', m.group(1)))
                m = re.match(r'#\s*tag\s+(\S+)', raw)
                if m:
                    self.tag = m.group(1)
            elif raw.startswith('#'):
                cur.lines.append(('#', raw))
            elif raw.strip() == '':
                continue
            else:
                tag, _, text = raw.partition(' ')
                if tag not in (self.tag, EN):
                    raise ValueError(f'{self.path}:{n}: line should start with "{self.tag} ", "{EN} ", "@" or "#"')
                cur.lines.append((tag, text))
        while self.header and not self.header[-1].strip():
            self.header.pop()
        ids = [b.id for b in self.blocks]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValueError(f'{self.path}: duplicate block ids {", ".join(sorted(dup))}')

    def source(self, block):
        return block.tagged(self.tag)

    def get(self, ident):
        return next((b for b in self.blocks if b.id == ident), None)

    def text(self):
        out = self.header + ['']
        for b in self.blocks:
            out.append(f'@ {b.id} {b.meta}'.rstrip())
            out += [t if k == '#' else f'{k} {t}' for k, t in b.lines]
            out.append('')
        return '\n'.join(out)

    def save(self, path=None):
        Path(path or self.path).write_text(self.text(), encoding='utf-8', newline='\n')


def merge(path, header, items, generated=None, quiet=False):
    """Write a dumped block file, keeping what people added to the existing one.

    header: the dump's header lines; items: [(id, meta, source lines, dump comment lines)] in the
    dump's order (comment lines include their '#'). From the existing file, if any, each block
    keeps its EN lines and the '#' lines the dump didn't write (before or after the dump's
    comments, as they were), and the header keeps lines the dump's header doesn't have.
    generated: a regex matching the dump's own comment lines whose content can change between
    dumps (re.compile(r'# (px|addr)=')) - old versions of those are dropped, not kept as hand
    notes. A
    block the dump no longer produces is kept at the end if it has English or hand comments,
    marked '# not in the latest dump'. Returns {'new': n, 'kept': n, 'orphans': [ids]}."""
    path = Path(path)
    old = BlockFile(path) if path.exists() else None
    bf = BlockFile.__new__(BlockFile)
    bf.path, bf.tag, bf.limits, bf.blocks = path, old.tag if old else DEFAULT_TAG, {}, []
    bf.header = list(header) + ([ln for ln in old.header if ln.strip() and ln not in header
                                 and not (generated and generated.match(ln))] if old else [])
    previous = {b.id: b for b in old.blocks} if old else {}
    seen, stats = set(), {'new': 0, 'kept': 0, 'orphans': []}
    for ident, meta, source, comments in items:
        b = Block(ident, meta, 0)
        b.lines = [('#', c) for c in comments] + [(bf.tag, t) for t in source]
        was = previous.get(ident)
        if was:
            before, after, dumped = [], [], False      # hand notes stay on their side of the dump's
            for k, t in was.lines:
                if k != '#' or t == ORPHAN:
                    continue
                if t in comments or (generated and generated.match(t)):
                    dumped = True
                else:
                    (after if dumped else before).append(t)
            b.lines = [('#', c) for c in before + list(comments) + after] + [(bf.tag, t) for t in source]
            b.english = was.english
            stats['kept'] += bool(was.english)
        else:
            stats['new'] += 1
        bf.blocks.append(b)
        seen.add(ident)
    for b in (old.blocks if old else []):
        if b.id not in seen and (b.english or any(k == '#' for k, _ in b.lines)):
            if ('#', ORPHAN) not in b.lines:
                b.lines.insert(0, ('#', ORPHAN))
            bf.blocks.append(b)
            stats['orphans'].append(b.id)
    bf.save()
    if not quiet and stats['orphans']:
        print(f'{path}: {len(stats["orphans"])} blocks no longer in the dump kept at the end '
              f'(marked "{ORPHAN}"): {", ".join(stats["orphans"][:8])}')
    return stats


ORPHAN = '# not in the latest dump'


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) >= 2 and argv[0] == 'show':
        bf = BlockFile(argv[1])
        for b in bf.blocks:
            if argv[2:] and b.id not in argv[2:]:
                continue
            print(f'@ {b.id} {b.meta}'.rstrip())
            for k, t in b.lines:
                print(t if k == '#' else f'{k} {t}')
            print()
    elif len(argv) >= 2 and argv[0] == 'stats':
        for p in argv[1:]:
            bf = BlockFile(p)
            done = sum(1 for b in bf.blocks if b.english)
            print(f'{p}: {done}/{len(bf.blocks)} translated')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
