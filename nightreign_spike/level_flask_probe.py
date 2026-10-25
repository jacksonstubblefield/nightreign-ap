"""Metaprogression spike: read and set the local player's level and max flask charges, to answer
two questions before wiring a "minimum level / minimum flasks" floor into the client.

Targets ported from the user's CE table (Nightreign_w_apvalues.CT, "--- Expedition ---" group),
all relative to PlayerGameData = [GameDataMan + 0x8] (memory_reader.read_player_data_base()):
    level      = uint32 at +0x68                     ("Level" entry)
    max flasks = uint8  at +0xFF                     ("Max Flask Quantity [Max = 20]" entry)
    SetLevel   = fn(PlayerGameData, level) at SET_LEVEL_AOB ("Set Max lvl" script, which passes
                 0x10 - but the in-game max is 15, so what the arg means is open question #1)
SetLevel's prologue does `mov [rcx+68h],edx` and then calls further, presumably a stat recalc -
which is why `set-level` goes through the function rather than poking +0x68 directly. Max HP
(PlayerIns hp_base+0x144) is printed before/after as the clearest evidence of a recalc.

Open question #2: does raising max flasks also give usable charges, or only empty slots? `watch`
prints every byte that changes in a PlayerGameData window - drink a flask while it runs and the
current-charge byte (if it lives here) should be the one that ticks down.

Modes:
  read                 One-shot: level, runes, max flasks, max HP, and a hex dump of the window.
  watch                Polls the window and prints every byte change (old -> new).
  set-level N          Calls SetLevel(PlayerGameData, N), then shows what changed.
  set-flask N          Writes N to +0xFF, then shows what changed.
set-level/set-flask take --delay N to give you time to alt-tab back into the game first.

Usage: py -3.12 nightreign_spike/level_flask_probe.py read
       py -3.12 -u nightreign_spike/level_flask_probe.py watch [--interval 0.25]
       py -3.12 nightreign_spike/level_flask_probe.py set-level 7 --delay 5
       py -3.12 nightreign_spike/level_flask_probe.py set-flask 4 --delay 5
"""
import argparse
import os
import sys
import time

import pymem.exception

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "worlds", "nightreign"))
from memory_reader import NightreignMemoryReader, PointerNotFoundError  # noqa: E402
from memory_writer import NightreignCurrencyWriter  # noqa: E402

SET_LEVEL_AOB = "40 53 48 83 EC 40 89 51 68 44 8B C2 48 8D 54 24 20"
LEVEL_OFFSET = 0x68
RUNES_OFFSET = 0x6C
MAX_FLASK_OFFSET = 0xFF

# Byte range of PlayerGameData that read/watch dump and set-* diff. Covers level, runes and max
# flasks plus the area where Elden Ring keeps attributes (+0x3C..), in case Nightreign does too.
WINDOW_START = 0x00
WINDOW_SIZE = 0x200

# SetLevel is only called with values in this range - 16 included because the CE script itself
# passes 0x10.
LEVEL_RANGE = range(1, 17)
FLASK_RANGE = range(0, 21)


def _connect() -> NightreignMemoryReader:
    reader = NightreignMemoryReader()
    if not reader.connect():
        sys.exit("nightreign.exe not running - launch the game (offline) first.")
    return reader


def _player_data(reader: NightreignMemoryReader) -> int:
    base = reader.read_player_data_base()
    if base is None:
        sys.exit("PlayerGameData unreadable - load into a save (ideally mid-expedition) first.")
    return base


def _snapshot(reader: NightreignMemoryReader, player_data: int) -> bytes:
    return reader.pm.read_bytes(player_data + WINDOW_START, WINDOW_SIZE)


def _max_hp(reader: NightreignMemoryReader) -> str:
    try:
        reading = reader.read_player_hp(reader.resolve_current_animation_target())
    except PointerNotFoundError:
        return "?"
    return "?" if reading is None else f"{reading[0]}/{reading[1]}"


def _summary(reader: NightreignMemoryReader, player_data: int) -> str:
    pm = reader.pm
    return (f"level={pm.read_uint(player_data + LEVEL_OFFSET)}  "
            f"runes={pm.read_uint(player_data + RUNES_OFFSET)}  "
            f"max_flasks={pm.read_uchar(player_data + MAX_FLASK_OFFSET)}  "
            f"hp={_max_hp(reader)}")


