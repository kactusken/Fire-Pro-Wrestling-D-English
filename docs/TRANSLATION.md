# Translation

## Where the text is

| File | Holds | Checked by |
|---|---|---|
| `translation/text/ui.csv` | the program's strings: menus, help lines, messages, Edit labels, CPU logic, costumes | `tools/lint.py` (charset, codes, width estimate, rooms.csv) |
| `translation/text/fixed.csv` | in-place strings: save-file labels, referees, promotion names, built-in names | `tools/lint.py` (byte limits) |
| `translation/text/wrestlers.csv` | the 220-wrestler roster: real and parody names, nicknames | `tools/lint.py` (byte limits) |
| `translation/text/moves.csv` | the 1000 move names | `tools/lint.py` |
| `translation/text/name_tokens.csv` | `<Name>` tokens resolved per build (real/parody) | `tools/lint.py` (unknown tokens) |
| `translation/text/rooms.csv` | measured room of text areas (px) | `tools/lint.py` |
| `translation/graphics.csv` | images with text | `tools/check.py` |

## File formats

Message blocks: `@ id`, source lines (`JP `), translation lines (`EN `); no `EN` lines = original
kept. A file's header says what it holds and its limits (`# limit lines=3 chars=28` is checked by
lint). Tables: original columns beside English ones (`japanese`/`english`, or `X`/`en_X`). See
`tools/blocks.py` and `tools/textdb.py`.

Control codes: `%d %s %02d ...` (printf: keep, same order), `#xN` (extra spacing around a label;
may be dropped in pairs), a line break where the Japanese has one. `<Name>` = a name token
(tools/fpdtext.py name_tokens): a wrestler's parody name or a name_tokens.csv entry, replaced by
the real name (default build) or the parody name (`build.py --names parody`).

## Style guide

- Names: given name first, Hepburn without macrons; parody names romanized from the game's kana,
  katakana English as the English word (provisional, lead 2026-10-27).
