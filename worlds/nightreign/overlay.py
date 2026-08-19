"""External always-on-top sidebar overlay for Elden Ring Nightreign boss-access gating.

v1 scope (see project plan): a simple always-visible panel listing which Nightlords aren't yet
AP-owned, shown whenever the game is in the hub. This exists because SetEventFlag(110, 1) reveals
all 6 secondary Nightlords in the game's own menu as one atomic batch (see memory_writer.py) - so
once any one Access item is owned, bosses the player hasn't actually received yet still show as
selectable in-game. This overlay is how the player tells the two apart, without needing a
menu-state-detection spike or per-row coordinate masking (deferred as a separate, time-boxed
stretch goal - see the project plan).

A second, independent small window sits at the bottom-right corner and shows the raw win-detection
reads (boss_id, the boss it resolved to, detected character) - added to help diagnose reports of
wins that didn't produce a check, and shown in both the hub and an active Expedition (not just the
latter) since a character-recognition bug tied to cosmetic skins turned out to need comparing
readings on both sides of that boundary. It's a separate fixed-size Toplevel rather than a second
mode of the locked-boss panel above because the two aren't mutually exclusive - both can be true
at once in the hub (locked Nightlords top-right, boss/character bottom-right) - so each needs its
own window rather than sharing one label. A full-client-area single window that tried to host both
corners at once was attempted and reverted (see project history) after it broke mouse input in the
game entirely; every panel here stays a small, fixed-size window that only ever moves, never
resizes to cover more of the screen, to sidestep that class of bug rather than re-fixing it.

A third, independent small window shows a brief "Weapon received"/"Talisman received" toast,
center-top, on a successful randomize_weapons/randomize_talismans drop (see client.py's
_show_toast). Same reasoning as the debug panel above: it isn't mutually exclusive with the other
two (a drop can land while both other panels are already showing), so it gets its own window too.

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
    whatever process is actually live instead of silently hunting for a dead one forever.

    Also carries the boss/character debug reads (boss_raw/boss_desc/character) for the second
    panel - shown in both the hub and an Expedition, see the module docstring - and toast_text for
    the independent item-drop toast (None when there's nothing to show; client.py owns the ~3
    second timing and just stops passing text once it's expired, see poll_loop/_show_toast)."""

    def __init__(self, pid: int):
        self._lock = threading.Lock()
        self._visible = False
        self._locked_names: list[str] = []
        self._pid = pid
        self._boss_raw: Optional[int] = None
        self._boss_desc: Optional[str] = None
        self._character: Optional[str] = None
        self._toast_text: Optional[str] = None

    def update(
        self,
        visible: bool,
        locked_names: list[str],
        pid: int,
        boss_raw: Optional[int],
        boss_desc: Optional[str],
        character: Optional[str],
        toast_text: Optional[str],
    ) -> None:
        with self._lock:
            self._visible = visible
            self._locked_names = list(locked_names)
            self._pid = pid
            self._boss_raw = boss_raw
            self._boss_desc = boss_desc
            self._character = character
            self._toast_text = toast_text

    def snapshot(
        self,
    ) -> tuple[bool, list[str], int, Optional[int], Optional[str], Optional[str], Optional[str]]:
        with self._lock:
            return (
                self._visible,
                list(self._locked_names),
                self._pid,
                self._boss_raw,
                self._boss_desc,
                self._character,
                self._toast_text,
            )


