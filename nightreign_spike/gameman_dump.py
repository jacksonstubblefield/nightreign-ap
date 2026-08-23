"""One-off raw dump of a resolved struct's bytes, taken twice a few seconds apart,
for offline diffing against another state's dump pair (see gameman_diff.py). Two
dumps per state let the diff step exclude addresses that drift on their own
(timers, position floats, animation counters) rather than because the state
actually changed.

Defaults to GameMan for backward compatibility; pass --target gamedataman to dump
GameDataMan instead (see spike_common.AOB_TARGETS).

Usage: python gameman_dump.py <label> [--target gameman|gamedataman] [--size hex]
Writes dumps/<label>_1.bin and dumps/<label>_2.bin, ~3s apart.
"""
import argparse
import os
import sys
import time

from spike_common import AOB_TARGETS, kernel32, read_bytes, resolve_pid_module_slot, struct

DEFAULT_DUMP_SIZE = 0x3000
GAP_SECONDS = 3

DUMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dumps")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--target", choices=sorted(AOB_TARGETS), default="gameman")
    parser.add_argument("--size", type=lambda s: int(s, 16), default=DEFAULT_DUMP_SIZE)
    args = parser.parse_args()

    aob_pattern = AOB_TARGETS[args.target]

    try:
        h_process, pointer_slot = resolve_pid_module_slot(aob_pattern)
    except LookupError as e:
        print(e)
        sys.exit(1)

    try:
        os.makedirs(DUMP_DIR, exist_ok=True)

        for i in (1, 2):
            obj_addr = struct.unpack("<Q", read_bytes(h_process, pointer_slot, 8))[0]
            if not obj_addr:
                print(f"Dump {i}: {args.target} pointer is currently null (scene transition?) - aborting")
                sys.exit(1)
            blob = read_bytes(h_process, obj_addr, args.size)
            out_path = os.path.join(DUMP_DIR, f"{args.label}_{i}.bin")
            with open(out_path, "wb") as f:
                f.write(blob)
            print(f"Dump {i}: {args.target}={obj_addr:#x} -> {out_path} ({len(blob)} bytes)")
            if i == 1:
                time.sleep(GAP_SECONDS)
    finally:
        kernel32.CloseHandle(h_process)


if __name__ == "__main__":
    main()
