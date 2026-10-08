"""DeathLink spike: watch the LOCAL player through downed / revived / fully-dead transitions, and
test the two candidate "receive a DeathLink" writes.

Chains ported from the user's CE table (Nightreign_w_apvalues.CT, Host class + "Kill Player
Instantly" script):
    PlayerIns = [[WorldChrMan] + 0x174E8]          (CE symbol XA)
    hp_base   = [[PlayerIns + 0x1B8] + 0x00]
    hp        = [hp_base + 0x140]   maxhp = [hp_base + 0x144]   (int32)
    [hp_base + 0x189] bit 2 = the table's "Set No Dead" flag
    anim      = [[[PlayerIns + 0x1B8] + 0x80] + 0x98]  (same read the client already uses)
The CE "Auto Revive" script treats hp == 0 as "downed" (revives by restoring HP + zeroing
[[PlayerIns+0x1B8]+0x58]+0x18), so hp alone probably can't tell downed from fully dead - the
point of this spike is finding what can.

Modes:
  watch  Polls fast, prints every HP / animation / hub / day-phase change, and records a raw
         snapshot of PlayerIns[0:SIZE] + hp_base[0:SIZE] every tick to a .bin file so offsets can
         be correlated with downed/dead across the FULL timeline afterward (not just the death
         tick - see roadmap memory for why). Press F8 in-game to drop a MARK into both logs.
  down   Writes hp = 0 once (candidate receive path #1).
  kill   Calls the table's deathCall function on PlayerIns via a remote thread (candidate
         receive path #2) - same as CE's "Kill Player Instantly".
  down/kill take --delay N to give you time to alt-tab back into the game first.

Usage: py -3.12 -u player_down_watch.py watch [--interval 0.05]
       py -3.12 player_down_watch.py down --delay 5
       py -3.12 player_down_watch.py down --delay 10 --toast "DeathLink: Alex died"
       py -3.12 player_down_watch.py toast "DeathLink: Alex died"   (look only, no HP write)
       py -3.12 player_down_watch.py kill --delay 5
"""
import argparse
import ctypes
import os
import struct
import sys
import time

import pymem
import pymem.process

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "worlds", "nightreign"))
from memory_reader import NightreignMemoryReader  # noqa: E402
from overlay import NightreignOverlay, _get_client_rect_on_screen  # noqa: E402
from popup_trigger import _resolve_function_address  # noqa: E402

PLAYER_INS_OFFSET = 0x174E8
HP_MODULE_OFFSET = 0x1B8
HP_OFFSET = 0x140
MAXHP_OFFSET = 0x144
NO_DEAD_FLAG_OFFSET = 0x189

DEATH_CALL_AOB = ("40 53 48 83 ec 20 48 8b d9 e8 ?? ?? ?? ?? 80 a3 f4 01 00 00 fd b2 01 48 8b cb "
                  "48 83 c4 20")

# rcx already holds PlayerIns (start_thread's lpParameter), so just call through.
_KILL_PREFIX = bytes.fromhex(
    "4883EC28"      # sub rsp, 0x28
    "48B8"          # movabs rax, <death_call_addr>
)
_KILL_SUFFIX = bytes.fromhex(
    "FFD0"          # call rax
    "4883C428"      # add rsp, 0x28
    "31C0"          # xor eax, eax
    "C3"            # ret
)

PLAYER_INS_SNAPSHOT = 0x800
HP_BASE_SNAPSHOT = 0x400
# Per-tick record: time (double), mark (u8), hub (i8, -1 = unreadable), phase (i16), anim (i32),
# hp (i32), maxhp (i32), then the two blobs (zero-filled if unreadable).
RECORD_HEADER = struct.Struct("<dBbhiii")

VK_F8 = 0x77
user32 = ctypes.WinDLL("user32")


