#!/usr/bin/env python3
"""The game's text areas on screen right now and the room each one has - what the kit's headless
runner (testing/drive.py) checks on every screen it visits. Fill it in per game once the renderer
is known (FRAMEWORK.md section 7, "Room from the game itself").

  python3 <kit>/testing/drive.py run [--image IMG] STEP... check NAME     one screen
  python3 <kit>/testing/drive.py sweep [--image IMG]                      every private/work/sweep/*.steps

REGIONS names the memory areas() reads; drive.py fetches them at each `check` step:
  Saturn  lwram hwram vdp1 vdp2 (big-endian, as the Saturn sees it)
  Dreamcast  ram (16 MB from 0x8C000000, little-endian; Flycast gives no video RAM)
  SNES    wram vram cgram oam

areas(mem) gets {region: bytes} and returns one dict per text area in use:
  area   a stable name: the same area on the same screen gets the same name in every run
         (a slot number, a window, a tilemap rectangle)
  used   glyphs (or tiles) the text in it takes now
  room   what the area holds, None if unknown (the next area's start, the window's width...)
  where  optional: screen position or address, for the report
  id     optional: the translation block id it shows (file|key, as in rooms.csv), when the game
         keeps a pointer to the string
  over   optional: True/False to override `used > room` (a pixel measure, a hang flag)
How the game shows its text decides how room is found: a list of text objects with their own
video-memory areas (Fire Pro Wrestling S: slots in work RAM, room = the gap to the next slot's
address), a fixed window (room = its width in tiles), a tilemap (room = blank cells up to the
next non-blank one). Run it on the ORIGINAL first: the Japanese shows each area's real room.
"""
REGIONS = []


def areas(mem):
    return []
