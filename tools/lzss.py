#!/usr/bin/env python3
"""The LZSS of SBL.BIN entries (Fire Pro Wrestling D): decompress and compress.

  lzss.py unpack <in> <out>      decompress a raw entry
  lzss.py pack <in> <out>        compress
  lzss.py test <in>              compress the decompressed entry again: round trip and sizes

Format (from the code's output in RAM, verified on SBL entries 1 and 2, 2026-10-27): no header,
no size - the stream runs to the end of the entry. A flag byte covers the next 8 items, bit 0
first: 0 = a literal byte, 1 = a 2-byte reference b0 b1 - position in a 1024-byte window
b0 | (b1 & 0xC0) << 2, length (b1 & 0x3F) + 3 (3..66). The window starts zero-filled and is
written from 0x3BE (1024 - 66), Okumura-style but with the flag bits inverted.

The compressor finds the longest match (hash chains, window positions not yet written count as
zeros like the original's) with one step of lazy matching; it doesn't reproduce the original
bytes - the control build never rewrites an untouched entry.
"""
import sys
from pathlib import Path

N, F, MIN = 1024, 66, 3
START = N - F


def decompress(c, out_size=None):
    ring = bytearray(N)
    r = START
    out = bytearray()
    i, n = 0, len(c)
    while i < n and (out_size is None or len(out) < out_size):
        flags = c[i]
        i += 1
        for bit in range(8):
            if i >= n or (out_size is not None and len(out) >= out_size):
                break
            if flags >> bit & 1:
                if i + 1 >= n:
                    if any(c[i:]):
                        raise ValueError(f'reference cut short at {i}')
                    return bytes(out)           # container items are padded to 4 bytes
                b0, b1 = c[i], c[i + 1]
                i += 2
                pos = b0 | ((b1 & 0xC0) << 2)
                for k in range((b1 & 0x3F) + MIN):
                    v = ring[(pos + k) % N]
                    out.append(v)
                    ring[r] = v
                    r = (r + 1) % N
            else:
                v = c[i]
                i += 1
                out.append(v)
                ring[r] = v
                r = (r + 1) % N
    return bytes(out)


def compress(data):
    """LZSS stream for `data` (decompress(compress(x)) == x)."""
    data = bytes(data)
    n = len(data)
    # The window as the decoder sees it: N zero bytes (positions START-N .. START-1 relative to the
    # first output byte), then the data. Search a virtual buffer of N-F zeros + data.
    pad = START                               # zero bytes in the window before the first output byte
    buf = bytes(pad) + data
    head = {}
    prev = [-1] * len(buf)

    def insert(p):
        if p + MIN <= len(buf):
            k = buf[p:p + MIN]
            prev[p] = head.get(k, -1)
            head[k] = p

    for p in range(pad):                      # the zero window is matchable from the start
        insert(p)

    def longest(p):
        """(length, source position in buf) of the best match for buf[p:], within the window."""
        best_len, best_src = 0, -1
        if p + MIN > len(buf):
            return 0, -1
        limit = min(F, len(buf) - p)
        cand = head.get(buf[p:p + MIN], -1)
        tries = 0
        while cand >= 0 and p - cand <= N - F and tries < 256:
            ln = MIN
            while ln < limit and buf[cand + ln] == buf[p + ln]:
                ln += 1
            if ln > best_len:
                best_len, best_src = ln, cand
                if ln == limit:
                    break
            cand = prev[cand]
            tries += 1
        return best_len, best_src

    out = bytearray()
    items = []                                # literal int, or (pos, length)
    p = pad
    while p < len(buf):
        ln, src = longest(p)
        if ln >= MIN:
            ln2, _ = longest(p + 1) if p + 1 < len(buf) else (0, -1)
            if ln2 > ln + 1:                  # lazy: a literal now buys a longer match next
                items.append(buf[p])
                insert(p)
                p += 1
                continue
            # window position of buf index `src`: output index src - pad, ring at START + that
            items.append(((START + src - pad) % N, ln))
            for q in range(p, p + ln):
                insert(q)
            p += ln
        else:
            items.append(buf[p])
            insert(p)
            p += 1
    for g in range(0, len(items), 8):
        group = items[g:g + 8]
        flags = 0
        body = bytearray()
        for b, it in enumerate(group):
            if isinstance(it, tuple):
                pos, ln = it
                flags |= 1 << b
                body += bytes((pos & 0xFF, ((pos >> 2) & 0xC0) | (ln - MIN)))
            else:
                body.append(it)
        out.append(flags)
        out += body
    return bytes(out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 3 and argv[0] == 'unpack':
        Path(argv[2]).write_bytes(decompress(Path(argv[1]).read_bytes()))
    elif len(argv) == 3 and argv[0] == 'pack':
        Path(argv[2]).write_bytes(compress(Path(argv[1]).read_bytes()))
    elif len(argv) == 2 and argv[0] == 'test':
        raw = Path(argv[1]).read_bytes()
        data = decompress(raw)
        c = compress(data)
        ok = decompress(c) == data
        print(f'{argv[1]}: {len(raw)} -> {len(data)} bytes; recompressed {len(c)} '
              f'({len(c) - len(raw):+d}); round trip {"ok" if ok else "FAILED"}')
        return 0 if ok else 1
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
