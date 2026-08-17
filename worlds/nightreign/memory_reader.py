"""Standalone Windows memory reader for Elden Ring Nightreign.

Deliberately free of any Archipelago/CommonClient imports so it can be
exercised on its own against the live game (see the __main__ block below),
independent of the rest of the world/client. This is a straight port of the
manual ctypes-based proof-of-concept in `nightreign_spike/nightreign_poc.py`
onto `pymem` (which the AP root `requirements.txt` already depends on for
other worlds), plus the additional offsets found after that PoC was written.

All offsets/AOBs below were live-tested against game build 1.03.3.0 and are
likely to drift on a game patch - see the "Nightreign AP project" notes for
the full history of how each one was found.
"""

from __future__ import annotations

import re
import struct
import time
from dataclasses import dataclass, field
from typing import Optional

import pymem
import pymem.exception
import pymem.pattern
import pymem.process

try:
    from .game_data import (
        CHARACTER_CLASS_NAMES,
        DRIFT_TOLERANCE,
        KNOWN_BOSS_IDS,
        UNSET_SENTINEL,
    )
except ImportError:
    # Run directly as a script (python memory_reader.py), not as part of the
    # worlds.nightreign package - `worlds/__init__.py` pulls in the entire AP
    # core (NetUtils, Utils, ...), which would defeat the point of this
    # module being independently testable. Fall back to a plain sys.path
    # import of the sibling module instead.
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from game_data import (  # type: ignore[no-redef]
        CHARACTER_CLASS_NAMES,
        DRIFT_TOLERANCE,
        KNOWN_BOSS_IDS,
        UNSET_SENTINEL,
    )

PROCESS_NAME = "nightreign.exe"

# From the CE table's "Baza" pointer registry. Both are the x64
# `mov reg, [rip+disp32]` shape: the pointer *slot* address is
# `match_addr + 7 + signed_disp32`, and that slot holds the live object
# address for the current process run (re-read it on every access rather
# than caching the dereferenced value - it can go transiently null during
# scene transitions).
GAMEMAN_AOB = "48 8B 05 ?? ?? ?? ?? 83 B8 ?? ?? ?? ?? 00 ?? ?? ?? ?? ?? ?? 48 8D 4C 24"
GAMEDATAMAN_AOB = "48 8B 0D ?? ?? ?? ?? F3 48 0F 2C C0"

# EventFlagBaseA / EventFlag - the boss-unlock write path (see memory_writer.py). From the CE
# table's "Hexinton Events" script, confirmed live: EventFlagBaseA(EventFlag_value, flag, on) sets
# the given EventFlag. Resolved lazily via resolve_event_flag_targets(), NOT inside connect()
# alongside GAMEMAN_AOB/GAMEDATAMAN_AOB - a future patch that only breaks these two AOBs must not
# take down the read-only tracker for players who never opted into write access.
EVENTFLAG_PTR_AOB = "48 8B 1D ?? ?? ?? ?? 49 8B F0 48 8B F9"
EVENTFLAG_BASE_A_AOB = "48 89 5C 24 08 44 8B 49 1C 44"

# GameMan-relative offsets.
HUB_FLAG_OFFSET = 0xB40          # bit 0x10000 set => not in an active run
BOSS_ID_OFFSET = 0xB50           # small clean int, +~10 per boss, drifts +/-3
OUTCOME_PULSE_OFFSET = 0xAF1     # byte; transient 0->1 pulse on a win only

# GameDataMan resolves to an object whose +0x8 qword is the player-data base;
# character class lives on that base, not on GameMan.
PLAYER_DATA_PTR_OFFSET = 0x8
CHARACTER_CLASS_OFFSET = 0xE8

UNKNOWN_BOSS_MESSAGE = (
    "boss_id {boss_id} not found - please report this to the mod owner "
    "with your Expedition's Nightlord"
)


@dataclass
class BossIdReading:
    """Result of a read_boss_id() call.

    status is one of:
      "matched"    - raw resolved to exactly one known boss.
      "ambiguous"  - raw is within tolerance of more than one known boss.
      "unknown"    - raw isn't within tolerance of any known boss.
      "unset"      - raw is the sentinel value read while no boss is
                     selected (hub/menu) - not an error, just not a win.
      "unreadable" - GameMan itself couldn't be resolved right now (e.g. a
                     scene transition) - not the same as a bad boss_id value.
    """

    raw: Optional[int]
    status: str
    name: Optional[str] = None
    candidates: list = field(default_factory=list)

    @property
    def message(self) -> Optional[str]:
        """Tester-facing message for the non-matched cases, else None."""
        if self.status == "unknown":
            return UNKNOWN_BOSS_MESSAGE.format(boss_id=self.raw)
        if self.status == "ambiguous":
            return (
                f"boss_id {self.raw} is ambiguous between {', '.join(self.candidates)} "
                f"- please report this to the mod owner with your Expedition's Nightlord"
            )
        return None


