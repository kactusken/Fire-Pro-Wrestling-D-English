#!/usr/bin/env python3
"""Guess the characters of a game's font by comparing every glyph with Japanese fonts (research;
Pillow and numpy: run with .venv/bin/python).

  fontid.py SHEET.png --cell 12x12 OUT.tsv [--first 0x2000] [--step 1] [--set jis|half|both]
            [--ordered] [--invert] [--ttf FILE:SIZE ...]

SHEET.png is the font as a grid of glyph cells, left to right and top to bottom - export it with
the platform's graphics tools (tools/snesgfx.py, tim.py, tim2.py, gfx.py) or a script that draws
the game's own glyph layout. Light pixels are ink (--invert for dark ink on light). Cell n gets
the code --first + n * --step; blank and solid cells are skipped.

Each glyph is compared, with small shifts, against every candidate character drawn by several
Japanese TrueType fonts (Windows' MS Gothic/Mincho, BIZ UD, Yu Gothic from /mnt/c/Windows/Fonts;
--ttf adds others): --set jis is full-width JIS X 0208 (kana, kanji, symbols), half is ASCII and
half-width katakana, both is both.

  default    per glyph the best guess and the next four (fonts stored in order of first use)
  --ordered  the best strictly increasing assignment over the whole font (fonts that hold their
             characters in JIS order): much more accurate when it applies; glyphs that match
             nothing well get '?' (e.g. two-letter glyphs like 'Yu')

OUT.tsv: code, character, score (0-1; below about 0.5 check by eye), other guesses. It is a
start for the game's table (tools/tbl.py on cartridges): check every low score by eye.
From Bishoujo Wrestler Retsuden (16x16, JIS order) and Jikkyou Power Pro Wrestling '96 (12x12 and
8x12, order of first use).
"""
import argparse
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    sys.exit("needs Pillow and numpy: .venv/bin/pip install numpy, then run with .venv/bin/python")

WINDOWS_FONTS = Path('/mnt/c/Windows/Fonts')
FACES = ['msgothic.ttc', 'msmincho.ttc', 'BIZ-UDGothicR.ttc', 'BIZ-UDGothicB.ttc', 'YuGothM.ttc', 'BIZ-UDMinchoM.ttc']


def jis_chars():
    out = []
    for hi in list(range(0x81, 0xa0)) + list(range(0xe0, 0xeb)):
        for lo in range(0x40, 0xfd):
            if lo == 0x7f:
                continue
            try:
                out.append(bytes([hi, lo]).decode('shift_jis'))
            except UnicodeDecodeError:
                pass
    return out


def half_chars():
    return [chr(c) for c in range(0x21, 0x7f)] + [chr(c) for c in range(0xff61, 0xffa0)]


def cells(sheet, w, h, invert):
    im = Image.open(sheet).convert('L')
    a = np.asarray(im, np.float32) / 255
    if invert:
        a = 1 - a
    a = (a > 0.5).astype(np.float32)
    return [a[y:y + h, x:x + w] for y in range(0, im.height - h + 1, h) for x in range(0, im.width - w + 1, w)]


