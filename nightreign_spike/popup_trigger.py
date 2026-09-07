"""Port of the CE table's "popupMessage" script (Target Class section) to Python via pymem, so we
can fire a UI banner on OUR OWN command instead of waiting for a real boss kill and racing its
~2s on-screen window with chat cues. Same trampoline shape as
worlds/nightreign/memory_writer.py's SetEventFlag port (CreateRemoteThread via pymem's
start_thread(), a plain `ret` cleanly exits the thread per that module's docstring) - just 2
params (MenuMan object addr, eventId) instead of 3, and no r8 load.

Known eventId catalog (from the CE table's own dropdown), see roadmap memory for the full list:
  1000 Demigod felled   2300 Objective Achieved   4000/4010 Victory/Defeat
  1100 Invader Vanquished  2200 Power Gained        4099-4101 Day 1/2/3
  1200 Commence            2000 Lost Grace Discovered  3000 You Died

Purely a cosmetic UI trigger - popupMessageCall only displays a banner, it does not touch save
state, EventFlags, or anything else. Requires the Python 3.12 install (pymem), same as
memory_writer.py.

Usage: python popup_trigger.py <eventId>
"""
import re
import struct
import sys

import pymem
import pymem.exception
import pymem.pattern
import pymem.process

MENUMAN_AOB = "48 8B 0D ?? ?? ?? ?? 83 79 48 00 ?? ?? ?? ?? ?? ?? 49 8B 85 B8 01 00 00 48 8B 88 88 00 00 00 E8"
POPUP_CALL_AOB = "40 53 48 83 EC 30 48 8D 4C 24 20 C7 44 24 20 FF FF FF FF 8B DA 48 C7 44 24 28 00 00 00 00"

PROCESS_NAME = "nightreign.exe"

_TRAMPOLINE_PREFIX = bytes.fromhex(
    "4889C8"        # mov rax, rcx
    "488B08"        # mov rcx, [rax]        ; rcx = MenuMan object addr
    "488B5008"      # mov rdx, [rax+8]      ; rdx = eventId
    "4883EC28"      # sub rsp, 0x28
    "48B8"          # movabs rax, <popup_call_addr>
)
_TRAMPOLINE_SUFFIX = bytes.fromhex(
    "FFD0"          # call rax
    "4883C428"      # add rsp, 0x28
    "31C0"          # xor eax, eax
    "C3"            # ret
)


def _aob_to_regex_bytes(pattern: str) -> bytes:
    """Ported verbatim from worlds/nightreign/memory_reader.py - pymem's pattern_scan_module
    wants a regex-style bytes pattern (. as wildcard), not the raw CE '??'-wildcard string."""
    chunks = []
    for part in pattern.split():
        if part in ("??", "?"):
            chunks.append(b".")
        else:
            chunks.append(re.escape(bytes.fromhex(part)))
    return b"".join(chunks)


def _resolve_pointer_slot(pm: pymem.Pymem, module, aob: str) -> int:
    pattern = _aob_to_regex_bytes(aob)
    match_addr = pymem.pattern.pattern_scan_module(
        pm.process_handle, module, pattern, check_memory_protection=False
    )
    if match_addr is None:
        raise LookupError(f"AOB not found: {aob}")
    disp = struct.unpack("<i", pm.read_bytes(match_addr + 3, 4))[0]
    return match_addr + 7 + disp


def _resolve_function_address(pm: pymem.Pymem, module, aob: str) -> int:
    pattern = _aob_to_regex_bytes(aob)
    match_addr = pymem.pattern.pattern_scan_module(
        pm.process_handle, module, pattern, check_memory_protection=False
    )
    if match_addr is None:
        raise LookupError(f"AOB not found: {aob}")
    return match_addr


def main():
    if len(sys.argv) != 2:
        print("Usage: python popup_trigger.py <eventId>")
        sys.exit(1)
    event_id = int(sys.argv[1])

    pm = pymem.Pymem(PROCESS_NAME)
    module = pymem.process.module_from_name(pm.process_handle, PROCESS_NAME)

    menuman_slot = _resolve_pointer_slot(pm, module, MENUMAN_AOB)
    popup_call_addr = _resolve_function_address(pm, module, POPUP_CALL_AOB)
    print(f"MenuMan slot: {menuman_slot:#x}   popupMessageCall: {popup_call_addr:#x}")

    menuman_obj = pm.read_ulonglong(menuman_slot)
    if not menuman_obj:
        print("MenuMan object pointer is currently null - aborting")
        sys.exit(1)
    print(f"MenuMan object: {menuman_obj:#x}")

    code = _TRAMPOLINE_PREFIX + struct.pack("<Q", popup_call_addr) + _TRAMPOLINE_SUFFIX
    trampoline_addr = pm.allocate(len(code))
    pm.write_bytes(trampoline_addr, code, len(code))

    param_addr = pm.allocate(16)
    params = struct.pack("<QQ", menuman_obj, event_id)
    pm.write_bytes(param_addr, params, len(params))

    print(f"Firing eventId={event_id} ...")
    pm.start_thread(trampoline_addr, params=param_addr)
    print("Done.")


if __name__ == "__main__":
    main()
