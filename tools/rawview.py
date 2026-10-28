#!/usr/bin/env python3
"""Look at raw data as pictures before its format is known (research; needs Pillow: run with
.venv/bin/python). The first step of the image inventory when nothing exports the images yet.

  rawview.py view FILE [--offset N] [--length N] [--bpp 4] [--width W|auto] [--tiles 8 [--per-row 32]]
                 [--palette FILE[@OFFSET]] [--rgb555 be|le] [--nibbles hi|lo] [--scale 2] [--out PNG]
  rawview.py scan FILE|FOLDER... [--bpp 4,8] [--min-size 2048] [--out DIR]
                 contact sheets: every file (every file of a folder, recursively) at each depth,
                 linear at its likeliest width and as 8x8 tiles, labelled -> DIR/scan_NN.png

View modes: linear (rows of W pixels; --width auto takes the width at which rows line up best,
compared with the strides beside it) or tiles (--tiles 8: 8x8 cells, --per-row cells across). Depths: 1, 2, 4
(--nibbles hi = the high nibble is the left pixel, as on Saturn; lo for PS1/PS2), 8, 16 (RGB555,
--rgb555 be on Saturn, le on PS1/SNES/PS2; bit 15 = transparent/STP is ignored). SNES planar
tiles: tools/snesgfx.py. Without --palette, indices show as greys; with it, colours are read as
RGB555 from FILE at OFFSET (--rgb555 sets the byte order) - a palette found next to the data or
in a savestate's colour RAM.

What to look for: text appears as clean horizontal strokes at the right width; a wrong width
shears it, a wrong depth doubles or halves it. Once a picture with text is found, write its
reader in tools/gfx.py (export_all) so it gets an id, a row in graphics.csv and the normal image
workflow (FRAMEWORK.md section 9). Compressed data looks like noise at every width: find the
decompressor first.
"""
import argparse
import struct
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("rawview: needs Pillow - run it with the project's .venv/bin/python")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402


def values(data, bpp, nibbles='hi'):
    """Pixel values of the data, in order."""
    if bpp == 8:
        return list(data)
    if bpp == 16:
        return None
    per = 8 // bpp
    mask = (1 << bpp) - 1
    out = []
    for b in data:
        shifts = range(8 - bpp, -1, -bpp) if nibbles == 'hi' else range(0, 8, bpp)
        out += [(b >> s) & mask for s in shifts]
    return out[:len(data) * per]


def rgb555(v):
    return ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3)