- Menus and labels Title Case; help lines and messages sentence case with a period.
- Printable ASCII only (no #), plus the font's symbols ○ × △ ▲ □ ■ ● ★ ☆ ・ → and the full-width
  space; small-font screens (Move Edit, CPU logic) have no ASCII % - keep ％ there.
- Width: the menu font draws ~24 px a kanji but ~14 px a lowercase letter, 16 a space. Measured
  limits: main-menu help line 555 px, Edit menu ~190 px, Edit Wrestler menu ~170 px, Options menu
  ~165 px, wrestler list short name ~112 px, config values (referee) ~110 px, name-entry mode
  column ~110 px. Other menus resize to their text.
- Moves: standard English names (German Suplex, Lariat, DDT); 雪崩式 = Super, 高角度 = Hi-Angle,
  串刺し = Corner, リバース = Rev.; abbreviations PB/PD only when a name is too long.
- Women's costume parts: "W." prefix.

## Glossary

`translation/glossary.csv` (`japanese, english, notes`): lint warns when a source line contains a
term and the English doesn't use its translation (several accepted forms: `A | B`). Prefer
established community names (existing English guides) over new coinages.

## Decisions

| Decision | Who / why |
|---|---|
| No periods in abbreviations or labels (Def, Rev, Jr, KO, 5 Min); sentences keep theirs; women's prefix "W " | owner 2026-10-28 |
| Real names from the owner's list (private/wrestler_names.md) for 217 roster rows; The Undertaker | owner 2026-10-28 |
| Wrestler list short names that clip stay as they are | owner 2026-10-28 |
| Real-name build uses real promotions (NEW JAPAN, ALL JAPAN, NOAH, FMW, MICHINOKU PRO, TORYUMON, BIG JAPAN, OSAKA PRO, WWF, WCW, AAA, RINGS, PANCRASE, BATTLARTS; nWo, NWA, UWF in team names) - name_tokens.csv | owner 2026-10-28; short forms by lead |
| Picture drafts approved (all 6, incl. Edit Army labels) | owner 2026-10-28 |
| Referee names from the EDIT WRESTLERS list confirmed; roster rows 16, 17, 65 keep the agent's names (Kendo Kashin, Tatsuhito Takaiwa, Dory Funk Jr.) | owner 2026-10-28 |
| Victory Road Kai; Crazy Fuckin' uncensored; 分 stays "min"; name tokens approved | owner 2026-10-28 |
| Referees from the owner's list (Tottori/Hattori, Saga/Wada, Wakabe/Tanabe, Imada/Shimada, Kessler/Hebner, Kugayama/Murayama, Mizunaka/Soranaka, Hiroshi/Higuchi), surnames | owner 2026-10-28 |
| Nicknames: en_nick = the real wrestler's own nickname (real build), parody_nick = the game's (parody build) | owner 2026-10-28; 48 real nicknames by agent (private/work/tr/real_nicks.md) |
| 喉輪落とし = Chokeslam | owner 2026-10-28 |
| Referees: surname only (the config value fits ~110 px); real build Hattori / Hebner / Higuchi for three of them (tokens) | lead 2026-10-27, provisional |
| Promotion names stay the game's own (VIEW JAPAN, OLIVE JAPAN...) in both builds; uppercase like the originals | lead 2026-10-27, provisional - question for the owner |
| Name tokens in move/costume/team names: Dolphin -> Delfin, Kaiser -> Liger, Panther -> Tiger, Hayate -> Sasuke ... in the real build | lead 2026-10-27, provisional |
| Birth dates: 年/月 become "/", 日 a space (1953/12/13) | lead 2026-10-27 |
| A fresh translation: the English patch that circulates is not used | user, 2026-10-27 |
| Scope: everything the player needs to understand how to play and what is going on - menus, help and description lines, match text, Edit mode, Victory Road and the other modes, move and wrestler names | user, 2026-10-27 |
| The game font's space stays 16 px wide (every space form the font has is that wide); English reads fine with it | owner, 2026-10-28 |
| The network mode (DreamPassport 3 browser: messages, pictures, keyboard labels, the upload form) is in scope too | owner, 2026-10-28 |
| Network terms: SEGA Provider / User Provider, Bookmarks, Anywhere Chat (どこでもチャット), room (会議室), Communication ID (Comm ID on small labels), outside line prefix (外線発信番号), discount call prefix (市内外割引番号), Advanced Settings (むずかしい設定) | translators + lead 2026-10-28; owner accepted as is 2026-10-28 |
| Browser pictures: lettering redrawn in Noto Sans SemiCondensed Bold in the original colours; the soft keyboards keep the kana keys and emoticon keys, their mode tabs and function keys are English (Full, Half, Hira, Kata, abc, ABC, 1-Touch, Symbols/Faces, Done, Space, Enter, Delete, Backspace) | lead 2026-10-28, provisional |
| Two English releases: real wrestler names and the game's parody names (`build.py --names real\|parody`), as in Fire Pro Wrestling S | user, 2026-10-27 |

## What stays untranslated

- In the network mode: the pages Sega's servers served (gone), the input method's kana-kanji
  dictionary and kana key map, the kana and emoticon keys of the soft keyboard, and the sample
  registration data in 2_DP.BIN (owner put the mode in scope 2026-10-28; these are input tables
  or not reachable).
- Staff credits (user, 2026-10-27).
- Decorative graphics that don't affect play: shirts, signs, banners, ring art, logos (user,
  2026-10-27). Text in graphics that the player needs (menu captions drawn as pictures, for
  example) is in scope.
- The name-entry kana/kanji keyboards (1ST_READ.BIN 0xB762C-0xB97EC) and the kana-to-kanji
  dictionary: they are input tables; the keyboard's ABC page covers English names (lead,
  2026-10-27).
- The intro movie captions "1989 誕生 / 2001 新生" (SBL 234) - decorative (lead, provisional).
- Debug/test screens left in the program (model test, palette editor) - not reachable in normal play.
