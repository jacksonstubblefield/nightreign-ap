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

import ctypes
import struct
from typing import Optional

import pymem
import pymem.exception
import pymem.process

try:
    from .game_data import EFFECT_CAP_MAP
except ImportError:
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from game_data import EFFECT_CAP_MAP  # type: ignore[no-redef]

try:
    from .memory_reader import ItemDropTargets
except ImportError:
    from memory_reader import ItemDropTargets  # type: ignore[no-redef]

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


# --- Item-drop write primitive (randomized-weapon filler) ---
#
# Ported from the CT table's "Sly - ItemDrop" script (contributor Volkov_ilya37) - see
# game_data.py's MAPITEMMAN_AOB/ITEMDROP_CALL_AOB/TLS_SLOT_FETCHER_ITEMDROP_AOB/ABOBA_AOB for
# provenance of the addresses resolved into an ItemDropTargets by
# NightreignMemoryReader.resolve_item_drop_targets().

def _resolve_remote_tls_set_value(pm: pymem.Pymem) -> int:
    """TlsSetValue's address in the target process. The CT script calls it by bare name, which
    only works because CE resolves well-known WinAPI exports against the *target* process's own
    import table, not CE's own. Replicated here via the same base-delta trick most game-hacking
    tools use, rather than parsing the remote PE export table by hand: kernel32.dll is a system
    DLL, and Windows shares one randomized load address for it across every process started in
    the same boot session, so `local_addr - local_kernel32_base + remote_kernel32_base` recovers
    the correct remote address even on the rare occasion the two processes don't happen to share
    the exact same base (e.g. different integrity levels)."""
    local_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    local_func_addr = ctypes.cast(local_kernel32.TlsSetValue, ctypes.c_void_p).value
    # ctypes' default assumed restype for a windll-wrapped call is c_int (32-bit signed) - without
    # this, GetModuleHandleW's real 64-bit HMODULE return value gets truncated/sign-extended into
    # garbage, corrupting every address derived from it below.
    local_kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    local_kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    local_base = local_kernel32.GetModuleHandleW("kernel32.dll")
    remote_module = pymem.process.module_from_name(pm.process_handle, "kernel32.dll")
    return local_func_addr - local_base + remote_module.lpBaseOfDll


def _hx(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str.replace(" ", ""))


def _imm(addr: int) -> bytes:
    return struct.pack("<Q", addr)


# rcx (lpParameter) points at a 2-qword block: [0] buf address, [1] item id. Loads those into
# rcx/rdx and calls the weapon-lookup helper ("Aboba" in the CT script's own Lua) - same shape as
# _TRAMPOLINE_PREFIX/_TRAMPOLINE_SUFFIX above, just one fewer argument.
_LOOKUP_TRAMPOLINE_PREFIX = (
    _hx("48 89 C8")     # mov rax, rcx
    + _hx("48 8B 08")   # mov rcx, [rax]      ; rcx = buf address
    + _hx("48 8B 50 08")  # mov rdx, [rax+8]  ; rdx = item id
    + _hx("48 83 EC 28")  # sub rsp, 0x28
    + _hx("48 B8")      # movabs rax, <Aboba address, filled in below>
)


def _build_lookup_trampoline(aboba_func_addr: int) -> bytes:
    return _LOOKUP_TRAMPOLINE_PREFIX + _imm(aboba_func_addr) + _TRAMPOLINE_SUFFIX


def _build_additem_trampoline(
    targets: ItemDropTargets, tls_set_value_addr: int, item_data_addr: int
) -> bytes:
    """Two-call trampoline, parameterless (lpParameter unused) - unlike the EventFlag/lookup
    trampolines above, every input here either never varies per-call (baked in as a movabs
    immediate) or lives in the ItemData buffer at item_data_addr, written separately by
    NightreignItemDropWriter.drop_item() before each dispatch, exactly mirroring the source
    script's own AddItem/ItemData split.

    Call 1, TlsSetValue(tls_index, fake_context): fakes a valid game-thread context. A raw
    CreateRemoteThread thread has none, and the drop function silently no-ops without it -
    tls_index itself isn't a constant, it's read out of the game's own code at
    tls_slot_fetcher_addr+0xD the same way the compiler would resolve a thread-local variable.

    Call 2, drop-function(*MapItemMan, &ItemData, 0, 1): the actual drop.
    """
    return (
        _hx("48 81 EC 28 02 00 00")                                   # sub rsp, 0x228
        + _hx("48 B9") + _imm(targets.tls_slot_fetcher_addr + 0xD)    # movabs rcx, fetcher+0xD
        + _hx("8B 01")                                                # mov eax, [rcx]
        + _hx("48 98")                                                # cdqe
        + _hx("8B 4C 01 04")                                          # mov ecx, [rcx+rax+4]
        + _hx("48 BA") + _imm(targets.tls_fake_context_addr)          # movabs rdx, fake context
        + _hx("48 B8") + _imm(tls_set_value_addr)                     # movabs rax, TlsSetValue
        + _hx("FF D0")                                                # call rax
        + _hx("48 B9") + _imm(targets.map_item_man_slot)              # movabs rcx, MapItemMan slot
        + _hx("48 8B 09")                                             # mov rcx, [rcx]
        + _hx("48 BA") + _imm(item_data_addr)                         # movabs rdx, &ItemData
        + _hx("45 31 C0")                                             # xor r8d, r8d
        + _hx("41 B9 01 00 00 00")                                    # mov r9d, 1
        + _hx("48 B8") + _imm(targets.item_drop_func_addr)            # movabs rax, drop-func entry
        + _hx("FF D0")                                                # call rax
        + _hx("48 81 C4 28 02 00 00")                                 # add rsp, 0x228
        + _hx("31 C0")                                                # xor eax, eax
        + _hx("C3")                                                   # ret
    )


