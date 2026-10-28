#!/usr/bin/env python3
"""Dreamcast PVR textures (GBIX/PVRT): decode to RGBA, encode back, find them in data.

  pvr.py scan <file>...             PVRT chunks in files (raw or SBL LZSS entries): offset, size, format
  pvr.py png <file> <offset> <out>  one texture to PNG (Pillow)

PVRT header (16 bytes): 'PVRT', u32 size of the rest, u8 pixel format (0 ARGB1555, 1 RGB565,
2 ARGB4444, 5 4-bit palette, 6 8-bit palette), u8 data format (1/2 square twiddled [mipmaps],
3/4 VQ [mipmaps], 5/6 4-bit palette twiddled, 7/8 8-bit palette twiddled, 9 rectangle,
0x0B stride, 0x0D rectangle twiddled, 0x10/0x11 small VQ), u16 0, u16 width, u16 height.
Mipmapped data stores the small levels first; the full-size image is the last one.
An optional 'GBIX' chunk (8 + its size bytes) comes before PVRT.
"""
import struct
import sys
from pathlib import Path

PIXEL = {0: 'ARGB1555', 1: 'RGB565', 2: 'ARGB4444', 5: 'PAL4', 6: 'PAL8'}


def twiddle_table(n):
    t = []
    for i in range(n):
        v, b, k = 0, 0, i
        while k:
            v |= (k & 1) << (2 * b)
            k >>= 1
            b += 1
        t.append(v)
    return t


_TW = twiddle_table(1024)


def tw(x, y):
    """Twiddled index of (x, y) in a square texture (x is the slow bit: y | x << 1)."""
    return (_TW[y] | (_TW[x] << 1))


def rgba(px, fmt):
    if fmt == 0:
        a = 255 if px & 0x8000 else 0
        return ((px >> 10) & 31) * 255 // 31, ((px >> 5) & 31) * 255 // 31, (px & 31) * 255 // 31, a
    if fmt == 1:
        return (px >> 11) * 255 // 31, ((px >> 5) & 63) * 255 // 63, (px & 31) * 255 // 31, 255
    if fmt == 2:
        return ((px >> 8) & 15) * 17, ((px >> 4) & 15) * 17, (px & 15) * 17, (px >> 12) * 17
    raise ValueError(f'pixel format {fmt}')


