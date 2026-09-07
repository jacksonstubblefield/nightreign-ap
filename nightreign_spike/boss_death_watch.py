"""Watch a locked-on boss's HP module through to death, looking for a "felled/reward granted" bit
near HP - base Elden Ring's "Great Enemy Felled" banner is normally tied to a per-NPC reward flag,
not the popup-queue system found in disasm_popup.py (confirmed NOT to fire for boss kills - see
roadmap memory). Chain ported from the CE table's Target class (Target:getHp()/getMaxHp()):
    hp_module = [EnemyIns + 0x1B8]
    hp_base   = [hp_module + 0x00]
    hp        = [hp_base + 0x140]   (int32)
    maxhp     = [hp_base + 0x144]   (int32)

Polls fast, prints every HP change, and once HP crosses to <=0, dumps + diffs a wide region of
hp_base repeatedly for a few more seconds to catch anything that flips right at/after death.

Usage: python -u boss_death_watch.py <EnemyIns_ptr_hex> [--interval 0.1] [--size 800]
"""
import argparse
import struct
import sys
import time

import pymem

from popup_trigger import PROCESS_NAME


def group_runs(offsets):
    runs = []
    start = prev = offsets[0]
    for o in offsets[1:]:
        if o == prev + 1:
            prev = o
            continue
        runs.append((start, prev))
        start = prev = o
    runs.append((start, prev))
    return runs


def print_diff(prev_blob, curr_blob):
    diffs = [o for o in range(len(curr_blob)) if prev_blob[o] != curr_blob[o]]
    if not diffs:
        return
    for start, end in group_runs(diffs):
        length = end - start + 1
        a_bytes = prev_blob[start:end + 1]
        b_bytes = curr_blob[start:end + 1]
        line = f"    +{start:#06x}..+{end:#06x} ({length}B): {a_bytes.hex()} -> {b_bytes.hex()}"
        if length == 4:
            a_i = struct.unpack("<i", a_bytes)[0]
            b_i = struct.unpack("<i", b_bytes)[0]
            line += f"   as int32: {a_i} -> {b_i}"
        elif length == 1:
            line += f"   as byte: {a_bytes[0]} -> {b_bytes[0]}"
        print(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("enemy_ins", type=lambda s: int(s, 16))
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument("--size", type=lambda s: int(s, 16), default=0x800)
    args = parser.parse_args()

    pm = pymem.Pymem(PROCESS_NAME)

    print(f"Watching EnemyIns={args.enemy_ins:#x} - Ctrl+C to stop.")
    last_hp = None
    last_blob = None
    died_at = None
    try:
        while True:
            try:
                hp_module = pm.read_ulonglong(args.enemy_ins + 0x1B8)
                hp_base = pm.read_ulonglong(hp_module + 0x00)
                hp = struct.unpack("<i", pm.read_bytes(hp_base + 0x140, 4))[0]
                maxhp = struct.unpack("<i", pm.read_bytes(hp_base + 0x144, 4))[0]
                blob = pm.read_bytes(hp_base, args.size)
            except Exception as e:
                print(f"  (read failed: {e})")
                time.sleep(args.interval)
                continue

            ts = time.strftime("%H:%M:%S")
            if last_hp is not None and hp != last_hp:
                print(f"[{ts}] HP: {last_hp} -> {hp} / {maxhp}")
                if hp <= 0 and last_hp > 0:
                    died_at = time.time()
                    print(f"[{ts}] *** DEATH DETECTED (HP crossed to <= 0) ***")

            if last_blob is not None:
                print_diff(last_blob, blob)

            last_hp = hp
            last_blob = blob

            if died_at is not None and (time.time() - died_at) > 8:
                print("8 seconds post-death elapsed, stopping.")
                break

            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
