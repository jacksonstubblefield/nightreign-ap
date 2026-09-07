"""Watch the popup-state object found via disasm_popup.py (module_base + slot_rva, dereferenced)
for the +0xEC00 "popup fired" pulse found in popup_bracket_test2.py - confirmed to fire on our own
artificial popupMessageCall triggers (eventId 1000 and 2300), NOT yet confirmed against a real
in-game "GREAT ENEMY FELLED"/"ENEMY FELLED" banner (which may go through Elden Ring's generic
banner system rather than this Nightreign-specific eventId path). This script is that test.

Usage: python -u popup_flag_watch.py [--slot-rva 3c14a70] [--interval 0.1] [--size 10000]
"""
import argparse
import struct
import sys
import time

import pymem
import pymem.process

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot-rva", type=lambda s: int(s, 16), default=0x3c14a70)
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument("--size", type=lambda s: int(s, 16), default=0x10000)
    args = parser.parse_args()

    pm = pymem.Pymem(PROCESS_NAME)
    module = pymem.process.module_from_name(pm.process_handle, PROCESS_NAME)
    slot_addr = module.lpBaseOfDll + args.slot_rva

    print(f"Watching popup-state object via slot {slot_addr:#x} ({args.size:#x} bytes, "
          f"every {args.interval}s) - Ctrl+C to stop.")

    last_blob = None
    try:
        while True:
            try:
                obj_addr = pm.read_ulonglong(slot_addr)
                if not obj_addr:
                    time.sleep(args.interval)
                    continue
                blob = pm.read_bytes(obj_addr, args.size)
            except Exception:
                time.sleep(args.interval)
                continue

            if last_blob is not None and len(last_blob) == len(blob):
                diffs = [o for o in range(len(blob)) if last_blob[o] != blob[o]]
                if diffs:
                    ts = time.strftime("%H:%M:%S")
                    print(f"[{ts}] {len(diffs)} byte(s) changed:")
                    for start, end in group_runs(diffs):
                        length = end - start + 1
                        a_bytes = last_blob[start:end + 1]
                        b_bytes = blob[start:end + 1]
                        line = f"    +{start:#06x}..+{end:#06x} ({length}B): {a_bytes.hex()} -> {b_bytes.hex()}"
                        if length == 4:
                            a_i = struct.unpack("<i", a_bytes)[0]
                            b_i = struct.unpack("<i", b_bytes)[0]
                            line += f"   as int32: {a_i} -> {b_i}"
                        print(line)
                    print()
            last_blob = blob
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
