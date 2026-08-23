"""Diff two labeled dump pairs (see gameman_dump.py) to find byte offsets that
are stable within each state but differ between states - i.e. state flags,
not noise (timers/position/animation floats drift within a single state too
and get excluded by the stability check).

Usage: python gameman_diff.py <label_a> <label_b>
"""
import os
import struct
import sys

DUMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dumps")


def load(label, i):
    path = os.path.join(DUMP_DIR, f"{label}_{i}.bin")
    with open(path, "rb") as f:
        return f.read()


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
    if len(sys.argv) != 3:
        print("Usage: python gameman_diff.py <label_a> <label_b>")
        sys.exit(1)
    label_a, label_b = sys.argv[1], sys.argv[2]

    a1, a2 = load(label_a, 1), load(label_a, 2)
    b1, b2 = load(label_b, 1), load(label_b, 2)
    size = min(len(a1), len(a2), len(b1), len(b2))

    candidates = [
        o for o in range(size)
        if a1[o] == a2[o] and b1[o] == b2[o] and a1[o] != b1[o]
    ]

    if not candidates:
        print(f"No stable-but-different byte offsets found between {label_a!r} and {label_b!r}.")
        return

    print(f"{len(candidates)} stable-but-different byte offset(s) between {label_a!r} and {label_b!r}:\n")
    for start, end in group_runs(candidates):
        length = end - start + 1
        a_bytes = a1[start:end + 1]
        b_bytes = b1[start:end + 1]
        print(f"+{start:#06x}..+{end:#06x} ({length} byte{'s' if length != 1 else ''})")
        print(f"    {label_a}: {a_bytes.hex()}")
        print(f"    {label_b}: {b_bytes.hex()}")
        if length == 4:
            a_i32 = struct.unpack("<i", a_bytes)[0]
            b_i32 = struct.unpack("<i", b_bytes)[0]
            a_f = struct.unpack("<f", a_bytes)[0]
            b_f = struct.unpack("<f", b_bytes)[0]
            print(f"    as int32: {a_i32} vs {b_i32}   as float: {a_f} vs {b_f}")
        elif length == 1:
            print(f"    as byte: {a_bytes[0]} vs {b_bytes[0]}")
        elif length == 8:
            a_i64 = struct.unpack("<q", a_bytes)[0]
            b_i64 = struct.unpack("<q", b_bytes)[0]
            print(f"    as int64: {a_i64} vs {b_i64}")
        print()


if __name__ == "__main__":
    main()
