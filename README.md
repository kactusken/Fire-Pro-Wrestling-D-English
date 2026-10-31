# Fire Pro Wrestling D — English Translation

An English translation patch for **Fire Pro Wrestling D**, Spike's 2001 Dreamcast game, released
only in Japan.

Everything the player needs is in English: every menu and mode, the 220-wrestler roster with
nicknames and profiles (in a real-names and a parody-names patch), all 1,000 move names, the whole
of Edit Mode including CPU Logic, Victory Road Kai, and the network mode's built-in DreamPassport
browser. The menu buttons, profile tags, result banners and the browser's 13 sheets of buttons and
keyboard keys are redrawn as English pictures. The game's text area was repacked to make room for
the English, and the browser's compressed (VQ) textures are re-encoded after redrawing.

**The downloadable content is built in.** In 2001-2002 Spike offered new moves and wrestlers that
players downloaded through the Dreamcast's modem onto a memory card. The servers are long gone.
The (All Unlocked) patches put all of it in the game: [100 downloadable moves and 50 downloadable
wrestlers](#the-downloadable-content-built-in), ready from the first boot with no memory card or
save files needed.

**[See screenshots](docs/SCREENSHOTS.md)** of the patched game. **[Read the guide](https://kactusken.github.io/Fire-Pro-Wrestling-D-English/guide/)**: controls, every mode, Edit Mode, all 220 wrestlers, the 50 downloadable ones and every move, and the secrets.

> **Status: v1.0, complete.** Tested in Flycast over several rounds, including every Victory Road
> ending. The network mode could only be checked offline: Sega's servers are gone, so the online
> pages can't be reached. Loading saves made with the Japanese game hasn't been tested yet. Please
> report anything that looks wrong ([how to report](#reporting-problems)).
> [CHANGELOG.md](CHANGELOG.md) lists what's in each release.

## The downloadable content, built in

Through its network mode, Fire Pro Wrestling D let players download new moves and Spike's own
edit wrestlers onto a memory card.
With the servers shut down, that content survived only as memory card files passed around by
fans. The **(All Unlocked)** patches make it part of the game:

- **100 downloadable moves** (W00-W99). W00-W56 are the official downloads Spike released;
  W57-W99 were backported from *Fire Pro Wrestling Z* by the Fire Pro community, some fixed so
  they can finish a match. They are at the end of Move Edit's lists, in red. The six moves named in Japanese have English names in the English patches.
- **50 downloadable wrestlers**, the edit wrestlers Spike released, each in their promotion on
  the wrestler select screen: 2 Cold Scorpio, Naomichi Marufuji, Tajiri, Rey Mysterio Jr., the
  Hardys and the Dudleys, Mark Coleman and Randy Couture, Ted DiBiase, Bob Backlund, Barry
  Windham, Seiji Sakaguchi, Killer Khan... and Zangief. Their finishers are in English in the
  English patches.
- **No memory card needed.** Everything loads at every boot. Your own edit wrestlers in groups
  1-3 load beside the downloadable wrestlers, which sit in edit group 4 (Ext Data 4); your own
  Ext Data 4 file replaces them. To build on one of them, use Edit Wrestler > Save/Load > Quick
  Load > Ext Data 4, then Quick Save into another group.
- **Your saves stay safe.** These patches won't save over a file on a card unless that file was
  loaded from it ("Can't overwrite: load it first."), so insert your memory card before switching
  on.

Thanks to the Fire Pro community for preserving the downloads and for the backports. Every
downloadable move and wrestler is in the [guide](https://kactusken.github.io/Fire-Pro-Wrestling-D-English/guide/),
with full profiles and move lists. With the other patches, the moves still load from a memory card
holding the move files, as on the original.

## Downloads

Get the latest zip from the [Releases](../../releases) page. It contains 5 patches. Pick one:

| Patch | What you get |
|---|---|
| **Fire Pro Wrestling D (English) (Real Names)** | The translation, with the real names of the wrestlers the characters stand for. |
| **Fire Pro Wrestling D (English) (Parody Names)** | The translation, with the game's own parody names for the wrestlers. |
| **Fire Pro Wrestling D (English) (Real Names) (All Unlocked)** | Real Names with everything unlocked from the start, plus the 100 downloadable moves and the 50 downloadable wrestlers built in ([above](#the-downloadable-content-built-in)). |
| **Fire Pro Wrestling D (English) (Parody Names) (All Unlocked)** | The same, with Parody Names. |
| **Fire Pro Wrestling D (Japan) (All Unlocked)** | The original Japanese game with the same unlocks and downloads. |

## How to patch

**[Follow the step-by-step guide](docs/HOW_TO_PATCH.md).** You patch two of the disc's files with
[Delta Patcher](https://github.com/marco-calautti/DeltaPatcher/releases), then open the disc's
original `.cue`. Nothing needs renaming.

You need your own copy of the original Japanese disc. Disc images are not provided here.

- Game: *Fire Pro Wrestling D* (Japan), serial T-18805M, a 50-track BIN/CUE dump (Redump).
- The main track must match: `Fire Pro Wrestling D (Japan) (Track 50).bin`, 112009296 bytes,
  CRC32 `c0114432`, SHA-1 `c6037b763e59b801101b9538cbf3ec406e14490b`.

Other xdelta tools work too, such as [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/)
in a web browser or `xdelta3` on the command line, but the patched files must end up with the
original file names. To keep several versions in one folder, use the patch's `.cue` and name the
patched files as it does.

Tested in [Flycast](https://github.com/flyinghead/flycast).

## Notes for players

- **Names.** The Real Names patches use the wrestlers' real names and nicknames and the real
  promotions (NEW JAPAN, ALL JAPAN, NOAH, WWF, WCW...). The Parody Names patches keep the names
  the game itself uses, translated. A few names are cut short in the wrestler list (known, left as is).
- **What's still in Japanese.** Staff credits, decorative art (logos, shirts, signs, ring art),
  the intro movie's captions, the kana and kanji keys of the name-entry keyboards (its ABC page
  covers English names), and in the network mode the kana keys of the soft keyboard. The pages
  that Sega's servers sent are gone and can't be translated.
- **Saves.** The patches use the same save files as the Japanese game, so saves should carry
  over, but this hasn't been tested yet. Edit wrestlers named in Japanese keep their Japanese
  names.
- **Network mode.** The browser, its settings, mail, chat and the upload form are in English, but
  the servers it connected to were shut down long ago.
- **(All Unlocked) patches.** Everything that winning every Victory Road title (or L+R+Y at the
  main menu) opens is open from the start: Credits, the full edit limit, all elimination teams,
  plus [the downloadable content](#the-downloadable-content-built-in).
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
| [docs/HOW_TO_PATCH.md](docs/HOW_TO_PATCH.md) | The simplest way to patch your disc, with no renaming |
| [docs/BUILDING.md](docs/BUILDING.md) | Setting up, building, making patches, and the checking tools |
| [docs/TRANSLATION.md](docs/TRANSLATION.md) | Text file formats, scope, style guide, glossary, and naming decisions |
| [docs/EDITING.md](docs/EDITING.md) | Editing the in-game text graphics |
| [docs/PATCHES.md](docs/PATCHES.md) | How each code patch works |
| [docs/TECHNICAL.md](docs/TECHNICAL.md) | The game's disc layout, archives, compression, data formats, and memory map |
| [docs/PLATFORM.md](docs/PLATFORM.md) | DREAMCAST pitfalls for this kind of work |
| [docs/HIDDEN_CONTENT.md](docs/HIDDEN_CONTENT.md) | Unlockables, debug features, and unused and cut content |
| [docs/guide/](https://kactusken.github.io/Fire-Pro-Wrestling-D-English/guide/) | The player's guide (one page; its wrestler and move tables come from `tools/guidedata.py`) |
| [tools/README.md](tools/README.md) | Every tool, what it's for and how to run it |

Quick start:

```sh
python3 tools/extract.py                 # unpack the disc in rom/ into extracted/
python3 build.py                         # -> build/Fire Pro Wrestling D (English).bin
python3 make_patches.py --version v1.0   # -> release/*.xdelta and a zip (needs xdelta3)
```

## AI disclosure

AI assisted with the translation.

## Legal

This is a non-commercial fan translation, not affiliated with or endorsed by the game's developers
or publishers. It contains no copyrighted game data that would let
anyone play without owning the game. The patches only work on your own copy of the disc.
Fire Pro Wrestling D and its contents belong to their respective owners. The Japanese text in this
repository is included for translation and reference.

The code in this repository is released under the [MIT License](LICENSE).
