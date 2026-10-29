#!/usr/bin/env python3
"""Build the translated image from the original. Standard library only.

  python3 build.py [--name NAME] [--unlocks all|none|GROUP,...] [--clean]
      -> build/NAME.<ext> (default NAME: "<game> (English)")

Steps (default folders shown; move any of them with the folder options - see --help):
  1. verify the original in rom/ (size + SHA-1; --skip-verify skips the hash)
  2. prepare build/NAME: a fresh copy of the original, or - much faster for big images - the last
     build with every range it wrote restored from the original (tools/image.py; --clean copies)
  3. text: translation/script/ and translation/text/ into the game's files (TEXT_STEPS)
  4. code patches picked by --unlocks (CODE_PATCHES, tools/codepatch.py; debug-* groups only when named)
  5. images: for every catalogued image the English file the catalogue picks (hand-made >
     approved > rendered), imported by tools/gfx.py; the final set is copied to review/images-english/
  6. write every changed file back into the image (files that fit in place first)

Wrestler names: --names real (default) or parody - the two English releases. Text steps that hold
names read NAMES (set from --names) to pick the column.

Test builds: --boot PART starts the game straight in PART (BOOT_PATCHES, once known);
--no-translation skips text and images, and gameplay patches unless --unlocks is given - on its
own the result is byte-identical to the original (tools/check.py --control proves it).
Developer flags (never for releases): --no-text FILE skips one text file.
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'tools'))
import catalog  # noqa: E402
import codepatch  # noqa: E402
import disc  # noqa: E402
import dpnet  # noqa: E402
import dptex  # noqa: E402
import dlc  # noqa: E402
import fpdtext  # noqa: E402
import gfx  # noqa: E402
import image  # noqa: E402
import paths  # noqa: E402

# Gameplay patches: (group, file, address, original, new, description) - see tools/codepatch.py.
# Groups named debug-* are developer extras (debug menus, cheat windows): never in "all" or the
# default, only when named, never in a release variant.
# The debug-* groups each change the start-up jump (the word at 0x8C015AB8 that normally points to
# the game loop 0x8C0913C4) to boot into one of the program's unreached test menus - one at a time
# (docs/HIDDEN_CONTENT.md, docs/PATCHES.md).
_BOOT = 0x8C015AB8
CODE_PATCHES = [
    # The save's unlock flag (save + 0x43FC, 13 extra elimination teams) and progress level (+0x43FD:
    # Credits in Options at 1+, the edit limit 150/200/250/300, an edit colour option at 3) are
    # set by L+R+Y at the main menu or by clearing Victory Road titles, and read only through these
    # two getters: each now returns the full value (rts; mov #N,r0). docs/PATCHES.md "Unlock all".
    ('unlocks', '/1ST_READ.BIN', 0x8C015C04, 0x911BD313, 0xE001000B, 'unlock flag always on (extra elimination teams)'),
    ('unlocks', '/1ST_READ.BIN', 0x8C015C12, 0x9115D310, 0xE003000B, 'progress level always 3 (credits, edit limit 300, colours)'),
    # The downloadable moves and the downloadable wrestlers (Spike's edit set), read from a new SBL.BIN entry on cold boot
    # (tools/dlc.py; the routine replaces the never-called match overlay 0x8C030A80, the hook is
    # the cold-boot jump to the card autoload). docs/PATCHES.md "Downloadable moves".
    ('dlc', '/1ST_READ.BIN', dlc.ROUTINE_AT, bytes.fromhex('e62fd62fc62fb62fa62f962f862ffbffebffdbffcbff224fd87f47d38390326d46d2dc011821228d226c45d17c90126344d23e03282309897790de03'),
     bytes.fromhex('224f08d008d509d40b40090008d109d265e3166002221043fb8f0472264f06d02b4009002c2e018c604b1d8c72010000acb6268c8cba1b8cd8e3038c'), 'boot routine: load the built-in downloadable moves and roster'),
    ('dlc', '/1ST_READ.BIN', dlc.HOOK, dlc.AUTOLOAD, dlc.ROUTINE_AT, None),
    # Save guard: Memory Card > Save won't overwrite a file on a card unless that file was loaded
    # from (or saved to) that same card - e.g. a card put in after power-on (tools/dlc.py,
    # docs/PATCHES.md "Save guard"). The message is replaced by the Japanese one in the Japanese build.
    ('saveguard', '/1ST_READ.BIN', dlc.GUARD_AT, bytes.fromhex('33600988028b709000e3360d3cd16b9012623dd32e00382009896790de020172260d23600a88028b609000e2260d5c9036dbdd035b9036de350d01e35690de023732258b1de50b4b00e432d30b4e362f1ee50b4b00e44b904b9adc02ff70dc3a262fdc03362fa184a063084008400c33a28418400c33a3841840084008400c33'),
     dlc.guard('english'), 'save guard: no overwriting a file that was not loaded from that card'),
    ('saveguard', '/1ST_READ.BIN', dlc.GUARD_LITERAL, dlc.FIND_FILE, dlc.GUARD_AT, None),
    ('debug-scene-select', '/1ST_READ.BIN', _BOOT, 0x8C0913C4, 0x8C0A954C, 'boot into the scene select (10 = the game)'),
    ('debug-test-menu', '/1ST_READ.BIN', _BOOT, 0x8C0913C4, 0x8C0A9688, 'boot into the test menu (flag test, EffectView...)'),
    ('debug-editor-select', '/1ST_READ.BIN', _BOOT, 0x8C0913C4, 0x8C04B9B4, 'boot into ONE NIGHT MATCH / DOT EDITOR / RENAME TEST'),
    ('debug-bup-select', '/1ST_READ.BIN', _BOOT, 0x8C0913C4, 0x8C01435C, 'boot into BUP TEST / RING VIEW'),
    ('debug-model-test', '/1ST_READ.BIN', _BOOT, 0x8C0913C4, 0x8C0A8A48, 'boot into the model viewer'),
    ('debug-sound-test', '/1ST_READ.BIN', _BOOT, 0x8C0913C4, 0x8C0A9390, 'boot into the sound test'),
]
UNLOCK_GROUPS = sorted({p[0] for p in CODE_PATCHES})
PLAYER_GROUPS = [g for g in UNLOCK_GROUPS if not g.startswith('debug-')]

# --boot: (part, file, address, original, new) - patches that start the game in a given part.
BOOT_PATCHES = {
}


def to_offset(name, addr):
    """GAME-SPECIFIC: file offset of a RAM address in file `name` (overlay base, ELF segments, ...)."""
    if name == '/1ST_READ.BIN':                 # loaded at 0x8C010000 (docs/PLATFORM.md)
        return addr - 0x8C010000
    raise SystemExit(f'build.py to_offset(): no address mapping for {name} yet')


# Wrestler names: 'real' (the real wrestlers each character stands for) or 'parody' (the game's own
# names, romanized). Set by --names before the text steps run.
NAME_SETS = ('real', 'parody')
NAMES = 'real'

# Text steps: (text file or folder under translation/, function(path, files)). Each inserts the
# English into the game's files through `files` and stops with a clear message if anything doesn't fit.
# Zero-padding files a grown file may take room from when the disc is full (PS2 disc.py
# take_from_padding: their end is cut off) - e.g. ['/DUMMY.DAT']; check they are all zeros.
PADDING_DONORS = []

TEXT_STEPS = [
    ('text/ui.csv', lambda path, files: fpdtext.step_ui(files, NAMES)),       # ui.csv + fixed.csv -> 1ST_READ.BIN
    ('text/wrestlers.csv', lambda path, files: fpdtext.step_sbl(files, NAMES)),   # roster + moves -> SBL.BIN
    ('text/dpmsg.csv', lambda path, files: dpnet.step(files)),           # network mode browser text
]


class Files:
    """The game's files for this build: read from the image on first use, written back at the end."""

    def __init__(self, d):
        self.d, self.data, self.changed = d, {}, set()

    def get(self, name):
        if name not in self.data:
            self.data[name] = bytearray(self.d.read_file(self.d.find(name)))
        return self.data[name]

    def put(self, name, data):
        self.data[name] = bytearray(data)
        self.changed.add(name)


