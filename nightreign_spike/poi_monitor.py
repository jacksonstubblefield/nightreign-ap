"""Live monitor for the GameDataMan candidate offsets found during the POI-tracking spike
session (2026-08-30) - polls continuously and prints a guess whenever one changes, instead of
requiring a manual before/after dump-and-diff bracket around each event. Purely a corroboration
aid: nothing here is confirmed enough to trust blindly yet (see nightreign-roadmap memory for the
full incident history/corroboration counts), so treat every printed line as "does this match what
you just did?", not as ground truth.

Candidates and what triggered them so far:
  - DAY_COUNTER_OFFSET (0xDE): 1 on Day 1, 2 on Day 2, 3 after the Night 2 (final) boss.
    Confirmed 2/2 transitions, no false positives.
  - MAJOR_COUNTER_OFFSET (0x604): increments on ruins, evergaol, and both Night bosses.
    Does NOT fire on camp/fort/church/Rise. Confirmed 5 firings, 0 false positives.
  - STRUCTURE_COUNTER_OFFSET (0x194): increments on camp, fort, and church.
    Does NOT fire on ruins/evergaol/Night bosses/Rise. Confirmed 4 firings, 0 false positives.
  - WIN_FLAG_CANDIDATE_OFFSET (0x608): flipped 0->1 on the Night 2 (expedition-ending) boss kill
    only - did NOT fire on the Night 1 boss. Only 1 data point so far, unconfirmed.

Rise (puzzle-tower POIs) triggered none of the above - no known signal for it yet.

Usage: python poi_monitor.py [--interval seconds]
       python poi_monitor.py --diff [--region-size hex]
    --diff widens each poll to read the whole GameDataMan region (default 0x3000,
    same as gameman_dump.py's default) instead of just the 4 known offsets, and
    whenever a watched offset changes, prints every OTHER byte that changed since
    the previous poll too - this is for hunting an identity field (which specific
    boss/POI, not just tier) that might sit elsewhere in the struct and tick at the
    same moment. Expect noise (this is a raw poll-to-poll diff, not the
    stability-filtered kind gameman_diff.py does) - treat hits as candidates to
    eyeball, not confirmed offsets.
"""
import argparse
import struct
import sys
import time

from spike_common import AOB_TARGETS, kernel32, read_bytes, resolve_pid_module_slot

DAY_COUNTER_OFFSET = 0xDE
STRUCTURE_COUNTER_OFFSET = 0x194
MAJOR_COUNTER_OFFSET = 0x604
WIN_FLAG_CANDIDATE_OFFSET = 0x608

WATCHED_BYTE_OFFSETS = {
    DAY_COUNTER_OFFSET: "day counter",
    STRUCTURE_COUNTER_OFFSET: "structure-POI counter (camp/fort/church)",
    MAJOR_COUNTER_OFFSET: "major-encounter counter (ruins/evergaol/Night boss)",
    WIN_FLAG_CANDIDATE_OFFSET: "win-flag candidate",
}

DEFAULT_REGION_SIZE = 0x3000


def _describe_change(offset: int, before: int, after: int) -> str:
    label = WATCHED_BYTE_OFFSETS[offset]
    if offset == DAY_COUNTER_OFFSET:
        return f"[day counter] {before} -> {after} - did you just transition to Day {after}?"
    if offset == STRUCTURE_COUNTER_OFFSET:
        return f"[structure counter] {before} -> {after} - did you just clear a camp/fort/church?"
    if offset == MAJOR_COUNTER_OFFSET:
        return f"[major counter] {before} -> {after} - did you just clear a ruins/evergaol, or a Night boss?"
    if offset == WIN_FLAG_CANDIDATE_OFFSET:
        return f"[win flag] {before} -> {after} - did you just win the expedition?"
    return f"[{label}] {before} -> {after}"


def _group_runs(offsets):
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


def _print_region_diff(prev_blob, curr_blob):
    size = min(len(prev_blob), len(curr_blob))
    diffs = [o for o in range(size) if prev_blob[o] != curr_blob[o] and o not in WATCHED_BYTE_OFFSETS]
    if not diffs:
        print("  (no other bytes changed in the region this poll)")
        return
    print(f"  {len(diffs)} other byte(s) also changed this poll (candidates - could be identity, could be noise):")
    for start, end in _group_runs(diffs):
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
    parser.add_argument("--interval", type=float, default=0.5, help="poll interval in seconds")
    parser.add_argument(
        "--diff", action="store_true",
        help="on any watched-offset change, also print other bytes that changed in the region "
             "since the last poll (identity-field hunting - see module docstring)",
    )
    parser.add_argument("--region-size", type=lambda s: int(s, 16), default=DEFAULT_REGION_SIZE)
    args = parser.parse_args()

    try:
        h_process, gamedataman_slot = resolve_pid_module_slot(AOB_TARGETS["gamedataman"])
    except LookupError as e:
        print(e)
        sys.exit(1)

    print("Watching GameDataMan candidate offsets - Ctrl+C to stop.")
    if args.diff:
        print(f"Region-diff mode on: reading {args.region_size:#x} bytes/poll, will surface other "
              f"changed bytes whenever a watched offset fires.")

    last_values = {}
    last_region = None
    try:
        while True:
            try:
                obj_addr = struct.unpack("<Q", read_bytes(h_process, gamedataman_slot, 8))[0]
                if not obj_addr:
                    time.sleep(args.interval)
                    continue
                if args.diff:
                    region = read_bytes(h_process, obj_addr, args.region_size)
                    current = {offset: region[offset] for offset in WATCHED_BYTE_OFFSETS}
                else:
                    region = None
                    current = {
                        offset: read_bytes(h_process, obj_addr + offset, 1)[0]
                        for offset in WATCHED_BYTE_OFFSETS
                    }
            except OSError:
                # transient - scene transition or momentarily unreadable, matching every other
                # reader in this repo's "don't treat this as fatal" convention.
                time.sleep(args.interval)
                continue

            if last_values:
                changed = False
                for offset, value in current.items():
                    if last_values.get(offset) != value:
                        print(_describe_change(offset, last_values[offset], value))
                        changed = True
                if changed and args.diff and last_region is not None:
                    _print_region_diff(last_region, region)
            last_values = current
            last_region = region
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        kernel32.CloseHandle(h_process)


if __name__ == "__main__":
    main()
