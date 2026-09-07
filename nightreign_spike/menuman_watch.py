"""Continuous live monitor for a manager's memory region - for catching short-lived transient
events (like the ~2s "GREAT ENEMY FELLED" banner) that are too fast to bracket with manual
before/after chat cues. Polls fast (default 150ms) and prints a timestamped diff the moment
anything changes, so you can just play normally and correlate the printed output against what you
saw on screen afterward.

Run this yourself in its own terminal window alongside the game - it's meant to run continuously
while you play, not be driven turn-by-turn through chat.

Usage: python -u menuman_watch.py [--target menuman] [--interval 0.15] [--size 2000]
"""
import argparse
import struct
import sys
import time

from spike_common import AOB_OFFSETS, AOB_TARGETS, kernel32, read_bytes, resolve_pid_module_slot


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


def describe_diff(prev_blob, curr_blob):
    diffs = [o for o in range(len(prev_blob)) if prev_blob[o] != curr_blob[o]]
    if not diffs:
        return
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {len(diffs)} byte(s) changed:")
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
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=sorted(AOB_TARGETS), default="menuman")
    parser.add_argument("--interval", type=float, default=0.15, help="poll interval in seconds")
    parser.add_argument("--size", type=lambda s: int(s, 16), default=0x2000)
    args = parser.parse_args()

    aob_pattern = AOB_TARGETS[args.target]
    aob_offset = AOB_OFFSETS.get(args.target, 0)

    try:
        h_process, pointer_slot = resolve_pid_module_slot(aob_pattern, offset=aob_offset)
    except LookupError as e:
        print(e)
        sys.exit(1)

    print(f"Watching {args.target} ({args.size:#x} bytes, every {args.interval}s) - Ctrl+C to stop.")
    last_blob = None
    try:
        while True:
            try:
                obj_addr = struct.unpack("<Q", read_bytes(h_process, pointer_slot, 8))[0]
                if not obj_addr:
                    time.sleep(args.interval)
                    continue
                blob = read_bytes(h_process, obj_addr, args.size)
            except OSError:
                time.sleep(args.interval)
                continue

            if last_blob is not None and len(last_blob) == len(blob):
                describe_diff(last_blob, blob)
            last_blob = blob
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        kernel32.CloseHandle(h_process)


if __name__ == "__main__":
    main()