def unlock_groups(value):
    if value == 'all':
        return set(PLAYER_GROUPS)
    if value == 'none':
        return set()
    groups = {g.strip() for g in value.split(',') if g.strip()}
    if groups - set(UNLOCK_GROUPS):
        raise argparse.ArgumentTypeError(f'expected all, none or some of {",".join(UNLOCK_GROUPS) or "(no groups yet)"}')
    return groups


def images_step(files):
    final = catalog.final_images()
    missing, changed, _ = catalog.stale()
    if missing or changed:
        print(f'note: {len(missing) + len(changed)} automatic renders are out of date - run tools/render.py '
              f'(building with the frozen files there are)')
    # the network mode's label atlases come VQ-encoded from tools/dptex.py, the rest via gfx
    n = gfx.import_images({k: p for k, (tag, p) in final.items() if not k.startswith('dp_')}, files)
    n += dptex.step(files)
    if paths.ENGLISH_IMAGES.exists():
        shutil.rmtree(paths.ENGLISH_IMAGES)
    if final:
        paths.ENGLISH_IMAGES.mkdir(parents=True)
        for name, (tag, p) in final.items():
            shutil.copyfile(p, paths.ENGLISH_IMAGES / f'{name}.png')
        counts = {}
        for tag, _ in final.values():
            counts[tag] = counts.get(tag, 0) + 1
        print(f'images: {n} imported (' + ', '.join(f'{c} {t}' for t, c in sorted(counts.items())) + ')')


