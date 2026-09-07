"""Watch several entities' HP simultaneously through a real multi-enemy POI clear, instead of
assuming (wrongly - see nightreign-roadmap memory's 2026-09-05 correction) that any single locked
enemy's death is "the" completion signal. Built to let the user directly observe, live, whether a
POI's reward actually requires every present enemy dead, or something else entirely - rather than
inferring it from unrelated third-party docs.

Usage:
    python -u poi_multi_watch.py <EnemyIns_ptr_hex> [<EnemyIns_ptr_hex> ...] [--interval 0.1]

Get each EnemyIns pointer by locking onto each enemy in the group one at a time with the CE table's
CanBeLockedOn hook active (same "pEnemyIns" source boss_death_watch.py uses) and passing all of them
here together. Run this yourself in its own terminal (run_in_background) while playing normally -
narrate what you see in chat (e.g. "reward picker appeared now") so the printed timestamps can be
correlated against what actually happened on screen afterward.
"""
import argparse
import sys
import time

import pymem

from popup_trigger import PROCESS_NAME


def read_hp(pm, enemy_ins):
    hp_module = pm.read_ulonglong(enemy_ins + 0x1B8)
    hp_base = pm.read_ulonglong(hp_module + 0x00)
    hp = pm.read_int(hp_base + 0x140)
    maxhp = pm.read_int(hp_base + 0x144)
    return hp, maxhp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("enemy_ins_list", nargs="+", type=lambda s: int(s, 16))
    parser.add_argument("--interval", type=float, default=0.1)
    args = parser.parse_args()

    pm = pymem.Pymem(PROCESS_NAME)

    print(f"Watching {len(args.enemy_ins_list)} entities - Ctrl+C to stop.")
    for i, e in enumerate(args.enemy_ins_list):
        print(f"  [{i}] EnemyIns={e:#x}")

    last_hp = {}
    dead = {}
    try:
        while True:
            ts = time.strftime("%H:%M:%S")
            for i, enemy_ins in enumerate(args.enemy_ins_list):
                try:
                    hp, maxhp = read_hp(pm, enemy_ins)
                except Exception as e:
                    if i not in dead or dead[i] != "unreadable":
                        print(f"[{ts}] [{i}] read failed ({e}) - entity may have despawned/died")
                        dead[i] = "unreadable"
                    continue

                prev = last_hp.get(i)
                if prev is not None and hp != prev:
                    print(f"[{ts}] [{i}] HP: {prev} -> {hp} / {maxhp}")
                    if hp <= 0 and prev > 0:
                        dead[i] = "dead"
                        alive_count = sum(1 for k in range(len(args.enemy_ins_list)) if dead.get(k) is None)
                        print(f"[{ts}] [{i}] *** DEAD *** ({alive_count} of {len(args.enemy_ins_list)} still tracked as alive)")
                last_hp[i] = hp

            if len(dead) == len(args.enemy_ins_list):
                print(f"[{ts}] all tracked entities dead/unreadable - keep watching for the reward "
                      f"moment, or Ctrl+C if you already saw it.")

            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
