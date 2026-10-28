#!/usr/bin/env python3
"""Sega Dreamcast GD-ROM image (platform pack dreamcast): a Redump BIN/CUE with an ISO9660 file
system spread over the high-density area's two data tracks.

  disc.py list    <track.bin>
  disc.py extract <track.bin> <outdir>
  disc.py inject  <track.bin> <iso_path> <file>   overwrite a file (must fit in its allocated sectors)
  disc.py verify  <track.bin> [iso_path...]       check EDC/ECC (of the given files, or every data sector - slow)
  disc.py header  <track.bin>                     IP.BIN: product number, version, date, area, boot file, title
  disc.py tracks  <cue>                           the tracks with their absolute LBAs

A GD-ROM has a single-density area (tracks 1-2: a small ISO with a warning text and an audio track
that says "this is a Dreamcast disc", from LBA 0) and a high-density area from LBA 45000: track 3
(data), any CD audio tracks, and - when there is audio - a last data track that ends at the very
end of the disc (LBA 549149). Redump's .cue marks the areas with REM SINGLE-DENSITY AREA / REM
HIGH-DENSITY AREA; each track's absolute start is the area's start plus the sizes of the files
before it (pregaps are inside the files). Sector headers carry the absolute address (minutes past
99 as 0xA0.. 0xC2 in the BCD byte).

The file system lives in the high-density area: IP.BIN in sectors 0-15 of track 3 (the system ID
`SEGA SEGAKATANA`, product number, boot file name - never written here), the PVD at track 3 + 16,
the directories after it. Directory LBAs are absolute, and files usually sit on the last data
track, with track 3 holding the directories and a large run of zero padding.

The project's image (paths.ROM) is the data track that holds the files: the last data track of the
high-density area (main_track()). The other data track (track 3) holds the directory records a
build rewrites when a file changes size, and the padding a grown file is relocated into, so a
build keeps its own copy of it next to the image, refreshed from the original on every build.
written_tracks() lists those copies: check.py --control and make_patches.py treat them like the
image (a second patch when one changed). Audio tracks are never changed.

Writing regenerates EDC/ECC for every written sector and updates the directory record (size, and
LBA when a file that outgrew its slot is relocated into free zero sectors of a data track). The
last data track already ends at the end of the disc, so nothing can be appended: a grown file goes
into existing padding or the build stops. Games usually open files by name through the GD file
system (gdFsOpen), which reads the directory; some address files by LBA - check before relocating.

Interface shared by every platform's disc.py (build.py and extract.py use only this):
  SECTOR                        data bytes per sector
  Disc(path or file, writable)  .files(), .find(path), .read_file(e), .write_file(e, data, relocate),
                                .allocated_sectors(e), .is_empty(e), .extract_file(e, out), .close()
  companion_files(image, original)  write what an emulator needs next to the image (the .cue, other tracks)
Dreamcast extras: main_track(cue), written_tracks(image, original), gd_layout(cue).
"""
import re
import shutil
import struct
import sys
from pathlib import Path

RAW = 2352
SECTOR = USER = 2048
DATA = 16        # user data offset in a MODE1 sector
HD_START = 45000     # first LBA of the high-density area
DISC_END = 549150    # one past the last LBA of a GD-ROM

# ---------------------------------------------------------------- EDC / ECC

EDC_LUT = []
for i in range(256):
    e = i
    for _ in range(8):
        e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
    EDC_LUT.append(e)

ECC_F = [0] * 256
ECC_B = [0] * 256
for i in range(256):
    j = (i << 1) ^ (0x11D if i & 0x80 else 0)
    ECC_F[i] = j
    ECC_B[i ^ j] = i


def edc(data):
    e = 0
    for b in data:
        e = (e >> 8) ^ EDC_LUT[(e ^ b) & 0xFF]
    return e


def _ecc_block(src, major_count, minor_count, major_mult, minor_inc):
    size = major_count * minor_count
    out = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            t = src[index]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= t
            b ^= t
            a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ b]
        out[major] = a
        out[major + major_count] = a ^ b
    return out


def fix_sector(sec):
    """Recompute EDC and ECC of a mode 1 sector in place (the header is part of both)."""
    struct.pack_into('<I', sec, 0x810, edc(sec[0:0x810]))
    sec[0x814:0x81C] = bytes(8)
    sec[0x81C:0x8C8] = _ecc_block(memoryview(sec)[0xC:], 86, 24, 2, 86)
    sec[0x8C8:0x930] = _ecc_block(memoryview(sec)[0xC:], 52, 43, 86, 88)


