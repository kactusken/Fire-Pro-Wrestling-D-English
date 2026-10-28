#!/usr/bin/env python3
"""The network mode's picture labels (/DPTEX/*.PVR atlases): draw the English, VQ-encode, build step.

  .venv/bin/python tools/dptex.py draw [ATLAS...]    labels of translation/text/dptex.csv drawn over
                                                     the original atlas -> translation/images-handmade/
                                                     dp_<atlas>.png, and review/edit/dp_<atlas>_compare.png
  .venv/bin/python tools/dptex.py encode [ATLAS...]  VQ-encode the picture the build uses (approved, else
                                                     hand-made) -> <same name>.pvr beside it
  python3 tools/dptex.py check                       which atlases are drawn, encoded, out of date

The DreamPassport 3 browser draws its buttons, titles and setting names from 512x512 VQ textures
(layout 3: a 256-entry codebook of 2x2 pixel blocks + one index byte per block, ARGB4444/1555),
cut into rectangles by the DPS layout files (`frame='tex:WxH+X+Y'`) and by the browser's code.
English keeps inside each label's box, which is the Japanese lettering's own area, so it shows
whatever rectangle the game cuts.

dptex.csv: one row per label - atlas, box `x,y,w,h`, japanese, english (empty: left as it is),
align (left/center/right, empty: the atlas default), repair, notes. A row with `repair` = `row N`
draws no text: it refills its box with row N of the original - for a strip of an icon that the
Japanese lettering covered (the English doesn't reach it). The style of each label is read from
the original pixels: lettering on a clear background (fill + outline colours) or on a plate
(the plate is repainted row by row, then the text drawn in the original's text colour).

VQ encoding needs numpy (k-means over the 2x2 blocks, started from the original codebook), so
it runs at edit time; the .pvr it writes is frozen beside the picture with the picture's SHA-1,
and the build (standard library only) copies it in, stopping if the picture changed since.
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import pvr  # noqa: E402

ATLASES = {  # atlas -> default align, what it holds
    'C_M_S': ('left', 'chat / mail / bookmark screen titles and field names'),
    'JYOUCYU0': ('center', 'dialog buttons (Yes/No/OK...), button hints, password titles'),
    'JYOUCYU1': ('center', 'the L-trigger menu and the mail/chat command buttons'),
    'OPTION01': ('center', 'option values, settings titles, Yes/No/OK buttons'),
    'OPTION02': ('center', 'network / provider / modem setting names'),
    'OPTION03': ('center', 'option page names and values'),
    'TAG_SU': ('left', 'network setup step titles'),
    'VMSPARTS': ('left', 'memory card (VM) file screen labels'),
    'SU_ICON': ('center', 'network setup choice panels (terms, save info, provider)'),
    'SU_ICO2': ('center', 'chat server choice panels'),
    'SKB_EISU': ('center', 'soft keyboard, letters: mode tabs and function keys (the keys stay)'),
    'SKB_KANA': ('center', 'soft keyboard, kana: mode tabs and function keys (kana, emoticon keys stay)'),
    'SKB_V102': ('center', 'soft keyboard, 102-key layout: function keys'),
}
PLAIN = {'SKB_EISU', 'SKB_KANA', 'SKB_V102'}    # one plain colour, no outline (the keys' lettering)
TABLE = 'dptex.csv'
FONT = 'NotoSans_SemiCondensed-Bold.ttf'
SYMBOL_FONT = 'DejaVuSans-Bold.ttf'      # ★ and other signs the main font lacks
CAP = 0.8        # English cap height / the Japanese lettering's height
FONT_DIRS = [Path(__file__).resolve().parent / 'fonts', Path('/mnt/c/Windows/Fonts'), Path('C:/Windows/Fonts'),
             Path('/usr/share/fonts/truetype/noto'), Path('/usr/share/fonts/truetype/dejavu')]
SQUEEZE_MIN = 0.72
VERSION = 1      # bump when drawing changes


def image_id(atlas):
    return 'dp_' + atlas.lower()


def disc_path(atlas):
    return f'/DPTEX/{atlas}.PVR'


def labels(atlas=None):
    p = paths.TEXT / TABLE
    with open(p, encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(ln for ln in f if not ln.startswith('#')))
    for r in rows:
        if r['atlas'] not in ATLASES:
            sys.exit(f'{TABLE}: unknown atlas {r["atlas"]!r} (tools/dptex.py ATLASES)')
        r['box'] = tuple(int(v) for v in r['box'].split(','))
    return [r for r in rows if atlas is None or r['atlas'] == atlas]


def final_png(atlas):
    """The picture the build uses (approved over hand-made), or None."""
    for d in (paths.APPROVED, paths.HANDMADE):
        p = d / f'{image_id(atlas)}.png'
        if p.exists():
            return p
    return None


def sha1(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- build (standard library only)

def frozen(atlas):
    """(bytes of the encoded .PVR, None) for the build, or (None, why not)."""
    png = final_png(atlas)
    if png is None:
        return None, 'not drawn'
    enc, meta = png.with_suffix('.pvr'), png.with_suffix('.pvr.json')
    if not enc.exists() or not meta.exists():
        return None, f'{png.name} is not encoded: .venv/bin/python tools/dptex.py encode {atlas}'
    if json.loads(meta.read_text())['png_sha1'] != sha1(png):
        return None, f'{png.name} changed since it was encoded: .venv/bin/python tools/dptex.py encode {atlas}'
    return enc.read_bytes(), None


def step(files):
    """Every drawn atlas into /DPTEX/ (same size as the original, in place)."""
    n = 0
    for atlas in ATLASES:
        data, why = frozen(atlas)
        if data is None:
            if why != 'not drawn':
                sys.exit(f'dptex: {why}')
            continue
        old = bytes(files.get(disc_path(atlas)))
        if len(data) != len(old):
            sys.exit(f'dptex: {atlas}.pvr is {len(data)} bytes, the original {len(old)}: encode it again')
        files.put(disc_path(atlas), data)
        n += 1
    return n


# ---------------------------------------------------------------- drawing (Pillow)

def original_image(atlas):
    d = (paths.EXTRACTED / disc_path(atlas).lstrip('/')).read_bytes()
    t = pvr.Texture(d, pvr.find(d)[0])
    return t, t.to_image()


def _font(size, name=FONT, cache={}):
    from PIL import ImageFont
    if (name, size) not in cache:
        p = next((d / name for d in FONT_DIRS if (d / name).exists()), None)
        if p is None:
            sys.exit(f'font {name} not found in {", ".join(map(str, FONT_DIRS))}: put it in tools/fonts/')
        cache[name, size] = ImageFont.truetype(str(p), size)
    return cache[name, size]


def _runs(text, size):
    """[(piece, font)]: characters the main font lacks go to the symbol font."""
    main, sym = _font(size), _font(size, SYMBOL_FONT)
    out = []
    for ch in text:
        f = main if ord(ch) < 0x2000 else sym
        if out and out[-1][1] is f:
            out[-1][0] += ch
        else:
            out.append([ch, f])
    return out


def _lum(c):
    return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def analyse(im, box):
    """Style of the lettering in box: {'plate': bool, 'fill', 'outline' or None, 'ink': (top, bottom)}."""
    from collections import Counter
    x, y, w, h = box
    px = [im.getpixel((x + i, y + j)) for j in range(h) for i in range(w)]
    opaque = [p for p in px if p[3] >= 200]
    edge = [im.getpixel((x + i, y + j)) for j in (0, h - 1) for i in range(w)] + \
           [im.getpixel((x + i, y + j)) for i in (0, w - 1) for j in range(h)]
    plate = sum(p[3] >= 200 for p in edge) > 0.8 * len(edge)
    if plate:
        bg = Counter(edge).most_common(1)[0][0]
        fill, outline = _plate_colours(im, box, bg)
    else:
        bright = [p for p in opaque if _lum(p) > 150]
        dark = [p for p in opaque if _lum(p) < 120]
        if bright:
            fill = Counter(bright).most_common(1)[0][0]
            outline = Counter(dark).most_common(1)[0][0] if len(dark) > 0.15 * len(bright) else None
        else:                       # dim lettering alone (the soft keyboards): its own colour, no outline
            fill = Counter(opaque).most_common(1)[0][0] if opaque else (255, 255, 255, 255)
            outline = None
    rows = [j for j in range(h) if any(_lum(im.getpixel((x + i, y + j))) > 0 and
                                         abs(_lum(im.getpixel((x + i, y + j))) - _lum(fill)) < 40 and
                                         im.getpixel((x + i, y + j))[3] >= 200 for i in range(w))]
    # the lettering's height: the tallest run of rows (gaps of a pixel allowed), so reading aids
    # above the kanji (furigana) don't count
    runs = []
    for j in rows:
        if runs and j - runs[-1][1] <= 2:
            runs[-1][1] = j
        else:
            runs.append([j, j])
    top, bottom = max(runs, key=lambda r: r[1] - r[0]) if runs else (2, h - 3)
    ink = (y + top, y + bottom + 1)
    return {'plate': plate, 'fill': fill, 'outline': outline, 'ink': ink}


def _plate_colours(im, box, bg):
    """(fill, outline or None) of lettering on a plate: the two strongest colours unlike the
    plate; the one that touches the plate is the outline."""
    from collections import Counter
    x, y, w, h = box
    px = {(i, j): im.getpixel((x + i, y + j)) for j in range(h) for i in range(w)}
    far = Counter(p for p in px.values() if _dist(p, bg) > 60)
    if not far:
        return (0, 0, 0, 255), None
    groups = []                                  # [(count, colour)] of distinct colours
    for c, n in far.most_common():
        for g in groups:
            if _dist(g[1], c) < 60:
                g[0] += n
                break
        else:
            groups.append([n, c])
    groups.sort(key=lambda g: -g[0])
    if len(groups) < 2 or groups[1][0] < 0.25 * groups[0][0]:
        return groups[0][1], None
    a, b = groups[0][1], groups[1][1]

    def touching(c):
        near = [k for k, p in px.items() if _dist(p, c) < 60]
        hit = sum(1 for (i, j) in near if any(_dist(px.get((i + di, j + dj), c), bg) < 40
                                              for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))))
        return hit / max(1, len(near))
    return (b, a) if touching(a) > touching(b) else (a, b)


def clear(im, box, style):
    """Erase the lettering: plates repainted row by row with the row's plate colour, clear
    backgrounds set to the box's most common see-through pixel (keeps the faint haze)."""
    from collections import Counter
    x, y, w, h = box
    if style['plate']:
        own = style.get('own', (style['fill'], style['outline']))     # the label's own colours
        text = [c for c in own + (style['fill'], style['outline']) if c]
        for j in range(h):
            row = [im.getpixel((x + i, y + j)) for i in range(w)]
            keep = [p for p in row if p[3] >= 200 and all(_dist(p, t) > 60 for t in text)]
            c = Counter(keep or row).most_common(1)[0][0]
            for i in range(w):
                im.putpixel((x + i, y + j), c)
    else:
        see = [im.getpixel((x + i, y + j)) for j in range(h) for i in range(w)]
        see = [p for p in see if p[3] < 128]
        c = Counter(see).most_common(1)[0][0] if see else (0, 0, 0, 0)
        for j in range(h):
            for i in range(w):
                im.putpixel((x + i, y + j), c)


