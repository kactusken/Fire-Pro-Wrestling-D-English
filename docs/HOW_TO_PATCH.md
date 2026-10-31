# How to Patch Fire Pro Wrestling D

You patch two of the disc's 50 files, then open the disc's original `.cue`. Nothing needs renaming.

## What you need

- **Your own copy of the Japanese disc:** a folder with 50 `.bin` files and one `.cue` file. Other
  formats, such as `.gdi` or `.chd`, won't work with these steps.
- **The patch:** download the zip from the
  [releases page](https://github.com/kactusken/Fire-Pro-Wrestling-D-English/releases) and unzip it.
- **Delta Patcher:** download it from
  [its releases page](https://github.com/marco-calautti/DeltaPatcher/releases). It runs on Windows,
  macOS and Linux.

## Steps

These steps use the Real Names version. For another version, pick the two patch files with that
version's name instead. Delta Patcher changes the file you give it, so always work on a copy.

1. Copy your whole disc folder and work in the copy.
2. Open Delta Patcher and make the first patch:
   - **Original file:** `Fire Pro Wrestling D (Japan) (Track 50).bin`
   - **XDelta patch:** `Fire Pro Wrestling D (English) (Real Names).xdelta`
   - Click **Apply patch** and wait for "Patch successfully applied!"
3. Make the second patch the same way:
   - **Original file:** `Fire Pro Wrestling D (Japan) (Track 03).bin`
   - **XDelta patch:** `Fire Pro Wrestling D (English) (Real Names) (Track 03).xdelta`
   - Click **Apply patch** and wait for the same message.
4. Open `Fire Pro Wrestling D (Japan).cue` from the copied folder in your emulator. It has been
   tested in [Flycast](https://github.com/flyinghead/flycast).

The game should now be in English, even though the files still say "Japan". Ignore the `.cue`
files in the patch zip: you only need them to keep several versions in one folder.

## If it goes wrong

Most problems come from a mixed-up file or a file that was already patched. The usual fix is to
make a fresh copy of your original folder and start again.

| What you see | Likely cause | Fix |
| --- | --- | --- |
| "The file you are trying to patch is not the right one" | The patches are swapped, the file is already patched, or your disc is a different dump | Check which patch goes with which track, then start again from a fresh copy |
| The game is still in Japanese | You opened the `.cue` in the original folder | Open the `.cue` in the copied folder |
| The game crashes or won't load | Only one of the two patches was applied, or they came from different versions | Start again from a fresh copy and use two patches with the same version name |
| The patched files end in "(patched)" | You used Rom Patcher JS, which adds that to the name | Use Delta Patcher, or rename the files back to their original names |
