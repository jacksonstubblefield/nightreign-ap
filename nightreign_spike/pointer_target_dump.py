"""Dump the object a struct-relative pointer field points to, twice a few
seconds apart (same noise-filtering rationale as gameman_dump.py).

Defaults to a GameMan-relative pointer for backward compatibility; pass
--target gamedataman to walk a GameDataMan-relative pointer instead.

Usage: python pointer_target_dump.py <label> [--offset hex] [--size hex] [--target gameman|gamedataman]
Defaults: offset=0xd98, size=0x400
Writes dumps/<label>_ptrtarget_1.bin and _2.bin.
"""
import argparse
import os
import sys
import time

from spike_common import AOB_TARGETS, kernel32, read_bytes, resolve_pid_module_slot, struct

GAP_SECONDS = 3

DUMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dumps")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--target", choices=sorted(AOB_TARGETS), default="gameman")
    parser.add_argument("--offset", type=lambda s: int(s, 16), default=0xD98)
    parser.add_argument("--size", type=lambda s: int(s, 16), default=0x400)
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
                print(f"Dump {i}: {args.target} pointer is currently null - aborting")
                sys.exit(1)
            target_addr = struct.unpack("<Q", read_bytes(h_process, obj_addr + args.offset, 8))[0]
            if not target_addr:
                print(f"Dump {i}: target pointer at {args.target}+{args.offset:#x} is null - aborting")
                sys.exit(1)
            blob = read_bytes(h_process, target_addr, args.size)
            out_path = os.path.join(DUMP_DIR, f"{args.label}_ptrtarget_{i}.bin")
            with open(out_path, "wb") as f:
                f.write(blob)
            print(
                f"Dump {i}: {args.target}={obj_addr:#x}  target={target_addr:#x} "
                f"-> {out_path} ({len(blob)} bytes)"
            )
            if i == 1:
                time.sleep(GAP_SECONDS)
    finally:
        kernel32.CloseHandle(h_process)


if __name__ == "__main__":
    main()