def _hexdump(data: bytes) -> None:
    for row in range(0, len(data), 16):
        chunk = data[row:row + 16]
        print(f"  +{WINDOW_START + row:04X}  {chunk.hex(' ')}")


def _print_diff(before: bytes, after: bytes) -> int:
    changed = 0
    for i, (old, new) in enumerate(zip(before, after)):
        if old != new:
            print(f"  +{WINDOW_START + i:04X}: {old:3d} (0x{old:02X}) -> {new:3d} (0x{new:02X})")
            changed += 1
    return changed


def cmd_read(reader: NightreignMemoryReader) -> None:
    player_data = _player_data(reader)
    print(f"PlayerGameData @ {player_data:#x}")
    print(_summary(reader, player_data))
    _hexdump(_snapshot(reader, player_data))


def cmd_watch(reader: NightreignMemoryReader, interval: float) -> None:
    print("Watching PlayerGameData - drink a flask, level up, pick up a flask charge... Ctrl+C "
          "to stop.")
    player_data, previous = None, None
    while True:
        current_base = reader.read_player_data_base()
        if current_base is None:
            time.sleep(interval)
            continue
        if current_base != player_data:
            player_data = current_base
            previous = _snapshot(reader, player_data)
            print(f"[{time.strftime('%H:%M:%S')}] PlayerGameData @ {player_data:#x}  "
                  f"{_summary(reader, player_data)}")
            continue
        try:
            current = _snapshot(reader, player_data)
        except pymem.exception.MemoryReadError:
            player_data = None
            continue
        if current != previous:
            print(f"[{time.strftime('%H:%M:%S')}] {_summary(reader, player_data)}")
            _print_diff(previous, current)
            previous = current
        time.sleep(interval)


def _apply_and_diff(reader: NightreignMemoryReader, label: str, apply) -> None:
    player_data = _player_data(reader)
    print(f"before: {_summary(reader, player_data)}")
    before = _snapshot(reader, player_data)
    apply(player_data)
    # Give the game a frame or two to propagate anything the call kicks off (e.g. max HP).
    time.sleep(0.5)
    after = _snapshot(reader, player_data)
    print(f"after:  {_summary(reader, player_data)}")
    print(f"{label} changed {_print_diff(before, after)} byte(s) in the window.")


def cmd_set_level(reader: NightreignMemoryReader, level: int) -> None:
    try:
        func_addr = reader._resolve_function_address(reader.pm, SET_LEVEL_AOB)
    except PointerNotFoundError as exc:
        sys.exit(f"Fatal: {exc}")
    print(f"SetLevel @ {func_addr:#x}")
    # NightreignCurrencyWriter is just a generic fn(PlayerGameData, int) remote call - the same
    # shape SetLevel has - so reuse it rather than building a second trampoline here.
    caller = NightreignCurrencyWriter(reader.pm, {"SetLevel": func_addr})
    _apply_and_diff(reader, f"SetLevel({level})",
                    lambda player_data: caller.grant("SetLevel", player_data, level))


def cmd_set_flask(reader: NightreignMemoryReader, count: int) -> None:
    _apply_and_diff(reader, f"max_flasks={count}",
                    lambda player_data: reader.pm.write_uchar(player_data + MAX_FLASK_OFFSET, count))


def main() -> None:
    parser = argparse.ArgumentParser(description="Read/set the local player's level and max "
                                     "flask charges (metaprogression spike).")
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("read")
    watch = sub.add_parser("watch")
    watch.add_argument("--interval", type=float, default=0.25)
    set_level = sub.add_parser("set-level")
    set_level.add_argument("level", type=int, choices=LEVEL_RANGE, metavar="N (1-16)")
    set_level.add_argument("--delay", type=float, default=0)
    set_flask = sub.add_parser("set-flask")
    set_flask.add_argument("count", type=int, choices=FLASK_RANGE, metavar="N (0-20)")
    set_flask.add_argument("--delay", type=float, default=0)
    args = parser.parse_args()

    reader = _connect()
    try:
        if getattr(args, "delay", 0):
            print(f"Waiting {args.delay:g}s - switch back to the game...")
            time.sleep(args.delay)
        if args.mode == "read":
            cmd_read(reader)
        elif args.mode == "watch":
            cmd_watch(reader, args.interval)
        elif args.mode == "set-level":
            cmd_set_level(reader, args.level)
        else:
            cmd_set_flask(reader, args.count)
    except KeyboardInterrupt:
        pass
    finally:
        reader.disconnect()


if __name__ == "__main__":
    main()
