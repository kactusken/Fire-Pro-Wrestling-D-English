# Hidden content

Unlockables, debug features, button codes, cut and unused content. Every find says how sure it
is:

- *verified in game* - seen in an emulator (with the date, and the build or code used to get there)
- *seen headless* - seen in the Flycast core run without a window, not yet by a player
- *from the code* - read in the disassembly, not seen running
- *from the data* - in the game's files or tables, whether or not the code uses it
- *from a guide* / *from fans* - a published source, not yet matched with the code

Addresses are RAM addresses (1ST_READ.BIN is loaded at 0x8C010000: file offset = address -
0x8C010000) unless marked as a file offset. Optional patches that switch some of this on are in
[PATCHES.md](PATCHES.md).

**Prior art (2026-10-28).** No page on The Cutting Room Floor or Data Crystal could be found for
this game, and nothing on GameFAQs or in Japanese sources about hidden content. Almar's Guides
lists CodeBreaker codes that fill the per-promotion wrestler lists (RAM about 0x8C355BD4 onward,
*from a guide*, not tried). On the Saturn, Fire Pro Wrestling S's debug menu is reached by patching
its start-up mode (32bits newsletter); Fire Pro D works the same way - see below.

## Contents
- [L+R+Y: unlock everything](#lry-unlock-everything) · [Debug menus](#debug-menus) ·
  [Developer leftovers](#developer-leftovers) · [Unused files and pictures](#unused-files-and-pictures) ·
  [Searched and not found](#searched-and-not-found) · [How to see it yourself](#how-to-see-it-yourself)

## L+R+Y: unlock everything
*seen headless* (2026-10-28, original and the English test build)

At the main menu, press **L, R and Y together** (all three on the same frame). A sound plays and
the game saves: it now behaves as if every Victory Road title had been won. The check is at
0x8C09A884; it sets the save's progress level (save data + 0x43FD, save data at 0x8C1BBC48) to 3,
the value Victory Road gives for clearing all six titles (1 for any one, 2 for three).

What level 3 opens: **Credits** in Options (the staff roll), and 13 more teams in the elimination
team list (41 instead of 28) - both *seen headless*. *From the code*: the Edit Mode limit read from
the table at 0x8C12E0B0 goes 150 / 200 / 250 / 300 with the level, and level 3 enables an extra
in the edit colour screen (0x8C0406DE).

Related, *from the code* only: holding exactly L+R+Y+A while saving an edit wrestler (0x8C035620)
saves the slot with a different status (2 instead of 1); what that changes wasn't traced.

## Debug menus
*seen headless* (2026-10-28, original; the scene select also in the English build)

The program still holds six developer menus. Nothing in it calls or points to them, so they can't
be reached by playing. At start-up the game jumps to its loop through the word at 0x8C015AB8
(file offset 0x5AB8, normally 0x8C0913C4); pointing it at a menu's function boots straight into
that menu. Each menu takes a hex number: Up/Down change a digit, Left/Right move between digits,
A starts the entry. They are drawn in a plain debug font (blue screen); the entries are English
or Japanese as the developers wrote them, and are left as they are.

| Menu | Function | What it holds |
|---|---|---|
| Scene select | 0x8C0A954C | Test, Demo (actually the costume palette editor, "PRESS START TO EDITPAL SAVE"), Staff (the credits), ReCostume, EditInfo, Illumination (the elimination team viewer), the result and versus screens, Title, Main Menu, Wrs Sel; 10 starts the normal game |
| Test menu | 0x8C0A9688 | 旗テスト (flag test), SCIサンプル, ドリームパスポート実験くん (opens the browser's home page), フォントの変更 (font change), EffectView, なんとなくテスト ("just a test": an arena with ring and crowd; its lighting and effects settings - brightness, view angle, spotlights, fireworks, smoke) |
| Editor select | 0x8C04B9B4 | ONE NIGHT MATCH, DOT EDITOR TEST (the logo editor), RENAME TEST |
| BUP TEST / RING VIEW | 0x8C01435C | BUP TEST is Sega's memory card sample ("BACKUP SAMPLE #2": a card in port A-1, A save, X load, Y delete a test file). The test file is named FIREPROD.SYS, the game's own system save (options, records, the unlock level), so use it only with a spare card. RING VIEW is a ring and hall viewer; unlisted numbers: 4 drive status, 0x20 memory table, 0x30 sound test, 0x40 a grid. 5, 0x100 and 0x101 write files to the developers' PC and do nothing useful on a console |
| Model Test | 0x8C0A8A48 | a wireframe model viewer |
| Sound test | 0x8C0A9390 | "SOUND TEST / DRIVER VERSION 2.02.07", sound effects by number |

A match information overlay (format strings at file offsets 0xB3324 / 0xB335C, function
0x8C030A80) is also never called (*from the code*, not run).

## Developer leftovers
*from the data*

- Paths to the developers' PC in 1ST_READ.BIN: `D:/GODA/USE/WRSPAL/DAT/PAL%03d.BIN`,
  `PATRS%02d.BIN`, `D:/GODA/USE/LOGIC/LOGIC%02d.BIN`, `D:/GODA/USE/DOWNWAZA/WAZA%02d.DWS` - the
  debug menus' export of palettes, CPU logic and moves.
- Editor leftovers in the text: サンプルＣＧロード ("load sample CG", dot editor), a "sample
  gradation" in the costume colours, ダミー ("dummy").

## Unused files and pictures
*from the data*

- `/0GDTEX.PVR` (the disc label picture) and `/DPTEX/WALLPAPER00-03.PVR` (browser wallpapers) are
  named by no file. `/DPMODEL/` holds only a note: "Do NOT remove the \dpmodel directory."
- In SBL.BIN: test patterns (entry 252, entry 234 item 3: noise and moiré; entry 253: concentric
  hearts), a red X with a "D" (234 item 62, a placeholder), an English feature list "4on4 TAG
  MATCH / NET-WORK / EDIT / ORIGINALITY" (234 item 8), and the intro's "1989 誕生 / 2001 新生".

## Music
*seen headless / from the code* (2026-10-28)

All 46 CD audio tracks (4-49) are used: 4-31 the 28 entrance themes (Edit's Theme 1-28), 32-43
the 12 match BGMs ("Spinning Pancer", "Another Tornado", "Blue Thunder"... - names at
0x8C128BF0), 44-46 result/ceremony music (leagues, tournaments, Victory Road, Title Match), 47 a
9-second "no theme" jingle (theme value 0xFF, which nothing seems to set), 48 the intro/versus
sting, 49 the staff credits and Victory Road ending. The menus' music comes from the sound chip,
not the CD. Edit's Theme is capped at 28 by a data field (descriptor 0x8C12DF80, maximum at
0x8C12DF86 = 27); the entrance code plays value+4 without a range check, so a raised cap would
let edit wrestlers enter to the match BGMs (seen headless: theme 41 asked for track 45).

## Searched and not found
- Button codes anywhere but the main menu (every compare against a multi-button value was
  checked: title screen, wrestler select, menus) and name-entry passwords (the only string compare
  checks file tags).
- Unreached main menu modes: the 11 items are modes 0-10; 11 returns to the title.
- Hidden or test wrestlers: the roster is exactly the 220 selectable records, with no spare slots.
- Unused move names: all 1,000 are used by at least one move.
- A start-up mode byte like Fire Pro Wrestling S's: the start-up jump word is the only switch.

## How to see it yourself
| Find | How |
|---|---|
| Unlock everything | L+R+Y together at the main menu (the game saves at once), or the "(All Unlocked)" patches: open from the start, no code |
| A debug menu | `python3 build.py --unlocks debug-scene-select` (or `debug-test-menu`, `debug-editor-select`, `debug-bup-select`, `debug-model-test`, `debug-sound-test` - one at a time); the build boots into it |
| The same in RAM | poke the menu's function address into 0x8C015AB8 before the game starts (frame 0) |
