# Platform notes: Sega Dreamcast

Starting notes for Dreamcast projects. The first project is Fire Pro Wrestling D (T-18805M). Facts
are marked **verified** once they have been checked on a real disc or in game. The rest is general
knowledge still to be confirmed. Add what you learn here and in the kit's copy.

## Disc (GD-ROM)
- **Verified:** Redump images are BIN/CUE with one file per track. A single-density area (track 1:
  a small ISO with a warning text, track 2: the "this is a Dreamcast disc" audio) starts at LBA 0.
  The high-density area starts at **LBA 45000**: track 3 (data), the CD audio tracks, and a last
  data track. The .cue marks the areas with `REM SINGLE-DENSITY AREA` / `REM HIGH-DENSITY AREA`.
  Each track's absolute start is its area's start plus the sizes of the files before it (pregaps
  are inside the files). `disc.py tracks <cue>` prints the layout.
- **Verified:** the last data track ends at LBA 549149, the end of the disc, so a GD-ROM with
  audio is full. Nothing can be appended. A grown file goes into existing zero sectors or the
  build stops.
- **Verified:** the last data track has a 3-second pregap (225 sectors, INDEX 01 00:03:00) inside
  its file. Some of those sectors are MODE1 with zero data. `disc.py` never puts a file there,
  because emulators and .gdi conversions drop the pregap.
- **Verified:** sector headers carry the absolute address. Past 99 minutes the BCD minutes byte
  goes on as 0xA0..0xC2.
- **Verified:** MODE1 sectors as on the Saturn: 2048 data bytes at offset 16, EDC over bytes
  0-2063, P/Q ECC. `disc.py` regenerates both on every write, and `disc.py verify` recomputes them.
- **Verified:** IP.BIN is in sectors 0-15 of track 3: `SEGA SEGAKATANA`, maker, device info,
  area, peripherals, product number, version, date, **boot file name** (`1ST_READ.BIN`),
  company, title. The boot ROM checks it, so never write it. `disc.py header <track>` prints it.
- **Verified:** the ISO9660 file system starts in track 3 (PVD at +16, directories after it),
  with absolute LBAs. On Fire Pro D, track 3 holds only the directories, `0GDTEX.PVR` (the disc
  label) and about 44,000 zero sectors (~90 MB). Every game file is on the last data track
  (track 50), so the project's image (`paths.ROM`) is that track (`disc.main_track()`).
- **Verified:** a build changes two files. The image (the last data track) holds the files.
  The build's own copy of track 3, `<build> (Track 03).bin`, holds the directory records and any
  relocated file. A file that outgrows its slot stays put when the files in its way are smaller:
  those move instead (`_make_room`; Fire Pro D: 1ST_READ.BIN to track 3, the 83 MB SBL.BIN grows in
  place). Relocation fills track 3's padding first, which keeps the room after the last
  file (usually 1ST_READ.BIN) free. `check.py --control` compares both with the original, and
  `make_patches.py` makes a second patch `<variant> (Track 03).xdelta` when track 3 changed. The
  release .cue names both.
- **Verified:** 1ST_READ.BIN on a pressed GD-ROM is plain SH-4 code loaded at 0x8C010000. Only
  CD-R (MIL-CD) boot files are scrambled. Fire Pro D starts by writing the cache control
  register (0xFF00001C), then jumps to 0x8C157EC0.
- Games open files by name through the GD file system (`gdFsOpen`), which reads the directory.
  Some keep LBAs in their own tables, so check before relocating a file. Big streamed files
  (`.SFD` movies, `.ADX`/`.AFS` audio) are read by LBA ranges and should never move.

## Code
- CPU: Hitachi SH-4 (SH7091) at 200 MHz, **little-endian**. Instructions are 16 bits. 32-bit
  constants come from literal pools after the code (`mov.l @(disp,PC),Rn`), so a reference
  search finds the pool word (`tools/sh4.py refs`). Delay slots work as on the SH-2. The FPU is
  single-precision by default: FPSCR.PR switches the same words to double and FPSCR.SZ makes
  fmov move pairs.
- Memory map: main RAM is 16 MB at 0x0C000000, used through the cached mirror 0x8C000000
  (P1) or uncached 0xAC000000 (P2). The boot ROM loads 1ST_READ.BIN at 0x8C010000. Video RAM is
  8 MB at 0xA4000000 (64-bit path) / 0xA5000000 (32-bit). Sound RAM (2 MB, for the ARM7) is at
  0xA0800000.
- Libraries: games are built with Katana (Sega's SDK: Shinobi/Ninja/Kamui, GD file system) or
  Windows CE. Library names and versions show up as strings ("Lib Handle Start" in Fire Pro D).
- Debugging: Flycast has no GDB stub in its libretro build. `tools/emu.py` reads and writes
  main RAM live, which covers most needs.

## Text
- Fonts are on the disc (Fire Pro D: `DPFONT/S18RM04P.DAT`, `S20`, `S24`, `S26` - by name 18-26
  px fonts of the DreamPassport browser engine, to be confirmed). The BIOS also has a system font
  of 12x12 / 24x24 kanji and half-width ASCII, which Katana games can call through syFontRom.
- Text is usually drawn as textured polygons (PowerVR2): glyphs are copied into a texture and
  drawn as quads, so the room is in pixels or glyph slots, not tiles.

## Fire Pro Wrestling D (2026-10)
- **Seen headless:** boots on Flycast's HLE BIOS. START at the title opens the main menu
  (ワンナイトマッチ, ヴィクトリーロード改, エディットモード, ネットワークモード, ...), drawn
  in large Japanese menu captions with a description line underneath.
- The disc carries Sega's DreamPassport 3 browser (`DPETC/`, `DPWWW/`, `SG_DPLDR.BIN`,
  `DP3.INI`, `MESSAGE.INI`) for the network mode, and an 83 MB `SBL.BIN` archive (the game data,
  format still to find).

## Emulator (platforms/dreamcast/emu.py)
- Flycast libretro core, driven from Python with an off-screen OpenGL context (EGL on Mesa's
  surfaceless platform). About 330 frames per second here. The BIOS (`dc_boot.bin`,
  `dc_flash.bin`) is optional: without it Flycast boots with its HLE BIOS.
- **Verified:** the core reads no input until a pad is plugged into port A
  (`retro_set_controller_port_device`). The runner does that. It also must answer the log and
  performance interfaces, or the core crashes while loading.
- The core exposes main RAM (16 MB) but not video RAM. Savestates are about 36 MB. Make new ones
  after every build, as on the Saturn.
- Pad mapping: libretro B = Dreamcast A (by position). L/R are the analog triggers, pulled fully.

## Screenshots
- Native resolution is 640x480 (VGA and most NTSC games), some 320x240. The runner renders at
  640x480 internally. Record the size each project uses in `<kit>/release/shots.py` SIZES and
  here.