def msf(lba):
    """The 3 header bytes of absolute `lba` (GD-ROM: the minutes byte goes past 0x99 as 0xA0..)."""
    m, rest = divmod(lba + 150, 75 * 60)
    s, f = divmod(rest, 75)
    return bytes(((v // 10) << 4) | (v % 10) for v in (m, s, f))


def header_lba(sec):
    """Absolute LBA in a sector header (inverse of msf)."""
    m, s, f = (((b >> 4) * 10) + (b & 15) for b in sec[12:15])
    return (m * 60 + s) * 75 + f - 150


def mode1_sector(lba, data=b''):
    """A MODE1 sector at absolute `lba` holding `data` (zero-padded), EDC/ECC filled in."""
    sec = bytearray(RAW)
    sec[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'
    sec[12:16] = msf(lba) + b'\x01'
    sec[DATA:DATA + len(data)] = data
    fix_sector(sec)
    return sec


# ---------------------------------------------------------------- cue sheets

class Track:
    def __init__(self, file, number, mode, area, start, sectors, pregap=0):
        self.file, self.number, self.mode, self.area = file, number, mode, area
        self.start, self.sectors = start, sectors   # absolute LBA of the file's first sector
        self.pregap = pregap                        # sectors before INDEX 01 (inside the file)

    @property
    def data(self):
        return self.mode.startswith('MODE1')

    def __repr__(self):
        return f'Track({self.number}, {self.mode}, {self.area}, {self.start}+{self.sectors}, {self.file!r})'


def cue_tracks(cue):
    """[(file name, track number, mode)] of a cue sheet, in order."""
    return [(t.file, t.number, t.mode) for t in gd_layout(cue, sizes=False)]


def gd_layout(cue, sizes=True):
    """The tracks of a GD-ROM cue sheet with their absolute start LBA (from the file sizes)."""
    cue = Path(cue)
    out, cur, area, pos = [], None, 'HD', {'SD': 0, 'HD': HD_START}
    for line in cue.read_text(errors='replace').splitlines():
        if re.match(r'\s*REM\s+SINGLE-DENSITY', line, re.I):
            area = 'SD'
            continue
        if re.match(r'\s*REM\s+HIGH-DENSITY', line, re.I):
            area = 'HD'
            continue
        m = re.match(r'\s*FILE\s+"(.*)"\s+\w+', line) or re.match(r'\s*FILE\s+(\S+)\s+\w+', line)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r'\s*TRACK\s+(\d+)\s+(\S+)', line)
        if m:
            n = (cue.parent / cur).stat().st_size // RAW if sizes else 0
            out.append(Track(cur, int(m.group(1)), m.group(2).upper(), area, pos[area], n))
            pos[area] += n
            continue
        m = re.match(r'\s*INDEX\s+01\s+(\d+):(\d+):(\d+)', line)
        if m and out:
            mm, ss, ff = map(int, m.groups())
            out[-1].pregap = (mm * 60 + ss) * 75 + ff
    return out


def find_cue(image):
    """The .cue next to `image` that names it, or None."""
    image = Path(image)
    for cue in sorted(image.parent.glob('*.cue')):
        if any(f == image.name for f, _, _ in cue_tracks(cue)):
            return cue
    return None


def main_track(cue):
    """The file of the data track a project works on: the last data track of the high-density area."""
    data = [t for t in gd_layout(cue) if t.area == 'HD' and t.data]
    return Path(cue).parent / data[-1].file if data else None


def companion_name(image, name):
    """What the copy of the original's track file `name` is called next to build `image`."""
    image = Path(image)
    num = re.search(r'\(Track (\d+)\)', name)
    return f'{image.stem} (Track {num.group(1)}){Path(name).suffix}' if num else f'{image.stem} - {name}'


def written_tracks(image, original):
    """[(original track, its copy next to `image`)] for the other data tracks of the high-density
    area: a build may change them (directory records, relocated files), so they are checked and
    patched like the image."""
    original, image = Path(original), Path(image)
    cue = find_cue(original)
    if cue is None:
        return []
    return [(cue.parent / t.file, image.parent / companion_name(image, t.file))
            for t in gd_layout(cue) if t.area == 'HD' and t.data and t.file != original.name]


# ---------------------------------------------------------------- ISO9660

class Entry:
    def __init__(self, path, lba, size, is_dir, rec_sector, rec_offset):
        self.path, self.lba, self.size, self.is_dir = path, lba, size, is_dir
        self.rec_sector, self.rec_offset = rec_sector, rec_offset  # where the dir record lives

    @property
    def sectors(self):
        return (self.size + USER - 1) // USER


class _Open:
    """One data track's file: absolute LBAs start..start+sectors."""

    def __init__(self, f, start, sectors, own, pregap=0):
        self.f, self.start, self.sectors, self.own, self.pregap = f, start, sectors, own, pregap

    @property
    def end(self):
        return self.start + self.sectors


def _refresh(original, copy):
    """Make `copy` an exact copy of `original` and open it for writing (journalled when the
    project's tools/image.py is importable, so a rebuild restores only what was written)."""
    try:
        import image
        return image.prepare(original, copy, quiet=True)
    except ImportError:
        shutil.copyfile(original, copy)
        return open(copy, 'r+b')


class Disc:
    def __init__(self, path, writable=False):
        own = not hasattr(path, 'read')
        f = open(path, 'r+b' if writable else 'rb') if own else path
        here = Path(path) if own else Path(getattr(path, 'path', getattr(path, 'name', '')))
        original = Path(getattr(path, 'original', here))
        f.seek(0, 2)
        size = f.tell() // RAW
        cue = find_cue(original)
        self.tracks = []
        if cue is None:   # a lone data track: its start from the first data sector's header (past a pregap)
            for i in range(size):
                f.seek(i * RAW)
                sec = bytearray(f.read(RAW))
                if sec[15] == 1:
                    break
            self.tracks.append(_Open(f, header_lba(sec) - i, size, own, i))
        else:
            for t in gd_layout(cue):
                if t.area != 'HD' or not t.data:
                    continue
                if t.file == original.name:
                    self.tracks.append(_Open(f, t.start, size, own, t.pregap))
                    continue
                src = cue.parent / t.file
                copy = here.parent / companion_name(here, t.file)
                if here == original:          # the original disc (or one patched in place)
                    other = open(src, 'r+b' if writable else 'rb')
                elif writable:                # a build: a fresh copy next to the image
                    other = _refresh(src, copy)
                else:
                    other = open(copy if copy.exists() else src, 'rb')
                self.tracks.append(_Open(other, t.start, t.sectors, True, t.pregap))
        self.tracks.sort(key=lambda t: t.start)
        self.entries = []
        first = self.tracks[0]
        sec = self.read_raw(first.start + 16)
        assert sec[15] == 1, 'not a MODE1/2352 data track'
        pvd = bytes(sec[DATA:DATA + USER])
        assert pvd[1:6] == b'CD001', ('no ISO9660 PVD at the first data track + 16' if cue else
                                      f'no ISO9660 PVD: no .cue next to {here.name} names it, and the file system '
                                      'starts on track 3 (keep the .cue with the tracks)')
        root = pvd[156:190]
        self._walk(struct.unpack('<I', root[2:6])[0], struct.unpack('<I', root[10:14])[0], '/')
        self.entries.sort(key=lambda e: e.lba)

    def close(self):
        for t in self.tracks:
            if t.own:
                t.f.close()

    def _track(self, lba):
        for t in self.tracks:
            if t.start <= lba < t.end:
                return t
        raise ValueError(f'LBA {lba} is on no data track of this image '
                         f'({", ".join(f"{t.start}-{t.end - 1}" for t in self.tracks)})')

    def read_raw(self, lba):
        t = self._track(lba)
        t.f.seek((lba - t.start) * RAW)
        return bytearray(t.f.read(RAW))

    def write_raw(self, lba, sec):
        t = self._track(lba)
        t.f.seek((lba - t.start) * RAW)
        t.f.write(sec)

    def read_user(self, lba):
        return bytes(self.read_raw(lba)[DATA:DATA + USER])

    def header(self):
        """IP.BIN's meta information (sector 0 of the first data track of the high-density area)."""
        s = self.read_user(self.tracks[0].start)
        text = lambda a, b: s[a:b].decode('ascii', 'replace').strip()
        return {'hardware': text(0, 16), 'maker': text(16, 32), 'device': text(32, 48), 'area': text(48, 56),
                'peripherals': text(56, 64), 'product': text(64, 74), 'version': text(74, 80),
                'date': text(80, 96), 'boot_file': text(96, 112), 'company': text(112, 128),
                'title': text(128, 256)}

    def _walk(self, lba, size, path):
        for s in range((size + USER - 1) // USER):
            data = self.read_user(lba + s)
            i = 0
            while i < USER:
                ln = data[i]
                if ln == 0:
                    break
                r = data[i:i + ln]
                name = r[33:33 + r[32]]
                if name not in (b'\0', b'\1'):
                    e = Entry(path + name.decode('ascii').split(';')[0],
                              struct.unpack('<I', r[2:6])[0], struct.unpack('<I', r[10:14])[0],
                              bool(r[25] & 2), lba + s, i)
                    self.entries.append(e)
                    if e.is_dir:
                        self._walk(e.lba, e.size, e.path + '/')
                i += ln

    def files(self):
        return [e for e in self.entries if not e.is_dir]

    def find(self, path):
        path = '/' + path.lstrip('/')
        for e in self.entries:
            if e.path.upper() == path.upper():
                return e
        raise KeyError(path)

    def allocated_sectors(self, e):
        """Sectors available before the next thing on disc (or the end of the file's data track)."""
        end = self._track(e.lba).end
        later = [x.lba for x in self.entries if e.lba < x.lba < end]
        return (min(later) if later else end) - e.lba

    def read_file(self, e):
        out = bytearray()
        for s in range(e.sectors):
            out += self.read_user(e.lba + s)
        return bytes(out[:e.size])

    def is_empty(self, e, samples=64):
        """True if the file looks like zero padding (checks up to `samples` spread-out sectors)."""
        step = max(1, e.sectors // samples)
        return e.size > 0 and not any(any(self.read_user(e.lba + s)) for s in range(0, e.sectors, step))

    def extract_file(self, e, out):
        Path(out).write_bytes(self.read_file(e))

    def find_free(self, need):
        """First run of `need` empty MODE1 sectors used by no file or directory, in disc order: track
        3's padding first (past IP.BIN, the volume descriptors and the directories), so the room
        after the last file (often 1ST_READ.BIN, which hooks grow) stays free. Never in a pregap:
        emulators and .gdi conversions leave the sectors before INDEX 01 out."""
        used = sorted((x.lba, x.lba + max(x.sectors, 1)) for x in self.entries)
        for t in self.tracks:
            cur = t.start + max(t.pregap, 32 if t is self.tracks[0] else 0)
            for a, b in [u for u in used if t.start <= u[0] < t.end] + [(t.end, t.end)]:
                while a - cur >= need:
                    busy = next((l for l in range(cur, cur + need)
                                 if (s := self.read_raw(l))[15] != 1 or any(s[DATA:DATA + USER])), None)
                    if busy is None:
                        return cur
                    cur = busy + 1
                cur = max(cur, b)
        return None

    def _patch_record(self, e, offset, value):
        """Write a both-endian 32-bit field of e's directory record."""
        sec = self.read_raw(e.rec_sector)
        o = DATA + e.rec_offset
        struct.pack_into('<I', sec, o + offset, value)
        struct.pack_into('>I', sec, o + offset + 4, value)
        fix_sector(sec)
        self.write_raw(e.rec_sector, sec)

    def _make_room(self, e, need):
        """Let e grow in place by moving the files in its way, when they are smaller than e (a
        grown 80 MB archive stays put and the small file after it moves, so a patch carries a few
        sectors, not the archive). Only files on e's track, never a directory; the moved files
        go where find_free() puts them. True if e now has `need` sectors."""
        t = self._track(e.lba)
        if e.lba + need > t.end:
            return False
        span = (e.lba + self.allocated_sectors(e), e.lba + need)
        blockers = [x for x in self.entries if x is not e and x.lba < span[1] and x.lba + max(x.sectors, 1) > span[0]]
        if not blockers or any(x.is_dir or not t.start <= x.lba < t.end for x in blockers) \
                or sum(x.sectors for x in blockers) >= need:
            return False
        for x in blockers:
            new = self.find_free(x.sectors)
            if new is None or span[0] <= new < span[1]:
                return False
        for x in blockers:
            new = self.find_free(x.sectors)
            print(f'  making room for {e.path}: moving {x.path} LBA {x.lba} -> {new} ({x.sectors} sectors)')
            for s in range(x.sectors):
                sec = self.read_raw(x.lba + s)
                out = mode1_sector(new + s, bytes(sec[DATA:DATA + USER]))
                self.write_raw(new + s, out)
            x.lba = new
            self._patch_record(x, 2, new)
        return self.allocated_sectors(e) >= need

    def write_file(self, e, data, relocate=False):
        need = (len(data) + USER - 1) // USER
        avail = self.allocated_sectors(e)
        if need > avail and relocate and self._make_room(e, need):
            avail = self.allocated_sectors(e)
        if need > avail:
            if not relocate:
                raise ValueError(f'{e.path}: {len(data)} bytes needs {need} sectors, only {avail} available')
            new = self.find_free(need)
            if new is None:
                raise ValueError(f'{e.path}: {len(data)} bytes needs {need} sectors, only {avail} in place and no '
                                 f'run of {need} free sectors on the data tracks (a GD-ROM ends at LBA '
                                 f'{DISC_END - 1}: nothing can be appended) - make the file smaller')
            print(f'  relocating {e.path}: LBA {e.lba} -> {new} ({need} sectors)')
            e.lba = new
            self._patch_record(e, 2, new)
        for s in range(need):
            sec = self.read_raw(e.lba + s)
            new = data[s * USER:(s + 1) * USER].ljust(USER, b'\0')
            if sec[DATA:DATA + USER] == new and sec[15] == 1:
                continue                      # unchanged: keep the sector (a big file rewrites fast)
            sec[DATA:DATA + USER] = new
            fix_sector(sec)
            self.write_raw(e.lba + s, sec)
        if e.size != len(data):
            self._patch_record(e, 10, len(data))
        e.size = len(data)


def companion_files(image, original=None):
    """The .cue an emulator loads, next to the image, and copies of the original's other tracks
    (audio is never changed; a data track a build already wrote is kept as it is)."""
    image = Path(image)
    cue = find_cue(original) if original else None
    if cue is None:
        image.with_suffix('.cue').write_text(f'FILE "{image.name}" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n')
        return
    written = {c.name for _, c in written_tracks(image, original)}
    lines = []
    for line in cue.read_text(errors='replace').splitlines():
        m = re.match(r'(\s*FILE\s+)"?(.*?)"?(\s+\w+\s*)$', line)
        if m and m.group(2) == Path(original).name:
            line = f'{m.group(1)}"{image.name}"{m.group(3)}'
        elif m:
            src = cue.parent / m.group(2)
            name = companion_name(image, m.group(2))
            dst = image.parent / name
            if not dst.exists() or (name not in written and dst.stat().st_size != src.stat().st_size):
                shutil.copyfile(src, dst)
            line = f'{m.group(1)}"{name}"{m.group(3)}'
        lines.append(line)
    image.with_suffix('.cue').write_text('\n'.join(lines) + '\n')


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == 'list':
        d = Disc(argv[1])
        for e in d.files():
            print(f'{e.lba:7d} {e.size:10d} {d.allocated_sectors(e):6d}  {e.path}')
    elif cmd == 'header':
        for k, v in Disc(argv[1]).header().items():
            print(f'{k:12} {v}')
    elif cmd == 'tracks':
        for t in gd_layout(argv[1]):
            print(f'{t.number:2d} {t.area} {t.mode:12} {t.start:7d} {t.sectors:7d}  {t.file}')
    elif cmd == 'extract':
        d = Disc(argv[1])
        out = Path(argv[2])
        for e in d.files():
            p = out / e.path.lstrip('/')
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(d.read_file(e))
            print('extracted', e.path)
    elif cmd == 'inject':
        d = Disc(argv[1], writable=True)
        e = d.find(argv[2])
        data = Path(argv[3]).read_bytes()
        d.write_file(e, data)
        d.close()
        print(f'injected {argv[3]} -> {e.path} ({len(data)} bytes)')
    elif cmd == 'verify':
        d = Disc(argv[1])
        bad = 0
        if len(argv) > 2:
            lbas = [lba for p in argv[2:] for e in [d.find(p)] for lba in range(e.lba, e.lba + e.sectors)]
        else:
            lbas = [lba for t in d.tracks for lba in range(t.start, t.end)]
        for lba in lbas:
            sec = d.read_raw(lba)
            if sec[15] != 1:
                continue
            ref = bytearray(sec)
            fix_sector(ref)
            if ref != sec:
                bad += 1
                if bad <= 10:
                    print('bad sector', lba)
        print('bad sectors:', bad)
        return 1 if bad else 0
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
