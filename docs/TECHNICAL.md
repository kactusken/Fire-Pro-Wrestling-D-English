# Technical notes - Fire Pro Wrestling D

**Conventions:** numbers in hex with `0x`; addresses are RAM addresses unless marked as file
offsets; `u16`/`u32` little-endian unless marked BE. Findings are marked *verified in game* or
*from the code*.

## Contents
- [Image](#image) · [Disc layout](#disc-layout) · [Executable and memory](#executable-and-memory)
- [Archives and compression](#archives-and-compression) · [Text](#text) · [Images](#images)
- [Open questions](#open-questions) · [Prior art](#prior-art)

## Image
`Fire Pro Wrestling D (Japan) (Track 50).bin`, 112009296 bytes, SHA-1 `c6037b763e59b801101b9538cbf3ec406e14490b`.

A GD-ROM, Redump-style BIN/CUE with 50 tracks: product number T-18805M, version V1.002, dated
2001-01-22, area J (IP.BIN). The high-density area holds data track 3 (LBA 45000-89325), 46
audio tracks, and data track 50 (LBA 501527-549149, ending at the end of the disc). The ISO9660
file system starts in track 3: the PVD and the directories are there, along with `/0GDTEX.PVR`
and about 44,000 zero sectors. Every other file is on track 50, so track 50 is the project's
image. A build also writes its own copy of track 3 (the directory records, plus any file moved
into the padding), and a release has a second patch when that copy changed. SBL.BIN grows by
about 260 sectors (six picture entries recompress a few KB larger; 198, 206 and 244 move to its
end, and 245-247 shift down into the space 244 left, `tools/sbl.py` `put`) - *verified in game: the Victory Road Congratulations screen from the moved entries, (All Unlocked) build, 2026-10-28*, and by 302 more in
the (All Unlocked) builds (the downloadable moves, entry 370): 561 in all. 1ST_READ.BIN, right
after it, has 149 free sectors behind it - so the build moves 1ST_READ.BIN (808 sectors) to
track 3 and SBL.BIN grows in place (`disc.py` `_make_room`); the room behind SBL.BIN is then 957
sectors. When SBL.BIN outgrows that, the build relocates all of it to track 3 and that track's
patch carries the whole archive (70 MB) - `make_patches.py` sizes show it. The game boots from there (*seen
headless, Flycast HLE BIOS, 2026-10-28*), and the patches stay ~1 MB each instead of 70 MB. Details:
[PLATFORM.md](PLATFORM.md). *Verified: control build identical, 2026-10-27.*

The dump matches Redump's "Fire Pro Wrestling D (Japan)": all 50 tracks and the .cue, by size and
SHA-1 (track 50: `c6037b763e59b801101b9538cbf3ec406e14490b`). *Verified 2026-10-28 against the
Redump entry's hashes, which the owner supplied.*

## Disc layout
| LBA | Size | File | Contents |
|---|---|---|---|
| 89111 | 131104 | `/0GDTEX.PVR` |  |
| 501752 | 21821 | `/DPETC/CHAT.DPS` |  |
| 501763 | 135250 | `/DPETC/DP3.DPS` |  |
| 501830 | 1721120 | `/DPETC/DP3SOUND.MLT` |  |
| 502671 | 36768 | `/DPETC/MANATEE.DRV` |  |
| 502689 | 71329 | `/DPETC/MESSAGE.INI` |  |
| 502724 | 3766 | `/DPETC/NTP.DPS` |  |
| 502726 | 12508 | `/DPETC/PM.DPS` |  |
| 502733 | 248221 | `/DPETC/SOFTKEY.DPS` |  |
| 502855 | 7596 | `/DPETC/VMS.DPS` |  |
| 502859 | 702720 | `/DPFONT/S18RM04P.DAT` |  |
| 503203 | 780800 | `/DPFONT/S20RM04P.DAT` |  |
| 503585 | 1124352 | `/DPFONT/S24RM04P.DAT` |  |
| 504134 | 1421056 | `/DPFONT/S26RM04P.DAT` |  |
| 504828 | 47 | `/DPMODEL/ATTENTION.TXT` |  |
| 504829 | 1040 | `/DPTEX/BANK00.PVP` |  |
| 504830 | 1040 | `/DPTEX/BANK01.PVP` |  |
| 504831 | 1040 | `/DPTEX/BANK02.PVP` |  |
| 504832 | 1040 | `/DPTEX/BANK03.PVP` |  |
| 504833 | 67616 | `/DPTEX/C_M_S.PVR` |  |
| 504867 | 67616 | `/DPTEX/JYOUCYU0.PVR` |  |
| 504901 | 67616 | `/DPTEX/JYOUCYU1.PVR` |  |
| 504935 | 67616 | `/DPTEX/JYOUCYU2.PVR` |  |
| 504969 | 67616 | `/DPTEX/OPTION01.PVR` |  |
| 505003 | 67616 | `/DPTEX/OPTION02.PVR` |  |
| 505037 | 67616 | `/DPTEX/OPTION03.PVR` |  |
| 505071 | 67616 | `/DPTEX/SKB_BASE.PVR` |  |
| 505105 | 67616 | `/DPTEX/SKB_EISU.PVR` |  |
| 505139 | 67616 | `/DPTEX/SKB_KANA.PVR` |  |
| 505173 | 67616 | `/DPTEX/SKB_V102.PVR` |  |
| 505207 | 67616 | `/DPTEX/SU_ICO2.PVR` |  |
| 505241 | 67616 | `/DPTEX/SU_ICON.PVR` |  |
| 505275 | 67616 | `/DPTEX/TAG_SU.PVR` |  |
| 505309 | 67616 | `/DPTEX/VMSPART2.PVR` |  |
| 505343 | 67616 | `/DPTEX/VMSPARTS.PVR` |  |
| 505377 | 67616 | `/DPTEX/WALLPAPER.PVR` |  |
| 505411 | 65568 | `/DPTEX/WALLPAPER00.PVR` |  |
| 505444 | 65568 | `/DPTEX/WALLPAPER01.PVR` |  |
| 505477 | 65568 | `/DPTEX/WALLPAPER02.PVR` |  |
| 505510 | 65568 | `/DPTEX/WALLPAPER03.PVR` |  |
| 505543 | 467 | `/DPWWW/INDEX.HTML` |  |
| 505544 | 506 | `/DPWWW/HELP/INDEX.HTML` |  |
| 505545 | 493 | `/DPWWW/IMAGES/FIREBALL_02.GIF` |  |
| 505546 | 1409 | `/DPWWW/IMAGES/FIRE_01.GIF` |  |
| 505547 | 37425 | `/DPWWW/IMAGES/LOGO.GIF` |  |
| 505566 | 3480282 | `/2_DP.BIN` |  |
| 507266 | 5453 | `/DP3.INI` |  |
| 507269 | 14856 | `/MAIGO.BIN` |  |
| 507277 | 14856 | `/SG_DPLDR.BIN` |  |
| 507285 | 83777536 | `/SBL.BIN` |  |
| 548192 | 1653248 | `/1ST_READ.BIN` |  |

## Executable and memory
`/1ST_READ.BIN` (1653248 bytes) is plain SH-4 code loaded at 0x8C010000 (not scrambled). It
starts by writing the cache control register (0xFF00001C), then jumps to 0x8C157EC0. It holds
library strings ("Lib Handle Start"). *From the code.*

## Archives and compression
**SBL.BIN** (83 MB, `tools/sbl.py`): a table of (u32 offset, u32 size) pairs at 0, ended by a pair
with size 0 (its offset = the end); data from 0x1000, entries at 0x800 boundaries; 370 entries. The
game reads the table at run time (no copy in 1ST_READ.BIN), so entries may move: the build places an
entry that outgrew its slot after the last one. *Verified: a build with three entries moved boots and
shows them, 2026-10-27.* Kinds of entry: sound banks (SMLT/SOSB/SMPB/SMSB/SDRV), Ninja models
(NJTL/NJCM), PVR textures raw or LZSS-compressed, containers, and the game data (entries 1, 2).

**Containers** (e.g. 238): a table of (offset/4, size/4) pairs up to the first offset, each item a
separate LZSS stream (`tools/gfx.py container()`).

**LZSS** (`tools/lzss.py`, *verified against RAM*): no header; flag byte per 8 items, bit 0 first,
1 = a 2-byte reference: window position `b0 | (b1 & 0xC0) << 2` (1024-byte window, zero-filled,
written from 0x3BE), length `(b1 & 0x3F) + 3`; 0 = a literal byte.

**Entry 1** (215,762 bytes -> 241,988): header u32 5, then 4 words = section ends / 4: 0x14..0x1B134
the roster (entry 2's data, 220 x 504 bytes) and more, ..., 0x36B88..end the move names: 1536 u16
offsets (move id -> name, from the section start), then 1000 NUL-terminated names. Loaded at
0x8C8DBA40. **Entry 2** (90,811 -> 110,880): the roster alone, decompressed to 0x8C8DBA54.

**Roster record** (504 bytes): +0 01, +1 flags (bit 7: name2 first; bits 0-1 separator: 0 space,
1 ・, 2 =, 3 none - *verified in game*), +2 name1 (14 bytes, the short name in lists), +0x10 name2
(20), +0x24 nickname (26), then stats.

**PVR textures** (`tools/pvr.py`): GBIX + PVRT chunks; mostly ARGB4444 VQ; the menu-text sheets are
ARGB4444 square twiddled (imported by `tools/gfx.py`).

## Text
*Verified in game, 2026-10-27.* The program's strings are Shift-JIS (half-width katakana for
unvoiced kana to save bytes) in 1ST_READ.BIN 0xB2800-0xBBC00, NUL-terminated, each start reached by
32-bit pointers (literal pools and pointer tables; none from other files). The renderer draws them
live with a large proportional font that has every printable ASCII character except `#`, which
starts the `#xN` spacing code; half-width characters go through a conversion table (0x11F987) to
the full-width font. Widths at the menu size: ~24 px a kanji, 12 a half-width kana, ~14 a lowercase
letter, ~18 a capital, 16 a space (`tools/fpdtext.py FONT`, measured). Menus resize to their
English (the match-type box widens).

Insertion (`tools/fpdtext.py`, build steps): the pool of every pointer-referenced string in the
region (27,415 bytes) is repacked in order with 4-byte alignment and every pointer updated; English
takes 23,151 bytes of it (2026-10-27). Fixed fields (save labels, referees) are written in place.
The roster goes into SBL entries 1 and 2, the move names into entry 1 (both recompressed).
Text in pictures: the main menu labels, the wrestler profile tags, the elimination order boards and
the result banners are PVR textures (graphics.csv, tools/gfx.py).

## Wrestler records
*Checked against the editor screens, 2026-10-28.* Each built-in wrestler is 504 bytes (SBL.BIN
entry 2; the first 504 bytes of a 640-byte edit record are the same). `tools/fprecord.py` decodes
them for the guide:
- +0x00 class, +0x02/+0x10/+0x24 names and nickname, +0x3E height, +0x3F weight, +0x40 origin,
  +0x41..+0x43 birthday (year - 1900, 0xFF unknown), +0x44 promotion, +0x45 style, +0x46 reversal,
  +0x47..+0x4C recovery/breathing/spirit with their bleeding values, +0x4D..+0x50 durability,
  +0x51/+0x52 speed and climb speed (stored 3-7), +0x53 climb/run up, +0x54 critical, +0x55 theme
  (shown + 1), +0x56/+0x58 voices (a sample id; the tone is its range, table 0x8C12E05C),
  +0x5A stance, +0x5B size, +0x5C skill, +0x5D..+0x72 the 22 Param Edit ratings (stored 3-12, shown 1-10).
- +0x74: 78 move slots (u16: bits 0-11 the move, 0x800 a downloadable move; 0x1000 signature move
  (at most four), 0x2000 finisher, 0x4000/0x8000 voice 1/2 with the move). Record order is not Move
  Edit's: table 0x8C12EE6C maps screen rows to slots, 0x8C12F640 holds their button glyphs.
- +0x110..+0x1CF: CPU Logic. 20 situations (table 0x8C1302B0) with conditions; each condition
  stores cumulative percentages for its actions (the last gets the rest of 100). Action codes
  below 0x100 are move slots; 0x200+ are plain actions, whip and the style's grapple/counter reply
  (table 0x8C1303A0). Traits and Other are one byte each (+0x1BD..+0x1C0, +0x1CD..+0x1CF).
- +0x1D0..+0x1F7: the four costumes (not decoded).

### Move Edit lists
*From the data, 2026-10-28* (every list matches the slots the 220 wrestlers use its moves in, and
its moves' names). The move ids are grouped by kind, and Move Edit offers each slot one of 43 lists:
- 0x8C12EB8C: 43 x (u32 pointer to u16 move ids, u16 count, u16 another list also offered, or
  0xFFFF). The chain makes a heavier slot take the lighter moves too: strong grapples (list 12)
  -> medium (11) -> weak (10); the same for standing strikes (2 -> 1 -> 0) and from behind
  (15 -> 14 -> 13). Some lists start with move 0 (none).
- 0x8C12ECE4: 78 bytes by record slot, the list for that slot (Stand X 0, Grapple B 12, the taunts
  24, ...). Back Rev X and A have two lists with the same moves.
`tools/guidedata.py` reads both for the guide's Moves tab (`LIST_TITLES` names them).

### Move data
- SBL.BIN entry 150 (LZSS, 1,158,628 bytes): 3200 (u32 offset, u32 size) pairs, then 'GS' blocks,
  one per move (the motion and the move's settings). u16 table 0x8C1346C4 by move id gives the move's
  first block. *Verified in game, 2026-10-28:* the byte at GS+0x1A is the move's main attack type
  (high nibble) and sub attack type (low nibble), indexes into Punch, Kick, Throw, Lock, Choke,
  Power, Agility, Strength, Atk Tech, Rough, MMA Atk - Move Edit's box shows them (American Jab
  0x09 = Punch / Rough, Straight 0x00 = Punch / Punch). The number beside each in that box is the
  wrestler's own rating in the type, and Aff a grade of how the move suits him; the move holds
  no level.
- *From the data, 2026-10-28* - the same values as Fire Pro World's published move table (the
  FPW FAQ wiki's 技データ表), matched by Japanese name: of 1063 moves in both games, 792 have all
  seven damage values the same, every one has the same defence types, 1057 the same attack types
  (the rest are rows the wiki leaves blank or moves FPW rebalanced). From GS:
  +0x12 stamina, +0x13 spirit, +0x14 neck, +0x15 arm, +0x16 back, +0x17 leg, +0x18 breath damage;
  +0x19 bleed chance; +0x1A attack types; +0x1B defence types (Strike Def ... MMA Def, high nibble
  main); +0x23 flags: 0x80 illegal, 0x40 submission hold, 0x01 can cause a critical (the Finisher
  type), 0x02 striking, 0x04 suplex, 0x08 submission, 0x10 power, 0x20 technical critical.
  +0x1C (a class shared by similar moves) and +0x1D..+0x22 (probably the attacker's own damage,
  FPW's self-damage) are not confirmed. How a match turns these base values into damage (the
  ratings against the defence ratings) is in code not yet traced: `0x8C048D20` finds a wrestler's
  move block (via the id table) and returns GS+0x10; the entry is loaded whole at 0x8C7AC2E0
  (pointer at 0x8C26D0A4).
- A downloadable move (FIREPROD.Wnn, `tools/dlc.py`) is u16 its Move Edit list, u16 its slot
  number, the name (+8, 44 bytes), then one GS block of the same layout at +0x34. *From the data:*
  the list matches every slot the downloadable wrestlers equip one in.

## Network mode (DreamPassport 3)
*Seen headless in Flycast, 2026-10-28 (offline: the browser, its menus, Options, Mail, Chat, the soft
keyboard and the connect dialogs; nothing past the dial-up).* Network Mode > Home Page starts Sega's
DreamPassport 3 browser (`/SG_DPLDR.BIN` loads `/2_DP.BIN`). Its text lives in five places:

- `/DPETC/MESSAGE.INI`: the dialog and help messages, lines `N="text"` in Shift-JIS with HTML
  (`<br>`, `<font color="#CC0000">`), 785 live ids. The browser wraps lines to its boxes by itself
  (the Japanese has its own `<br>`s too); the file can grow (`tools/dpnet.py`, dpmsg.csv).
- `/DPETC/NTP.DPS` and `/DPWWW/INDEX.HTML`, `/DPWWW/HELP/INDEX.HTML`: a few pieces (dpmisc.csv).
- `/2_DP.BIN` 0x150344-0x1558CC: the program's own strings - chat page titles in the status bar,
  download progress, the history page, mail date pieces, the SSL and file-download boxes. NUL-
  terminated in 4-byte slots, written in place (dpbin.csv). The kana key map (0x154DFC-0x154F58),
  digit tables, sample registration data (0x1525B0) and the input method's dictionary (from
  0x16D000) stay.
- `/DPTEX/*.PVR`: every button, title, setting name and keyboard key is a picture: 512x512 **VQ**
  textures (layout 3, ARGB4444/1555: a 256-entry codebook of 2x2 blocks + an index byte per block,
  67,616 bytes), cut by the DPS layouts (`frame='tex:WxH+X+Y'` with a texture number) and by the
  program. `tools/dptex.py` draws the English into each label's box (the Japanese lettering's own
  area, translation/text/dptex.csv), VQ-encodes it (k-means from the original codebook, numpy, at
  edit time) and freezes the result beside the picture; the build copies it in (same size, in place).
- The upload form for edited wrestlers is in 1ST_READ.BIN (ui.csv, `<HTML>` string at 0xB5A78);
  its submit button has no NAME, so its caption isn't sent to the server.

The online pages (registration, mail and chat servers) came from Sega's servers and are gone.

## Images

## Open questions
- What format is the 83 MB `/SBL.BIN` (probably the game data archive)?

## Prior art
Searched 2026-10-27:
- An English translation by Irvgotti452, released in 2012 (owner, 2026-10-28), circulates as an
  "English patched" image on ROM sites (CDRomance, RetroGameTalk repo, updated 2025-03-08),
  pointing to a dreamcast-talk.com thread (forum f=22, t=5814). This project does not build on
  it: a fresh translation of all the text, move and wrestler names included, as a standalone
  patch, with the downloadable content built in.
- No technical documentation of this game's formats was found (Data Crystal, TCRF).
- CodeBreaker codes exist (Almar's Guides), for example an unlock for the New Japan wrestlers.
  These are RAM addresses to compare with the code later.

