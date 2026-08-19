"""External always-on-top overlay for Elden Ring Nightreign: boss-access gating display, a
run-state debug panel, and an item-drop toast.

v1 scope (see project plan): a simple always-visible panel listing which Nightlords aren't yet
AP-owned, shown whenever the game is in the hub. This exists because SetEventFlag(110, 1) reveals
all 6 secondary Nightlords in the game's own menu as one atomic batch (see memory_writer.py) - so
once any one Access item is owned, bosses the player hasn't actually received yet still show as
selectable in-game. This overlay is how the player tells the two apart, without needing a
menu-state-detection spike or per-row coordinate masking (deferred as a separate, time-boxed
stretch goal - see the project plan).

A second panel, bottom-right and only shown while in an active run, surfaces the raw win-detection
readings (boss_id, the boss that resolved to, detected character, and whether a win pulse is
currently being read) - added in response to reports of wins that didn't produce a check. This one
isn't gated on gate_boss_access: every player relies on win detection, not just those using boss
gating, so it's built and updated regardless of that option (see client.py's
_ensure_overlay_ready).

A third panel, center-top, briefly reads "Weapon received"/"Talisman received" whenever
randomize_weapons/randomize_talismans successfully lands a drop - client.py owns the ~3 second
timing (see _show_toast) and simply stops sending text once it's expired; this file just displays
whatever text it's handed.

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
    every tick, the same way the rest of this snapshot already is, means the overlay keeps
    following whatever process is actually live instead of silently hunting for a dead one
    forever.

    Carries three independent panels' worth of state: the locked-boss panel (visible/locked_names,
    gate_boss_access only), the run debug panel (in_run/boss_raw/boss_desc/character/win_pulse,
    always updated regardless of gate_boss_access - see client.py's _ensure_overlay_ready), and the
    center-top item-drop toast (toast_text - None when there's nothing to show; client.py owns the
    3-second timing and just stops passing text once it's expired, see poll_loop)."""

    def __init__(self, pid: int):
        self._lock = threading.Lock()
        self._visible = False
        self._locked_names: list[str] = []
        self._pid = pid
        self._in_run = False
        self._boss_raw: Optional[int] = None
        self._boss_desc: Optional[str] = None
        self._character: Optional[str] = None
        self._win_pulse = False
        self._toast_text: Optional[str] = None

    def update(
        self,
        visible: bool,
        locked_names: list[str],
        pid: int,
        in_run: bool,
        boss_raw: Optional[int],
        boss_desc: Optional[str],
        character: Optional[str],
        win_pulse: bool,
        toast_text: Optional[str],
    ) -> None:
        with self._lock:
            self._visible = visible
            self._locked_names = list(locked_names)
            self._pid = pid
            self._in_run = in_run
            self._boss_raw = boss_raw
            self._boss_desc = boss_desc
            self._character = character
            self._win_pulse = win_pulse
            self._toast_text = toast_text

    def snapshot(
        self,
    ) -> tuple[bool, list[str], int, bool, Optional[int], Optional[str], Optional[str], bool, Optional[str]]:
        with self._lock:
            return (
                self._visible,
                list(self._locked_names),
                self._pid,
                self._in_run,
                self._boss_raw,
                self._boss_desc,
                self._character,
                self._win_pulse,
                self._toast_text,
            )


