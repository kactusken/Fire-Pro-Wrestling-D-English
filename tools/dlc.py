#!/usr/bin/env python3
"""The downloadable moves and the downloadable edit wrestlers (Spike's), built into the disc (group `dlc`).

  python3 tools/dlc.py list         what rom/dlc/ holds: moves by slot, edit-wrestler files
  python3 tools/dlc.py routine      the boot routine's bytes (for build.py CODE_PATCHES)

Fire Pro Wrestling D loaded extra moves from memory cards: on every cold boot its autoload
(0x8C03E3D8) copies each FIREPROD.Wnn file it finds into a 0x78000-byte pool (0x8C1F4040) and
records a pointer in a table of 100 (0x8C1BBA8C; bytes used at +0x190); nothing is saved. A
wrestler's move slot refers to one as 0x800 + nn. Edit wrestlers come from FIREPROD.E01-E04
(0x7D38 bytes each, at 0x8C1D4B60 + k * 0x7D38, ending where the pool starts).
docs/HIDDEN_CONTENT.md and docs/PATCHES.md ("Downloadable moves") have the details.

The build packs an image of that memory - E01-E03 empty, the roster as E04, the pool, and at a
fixed place near the pool's end the 101-word table - into a new SBL.BIN entry. A routine in the
never-called match overlay function (0x8C030A80) reads the entry over that memory on cold boot
(0x8C012E2C(entry, dest) reads whole sectors: up to 2047 bytes past the end, which stays inside
the pool), copies the table into place and goes on to the card autoload. Cards still work: their
E01-E04 replace the built-in roster, their W files for filled slots are skipped.

Sources (never committed - game data): memory card images in rom/dlc/ (Flycast vmu_save_*.bin,
128 KB each). Every FIREPROD.Wnn found is used (the first file for a slot wins); the roster is
the FIREPROD.E01 found (its checksum is checked).
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import sbl  # noqa: E402

SOURCE = 'dlc'                      # folder under rom/
ENTRY = 370                         # the new SBL.BIN entry (the original has 370: 0-369)
E_BASE = 0x8C1D4B60                 # E01; E02-E04 follow
E_SIZE = 0x7D38
ROSTER_SLOT = 3                     # E04 (wrestler ids 0xC000 | n): see docs/PATCHES.md
POOL = 0x8C1F4040
POOL_SIZE = 0x78000
TABLE = 0x8C1BBA8C                  # 100 pointers, then the bytes used
TABLE_COPY = POOL + POOL_SIZE - 0x800 - 101 * 4   # the table's place in the image (fixed)
BLOCK_SIZE = TABLE_COPY + 101 * 4 - E_BASE
HOOK = 0x8C015AB4                   # literal of the cold-boot jump to the card autoload
AUTOLOAD = 0x8C03E3D8
ROUTINE_AT = 0x8C030A80             # the match information overlay: never called
READ = 0x8C012E2C

ROUTINE = f"""
        sts.l   pr,@-r15
        mov.l   =0x{READ:08X},r0
        mov.l   =0x{E_BASE:08X},r5
        mov.l   =ENTRYNUM,r4
        jsr     @r0
        nop
        mov.l   =0x{TABLE_COPY:08X},r1
        mov.l   =0x{TABLE:08X},r2
        mov     #101,r3
loop:   mov.l   @r1+,r0
        mov.l   r0,@r2
        dt      r3
        bf/s    loop
        add     #4,r2
        lds.l   @r15+,pr
        mov.l   =0x{AUTOLOAD:08X},r0
        jmp     @r0
        nop
        .align  2
        .pool
"""


# ---------------------------------------------------------------- save guard (group 'saveguard')
# Memory Card > Save, one file: when the chosen card already has that file, the game asks
# "Overwrite?" (0x8C03F5BA calls find_file 0x8C15E202 through the literal at 0x8C03F5E8; found ->
# r9 = r8 = 1 -> the prompt). The guard wraps find_file: the overwrite stays allowed only when the
# file in memory was loaded from (or saved to) this same card - status 2 Edited / 3 Saved with
# that unit in the per-file status (*(0x8C1BBA88) + 0x198 + 2 * kind: status, unit). Otherwise
# (a card inserted after power-on, another card, a file never loaded) it sets r8 = 4 (the caller
# copies it to r9: an error value - buzzer, no prompt) and r10 = its message (the status line;
# r10 is 0 on every frame until a message is set). Nothing is written.
GUARD_AT = 0x8C030AC0               # after the boot routine, in the same unused function
GUARD_SIZE = 128                    # fixed, so both languages patch the same bytes
GUARD_LITERAL = 0x8C03F5E8          # find_file's literal, used only by the single-file save
FIND_FILE = 0x8C15E202
GUARD_TEXT = {'english': "Can't overwrite: load it first.",
              'japanese': '読み込んでいないファイルは上書きできません'}
GUARD = f"""
        sts.l   pr,@-r15
        mov.l   r4,@-r15
        mov.l   =0x{FIND_FILE:08X},r0
        jsr     @r0
        nop
        mov.l   @r15+,r4
        lds.l   @r15+,pr
        tst     r0,r0
        bf      done
        mov.l   @r14,r1
        mov.w   @r1,r1
        add     r1,r1
        mov.l   =0x8C1BBA88,r2
        mov.l   @r2,r2
        add     r1,r2
        mov.l   =0x198,r1
        add     r1,r2
        mov.b   @r2+,r1
        extu.b  r1,r1
        add     #-2,r1
        mov     #1,r3
        cmp/hi  r3,r1
        bt      refuse
        mov.b   @r2,r1
        extu.b  r1,r1
        cmp/eq  r4,r1
        bt      done
