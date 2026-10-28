#!/usr/bin/env python3
"""Game images: export the pictures with text and import the English ones (Fire Pro Wrestling D).

export_all(extracted, out) -> count
    Every image in IMAGES as out/<id>.png (RGBA - the textures are 16-bit colour, no palette)
    plus out/<id>.json with its location.
import_images(images, files) -> count
    {id: PNG} into SBL.BIN: each PNG (RGBA, the original's size) is converted to the texture's
    pixel format and layout, the texture's LZSS stream is rebuilt, the entry's container table
    is updated, and the entry written back (tools/sbl.py moves it if it outgrows its slot).

Where pictures live (verified 2026-10-27): SBL.BIN entries hold PVR textures (tools/pvr.py),
either the whole entry LZSS-compressed (198, 206: one texture each), or a container: a table of
(offset/4, size/4) pairs up to the first offset, each item a separate LZSS stream (238: the main
menu labels are item 2, the wrestler profile tags item 3). Only square twiddled textures
(layout 1) are imported - VQ would need an encoder.

No dependencies here: build.py must run on a plain python3 (tools/pngio.py reads PNGs).
"""
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lzss  # noqa: E402
import pngio  # noqa: E402
import pvr  # noqa: E402
import sbl  # noqa: E402

# id: (SBL entry, container item or None for a whole-entry LZSS stream, what it shows)
IMAGES = {
    'menu_modes': (238, 2, 'main menu: the 11 mode labels'),
    'profile_tags': (238, 3, 'wrestler select: profile tags (name, nickname, finisher, ...), 1P-4P marks'),
    'elim_order': (196, None, 'elimination match: team order boards'),
    'army_labels': (238, 38, 'elimination team (Edit Army): position labels, Absent, Next Battle'),
    'result_words': (198, None, 'results: 制覇 / 優勝 / 勝利'),
    'title_result': (206, None, 'title match result: タイトル奪取 / タイトル防衛'),
}


# Other places holding the same texture (verified by pixel match, 2026-10-28): written too.
COPIES = {
    'result_words': [(244, 1), (245, 1), (246, 1), (247, 1)],   # Victory Road championship screens
}


def container(data):
    """[(offset, size)] of a container entry, or None if it isn't one."""
    first = struct.unpack_from('<I', data, 0)[0] * 4
    if not 8 <= first <= 0x2000 or first % 8:
        return None
    items = []
    for i in range(0, first, 8):
        o, s = struct.unpack_from('<II', data, i)
        items.append((o * 4, s * 4))
    if any(o + s > len(data) for o, s in items):
        return None
    return items


def rebuild(items):
    """A container from item blobs (each padded to 4 bytes)."""
    n = len(items)
    out = bytearray(n * 8)
    for k, b in enumerate(items):
        b = bytes(b) + bytes(-len(b) % 4)
        struct.pack_into('<II', out, k * 8, len(out) // 4, len(b) // 4)
        out += b
    return bytes(out)


def _texture_data(entry_data, item):
    """(decompressed texture data, LZ blob, items or None) for an image location."""
    if item is None:
        return lzss.decompress(entry_data), entry_data, None
    items = container(entry_data)
    o, s = items[item]
    blob = entry_data[o:o + s]
    return lzss.decompress(blob), blob, items


def _png_rgba(path):
    p = pngio.read(path)
    if p.palette:
        rows = [[tuple(p.palette[v]) + ((p.alpha[v] if p.alpha and v < len(p.alpha) else 255),) for v in r]
                for r in p.rows]
    else:
        rows = [[px if len(px) == 4 else tuple(px) + (255,) for px in r] for r in p.rows]
    return p.width, p.height, rows


def _write_rgba_png(path, w, h, pixels):
    raw = b''.join(b'\0' + bytes(c for px in pixels[y * w:(y + 1) * w] for c in px) for y in range(h))

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def export_all(extracted, out):
    s = sbl.Sbl((Path(extracted) / 'SBL.BIN').read_bytes())
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for name, (entry, item, what) in IMAGES.items():
        dec, _, _ = _texture_data(s.get(entry), item)
        t = pvr.Texture(dec, pvr.find(dec)[0])
        _write_rgba_png(out / f'{name}.png', t.w, t.h, t.decode())
        (out / f'{name}.json').write_text(json.dumps({'entry': entry, 'item': item, 'what': what,
                                                      'format': t.describe()}))
        n += 1
    import dptex                      # the network mode's label atlases (files in /DPTEX/)
    for atlas, (_, what) in dptex.ATLASES.items():
        d = (Path(extracted) / dptex.disc_path(atlas).lstrip('/')).read_bytes()
        t = pvr.Texture(d, pvr.find(d)[0])
        name = dptex.image_id(atlas)
        _write_rgba_png(out / f'{name}.png', t.w, t.h, t.decode())
        (out / f'{name}.json').write_text(json.dumps({'file': dptex.disc_path(atlas), 'what': what,
                                                      'format': t.describe()}))
        n += 1
    return n


def encode_texture(dec, rows):
    """`dec` (decompressed texture data) with the pixels replaced by `rows` (RGBA)."""
    t = pvr.Texture(dec, pvr.find(dec)[0])
    if t.layout != 1:
        sys.exit(f'texture layout {t.layout:#x} can not be imported (only square twiddled)')
    if len(rows) != t.h or len(rows[0]) != t.w:
        sys.exit(f'image is {len(rows[0])}x{len(rows)}, the texture {t.w}x{t.h}')
    out = bytearray(dec)
    p = t.data_start()
    for y in range(t.h):
        for x in range(t.w):
            struct.pack_into('<H', out, p + 2 * pvr.tw(x, y), pvr.to_px(rows[y][x], t.pixel))
    return bytes(out)


def import_images(images, files):
    if not images:
        return 0
    s = sbl.Sbl(files.get('/SBL.BIN'))
    by_entry = {}
    for name, png in sorted(images.items()):
        if name not in IMAGES:
            sys.exit(f'graphics.csv image {name!r} is not in tools/gfx.py IMAGES')
        by_entry.setdefault(IMAGES[name][0], []).append((name, png, IMAGES[name][1]))
        for entry, item in COPIES.get(name, []):
            by_entry.setdefault(entry, []).append((name, png, item))
    for entry, todo in sorted(by_entry.items()):
        data = s.get(entry)
        items = container(data)
        blobs = [data[o:o + n] for o, n in items] if items else None
        for name, png, item in todo:
            w, h, rows = _png_rgba(png)
            if item is None:
                data = lzss.compress(encode_texture(lzss.decompress(data), rows))
            else:
                blobs[item] = lzss.compress(encode_texture(lzss.decompress(blobs[item]), rows))
        if blobs is not None:
            data = rebuild(blobs)
        s.put(entry, data)
    files.put('/SBL.BIN', s.bytes())
    return len(images)