class NightreignOverlay:
    """Owns the overlay windows' dedicated Tk thread. Construct once the game's process id is
    known (see client.py's _ensure_overlay_ready - not gated on gate_boss_access, since the
    boss/character debug panel and item-drop toast are useful regardless of that option); call
    start() once. Update what it shows (and which process it tracks) via .state.update(...) from
    any thread."""

    _BG = "#0a0a0a"  # chroma-keyed transparent background - anything drawn stays opaque
    _PANEL_WIDTH = 280
    _PANEL_HEIGHT = 220
    _TOAST_WIDTH = 280
    _TOAST_HEIGHT = 40
    _INSET = 20

    def __init__(self, pid: int):
        self.state = OverlayState(pid)
        self._thread: Optional[threading.Thread] = None
        self._root: Optional[tk.Tk] = None
        self._debug_root: Optional[tk.Toplevel] = None
        self._toast_root: Optional[tk.Toplevel] = None

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

        # Independent Toplevel, not a second mode of the panel above - see the module docstring
        # for why (it isn't mutually exclusive with the locked-boss panel).
        debug_root = tk.Toplevel(root)
        self._debug_root = debug_root
        debug_root.overrideredirect(True)
        debug_root.attributes("-topmost", True)
        debug_root.configure(bg=self._BG)
        debug_root.attributes("-transparentcolor", self._BG)
        debug_root.geometry(f"{self._PANEL_WIDTH}x{self._PANEL_HEIGHT}+40+40")

        debug_label = tk.Label(
            debug_root,
            text="",
            fg="#5fd7ff",
            bg=self._BG,
            font=("Consolas", 10),
            justify="left",
            anchor="nw",
        )
        debug_label.pack(fill="both", expand=True, padx=8, pady=8)

        self._make_click_through(debug_root)

        # Independent Toplevel too, for the same reason - see the module docstring.
        toast_root = tk.Toplevel(root)
        self._toast_root = toast_root
        toast_root.overrideredirect(True)
        toast_root.attributes("-topmost", True)
        toast_root.configure(bg=self._BG)
        toast_root.attributes("-transparentcolor", self._BG)
        toast_root.geometry(f"{self._TOAST_WIDTH}x{self._TOAST_HEIGHT}+40+40")

        toast_label = tk.Label(
            toast_root,
            text="",
            fg="#ffd75f",
            bg=self._BG,
            font=("Segoe UI", 13, "bold"),
            justify="center",
        )
        toast_label.pack(fill="both", expand=True)

        self._make_click_through(toast_root)

        self._tick(label, debug_label, toast_label)
        root.mainloop()

    def _make_click_through(self, root: tk.Misc) -> None:
        root.update_idletasks()
        hwnd = root.winfo_id()
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)
        # Changing the ex-style on an already-layered window resets the color-key transparency
        # tkinter's own -transparentcolor set up (a Windows quirk - restyling a layered window
        # invalidates its previous SetLayeredWindowAttributes call) - reapply it here, or the
        # window renders as a solid opaque block instead of chroma-keyed transparent.
        user32.SetLayeredWindowAttributes(hwnd, _colorref(self._BG), 0, LWA_COLORKEY)

    @staticmethod
    def _debug_text(boss_raw: Optional[int], boss_desc: Optional[str], character: Optional[str]) -> str:
        return (
            f"boss_id: {boss_raw if boss_raw is not None else 'unset'}\n"
            f"boss: {boss_desc or 'unknown'}\n"
            f"character: {character or 'unknown'}"
        )

    def _tick(self, label: tk.Label, debug_label: tk.Label, toast_label: tk.Label) -> None:
        (visible, locked_names, pid, boss_raw, boss_desc, character,
         toast_text) = self.state.snapshot()
        game_hwnd = _find_window_for_pid(pid)
        # WS_EX_TOPMOST floats above every other window system-wide, not just the game - without
        # this check the panel would sit on top of the desktop, browser, IDE, etc. whenever
        # visible=True, not just the game. Only actually show it while the game is the foreground
        # (focused) window, the same way overlays like Discord's/Steam's scope themselves.
        is_game_foreground = game_hwnd is not None and user32.GetForegroundWindow() == game_hwnd

        show_locked = visible and locked_names and is_game_foreground
        # Shown in both the hub and an Expedition (not gated on run state) - see the module
        # docstring for why.
        show_debug = is_game_foreground
        show_toast = bool(toast_text) and is_game_foreground

        if show_locked:
            self._root.deiconify()
            label.configure(text="Locked (not yet unlocked):\n" + "\n".join(f"- {n}" for n in locked_names))
            self._reposition(self._root, game_hwnd, self._PANEL_WIDTH, self._PANEL_HEIGHT, corner="top-right")
        else:
            self._root.withdraw()

        if show_debug:
            self._debug_root.deiconify()
            debug_label.configure(text=self._debug_text(boss_raw, boss_desc, character))
            self._reposition(
                self._debug_root, game_hwnd, self._PANEL_WIDTH, self._PANEL_HEIGHT, corner="bottom-right"
            )
        else:
            self._debug_root.withdraw()

        if show_toast:
            self._toast_root.deiconify()
            toast_label.configure(text=toast_text)
            self._reposition(self._toast_root, game_hwnd, self._TOAST_WIDTH, self._TOAST_HEIGHT, corner="top-center")
        else:
            self._toast_root.withdraw()

        self._root.after(250, self._tick, label, debug_label, toast_label)

    @staticmethod
    def _reposition(window: tk.Misc, game_hwnd: int, panel_width: int, panel_height: int, corner: str) -> None:
        client_rect = _get_client_rect_on_screen(game_hwnd)
        if client_rect is None:
            return
        left, top, width, height = client_rect
        # Anchored to a fixed corner (or top-center, for the toast) of the game window with a
        # fixed inset - v1 doesn't track the native Expeditions list's own position (that's the
        # deferred row-masking stretch goal). Right-hand corners read less jarring than left,
        # which tends to sit over other UI. Every panel is a fixed size (see the module
        # docstring) - this only ever moves a window, never resizes one.
        inset = NightreignOverlay._INSET
        if corner == "top-right":
            x, y = left + width - panel_width - inset, top + inset
        elif corner == "bottom-right":
            x, y = left + width - panel_width - inset, top + height - panel_height - inset
        else:  # top-center
            x, y = left + (width - panel_width) // 2, top + inset
        window.geometry(f"+{x}+{y}")