refuse: mov     #4,r8
        mova    text,r0
        mov     r0,r10
        mov     #0,r0
done:   rts
        nop
        .align  2
        .pool
text:
"""


def guard(language='english'):
    """The save guard's bytes (code, literals and its message) for build.py CODE_PATCHES."""
    import sh4
    code, sym = sh4.assemble(GUARD, GUARD_AT)
    msg = GUARD_TEXT[language].encode('cp932') + b'\0'
    out = code + msg
    if len(out) > GUARD_SIZE:
        sys.exit(f'dlc: the save guard is {len(out)} bytes, room for {GUARD_SIZE}')
    return out + bytes(GUARD_SIZE - len(out))


def guard_patches(original, language='english'):
    """(address, original bytes, new bytes) for the guard, from the original 1ST_READ.BIN."""
    g = guard(language)
    off = GUARD_AT - 0x8C010000
    lit = GUARD_LITERAL - 0x8C010000
    return [(GUARD_AT, original[off:off + len(g)], g),
            (GUARD_LITERAL, original[lit:lit + 4], GUARD_AT.to_bytes(4, 'little'))]


def routine():
    """The boot routine's bytes."""
    import sh4
    src = ROUTINE.replace('ENTRYNUM', str(ENTRY))
    code, _ = sh4.assemble(src, ROUTINE_AT)
    return code


# ---------------------------------------------------------------- memory card images

def vmu_files(img):
    """[(name, payload)] of a VMU image's files (VMS header skipped: payload = data size at 0x48)."""
    d = Path(img).read_bytes()
    B = 512
    root = d[255 * B:256 * B]
    fat_b, _, dir_b, dir_n = struct.unpack_from('<HHHH', root, 0x46)
    fat = struct.unpack_from('<256H', d, fat_b * B)
    out = []
    for k in range(dir_n):
        blk = d[(dir_b - k) * B:(dir_b - k + 1) * B]
        for e in range(0, B, 32):
            if blk[e] not in (0x33, 0xCC):
                continue
            first = struct.unpack_from('<H', blk, e + 2)[0]
            size, hdr = struct.unpack_from('<HH', blk, e + 0x18)
            data, b = bytearray(), first
            for _ in range(size):
                data += d[b * B:(b + 1) * B]
                b = fat[b]
            n = struct.unpack_from('<I', data, 0x48)[0]
            out.append((blk[e + 4:e + 16].decode('ascii', 'replace').strip(), bytes(data[0x280:0x280 + n])))
    return out


def sources():
    """({slot: decoded move payload}, roster payload or None) from rom/dlc/."""
    folder = paths.ROM_DIR / SOURCE
    images = sorted(folder.glob('*.bin')) if folder.exists() else []
    if not images:
        sys.exit(f'dlc: no memory card images in {paths.show(folder)} (Flycast vmu_save_*.bin) - '
                 f'the "dlc" group needs them')
    moves, roster = {}, None
    for img in images:
        for name, p in vmu_files(img):
            if name.startswith('FIREPROD.W'):
                p = bytes(~b & 0xFF for b in p)
                slot, size = struct.unpack_from('<HI', p, 2)
                if slot < 100 and slot not in moves:
                    moves[slot] = p[:size]
            elif name == 'FIREPROD.E01' and roster is None:
                if len(p) != E_SIZE or sum(p[:E_SIZE - 4]) & 0xFFFFFFFF != struct.unpack_from('<I', p, E_SIZE - 4)[0]:
                    sys.exit(f'dlc: {img.name} FIREPROD.E01: wrong size or checksum')
                roster = p
    return moves, roster


def english_names():
    """{slot: English name} from translation/text/dlc_moves.csv (the Japanese-named moves)."""
    import csv
    p = paths.TEXT / 'dlc_moves.csv'
    if not p.exists():
        return {}
    with open(p, encoding='utf-8', newline='') as f:
        return {int(r['slot']): r['english'] for r in csv.DictReader(ln for ln in f if not ln.startswith('#'))
                if r.get('english')}


FINISHER = 0x24C                    # the profile's finisher name in an edit record (free text)
FINISHER_END = 0x276                # +0x276..+0x27F is appearance data: never touch it
RECORD = 640


