"""Archipelago client for Elden Ring Nightreign.

Polls the running game via memory_reader.py and sends a location check on
each detected Nightlord win. When a Nightlord's Everdark Sovereign entry is
included for this slot (slot_data's everdark_nightlords, from Options.py's
IncludedNightlords - each Everdark Sovereign is its own separate entry there,
e.g. "Everdark Tricephalos") and the win is detected as its Everdark variant
(memory_reader.py's read_everdark_flag()), a separate "Defeat Everdark X"
location is sent instead of the normal one. Everdark Sovereigns are made selectable by
unlock_all_bosses_in_game's menu patch (see below), not by any per-boss EventFlag. Everdark
Sovereigns are treated as entirely separate bosses from their base Nightlord: with
gate_boss_access on, an Everdark win is checked against its own "Everdark X Access" item, never
the base Nightlord's, so having received one doesn't unlock the other. When the
gate_boss_access option is on for this
slot (learned from slot_data on connect), received Access items are synced
into the game via memory_writer.py's SetEventFlag port, gating which
Nightlords are actually selectable - though the 6 secondary bosses share one EventFlag, so
receiving any one of their Access items reveals all 6 in-game, not just the one received (see
game_data.EVENT_FLAG_SECONDARY_BOSSES). gate_character_access works the same way for received
Character Access items, gating which playable characters are selectable (each individually
addressable, no shared-flag quirk there). Both also suppress checks client-side, keyed on the
specific Nightlord/character's own Access item rather than trusting in-game selectability: this is
essential (not just defense-in-depth) for gate_boss_access given the shared-flag quirk above - e.g.
a slot that's only received "Augur Access" can still queue into Fissure in the Fog in-game, and the
client must independently catch and skip that win. When randomize_weapons and/or
randomize_talismans is on, received "Randomized Weapon"/"Randomized Talisman"
filler items are rolled into a real weapon/talisman client-side (see
_roll_weapon_drop/_roll_talisman_drop) and dropped on the ground via
memory_writer.py's NightreignItemDropWriter (shared by both - it's item-type
agnostic) as soon as the player is confirmed both in an Expedition and not
mid-flight (see game_data.py's WORLDCHRMAN_AOB/is_flying_animation - the drop
function needs a grounded position, so this is checked every poll tick, not
just once on Expedition entry). Delivery is also withheld (not lost - just retried on a later run)
for the whole run whenever _current_run_is_locked() says the current boss/character isn't actually
unlocked for this slot yet, so an earned weapon/talisman drop is never spent on a run that
_handle_win would refuse to send a check for anyway. receive_murk/receive_runes/
receive_sovereign_sigils filler ("Murk"/"Runes"/"Sovereign Sigil") is granted by calling the game's
own currency-add functions directly via memory_writer.py's NightreignCurrencyWriter, every pending
copy of a currency summed into one call - Runes during an Expedition (same settle window and
locked-run withholding as drops, no grounded requirement), Murk/Sigils in the Roundtable Hold once a
save is loaded (see _deliver_pending_currency). When unlock_all_bosses_in_game is on, every
tick spent genuinely in the hub (not the main menu - read_hub_state() alone can't tell those apart,
see memory_reader.py's is_save_loaded()) re-applies a code patch (memory_reader.ACCESS_ALL_BOSSES_AOB)
that keeps every boss, including DLC Nightlords and Everdark Sovereigns, selectable in the game's
own Expeditions menu regardless of real in-game unlock progress - purely a menu-selectability patch,
it never touches AP's own unlock state, so gate_boss_access's Access-item checks above still apply
exactly as if this were off. Status-effect traps (Scarlet Rot/Poison/Sleep/Frostbite/Madness, see
game_data.STATUS_TRAPS) go off during an Expedition, after the same settle window as drops, by calling
the game's own apply-SpEffect function on the player (see _maybe_start_trap). Received Progressive
Level/Progressive Flask copies set a floor the player's level and max flask charges are raised to
after the same settle window - level kept there all run, flasks set once per Expedition (see
_apply_metaprogression_floors). With
otherworld_offerings on, weapon/talisman drops and Runes are held as offerings until the player
accepts them from the Offerings tab or with /accept - see offerings.py. With all four options off, received items
have no in-game effect - the base CommonContext/CLI/GUI machinery just logs
them, same as before any was added. Wins are detected via _trigger_win (at most once per
Expedition) from two signals: primarily the buff-pick counter ticking in the Day 3 Nightlord arena
(game_data.is_nightlord_kill_tick - the only signal Night Aspect produces), with
read_outcome_pulse()'s rising edge as a fallback. When win_count_checks is on, every detected win
with a resolved boss_id increments a per-seed win counter persisted in the run state file (_open_run_state/
_write_run_state), and crossing one of this slot's win_count_thresholds (from slot_data - see
game_data.win_count_threshold_list/__init__.py's generate_early()) sends that "Win N Expeditions"
location - see _handle_win_count. This track is deliberately ungated: it counts every real win
regardless of gate_boss_access/gate_character_access/per_character_checks or whether the
boss/character is even in this slot's included_nightlords/included_characters, since it isn't tied
to a specific boss or character in the first place.

Three more per-Nightlord check families add density within a single Expedition rather than only at
its very end. Every valid defeat sends checks_per_boss - 1 extra bonus locations (slot_data's
checks_per_boss, game_data.bonus_indices) together with _handle_win's own "Defeat X" send
- NOT a cumulative counter; repeat defeats of the same boss/character/everdark award nothing
further here (self.checked_location_ids already prevents re-sending, the same as the base "Defeat
X" location). Night 1/Night 2 Clear (slot_data's night_checks, on by default) are each a single
non-cumulative location per boss/character/everdark, sent via _credit_single_check once (never re-sent, same
dedup): Night 1 fires on the day/night phase's 1->2 transition (the mid-run boss defeated), Night 2
fires on the 3->4 transition (the Night 2 boss defeated, entering the Day 3 Nightlord arena - NOT
merely reaching the Night 2 fight, which is the 2->3 transition) - see game_data.py's DAY_PHASE_*
constants. The third family, weak_reward_checks/strong_reward_checks,
stays opt-in and IS a genuinely cumulative counter (fixed at 1-5, game_data.REWARD_CHECK_THRESHOLDS)
sharing _credit_threshold (via _credit_extra_check) with win_count above - driven by
memory_reader.read_weapon_pickup_count()/read_buff_pick_count(), monotonic per-Expedition
counters credited by their delta since the last poll. Night 1/Night 2 Clear and weak/strong reward
all attribute their event to whichever Nightlord/character/Everdark-ness is currently resolvable
(see _resolve_win_context), independently of the win-pulse _handle_win itself reacts to, and are
silently skipped (not queued) whenever that context can't be resolved this tick or _access_owned
says this slot hasn't earned it yet - same posture as _handle_win's own
locked_boss_win_skipped/locked_character_win_skipped guards.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import random
import re
import time
from datetime import datetime, timezone
from typing import Optional

import colorama

import Utils
from CommonClient import (ClientCommandProcessor, CommonContext, get_base_parser,
                          gui_enabled, server_loop)
from NetUtils import ClientStatus

from .game_data import (ACCESS_CHARACTERS, ACCESS_ITEM_EVENT_FLAGS, ACCESS_NIGHTLORDS,
                        CHARACTER_ACCESS_EVENT_FLAGS, CURRENCY_BUNDLES,
                        CURRENCY_COUNTER_OFFSETS, CURRENCY_GRANT_MAX,
                        DAY_PHASE_DAY_2, DAY_PHASE_DAY_3, DAY_PHASE_NIGHT_1, DAY_PHASE_NIGHT_2, EVERDARK_NIGHTLORDS,
                        CHECKS_PER_BOSS_DEFAULT, MAX_FLASK_OFFSET, PLAYER_LEVEL_OFFSET,
                        PROGRESSIVE_FLASK, PROGRESSIVE_LEVEL, STATUS_TRAPS, TRAP_APPLY_INTERVAL,
                        bonus_indices, currency_bundle_names, is_flying_animation,
                        is_nightlord_kill_tick, level_floor, max_flask_floor,
                        starting_free_characters, starting_free_everdark_nightlords,
                        starting_free_nightlords)
from .death_link import DEATH_LINK_MODES, DeathLinkDetector
from .item_data import (EFFECT_CAP_MAP, TALISMAN_TABLE, WEAPON_ART_TABLE, WEAPON_TABLE,
                        natural_weapon_tier, roll_effect_tier, roll_upgrade_tier,
                        weapon_pool_for_character)
from .Items import lookup_id_to_name
from .offerings import ACCEPT_ALIASES, OFFERING_ITEMS, OFFERING_RUNES, OfferingQueue
from .Locations import (location_name, location_name_boss_only, location_name_everdark,
                        location_name_everdark_boss_only, location_name_kill_bonus,
                        location_name_night1, location_name_night2, location_name_strong_reward,
                        location_name_to_id, location_name_weak_reward, location_name_win_count)
from .memory_reader import EACDetectedError, NightreignMemoryReader, PointerNotFoundError
from .memory_writer import (NightreignCurrencyWriter, NightreignItemDropWriter,
                            NightreignLevelWriter, NightreignMemoryWriter,
                            NightreignSpEffectWriter, set_max_flasks, set_player_hp)
from . import tracker
from .overlay import NightreignOverlay

logger = logging.getLogger("NightreignClient")

# Tight enough to reliably catch the win pulse - see
# project notes on how narrow that window was observed to be.
POLL_INTERVAL = 0.25
RECONNECT_INTERVAL = 2
BUILD_MISMATCH_BACKOFF = 30

# The fly-in animation
EXPEDITION_ENTRY_SETTLE_SECONDS = 30

# How long to wait after arriving in the Roundtable Hold before granting Murk/Sovereign Sigils -
# a margin past the load, same caution as EXPEDITION_ENTRY_SETTLE_SECONDS.
HUB_ENTRY_SETTLE_SECONDS = 5
# Minimum gap between two traps going off, so a backlog of received traps spreads out over the
# Expedition instead of landing at once (a second rot trap on an already-rotting player does nothing).
TRAP_COOLDOWN_SECONDS = 30
# Minimum gap between two attempts to raise the player's level - only matters if the game doesn't
# take one, so a write that isn't landing can't fire every tick.
LEVEL_FLOOR_RETRY_SECONDS = 10

# slot_data key -> currency name (see game_data.CURRENCY_COUNTER_OFFSETS). Runes are granted
# during an Expedition, the other two in the Roundtable Hold - see poll_loop.
CURRENCY_SLOT_DATA_KEYS = {
    "receive_murk": "Murk",
    "receive_runes": "Runes",
    "receive_sovereign_sigils": "Sovereign Sigil",
}
HUB_CURRENCIES = ("Murk", "Sovereign Sigil")

# slot_data "goal" key (Options.py's Goal) -> Unlocks tab header text
GOAL_DISPLAY_NAMES = {
    "night_aspect": "Night Aspect",
    "all_bosses_all_characters": "All Bosses All Characters",
    "all_bosses": "All Bosses",
    "random_subset": "Random",
}

# Item received toast duration
# (6s - eyes are usually on an enemy or the map, so 3s was only enough to notice, not read)
TOAST_DURATION_SECONDS = 6.0
# Received-DeathLink toast.
DEATH_LINK_TOAST_SECONDS = 6.0


def _safe_filename_component(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_") or "unknown"


# JSON has no tuple keys, so the two per-(nightlord, character, everdark) count dicts below
# (weak_reward_counts/strong_reward_counts - the only two genuinely cumulative counters among the
# extra check families; nightlord bonus and Night 1/Night 2 Clear are non-cumulative, so they have
# no dict of their own here, just self.checked_location_ids) are serialized as a flat list of
# [nightlord, character, everdark, count] entries instead - same round-trip idea as
# _delivered_weapon_keys/_delivered_talisman_keys' (index, player) tuple lists.
def _counts_to_json(counts: dict) -> list:
    return [
        [nightlord, character, everdark, count]
        for (nightlord, character, everdark), count in counts.items()
    ]


def _counts_from_json(data: list) -> dict:
    return {(nightlord, character, everdark): count for nightlord, character, everdark, count in data}


class NightreignCommandProcessor(ClientCommandProcessor):
    """ClientCommandProcessor for Nightreign

    Args:
        ClientCommandProcessor (_type_): _description_
    """
    ctx: "NightreignContext"

    def _cmd_status(self):
        """Show the memory reader's current live readings."""
        self.ctx.print_status()

    def _cmd_deathlink(self, mode: str = "") -> bool:
        """Toggle DeathLink on/off, or set it: /deathlink [off|dead|downed]. Lasts until the
        client is closed."""
        mode = mode.lower()
        if not mode:
            if self.ctx.death_link_mode != "off":
                mode = "off"
            else:
                mode = self.ctx.slot_death_link_mode if self.ctx.slot_death_link_mode != "off" else "dead"
        if mode not in DEATH_LINK_MODES:
            self.output(f"Unknown DeathLink mode '{mode}' - use one of: {', '.join(DEATH_LINK_MODES)}.")
            return False
        self.ctx.set_death_link_mode(mode, from_command=True)
        self.output(f"DeathLink: {mode}")
        return True

    def _cmd_offerings(self) -> bool:
        """List the Otherworld Offerings you're holding."""
        if not self.ctx.otherworld_offerings:
            self.output("Otherworld Offerings are off for this slot - in-run items arrive "
                        "automatically.")
            return True
        held = self.ctx.offerings_held()
        if not held:
            self.output("This slot doesn't receive any items that can be held as offerings.")
            return True
        for name, (count, accepted) in held.items():
            self.output(f"{name}: {count} held" + (f", {accepted} accepted" if accepted else ""))
        status = self.ctx.offering_status()
        if status:
            self.output(status)
        return True

    def _cmd_accept(self, item: str = "", count: str = "1") -> bool:
        """Accept held offerings: /accept <weapon|talisman|runes|heroic> [count|all], or
        /accept cancel to take back every accepted offering that hasn't arrived yet."""
        item = item.lower()
        if item == "cancel":
            self.ctx.offering_queue.clear()
            self.output("Cancelled every accepted offering that hadn't arrived yet.")
            return True
        name = ACCEPT_ALIASES.get(item)
        if name is None:
            self.output(f"Usage: /accept <{'|'.join(ACCEPT_ALIASES)}> [count|all], "
                        "or /accept cancel.")
            return False
        if count.lower() == "all":
            amount = None
        elif count.isdigit() and int(count) > 0:
            amount = int(count)
        else:
            self.output(f"Unknown count '{count}' - use a number or all.")
            return False
        self.output(self.ctx.accept_offering(name, amount))
        return True