def to_px(c, fmt):
    r, g, b, a = c
    if fmt == 0:
        return (0x8000 if a >= 128 else 0) | (r * 31 // 255) << 10 | (g * 31 // 255) << 5 | (b * 31 // 255)
    if fmt == 1:
        return (r * 31 // 255) << 11 | (g * 63 // 255) << 5 | (b * 31 // 255)
    if fmt == 2:
        return (a * 15 // 255) << 12 | (r * 15 // 255) << 8 | (g * 15 // 255) << 4 | (b * 15 // 255)
    raise ValueError(f'pixel format {fmt}')


class Texture:
    def __init__(self, data, off):
        """The PVRT chunk at `off` of `data` (a GBIX chunk before it is skipped by find())."""
        assert data[off:off + 4] == b'PVRT', 'no PVRT here'
        self.off = off
        self.size = struct.unpack_from('<I', data, off + 4)[0]
        self.pixel, self.layout = data[off + 8], data[off + 9]
        self.w, self.h = struct.unpack_from('<HH', data, off + 12)
        self.body = off + 16
        self.data = data

    @property
    def mip(self):
        return self.layout in (2, 4, 6, 8, 0x11)

    def describe(self):
        return f'{self.w}x{self.h} {PIXEL.get(self.pixel, self.pixel)} layout {self.layout:#x}'

    def level_bytes(self):
        """Bytes of the full-size level's pixel data (VQ: the index bytes)."""
        L, w, h = self.layout, self.w, self.h
        if L in (3, 4, 0x10, 0x11):
            return (w // 2) * (h // 2)
        if L in (5, 6):
            return w * h // 2
        if L in (7, 8):
            return w * h
        return w * h * 2

    def data_start(self):
        """Offset of the full-size level: mipmaps store it last, so count back from the chunk's
        end (no mipmaps: right after the header, or the VQ codebook)."""
        if self.mip:
            return self.off + 8 + self.size - self.level_bytes()
        return self.body + (self.codebook() * 8 if self.layout in (3, 0x10) else 0)

    def codebook(self):
        """Codebook entries of a VQ texture (small VQ keeps fewer for small sizes)."""
        w = self.w
        if self.layout == 0x10:
            return 16 if w <= 16 else 32 if w == 32 else 128 if w == 64 else 256
        if self.layout == 0x11:
            return 16 if w <= 16 else 64 if w == 32 else 256
        return 256

    def decode(self, palette=None):
        """[(r,g,b,a)] row-major, w*h."""
        d, w, h, L, f = self.data, self.w, self.h, self.layout, self.pixel
        out = [(0, 0, 0, 0)] * (w * h)
        p = self.data_start()
        if L in (1, 2, 0x0D):
            n = min(w, h)
            for y in range(h):
                for x in range(w):
                    # rectangle twiddled: squares of n x n side by side
                    blk = (x // n) + (y // n)
                    i = blk * n * n + tw(x % n, y % n)
                    out[y * w + x] = rgba(struct.unpack_from('<H', d, p + 2 * i)[0], f)
        elif L in (9, 0x0B):
            for y in range(h):
                for x in range(w):
                    out[y * w + x] = rgba(struct.unpack_from('<H', d, p + 2 * (y * w + x))[0], f)
        elif L in (3, 4, 0x10, 0x11):
            book = self.body
            codes = [[rgba(struct.unpack_from('<H', d, book + 8 * k + 2 * j)[0], f) for j in range(4)]
                     for k in range(self.codebook())]
            for y in range(0, h, 2):
                for x in range(0, w, 2):
                    c = codes[d[p + tw(x // 2, y // 2)] % len(codes)]
                    # codebook entry order: (0,0) (0,1) (1,0) (1,1) - x slow
                    out[y * w + x], out[(y + 1) * w + x], out[y * w + x + 1], out[(y + 1) * w + x + 1] = c
        elif L in (5, 6, 7, 8):
            pal = palette or [(k * 17 % 256,) * 3 + (255,) for k in range(256)]
            for y in range(h):
                for x in range(w):
                    i = tw(x, y)
                    if L in (5, 6):
                        v = d[p + i // 2]
                        v = (v >> 4) if i & 1 else (v & 15)
                    else:
                        v = d[p + i]
                    out[y * w + x] = pal[v % len(pal)]
        else:
            raise ValueError(f'layout {L:#x} not handled')
        return out

    def to_image(self, palette=None):
        from PIL import Image
        im = Image.new('RGBA', (self.w, self.h))
        im.putdata(self.decode(palette))
        return im


def find(data):
    """Offsets of every PVRT chunk in data."""
    out, i = [], 0
    while True:
        i = data.find(b'PVRT', i)
        if i < 0:
            return out
        if i + 16 <= len(data):
            w, h = struct.unpack_from('<HH', data, i + 12)
            if 8 <= w <= 1024 and 8 <= h <= 1024 and data[i + 9] in (1, 2, 3, 4, 5, 6, 7, 8, 9, 0x0B, 0x0D, 0x10, 0x11):
                out.append(i)
        i += 4


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['scan']:
        for f in argv[1:]:
            data = Path(f).read_bytes()
            for o in find(data):
                print(f'{f} 0x{o:x} {Texture(data, o).describe()}')
    elif len(argv) == 4 and argv[0] == 'png':
        data = Path(argv[1]).read_bytes()
        Texture(data, int(argv[2], 0)).to_image().save(argv[3])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
