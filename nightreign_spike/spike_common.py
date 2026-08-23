"""Shared ctypes/AOB boilerplate for the nightreign_spike scripts (process/module
resolution, raw ReadProcessMemory, AOB-to-regex, and the `mov reg,[rip+disp32]`
pointer-slot math used by every AOB in this project). Factored out once a 6th
near-identical script (gamedataman_dump.py) would otherwise have copy-pasted this
a 4th time - see project memory for that note.
"""
import ctypes
from ctypes import wintypes
import re
import struct

TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

EXE_NAME = "nightreign.exe"

# Both AOBs resolved so far are the x64 `mov reg, [rip+disp32]` shape (7 bytes:
# opcode+modrm at [0:3), disp32 at [3:7)) - the pointer *slot* address is
# `match_addr + 7 + signed_disp32`, and that slot holds the live object address.
GAMEMAN_AOB = "48 8B 05 ?? ?? ?? ?? 83 B8 ?? ?? ?? ?? 00 ?? ?? ?? ?? ?? ?? 48 8D 4C 24"
GAMEDATAMAN_AOB = "48 8B 0D ?? ?? ?? ?? F3 48 0F 2C C0"

AOB_TARGETS = {
    "gameman": GAMEMAN_AOB,
    "gamedataman": GAMEDATAMAN_AOB,
}


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


def find_pid(exe_name=EXE_NAME):
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        raise OSError("CreateToolhelp32Snapshot (process) failed")
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    try:
        if kernel32.Process32First(snapshot, ctypes.byref(entry)):
            while True:
                name = entry.szExeFile.decode(errors="ignore")
                if name.lower() == exe_name.lower():
                    return entry.th32ProcessID
                if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                    break
        return None
    finally:
        kernel32.CloseHandle(snapshot)


def find_module(pid, module_name=EXE_NAME):
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
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
    ok = kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytes_read))
    if not ok or bytes_read.value != size:
        raise OSError(f"ReadProcessMemory failed at {address:#x} (err={ctypes.get_last_error()})")
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


def open_process(pid):
    h_process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h_process:
        raise OSError(f"OpenProcess failed (err={ctypes.get_last_error()})")
    return h_process


def resolve_pointer_slot(h_process, module_base, module_size, aob_pattern):
    """Return the pointer-slot address for a `mov reg,[rip+disp32]`-shaped AOB
    (module_base/module_size from find_module(); slot holds the live object addr,
    re-read on every access rather than cached, per every other reader in this repo)."""
    module_bytes = read_bytes(h_process, module_base, module_size)
    regex = aob_to_regex(aob_pattern)
    match = regex.search(module_bytes)
    if not match:
        raise LookupError("AOB pattern not found in module - build/version likely changed")
    match_addr = module_base + match.start()
    disp = struct.unpack_from("<i", module_bytes, match.start() + 3)[0]
    return match_addr + 7 + disp


def resolve_pid_module_slot(aob_pattern, exe_name=EXE_NAME):
    """Convenience wrapper: find the process/module and resolve a pointer slot in
    one call. Returns (h_process, pointer_slot). Caller owns closing h_process."""
    pid = find_pid(exe_name)
    if pid is None:
        raise LookupError(f"Could not find a running process named {exe_name}")
    module = find_module(pid, exe_name)
    if module is None:
        raise LookupError(f"Could not find module {exe_name} within its own process (unexpected)")
    module_base, module_size = module
    h_process = open_process(pid)
    try:
        pointer_slot = resolve_pointer_slot(h_process, module_base, module_size, aob_pattern)
    except Exception:
        kernel32.CloseHandle(h_process)
        raise
    return h_process, pointer_slot
