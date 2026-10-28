#!/usr/bin/env python3
"""Two-letter glyphs: common letter pairs drawn as one glyph, so English needs fewer glyphs where
the game counts room in glyphs (one cell or sprite per character) - GAME-SPECIFIC hooks below.

  pairs.py choose [--write] [--count N]   pick the pairs that save the most glyphs in the English
                                          -> translation/text/pairs.txt
  pairs.py stats                          glyphs the English needs with and without the pairs
  pairs.py sheet PNG                      every pair's bitmap, 4x, to check by eye

When: English needs about twice the glyphs of Japanese, and room is counted in glyphs - a text
object's glyph list, VDP1 cells, OAM sprites, tiles per name. If the glyph cell is wider than
two narrow letters (Fire Pro Wrestling S: 12 px font, 16 px cells), a pair fits one cell and
text looks unchanged when its advance is the sum of its letters'. That game needed 67% of the
glyphs with 188 pairs. The build then needs: the pair bitmaps in the font (or a hook in front of
the glyph unpacker), codes nothing else uses, the width table entries, and the text encoder
using runs() - see platforms/saturn/PLATFORM.md "Text drawn as VDP1 sprites".

Fill in (GAME-SPECIFIC):
  CELL_W         the cell width a pair must fit in (pixels; leave room for bold/outline)
  PAIR_COUNT     how many codes the game has free for pairs
  letters()      {character: (rows, advance)} - each glyph's rows as ints, MSB = left pixel, in a
                 field of CELL_W bits, and its advance in pixels. From the game's font.
  corpus()       the English the build writes (default: every translated entry, all variants)
Generic: fits(), bitmap(), runs() (the fewest glyphs for a run of letters), choose(), count().
pairs.txt: one pair per line in code order (lines starting with # are comments); the build reads
it, so changing the list changes the codes - rebuild everything after.
"""
import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

CELL_W = 16          # GAME-SPECIFIC: the glyph cell's width in pixels
PAIR_COUNT = 0       # GAME-SPECIFIC: free codes for pairs


def letters():
    """GAME-SPECIFIC: {character: (rows, advance)}: rows of ints (MSB = leftmost pixel of a
    CELL_W-bit field), advance in pixels - read from the game's font."""
    raise SystemExit('pairs.py: fill in letters() (and CELL_W, PAIR_COUNT) from the game\'s font')


def corpus():
    """The English the build writes; override when names or variants expand (e.g. both name builds)."""
    import textdb
    return [e.english for e in textdb.entries() if e.english]


# ------------------------------------------------------------------ generic

def file():
    return paths.TEXT / 'pairs.txt'


def table():
    """[pair] in code order (empty if there's no pairs.txt)."""
    p = file()
    if not p.exists():
        return []
    return [ln[:2] for ln in p.read_text(encoding='utf-8').splitlines() if len(ln) >= 2 and not ln.startswith('#')]


def ink(rows):
    """(first, last) inked column of a glyph, or None if it is blank."""
    acc = 0
    for r in rows:
        acc |= r
    cols = [x for x in range(CELL_W) if acc & (1 << (CELL_W - 1 - x))]
    return (cols[0], cols[-1]) if cols else None


def fits(pair, font):
    """Does the pair's ink, second letter at the first's advance, stay inside the cell?"""
    a, b = (font.get(c) for c in pair)
    if not a or not b:
        return False
    span = ink(b[0])
    return span is None or a[1] + span[1] < CELL_W


def bitmap(pair, font):
    """The pair's rows: first letter at x=0, second at the first's advance."""
    (ra, adv), (rb, _) = font[pair[0]], font[pair[1]]
    mask = (1 << CELL_W) - 1
    return [(a | (b >> adv)) & mask for a, b in zip(ra, rb)]


def runs(text, known):
    """Split text into the fewest glyphs: [(piece, is_pair)] - a pair wherever one in `known` saves
    a glyph (dynamic programming, so 'tion' takes 'ti'+'on', not 't'+'io'+'n')."""
    n = len(text)
    best, step = [0] + [10 ** 9] * n, [0] * (n + 1)
    for i in range(1, n + 1):
        best[i], step[i] = best[i - 1] + 1, 1
        if i >= 2 and text[i - 2:i] in known and best[i - 2] + 1 <= best[i]:
            best[i], step[i] = best[i - 2] + 1, 2
    out, i = [], n
    while i > 0:
        out.append((text[i - step[i]:i], step[i] == 2))
        i -= step[i]
    return out[::-1]


def letter_runs(text, font):
    """Runs of characters the font has as letters (codes and other characters break a run)."""
    run = ''
    for c in text:
        if c in font and c != ' ':
            run += c
        else:
            if run:
                yield run
            run = ''
    if run:
        yield run


def count(text, known, font):
    """Glyphs the text needs with these pairs (characters outside the font count one each)."""
    n = sum(1 for c in text if c not in font and not c.isspace())
    return n + sum(len(runs(r, known)) for r in letter_runs(text, font))


def choose(font, n):
    """The n pairs that save the most glyphs over the corpus."""
    candidates = {a + b for a in font for b in font if a != ' ' and b != ' ' and fits(a + b, font)}
    used = collections.Counter()
    for t in corpus():
        for r in letter_runs(t, font):
            for piece, is_pair in runs(r, candidates):
                if is_pair:
                    used[piece] += 1
    return [p for p, _ in used.most_common(n)]


def sheet(path, font, pairs):
    import pngio
    scale, cols = 4, 16
    h = max(len(font[p[0]][0]) for p in pairs)
    W, H = cols * (CELL_W + 2) * scale, ((len(pairs) + cols - 1) // cols) * (h + 2) * scale
    rows = [[0] * W for _ in range(H)]
    for i, p in enumerate(pairs):
        x0, y0 = (i % cols) * (CELL_W + 2) * scale, (i // cols) * (h + 2) * scale
        for y, r in enumerate(bitmap(p, font)):
            for x in range(CELL_W):
                v = 1 if r & (1 << (CELL_W - 1 - x)) else 2
                for dy in range(scale):
                    for dx in range(scale):
                        rows[y0 + y * scale + dy][x0 + x * scale + dx] = v
    pngio.write(path, rows, [(24, 24, 32), (255, 255, 255), (60, 60, 80)])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('choose')
    p.add_argument('--write', action='store_true')
    p.add_argument('--count', type=int)
    sub.add_parser('stats')
    p = sub.add_parser('sheet')
    p.add_argument('png')
    a = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    font = letters()
    if a.cmd == 'stats':
        known = set(table())
        before = sum(count(t, set(), font) for t in corpus())
        after = sum(count(t, known, font) for t in corpus())
        print(f'{len(known)} pairs: {after} glyphs instead of {before} ({after / max(before, 1):.0%})')
    elif a.cmd == 'sheet':
        sheet(a.png, font, table())
        print(f'{a.png}: {len(table())} pairs')
    else:
        chosen = choose(font, a.count or PAIR_COUNT)
        if a.write:
            file().write_text('# Two-letter glyphs (tools/pairs.py choose --write), one per line in code order.\n'
                              '# Changing the list changes the codes: rebuild everything after.\n'
                              + '\n'.join(chosen) + '\n', encoding='utf-8')
            print(f'{paths.show(file())}: {len(chosen)} pairs')
        else:
            print(' '.join(chosen))


if __name__ == '__main__':
    main()