class Player:
    def __init__(self):
        self.reader = NightreignMemoryReader()
        if not self.reader.connect():
            sys.exit("nightreign.exe isn't running")
        self.pm = self.reader.pm
        self.wcm_slot = self.reader.resolve_current_animation_target()

    def player_ins(self):
        try:
            wcm = self.pm.read_ulonglong(self.wcm_slot)
            return self.pm.read_ulonglong(wcm + PLAYER_INS_OFFSET) if wcm else None
        except Exception:
            return None

    def hp_base(self, player_ins):
        try:
            module = self.pm.read_ulonglong(player_ins + HP_MODULE_OFFSET)
            return self.pm.read_ulonglong(module) if module else None
        except Exception:
            return None


def read_blob(pm, address, size):
    if not address:
        return bytes(size)
    try:
        return pm.read_bytes(address, size)
    except Exception:
        return bytes(size)


def watch(args):
    player = Player()
    pm = player.pm
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(os.path.dirname(__file__), "dumps")
    os.makedirs(out_dir, exist_ok=True)
    bin_path = os.path.join(out_dir, f"player_down_{stamp}.bin")
    log_path = os.path.join(out_dir, f"player_down_{stamp}.log")
    print(f"Recording to {bin_path}\n         and {log_path}\nF8 = mark, Ctrl+C = stop.")

    with open(bin_path, "wb") as bin_file, open(log_path, "w", encoding="utf-8") as log_file:
        bin_file.write(struct.pack("<II", PLAYER_INS_SNAPSHOT, HP_BASE_SNAPSHOT))
        start = time.time()

        def log(text):
            line = f"[{time.strftime('%H:%M:%S')} +{time.time() - start:8.2f}s] {text}"
            print(line)
            log_file.write(line + "\n")
            log_file.flush()

        last = {}
        f8_was_down = False
        try:
            while True:
                now = time.time()
                f8_down = bool(user32.GetAsyncKeyState(VK_F8) & 0x8000)
                mark = f8_down and not f8_was_down
                f8_was_down = f8_down

                hub = player.reader.read_hub_state()
                phase = player.reader.read_day_phase()
                anim = player.reader.read_current_animation(player.wcm_slot)
                ins = player.player_ins()
                hp_base = player.hp_base(ins) if ins else None
                ins_blob = read_blob(pm, ins, PLAYER_INS_SNAPSHOT)
                hp_blob = read_blob(pm, hp_base, HP_BASE_SNAPSHOT)
                hp = maxhp = None
                if hp_base:
                    hp, maxhp = struct.unpack_from("<ii", hp_blob, HP_OFFSET)
                no_dead = hp_blob[NO_DEAD_FLAG_OFFSET] if hp_base else None

                bin_file.write(RECORD_HEADER.pack(
                    now, int(mark), -1 if hub is None else int(hub),
                    -1 if phase is None else phase, -1 if anim is None else anim,
                    -1 if hp is None else hp, -1 if maxhp is None else maxhp))
                bin_file.write(ins_blob)
                bin_file.write(hp_blob)

                if mark:
                    log(f"===== MARK =====  hp={hp}/{maxhp} anim={anim}")
                current = {"hub": hub, "phase": phase, "ins": ins, "no_dead": no_dead}
                for key, value in current.items():
                    if last.get(key, "unset") != value:
                        shown = f"{value:#x}" if key == "ins" and value else value
                        log(f"{key} -> {shown}")
                if hp != last.get("hp", "unset"):
                    prev = last.get("hp")
                    note = ""
                    if prev not in (None, "unset") and hp is not None:
                        if prev > 0 and hp <= 0:
                            note = "   <<< HP HIT 0"
                        elif prev <= 0 < hp:
                            note = "   >>> HP BACK ABOVE 0"
                    log(f"hp {prev} -> {hp} / {maxhp}{note}")
                if anim != last.get("anim", "unset"):
                    log(f"anim {last.get('anim')} -> {anim}")
                current.update(hp=hp, anim=anim)
                last = current

                time.sleep(max(0.0, args.interval - (time.time() - now)))
        except KeyboardInterrupt:
            log("stopped")


def countdown(delay):
    for remaining in range(delay, 0, -1):
        print(f"  firing in {remaining}...")
        time.sleep(1)


