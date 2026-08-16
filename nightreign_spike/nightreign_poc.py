import csv
import ctypes
from ctypes import wintypes
import datetime
import os
import re
import struct
import sys
import time

TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]


kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32First.restype = wintypes.BOOL
kernel32.Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32Next.restype = wintypes.BOOL
kernel32.Module32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32)]
kernel32.Module32First.restype = wintypes.BOOL
kernel32.Module32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32)]
kernel32.Module32Next.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

EXE_NAME = "nightreign.exe"
AOB_PATTERN = "48 8B 05 ?? ?? ?? ?? 83 B8 ?? ?? ?? ?? 00 ?? ?? ?? ?? ?? ?? 48 8D 4C 24"
HUB_FLAG_OFFSET = 0xB40
NIGHTLORD_A_OFFSET = 0xB48
NIGHTLORD_B_OFFSET = 0xB4C
BOSS_ID_OFFSET = 0xB50

# Confirmed so far (Phase 0, see project memory) - fill in as new bosses are
# sampled. DLC Nightlord(s) not yet reachable/sampled.
KNOWN_BOSS_IDS = {
    2: "Tricephalos",
    12: "Gaping Jaw",
    22: "Sentient Pest",
    23: "Sentient Pest",
    32: "Augur",
    43: "Equilibrious Beast",
    53: "Darkdrift Night",
    61: "Fissure in the Fog",
    73: "Night Aspect",
}

# Same tolerance the eventual memory_reader.py match function will use -
# prototyped here first since it's cheap to validate against live drift data.
DRIFT_TOLERANCE = 3

# +0xB50 reads this sentinel when no boss is selected (hub/menu). With
# DRIFT_TOLERANCE=3 this sits right inside Tricephalos's (id=2) match
# window and gets misclassified as a Tricephalos win if not excluded first -
# found live while verifying the ported memory_reader.py against the game.
UNSET_SENTINEL = -1

UNKNOWN_BOSS_MESSAGE = (
    "boss_id {boss_id} not found - please report this to the mod owner "
    "with your Expedition's Nightlord"
)

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boss_id_log.csv")


def match_boss_id(boss_id, tolerance=DRIFT_TOLERANCE):
    """Return (status, detail) where status is 'matched', 'ambiguous', or 'unknown'.

    'matched' -> detail is the boss name.
    'ambiguous' -> detail is a sorted list of candidate names (ids too close together).
    'unknown' -> detail is None; caller should surface UNKNOWN_BOSS_MESSAGE.
    'unset' -> detail is None; no boss selected (hub/menu), not an error.
    """
    if boss_id == UNSET_SENTINEL:
        return "unset", None
    candidates = {name for known_id, name in KNOWN_BOSS_IDS.items() if abs(boss_id - known_id) <= tolerance}
    if len(candidates) == 1:
        return "matched", next(iter(candidates))
    if len(candidates) > 1:
        return "ambiguous", sorted(candidates)
    return "unknown", None


def guess_boss(boss_id):
    status, detail = match_boss_id(boss_id)
    if status == "matched":
        return detail
    if status == "ambiguous":
        return f"AMBIGUOUS between {detail} - tolerance too wide for this id"
    if status == "unset":
        return "unset (no boss selected - hub/menu)"
    return UNKNOWN_BOSS_MESSAGE.format(boss_id=boss_id)


def find_pid(exe_name):
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        raise OSError("CreateToolhelp32Snapshot (process) failed")
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    try:
        found = None
        if kernel32.Process32First(snapshot, ctypes.byref(entry)):
            while True:
                name = entry.szExeFile.decode(errors="ignore")
                if name.lower() == exe_name.lower():
                    found = entry.th32ProcessID
                    break
                if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                    break
        return found
    finally:
        kernel32.CloseHandle(snapshot)


def find_module(pid, module_name):
    snapshot = kernel32.CreateToolhelp32Snapshot(
        TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid
    )
    if snapshot == wintypes.HANDLE(-1).value:
        raise OSError("CreateToolhelp32Snapshot (module) failed - try running as the same elevation level as the game")
    entry = MODULEENTRY32()
    entry.dwSize = ctypes.sizeof(MODULEENTRY32)
    try:
        if kernel32.Module32First(snapshot, ctypes.byref(entry)):
            while True:
                name = entry.szModule.decode(errors="ignore")
                if name.lower() == module_name.lower():
                    base = ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value
                    return base, entry.modBaseSize
                if not kernel32.Module32Next(snapshot, ctypes.byref(entry)):
                    break
        return None
    finally:
        kernel32.CloseHandle(snapshot)