def palette(spec, bpp, endian='be'):
    n = 1 << bpp if bpp <= 8 else 0
    if not spec:
        return [(i * 255 // max(n - 1, 1),) * 3 for i in range(n)]
    f, _, off = spec.partition('@')
    raw = Path(f).read_bytes()[int(off, 0) if off else 0:]
    fmt = '>' if endian == 'be' else '<'
    cols = [rgb555(struct.unpack_from(fmt + 'H', raw, 2 * i)[0]) for i in range(min(n, len(raw) // 2))]
    return cols + [(255, 0, 255)] * (n - len(cols))


def linear(data, width, bpp, pal, nibbles='hi', endian='be'):
    if bpp == 16:
        fmt = '>' if endian == 'be' else '<'
        px = [rgb555(v) for v in struct.unpack(f'{fmt}{len(data) // 2}H', data[:len(data) // 2 * 2])]
    else:
        px = [pal[v] for v in values(data, bpp, nibbles)]
    h = len(px) // width
    im = Image.new('RGB', (width, max(h, 1)))
    im.putdata(px[:width * h] or [(0, 0, 0)])
    return im


def tiles(data, bpp, pal, size=8, per_row=32, nibbles='hi'):
    vals = values(data, bpp, nibbles)
    if vals is None:
        raise SystemExit('rawview: tiles need a palette depth (1, 2, 4 or 8)')
    cell = size * size
    n = len(vals) // cell
    rows = (n + per_row - 1) // per_row
    im = Image.new('RGB', (per_row * size, max(rows, 1) * size))
    px = im.load()
    for t in range(n):
        tx, ty = (t % per_row) * size, (t // per_row) * size
        for i in range(cell):
            px[tx + i % size, ty + i // size] = pal[vals[t * cell + i]]
    return im


def _diff(data, stride, n=4096):
    """Share of bytes that differ from the byte `stride` later (over the first n)."""
    n = min(n, len(data) - stride)
    return sum(1 for i in range(n) if data[i] != data[i + stride]) / max(n, 1)


def best_widths(data, bpp, widths=range(8, 1032, 8), top=3):
    """Likeliest widths for linear data: rows line up at the true width much better than at a
    stride one byte off either side (any narrow stride looks alike in a smooth picture, so plain
    row similarity picks the narrowest)."""
    out = []
    for w in widths:
        bw = w * bpp // 8
        if bw < 2 or len(data) < bw * 9:
            continue
        here = _diff(data, bw)
        around = (_diff(data, bw - 1) + _diff(data, bw + 1)) / 2
        out.append((here / around if around else 1, w))
    return [w for _, w in sorted(out)[:top]]


def sheet_pages(items, out, prefix, width=1100, height=1500):
    """[(label, image)] -> pages of labelled images; returns the paths."""
    pages, x, y, rowh = [], 0, 0, 0
    page = Image.new('RGB', (width, height), (36, 36, 44))
    draw = ImageDraw.Draw(page)
    for label, im in items:
        if im.width <= 260 and im.height <= 200:
            im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
        if im.width > width - 8:
            im = im.resize((width - 8, max(1, im.height * (width - 8) // im.width)), Image.NEAREST)
        im = im.crop((0, 0, im.width, min(im.height, height - 30)))
        w, h = max(im.width, 6 * len(label)) + 8, im.height + 16
        if x + w > width:
            x, y, rowh = 0, y + rowh, 0
        if y + h > height:
            pages.append(page)
            page = Image.new('RGB', (width, height), (36, 36, 44))
            draw = ImageDraw.Draw(page)
            x = y = rowh = 0
        draw.text((x + 2, y + 2), label, fill=(255, 220, 90))
        page.paste(im, (x + 2, y + 14))
        x, rowh = x + w, max(rowh, h)
    pages.append(page.crop((0, 0, width, max(1, y + rowh + 4))))
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for i, p in enumerate(pages, 1):
        f = out / f'{prefix}_{i:02d}.png'
        p.save(f)
        files.append(f)
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('view')
    p.add_argument('file')
    p.add_argument('--offset', type=lambda v: int(v, 0), default=0)
    p.add_argument('--length', type=lambda v: int(v, 0))
    p.add_argument('--bpp', type=int, default=4)
    p.add_argument('--width', default='auto')
    p.add_argument('--tiles', type=int)
    p.add_argument('--per-row', type=int, default=32)
    p.add_argument('--palette')
    p.add_argument('--rgb555', choices=('be', 'le'), default='be')
    p.add_argument('--nibbles', choices=('hi', 'lo'), default='hi')
    p.add_argument('--scale', type=int, default=2)
    p.add_argument('--out')
    p = sub.add_parser('scan')
    p.add_argument('paths', nargs='+')
    p.add_argument('--bpp', default='4,8')
    p.add_argument('--min-size', type=int, default=2048)
    p.add_argument('--nibbles', choices=('hi', 'lo'), default='hi')
    p.add_argument('--out')
    a = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    if a.cmd == 'view':
        data = Path(a.file).read_bytes()[a.offset:]
        data = data[:a.length] if a.length else data
        pal = palette(a.palette, a.bpp, a.rgb555)
        if a.tiles:
            im = tiles(data, a.bpp, pal, a.tiles, a.per_row, a.nibbles)
        else:
            w = best_widths(data, a.bpp, top=1)[0] if a.width == 'auto' else int(a.width)
            print(f'width {w}' + (' (auto)' if a.width == 'auto' else ''))
            im = linear(data, w, a.bpp, pal, a.nibbles, a.rgb555)
        im = im.resize((im.width * a.scale, im.height * a.scale), Image.NEAREST)
        out = Path(a.out or paths.WORK / 'rawview' / f'{Path(a.file).name}_{a.offset:x}_{a.bpp}bpp.png')
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out)
        print(paths.show(out))
        return 0
    files = []
    for p in map(Path, a.paths):
        files += sorted(f for f in p.rglob('*') if f.is_file()) if p.is_dir() else [p]
    files = [f for f in files if f.stat().st_size >= a.min_size]
    items = []
    for f in files:
        data = f.read_bytes()[:256 << 10]
        for bpp in map(int, a.bpp.split(',')):
            pal = palette(None, bpp)
            for w in best_widths(data, bpp, top=1):
                items.append((f'{f.name} {bpp}bpp w{w}', linear(data[:w * bpp // 8 * 256], w, bpp, pal, a.nibbles)))
            items.append((f'{f.name} {bpp}bpp 8x8 tiles', tiles(data[:8 * 8 * bpp // 8 * 32 * 24], bpp, pal, 8, 32, a.nibbles)))
    out = Path(a.out or paths.WORK / 'rawview')
    pages = sheet_pages(items, out, 'scan')
    print(f'{len(files)} files, {len(items)} views on {len(pages)} pages in {paths.show(out)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
