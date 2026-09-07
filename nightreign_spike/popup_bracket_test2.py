"""Same tight bracket as popup_bracket_test.py, but targeting the fixed global pointer slot found
by disassembling popupMessageCall (see disasm_popup.py) - 0x7ff77bf44a70 in the observed session,
NOT a stable address across restarts (ASLR) so this is re-derived via addr - module_base each run
and re-applied to the CURRENT session's module_base, same as every AOB-resolved target elsewhere.

Usage: python popup_bracket_test2.py <eventId> <slot_rva_hex> [--size 10000]
"""
import argparse
import struct
import sys

import pymem
import pymem.process

from popup_trigger import (
    MENUMAN_AOB,
    POPUP_CALL_AOB,
    PROCESS_NAME,
    _TRAMPOLINE_PREFIX,
    _TRAMPOLINE_SUFFIX,
    _resolve_function_address,
    _resolve_pointer_slot,
)


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
    parser.add_argument("slot_rva", type=lambda s: int(s, 16))
    parser.add_argument("--size", type=lambda s: int(s, 16), default=0x10000)
    args = parser.parse_args()

    pm = pymem.Pymem(PROCESS_NAME)
    module = pymem.process.module_from_name(pm.process_handle, PROCESS_NAME)

    slot_addr = module.lpBaseOfDll + args.slot_rva
    print(f"Module base: {module.lpBaseOfDll:#x}   slot addr: {slot_addr:#x}")

    obj_addr = pm.read_ulonglong(slot_addr)
    if not obj_addr:
        print("Object pointer at this slot is currently null - aborting")
        sys.exit(1)
    print(f"Object addr: {obj_addr:#x}")

    menuman_slot = _resolve_pointer_slot(pm, module, MENUMAN_AOB)
    popup_call_addr = _resolve_function_address(pm, module, POPUP_CALL_AOB)
    menuman_obj = pm.read_ulonglong(menuman_slot)

    code = _TRAMPOLINE_PREFIX + struct.pack("<Q", popup_call_addr) + _TRAMPOLINE_SUFFIX
    trampoline_addr = pm.allocate(len(code))
    pm.write_bytes(trampoline_addr, code, len(code))
    param_addr = pm.allocate(16)
    params = struct.pack("<QQ", menuman_obj, args.event_id)
    pm.write_bytes(param_addr, params, len(params))

    before = pm.read_bytes(obj_addr, args.size)
    pm.start_thread(trampoline_addr, params=param_addr)
    after = pm.read_bytes(obj_addr, args.size)

    diffs = [o for o in range(args.size) if before[o] != after[o]]
    if not diffs:
        print("No bytes changed at all in this window.")
        return

    print(f"{len(diffs)} byte(s) changed:\n")
    for start, end in group_runs(diffs):
        length = end - start + 1
        a_bytes = before[start:end + 1]
        b_bytes = after[start:end + 1]
        line = f"+{start:#06x}..+{end:#06x} ({length}B): {a_bytes.hex()} -> {b_bytes.hex()}"
        if length == 4:
            a_i = struct.unpack("<i", a_bytes)[0]
            b_i = struct.unpack("<i", b_bytes)[0]
            line += f"   as int32: {a_i} -> {b_i}"
        print(line)


if __name__ == "__main__":
    main()
