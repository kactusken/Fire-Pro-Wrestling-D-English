# Fire Pro Wrestling D — English Translation

An English translation patch for **Fire Pro Wrestling D**, *(year, platform: DREAMCAST, released only in Japan)*.

*(What it covers, with real counts: modes, menus, roster, moves, graphics. One line on the
hardest technical part - a new font, a renderer hook.)*

**[See screenshots](docs/SCREENSHOTS.md)** of the patched game.

> **Status: work in progress.** *(At release: "first public beta" - what is translated, what
> hasn't been played through yet, please report problems ([how to report](#reporting-problems)).
> [CHANGELOG.md](CHANGELOG.md) lists what's in each release.)*

## Downloads

Get the latest zip from the [Releases](../../releases) page. It contains *(N)* patches. Pick one:

| Patch | What you get |
|---|---|
| **Fire Pro Wrestling D (English)** | The translation, with the game otherwise unchanged. |

## How to patch

You need your own copy of the original Japanese disc. Disc images are not provided here.

- Game: *Fire Pro Wrestling D* (Japan), serial *(serial)*. *(Reissues that won't patch.)*
- The image must match: `Fire Pro Wrestling D (Japan) (Track 50).bin`, 112009296 bytes, CRC32 `c0114432`,
  SHA-1 `c6037b763e59b801101b9538cbf3ec406e14490b`.

Then:

1. Apply the `.xdelta` patch with an xdelta tool:
   - [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/) runs in your web browser
     (CD images; it may not cope with a multi-GB DVD image).
   - Delta Patcher is a desktop app for Windows, macOS and Linux.
   - On the command line: `xdelta3 -d -s "Fire Pro Wrestling D (Japan) (Track 50).bin" "patch.xdelta" "patched.bin"`
2. *(.bin/.cue: rename the patched .bin to match the .cue from the zip.)*
3. Open it in your emulator. *(Tested in ...)*

## Notes for players

- **Names.** *(real names, spellings)*
- **What's still in Japanese.** *(logos and other art, movies, audio, keyboards, credits, save title)*
- **Saves.** *(do saves from the original work?)*
- **Hidden content.** See [docs/HIDDEN_CONTENT.md](docs/HIDDEN_CONTENT.md).

## Reporting problems

Open an [issue](../../issues) with:

- a screenshot,
- which patch you used,
- where you were: the mode and menu, or roughly what had just happened.

Text that is cut off, overlaps, or still shows Japanese is especially helpful.

## For ROM hackers and contributors

Everything needed to rebuild the patches from the original disc is in this repository: the
translated text, the patching code (Python 3, no dependencies for the build) and documentation of
the game's formats.

| Document | What's in it |
|---|---|
| [docs/BUILDING.md](docs/BUILDING.md) | Setting up, building, making patches, and the checking tools |
| [docs/TRANSLATION.md](docs/TRANSLATION.md) | Text file formats, scope, style guide, glossary, and naming decisions |
| [docs/EDITING.md](docs/EDITING.md) | Editing the in-game text graphics |
| [docs/PATCHES.md](docs/PATCHES.md) | How each code patch works |
| [docs/TECHNICAL.md](docs/TECHNICAL.md) | The game's disc layout, archives, compression, data formats, and memory map |
| [docs/PLATFORM.md](docs/PLATFORM.md) | DREAMCAST pitfalls for this kind of work |
| [docs/HIDDEN_CONTENT.md](docs/HIDDEN_CONTENT.md) | Unlockables, debug features, and unused and cut content |
| [tools/README.md](tools/README.md) | Every tool, what it's for and how to run it |

Quick start:

```sh
python3 tools/extract.py                 # unpack the disc in rom/ into extracted/
python3 build.py                         # -> build/Fire Pro Wrestling D (English).bin
python3 make_patches.py --version v0.1   # -> release/*.xdelta and a zip (needs xdelta3)
```

## AI disclosure

*(Required - FRAMEWORK.md section 11. A short generic line, e.g. "AI assisted with the
translation." Same wording as `AI_DISCLOSURE` in tools/paths.py.)*

## Legal

This is a non-commercial fan translation, not affiliated with or endorsed by the game's developers
or publishers. It contains no copyrighted game data that would let
anyone play without owning the game. The patches only work on your own copy of the disc.
Fire Pro Wrestling D and its contents belong to their respective owners. The Japanese text in this
repository is included for translation and reference.

The code in this repository is released under the [MIT License](LICENSE).
