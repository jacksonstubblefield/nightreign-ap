"""Hunt for a live entity's own placement/event Entity ID by searching its memory for known values,
instead of eyeballing a before/after diff - see nightreign-roadmap memory's 2026-09-05 "external repo
lead" entry for the full context. The enemy-rando repo's own docs (BOSS_REWARD_EMEVD_README.md)
show Nightreign's own POI-completion signal is a single entity's Entity ID (chr2.Passed ->
HandleMinibossDefeat(chrEntityId)), and nr_slot_metadata.json (cached in dumps/) catalogs every
recipient_is_boss==true placement's entity_id across all ~195 pre-baked maps. If a live entity's own
Entity ID is stored anywhere near its EnemyIns/ChrIns struct or its HP module, it should show up
verbatim as a known integer in a raw scan - no need to know which boss this is in advance, and no
need to cross-reference a name first.

Usage: python poi_entityid_probe.py <EnemyIns_ptr_hex> [--size 800] [--unaligned]
    <EnemyIns_ptr_hex> - the pEnemyIns value captured by the CE table's CanBeLockedOn hook while
    locked onto a real boss/POI-reward enemy in-game (same source boss_death_watch.py uses).
    --unaligned also checks every byte offset, not just 4-byte-aligned ones (slower, noisier,
    use only if the aligned scan comes back empty).
"""
import argparse
import json
import os
import struct
import sys

import pymem

from popup_trigger import PROCESS_NAME

DUMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dumps")
METADATA_PATH = os.path.join(DUMP_DIR, "nr_slot_metadata.json")

DEFAULT_SIZE = 0x800


def load_boss_entity_ids():
    with open(METADATA_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    by_id = {}
    for row in rows:
        eid = row["entity_id"]
        if row["recipient_is_boss"] and eid:
            by_id.setdefault(eid, []).append(row)
    return by_id


def scan_blob(label, base_addr, blob, by_id, unaligned):
    step = 1 if unaligned else 4
    hits = []
    for offset in range(0, len(blob) - 3, step):
        value = struct.unpack_from("<I", blob, offset)[0]
        if value in by_id:
            hits.append((offset, value))
    if not hits:
        print(f"  [{label}] no matches in {len(blob):#x} bytes from {base_addr:#x}")
        return
    print(f"  [{label}] {len(hits)} match(es) in {len(blob):#x} bytes from {base_addr:#x}:")
    for offset, value in hits:
        rows = by_id[value]
        row_desc = "; ".join(f"{r['map']} c_prefix={r['c_prefix']} npc_param_id={r['npc_param_id']}" for r in rows)
        print(f"    +{offset:#06x} (abs {base_addr + offset:#x}): entity_id={value}  <-  {row_desc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("enemy_ins", type=lambda s: int(s, 16))
    parser.add_argument("--size", type=lambda s: int(s, 16), default=DEFAULT_SIZE)
    parser.add_argument("--unaligned", action="store_true")
    args = parser.parse_args()

    by_id = load_boss_entity_ids()
    print(f"Loaded {len(by_id)} known recipient_is_boss entity_id(s) from {METADATA_PATH}")

    pm = pymem.Pymem(PROCESS_NAME)

    print(f"Scanning around EnemyIns={args.enemy_ins:#x} ({'unaligned' if args.unaligned else '4-byte aligned'}):")

    try:
        top_blob = pm.read_bytes(args.enemy_ins, args.size)
        scan_blob("EnemyIns/ChrIns top", args.enemy_ins, top_blob, by_id, args.unaligned)
    except Exception as e:
        print(f"  [EnemyIns/ChrIns top] read failed: {e}")

    try:
        hp_module = pm.read_ulonglong(args.enemy_ins + 0x1B8)
        hp_base = pm.read_ulonglong(hp_module + 0x00)
        hp_blob = pm.read_bytes(hp_base, args.size)
        scan_blob("HP module (via +0x1B8 chain)", hp_base, hp_blob, by_id, args.unaligned)
    except Exception as e:
        print(f"  [HP module] read failed: {e}")


if __name__ == "__main__":
    main()