def lettering(text, size, fill, outline, squeeze_to=None):
    """RGBA image of text (stroke 2 in the outline colour, if any)."""
    from PIL import Image, ImageDraw
    f = _font(size)
    sw = 2 if outline else 0
    runs = _runs(text, size)
    width = sum(rf.getlength(piece) for piece, rf in runs) + 2 * sw
    t = min(min(rf.getbbox(piece, stroke_width=sw)[1] for piece, rf in runs), f.getbbox('H', stroke_width=sw)[1])
    b = max(rf.getbbox(piece, stroke_width=sw)[3] for piece, rf in runs)
    im = Image.new('RGBA', (int(width) + 3, b - t + 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 1 + sw
    for piece, rf in runs:
        d.text((x, 1 - t), piece, font=rf, fill=tuple(fill), stroke_width=sw,
               stroke_fill=tuple(outline) if outline else None)
        x += rf.getlength(piece)
    return im, 1 - t + f.getbbox('H')[1]   # image, y of the cap top inside it


def repair(im, orig, row):
    """A `repair` row: refill its box with one clean row of the original (`row N`), for an
    icon edge the Japanese lettering covered (vertical edges stay continuous)."""
    x, y, w, h = row['box']
    src = int(row['repair'].split()[1])
    line = [orig.getpixel((x + i, src)) for i in range(w)]
    for j in range(h):
        for i in range(w):
            im.putpixel((x + i, y + j), line[i])


def place(im, row, default_align, jp_h, style):
    """Draw row's English into its box (jp_h: the Japanese lettering height of its group);
    returns a warning or None."""
    from PIL import Image
    box = row['box']
    x, y, w, h = box
    text = row['english']
    if not text:
        return None
    clear(im, box, style)
    cap = max(7, round(jp_h * CAP))
    warn = None
    for size in range(40, 6, -1):
        if _font(size).getbbox('H')[3] - _font(size).getbbox('H')[1] > cap:
            continue
        g, cap_top = lettering(text, size, style['fill'], style['outline'])
        if g.height > h + 2:
            continue
        if g.width <= w:
            break
        if g.width * SQUEEZE_MIN <= w:
            g = g.resize((w, g.height), Image.LANCZOS)
            break
    else:
        warn = f'{row["atlas"]} {box}: {text!r} does not fit'
    # vertical: the caps where the Japanese sat (centred on its ink), kept inside the box
    ink_mid = (style['ink'][0] + style['ink'][1]) / 2
    capsize = _font(size).getbbox('H')[3] - _font(size).getbbox('H')[1]
    top = round(ink_mid - capsize / 2) - cap_top
    top = max(y - 1, min(top, y + h - g.height + 1))
    align = row.get('align') or default_align
    if align == 'left':
        left = x
    elif align == 'right':
        left = x + w - g.width
    else:
        left = x + (w - g.width) // 2
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    layer.paste(g, (left, top))
    region = (x, y, x + w, y + h)
    base = im.crop(region)
    base.alpha_composite(layer.crop(region))
    im.paste(base, region[:2])
    return warn


def draw(atlases):
    from PIL import Image
    out_dir = paths.HANDMADE
    out_dir.mkdir(parents=True, exist_ok=True)
    review = paths.REVIEW / 'edit'
    review.mkdir(parents=True, exist_ok=True)
    for atlas in atlases:
        rows = labels(atlas)
        if not rows:
            continue
        _, orig = original_image(atlas)
        im = orig.copy()
        for r in rows:
            if r.get('repair'):
                repair(im, orig, r)
        rows = [r for r in rows if not r.get('repair')]
        styles = [analyse(orig, r['box']) for r in rows]
        # plate labels of one kind share a style: the commonest (fill, outline) of their size class
        # (lettering on a clear background keeps its own colours: some titles are orange on purpose)
        from collections import Counter
        kind = lambda r, st: (st['plate'], r['box'][3] >= 30)
        votes = {}
        for r, st in zip(rows, styles):
            if st['plate']:
                votes.setdefault(kind(r, st), Counter())[(st['fill'], st['outline'])] += 1
        if atlas in PLAIN:
            from collections import Counter as _C
            brown = _C(st['fill'] for st in styles if _lum(st['fill']) < 150).most_common(1)
            for r, st in zip(rows, styles):
                st['fill'], st['outline'] = (brown[0][0] if brown else st['fill']), None
                # dithered lettering: size and centre from the key itself (the lower part, under
                # any furigana)
                x, y, w, h = r['box']
                st['ink'] = (y + round(h * 0.25), y + round(h * 0.25) + round(min(h, 32) * 0.58))
        for r, st in zip(rows, styles):
            if st['plate']:
                st['own'] = (st['fill'], st['outline'])
                st['fill'], st['outline'] = votes[kind(r, st)].most_common(1)[0][0]
        groups = {}
        for r, st in zip(rows, styles):    # one lettering size per box height (the median Japanese)
            groups.setdefault(r['box'][3], []).append(st['ink'][1] - st['ink'][0])
        size_of = {k: sorted(v)[len(v) // 2] for k, v in groups.items()}
        warns = [w for w in (place(im, r, ATLASES[atlas][0], size_of[r['box'][3]], st)
                             for r, st in zip(rows, styles)) if w]
        p = out_dir / f'{image_id(atlas)}.png'
        im.save(p)
        sheet = Image.new('RGBA', (1024, 512), (24, 24, 48, 255))
        sheet.alpha_composite(orig, (0, 0))
        sheet.alpha_composite(im, (512, 0))
        sheet.save(review / f'{image_id(atlas)}_compare.png')
        print(f'{paths.show(p)}: {sum(1 for r in rows if r["english"])} labels' +
              ''.join(f'\n  warning: {w}' for w in warns))


# ---------------------------------------------------------------- VQ encoding (numpy)

def encode(atlases, iterations=12):
    import numpy as np
    from PIL import Image
    for atlas in atlases:
        png = final_png(atlas)
        if png is None:
            print(f'{atlas}: not drawn')
            continue
        t, _ = original_image(atlas)
        if t.layout != 3 or t.w != t.h:
            sys.exit(f'{atlas}: layout {t.layout:#x} is not square VQ')
        n = t.w
        a = np.asarray(Image.open(png).convert('RGBA'), dtype=np.float64)
        if a.shape[:2] != (n, n):
            sys.exit(f'{png}: {a.shape[1]}x{a.shape[0]}, the texture is {n}x{n}')
        # 2x2 blocks in codebook order (0,0) (0,1) (1,0) (1,1) - x slow; premultiplied alpha
        al = a[:, :, 3:4] / 255
        pm = np.concatenate([a[:, :, :3] * al, a[:, :, 3:4]], axis=2)
        blocks = np.stack([pm[0::2, 0::2], pm[1::2, 0::2], pm[0::2, 1::2], pm[1::2, 1::2]], axis=2)
        vecs = blocks.reshape(-1, 16)
        uniq, inverse, counts = np.unique(vecs, axis=0, return_inverse=True, return_counts=True)
        inverse = inverse.reshape(-1)
        # start from the original codebook (decoded, premultiplied)
        d = t.data
        book = np.array([[c for j in range(4) for c in
                          _premul(pvr.rgba(int.from_bytes(d[t.body + 8 * k + 2 * j:t.body + 8 * k + 2 * j + 2],
                                                          'little'), t.pixel))]
                         for k in range(256)], dtype=np.float64)
        w = counts.astype(np.float64)
        for _ in range(iterations):
            lab = _nearest(uniq, book)
            for k in range(256):
                m = lab == k
                if m.any():
                    book[k] = (uniq[m] * w[m, None]).sum(0) / w[m].sum()
            # empty codes take the worst-served blocks
            used = np.bincount(lab, minlength=256)
            if (used == 0).any():
                err = ((uniq - book[lab]) ** 2).sum(1) * w
                worst = np.argsort(-err)
                for k, b in zip(np.nonzero(used == 0)[0], worst):
                    book[k] = uniq[b]
        # quantize the codebook to the pixel format, then the final assignment against it
        codes = [[pvr.to_px(_unpremul(book[k, 4 * j:4 * j + 4]), t.pixel) for j in range(4)] for k in range(256)]
        qbook = np.array([[c for px in code for c in _premul(pvr.rgba(px, t.pixel))] for code in codes], dtype=np.float64)
        lab = _nearest(uniq, qbook)[inverse]
        idx = lab.reshape(n // 2, n // 2)          # [by, bx]
        out = bytearray(d)
        for k, code in enumerate(codes):
            for j, px in enumerate(code):
                out[t.body + 8 * k + 2 * j:t.body + 8 * k + 2 * j + 2] = px.to_bytes(2, 'little')
        p = t.data_start()
        for by in range(n // 2):
            for bx in range(n // 2):
                out[p + pvr.tw(bx, by)] = int(idx[by, bx])
        enc = png.with_suffix('.pvr')
        enc.write_bytes(bytes(out))
        # error report: decoded vs the drawn picture
        dec = np.asarray(pvr.Texture(bytes(out), t.off).to_image(), dtype=np.float64)
        diff = np.abs(dec - a)[a[:, :, 3] > 0].mean() if (a[:, :, 3] > 0).any() else 0
        png.with_suffix('.pvr.json').write_text(json.dumps({'png_sha1': sha1(png), 'version': VERSION,
                                                            'mean_abs_error': round(float(diff), 2)}))
        print(f'{paths.show(enc)}: {len(uniq)} distinct blocks -> 256 codes, mean error {diff:.1f}')


def _premul(c):
    r, g, b, a = c
    return [r * a / 255, g * a / 255, b * a / 255, a]


def _unpremul(v):
    r, g, b, a = (float(x) for x in v)
    if a <= 0.5:
        return 0, 0, 0, 0
    return tuple(int(max(0, min(255, round(x)))) for x in (r * 255 / a, g * 255 / a, b * 255 / a, a))


def _nearest(vecs, book, chunk=4096):
    import numpy as np
    bb = (book ** 2).sum(1)
    out = np.empty(len(vecs), dtype=np.int64)
    for i in range(0, len(vecs), chunk):
        v = vecs[i:i + chunk]
        out[i:i + chunk] = np.argmin(bb[None, :] - 2 * v @ book.T, axis=1)
    return out


def check():
    for atlas in ATLASES:
        png = final_png(atlas)
        _, why = frozen(atlas)
        print(f'{atlas:9} {len(labels(atlas)):4} labels  {paths.show(png) if png else "-":50} {why or "encoded"}')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ('draw', 'encode', 'check'):
        print(__doc__)
        return 1
    names = [a.upper() for a in argv[1:]] or [a for a in ATLASES if labels(a)]
    bad = [a for a in names if a not in ATLASES]
    if bad:
        sys.exit(f'unknown atlas {bad} (known: {", ".join(ATLASES)})')
    if argv[0] == 'draw':
        draw(names)
    elif argv[0] == 'encode':
        encode(names)
    else:
        check()
    return 0


if __name__ == '__main__':
    sys.exit(main())