def verify_original(original):
    """SHA-1 of the original image, once: the result is remembered with the file's size and
    modification time (build/original.verified), so later builds only re-hash a changed file
    (a DVD image takes ~20 s to hash)."""
    st = original.stat()
    stamp = f'{original.resolve()} {st.st_size} {st.st_mtime_ns} {paths.ORIGINAL["sha1"]}'
    memo = paths.BUILD / 'original.verified'
    if memo.exists() and memo.read_text() == stamp:
        return
    print('verifying the original...')
    if image.sha1(original) != paths.ORIGINAL['sha1']:
        sys.exit(f'{original.name} does not match the expected SHA-1 {paths.ORIGINAL["sha1"]}')
    paths.BUILD.mkdir(parents=True, exist_ok=True)
    memo.write_text(stamp)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--name', default=f'{paths.GAME_FILE} (English)')
    ap.add_argument('--skip-verify', action='store_true', help="don't hash the original image")
    ap.add_argument('--clean', action='store_true', help='copy the original instead of restoring the last build')
    ap.add_argument('--no-translation', action='store_true', help='skip text and images (alone: identical to the original)')
    ap.add_argument('--unlocks', type=unlock_groups, metavar='all|none|GROUP,...',
                    help='gameplay patches: all (default; debug-* groups only when named), none or some groups; '
                         'none with --no-translation')
    ap.add_argument('--names', choices=NAME_SETS, default='real',
                    help="wrestler names: real (default) or the game's parody names")
    ap.add_argument('--boot', choices=sorted(BOOT_PATCHES), help='TEST BUILD: start the game in this part')
    ap.add_argument('--no-text', action='append', default=[], metavar='FILE',
                    help='developer: leave this text file untranslated (repeatable)')
    args = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    global NAMES
    NAMES = args.names
    if args.unlocks is None:
        args.unlocks = set() if args.no_translation else set(PLAYER_GROUPS)

    original = paths.ROM
    if not original.exists():
        sys.exit(f'put the original image in {paths.show(paths.ROM_DIR)} (or pass --rom): {paths.ORIGINAL_NAME}')
    if original.stat().st_size != paths.ORIGINAL['size']:
        sys.exit(f'{original.name}: {original.stat().st_size} bytes, expected {paths.ORIGINAL["size"]} - not the right image')
    if not args.skip_verify:
        verify_original(original)

    out = paths.BUILD / (args.name + original.suffix)
    with image.prepare(original, out, clean=args.clean) as f:
        d = disc.Disc(f, writable=True)
        files = Files(d)

        if not args.no_translation:
            for rel, step in TEXT_STEPS:
                if rel in args.no_text:
                    print(f'text: skipped {rel} (--no-text)')
                    continue
                step(paths.TRANSLATION / rel, files)

        patches = CODE_PATCHES
        if args.no_translation:     # the save guard's message in Japanese
            patches = [p[:4] + (dlc.guard('japanese'),) + p[5:] if p[0] == 'saveguard' and p[2] == dlc.GUARD_AT
                       else p for p in CODE_PATCHES]
        codepatch.apply(files, patches, args.unlocks, to_offset)

        if not args.no_translation:
            images_step(files)

        if 'dlc' in args.unlocks:
            dlc.step(files, english=not args.no_translation, names=NAMES)

        if args.boot:
            codepatch.apply(files, [(args.boot, *p, f'TEST BUILD: boots into {args.boot}') for p in BOOT_PATCHES[args.boot]],
                            {args.boot}, to_offset)

        def fits(name):
            return (len(files.data[name]) + disc.SECTOR - 1) // disc.SECTOR <= d.allocated_sectors(d.find(name))
        for name in sorted(files.changed, key=lambda n: (not fits(n), n)):  # fixed order: same disc layout every build
            d.write_file(d.find(name), bytes(files.data[name]), relocate=True,
                         **({'donors': PADDING_DONORS} if PADDING_DONORS else {}))
            print(f'patched {name}')
    disc.companion_files(out, original)
    print(f'done: {paths.show(out)}  ({len(files.changed)} files patched)')
    return out


if __name__ == '__main__':
    main()
