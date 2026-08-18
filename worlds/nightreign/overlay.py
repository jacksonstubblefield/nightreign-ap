"""External always-on-top sidebar overlay for Elden Ring Nightreign boss-access gating.

v1 scope (see project plan): a simple always-visible panel listing which Nightlords aren't yet
AP-owned, shown whenever the game is in the hub. This exists because SetEventFlag(110, 1) reveals
all 6 secondary Nightlords in the game's own menu as one atomic batch (see memory_writer.py) - so
once any one Access item is owned, bosses the player hasn't actually received yet still show as
selectable in-game. This overlay is how the player tells the two apart, without needing a
menu-state-detection spike or per-row coordinate masking (deferred as a separate, time-boxed
stretch goal - see the project plan).

Draws an external transparent window on top of the game (chroma-key transparency via tkinter's
-transparentcolor, Windows-only) rather than hooking the game's own DirectX render pipeline -
modeled on a real precedent for this game, NightreignArmamentHelper. That tool uses OCR to avoid
touching game memory, for EAC safety in online play; this project doesn't have that constraint
(offline-only), so state is driven directly by AP's received-items tracking instead.

Runs its own Tk mainloop on a dedicated daemon thread - client.py's asyncio loop already drives
Kivy's async_run() for the stock GameManager window, and Tk's mainloop is blocking and not
asyncio-aware, so it can't share that loop the way Kivy does. State crosses the thread boundary
through OverlayState, a small lock-guarded last-write-wins snapshot - no queue/history needed,
only the latest state ever matters (same convention memory_reader.py uses for transient reads).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import threading
import tkinter as tk
from typing import Optional

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080  # keep it off the taskbar/alt-tab list
LWA_COLORKEY = 0x00000001

user32 = ctypes.windll.user32


def _colorref(hex_color: str) -> int:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return r | (g << 8) | (b << 16)

_EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


def _find_window_for_pid(pid: int) -> Optional[int]:
    """First top-level, visible window belonging to the given process id. PID-matched rather than
    title-matched, since nightreign.exe's window title isn't confirmed stable/non-blank."""
    found: list[int] = []

    def _callback(hwnd, _lparam):
        window_pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
            return False  # stop enumerating
        return True

    user32.EnumWindows(_EnumWindowsProc(_callback), 0)
    return found[0] if found else None


def _get_client_rect_on_screen(hwnd: int) -> Optional[tuple[int, int, int, int]]:
    """(left, top, width, height) of hwnd's client area, in screen coordinates."""
    rect = ctypes.wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    top_left = ctypes.wintypes.POINT(rect.left, rect.top)
    if not user32.ClientToScreen(hwnd, ctypes.byref(top_left)):
        return None
    return top_left.x, top_left.y, rect.right - rect.left, rect.bottom - rect.top


class OverlayState:
    """Thread-safe last-write-wins snapshot: written from client.py's asyncio side on every poll
    tick, read from the Tk thread's own periodic tick. No history - only the latest matters.

    pid is included here (not just set once at construction) because the game process can restart
    mid-session - the reader reconnects to a new pid, but client.py never tears down/rebuilds an
    already-running overlay (see the `self.overlay is None` guard in poll_loop). Refreshing pid on
    every tick, the same way visible/locked_names already are, means the overlay keeps following
    whatever process is actually live instead of silently hunting for a dead one forever."""

    def __init__(self, pid: int):
        self._lock = threading.Lock()
        self._visible = False
        self._locked_names: list[str] = []
        self._pid = pid

    def update(self, visible: bool, locked_names: list[str], pid: int) -> None:
        with self._lock:
            self._visible = visible
            self._locked_names = list(locked_names)
            self._pid = pid

    def snapshot(self) -> tuple[bool, list[str], int]:
        with self._lock:
            return self._visible, list(self._locked_names), self._pid


class NightreignOverlay:
    """Owns the overlay window's dedicated Tk thread. Construct once the game's process id is
    known and gate_boss_access is confirmed true; call start() once. Update what it shows (and
    which process it tracks) via .state.update(...) from any thread."""

    _BG = "#0a0a0a"  # chroma-keyed transparent background - anything drawn stays opaque
    _PANEL_WIDTH = 280
    _PANEL_HEIGHT = 220
    _INSET = 20

    def __init__(self, pid: int):
        self.state = OverlayState(pid)
        self._thread: Optional[threading.Thread] = None
        self._root: Optional[tk.Tk] = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="NightreignOverlay", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        root = tk.Tk()
        self._root = root
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=self._BG)
        root.attributes("-transparentcolor", self._BG)
        root.geometry(f"{self._PANEL_WIDTH}x{self._PANEL_HEIGHT}+40+40")

        label = tk.Label(
            root,
            text="",
            fg="#ff5f5f",
            bg=self._BG,
            font=("Segoe UI", 11, "bold"),
            justify="left",
            anchor="nw",
        )
        label.pack(fill="both", expand=True, padx=8, pady=8)

        self._make_click_through(root)
        self._tick(label)
        root.mainloop()

    def _make_click_through(self, root: tk.Tk) -> None:
        root.update_idletasks()
        hwnd = root.winfo_id()
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)
        # Changing the ex-style on an already-layered window resets the color-key transparency
        # tkinter's own -transparentcolor set up (a Windows quirk - restyling a layered window
        # invalidates its previous SetLayeredWindowAttributes call) - reapply it here, or the
        # window renders as a solid opaque block instead of chroma-keyed transparent.
        user32.SetLayeredWindowAttributes(hwnd, _colorref(self._BG), 0, LWA_COLORKEY)

    def _tick(self, label: tk.Label) -> None:
        visible, locked_names, pid = self.state.snapshot()
        game_hwnd = _find_window_for_pid(pid)
        # WS_EX_TOPMOST floats above every other window system-wide, not just the game - without
        # this check the panel would sit on top of the desktop, browser, IDE, etc. whenever
        # visible=True, not just the game. Only actually show it while the game is the foreground
        # (focused) window, the same way overlays like Discord's/Steam's scope themselves.
        is_game_foreground = game_hwnd is not None and user32.GetForegroundWindow() == game_hwnd
        if visible and locked_names and is_game_foreground:
            self._root.deiconify()
            label.configure(text="Locked (not yet unlocked):\n" + "\n".join(f"- {n}" for n in locked_names))
            self._reposition(game_hwnd)
        else:
            self._root.withdraw()
        self._root.after(250, self._tick, label)

    def _reposition(self, game_hwnd: int) -> None:
        client_rect = _get_client_rect_on_screen(game_hwnd)
        if client_rect is None:
            return
        left, top, width, _height = client_rect
        # Anchored to the game window's top-right corner with a fixed inset - v1 doesn't track
        # the native Expeditions list's own position (that's the deferred row-masking stretch
        # goal). Top-right reads less jarring than top-left, which tends to sit over other UI.
        x = left + width - self._PANEL_WIDTH - self._INSET
        y = top + self._INSET
        self._root.geometry(f"+{x}+{y}")
