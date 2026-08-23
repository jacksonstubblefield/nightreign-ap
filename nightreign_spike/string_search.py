"""Search nightreign.exe's loaded module memory for ASCII/UTF-16LE strings
matching given keywords - a starting anchor for tracing Everdark-related code
via disassembly, rather than guessing at byte offsets blind. Reuses the
process/module resolution from nightreign_poc.py.

Usage: python string_search.py <keyword> [<keyword> ...]
"""
import ctypes
from ctypes import wintypes
import re
import sys

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


def main():
    if len(sys.argv) < 2:
        print("Usage: python string_search.py <keyword> [<keyword> ...]")
        sys.exit(1)
    keywords = sys.argv[1:]

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
        print(f"Reading module ({module_size:#x} bytes)...")
        module_bytes = read_bytes(h_process, module_base, module_size)

        for kw in keywords:
            print(f"\n=== '{kw}' ===")
            found_any = False

            ascii_pattern = re.compile(kw.encode("ascii"), re.IGNORECASE)
            for m in ascii_pattern.finditer(module_bytes):
                start = max(0, m.start() - 8)
                end = min(len(module_bytes), m.end() + 40)
                context = module_bytes[start:end]
                printable = re.sub(rb"[^\x20-\x7e]", b".", context).decode("ascii")
                addr = module_base + m.start()
                print(f"  ASCII  {addr:#x}: {printable}")
                found_any = True

            utf16_kw = kw.encode("utf-16-le")
            utf16_pattern = re.compile(re.escape(utf16_kw), re.IGNORECASE)
            for m in utf16_pattern.finditer(module_bytes):
                start = max(0, m.start() - 16)
                end = min(len(module_bytes), m.end() + 80)
                context = module_bytes[start:end]
                try:
                    text = context.decode("utf-16-le", errors="replace")
                except Exception:
                    text = repr(context)
                text = re.sub(r"[^\x20-\x7e]", ".", text)
                addr = module_base + m.start()
                print(f"  UTF16  {addr:#x}: {text}")
                found_any = True

            if not found_any:
                print("  (no matches)")
    finally:
        kernel32.CloseHandle(h_process)


if __name__ == "__main__":
    main()
