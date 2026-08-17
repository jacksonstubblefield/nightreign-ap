"""Remote-call write primitive for Elden Ring Nightreign: fires the game's own SetEventFlag
semantics via a hand-built x64 trampoline run through pymem's allocate()/write_bytes()/
start_thread() wrappers - no ctypes needed beyond struct.pack, no new pip dependency.

Deliberately free of any Archipelago/CommonClient imports, same reasoning as memory_reader.py -
see its module docstring. Exercise this standalone against the live game via the __main__ block
below, independent of the rest of the world/client.

Background: a Cheat Engine table exposes a SetEventFlag(flag, on) Lua helper that calls a real
function in the game process (EventFlagBaseA, found via AOB) through CE's executeCodeEx, i.e.
EventFlagBaseA(EventFlag_value, flag, on) - a 3-argument x64 call (rcx/rdx/r8). Live-tested via CE
and confirmed: SetEventFlag(110, 1) reveals all 6 secondary Nightlords as one atomic batch, and
SetEventFlag(115, 1) separately reveals Night Aspect. This module is the Python port of that call.

pymem has no multi-argument remote-call helper - Pymem.start_thread() only wraps
CreateRemoteThread's single lpParameter. The trampoline below works around that: lpParameter
points at a 3-qword block in the target process; the trampoline loads those three qwords into
rcx/rdx/r8 and calls EventFlagBaseA, then does a plain `ret`. Windows' thread-init thunk sets up a
new thread's initial stack such that a ThreadProc-style function returning via `ret` cleanly exits
the thread - the same mechanism the classic CreateRemoteThread(LoadLibraryA) DLL-injection trick
relies on - so no separate ExitThread call/address is needed.
"""

from __future__ import annotations

import struct
from typing import Optional

import pymem
import pymem.exception

# rcx (the single CreateRemoteThread lpParameter) points at a 3-qword block:
#   [0] EventFlag pointer VALUE (already dereferenced, not its slot address)
#   [1] flag id
#   [2] on (0/1)
# Loads those into rcx/rdx/r8, calls EventFlagBaseA, restores the stack, returns 0.
_TRAMPOLINE_PREFIX = bytes.fromhex(
    "48 89 C8"      # mov rax, rcx
    "48 8B 08"      # mov rcx, [rax]
    "48 8B 50 08"   # mov rdx, [rax+8]
    "4C 8B 40 10"   # mov r8,  [rax+16]
    "48 83 EC 28"   # sub rsp, 0x28         ; shadow space + 16-byte align before the call
    "48 B8"         # movabs rax, <8-byte address filled in below>
    .replace(" ", "")
)
_TRAMPOLINE_SUFFIX = bytes.fromhex(
    "FF D0"         # call rax
    "48 83 C4 28"   # add rsp, 0x28
    "31 C0"         # xor eax, eax
    "C3"            # ret
)


def _build_trampoline(eventflag_base_a_addr: int) -> bytes:
    return _TRAMPOLINE_PREFIX + struct.pack("<Q", eventflag_base_a_addr) + _TRAMPOLINE_SUFFIX


class NightreignMemoryWriter:
    """Fires SetEventFlag-equivalent calls into a running nightreign.exe.

    Construct with the (eventflag_ptr_slot, eventflag_base_a_addr) pair from
    NightreignMemoryReader.resolve_event_flag_targets(), against the same pymem.Pymem instance the
    reader is already attached with (don't open a second handle to the same process).
    """

    def __init__(self, pm: pymem.Pymem, eventflag_ptr_slot: int, eventflag_base_a_addr: int):
        self.pm = pm
        self._eventflag_ptr_slot = eventflag_ptr_slot
        self._eventflag_base_a_addr = eventflag_base_a_addr
        self._trampoline_addr: Optional[int] = None
        self._param_addr: Optional[int] = None

    def _ensure_allocated(self) -> None:
        # Allocated once and reused for the life of this writer - never freed, but this is called
        # at most a handful of times per session (one AP item receive = one flag write), so the
        # leak is bounded and not worth the extra bookkeeping of a free() path.
        if self._trampoline_addr is None:
            code = _build_trampoline(self._eventflag_base_a_addr)
            self._trampoline_addr = self.pm.allocate(len(code))
            self.pm.write_bytes(self._trampoline_addr, code, len(code))
        if self._param_addr is None:
            self._param_addr = self.pm.allocate(24)

    def set_event_flag(self, flag: int, on: bool) -> bool:
        """Best-effort, SYNCHRONOUS AND BLOCKING (pymem's start_thread waits on the remote thread
        internally) - call via loop.run_in_executor from client.py, never directly from the
        asyncio thread, or it will stall the whole client for the duration of the remote call.

        Returns False if the EventFlag pointer is transiently unreadable (e.g. a scene
        transition), matching memory_reader.py's convention. Returns True only if the remote
        thread was dispatched and ran to completion - NOT that the flag change is confirmed, since
        there's no known read-back offset for a flag's current value. Treat success here as
        provisional until visually confirmed in-game.
        """
        try:
            eventflag_value = self.pm.read_ulonglong(self._eventflag_ptr_slot)
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            return False
        if not eventflag_value:
            return False

        self._ensure_allocated()
        params = struct.pack("<QQQ", eventflag_value, flag, 1 if on else 0)
        self.pm.write_bytes(self._param_addr, params, len(params))
        self.pm.start_thread(self._trampoline_addr, params=self._param_addr)
        return True


def _main():
    import argparse

    try:
        from .memory_reader import NightreignMemoryReader, PointerNotFoundError
    except ImportError:
        import os
        import sys

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from memory_reader import NightreignMemoryReader, PointerNotFoundError  # type: ignore[no-redef]

    parser = argparse.ArgumentParser(
        description="Fire a single SetEventFlag call against a running nightreign.exe, for "
        "manual parity testing against the known-good Cheat Engine behavior."
    )
    parser.add_argument("--flag", type=int, required=True, help="EventFlag id, e.g. 110 or 115")
    parser.add_argument("--on", type=int, choices=(0, 1), default=1, help="0 or 1, default 1")
    args = parser.parse_args()

    reader = NightreignMemoryReader()
    if not reader.connect():
        print("nightreign.exe not running - launch the game first.")
        return

    try:
        ptr_slot, base_a_addr = reader.resolve_event_flag_targets()
    except PointerNotFoundError as exc:
        print(f"Fatal: {exc}")
        return

    print(f"EventFlag ptr slot: {ptr_slot:#x}  EventFlagBaseA: {base_a_addr:#x}")
    writer = NightreignMemoryWriter(reader.pm, ptr_slot, base_a_addr)
    ok = writer.set_event_flag(args.flag, bool(args.on))
    print(f"SetEventFlag({args.flag}, {args.on}) -> {'dispatched' if ok else 'FAILED (pointer unreadable)'}")
    print("Check the in-game Expeditions screen to confirm the visual result.")


if __name__ == "__main__":
    _main()