def roster_english(roster, names):
    """The roster with translation/text/dlc_roster.csv's finisher names (tokens for `names`)."""
    import csv
    import fpdtext
    p = paths.TEXT / 'dlc_roster.csv'
    if not p.exists():
        return roster
    out = bytearray(roster)
    with open(p, encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(ln for ln in f if not ln.startswith('#')))
    for r in rows:
        if not r.get('english'):
            continue
        at = 50 + int(r['index']) * RECORD + FINISHER
        size = FINISHER_END - FINISHER
        if bytes(out[at:at + size]).split(b'\0')[0].decode('cp932') != r['japanese']:
            sys.exit(f'dlc_roster.csv {r["index"]}: the roster\'s finisher is not {r["japanese"]!r}')
        b = fpdtext.encode(fpdtext.resolve(r['english'], names, f'dlc_roster.csv {r["index"]}'))
        if len(b) >= size:
            sys.exit(f'dlc_roster.csv {r["index"]}: {r["english"]!r} is too long')
        out[at:at + size] = b + bytes(size - len(b))
    struct.pack_into('<I', out, E_SIZE - 4, sum(out[:E_SIZE - 4]) & 0xFFFFFFFF)   # the file's checksum
    return bytes(out)


# Corrections to the downloadable wrestlers (owner, 2026-10-28), in every build: index -> (name1 = the
# short name in lists, name2, name2 shown first in the full name). Written full-width like the rest.
ROSTER_FIXES = {
    33: ('Bubba', 'Ray', False),         # the D-Von and Bubba Ray records had each other's names
    34: ('D-Von', 'Dudley', False),
    44: ('Matt', 'Hardy', False),        # was Hardy / Matt, name2 first: lists showed "Hardy"
}


def _wide(text):
    return ''.join('\u3000' if c == ' ' else chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c for c in text)


def roster_fixed(roster):
    """The roster with ROSTER_FIXES applied and its checksum refreshed."""
    out = bytearray(roster)
    for i, (n1, n2, second_first) in ROSTER_FIXES.items():
        at = 50 + i * RECORD
        for off, size, text in ((2, 14, n1), (0x10, 20, n2)):
            b = _wide(text).encode('cp932')
            if len(b) >= size:
                sys.exit(f'dlc: roster {i}: {text!r} is too long')
            out[at + off:at + off + size] = b + bytes(size - len(b))
        out[at + 1] = (out[at + 1] & 0x7F) | (0x80 if second_first else 0)
    struct.pack_into('<I', out, E_SIZE - 4, sum(out[:E_SIZE - 4]) & 0xFFFFFFFF)
    return bytes(out)


def block(english=True, names='real'):
    """The memory image for the SBL entry, and a one-line summary. english: name the moves
    translation/text/dlc_moves.csv lists in English (not in the Japanese build)."""
    moves, roster = sources()
    if roster:
        roster = roster_fixed(roster)
    if roster and english:
        roster = roster_english(roster, names)
    for slot, name in (english_names() if english else {}).items():
        if slot in moves:
            b = name.encode('cp932')
            if len(b) > 0x2B:
                sys.exit(f'dlc_moves.csv slot {slot}: {name!r} is longer than 43 bytes')
            p = bytearray(moves[slot])
            p[8:0x34] = b + bytes(0x2C - len(b))
            moves[slot] = bytes(p)
    out = bytearray(BLOCK_SIZE)
    if roster:                      # in the E04 slot: players' own E01-E03 stay free and load beside it
        at = ROSTER_SLOT * E_SIZE
        out[at:at + E_SIZE] = roster
    table = [0] * 101
    used = 0
    for slot in sorted(moves):
        p = moves[slot]
        if used + len(p) > TABLE_COPY - POOL:
            sys.exit(f'dlc: the moves need more than the pool holds (slot {slot})')
        at = POOL - E_BASE + used
        out[at:at + len(p)] = p
        table[slot] = POOL + used
        used += (len(p) + 3) & ~3
    table[100] = used
    struct.pack_into('<101I', out, TABLE_COPY - E_BASE, *table)
    return bytes(out), f'{len(moves)} moves ({used} bytes), roster {"in E04" if roster else "none"}'


def step(files, english=True, names='real'):
    """Add the entry to SBL.BIN (its code patches are the 'dlc' group in build.py)."""
    data, what = block(english, names)
    s = sbl.Sbl(files.get('/SBL.BIN'))
    if len(s) != ENTRY:
        sys.exit(f'dlc: SBL.BIN has {len(s)} entries, expected {ENTRY}')
    s.entries.append([s.end, 0])           # a new entry at the end (put() places it there)
    s.put(ENTRY, data)
    files.put('/SBL.BIN', s.bytes())
    print(f'dlc: SBL entry {ENTRY}: {what}')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['list']:
        moves, roster = sources()
        for slot in sorted(moves):
            print(f'W{slot:02d} {len(moves[slot]):6d}  {moves[slot][8:0x34].split(bytes(1))[0].decode("cp932", "replace")}')
        print('roster:', 'E01' if roster else 'none')
    elif argv[:1] == ['routine']:
        print(routine().hex())
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