class NightreignOverlay:
    """Owns the overlay window's dedicated Tk thread. Construct once the game's process id is
    known (see client.py's _ensure_overlay_ready); call start() once. Update what it shows (and
    which process it tracks) via .state.update(...) from any thread."""

    _BG = "#0a0a0a"  # chroma-keyed transparent background - anything drawn stays opaque
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
        # Placeholder geometry until the first _reposition() call - the window is resized to
        # match the game's full client area (not just a small panel) so the two panels below can
        # each be placed in their own corner independently.
        root.geometry("400x300+40+40")

        # Top-right: which Nightlords aren't yet AP-owned. Only populated/shown while
        # gate_boss_access is on for this slot (see client.py's poll_loop).
        locked_label = tk.Label(
            root,
            text="",
            fg="#ff5f5f",
            bg=self._BG,
            font=("Segoe UI", 11, "bold"),
            justify="left",
            anchor="ne",
        )
        locked_label.place(relx=1.0, rely=0.0, x=-self._INSET, y=self._INSET, anchor="ne")

        # Bottom-right: raw win-detection readings, shown while in an active run regardless of
        # gate_boss_access - added to diagnose reports of wins not producing a check.
        debug_label = tk.Label(
            root,
            text="",
            fg="#5fd75f",
            bg=self._BG,
            font=("Consolas", 10),
            justify="left",
            anchor="se",
        )
        debug_label.place(relx=1.0, rely=1.0, x=-self._INSET, y=-self._INSET, anchor="se")

        # Center-top: a brief "Weapon received"/"Talisman received" toast on a successful drop
        # (see client.py's _show_toast) - only up for TOAST_DURATION_SECONDS, timed on the
        # client.py/asyncio side, not here (see OverlayState's docstring).
        toast_label = tk.Label(
            root,
            text="",
            fg="#ffd75f",
            bg=self._BG,
            font=("Segoe UI", 13, "bold"),
            justify="center",
            anchor="n",
        )
        toast_label.place(relx=0.5, rely=0.0, y=self._INSET, anchor="n")

        self._make_click_through(root)
        self._tick(locked_label, debug_label, toast_label)
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

    @staticmethod
    def _debug_text(
        boss_raw: Optional[int], boss_desc: Optional[str], character: Optional[str], win_pulse: bool
    ) -> str:
        lines = [
            f"boss_id: {boss_raw if boss_raw is not None else 'unset'}",
            f"boss: {boss_desc or 'unknown'}",
            f"character: {character or 'unknown'}",
        ]
        # Hidden until an actual win pulse reads True, rather than always showing a "not
        # detected" line - the point is to catch the transient moment a reported miss happened,
        # not to add a permanently-on line no one needs to watch.
        if win_pulse:
            lines.append("WIN PULSE DETECTED")
        return "\n".join(lines)

    def _tick(self, locked_label: tk.Label, debug_label: tk.Label, toast_label: tk.Label) -> None:
        (visible, locked_names, pid, in_run, boss_raw, boss_desc, character, win_pulse,
         toast_text) = self.state.snapshot()
        game_hwnd = _find_window_for_pid(pid)
        # WS_EX_TOPMOST floats above every other window system-wide, not just the game - without
        # this check the panel would sit on top of the desktop, browser, IDE, etc. whenever
        # visible=True, not just the game. Only actually show it while the game is the foreground
        # (focused) window, the same way overlays like Discord's/Steam's scope themselves.
        is_game_foreground = game_hwnd is not None and user32.GetForegroundWindow() == game_hwnd

        show_locked = visible and locked_names and is_game_foreground
        show_debug = in_run and is_game_foreground
        show_toast = bool(toast_text) and is_game_foreground

        if show_locked or show_debug or show_toast:
            self._root.deiconify()
            self._reposition(game_hwnd)

            if show_locked:
                locked_label.place(relx=1.0, rely=0.0, x=-self._INSET, y=self._INSET, anchor="ne")
                locked_label.configure(text="Locked (not yet unlocked):\n" + "\n".join(f"- {n}" for n in locked_names))
            else:
                locked_label.place_forget()

            if show_debug:
                debug_label.place(relx=1.0, rely=1.0, x=-self._INSET, y=-self._INSET, anchor="se")
                debug_label.configure(text=self._debug_text(boss_raw, boss_desc, character, win_pulse))
            else:
                debug_label.place_forget()

            if show_toast:
                toast_label.place(relx=0.5, rely=0.0, y=self._INSET, anchor="n")
                toast_label.configure(text=toast_text)
            else:
                toast_label.place_forget()
        else:
            self._root.withdraw()
        self._root.after(250, self._tick, locked_label, debug_label, toast_label)

    def _reposition(self, game_hwnd: int) -> None:
        client_rect = _get_client_rect_on_screen(game_hwnd)
        if client_rect is None:
            return
        left, top, width, height = client_rect
        # The window now spans the game's whole client area (rather than a small corner-sized
        # panel) so the locked-boss panel (top-right) and the run debug panel (bottom-right) can
        # each be placed independently via place()'s relx/rely anchors.
        self._root.geometry(f"{width}x{height}+{left}+{top}")