# ItemData's static defaults (everything the source script's per-call writes never touch),
# transcribed verbatim from the CT script's own `dq` initializer block - written once, the same
# way CE writes it once at script-enable time, not re-applied per drop.
_ITEM_DATA_DEFAULT = b"".join(
    struct.pack("<Q", q)
    for q in (
        0xFFFFFFFFFFFFFFFF,
        0xFFFFFFFFFFFFFFFF,
        0xFFFFFFFFFFFFFFFF,
        0x00000000FFFFFFFF,
        0x0000000000000000,
        0xFFFFFFFFFFFFFFFF,
        0xFFFFFFFFFFFFFFFF,
        0x00000000FFFFFFFF,
        0x00000000FFFF0001,
    )
)
# The 9 default qwords above span 0x00-0x47; the quantity byte the source script writes on every
# call lives at +0x48, one byte past that - round the allocation up a little for headroom.
_ITEM_DATA_SIZE = 0x50


class NightreignItemDropWriter:
    """Drops a real weapon on the ground at the player's current position in a running
    nightreign.exe - the write primitive behind Archipelago's randomized-weapon filler.

    Construct with an ItemDropTargets from NightreignMemoryReader.resolve_item_drop_targets(),
    against the same pymem.Pymem instance the reader is already attached with (don't open a
    second handle to the same process).

    Two remote calls are involved, both dispatched via a fresh CreateRemoteThread (through
    pymem's start_thread() - SYNCHRONOUS AND BLOCKING, same threading caveat as
    NightreignMemoryWriter.set_event_flag: call via loop.run_in_executor from client.py, never
    directly from the asyncio thread):
      - get_weapon_addr(item_id): looks up a weapon's live param row, needed only to read its
        max upgrade tier before deciding which itemId+upgradeLevel variant to actually drop.
      - drop_item(...): the actual drop, via the two-call trampoline documented on
        _build_additem_trampoline above.
    """

    def __init__(self, pm: pymem.Pymem, targets: ItemDropTargets):
        self.pm = pm
        self.targets = targets
        self._tls_set_value_addr: Optional[int] = None
        self._lookup_trampoline_addr: Optional[int] = None
        self._lookup_param_addr: Optional[int] = None
        self._lookup_buf_addr: Optional[int] = None
        self._drop_trampoline_addr: Optional[int] = None
        self._item_data_addr: Optional[int] = None

    def _ensure_lookup_trampoline(self) -> None:
        # Same unbounded-but-bounded allocation tradeoff as NightreignMemoryWriter._ensure_allocated
        # - reused for the life of this writer, never freed.
        if self._lookup_trampoline_addr is None:
            code = _build_lookup_trampoline(self.targets.aboba_func_addr)
            self._lookup_trampoline_addr = self.pm.allocate(len(code))
            self.pm.write_bytes(self._lookup_trampoline_addr, code, len(code))
        if self._lookup_param_addr is None:
            self._lookup_param_addr = self.pm.allocate(16)
        if self._lookup_buf_addr is None:
            self._lookup_buf_addr = self.pm.allocate(32)  # matches the CT script's allocateMemory(32)

    def get_weapon_addr(self, item_id: int) -> Optional[int]:
        """Looks up a weapon's live param row address (the source script's getWeaponAddr(id), via
        its "Aboba" helper). Returns None if the result reads back as a null pointer."""
        self._ensure_lookup_trampoline()
        params = struct.pack("<QQ", self._lookup_buf_addr, item_id)
        self.pm.write_bytes(self._lookup_param_addr, params, len(params))
        self.pm.start_thread(self._lookup_trampoline_addr, params=self._lookup_param_addr)
        try:
            result = self.pm.read_ulonglong(self._lookup_buf_addr + 8)
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            return None
        return result or None

    def _clamp_upgrade_tier(self, item_id: int, upgrade_level: int) -> int:
        """Port of the source script's checkTier(): clamps a requested upgrade level (0-3) down
        to whatever this specific weapon's own max reinforcement tier actually supports.

        upgrade_level <= 0 is a fast path with no remote call - tracing checkTier's own branches
        shows a 0 input always comes back as 0 regardless of the weapon's base tier, so the
        lookup call is skippable without changing the result."""
        if upgrade_level <= 0:
            return 0
        upgrade_level = min(upgrade_level, 3)
        weapon_addr = self.get_weapon_addr(item_id)
        if weapon_addr is None:
            return 0
        try:
            base_upgrade = self.pm.read_uint(weapon_addr + 0x5C)
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            return 0
        if base_upgrade == 0xFFFFFFFF:
            return 0
        base_upgrade //= 100
        if base_upgrade == 2 and upgrade_level > 1:
            return 1
        if base_upgrade == 1 and upgrade_level == 3:
            return 2
        return upgrade_level

    def _ensure_drop_trampoline(self) -> bool:
        """Returns False (without raising) if TlsSetValue couldn't be resolved this call -
        transient, matching memory_reader.py's read convention, safe to retry on the next
        drop_item() call."""
        if self._tls_set_value_addr is None:
            try:
                self._tls_set_value_addr = _resolve_remote_tls_set_value(self.pm)
            except (pymem.exception.ProcessError, OSError):
                return False
        if self._item_data_addr is None:
            self._item_data_addr = self.pm.allocate(_ITEM_DATA_SIZE)
            self.pm.write_bytes(self._item_data_addr, _ITEM_DATA_DEFAULT, len(_ITEM_DATA_DEFAULT))
        if self._drop_trampoline_addr is None:
            code = _build_additem_trampoline(
                self.targets, self._tls_set_value_addr, self._item_data_addr
            )
            self._drop_trampoline_addr = self.pm.allocate(len(code))
            self.pm.write_bytes(self._drop_trampoline_addr, code, len(code))
        return True

    def drop_item(
        self,
        item_id: int,
        upgrade_level: int = 0,
        weapon_art: int = -1,
        wep_effect: int = -1,
        effect_tier: int = 0,
        magic_skill_1: int = -1,
        magic_skill_2: int = -1,
    ) -> bool:
        """Drops a weapon on the ground at the player's current position. Ported from the source
        script's dropItem(), scoped to weapons only - quantity is always 1 (the original's
        stack-size clamp only applies to its "Goods" item type, never reached here).

        -1 means "none" for weapon_art/wep_effect/magic_skill_1/2, matching the game's own
        sentinel convention. wep_effect's *tier* is capped automatically via
        game_data.EFFECT_CAP_MAP, the same way upgrade_level is capped against this specific
        weapon's own max reinforcement tier (see _clamp_upgrade_tier) - both mirror
        checkTier/getEffectCap in the source script exactly.

        One intentional deviation from the source script: it also writes -1 into weaponArt (or
        magicSkill_1/2) when magic_skill_1/2 look like a valid staff/seal skill and the weapon
        turns out not to be a casting weapon - but that write is unconditionally overwritten a
        few lines later by the same script's own final writeInteger(addr+4, weaponArt) /
        writeInteger(addr+0x14/0x18, magicSkill_1/2) calls, using the ORIGINAL, un-invalidated
        argument values. That branch is dead code in the source script (traced through, not
        assumed) - reproducing it here would add complexity with zero behavioral effect, so it's
        omitted rather than silently "fixed" into something the original script never actually
        did live.

        Returns False if the write path (TlsSetValue resolution, ItemData buffer) was
        transiently unavailable. Returns True only if the remote thread was dispatched and ran to
        completion - NOT that the drop is visually confirmed, same provisional-success caveat as
        NightreignMemoryWriter.set_event_flag.
        """
        if not self._ensure_drop_trampoline():
            return False

        cap = EFFECT_CAP_MAP.get(wep_effect)
        if cap is None:
            effect_tier = 0
        elif effect_tier != 0 and effect_tier > cap:
            effect_tier = cap
        resolved_wep_effect = wep_effect + effect_tier

        resolved_item_id = item_id + self._clamp_upgrade_tier(item_id, upgrade_level)

        try:
            self.pm.write_int(self._item_data_addr, resolved_item_id)
            self.pm.write_int(self._item_data_addr + 0x4, weapon_art)
            self.pm.write_int(self._item_data_addr + 0x8, resolved_wep_effect)
            self.pm.write_int(self._item_data_addr + 0x14, magic_skill_1)
            self.pm.write_int(self._item_data_addr + 0x18, magic_skill_2)
            self.pm.write_uchar(self._item_data_addr + 0x48, 1)
        except (pymem.exception.MemoryWriteError, pymem.exception.WinAPIError):
            return False

        self.pm.start_thread(self._drop_trampoline_addr)
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