def match_boss_id(boss_id: int, tolerance: int = DRIFT_TOLERANCE) -> BossIdReading:
    if boss_id == UNSET_SENTINEL:
        return BossIdReading(raw=boss_id, status="unset")
    candidates = sorted({name for known_id, name in KNOWN_BOSS_IDS.items() if abs(boss_id - known_id) <= tolerance})
    if len(candidates) == 1:
        return BossIdReading(raw=boss_id, status="matched", name=candidates[0])
    if len(candidates) > 1:
        return BossIdReading(raw=boss_id, status="ambiguous", candidates=candidates)
    return BossIdReading(raw=boss_id, status="unknown")


def _aob_to_regex_bytes(pattern: str) -> bytes:
    chunks = []
    for part in pattern.split():
        if part in ("??", "?"):
            chunks.append(b".")
        else:
            chunks.append(re.escape(bytes.fromhex(part)))
    return b"".join(chunks)


class PointerNotFoundError(RuntimeError):
    """Raised when an AOB pattern can't be found - build/version likely changed."""


class NightreignMemoryReader:
    """Attaches to a running nightreign.exe and exposes read-only state.

    Usage: call connect() (returns False, not an exception, if the game
    isn't running yet - safe to poll in a reconnect loop), then use the
    read_*() methods. Every read_*() method returns None instead of raising
    if the underlying pointer chain is momentarily unreadable (e.g. a scene
    transition), matching the transient-null behavior already observed live
    against GameMan. If the process itself goes away, connected flips to
    False and the caller should go back to polling connect().
    """

    def __init__(self, process_name: str = PROCESS_NAME):
        self.process_name = process_name
        self.pm: Optional[pymem.Pymem] = None
        self._gameman_slot: Optional[int] = None
        self._gamedataman_slot: Optional[int] = None

    @property
    def connected(self) -> bool:
        return self.pm is not None

    def connect(self) -> bool:
        """Attach to the game process and resolve pointer slots.

        Returns True on success. Returns False if the process isn't running
        (a normal, expected state pre-launch - not an error). Raises
        PointerNotFoundError if the process is running but the known AOB
        patterns don't match, which most likely means the game updated and
        the offsets need to be re-derived.
        """
        try:
            pm = pymem.Pymem(self.process_name)
        except pymem.exception.ProcessNotFound:
            return False

        try:
            self._gameman_slot = self._resolve_pointer_slot(pm, GAMEMAN_AOB)
            self._gamedataman_slot = self._resolve_pointer_slot(pm, GAMEDATAMAN_AOB)
        except PointerNotFoundError:
            self.pm = None
            raise

        self.pm = pm
        return True

    def disconnect(self):
        self.pm = None
        self._gameman_slot = None
        self._gamedataman_slot = None

    def _resolve_pointer_slot(self, pm: pymem.Pymem, aob: str) -> int:
        pattern = _aob_to_regex_bytes(aob)
        module = pymem.process.module_from_name(pm.process_handle, self.process_name)
        # check_memory_protection=False: this game's code sections are
        # PAGE_EXECUTE_WRITECOPY (likely from the mod-loader/anti-tamper
        # wrapping - see project notes), which isn't in pymem's default
        # allowed-protections list. With the default it silently skips the
        # very pages containing our targets and returns None.
        match_addr = pymem.pattern.pattern_scan_module(
            pm.process_handle, module, pattern, check_memory_protection=False
        )
        if match_addr is None:
            raise PointerNotFoundError(f"AOB not found (build/version likely changed): {aob}")
        disp = struct.unpack("<i", pm.read_bytes(match_addr + 3, 4))[0]
        return match_addr + 7 + disp

    def _resolve_function_address(self, pm: pymem.Pymem, aob: str) -> int:
        """Like _resolve_pointer_slot, but for a code address the AOB scan itself already
        resolves (a callable entry point), not a data pointer slot that needs dereferencing."""
        pattern = _aob_to_regex_bytes(aob)
        module = pymem.process.module_from_name(pm.process_handle, self.process_name)
        match_addr = pymem.pattern.pattern_scan_module(
            pm.process_handle, module, pattern, check_memory_protection=False
        )
        if match_addr is None:
            raise PointerNotFoundError(f"AOB not found (build/version likely changed): {aob}")
        return match_addr

    def resolve_event_flag_targets(self) -> tuple[int, int]:
        """Resolves (eventflag_ptr_slot, eventflag_base_a_addr) for memory_writer.py's
        NightreignMemoryWriter. Call only when write access is actually wanted (see the AOB
        constants' comment above) - raises PointerNotFoundError if either AOB can't be found,
        same convention as connect()."""
        if not self.connected:
            raise PointerNotFoundError("not connected - call connect() first")
        ptr_slot = self._resolve_pointer_slot(self.pm, EVENTFLAG_PTR_AOB)
        base_a_addr = self._resolve_function_address(self.pm, EVENTFLAG_BASE_A_AOB)
        return ptr_slot, base_a_addr

    def _safe_read_qword(self, address: int) -> Optional[int]:
        try:
            return self.pm.read_ulonglong(address)
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            self.disconnect()
            return None

    def _safe_read_uint(self, address: int) -> Optional[int]:
        try:
            return self.pm.read_uint(address)
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            self.disconnect()
            return None

    def _safe_read_int(self, address: int) -> Optional[int]:
        try:
            return self.pm.read_int(address)
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            self.disconnect()
            return None

    def _safe_read_ubyte(self, address: int) -> Optional[int]:
        try:
            return self.pm.read_uchar(address)
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            self.disconnect()
            return None

    def _read_gameman_base(self) -> Optional[int]:
        if not self.connected:
            return None
        base = self._safe_read_qword(self._gameman_slot)
        return base or None  # null during scene transitions - not an error

    def _read_player_data_base(self) -> Optional[int]:
        if not self.connected:
            return None
        gamedataman_addr = self._safe_read_qword(self._gamedataman_slot)
        if not gamedataman_addr:
            return None
        player_data_base = self._safe_read_qword(gamedataman_addr + PLAYER_DATA_PTR_OFFSET)
        return player_data_base or None

    def read_character_class(self) -> Optional[int]:
        """Raw class id (see CHARACTER_CLASS_NAMES), or None if unreadable."""
        base = self._read_player_data_base()
        if base is None:
            return None
        return self._safe_read_uint(base + CHARACTER_CLASS_OFFSET)

    def read_character_class_name(self) -> Optional[str]:
        class_id = self.read_character_class()
        if class_id is None:
            return None
        return CHARACTER_CLASS_NAMES.get(class_id)

    def read_boss_id(self) -> BossIdReading:
        """Raw boss_id plus roster match, per the Phase 0 design decision:
        never silently guess - the client should surface `.message` to the
        tester whenever status isn't "matched"."""
        base = self._read_gameman_base()
        if base is None:
            return BossIdReading(raw=None, status="unreadable")
        raw = self._safe_read_int(base + BOSS_ID_OFFSET)
        if raw is None:
            return BossIdReading(raw=None, status="unreadable")
        return match_boss_id(raw)

    def read_hub_state(self) -> Optional[bool]:
        """True if in hub/menu/loading, False if in an active run, None if unreadable."""
        base = self._read_gameman_base()
        if base is None:
            return None
        flag = self._safe_read_uint(base + HUB_FLAG_OFFSET)
        if flag is None:
            return None
        return bool(flag & 0x10000)

    def read_outcome_pulse(self) -> Optional[int]:
        """Raw transient win-pulse byte (GameMan+0xAF1). 1 briefly on a win,
        0 otherwise/on a loss. Caller is responsible for edge-detecting the
        0->1 transition and debouncing - this just exposes the raw read."""
        base = self._read_gameman_base()
        if base is None:
            return None
        return self._safe_read_ubyte(base + OUTCOME_PULSE_OFFSET)


