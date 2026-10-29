#!/usr/bin/env python3
"""SBL.BIN, Fire Pro Wrestling D's data archive: read entries, write changed ones back.

  sbl.py list [file]             entries: index, offset, size, slot, first bytes
  sbl.py extract <outdir>        every entry as NNN.bin (raw, as stored)

Layout (verified 2026-10-27): a table of (u32 offset, u32 size) pairs at 0, one per entry, ended
by a pair whose size is 0 (its offset = the end of the data); the data starts at 0x1000 and every
entry at a 0x800 boundary. The game reads the table at run time (1ST_READ.BIN holds no copy), so an
entry may move: a changed entry that no longer fits its slot (up to the next entry) goes into the
first free run left by entries moved before it, else after the last entry (the table's end grows). Entries are stored raw - text entries 1 and 2 are
LZSS (tools/lzss.py).
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

ALIGN = 0x800


class Sbl:
    def __init__(self, data):
        self.data = bytearray(data)
        self.entries = []          # [offset, size]
        i = 0
        while True:
            off, size = struct.unpack_from('<II', self.data, i * 8)
            if size == 0:
                self.end = off
                break
            self.entries.append([off, size])
            i += 1

    def __len__(self):
        return len(self.entries)

    def get(self, k):
        off, size = self.entries[k]
        return bytes(self.data[off:off + size])

    def slot(self, k):
        """Bytes available for entry k before the next entry (or the end)."""
        off = self.entries[k][0]
        later = [o for o, _ in self.entries if o > off]
        return (min(later) if later else self.end) - off

    def gaps(self, k):
        """Free runs (start, end) between the other entries; entry k's own space counts as free."""
        used = sorted((o, o + s) for i, (o, s) in enumerate(self.entries) if i != k)
        at, out = 0x1000, []
        for o, e in used:
            if o > at:
                out.append((at, o))
            at = max(at, (e + ALIGN - 1) // ALIGN * ALIGN)
        if self.end > at:
            out.append((at, self.end))
        return out

    def put(self, k, blob):
        """Replace entry k: in its slot if it fits, else in the first free run left by entries
        moved before it (adjacent entries that each grow a little shift into each other's space
        instead of all moving), else after the last entry."""
        off, _ = self.entries[k]
        if len(blob) > self.slot(k):
            fit = [a for a, e in self.gaps(k) if e - a >= len(blob)]
            if fit:
                off = fit[0]
                print(f'  SBL entry {k}: {len(blob)} bytes, moved to free space at 0x{off:x}')
            else:
                off = self.end
                self.end = (off + len(blob) + ALIGN - 1) // ALIGN * ALIGN
                if len(self.data) < self.end:
                    self.data += bytes(self.end - len(self.data))
                print(f'  SBL entry {k}: {len(blob)} bytes, moved to 0x{off:x}')
            self.data[off:off + len(blob)] = blob
            size = (len(blob) + ALIGN - 1) // ALIGN * ALIGN
            self.data[off + len(blob):off + size] = bytes(size - len(blob))
        else:
            self.data[off:off + self.slot(k)] = bytes(self.slot(k))
        self.data[off:off + len(blob)] = blob
        self.entries[k] = [off, len(blob)]
        for i, (o, s) in enumerate(self.entries):
            struct.pack_into('<II', self.data, i * 8, o, s)
        struct.pack_into('<II', self.data, len(self.entries) * 8, self.end, 0)

    def bytes(self):
        return bytes(self.data[:max(self.end, len(self.data))])


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'list':
        src = Path(argv[1]) if len(argv) > 1 else paths.EXTRACTED / 'SBL.BIN'
        s = Sbl(src.read_bytes())
        for k, (o, n) in enumerate(s.entries):
            print(f'{k:3d} 0x{o:08x} {n:9d} {s.slot(k):9d}  {s.get(k)[:8].hex()}')
    elif len(argv) == 2 and argv[0] == 'extract':
        s = Sbl((paths.EXTRACTED / 'SBL.BIN').read_bytes())
        out = Path(argv[1])
        out.mkdir(parents=True, exist_ok=True)
        for k in range(len(s)):
            (out / f'{k:03d}.bin').write_bytes(s.get(k))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
