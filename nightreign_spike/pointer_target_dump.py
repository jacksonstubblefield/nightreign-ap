"""Dump the object a GameMan-relative pointer field points to, twice a few
seconds apart (same noise-filtering rationale as gameman_dump.py). Reuses the
AOB/process-resolution code from nightreign_poc.py.

Usage: python pointer_target_dump.py <label> [pointer_offset_hex] [dump_size_hex]
Defaults: pointer_offset=0xd98, dump_size=0x400
Writes dumps/<label>_ptrtarget_1.bin and _2.bin.
"""
import ctypes
from ctypes import wintypes
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
GAP_SECONDS = 3

DUMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dumps")


def find_pid(exe_name):
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
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


def find_module(pid, module_name):
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
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


def main():
    if len(sys.argv) < 2:
        print("Usage: python pointer_target_dump.py <label> [pointer_offset_hex] [dump_size_hex]")
        sys.exit(1)
    label = sys.argv[1]
    pointer_offset = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0xD98
    dump_size = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x400

    pid = find_pid(EXE_NAME)
    if pid is None:
        print(f"Could not find a running process named {EXE_NAME}")
        sys.exit(1)

    module_base, module_size = find_module(pid, EXE_NAME)
    h_process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
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

        os.makedirs(DUMP_DIR, exist_ok=True)

        for i in (1, 2):
            gameman_addr = struct.unpack("<Q", read_bytes(h_process, pointer_slot, 8))[0]
            if not gameman_addr:
                print(f"Dump {i}: GameMan pointer is currently null - aborting")
                sys.exit(1)
            target_addr = struct.unpack(
                "<Q", read_bytes(h_process, gameman_addr + pointer_offset, 8)
            )[0]
            if not target_addr:
                print(f"Dump {i}: target pointer at GameMan+{pointer_offset:#x} is null - aborting")
                sys.exit(1)
            blob = read_bytes(h_process, target_addr, dump_size)
            out_path = os.path.join(DUMP_DIR, f"{label}_ptrtarget_{i}.bin")
            with open(out_path, "wb") as f:
                f.write(blob)
            print(
                f"Dump {i}: GameMan={gameman_addr:#x}  target={target_addr:#x} "
                f"-> {out_path} ({len(blob)} bytes)"
            )
            if i == 1:
                time.sleep(GAP_SECONDS)
    finally:
        kernel32.CloseHandle(h_process)


if __name__ == "__main__":
    main()
