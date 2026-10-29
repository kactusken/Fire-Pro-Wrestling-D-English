# Patches

What the build changes besides text and images, one section per patch: what the original code
does, what changed, why it works, the tool that makes it, limits to respect, and whether it was
*verified in game*.

## Debug menus (debug-* groups, developer builds only)
*Seen headless, 2026-10-28.* At start-up 1ST_READ.BIN jumps to the game loop through the word at
0x8C015AB8 (file offset 0x5AB8, original value 0x8C0913C4). Each `debug-*` group in build.py
`CODE_PATCHES` replaces that word with the address of one of the program's unreached test menus
(docs/HIDDEN_CONTENT.md, "Debug menus"), so the game boots into it; the scene select's entry 10
continues into the normal game. All groups change the same word, so build one at a time (a
second fails the original-bytes check). They are never part of `all` or a release variant.

## Unlock all (group `unlocks`, the "(All Unlocked)" variants)
*Seen headless, 2026-10-28* (Credits in Options and 41 elimination teams without any code; the
edit limit and colour option are *from the code*).
The save holds an unlock flag (save data + 0x43FC) and a progress level 0-3 (+0x43FD). The game
sets them when Victory Road titles are won (any one: level 1, three: 2, all six: 3) or when L+R+Y
is pressed together at the main menu (flag 1, level 3). They are read only through two getters,
0x8C015C04 (flag) and 0x8C015C12 (level); nothing else touches the bytes. The patch makes the
getters return the full values (`rts; mov #1,r0` and `rts; mov #3,r0`), so everything is open
from the first boot: the 13 extra elimination teams, Credits in Options, the edit limit of 300
(table 0x8C12E0B0: 150 / 200 / 250 / 300 by level) and the extra edit colour option. The save
itself is not changed: the same memory card works with the normal patches, which go back to what
the save says.

## Downloadable moves and roster (group `dlc`, the "(All Unlocked)" variants)
*Seen headless, 2026-10-28* (cold boot without a memory card: all 100 slots filled, the roster's
wrestlers in their promotions, the moves in red at the end of Move Edit's lists).
The game loaded extra moves from memory cards only: on every cold boot its autoload (0x8C03E3D8)
copies each FIREPROD.Wnn into a 0x78000-byte pool at 0x8C1F4040 and points a table of 100
(0x8C1BBA8C, bytes used at +0x190) at it; nothing is saved. A move slot refers to one as 0x800+nn.
Edit wrestlers come from FIREPROD.E01-E04 (0x7D38 bytes each at 0x8C1D4B60, ending where the pool
starts). The build (tools/dlc.py) packs an image of that memory - E01-E03 empty, the roster as
E04 (wrestler ids 0xC000|n), the 100 moves, and the table at a fixed place near the pool's end - into a new SBL.BIN
entry, 370. The cold-boot jump to the autoload (literal at 0x8C015AB4) now goes to a 60-byte
routine in the never-called match overlay function (0x8C030A80): it reads entry 370 over that
memory (0x8C012E2C reads whole sectors, at most 2047 bytes past the end, still inside the pool),
copies the table into place and continues to the autoload. Memory cards still work, and players' saved wrestlers are safe (*tested headless with memory
cards, 2026-10-28*): the game writes a card file only when the player saves it - a single save of
a file they changed (asking before it overwrites one on the card), or "Overwrite All", which
writes only files the player changed, each to the card it came from. There is no autosave. A
card's own E01-E03 load beside the roster (tested: byte-identical in RAM, the card untouched), a
card's E04 replaces it, and W files for filled slots are skipped. The roster reaches a card only
if the player edits a wrestler into its group (Ext Data 4) and saves that. The one way to lose a
file - saving a group to a card that wasn't inserted at power-on and answering Yes to "Overwrite?"
- is the original game's, for every group.
The source files are the owner's memory card images in rom/dlc/ (never committed); the six moves
named in Japanese get English names from translation/text/dlc_moves.csv in the English builds. The roster's
finisher names are free text in each edit record (+0x24C, 42 bytes, not the move table;
+0x276..+0x27F right after it is appearance data and is left alone), so they get
English from translation/text/dlc_roster.csv the same way (the file's checksum is refreshed).
Edit wrestlers are never offered under Base Model (the game's own filter, for every edit
wrestler); Edit Wrestler > Save > Quick Load > Ext Data 4 loads one into the editor instead, and
Quick Save to another group keeps the copy. Edit wrestlers have one appearance (*from the data*): a built-in
record keeps four 10-byte parts sets, one per costume, at +0x1D2/+0x1DC/+0x1E6/+0x1F0; an edit
record uses that area for its custom colours and has a single parts set at +0x276, so all four
costume choices on the select screen draw the same look - as for any player-made wrestler.

## Save guard (group `saveguard`, the "(All Unlocked)" variants)
*Tested headless with memory cards, 2026-10-28* (English and Japanese builds).
In Memory Card > Save, when the chosen card already holds the file, the original game asks
"Overwrite?" - even when the file in memory did not come from that card (a card put in after
power-on, or a second card): answering Yes there replaced the card's file. The guard wraps the
file search of that screen (its literal at 0x8C03F5E8, which only this screen uses) with a
routine at 0x8C030AC0 (the same never-called overlay function as the boot routine): the
overwrite stays allowed only when the file's status is Edited or Saved with this card as its
unit (per-file status at *(0x8C1BBA88) + 0x198 + 2 * kind). Otherwise the screen shows "Can't
overwrite: load it first." (読み込んでいないファイルは上書きできません in the Japanese build), plays
the error sound and writes nothing. Tested: a file loaded from the card can be overwritten as
before (the "Overwrite?" prompt); the same file marked as not loaded from it is refused and the
card stays byte-identical; a new file saves normally to a card that doesn't have it.
"Overwrite All" needs no guard: it writes only edited files, each to the card it was loaded from.
