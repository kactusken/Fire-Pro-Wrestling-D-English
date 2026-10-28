# Hidden content

Unlockables, debug features, button codes, cut and unused content. Every find says how sure it
is:

- *verified in game* - seen in an emulator (with the date, and the build or code used to get there)
- *from the code* - read in the disassembly, not seen running
- *from the data* - in the game's files or tables, whether or not the code uses it
- *from a guide* / *from fans* - a published source, not yet matched with the code

Addresses: [say how - RAM or file offsets, `$bank:addr` for cartridges, overlay names].
Optional patches that switch some of this on are in [PATCHES.md](PATCHES.md).

**Prior art (2026-10-27).** The Cutting Room Floor has no page for this game. No debug menu or
unused content has been documented. Almar's Guides lists CodeBreaker codes for the Japanese
release, including an unlock for the New Japan wrestlers (*from a guide*, not checked). Fire Pro
Wrestling S on the Saturn has a hidden debug menu with an advanced editor (32bits newsletter), so
a similar menu here is worth hunting for (*lead, unverified*).

## Contents
- [Find](#find) · [Searched and not found](#searched-and-not-found) · [How to see it yourself](#how-to-see-it-yourself)

## [Find]
*verified in game* ([date], `build.py --unlocks group`) / *from the code*

What it is and what it does, how it's reached in the original (or that it can't be), where it
lives (address, file), and a screenshot in `screenshots/` when there is one. Say when a release
patch can't reach it (needs dev-kit hardware, SRAM edits, a test image).

## Debug menus in the program (leads)
*from the data* (2026-10-27) - strings in 1ST_READ.BIN, not yet traced to the code that shows them:
- 0xB6BBC: `< SELECT >  0 : ONE NIGHT MATCH  1 : DOT EDITOR TEST  2 : RENAME TEST  -1 : EXIT`
- 0xBB5EC: `< SELECT >  0 : Test  1 : Demo  2 : Staff  3 : ReCostume  4 : EditInfo  5 : Illumination
  6 : BTR RESULT  7 : VS RESULT  8 : BTR VERSUS  9 : VERSUS  B : Title  C : Main Menu  D : Wrs Sel
  10 : MainGame  -1 : EXIT` - a scene select.
- Nearby: `PRESS START TO EDITPAL SAVE`, `SAVE START %04d / SAVE END %04d` (palette editor),
  `Model Test`, `SE NUMBER = %x`, a lighting test (`明るさの設定`, `画角の設定`, `スポットライト`,
  fireworks and smoke effects), `旗テスト` (flag test), `SCIサンプル`, `ドリームパスポート 実験くん`
  (DreamPassport experiment), `フォントの変更` (font change) with two Windows font names.
- Debug overlays: format strings like `N P T ST1 AN FOM Z` and `SPD INFO T B R TM B RG PT LV BGM`
  (0xB3324, 0xB335C) - a match state display.
Next step: find the code that references these strings (tools/sh4.py refs) and how it is reached.

## Searched and not found
What was checked and came up empty, so nobody searches again: button-code readers, name-entry
passwords, unreached menu entries, unused files, never-set flags.

## How to see it yourself
| Find | How |
|---|---|
| [find] | `python3 build.py --unlocks group` / the "(All Unlocked)" patch / a RAM poke / a cheat code |
