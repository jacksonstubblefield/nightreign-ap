"""Intersect the stable-but-different byte offsets across 2+ dump-pair labels (see
gameman_dump.py/gameman_diff.py) - for when a single before/after diff is too noisy to eyeball
(e.g. FieldArea's busy nearby-object-tracking region during the 2026-09 POI-completion spike).
An offset that changes across every listed event is a much stronger candidate for a real,
generically-triggered signal than one that only changed once, which is more likely noise specific
to that particular encounter (extra nearby enemies, projectiles, position drift, etc.).

Usage: python gameman_intersect.py <label_a> <label_b> [<label_c> ...]
"""
import os
import sys

DUMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dumps")


def load(label, i):
    with open(os.path.join(DUMP_DIR, f"{label}_{i}.bin"), "rb") as f:
        return f.read()


def stable_diff_offsets(label_a, label_b):
    a1, a2 = load(label_a, 1), load(label_a, 2)
    b1, b2 = load(label_b, 1), load(label_b, 2)
    size = min(len(a1), len(a2), len(b1), len(b2))
    return {o for o in range(size) if a1[o] == a2[o] and b1[o] == b2[o] and a1[o] != b1[o]}


def main():
    if len(sys.argv) < 5 or len(sys.argv) % 2 != 1:
        print("Usage: python gameman_intersect.py <before_a> <after_a> <before_b> <after_b> [...]")
        sys.exit(1)

    pairs = list(zip(sys.argv[1::2], sys.argv[2::2]))
    per_pair = [stable_diff_offsets(before, after) for before, after in pairs]

    common = set.intersection(*per_pair)

    for (before, after), offsets in zip(pairs, per_pair):
        print(f"{before!r} -> {after!r}: {len(offsets)} changed offset(s)")
    print(f"\nCommon to ALL {len(pairs)} pairs: {len(common)}\n")
    for o in sorted(common):
        print(f"+{o:#06x}")


if __name__ == "__main__":
    main()