def centre(a):
    ys, xs = np.nonzero(a > 0.5)
    if not len(xs):
        return a
    h, w = a.shape
    return np.roll(np.roll(a, (h - 1 - ys.max() - ys.min()) // 2, 0), (w - 1 - xs.max() - xs.min()) // 2, 1)


def feature(a):
    im = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    v = np.asarray(im, np.float32).ravel() / 255
    v = v - v.mean()
    n = np.linalg.norm(v)
    return v / n if n else v


def render(ch, w, h, font, bitmap):
    im = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(im)
    if bitmap:
        d.fontmode = '1'
    bb = d.textbbox((0, 0), ch, font=font)
    d.text(((w - (bb[2] - bb[0])) // 2 - bb[0], (h - (bb[3] - bb[1])) // 2 - bb[1]), ch, font=font, fill=255)
    return np.asarray(im, np.float32) / 255


def renders(extra, h):
    out = [(str(WINDOWS_FONTS / f), s) for f in FACES for s in (h, h + 2) if (WINDOWS_FONTS / f).is_file()]
    for spec in extra:
        path, _, size = spec.rpartition(':')
        out.append((path, int(size)))
    if not out:
        sys.exit('no Japanese fonts found: give --ttf FILE:SIZE (a font with kana and kanji)')
    return out


def scores(glyphs, chars, w, h, fonts):
    """glyphs x chars: the best cosine similarity over fonts and shifts."""
    shifted = [np.stack([feature(np.roll(np.roll(centre(g), dy, 0), dx, 1)) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
               for g in glyphs]
    S = np.full((len(glyphs), len(chars)), -1.0, np.float32)
    for path, size in fonts:
        f = ImageFont.truetype(path, size)
        C = np.stack([feature(centre(render(ch, w, h, f, 'ms' in Path(path).name))) for ch in chars])
        for i, G in enumerate(shifted):
            S[i] = np.maximum(S[i], (G @ C.T).max(0))
    return S


def ordered(S, skip=0.2):
    """The best strictly increasing assignment: {glyph index: char index or None}."""
    ng, nj = S.shape
    best = np.full((ng + 1, nj + 1), -1e9, np.float32)
    best[0, :] = 0
    back = np.zeros((ng + 1, nj + 1), np.int8)       # 1 matched at j-1, 2 carried from j-1, 3 skipped
    for i in range(1, ng + 1):
        row = best[i - 1]
        m = np.full(nj + 1, -1e9, np.float32)
        m[1:] = row[:-1] + S[i - 1]
        sk = row + skip
        cur = np.maximum(m, sk)
        how = np.where(m >= sk, 1, 3).astype(np.int8)
        acc = np.maximum.accumulate(cur)
        how[acc > cur] = 2
        best[i], back[i] = acc, how
    res, i, j = {}, ng, nj
    while i > 0:
        h = back[i, j]
        if h == 2:
            j -= 1
        elif h == 1:
            res[i - 1] = j - 1
            i, j = i - 1, j - 1
        else:
            res[i - 1] = None
            i -= 1
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('sheet', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--cell', required=True, help='glyph cell size, e.g. 12x12 or 8x12')
    ap.add_argument('--first', type=lambda s: int(s, 0), default=0, help='code of the first cell')
    ap.add_argument('--step', type=lambda s: int(s, 0), default=1, help='code step per cell')
    ap.add_argument('--set', choices=('jis', 'half', 'both'), default='jis')
    ap.add_argument('--ordered', action='store_true', help='the font holds its characters in JIS order')
    ap.add_argument('--invert', action='store_true', help='dark ink on a light ground')
    ap.add_argument('--ttf', action='append', default=[], metavar='FILE:SIZE', help='another font to compare with')
    a = ap.parse_args(argv)
    w, h = (int(x) for x in a.cell.lower().split('x'))
    all_cells = cells(a.sheet, w, h, a.invert)
    keep = [i for i, g in enumerate(all_cells) if 0 < g.sum() < 0.8 * w * h]    # blank and solid cells skipped
    chars = (jis_chars() if a.set != 'half' else []) + (half_chars() if a.set != 'jis' else [])
    S = scores([all_cells[i] for i in keep], chars, w, h, renders(a.ttf, h))
    rows = {}
    if a.ordered:
        for k, j in ordered(S).items():
            rows[keep[k]] = (chars[j], float(S[k, j]), '') if j is not None else ('?', float(S[k].max()), '')
    else:
        for k in range(len(keep)):
            top = np.argsort(-S[k])[:5]
            rows[keep[k]] = (chars[top[0]], float(S[k, top[0]]), ' '.join(f'{chars[t]}{S[k, t]:.2f}' for t in top[1:]))
    with open(a.out, 'w', encoding='utf-8') as f:
        for n, g in enumerate(all_cells):
            ch, sc, more = rows.get(n, (' ' if g.sum() == 0 else '■', 1.0, ''))
            f.write(f'{a.first + n * a.step:04X}\t{ch}\t{sc:.2f}\t{more}\n'.replace('\t\n', '\n'))
    low = sum(1 for v in rows.values() if v[1] < 0.5)
    print(f'{a.out}: {len(all_cells)} cells, {len(keep)} glyphs compared, {low} below 0.5 (check by eye)')


if __name__ == '__main__':
    main()