def read_bytes(h_process, address, size):
    buffer = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(
        h_process, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytes_read)
    )
    if not ok or bytes_read.value != size:
        raise OSError(
            f"ReadProcessMemory failed at {address:#x} (err={ctypes.get_last_error()})"
        )
    return buffer.raw


def aob_to_regex(pattern):
    parts = pattern.split()
    chunks = []
    for p in parts:
        if p in ("??", "?"):
            chunks.append(b".")
        else:
            chunks.append(re.escape(bytes.fromhex(p)))
    return re.compile(b"".join(chunks), re.DOTALL)


def main():
    pid = find_pid(EXE_NAME)
    if pid is None:
        print(f"Could not find a running process named {EXE_NAME}")
        sys.exit(1)
    print(f"Found {EXE_NAME} at PID {pid}")

    module = find_module(pid, EXE_NAME)
    if module is None:
        print(f"Could not find module {EXE_NAME} within its own process (unexpected)")
        sys.exit(1)
    module_base, module_size = module
    print(f"Module base: {module_base:#x}  size: {module_size:#x}")

    h_process = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid
    )
    if not h_process:
        print(f"OpenProcess failed (err={ctypes.get_last_error()})")
        sys.exit(1)

    try:
        module_bytes = read_bytes(h_process, module_base, module_size)

        regex = aob_to_regex(AOB_PATTERN)
        match = regex.search(module_bytes)
        if not match:
            print("AOB pattern not found in module - build/version likely changed")
            sys.exit(1)

        match_addr = module_base + match.start()
        disp = struct.unpack_from("<i", module_bytes, match.start() + 3)[0]
        pointer_slot = match_addr + 7 + disp
        print(f"AOB match at {match_addr:#x}, pointer slot at {pointer_slot:#x}")

        print("Polling GameMan-relative fields. Ctrl+C to stop.")
        print(f"Logging every sample to {LOG_PATH}\n")
        print(
            "Tip for Phase 0: select a boss, let the reading settle, and note which\n"
            "boss you selected next to the printed line (or in the CSV afterward) -\n"
            "repeat several times per boss, including relaunches, to bound drift.\n"
        )

        log_is_new = not os.path.exists(LOG_PATH)
        log_file = open(LOG_PATH, "a", newline="")
        writer = csv.writer(log_file)
        if log_is_new:
            writer.writerow(
                ["timestamp", "gameman_addr", "hub_flag", "nightlord_a", "nightlord_b", "boss_id", "boss_guess"]
            )

        last = None
        try:
            while True:
                gameman_addr = struct.unpack("<Q", read_bytes(h_process, pointer_slot, 8))[0]
                hub_flag = struct.unpack(
                    "<I", read_bytes(h_process, gameman_addr + HUB_FLAG_OFFSET, 4)
                )[0]
                nl_a = struct.unpack(
                    "<i", read_bytes(h_process, gameman_addr + NIGHTLORD_A_OFFSET, 4)
                )[0]
                nl_b = struct.unpack(
                    "<i", read_bytes(h_process, gameman_addr + NIGHTLORD_B_OFFSET, 4)
                )[0]
                boss_id = struct.unpack(
                    "<i", read_bytes(h_process, gameman_addr + BOSS_ID_OFFSET, 4)
                )[0]
                current = (gameman_addr, hub_flag, nl_a, nl_b, boss_id)

                now = datetime.datetime.now().isoformat(timespec="seconds")
                boss_guess = guess_boss(boss_id)
                writer.writerow([now, f"{gameman_addr:#x}", hub_flag, nl_a, nl_b, boss_id, boss_guess])
                log_file.flush()

                if current != last:
                    print(
                        f"[{now}] GameMan={gameman_addr:#x}  hub_flag={hub_flag:#x} ({hub_flag})  "
                        f"nightlord_a={nl_a}  nightlord_b={nl_b}  boss_id={boss_id}  ({boss_guess})"
                    )
                    last = current
                time.sleep(0.5)
        finally:
            log_file.close()
    finally:
        kernel32.CloseHandle(h_process)


if __name__ == "__main__":
    main()