class DeathLinkOverlay(NightreignOverlay):
    """Mock-up of the planned DeathLink toast: the production overlay's toast, but red on a solid
    dark panel (the chroma-keyed window can't do partial alpha), sized to its text, and pushed
    down from the top edge so it clears the compass. Hides the debug panel - not part of the mock."""
    TOAST_FG = "#ff6b6b"
    TOAST_BG = "#1a0c0c"
    TOAST_BORDER = "#b03030"

    def __init__(self, pid, y_fraction):
        super().__init__(pid)
        self._y_fraction = y_fraction

    def _tick(self, debug_label, toast_label):
        toast_label.configure(fg=self.TOAST_FG, bg=self.TOAST_BG, padx=18, pady=8,
                              highlightthickness=2, highlightbackground=self.TOAST_BORDER,
                              highlightcolor=self.TOAST_BORDER)
        toast_label.pack_configure(fill="none", expand=False)
        super()._tick(debug_label, toast_label)
        self._debug_root.withdraw()

    def _reposition(self, window, game_hwnd, panel_width, panel_height, corner):
        if corner != "top-center":
            return NightreignOverlay._reposition(window, game_hwnd, panel_width, panel_height, corner)
        rect = _get_client_rect_on_screen(game_hwnd)
        if rect is None:
            return
        left, top, width, height = rect
        label = window.winfo_children()[0]
        w, h = label.winfo_reqwidth(), label.winfo_reqheight()
        x = left + (width - w) // 2
        y = top + int(height * self._y_fraction)
        window.geometry(f"{w}x{h}+{x}+{y}")


def show_toast(player, text, y_fraction):
    overlay = DeathLinkOverlay(player.pm.process_id, y_fraction)
    overlay.start()
    overlay.state.update(player.pm.process_id, None, None, None, None, text)
    return overlay


def toast(args):
    player = Player()
    countdown(args.delay)
    show_toast(player, args.text, args.toast_y)
    print(f"showing toast for {args.toast_seconds}s")
    time.sleep(args.toast_seconds)


def down(args):
    player = Player()
    countdown(args.delay)
    overlay = show_toast(player, args.toast, args.toast_y) if args.toast else None
    ins = player.player_ins()
    hp_base = player.hp_base(ins) if ins else None
    if not hp_base:
        sys.exit("PlayerIns / HP module unreadable - are you in an expedition?")
    before = player.pm.read_int(hp_base + HP_OFFSET)
    player.pm.write_int(hp_base + HP_OFFSET, 0)
    print(f"hp {before} -> 0 written at {hp_base + HP_OFFSET:#x}")
    if overlay:
        time.sleep(args.toast_seconds)


def kill(args):
    player = Player()
    module = pymem.process.module_from_name(player.pm.process_handle, "nightreign.exe")
    death_call = _resolve_function_address(player.pm, module, DEATH_CALL_AOB)
    print(f"deathCall: {death_call:#x}")
    countdown(args.delay)
    ins = player.player_ins()
    if not ins:
        sys.exit("PlayerIns unreadable - are you in an expedition?")
    code = _KILL_PREFIX + struct.pack("<Q", death_call) + _KILL_SUFFIX
    trampoline = player.pm.allocate(len(code))
    player.pm.write_bytes(trampoline, code, len(code))
    player.pm.start_thread(trampoline, params=ins)
    print(f"deathCall({ins:#x}) fired")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    watch_parser = sub.add_parser("watch")
    watch_parser.add_argument("--interval", type=float, default=0.05)
    for name in ("down", "kill"):
        p = sub.add_parser(name)
        p.add_argument("--delay", type=int, default=5)
    toast_parser = sub.add_parser("toast")
    toast_parser.add_argument("text")
    toast_parser.add_argument("--delay", type=int, default=5)
    sub.choices["down"].add_argument("--toast", help="also show this text as a mock DeathLink toast")
    for p in (sub.choices["down"], toast_parser):
        p.add_argument("--toast-seconds", type=float, default=6.0)
        p.add_argument("--toast-y", type=float, default=0.14,
                       help="toast's top edge as a fraction of the game window's height")
    args = parser.parse_args()
    {"watch": watch, "down": down, "kill": kill, "toast": toast}[args.mode](args)


if __name__ == "__main__":
    main()
