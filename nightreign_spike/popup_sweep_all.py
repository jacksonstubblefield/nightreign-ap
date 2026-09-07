"""Sweep every manager already resolved in the user's CE table, bracketed tightly around one
controlled popup_trigger.py-style call (zero latency, exact synchronization - see
popup_bracket_test.py). MenuMan itself was already conclusively ruled out (0 bytes changed at
256KB) - this checks whether the popup's actual display state lives in one of the OTHER managers
instead, since popupMessageCall may resolve its own internal state independently of the MenuMan
argument it's handed.

Usage: python popup_sweep_all.py <eventId> [--size 4000]
"""
import argparse
import struct
import sys

import pymem
import pymem.exception
import pymem.pattern
import pymem.process

from popup_trigger import (
    POPUP_CALL_AOB,
    PROCESS_NAME,
    _TRAMPOLINE_PREFIX,
    _TRAMPOLINE_SUFFIX,
    _resolve_function_address,
    _resolve_pointer_slot,
)

# Ported from the user's own CE table's generic-managers list (not previously in this project's
# spike tooling - added specifically for this sweep). name -> (aob, offset).
MANAGERS = {
    "menuman": ("48 8B 0D ?? ?? ?? ?? 83 79 48 00 ?? ?? ?? ?? ?? ?? 49 8B 85 B8 01 00 00 48 8B 88 88 00 00 00 E8", 0),
    "sessionmanager": ("?? 8B EC 48 83 EC ?? 48 8B F9 C7 45 F0 00 00 00 00 48 8B 0D", 0x11),
    "cstrophy": ("48 8B 0D ?? ?? ?? ?? 48 85 C9 ?? ?? 48 8D 55 10", 0),
    "csbulletins": ("48 8D 54 24 20 48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 8D 44 24 20", 0x5),
    "gameman": ("48 8B 05 ?? ?? ?? ?? 83 B8 ?? ?? ?? ?? 00 ?? ?? ?? ?? ?? ?? 48 8D 4C 24", 0),
    "gamedataman": ("48 8B 0D ?? ?? ?? ?? F3 48 0F 2C C0", 0),
    "csregulationmanager": ("48 8B 0D ?? ?? ?? ?? 48 85 C9 ?? ?? 4C 8B C0 48 8B D7", 0),
    "fd4padmanager": ("48 89 5C 24 08 48 89 74 24 10 55 57 41 54 41 55 41 56 48 8B EC 48 83 EC 60 4C 8B F1 C7 45 40 00 00 00 00", 0x35),
    "fieldarea": ("48 8B 05 ?? ?? ?? ?? 48 85 C0 ?? ?? ?? ?? ?? ?? 4C 8B 68", 0),
}


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
    parser.add_argument("event_id", type=int)
    parser.add_argument("--size", type=lambda s: int(s, 16), default=0x4000)
    args = parser.parse_args()

    pm = pymem.Pymem(PROCESS_NAME)
    module = pymem.process.module_from_name(pm.process_handle, PROCESS_NAME)

    resolved = {}
    for name, (aob, offset) in MANAGERS.items():
        try:
            slot = _resolve_pointer_slot(pm, module, aob) if offset == 0 else None
            if offset != 0:
                # _resolve_pointer_slot doesn't take offset in this spike port - inline it here.
                import re
                pattern = b"".join(
                    re.escape(bytes.fromhex(p)) if p not in ("??", "?") else b"."
                    for p in aob.split()
                )
                match_addr = pymem.pattern.pattern_scan_module(
                    pm.process_handle, module, pattern, check_memory_protection=False
                )
                if match_addr is None:
                    raise LookupError("not found")
                address = match_addr + offset
                disp = struct.unpack("<i", pm.read_bytes(address + 3, 4))[0]
                slot = address + 7 + disp
            obj_addr = pm.read_ulonglong(slot)
            if obj_addr:
                resolved[name] = obj_addr
            else:
                print(f"{name}: object pointer is null, skipping")
        except (LookupError, pymem.exception.MemoryReadError, pymem.exception.WinAPIError) as e:
            print(f"{name}: failed to resolve ({e})")

    print(f"\nResolved {len(resolved)}/{len(MANAGERS)} managers: {sorted(resolved)}\n")

    popup_call_addr = _resolve_function_address(pm, module, POPUP_CALL_AOB)
    menuman_obj = resolved.get("menuman")
    if not menuman_obj:
        print("menuman didn't resolve - can't fire the trigger, aborting")
        sys.exit(1)

    code = _TRAMPOLINE_PREFIX + struct.pack("<Q", popup_call_addr) + _TRAMPOLINE_SUFFIX
    trampoline_addr = pm.allocate(len(code))
    pm.write_bytes(trampoline_addr, code, len(code))
    param_addr = pm.allocate(16)
    params = struct.pack("<QQ", menuman_obj, args.event_id)
    pm.write_bytes(param_addr, params, len(params))

    before = {name: pm.read_bytes(addr, args.size) for name, addr in resolved.items()}
    pm.start_thread(trampoline_addr, params=param_addr)
    after = {name: pm.read_bytes(addr, args.size) for name, addr in resolved.items()}

    any_hit = False
    for name in resolved:
        diffs = [o for o in range(args.size) if before[name][o] != after[name][o]]
        if not diffs:
            print(f"{name}: no change")
            continue
        any_hit = True
        print(f"{name}: {len(diffs)} byte(s) changed:")
        for start, end in group_runs(diffs):
            length = end - start + 1
            a_bytes = before[name][start:end + 1]
            b_bytes = after[name][start:end + 1]
            line = f"    +{start:#06x}..+{end:#06x} ({length}B): {a_bytes.hex()} -> {b_bytes.hex()}"
            if length == 4:
                a_i = struct.unpack("<i", a_bytes)[0]
                b_i = struct.unpack("<i", b_bytes)[0]
                line += f"   as int32: {a_i} -> {b_i}"
            print(line)
    if not any_hit:
        print("\nNothing changed in ANY resolved manager.")


if __name__ == "__main__":
    main()