class NightreignContext(CommonContext):
    """Full client context for nightreign
    """
    game = "Elden Ring Nightreign"
    command_processor = NightreignCommandProcessor
    items_handling = 0b111
    reader: NightreignMemoryReader
    poll_task: Optional[asyncio.Task]
    run_state_path: Optional[str]
    checked_location_ids: set
    slot_data: dict
    gate_boss_access: bool
    gate_character_access: bool
    unlock_all_bosses_in_game: bool
    randomize_weapons: bool
    weapon_pool: str
    preferred_weapon_chance: int
    randomize_talismans: bool
    currency_items: set
    everdark_nightlords: set
    included_nightlords: list
    included_characters: list
    freed_nightlords: set
    freed_everdark_nightlords: set
    freed_characters: set
    per_character_checks: bool
    win_count_checks: bool
    win_count_thresholds: list
    win_count: int
    weak_reward_checks: bool
    weak_reward_thresholds: list
    strong_reward_checks: bool
    strong_reward_thresholds: list
    weak_reward_counts: dict
    strong_reward_counts: dict
    _last_day_phase: Optional[int]
    _last_weak_reward_raw: Optional[int]
    _last_buff_pick_raw: Optional[int]
    _last_in_hub: Optional[bool]
    _win_handled_this_run: bool
    _arena_trace: Optional[dict]
    goal: str
    goal_groups: list
    writer: Optional[NightreignMemoryWriter]
    overlay: Optional[NightreignOverlay]
    item_drop_writer: Optional[NightreignItemDropWriter]
    currency_writer: Optional[NightreignCurrencyWriter]
    _currency_worldchrman_slot: Optional[int]
    status_traps: bool
    speffect_writer: Optional[NightreignSpEffectWriter]
    _trap_worldchrman_slot: Optional[int]
    _trap_task: Optional[asyncio.Task]
    _last_trap_time: Optional[float]
    progressive_levels: bool
    progressive_flasks: bool
    level_writer: Optional[NightreignLevelWriter]
    _last_level_floor_attempt: Optional[float]
    _flask_floor_applied: Optional[int]
    _worldchrman_slot: Optional[int]
    _hub_exit_time: Optional[float]
    _hub_entry_time: Optional[float]
    _all_bosses_unlock_addr: Optional[int]
    _all_bosses_worldchrman_slot: Optional[int]
    _all_bosses_unlocked_this_hub: bool

    _last_pulse: Optional[int]
    _synced_flags: set
    _delivered_weapon_keys: set
    _delivered_talisman_keys: set
    _delivered_currency_keys: dict
    _delivered_trap_keys: set
    otherworld_offerings: bool
    offering_queue: OfferingQueue
    _offering_run_locked: bool
    _offering_flying: bool
    _locked_boss_warned: bool
    _locked_character_warned: bool
    _locked_run_drop_withheld_warned: bool
    _toast_text: Optional[str]
    _toast_style: str
    _toast_expiry: Optional[float]
    death_link_mode: str
    slot_death_link_mode: str
    _death_link_overridden: bool
    _death_link_detector: DeathLinkDetector
    _pending_death_link: Optional[dict]
    _death_link_last_in_hub: Optional[bool]

    def __init__(self, server_address: Optional[str], password: Optional[str]):
        super().__init__(server_address, password)
        self.reader = NightreignMemoryReader()
        self.poll_task = None
        self.run_state_path = None
        self.checked_location_ids = set()
        self.slot_data = {}
        self.gate_boss_access = False
        self.gate_character_access = False
        self.unlock_all_bosses_in_game = False
        self.randomize_weapons = False
        self.weapon_pool = "any"
        self.preferred_weapon_chance = 85
        self.randomize_talismans = False
        self.currency_items = set()
        self.everdark_nightlords = set()
        self.included_nightlords = list(ACCESS_NIGHTLORDS)
        self.included_characters = list(ACCESS_CHARACTERS)
        self.freed_nightlords = set()
        self.freed_everdark_nightlords = set()
        self.freed_characters = set()
        self.per_character_checks = False
        self.checks_per_boss = CHECKS_PER_BOSS_DEFAULT
        self.night_checks = True
        self.win_count_checks = False
        self.win_count_thresholds = []
        self.win_count = 0
        self.weak_reward_checks = False
        self.weak_reward_thresholds = []
        self.strong_reward_checks = False
        self.strong_reward_thresholds = []
        self.weak_reward_counts = {}
        self.strong_reward_counts = {}
        self._last_day_phase = None
        self._last_weak_reward_raw = None
        self._last_buff_pick_raw = None
        self._last_in_hub = None
        self._win_handled_this_run = False
        self._arena_trace = None
        self.goal = "all_bosses_all_characters"
        self.goal_groups = []
        self.writer = None
        self.overlay = None
        self.item_drop_writer = None
        self.currency_writer = None
        self._currency_worldchrman_slot = None
        self.status_traps = False
        self.speffect_writer = None
        self._trap_worldchrman_slot = None
        self._trap_task = None
        self._last_trap_time = None
        self.progressive_levels = False
        self.progressive_flasks = False
        self.level_writer = None
        self._last_level_floor_attempt = None
        self._flask_floor_applied = None
        self._worldchrman_slot = None
        self._hub_exit_time = None
        self._hub_entry_time = None
        self._all_bosses_unlock_addr = None
        self._all_bosses_worldchrman_slot = None
        self._all_bosses_unlocked_this_hub = False
        self._last_pulse = None
        self._synced_flags = set()
        self._delivered_weapon_keys = set()
        self._delivered_talisman_keys = set()
        self._delivered_currency_keys = {name: set() for name in CURRENCY_COUNTER_OFFSETS}
        self._delivered_trap_keys = set()
        self.otherworld_offerings = False
        self.offering_queue = OfferingQueue()
        self._offering_run_locked = False
        self._offering_flying = False
        self._locked_boss_warned = False
        self._locked_character_warned = False
        self._locked_run_drop_withheld_warned = False
        self._toast_text = None
        self._toast_style = "item"
        self._toast_expiry = None
        self.death_link_mode = "off"
        self.slot_death_link_mode = "off"
        self._death_link_overridden = False
        self._death_link_detector = DeathLinkDetector()
        self._pending_death_link = None
        self._death_link_last_in_hub = None

    def run_gui(self):

        # Allow deferred import for GUI
        from kvui import GameManager

        from kivy.clock import Clock
        from kivy.metrics import dp
        from kivy.uix.behaviors import ButtonBehavior
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.button import MDButton, MDButtonText
        from kivymd.uix.label import MDLabel
        from kivymd.uix.scrollview import MDScrollView

        STATUS_COLORS = {
            tracker.LOCKED: (0.90, 0.30, 0.30, 1),
            tracker.AVAILABLE: (0.30, 0.80, 0.35, 1),
            tracker.DONE: (0.55, 0.55, 0.55, 1),
        }

        def status_label(text: str, status: str, **kwargs) -> MDLabel:
            return MDLabel(text=text, adaptive_height=True, theme_text_color="Custom",
                           text_color=STATUS_COLORS[status], **kwargs)

        class ToggleLabel(ButtonBehavior, MDLabel):
            pass

        class TrackerSection(MDBoxLayout):
            """A bold title over a list of colored rows. Rows with children (bosses in
            boss-with-character mode) render collapsed behind a +/- toggle."""

            def __init__(self, title: str, expanded: set, **kwargs):
                super().__init__(orientation="vertical", adaptive_height=True, spacing=dp(2),
                                 padding=(dp(8), dp(8), dp(8), dp(8)), **kwargs)
                self.expanded = expanded  # shared with the manager so it survives rebuilds
                self.header = MDLabel(text=title, bold=True, adaptive_height=True)
                self.add_widget(self.header)
                self.rows = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(2))
                self.add_widget(self.rows)

            def set_rows(self, title: str, rows: list, empty_text: str) -> None:
                self.header.text = title
                self.rows.clear_widgets()
                if not rows:
                    self.rows.add_widget(MDLabel(text=empty_text, adaptive_height=True))
                    return
                for row in rows:
                    if not row.children:
                        self.rows.add_widget(status_label(row.name, row.status))
                        continue
                    self._add_collapsible(row)

            def _add_collapsible(self, row) -> None:
                children_box = MDBoxLayout(orientation="vertical", adaptive_height=True,
                                           padding=(dp(24), 0, 0, 0))
                for child in row.children:
                    children_box.add_widget(status_label(child.name, child.status))
                toggle = ToggleLabel(adaptive_height=True, theme_text_color="Custom",
                                     text_color=STATUS_COLORS[row.status])

                def render(*_args) -> None:
                    is_open = row.name in self.expanded
                    toggle.text = f"{'-' if is_open else '+'} {row.name}"
                    index = self.rows.children.index(toggle)
                    if is_open and children_box.parent is None:
                        # Kivy's add_widget index counts from the end - this lands right below.
                        self.rows.add_widget(children_box, index=index)
                    elif not is_open and children_box.parent is not None:
                        self.rows.remove_widget(children_box)

                def on_release(*_args) -> None:
                    self.expanded.symmetric_difference_update({row.name})
                    render()

                toggle.bind(on_release=on_release)
                self.rows.add_widget(toggle)
                render()

        def scrolled(*sections) -> MDScrollView:
            body = MDBoxLayout(orientation="vertical", adaptive_height=True)
            for section in sections:
                body.add_widget(section)
            scroll = MDScrollView()
            scroll.add_widget(body)
            return scroll

        def count_done(rows: list) -> int:
            return sum(1 for r in rows if r.status == tracker.DONE)

        ctx = self

        def button(text: str, on_release, disabled: bool = False) -> MDButton:
            return MDButton(MDButtonText(text=text), style="tonal", disabled=disabled,
                            pos_hint={"center_y": 0.5}, on_release=lambda *_args: on_release())

        class OfferingsTab(MDBoxLayout):
            """Held Otherworld Offerings with accept buttons - see offerings.py. Every button goes
            through the same ctx methods as /offerings and /accept."""

            def __init__(self, **kwargs):
                super().__init__(orientation="vertical", adaptive_height=True, spacing=dp(6),
                                 padding=(dp(8), dp(8), dp(8), dp(8)), **kwargs)
                self._last_state = ()  # never equal to a real state, so the first tick renders

            def label(self, text: str, **kwargs) -> MDLabel:
                return MDLabel(text=text, adaptive_height=True, pos_hint={"center_y": 0.5},
                               **kwargs)

            def row(self, *widgets) -> None:
                box = MDBoxLayout(orientation="horizontal", adaptive_height=True, spacing=dp(8))
                for widget in widgets:
                    box.add_widget(widget)
                self.add_widget(box)

            def act(self, action) -> None:
                # Via "Client", the logger the GUI's visible Archipelago tab follows.
                logging.getLogger("Client").info(action())
                self._last_state = ()
                self.refresh()

            def refresh(self) -> None:
                state = (tuple(ctx.offerings_held().items()), ctx.offering_status())
                if state == self._last_state:
                    return
                self._last_state = state
                held, status = state
                self.clear_widgets()
                self.add_widget(self.label("Offerings from Beyond the Night", bold=True))
                self.add_widget(self.label(
                    "Gifts from other worlds. They await your acceptance."
                ))
                if not held:
                    self.add_widget(self.label(
                        "This slot doesn't receive any items that can be held as offerings."
                    ))
                    return
                for name, (count, accepted) in held:
                    text = name
                    if name in CURRENCY_BUNDLES:
                        text += f" ({CURRENCY_BUNDLES[name][1]:,} runes)"
                    text += f": {count} held" + (f", {accepted} accepted" if accepted else "")
                    full = accepted >= count
                    self.row(
                        self.label(text),
                        button("Accept 1", functools.partial(self.act, functools.partial(
                            ctx.accept_offering, name, 1)), disabled=full),
                        button("All", functools.partial(self.act, functools.partial(
                            ctx.accept_offering, name, None)), disabled=full),
                    )
                if status:
                    def cancel() -> str:
                        ctx.offering_queue.clear()
                        return "Cancelled every accepted offering that hadn't arrived yet."

                    self.row(self.label(status, italic=True),
                             button("Cancel", lambda: self.act(cancel)))

        class NightreignManager(GameManager):
            logging_pairs = [("Client", "Archipelago")]
            base_title = "Archipelago Nightreign Client"

            def build(self):
                container = super().build()
                self.expanded_bosses = set()  # every boss starts collapsed
                self.bosses_section = TrackerSection("Bosses", self.expanded_bosses)
                self.characters_section = TrackerSection("Characters", set())
                self.wins_section = TrackerSection("Win Count", set())
                self.goal_section = TrackerSection("Goal", set())
                unlocks = MDBoxLayout(orientation="horizontal")
                unlocks.add_widget(scrolled(self.bosses_section))
                unlocks.add_widget(scrolled(self.goal_section, self.characters_section,
                                            self.wins_section))
                self.add_client_tab("Unlocks", unlocks)
                # Added once a slot with otherworld_offerings on connects - see refresh_offerings.
                self.offerings = None
                self.offerings_tab = None
                self._last_unlocks = ()  # never equal to a real state, so the first tick renders
                Clock.schedule_interval(self.refresh_unlocks, 1)
                return container

            def refresh_offerings(self) -> None:
                # slot_data only arrives on connect, after build(), so the tab can't be decided
                # up front - shown only while the connected slot has otherworld_offerings on.
                wanted = ctx.slot is not None and ctx.otherworld_offerings
                if wanted and self.offerings_tab is None:
                    self.offerings = OfferingsTab()
                    self.offerings_tab = self.add_client_tab("Offerings", scrolled(self.offerings))
                elif not wanted and self.offerings_tab is not None:
                    self.remove_client_tab(self.offerings_tab)
                    self.offerings = self.offerings_tab = None
                if self.offerings is not None:
                    self.offerings.refresh()

            def refresh_unlocks(self, _dt) -> None:
                # Only rebuilt on change - received items, checked locations and slot_data all land
                # asynchronously, so polling once a second is simpler than hooking every path.
                self.refresh_offerings()
                state = None if ctx.slot is None else ctx.tracker_state()
                if state == self._last_unlocks:
                    return
                self._last_unlocks = state
                if state is None:
                    for section, title in ((self.goal_section, "Goal"),
                                           (self.bosses_section, "Bosses"),
                                           (self.characters_section, "Characters"),
                                           (self.wins_section, "Win Count")):
                        section.set_rows(title, [], "Connect to a slot to see this.")
                    return
                bosses, characters, wins = state["bosses"], state["characters"], state["wins"]
                goal_done, goal_total = state["goal_progress"]
                self.goal_section.set_rows(
                    f"Goal: {GOAL_DISPLAY_NAMES.get(state['goal'], state['goal'])} "
                    f"({goal_done}/{goal_total})", state["goal_rows"],
                    "No goal list in this seed - the goal is checking every location.",
                )
                self.bosses_section.set_rows(
                    f"Bosses ({count_done(bosses)}/{len(bosses)} cleared)", bosses,
                    "No boss checks in this slot.",
                )
                received = sum(1 for r in characters if r.status == tracker.AVAILABLE)
                self.characters_section.set_rows(
                    f"Characters ({received}/{len(characters)} unlocked)", characters,
                    "Character access isn't gated for this slot.",
                )
                self.wins_section.set_rows(
                    f"Win Count ({state['win_count']} wins)", wins,
                    "Win count checks are off for this slot.",
                )

        self.ui = NightreignManager(self)
        self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        if cmd == "RoomInfo":
            self.seed_name = args["seed_name"]

        if cmd == "Connected":
            # CommonContext doesn't assign slot_data itself even though
            # want_slot_data defaults to True - every game client that needs
            # it sets this itself here.
            self.slot_data = args.get("slot_data", {}) or {}
            self.gate_boss_access = bool(self.slot_data.get("gate_boss_access", False))
            self.gate_character_access = bool(self.slot_data.get("gate_character_access", False))
            self.unlock_all_bosses_in_game = bool(
                self.slot_data.get("unlock_all_bosses_in_game", False)
            )
            # slot_data keys are "receive_weapons"/"receive_talismans" (see Options.py/__init__.py's
            # fill_slot_data), not "randomize_weapons"/"randomize_talismans" - using the wrong keys
            # previously fell back to False regardless of the player's actual YAML settings.
            self.randomize_weapons = bool(self.slot_data.get("receive_weapons", False))
            self.weapon_pool = self.slot_data.get("weapon_pool", "any")
            self.preferred_weapon_chance = int(self.slot_data.get("preferred_weapon_chance", 85))
            self.randomize_talismans = bool(self.slot_data.get("receive_talismans", False))
            self.currency_items = {
                name for key, name in CURRENCY_SLOT_DATA_KEYS.items()
                if self.slot_data.get(key, False)
            }
            # starting_murk arrives as start-inventory Murk bundles - deliverable through the
            # same Murk path even when receive_murk (Murk as filler) is off.
            if self.slot_data.get("starting_murk", 0):
                self.currency_items.add("Murk")
            self.status_traps = bool(self.slot_data.get("status_traps", False))
            self.progressive_levels = bool(self.slot_data.get("progressive_levels", 0))
            self.progressive_flasks = bool(self.slot_data.get("progressive_flasks", 0))
            self.otherworld_offerings = bool(self.slot_data.get("otherworld_offerings", False))
            # Accepted offerings are per-session, never carried over to another slot.
            self.offering_queue.clear()
            self.everdark_nightlords = set(self.slot_data.get("everdark_nightlords") or [])
            # Seeds generated before these keys existed fall back to every boss/character.
            self.included_nightlords = list(
                self.slot_data.get("included_nightlords") or ACCESS_NIGHTLORDS
            )
            self.included_characters = list(
                self.slot_data.get("included_characters") or ACCESS_CHARACTERS
            )
            # starting_boss_everdark (see Options.py's StartingBoss/__init__.py's generate_early())
            # decides which set the starting_boss name goes into - Everdark Sovereigns are separate
            # bosses from their base Nightlord, so an everdark_* starting_boss frees the Everdark
            # form only, leaving the base Nightlord just as gated as any other.
            starting_boss = self.slot_data.get("starting_boss", "Tricephalos")
            if bool(self.slot_data.get("starting_boss_everdark", False)):
                self.freed_nightlords = set()
                self.freed_everdark_nightlords = set(
                    starting_free_everdark_nightlords(starting_boss)
                )
            else:
                self.freed_nightlords = set(starting_free_nightlords(starting_boss))
                self.freed_everdark_nightlords = set()
            self.freed_characters = set(
                starting_free_characters(self.slot_data.get("starting_character", "Wylder"))
            )
            self.per_character_checks = (
                self.slot_data.get("check_style", "boss") == "boss_per_character"
            )
            # Defaults match seeds from before these were options (fixed 5 checks, nights always on).
            self.checks_per_boss = int(
                self.slot_data.get("checks_per_boss", CHECKS_PER_BOSS_DEFAULT)
            )
            self.night_checks = bool(self.slot_data.get("night_checks", True))
            self.win_count_checks = bool(self.slot_data.get("win_count_checks", False))
            # Already capped at this slot's win_count_up_to by __init__.py's generate_early() - a
            # threshold above that cap has no location in the pool at all.
            self.win_count_thresholds = list(self.slot_data.get("win_count_thresholds") or [])
            self.weak_reward_checks = bool(self.slot_data.get("weak_reward_checks", False))
            self.weak_reward_thresholds = list(self.slot_data.get("weak_reward_thresholds") or [])
            self.strong_reward_checks = bool(self.slot_data.get("strong_reward_checks", False))
            self.strong_reward_thresholds = list(
                self.slot_data.get("strong_reward_thresholds") or []
            )
            self.goal = self.slot_data.get("goal", "all_bosses_all_characters")
            self.goal_groups = self.slot_data.get("goal_groups") or []
            self.slot_death_link_mode = self.slot_data.get("death_link", "off")
            # A /deathlink typed this session wins over the slot's setting across reconnects.
            self.set_death_link_mode(
                self.death_link_mode if self._death_link_overridden else self.slot_death_link_mode
            )
            logger.info("gate_boss_access=%s for this slot.", self.gate_boss_access)
            logger.info("gate_character_access=%s for this slot.", self.gate_character_access)

            # A flag write only confirms dispatch, not that it landed in-game (see
            # memory_writer.py's set_event_flag docstring), so clear this on every fresh AP
            # connection - not just a game-process reconnect - to make reconnecting a retry path.
            self._synced_flags.clear()

            self._open_run_state()
            # Replay anything our local state already thinks is checked, in case the server and
            # our local record ever drifted (e.g. a connection dropped mid-send).
            # check_locations() only sends what's still in ctx.missing_locations, so this is safe.
            if self.checked_location_ids:
                asyncio.create_task(self.check_locations(self.checked_location_ids))
            asyncio.create_task(self._maybe_declare_goal())
            # gate_boss_access is only known once this packet arrives, but the game process may
            # already be attached from before this connect (poll_loop's own connect-transition ran
            # with it still False) - build the writer here too, or it stays unbuilt all session.
            self._ensure_gating_ready()
            self._ensure_overlay_ready()
            asyncio.create_task(self._sync_event_flags())
            # Same race as gating above: the game process may already be attached from before
            # this connect, so build the item-drop writer here too, not just in poll_loop.
            self._ensure_item_drop_ready()
            self._ensure_animation_ready()
            self._ensure_currency_ready()
            self._ensure_trap_ready()
            self._ensure_metaprogression_ready()
            self._ensure_all_bosses_unlock_ready()

        if cmd == "ReceivedItems":
            if self.gate_boss_access or self.gate_character_access:
                asyncio.create_task(self._sync_event_flags())
            # No action needed for randomize_weapons/randomize_talismans - _pending_drop_keys()
            # recomputes from self.items_received on every poll_loop hub-exit edge, so a new
            # "Randomized Weapon"/"Talisman" is picked up on the next Expedition entry automatically.
            # Currency items work the same way (see _deliver_pending_currency).

        if cmd == "RoomUpdate":
            # missing_locations is updated (by base on_package handling, before this hook runs)
            # from this packet's "checked_locations" field, so this - not right after our own
            # send - is the correct place to notice "nothing left to check".
            asyncio.create_task(self._maybe_declare_goal())

    def _goal_complete(self) -> bool:
        # goal_groups (from slot_data) is a list of groups, each satisfied by ANY one of its
        # location ids being checked; the goal needs EVERY group satisfied. Falls back to "no
        # locations left to check" if slot_data has no goal_groups (e.g. a seed from before this).
        if not self.goal_groups:
            return not self.missing_locations
        return all(
            any(location_id not in self.missing_locations for location_id in group)
            for group in self.goal_groups
        )

    async def _maybe_declare_goal(self) -> None:
        # No item/logic gating here (topology_present = False), so there's no CollectionState
        # completion_condition to rely on - "goal" can only be observed client-side via
        # _goal_complete() (docs/adding games.md requires a StatusUpdate on goal completion).
        if not self.finished_game and self.slot is not None and self._goal_complete():
            self.finished_game = True
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            logger.info("Goal '%s' complete!", self.goal)

    # --- Boss/character-access gating (write path) ---
    # Off unless slot_data's gate_boss_access/gate_character_access is on. Firing SetEventFlag(110)
    # for any one of the 6 secondary-boss Access items reveals all 6 in the game's own menu
    # (all-or-nothing) - character flags don't have this quirk, each is individually addressable
    # (live-verified, see game_data.CHARACTER_EVENT_FLAGS).

    def _owned_item_names(self) -> set:
        # freed_nightlords/freed_everdark_nightlords (from starting_boss) and freed_characters
        # (from starting_character) are stitched in as synthetic "X Access"/"Everdark X Access"/
        # "X Character Access" entries so every downstream consumer - flag-firing, the Unlocks
        # tab - treats them exactly like an already-received Access item, with
        # no separate code path needed.
        owned = {lookup_id_to_name.get(i.item) for i in self.items_received}
        owned |= {f"{name} Access" for name in self.freed_nightlords}
        owned |= {f"Everdark {name} Access" for name in self.freed_everdark_nightlords}
        owned |= {f"{name} Character Access" for name in self.freed_characters}
        return owned

    def tracker_state(self) -> dict:
        """Rows for the client's Unlocks tab (see tracker.py for the color rules). Characters are
        only listed when gated - ungated, there's nothing to receive. Bosses are always listed,
        since their checks are worth tracking either way."""
        owned = self._owned_item_names()
        slot_locations = set(self.checked_locations) | set(self.missing_locations)
        sent = set(self.checked_locations) | self.checked_location_ids
        return {
            "bosses": tracker.boss_rows(
                owned, slot_locations, sent, self.included_nightlords, self.everdark_nightlords,
                self.included_characters, self.per_character_checks, self.gate_boss_access,
                self.gate_character_access,
            ),
            "characters": (tracker.character_rows(owned, self.included_characters)
                           if self.gate_character_access else []),
            "wins": tracker.win_count_rows(slot_locations, sent, self.win_count_thresholds),
            "win_count": self.win_count,
            "goal": self.goal,
            "goal_rows": tracker.goal_rows(self.goal_groups, owned, sent, self.gate_boss_access,
                                           self.gate_character_access),
            "goal_progress": tracker.goal_progress(self.goal_groups, sent),
        }

    async def _sync_event_flags(self) -> None:
        if not (self.gate_boss_access or self.gate_character_access) or self.writer is None:
            return
        owned_names = self._owned_item_names()
        needed_flags = {
            flag for name, flag in ACCESS_ITEM_EVENT_FLAGS.items() if name in owned_names
        }
        needed_flags |= {
            flag for name, flag in CHARACTER_ACCESS_EVENT_FLAGS.items() if name in owned_names
        }
        needed_flags -= self._synced_flags
        if not needed_flags:
            return
        loop = asyncio.get_running_loop()
        for flag in needed_flags:
            ok = await loop.run_in_executor(None, self.writer.set_event_flag, flag, True)
            if ok:
                self._synced_flags.add(flag)
                logger.info("SetEventFlag(%s, 1) succeeded.", flag)
            else:
                # Not a real "next sync" trigger on its own - freed_nightlords (from
                # starting_boss) never arrives as a ReceivedItems packet, so without the
                # per-tick call in poll_loop this would silently never retry.
                logger.warning(
                    "SetEventFlag(%s, 1) skipped - game not ready, will retry on next sync.", flag
                )

    def _ensure_gating_ready(self) -> None:
        """Builds the writer once either gate_boss_access/gate_character_access/
        unlock_all_bosses_in_game and the game connection are known, regardless of which arrived
        first this session - the game process attaching and the AP 'Connected' packet (which is
        what sets all three options) race each other, and either can win. Called from both sides
        of that race: here and from poll_loop's connect-transition. A no-op once the writer
        already exists."""
        if (not (self.gate_boss_access or self.gate_character_access
                 or self.unlock_all_bosses_in_game)
                or not self.reader.connected or self.writer is not None):
            return
        self._try_build_writer()

    def _ensure_overlay_ready(self) -> None:
        """Builds the overlay once the game connection is known - unlike the writer above, this
        isn't gated on gate_boss_access: the Expedition debug panel (boss_id/detected boss/
        character) is useful for diagnosing missed win checks for every player, not just those
        using boss gating. Same race as _ensure_gating_ready (game-process attach vs. AP
        'Connected' packet), so called from both of that method's call sites. A no-op once
        already built."""
        if not self.reader.connected or self.overlay is not None:
            return
        self.overlay = NightreignOverlay(self.reader.pm.process_id)
        self.overlay.start()
        logger.info("Overlay started (pid=%s).", self.reader.pm.process_id)

    def _warn_if_boss_locked(self, boss_name: str, everdark: bool = False) -> None:
        """Logs (and records to run state) an Expedition started on a Nightlord (or, if everdark
        is True and boss_name has an Everdark form, its Everdark Sovereign - a separate boss with
        its own "Everdark X Access" item) whose Access item this slot hasn't received yet.
        gate_boss_access's flag write is all-or-nothing (see the module comment above
        _owned_item_names) - receiving any one base-boss Access item reveals all 6 secondary
        bosses in the game's own menu, so nothing in-game stops the player from selecting one they
        don't actually have Access to. The client's Unlocks tab already shows this passively; this is the same
        check surfaced as a log line for the "basically wasting their run" case the player might
        not notice mid-run."""
        is_everdark = everdark and boss_name in EVERDARK_NIGHTLORDS
        access_name = f"Everdark {boss_name} Access" if is_everdark else f"{boss_name} Access"
        # Everdark access names are never in ACCESS_ITEM_EVENT_FLAGS (no per-boss EventFlag - only
        # unlock_all_bosses_in_game's whole-menu patch makes them selectable), so this warning
        # naturally never fires for an Everdark run, same as it already skips
        # Tricephalos/Balancers/Dreglord for the same reason.
        if access_name not in ACCESS_ITEM_EVENT_FLAGS or access_name in self._owned_item_names():
            return
        logger.warning(
            "Expedition started on %s, but its Access item hasn't been received yet for this "
            "slot - this Nightlord is still locked for AP purposes.", boss_name
        )
        self._append_event({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "locked_boss_attempt",
            "boss": boss_name,
            "everdark": is_everdark,
        })

    def _warn_if_character_locked(self, character_name: str) -> None:
        """Character analog of _warn_if_boss_locked above - logs (and records to run state) an
        Expedition started as a character whose Character Access item this slot hasn't received
        yet. Unlike the boss batch-unlock quirk, character flags are individually addressable (see
        game_data.CHARACTER_EVENT_FLAGS), so nothing in-game stops the player from launching with
        a character unlocked some other way (e.g. a pre-existing save) even though only this one
        was actually earned via AP."""
        access_name = f"{character_name} Character Access"
        if (access_name not in CHARACTER_ACCESS_EVENT_FLAGS
                or access_name in self._owned_item_names()):
            return
        logger.warning(
            "Expedition started as %s, but its Character Access item hasn't been received yet "
            "for this slot - this character is still locked for AP purposes.", character_name
        )
        self._append_event({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "locked_character_attempt",
            "character": character_name,
        })

    def _current_run_is_locked(self) -> bool:
        """True if the Expedition in progress is on a boss and/or character this slot hasn't
        actually received the Access item for yet - i.e. a run that _handle_win's own
        locked_boss_win_skipped/locked_character_win_skipped guards would refuse to send a check
        for. Used to withhold randomized weapon/talisman drops for the same run, so an earned item
        isn't spent on a run that was never going to pay out - mirrors those guards' own
        owned-item-name checks exactly, so a "locked" verdict here always agrees with them. Reads
        fresh every call rather than caching, matching _handle_win's own pattern; boss_id/character
        can read "unset"/None for a tick or two around scene transitions, which this treats as "not
        locked" (fail open) since delivery is retried every tick anyway - the alternative (fail
        closed) would only delay an already-earned drop, not lose it, but there's no reason to
        default to the more paranoid choice here when the transient case self-corrects within a
        tick or two."""
        owned_names = self._owned_item_names()
        if self.gate_boss_access:
            boss = self.reader.read_boss_id()
            if boss.status == "matched":
                everdark = bool(self.reader.read_everdark_flag())
                is_everdark = everdark and boss.name in EVERDARK_NIGHTLORDS
                access_name = (
                    f"Everdark {boss.name} Access" if is_everdark else f"{boss.name} Access"
                )
                if access_name not in owned_names:
                    return True
        if self.gate_character_access:
            character_name = self.reader.read_character_class_name()
            if character_name is not None and f"{character_name} Character Access" not in owned_names:
                return True
        return False

    def _try_build_writer(self) -> None:
        try:
            ptr_slot, base_a_addr = self.reader.resolve_event_flag_targets()
        except PointerNotFoundError as e:
            logger.error("Boss/character-gating write path unavailable (%s) - disabling gating "
                         "this session, the read-only tracker is unaffected.", e)
            self.gate_boss_access = False
            self.gate_character_access = False
            self.unlock_all_bosses_in_game = False
            return
        self.writer = NightreignMemoryWriter(self.reader.pm, ptr_slot, base_a_addr)
        logger.info("Boss/character-gating writer resolved (ptr_slot=0x%X, base_a=0x%X).",
                    ptr_slot, base_a_addr)

    def _ensure_all_bosses_unlock_ready(self) -> None:
        """Resolves the all-bosses-unlock patch address and a dedicated WorldChrMan pointer slot
        (used only to tell the hub apart from the main menu - see memory_reader.py's
        is_save_loaded()) once unlock_all_bosses_in_game and the game connection are known. Same
        race/no-op-once-ready shape as _ensure_animation_ready - kept as its own dedicated
        WorldChrMan resolve rather than sharing _worldchrman_slot, so a failure here can't disable
        randomize_weapons/randomize_talismans (or vice versa) - the two features are otherwise
        unrelated. Requires self.writer already built (see _ensure_gating_ready)."""
        if (not self.unlock_all_bosses_in_game or not self.reader.connected
                or self.writer is None or self._all_bosses_unlock_addr is not None):
            return
        try:
            self._all_bosses_unlock_addr = self.reader.resolve_all_bosses_unlock_target()
            self._all_bosses_worldchrman_slot = self.reader.resolve_current_animation_target()
        except PointerNotFoundError as e:
            logger.error("All-bosses-unlock write path unavailable (%s) - disabling "
                         "unlock_all_bosses_in_game this session, the read-only tracker is "
                         "unaffected.", e)
            self.unlock_all_bosses_in_game = False
            self._all_bosses_unlock_addr = None
            self._all_bosses_worldchrman_slot = None

    # --- Randomized item-drop write path (weapons and talismans) ---
    # Off unless randomize_weapons/randomize_talismans is on. A received item is rolled into a
    # real item and dropped once poll_loop confirms in an Expedition and grounded (not mid-flight).

    def _ensure_item_drop_ready(self) -> None:
        """Same "build once both an option and the game connection are known" shape as
        _ensure_gating_ready, for the same race-condition reason - called from both here and
        poll_loop's connect-transition. A no-op once the writer already exists."""
        if (not (self.randomize_weapons or self.randomize_talismans) or not self.reader.connected
                or self.item_drop_writer is not None):
            return
        try:
            targets = self.reader.resolve_item_drop_targets()
        except PointerNotFoundError as e:
            logger.error("Randomized item-drop write path unavailable (%s) - disabling "
                         "randomize_weapons/randomize_talismans this session, the read-only "
                         "tracker is unaffected.", e)
            self.randomize_weapons = False
            self.randomize_talismans = False
            return
        self.item_drop_writer = NightreignItemDropWriter(self.reader.pm, targets)
        logger.info("Randomized item-drop writer resolved.")

    def _ensure_animation_ready(self) -> None:
        """Same "build once both an option and the game connection are known" shape as
        _ensure_item_drop_ready/_ensure_gating_ready, for the same race-condition reason - called
        from both here and poll_loop's connect-transition. A no-op once already resolved. Without
        this, delivery can't tell "in an Expedition but mid-flight" apart from "grounded", so a
        resolve failure disables randomize_weapons/randomize_talismans for the session rather than
        risk delivering (or crashing) mid-air - same conservative precedent as
        _ensure_item_drop_ready's own AOB failure handling."""
        if (not (self.randomize_weapons or self.randomize_talismans or self.death_link_mode != "off")
                or not self.reader.connected or self._worldchrman_slot is not None):
            return
        try:
            self._worldchrman_slot = self.reader.resolve_current_animation_target()
        except PointerNotFoundError as e:
            logger.error("Player animation/HP read path unavailable (%s) - disabling "
                         "randomize_weapons/randomize_talismans and DeathLink this session, the "
                         "read-only tracker is unaffected.", e)
            self.randomize_weapons = False
            self.randomize_talismans = False
            self.set_death_link_mode("off")

    def _pending_drop_keys(self, item_name: str, delivered_keys: set) -> set:
        """(index, player) keys for every received `item_name` filler item not yet delivered -
        recomputed fresh from self.items_received each call rather than tracked incrementally,
        the same "diff against what's already done" shape as _sync_event_flags. Keyed on each
        item's position within items_received, not (location, player) - a location-based key
        breaks for any item sent outside a real location check (e.g. the server's !getitem admin
        command, which always sends location=-1), since every such item would then collide on the
        same key and get deduped away after the first one delivers. items_received's order is
        stable across reconnects (the server always replays the same full history), so this stays
        just as resumable as the location-based key was."""
        received = {
            (index, i.player) for index, i in enumerate(self.items_received)
            if lookup_id_to_name.get(i.item) == item_name
        }
        return received - delivered_keys

    def _roll_weapon_drop(self, index: int, player: int, character: Optional[str] = None) -> dict:
        """Deterministic roll for one "Randomized Weapon" filler instance, seeded off which
        received-item instance sent it (seed_name + index + player) rather than delivery order or
        timing - so a reconnect, a retried drop, or a delayed Expedition entry always reproduces
        the exact same weapon instead of re-rolling. Every axis is independently randomized per
        the project's design discussion: weapon id (uniform over game_data.WEAPON_TABLE),
        upgrade_level (weighted via game_data.roll_upgrade_tier - see its own comment for the
        band shape), weapon_art and wep_effect (uniform, including a "None" outcome so not every
        drop is maximally loaded - left unweighted deliberately, so "None" is roughly 1-in-131),
        and effect_tier (weighted via game_data.roll_effect_tier, same band-percentile idea as
        upgrade_level - memory_writer.py's drop_item already discards this whenever wep_effect is
        None or the rolled effect's own cap is lower, so no extra logic is needed here to keep it
        valid). magic_skill_1/2 are left at "None" - narrower in scope (only staff/seal weapons
        use them) and out of scope for this pass; ask if you want those randomized too.

        roll_upgrade_tier()'s result is an ABSOLUTE target tier (0=Default/1=Blue/2=Purple/
        3=Orange), not a raw amount to add - some weapon ids in WEAPON_TABLE are already partway
        up that scale in their only obtainable form (see game_data.py's WEAPON_NATURAL_TIER
        comment - live-confirmed via "Ant's Skull Plate", which drops naturally Purple), so the
        upgrade_level actually requested from drop_item() is only the gap above that weapon's own
        natural floor, never negative. memory_writer.py's _clamp_upgrade_tier still applies on top
        of this for the separate, orthogonal concern of a weapon's own max reinforcement ceiling.

        character (weapon_pool "character_preferred" only) joins the seed, so the same item
        reproduces the same weapon per character, and preferred_weapon_chance percent
        of the time narrows the weapon id pick to item_data.weapon_pool_for_character (otherwise
        the full table); None keeps the original full-table roll and seed unchanged.
        """
        if character is None:
            rng = random.Random(f"{self.seed_name}:{index}:{player}:weapon")
            pool = list(WEAPON_TABLE)
        else:
            rng = random.Random(f"{self.seed_name}:{index}:{player}:weapon:{character}")
            if rng.randint(1, 100) <= self.preferred_weapon_chance:
                pool = weapon_pool_for_character(character)
            else:
                pool = list(WEAPON_TABLE)
        item_id = rng.choice(pool)
        target_tier = roll_upgrade_tier(rng.randint(0, 100))
        return {
            "item_id": item_id,
            "upgrade_level": max(0, target_tier - natural_weapon_tier(item_id)),
            "weapon_art": rng.choice([-1] + list(WEAPON_ART_TABLE)),
            "wep_effect": rng.choice([-1] + list(EFFECT_CAP_MAP)),
            "effect_tier": roll_effect_tier(rng.randint(0, 100)),
        }

    def _roll_talisman_drop(self, index: int, player: int) -> dict:
        """Deterministic roll for one "Randomized Talisman" filler instance, same seeding idea as
        _roll_weapon_drop (seed_name + index + player, so retries/reconnects reproduce the same
        talisman rather than re-rolling) but much simpler: talismans have no upgrade tier, Ash of
        War, or affinity to roll - just a uniform pick over game_data.TALISMAN_TABLE. Every other
        drop_item() argument is left at its default ("none"/no-op for a weapon-only field), which
        memory_writer.py's drop_item/the source CT script's dropItem() both already skip entirely
        for a non-Weapon item type.
        """
        rng = random.Random(f"{self.seed_name}:{index}:{player}:talisman")
        return {"item_id": rng.choice(list(TALISMAN_TABLE))}

    def _show_toast(self, text: str, style: str = "item",
                    duration: float = TOAST_DURATION_SECONDS) -> None:
        """Arms the overlay's center-top toast for TOAST_DURATION_SECONDS. Timing lives here
        (asyncio side), not in overlay.py - poll_loop's per-tick overlay update re-passes this
        same text on every tick until the expiry it set has passed, then lets it go back to None,
        so the Tk thread just displays whatever it's handed rather than running its own clock."""
        self._toast_text = text
        self._toast_style = style
        self._toast_expiry = time.monotonic() + duration

    async def _deliver_pending_drops(
        self, item_name: str, roll_fn, delivered_keys: set, event_type: str, log_label: str,
        toast_text: str,
    ) -> None:
        if self.item_drop_writer is None:
            return
        pending = self._accepted(item_name, self._pending_drop_keys(item_name, delivered_keys))
        if not pending:
            return
        loop = asyncio.get_running_loop()
        for index, player in pending:
            roll = roll_fn(index, player)
            ok = await loop.run_in_executor(
                None, functools.partial(self.item_drop_writer.drop_item, **roll)
            )
            if ok:
                delivered_keys.add((index, player))
                self._mark_offering_delivered(item_name)
                self._append_event({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": event_type,
                    "index": index,
                    "player": player,
                    **roll,
                })
                logger.info("Dropped %s 0x%X for index=%s player=%s.",
                            log_label, roll["item_id"], index, player)
                if self.overlay is not None:
                    self._show_toast(toast_text)
            else:
                # Not removed from the pending set - _pending_drop_keys() will offer it again on
                # the next Expedition entry, matching _sync_event_flags's retry shape.
                logger.warning("%s drop skipped for index=%s player=%s - game not ready, "
                                "will retry on next Expedition entry.", log_label, index, player)

    async def _deliver_pending_weapons(self) -> None:
        roll_fn = self._roll_weapon_drop
        if self.weapon_pool == "character_preferred":
            character = self.reader.read_character_class_name()
            if character is None:
                # Left pending, retried next tick - better than spending it on a random weapon.
                return
            roll_fn = functools.partial(self._roll_weapon_drop, character=character)
        await self._deliver_pending_drops(
            "Randomized Weapon", roll_fn, self._delivered_weapon_keys,
            "weapon_drop", "randomized weapon", "Weapon received"
        )

    async def _deliver_pending_talismans(self) -> None:
        await self._deliver_pending_drops(
            "Randomized Talisman", self._roll_talisman_drop, self._delivered_talisman_keys,
            "talisman_drop", "randomized talisman", "Talisman received"
        )

    # --- Otherworld Offerings (see offerings.py) ---
    # Off unless otherworld_offerings is on. Held offerings are just items still pending - the
    # delivery paths above and below only let through what the player has accepted.

    def _accepted(self, item_name: str, pending: set):
        """`pending` cut down to what's been accepted when `item_name` is held as an offering,
        else `pending` unchanged."""
        if self.otherworld_offerings and item_name in OFFERING_ITEMS:
            return self.offering_queue.take(item_name, pending)
        return pending

    def _mark_offering_delivered(self, item_name: str) -> None:
        if self.otherworld_offerings and item_name in OFFERING_ITEMS:
            self.offering_queue.delivered(item_name)

    def offerings_held(self) -> dict:
        """Item name -> (held, accepted) for every offering this slot receives, in OFFERING_ITEMS
        order."""
        delivered = {}
        if self.randomize_weapons:
            delivered["Randomized Weapon"] = self._delivered_weapon_keys
        if self.randomize_talismans:
            delivered["Randomized Talisman"] = self._delivered_talisman_keys
        if "Runes" in self.currency_items:
            for bundle in OFFERING_RUNES:
                delivered[bundle] = self._delivered_currency_keys["Runes"]
        return {
            name: (len(self._pending_drop_keys(name, delivered[name])),
                   self.offering_queue.queued(name))
            for name in OFFERING_ITEMS if name in delivered
        }

    def accept_offering(self, item_name: str, count: Optional[int]) -> str:
        """Accepts `count` (None = every held copy) of `item_name` and returns a line describing
        the result, for /accept and the Offerings tab."""
        if not self.otherworld_offerings:
            return "Otherworld Offerings are off for this slot."
        held = self.offerings_held()
        if item_name not in held:
            return f"This slot doesn't receive {item_name}s."
        count_held, _accepted = held[item_name]
        added = self.offering_queue.request(
            item_name, count_held if count is None else count, count_held
        )
        if not added:
            return f"No more {item_name}s held to accept."
        logger.info("Accepted %s %s offering(s).", added, item_name)
        return (f"Accepted {added} {item_name}{'s' if added != 1 else ''}. "
                f"{self.offering_status()}")

    def offering_status(self) -> str:
        """Why accepted offerings haven't arrived yet, or "" with none accepted."""
        if not self.offering_queue.any_queued():
            return ""
        if not self.reader.connected:
            return "Waiting for the game."
        if self._hub_exit_time is None:
            return "Arrives in your next Expedition."
        if time.monotonic() - self._hub_exit_time < EXPEDITION_ENTRY_SETTLE_SECONDS:
            return "Arrives once the Expedition has started."
        if self._offering_run_locked:
            return "Waiting - this run's boss or character isn't unlocked yet."
        if self._offering_flying:
            return "Weapons and talismans land once you're on the ground."
        return "Arriving now."

    # --- Currency grant write path (Murk, Runes, Sovereign Sigils) ---
    # Off unless the matching receive_* option is on. Unlike weapons/talismans, nothing is rolled
    # or dropped - every pending copy of a currency is summed and granted in one direct call.

    def _receives_in_run_items(self) -> bool:
        """True if anything is delivered during an Expedition (and so needs _hub_exit_time's
        settle window tracked) - weapon/talisman drops, Runes, traps, or Progressive Level/Flask."""
        return (self.randomize_weapons or self.randomize_talismans
                or "Runes" in self.currency_items or self.status_traps
                or self.progressive_levels or self.progressive_flasks)

    def _ensure_currency_ready(self) -> None:
        """Same "build once both an option and the game connection are known" shape as
        _ensure_item_drop_ready, for the same race-condition reason. Each currency's AOB is
        resolved independently - a failure only drops that one currency for the session. Also
        resolves its own WorldChrMan slot (for is_save_loaded(), Murk/Sigils' hub gate), kept
        separate from _worldchrman_slot for the same reason _all_bosses_worldchrman_slot is."""
        if not self.currency_items or not self.reader.connected or self.currency_writer is not None:
            return
        func_addrs = {}
        for currency in sorted(self.currency_items):
            try:
                func_addrs[currency] = self.reader.resolve_currency_target(currency)
            except PointerNotFoundError as e:
                logger.error("%s grant write path unavailable (%s) - disabling it this session, "
                             "the read-only tracker is unaffected.", currency, e)
                self.currency_items.discard(currency)
        if self.currency_items.intersection(HUB_CURRENCIES):
            try:
                self._currency_worldchrman_slot = self.reader.resolve_current_animation_target()
            except PointerNotFoundError as e:
                logger.error("Save-loaded read path unavailable (%s) - disabling Murk/Sovereign "
                             "Sigil grants this session.", e)
                self.currency_items.difference_update(HUB_CURRENCIES)
                func_addrs = {k: v for k, v in func_addrs.items() if k not in HUB_CURRENCIES}
        if not func_addrs:
            return
        self.currency_writer = NightreignCurrencyWriter(self.reader.pm, func_addrs)
        logger.info("Currency grant writer resolved for: %s.", ", ".join(sorted(func_addrs)))

    async def _deliver_pending_currency(self, currency: str) -> None:
        """Grants every received-but-undelivered bundle of `currency` (e.g. every pending "Murk
        Bundle"/"Large Murk Bundle"/"Titanic Murk Bundle" - see game_data.CURRENCY_BUNDLES) in one
        call. Same (index, player) dedup keys as _deliver_pending_drops. Marked delivered as soon as the call is
        dispatched and NEVER retried off the before/after counter read-back - those reads only go
        to the log: an unconfirmed counter offset that read wrong would otherwise re-grant every
        tick forever, a far worse failure than one missed grant."""
        if self.currency_writer is None or not self.currency_writer.supports(currency):
            return
        delivered_keys = self._delivered_currency_keys[currency]
        # (index, player) -> bundle item name, for every pending bundle of this currency.
        pending = {
            key: bundle
            for bundle in currency_bundle_names(currency)
            for key in self._accepted(bundle, self._pending_drop_keys(bundle, delivered_keys))
        }
        if not pending:
            return
        player_data = self.reader.read_player_data_base()
        if player_data is None:
            return  # transiently unreadable - retried next tick
        amount = min(sum(CURRENCY_BUNDLES[bundle][1] for bundle in pending.values()),
                     CURRENCY_GRANT_MAX)
        counter_offset = CURRENCY_COUNTER_OFFSETS[currency]
        before = self.reader.read_player_data_uint(counter_offset)
        ok = await asyncio.get_running_loop().run_in_executor(
            None, self.currency_writer.grant, currency, player_data, amount
        )
        if not ok:
            logger.warning("%s grant skipped - game not ready, will retry.", currency)
            return
        delivered_keys.update(pending)
        for bundle in pending.values():
            self._mark_offering_delivered(bundle)
        after = self.reader.read_player_data_uint(counter_offset)
        self._append_event({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "currency_grant",
            "currency": currency,
            "amount": amount,
            "bundles": sorted([index, player, bundle] for (index, player), bundle in pending.items()),
            "before": before,
            "after": after,
        })
        logger.info("Granted %s %s from %s; counter %s -> %s.", amount, currency,
                    ", ".join(sorted(pending.values())), before, after)
        if self.overlay is not None:
            self._show_toast(f"+{amount:,} {currency}")

    def _ensure_trap_ready(self) -> None:
        """Same "build once both an option and the game connection are known" shape as
        _ensure_currency_ready. Resolves its own WorldChrMan slot (PlayerIns and HP), kept separate
        from _worldchrman_slot for the same reason _all_bosses_worldchrman_slot is."""
        if not self.status_traps or not self.reader.connected or self.speffect_writer is not None:
            return
        try:
            func_addr = self.reader.resolve_speffect_target()
            self._trap_worldchrman_slot = self.reader.resolve_current_animation_target()
        except PointerNotFoundError as e:
            logger.error("Trap write path unavailable (%s) - traps won't go off this session, "
                         "the read-only tracker is unaffected.", e)
            return
        self.speffect_writer = NightreignSpEffectWriter(self.reader.pm, func_addr)
        logger.info("Trap SpEffect writer resolved.")

    def _maybe_start_trap(self) -> None:
        """Starts the oldest pending trap, one at a time and at most one per TRAP_COOLDOWN_SECONDS.
        Runs as a background task rather than awaited: a trap's applications are
        TRAP_APPLY_INTERVAL apart (several seconds in all), which would otherwise stall
        poll_loop's win detection."""
        if self.speffect_writer is None or self._trap_worldchrman_slot is None:
            return
        if self._trap_task is not None and not self._trap_task.done():
            return
        if (self._last_trap_time is not None
                and time.monotonic() - self._last_trap_time < TRAP_COOLDOWN_SECONDS):
            return
        pending = sorted(
            (key, name) for name in STATUS_TRAPS
            for key in self._pending_drop_keys(name, self._delivered_trap_keys)
        )
        if pending:
            key, name = pending[0]
            self._trap_task = asyncio.create_task(self._fire_trap(key, name))

    async def _fire_trap(self, key: tuple, name: str) -> None:
        """Applies one trap's SpEffect STATUS_TRAPS[name] times to the player. Skipped (and
        retried next tick) while the player is dead/downed, so a trap isn't wasted on a corpse.
        Marked delivered on the first application that runs, so a disconnect partway through
        can't fire it twice."""
        sp_effect_id, applications = STATUS_TRAPS[name]
        hp = self.reader.read_player_hp(self._trap_worldchrman_slot)
        if hp is None or hp[0] <= 0:
            return
        loop = asyncio.get_running_loop()
        applied = 0
        for i in range(applications):
            if i:
                await asyncio.sleep(TRAP_APPLY_INTERVAL)
            writer = self.speffect_writer
            player_ins = (self.reader.read_player_ins(self._trap_worldchrman_slot)
                          if writer is not None and self.reader.connected else None)
            if player_ins is None:
                break
            if not await loop.run_in_executor(None, writer.apply, player_ins, sp_effect_id):
                break
            if not applied:
                self._delivered_trap_keys.add(key)
                self._last_trap_time = time.monotonic()
                self._announce_trap(name, key[1])
            applied += 1
        if not applied:
            return
        index, player = key
        self._append_event({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "trap",
            "trap": name,
            "sp_effect_id": sp_effect_id,
            "applications": applied,
            "index": index,
            "player": player,
        })
        logger.info("%s went off (SpEffect %s x%s).", name, sp_effect_id, applied)

    def _announce_trap(self, name: str, sender: int) -> None:
        """Says what just happened and who sent it, as soon as a trap's first application lands -
        the in-game status banner alone doesn't explain where it came from. Toast for the player
        mid-fight (DeathLink's red style and duration), plus the "Client" logger so it also shows
        in the AP client window - this file's own logger doesn't reach that tab (see the
        EACDetectedError branch in poll_loop)."""
        if sender == self.slot:
            text = f"\u2620 {name}!"
            message = f"{name} went off (from your own world)."
        else:
            sender_name = self.player_names.get(sender, "Archipelago")
            text = f"\u2620 {name} from {sender_name}"
            message = f"{name} from {sender_name} went off."
        logging.getLogger("Client").info(message)
        if self.overlay is not None:
            self._show_toast(text, style="death_link", duration=DEATH_LINK_TOAST_SECONDS)

    # --- Metaprogression (Progressive Level / Progressive Flask) ---

    def _ensure_metaprogression_ready(self) -> None:
        """Same "build once both an option and the game connection are known" shape as
        _ensure_currency_ready. Only the level needs a resolved function - max flasks are a plain
        byte write."""
        if not self.progressive_levels or not self.reader.connected or self.level_writer is not None:
            return
        try:
            func_addr = self.reader.resolve_set_level_target()
        except PointerNotFoundError as e:
            logger.error("Progressive Level write path unavailable (%s) - your level won't be "
                         "raised this session, the read-only tracker is unaffected.", e)
            return
        self.level_writer = NightreignLevelWriter(self.reader.pm, func_addr)
        logger.info("Progressive Level writer resolved.")

    def _received_count(self, item_name: str) -> int:
        return sum(1 for i in self.items_received if lookup_id_to_name.get(i.item) == item_name)

    async def _apply_metaprogression_floors(self) -> None:
        """Raises the player's level and max flask charges to the floors this slot's received
        Progressive Level/Flask copies set (see game_data.level_floor/max_flask_floor). Only ever
        raises, so natural level-ups and flask pickups above the floor still count. Level is
        re-checked every tick, since it can drop mid-run; max flasks never drop, so they're only
        written once per Expedition (again if a new Progressive Flask arrives mid-run). A read of
        0 means PlayerGameData isn't populated yet and is skipped, never "raised"."""
        player_data = self.reader.read_player_data_base()
        if player_data is None:
            return

        now = time.monotonic()
        if self.level_writer is not None and (
            self._last_level_floor_attempt is None
            or now - self._last_level_floor_attempt >= LEVEL_FLOOR_RETRY_SECONDS
        ):
            level = self.reader.read_player_data_uint(PLAYER_LEVEL_OFFSET)
            floor = level_floor(self._received_count(PROGRESSIVE_LEVEL))
            if level and level < floor:
                self._last_level_floor_attempt = now
                ok = await asyncio.get_running_loop().run_in_executor(
                    None, self.level_writer.set_level, player_data, floor
                )
                if ok:
                    self._report_floor("level", level, floor, f"Level raised to {floor}")

        if self.progressive_flasks:
            floor = max_flask_floor(self._received_count(PROGRESSIVE_FLASK))
            if self._flask_floor_applied is None or self._flask_floor_applied < floor:
                flasks = self.reader.read_player_data_ubyte(MAX_FLASK_OFFSET)
                if not flasks:
                    return
                if flasks >= floor:
                    self._flask_floor_applied = floor
                elif set_max_flasks(self.reader.pm, player_data + MAX_FLASK_OFFSET, floor):
                    self._flask_floor_applied = floor
                    self._report_floor("max_flasks", flasks, floor, f"Max flasks raised to {floor}")

    def _report_floor(self, stat: str, before: int, after: int, toast: str) -> None:
        self._append_event({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "metaprogression_floor",
            "stat": stat,
            "before": before,
            "after": after,
        })
        logger.info("Raised %s from %s to %s.", stat, before, after)
        if self.overlay is not None:
            self._show_toast(toast)

    # --- Per-run local state file ---
    # One file per AP world/slot (keyed by seed + slot name), so switching multiworld games
    # never mixes up which locations were sent. Also logs wins and unresolved boss_id detections.

    def _run_state_key(self) -> tuple[str, str]:
        seed_name = self.seed_name or "unknown_seed"
        slot_name = self.player_names.get(self.slot, self.auth or "unknown_slot")
        return seed_name, slot_name

    def _open_run_state(self) -> None:
        seed_name, slot_name = self._run_state_key()
        directory = Utils.user_path("nightreign")
        os.makedirs(directory, exist_ok=True)
        filename = (
            f"{_safe_filename_component(seed_name)}_{_safe_filename_component(slot_name)}.json"
        )
        self.run_state_path = os.path.join(directory, filename)

        if os.path.exists(self.run_state_path):
            try:
                with open(self.run_state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.checked_location_ids = {int(x) for x in data.get("checked_locations", [])}
                self.win_count = int(data.get("win_count", 0))
                self.weak_reward_counts = _counts_from_json(data.get("weak_reward_counts", []))
                self.strong_reward_counts = _counts_from_json(data.get("strong_reward_counts", []))
                self._delivered_weapon_keys = {
                    (int(index), int(player))
                    for index, player in data.get("delivered_weapon_keys", [])
                }
                self._delivered_talisman_keys = {
                    (int(index), int(player))
                    for index, player in data.get("delivered_talisman_keys", [])
                }
                saved_currency_keys = data.get("delivered_currency_keys", {})
                self._delivered_currency_keys = {
                    name: {
                        (int(index), int(player))
                        for index, player in saved_currency_keys.get(name, [])
                    }
                    for name in CURRENCY_COUNTER_OFFSETS
                }
                self._delivered_trap_keys = {
                    (int(index), int(player))
                    for index, player in data.get("delivered_trap_keys", [])
                }
            except (json.JSONDecodeError, OSError, ValueError) as e:
                logger.warning(
                    "Could not read existing Nightreign run state at %s: %s", self.run_state_path, e
                )
                self.checked_location_ids = set()
                self.win_count = 0
                self.weak_reward_counts = {}
                self.strong_reward_counts = {}
                self._delivered_weapon_keys = set()
                self._delivered_talisman_keys = set()
                self._delivered_currency_keys = {name: set() for name in CURRENCY_COUNTER_OFFSETS}
                self._delivered_trap_keys = set()
        else:
            self.checked_location_ids = set()
            self.win_count = 0
            self.weak_reward_counts = {}
            self.strong_reward_counts = {}
            self._delivered_weapon_keys = set()
            self._delivered_talisman_keys = set()
            self._delivered_currency_keys = {name: set() for name in CURRENCY_COUNTER_OFFSETS}
            self._delivered_trap_keys = set()
            self._write_run_state(seed_name, slot_name, events=[])

        logger.info("Nightreign run state file: %s", self.run_state_path)

    def _write_run_state(self, seed_name: str, slot_name: str, events: list) -> None:
        data = {
            "seed_name": seed_name,
            "slot_name": slot_name,
            "checked_locations": sorted(self.checked_location_ids),
            "win_count": self.win_count,
            "weak_reward_counts": _counts_to_json(self.weak_reward_counts),
            "strong_reward_counts": _counts_to_json(self.strong_reward_counts),
            "delivered_weapon_keys": sorted(list(key) for key in self._delivered_weapon_keys),
            "delivered_talisman_keys": sorted(list(key) for key in self._delivered_talisman_keys),
            "delivered_currency_keys": self._currency_keys_to_json(),
            "delivered_trap_keys": sorted(list(key) for key in self._delivered_trap_keys),
            "events": events,
        }
        with open(self.run_state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _currency_keys_to_json(self) -> dict:
        return {
            name: sorted(list(key) for key in keys)
            for name, keys in self._delivered_currency_keys.items()
        }

    def _append_event(self, event: dict) -> None:
        if not self.run_state_path:
            return
        seed_name, slot_name = self._run_state_key()
        try:
            with open(self.run_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            data = {
                "seed_name": seed_name, "slot_name": slot_name,
                "checked_locations": [], "win_count": 0, "delivered_weapon_keys": [],
                "delivered_talisman_keys": [], "events": [],
            }
        data["checked_locations"] = sorted(self.checked_location_ids)
        data["win_count"] = self.win_count
        data["weak_reward_counts"] = _counts_to_json(self.weak_reward_counts)
        data["strong_reward_counts"] = _counts_to_json(self.strong_reward_counts)
        data["delivered_weapon_keys"] = sorted(list(key) for key in self._delivered_weapon_keys)
        data["delivered_talisman_keys"] = sorted(
            list(key) for key in self._delivered_talisman_keys
        )
        data["delivered_currency_keys"] = self._currency_keys_to_json()
        data["delivered_trap_keys"] = sorted(list(key) for key in self._delivered_trap_keys)
        data.setdefault("events", []).append(event)
        with open(self.run_state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # --- Memory polling ---

    async def poll_loop(self) -> None:
        """Polls the game process for wins and other state changes, and handles them.
        """
        while True:
            try:
                if not self.reader.connected:
                    # A stale writer holds addresses from a now-dead process handle - don't let
                    # _sync_event_flags() reuse it. Drop synced-flag bookkeeping too, so a fresh
                    # connect re-verifies rather than trusting state from a writer that's gone.
                    self.writer = None
                    self._synced_flags.clear()
                    self.item_drop_writer = None
                    self.currency_writer = None
                    self._currency_worldchrman_slot = None
                    self.speffect_writer = None
                    self._trap_worldchrman_slot = None
                    self.level_writer = None
                    self._last_level_floor_attempt = None
                    self._flask_floor_applied = None
                    self._worldchrman_slot = None
                    self._hub_exit_time = None
                    self._hub_entry_time = None
                    self._all_bosses_unlock_addr = None
                    self._all_bosses_worldchrman_slot = None
                    self._all_bosses_unlocked_this_hub = False
                    self._locked_boss_warned = False
                    self._locked_character_warned = False
                    self._locked_run_drop_withheld_warned = False
                    self._last_in_hub = None
                    self._win_handled_this_run = False
                    self._arena_trace = None
                    self._death_link_detector.reset()
                    self._death_link_last_in_hub = None
                    try:
                        if self.reader.connect():
                            logger.info("Connected to nightreign.exe")
                            self._ensure_gating_ready()
                            self._ensure_overlay_ready()
                            if self.gate_boss_access or self.gate_character_access:
                                asyncio.create_task(self._sync_event_flags())
                            self._ensure_item_drop_ready()
                            self._ensure_animation_ready()
                            self._ensure_currency_ready()
                            self._ensure_trap_ready()
                            self._ensure_metaprogression_ready()
                            self._ensure_all_bosses_unlock_ready()
                        else:
                            await asyncio.sleep(RECONNECT_INTERVAL)
                            continue
                    except EACDetectedError as e:
                        # Unlike PointerNotFoundError below, this isn't retry-with-backoff: nothing
                        # about this client's read/write behavior is safe to run while EAC is
                        # loaded, so the whole client - not just the memory-polling task - has to
                        # stop.
                        message = (
                            f"EasyAntiCheat detected - {e} Shutting down; relaunch the game "
                            "offline with Anti-Cheat disabled, then restart this client."
                        )
                        logger.error(message)
                        # logger ("NightreignClient") isn't one of NightreignManager's
                        # logging_pairs, so on its own this would never reach the GUI's visible
                        # "Archipelago" tab (only console/file output) - this is the one message
                        # in this file that must not be missed, so also log it via "Client", the
                        # logger that tab actually follows.
                        logging.getLogger("Client").error(message)
                        # Mirrors CommonClient.py's own _cmd_exit ("/exit") exactly: exit_event
                        # alone only unblocks main()'s `await ctx.exit_event.wait()` - nothing
                        # in kvui.py watches exit_event to stop the GUI itself (it's set FROM
                        # GameManager.on_stop, not consumed by it), so without also calling
                        # ui.stop() here, ctx.shutdown()'s `await self.ui_task` blocks forever on a
                        # Kivy app nothing ever told to close, and the client (and this warning)
                        # never actually goes away - live-confirmed: the GUI kept running and
                        # connected to the server normally after this branch logged and returned.
                        if self.ui:
                            self.ui.stop()
                        self.exit_event.set()
                        return
                    except PointerNotFoundError as e:
                        logger.error("%s - is the game up to date with this client? Retrying in "
                                    "%ss.", e, BUILD_MISMATCH_BACKOFF)
                        await asyncio.sleep(BUILD_MISMATCH_BACKOFF)
                        continue

                # Fallback win signal - the primary one is the buff-pick counter's Nightlord-kill
                # tick below, which also covers Night Aspect (this pulse never fires for it).
                pulse = self.reader.read_outcome_pulse()
                if pulse == 1 and self._last_pulse == 0:
                    await self._trigger_win("outcome pulse")
                if pulse is not None:
                    self._last_pulse = pulse

                if (self.gate_boss_access or self.gate_character_access) and self.writer is not None:
                    # Retried every tick, not just on Connected/ReceivedItems: freed_nightlords/
                    # freed_characters never arrive as a ReceivedItems packet, so this is the only
                    # retry path for a flag write that failed from a transiently-unreadable pointer.
                    # A no-op once synced.
                    await self._sync_event_flags()

                # Read once per tick and shared below - True in hub/menu/loading, False in an
                # active run, None if transiently unreadable (e.g. a scene transition).
                in_hub = self.reader.read_hub_state()
                if in_hub is False and self._last_in_hub is True:
                    # Re-arm win detection on Expedition entry only, not on hub arrival: the pulse
                    # can still be held high after in_hub flips True (the results screen), and
                    # re-arming there would let it count the same win twice.
                    self._win_handled_this_run = False
                    self._arena_trace = None
                if in_hub is True and self._last_in_hub is False:
                    self._report_arena_exit_without_win()
                if in_hub is not None:
                    self._last_in_hub = in_hub

                if self.death_link_mode != "off" or self._pending_death_link is not None:
                    await self._poll_death_link(in_hub)

                if in_hub is False:
                    # Re-arm on every Expedition, so the next hub visit patches once more.
                    self._all_bosses_unlocked_this_hub = False
                if (self.unlock_all_bosses_in_game and self.writer is not None
                        and self._all_bosses_unlock_addr is not None
                        and self._all_bosses_worldchrman_slot is not None and in_hub
                        and not self._all_bosses_unlocked_this_hub):
                    # in_hub alone can't tell the main menu apart from the actual hub (both read
                    # True - see the comment above), so also require WorldChrMan to resolve to a
                    # live object (see memory_reader.py's is_save_loaded()) before patching menu
                    # code - firing this at the main menu, before any save is even loaded, is
                    # untested and deliberately avoided. Written once per hub visit rather than
                    # every tick: it's a write to live game code, so keep it as rare as possible. A
                    # failed write leaves the latch unset and retries next tick.
                    if self.reader.is_save_loaded(self._all_bosses_worldchrman_slot):
                        self._all_bosses_unlocked_this_hub = self.writer.set_all_bosses_unlocked(
                            self._all_bosses_unlock_addr, True
                        )

                if self.gate_boss_access:
                    if in_hub:
                        # Back in the hub (or a fresh/unreadable tick before the first Expedition
                        # entry this connection) - re-arm so the next Expedition entry gets its
                        # own check, one warning per run rather than once ever.
                        self._locked_boss_warned = False
                    elif in_hub is False and not self._locked_boss_warned:
                        # boss_id can lag a tick or two behind the hub-exit edge (same drift the
                        # win-detection path tolerates) - read_boss_id() returning "unset"/
                        # "unreadable" here just means try again next tick, not a bad Expedition.
                        boss = self.reader.read_boss_id()
                        if boss.status == "matched":
                            self._locked_boss_warned = True
                            self._warn_if_boss_locked(
                                boss.name, bool(self.reader.read_everdark_flag())
                            )

                if self.gate_character_access:
                    if in_hub:
                        self._locked_character_warned = False
                    elif in_hub is False and not self._locked_character_warned:
                        character_name = self.reader.read_character_class_name()
                        if character_name is not None:
                            self._locked_character_warned = True
                            self._warn_if_character_locked(character_name)

                if self._receives_in_run_items():
                    # Tracks how long in_hub has continuously been False, so the settle-time check
                    # below can tell "just exited the hub" from "been in the Expedition a while" -
                    # reset on True so each fresh Expedition gets its own settle window.
                    if in_hub:
                        self._hub_exit_time = None
                        self._locked_run_drop_withheld_warned = False
                        # Every Expedition starts back at the game's own max flasks.
                        self._flask_floor_applied = None
                    elif in_hub is False and self._hub_exit_time is None:
                        self._hub_exit_time = time.monotonic()

                if self.currency_items.intersection(HUB_CURRENCIES):
                    if not in_hub:
                        self._hub_entry_time = None
                    elif self._hub_entry_time is None:
                        self._hub_entry_time = time.monotonic()
                    elif (time.monotonic() - self._hub_entry_time >= HUB_ENTRY_SETTLE_SECONDS
                          and self._currency_worldchrman_slot is not None
                          and self.reader.is_save_loaded(self._currency_worldchrman_slot)):
                        # in_hub alone also reads True at the main menu (see the
                        # unlock_all_bosses_in_game block above) - is_save_loaded() rules that out,
                        # so Murk/Sigils are only ever granted into a loaded save.
                        for currency in HUB_CURRENCIES:
                            if currency in self.currency_items:
                                await self._deliver_pending_currency(currency)

                if in_hub:
                    # Back in the hub (or a fresh/unreadable tick before the first Expedition
                    # entry this connection) - reset so a stale reading from the previous
                    # Expedition can't produce a false edge/delta on the next one (these all
                    # reset to 0/DAY_PHASE_DAY_1 at the start of each real Expedition anyway).
                    self._last_day_phase = None
                    self._last_weak_reward_raw = None
                    self._last_buff_pick_raw = None
                elif in_hub is False:
                    extra_check_timestamp = datetime.now(timezone.utc).isoformat()

                    # Night 1/Night 2 Clear - always read (cheap); _credit_night_phase_check itself
                    # skips sending when night_checks is off.
                    day_phase = self.reader.read_day_phase()
                    if day_phase is not None:
                        if self._last_day_phase == DAY_PHASE_NIGHT_1 and day_phase == DAY_PHASE_DAY_2:
                            await self._credit_night_phase_check(
                                location_name_night1, "night1_clear", extra_check_timestamp,
                            )
                        if self._last_day_phase == DAY_PHASE_NIGHT_2 and day_phase == DAY_PHASE_DAY_3:
                            await self._credit_night_phase_check(
                                location_name_night2, "night2_clear", extra_check_timestamp,
                            )
                        self._last_day_phase = day_phase

                    if self.weak_reward_checks:
                        weak_raw = self.reader.read_weapon_pickup_count()
                        if weak_raw is not None:
                            if (self._last_weak_reward_raw is not None
                                    and weak_raw > self._last_weak_reward_raw):
                                await self._credit_extra_check(
                                    self.weak_reward_counts, location_name_weak_reward,
                                    self.weak_reward_thresholds, "weak_reward",
                                    extra_check_timestamp,
                                    increment=weak_raw - self._last_weak_reward_raw,
                                )
                            self._last_weak_reward_raw = weak_raw

                    # Always read, not just when strong_reward_checks is on: this counter's tick in
                    # the Day 3 arena is the primary Nightlord-kill signal (see
                    # game_data.is_nightlord_kill_tick).
                    buff_raw = self.reader.read_buff_pick_count()
                    self._trace_arena(day_phase, buff_raw)
                    if buff_raw is not None:
                        if is_nightlord_kill_tick(self._last_buff_pick_raw, buff_raw, day_phase):
                            await self._trigger_win("buff-pick counter in the Nightlord arena")
                        if (self.strong_reward_checks and self._last_buff_pick_raw is not None
                                and buff_raw > self._last_buff_pick_raw):
                            await self._credit_extra_check(
                                self.strong_reward_counts, location_name_strong_reward,
                                self.strong_reward_thresholds, "strong_reward",
                                extra_check_timestamp,
                                increment=buff_raw - self._last_buff_pick_raw,
                            )
                        self._last_buff_pick_raw = buff_raw

                if (
                    self._receives_in_run_items()
                    and in_hub is False
                    and self._hub_exit_time is not None
                    and time.monotonic() - self._hub_exit_time >= EXPEDITION_ENTRY_SETTLE_SECONDS
                ):
                    # Traps aren't rewards, so unlike drops below they still go off on a locked run.
                    if self.status_traps:
                        self._maybe_start_trap()
                    # Nothing is spent raising level/flasks, so this also applies on a locked run.
                    if self.progressive_levels or self.progressive_flasks:
                        await self._apply_metaprogression_floors()
                    self._offering_run_locked = self._current_run_is_locked()
                    if self._offering_run_locked:
                        # Don't spend an earned weapon/talisman drop on a run that's on a
                        # not-yet-unlocked boss/character - _handle_win would refuse to send a check
                        # for this same run's win (locked_boss_win_skipped/
                        # locked_character_win_skipped), so delivering here would just burn the item
                        # for nothing. Left pending, not lost: _delivered_weapon_keys/
                        # _delivered_talisman_keys never gets marked, so the same item is retried on
                        # a later, unlocked run. Warned once per run, not every tick, to avoid log
                        # spam for the run's full remaining duration.
                        if not self._locked_run_drop_withheld_warned:
                            self._locked_run_drop_withheld_warned = True
                            logger.info(
                                "Withholding weapon/talisman/rune deliveries this run - the "
                                "current boss and/or character isn't unlocked for this slot yet."
                            )
                    else:
                        # Runes are a counter increment, not a ground drop - no grounded/flight
                        # requirement beyond the settle window above.
                        if "Runes" in self.currency_items:
                            await self._deliver_pending_currency("Runes")
                        # Level-triggered every tick, not edge-triggered on hub-exit: a pending drop
                        # needs both "in an Expedition" and "not mid-flight" (live-tested, see
                        # game_data.py) to land. Safe to retry: _delivered_weapon_keys/
                        # _delivered_talisman_keys dedupe.
                        animation = (
                            self.reader.read_current_animation(self._worldchrman_slot)
                            if self._worldchrman_slot is not None else None
                        )
                        self._offering_flying = animation is None or is_flying_animation(animation)
                        if not self._offering_flying:
                            if self.randomize_weapons:
                                await self._deliver_pending_weapons()
                            if self.randomize_talismans:
                                await self._deliver_pending_talismans()

                if self.overlay is not None:
                    # Boss/character debug panel - always updated regardless of gate_boss_access,
                    # since win detection matters for every player. Read every tick in both the hub
                    # and an Expedition, to compare readings across that boundary (skin bugs).
                    debug_boss = self.reader.read_boss_id()
                    boss_raw = debug_boss.raw
                    boss_desc = debug_boss.name or debug_boss.message or debug_boss.status
                    character = self.reader.read_character_class_name()
                    everdark = self.reader.read_everdark_flag()

                    # Center-top "Weapon/Talisman received" toast - _show_toast() sets the expiry once
                    # on a successful drop; every tick until it passes re-sends the same text so the
                    # Tk thread keeps showing it, and once passed this clears it back to None.
                    toast_text = None
                    if self._toast_expiry is not None:
                        if time.monotonic() < self._toast_expiry:
                            toast_text = self._toast_text
                        else:
                            self._toast_text = None
                            self._toast_expiry = None

                    # pid is refreshed here too, not just at overlay construction - the game process
                    # can restart under a new pid without the overlay being torn down/rebuilt
                    # (see the `self.overlay is None` guard), or it'd hunt a dead process forever.
                    self.overlay.state.update(
                        self.reader.pm.process_id, boss_raw, boss_desc, character, everdark,
                        toast_text, self._toast_style,
                    )
            except Exception:
                logger.exception("Error in Nightreign poll loop")
            await asyncio.sleep(POLL_INTERVAL)

    # --- DeathLink ---
    # See death_link.py for how a down/death is detected and why a down caused by a received
    # DeathLink is never sent back out.

    def set_death_link_mode(self, mode: str, from_command: bool = False) -> None:
        self.death_link_mode = mode
        if from_command:
            self._death_link_overridden = True
        self._death_link_detector.reset()
        asyncio.create_task(self.update_death_link(mode != "off"))
        self._ensure_animation_ready()

    def on_deathlink(self, data: dict) -> None:
        super().on_deathlink(data)
        if self.death_link_mode != "off":
            # Applied (or dropped) on the next poll tick, which has the live run/HP state.
            self._pending_death_link = data

    async def _poll_death_link(self, in_hub: Optional[bool]) -> None:
        pending, self._pending_death_link = self._pending_death_link, None
        source = pending.get("source", "someone") if pending else None
        now = time.monotonic()

        if in_hub:
            if self._death_link_last_in_hub is False and self._death_link_detector.run_ended(
                    self.death_link_mode, won=self._win_handled_this_run):
                await self._send_death_link()
            self._death_link_last_in_hub = True
            if pending:
                logger.info("DeathLink from %s ignored - not in an Expedition.", source)
            return
        if in_hub is None or self._worldchrman_slot is None:
            if pending:
                logger.info("DeathLink from %s ignored - game state unreadable right now.", source)
            return
        self._death_link_last_in_hub = False

        hp_reading = self.reader.read_player_hp(self._worldchrman_slot)
        animation = self.reader.read_current_animation(self._worldchrman_slot)
        if pending:
            self._apply_death_link(pending, hp_reading, animation, now)
        hp, max_hp = hp_reading if hp_reading else (None, None)
        if self._death_link_detector.update(hp, max_hp, animation, self.death_link_mode, now):
            await self._send_death_link()

    def _apply_death_link(self, data: dict, hp_reading: Optional[tuple], animation: Optional[int],
                          now: float) -> None:
        source = data.get("source", "someone")
        if hp_reading is None or hp_reading[0] <= 0 or self._death_link_detector.downed:
            logger.info("DeathLink from %s ignored - already down.", source)
            return
        if animation is not None and is_flying_animation(animation):
            # Mid-flight (the Expedition fly-in, or respawning after a death) - untested there.
            logger.info("DeathLink from %s ignored - mid-flight.", source)
            return
        address = self.reader.player_hp_address(self._worldchrman_slot)
        if address is None or not set_player_hp(self.reader.pm, address, 0):
            logger.warning("DeathLink from %s couldn't be applied - HP write failed.", source)
            return
        self._death_link_detector.link_applied(now)
        cause = data.get("cause") or f"{source} died"
        if self.overlay is not None:
            self._show_toast(f"\u2620 DeathLink: {cause}", style="death_link",
                             duration=DEATH_LINK_TOAST_SECONDS)

    async def _send_death_link(self) -> None:
        name = self.player_names.get(self.slot, self.auth or "Someone")
        await self.send_death(f"{name} succumbed to the night.")
        if self.overlay is not None:
            self._show_toast("\u2620 DeathLink sent", style="death_link")

    def _resolve_win_context(self) -> Optional[tuple]:
        """Reads boss_id/everdark/character together and returns (nightlord, everdark, character)
        when a check-worthy Nightlord (and, in per_character_checks mode, character) is currently
        resolvable - None otherwise. Mirrors the gating at the top of _handle_win, but reusable by
        the Night 1/Night 2/weak/strong reward tracks below, which fire from poll_loop
        independently of the win pulse _handle_win itself reacts to."""
        boss = self.reader.read_boss_id()
        if boss.status != "matched":
            return None
        everdark = bool(self.reader.read_everdark_flag())
        is_everdark = everdark and boss.name in EVERDARK_NIGHTLORDS
        if everdark and not is_everdark:
            return None
        if is_everdark and boss.name not in self.everdark_nightlords:
            return None
        character_name = self.reader.read_character_class_name()
        if self.per_character_checks and character_name is None:
            return None
        return boss.name, is_everdark, (character_name if self.per_character_checks else None)

    def _access_owned(self, nightlord: str, everdark: bool, character: Optional[str]) -> bool:
        """True if this slot has already earned access to `nightlord` (or its Everdark Sovereign)
        and, when per_character_checks and character is not None, to `character` too - mirrors
        _handle_win's own gate_boss_access/gate_character_access checks, reused by the Night 1/
        Night 2/weak/strong reward tracks below since they fire independently of that method."""
        owned = self._owned_item_names()
        if character is not None and self.gate_character_access:
            if f"{character} Character Access" not in owned:
                return False
        if self.gate_boss_access:
            access_name = f"Everdark {nightlord} Access" if everdark else f"{nightlord} Access"
            if access_name not in owned:
                return False
        return True

    async def _credit_threshold(
        self, new_total: int, thresholds: list, name_fn, event_type: str,
    ) -> None:
        """Shared cumulative-counter crediting logic used by win_count and the weak/strong reward
        tracks (via _credit_extra_check below) - NOT used by nightlord bonus checks or Night 1/
        Night 2 Clear, neither of which is a cumulative counter (see _handle_win's dedicated bonus-
        sending block and _credit_single_check instead). Walks `thresholds` up to new_total (not
        just the one just crossed, so a stale/
        hand-edited run state file can never leave an earlier threshold's check permanently
        un-sent) and sends any not yet in self.checked_location_ids. name_fn(count) must return
        that threshold's location name. Callers are responsible for updating their own counter and
        appending their own per-tick run-state event before calling this - this only handles the
        threshold-crossing side effect (logging + check_locations), not the raw-tick bookkeeping,
        since that bookkeeping's shape (and whether it fires unconditionally) differs per family."""
        newly_earned = []  # (location_id, name)
        for threshold in thresholds:
            if threshold > new_total:
                break
            name = name_fn(threshold)
            location_id = location_name_to_id.get(name)
            if location_id is not None and location_id not in self.checked_location_ids:
                self.checked_location_ids.add(location_id)
                newly_earned.append((location_id, name))
        if not newly_earned:
            return
        for _location_id, name in newly_earned:
            logger.info("%s threshold reached: %s (total=%s)", event_type, name, new_total)
        await self.check_locations([location_id for location_id, _name in newly_earned])

    async def _credit_extra_check(
        self, counts: dict, name_fn, thresholds: list, event_type: str, timestamp: str,
        increment: int = 1,
    ) -> None:
        """Shared body for the weak/strong reward tracks (the only two extra check families that
        are genuinely cumulative counters): resolves the current Nightlord/character/everdark
        context (_resolve_win_context) and, only if this slot has actually earned access to it
        (_access_owned), advances the matching `counts` entry by `increment` (a reward counter's
        raw delta since the last poll), appends a run-state event for the raw tick (same "log every
        tick" fidelity as _handle_win_count below), and credits any newly-crossed threshold via
        _credit_threshold. A no-op if the context can't be resolved, isn't owned yet, or
        `thresholds` is empty (the family's toggle is off) - same posture as _handle_win's own
        locked_boss_win_skipped/locked_character_win_skipped guards."""
        if not thresholds:
            return
        ctx = self._resolve_win_context()
        if ctx is None:
            return
        nightlord, everdark, character = ctx
        if not self._access_owned(nightlord, everdark, character):
            return
        key = (nightlord, character, everdark)
        new_total = counts.get(key, 0) + increment
        counts[key] = new_total
        self._append_event({
            "timestamp": timestamp, "type": event_type, "key": list(key), "total": new_total,
        })
        await self._credit_threshold(
            new_total, thresholds,
            lambda count, nightlord=nightlord, character=character, everdark=everdark:
                name_fn(nightlord, count, character, everdark),
            event_type,
        )

    async def _credit_single_check(self, name: str, event_type: str, timestamp: str) -> None:
        """Sends one non-cumulative location once - self.checked_location_ids alone prevents a
        repeat event from re-sending it, the same way the base "Defeat X"/nightlord-bonus locations
        already rely on that set rather than a counter. Used by _credit_night_phase_check below."""
        location_id = location_name_to_id.get(name)
        if location_id is None or location_id in self.checked_location_ids:
            return
        self.checked_location_ids.add(location_id)
        logger.info("%s check sent: %s", event_type, name)
        self._append_event({"timestamp": timestamp, "type": event_type, "location": name})
        await self.check_locations([location_id])

    async def _credit_night_phase_check(self, name_fn, event_type: str, timestamp: str) -> None:
        """Shared body for the Night 1/Night 2 Clear checks - each Nightlord/character/everdark
        combo has exactly one location (not a cumulative counter, unlike weak/strong reward above),
        sent via _credit_single_check once this slot has both a resolvable context
        (_resolve_win_context) and access to it (_access_owned). Does nothing with slot_data's
        night_checks off (see game_data.py's DAY_PHASE_* constants)."""
        if not self.night_checks:
            return
        ctx = self._resolve_win_context()
        if ctx is None:
            return
        nightlord, everdark, character = ctx
        if not self._access_owned(nightlord, everdark, character):
            return
        await self._credit_single_check(name_fn(nightlord, character, everdark), event_type, timestamp)

    async def _handle_win_count(self, timestamp: str) -> None:
        """Increments this seed's cumulative win count and sends any newly-crossed threshold's
        location. Deliberately independent of gate_boss_access/gate_character_access/
        per_character_checks/included_nightlords/included_characters below - a win-count threshold
        isn't tied to any specific boss or character, so every real win counts toward it the same
        way Deadlock's own ungated wins_total does."""
        self.win_count += 1
        self._append_event({"timestamp": timestamp, "type": "win_count", "win_count": self.win_count})
        await self._credit_threshold(
            self.win_count, self.win_count_thresholds, location_name_win_count, "win_count",
        )

    def _trace_arena(self, day_phase: Optional[int], buff_raw: Optional[int]) -> None:
        """Diagnostics only: records the win signals seen in the Day 3 Nightlord arena so a run
        that ends there without a detected win (see _report_arena_exit_without_win) leaves enough
        in the log/event file to tell which signal failed. Night Aspect's kill-tick trigger rests
        on one live run, so this is what a failed report needs to come with."""
        if day_phase != DAY_PHASE_DAY_3:
            return
        if self._arena_trace is None:
            boss = self.reader.read_boss_id()
            self._arena_trace = {
                "raw_boss_id": boss.raw, "boss": boss.name, "buff_picks_at_entry": buff_raw,
                "buff_picks_last": buff_raw, "pulse_seen": False,
            }
            logger.info("Entered the Nightlord arena (boss_id=%s, %s, buff_picks=%s).",
                        boss.raw, boss.name or boss.status, buff_raw)
            return
        if buff_raw is not None and buff_raw != self._arena_trace["buff_picks_last"]:
            logger.info("Nightlord arena: buff-pick counter %s -> %s.",
                        self._arena_trace["buff_picks_last"], buff_raw)
            self._arena_trace["buff_picks_last"] = buff_raw
        if self._last_pulse == 1:
            self._arena_trace["pulse_seen"] = True

    def _report_arena_exit_without_win(self) -> None:
        if self._arena_trace is None or self._win_handled_this_run:
            return
        trace = self._arena_trace
        self._arena_trace = None
        logger.warning(
            "Left the Nightlord arena without detecting a win (boss_id=%s, buff_picks %s -> %s, "
            "outcome pulse %s). If you won this fight, please report it with this log file.",
            trace["raw_boss_id"], trace["buff_picks_at_entry"], trace["buff_picks_last"],
            "seen" if trace["pulse_seen"] else "never fired",
        )
        self._append_event({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "arena_exit_without_win",
            **trace,
        })

    async def _trigger_win(self, source: str) -> None:
        """Runs _handle_win at most once per Expedition. Two independent signals can report the
        same win - the buff-pick counter's Nightlord-kill tick and, ~7s later, the outcome pulse -
        and without this a normal win would double-increment win_count. Re-armed on Expedition
        entry in poll_loop."""
        if self._win_handled_this_run:
            return
        self._win_handled_this_run = True
        logger.info("Nightlord win detected via %s.", source)
        await self._handle_win()

    async def _handle_win(self) -> None:
        boss = self.reader.read_boss_id()
        character_name = self.reader.read_character_class_name()
        timestamp = datetime.now(timezone.utc).isoformat()

        if self.win_count_checks and boss.status == "matched":
            await self._handle_win_count(timestamp)

        if self.per_character_checks and character_name is None:
            logger.warning("Detected a win, but couldn't read the character class - skipping "
                            "this check.")
            return

        if (self.per_character_checks and self.gate_character_access
                and f"{character_name} Character Access" not in self._owned_item_names()):
            # The user's own requirement for this feature: no check for a character this slot
            # hasn't unlocked via AP yet, even though nothing in-game should let the player select
            # it (gate_character_access's write path locks it out) - a defense-in-depth guard for
            # any case where that didn't hold (e.g. a pre-existing save, a missed/failed flag sync).
            logger.info(
                "Win detected as %s, but this slot hasn't received %s's Character Access item "
                "yet - not sending.", character_name, character_name,
            )
            self._append_event({
                "timestamp": timestamp,
                "type": "locked_character_win_skipped",
                "character": character_name,
            })
            return

        if boss.status != "matched":
            message = (
                boss.message or f"boss_id {boss.raw} could not be resolved (status={boss.status})"
            )
            logger.warning(message)
            self._append_event({
                "timestamp": timestamp,
                "type": "unmatched_boss",
                "character": character_name,
                "raw_boss_id": boss.raw,
                "status": boss.status,
                "message": message,
            })
            return

        # Read everdark before the access-item gate below: Everdark Sovereigns are separate bosses
        # from their base Nightlord (own checks, own "Everdark X Access" item - see Items.py), so
        # which access item this win needs to be checked against depends on it.
        everdark = bool(self.reader.read_everdark_flag())  # None (unreadable) treated as False
        has_everdark_form = boss.name in EVERDARK_NIGHTLORDS

        if everdark and not has_everdark_form:
            # An Everdark win, but this Nightlord has no Everdark form (shouldn't happen - Night
            # Aspect/Dreglord are the only ones, and neither is fought via a normal win pulse the
            # same way). Deliberately not falling back to crediting the normal "Defeat X" location
            # instead - that would reward a harder fight with a check that doesn't reflect what
            # actually happened.
            logger.info(
                "Win detected as Everdark %s, but this Nightlord has no Everdark form - not "
                "sending.", boss.name,
            )
            self._append_event({
                "timestamp": timestamp, "type": "everdark_win_skipped", "character": character_name,
                "boss": boss.name, "raw_boss_id": boss.raw, "reason": "no_everdark_form",
            })
            return

        if everdark and boss.name not in self.everdark_nightlords:
            # self.everdark_nightlords (from slot_data's everdark_nightlords - see __init__.py's
            # create_regions()) is exactly this slot's included_nightlords "Everdark X" entries. A
            # Nightlord with a structural Everdark form but no entry here has no location/Access
            # item at all for it in this slot.
            logger.info(
                "Win detected as Everdark %s, but this slot's included_nightlords doesn't "
                "include \"Everdark %s\" - not sending.", boss.name, boss.name,
            )
            self._append_event({
                "timestamp": timestamp, "type": "everdark_win_skipped", "character": character_name,
                "boss": boss.name, "raw_boss_id": boss.raw, "reason": "not_included",
            })
            return

        is_everdark_win = everdark  # everdark here implies has_everdark_form and is included
        access_name = f"Everdark {boss.name} Access" if is_everdark_win else f"{boss.name} Access"
        if self.gate_boss_access and access_name not in self._owned_item_names():
            # Not just defense-in-depth for the non-Everdark case: the 6 secondary bosses share
            # EventFlag 110 (game_data.EVENT_FLAG_SECONDARY_BOSSES), so receiving any one of their
            # Access items makes the game's own UI select-able for all 6, including ones this slot
            # hasn't actually received yet (e.g. only "Augur Access" received unlocks Fissure in
            # the Fog, Sentient Pest, etc. too, in-game). This check is keyed on the specific
            # Nightlord's own Access item, not the shared flag, so a win against one of those
            # still-unowned 5 is correctly skipped here even though the game let the player queue
            # into it. Everdark Access items have no per-boss EventFlag at all (only
            # unlock_all_bosses_in_game's whole-menu patch makes Everdark selectable), so for
            # those this check is the only gate, not defense-in-depth on top of an in-game one.
            logger.info(
                "Win detected against %s, but this slot hasn't received %s yet - not sending.",
                (f"Everdark {boss.name}" if is_everdark_win else boss.name), access_name,
            )
            self._append_event({
                "timestamp": timestamp,
                "type": "locked_boss_win_skipped",
                "character": character_name,
                "boss": boss.name,
                "everdark": is_everdark_win,
            })
            return

        if is_everdark_win:
            name = (location_name_everdark(character_name, boss.name) if self.per_character_checks
                    else location_name_everdark_boss_only(boss.name))
        else:
            name = (location_name(character_name, boss.name) if self.per_character_checks
                    else location_name_boss_only(boss.name))
        location_id = location_name_to_id.get(name)
        if location_id is None:
            # Not in this player's included_characters/included_nightlords - nothing to send.
            logger.info(
                "Win detected (%s) but that location isn't in this slot's options - not sending.",
                name,
            )
            self._append_event({
                "timestamp": timestamp, "type": "win_location_not_in_slot", "location": name,
                "raw_boss_id": boss.raw, "everdark": everdark,
            })
            return

        logger.info("Win detected: %s (boss_id=%s)", name, boss.raw)
        self.checked_location_ids.add(location_id)
        self._append_event({
            "timestamp": timestamp,
            "type": "win",
            "everdark": everdark,
            "character": character_name,
            "raw_boss_id": boss.raw,
            "matched": boss.name,
            "location": name,
        })
        await self.check_locations([location_id])

        # Sends this slot's checks_per_boss - 1 bonus locations (game_data.bonus_indices) together
        # with this same win, against the exact same boss/character/everdark combination this slot
        # already earned that win against - reuses every gating check already passed
        # above, so no further access_owned check is needed here. NOT a cumulative counter: this
        # runs on every valid win, but self.checked_location_ids (below) already prevents a repeat
        # defeat of the same combination from re-sending anything, the same way the base
        # "Defeat X" location above never re-fires either.
        character_key = character_name if self.per_character_checks else None
        bonus_sent = []  # (location_id, name)
        for index in bonus_indices(self.checks_per_boss):
            bonus_name = location_name_kill_bonus(boss.name, index, character_key, is_everdark_win)
            bonus_id = location_name_to_id.get(bonus_name)
            if bonus_id is not None and bonus_id not in self.checked_location_ids:
                self.checked_location_ids.add(bonus_id)
                bonus_sent.append((bonus_id, bonus_name))
        if bonus_sent:
            for _bonus_id, bonus_name in bonus_sent:
                logger.info("Nightlord bonus check sent: %s", bonus_name)
            self._append_event({
                "timestamp": timestamp, "type": "nightlord_bonus",
                "locations": [name for _bonus_id, name in bonus_sent],
            })
            await self.check_locations([bonus_id for bonus_id, _name in bonus_sent])

    def print_status(self) -> None:
        """Prints the current live readings from the memory reader, for debugging.
        """
        if not self.reader.connected:
            logger.info("Nightreign: not connected to the game process.")
            return
        character = self.reader.read_character_class_name()
        boss = self.reader.read_boss_id()
        in_hub = self.reader.read_hub_state()
        pulse = self.reader.read_outcome_pulse()
        boss_desc = boss.name or boss.message or boss.status
        logger.info(
            "Nightreign status: character=%s  boss_id=%s (%s)  in_hub=%s  outcome_pulse=%s  "
            "death_link=%s  run_state=%s",
            character, boss.raw, boss_desc, in_hub, pulse, self.death_link_mode, self.run_state_path
        )


async def main(args) -> None:
    """Main entry point for the Nightreign client.

    """
    ctx = NightreignContext(args.connect, args.password)
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    ctx.poll_task = asyncio.create_task(ctx.poll_loop(), name="Nightreign poll loop")

    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()

    await ctx.exit_event.wait()
    await ctx.shutdown()


def launch(*launch_args: str) -> None:
    # Writes logs/NightreignClient_<timestamp>.txt - without this the client only logged to the
    # GUI/console, so a failed run left nothing behind to report.
    Utils.init_logging("NightreignClient", exception_logger="Client")
    colorama.just_fix_windows_console()
    parser = get_base_parser(description="Archipelago Elden Ring Nightreign Client")
    parser.add_argument("--name", default=None, help="Slot Name to connect as.")
    args = parser.parse_args(launch_args)
    asyncio.run(main(args))
    colorama.deinit()