def _main():
    reader = NightreignMemoryReader()
    print(f"Waiting for {PROCESS_NAME}...")
    while not reader.connected:
        try:
            if reader.connect():
                print("Connected.")
            else:
                time.sleep(1)
        except PointerNotFoundError as exc:
            print(f"Fatal: {exc}")
            return

    last = None
    while True:
        if not reader.connected:
            print(f"Lost {PROCESS_NAME}, waiting to reconnect...")
            while not reader.connected:
                try:
                    if reader.connect():
                        print("Reconnected.")
                    else:
                        time.sleep(1)
                except PointerNotFoundError as exc:
                    print(f"Fatal: {exc}")
                    return

        char_id = reader.read_character_class()
        char_name = CHARACTER_CLASS_NAMES.get(char_id, f"unknown({char_id})") if char_id is not None else None
        boss = reader.read_boss_id()
        in_hub = reader.read_hub_state()
        pulse = reader.read_outcome_pulse()

        current = (char_id, boss.raw, boss.status, in_hub, pulse)
        if current != last:
            boss_desc = boss.name or boss.message or boss.status
            print(
                f"character={char_name}  boss_id={boss.raw} ({boss_desc})  "
                f"in_hub={in_hub}  outcome_pulse={pulse}"
            )
            last = current
        time.sleep(0.25)


if __name__ == "__main__":
    _main()
