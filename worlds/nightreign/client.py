"""Archipelago client for Elden Ring Nightreign.

Polls the running game via memory_reader.py and sends a location check on
each detected Nightlord win. When enable_everdark_checks is on for this slot
and the win is detected as an Everdark Sovereign variant (memory_reader.py's
read_everdark_flag()), a separate "Defeat Everdark X" location is sent instead
of the normal one - see Options.py's EnableEverdarkChecks for the disclaimer
around Everdark availability being outside this project's control. When the
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
_handle_win would refuse to send a check for anyway. With all three options off, received items
have no in-game effect - the base CommonContext/CLI/GUI machinery just logs
them, same as before any was added.
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
                        CHARACTER_ACCESS_EVENT_FLAGS, EFFECT_CAP_MAP, EVERDARK_NIGHTLORDS,
                        TALISMAN_TABLE, WEAPON_ART_TABLE, WEAPON_TABLE, is_flying_animation,
                        natural_weapon_tier, roll_effect_tier, roll_upgrade_tier,
                        starting_free_characters, starting_free_nightlords)
from .Items import lookup_id_to_name
from .Locations import (location_name, location_name_boss_only, location_name_everdark,
                        location_name_everdark_boss_only, location_name_to_id)
from .memory_reader import EACDetectedError, NightreignMemoryReader, PointerNotFoundError
from .memory_writer import NightreignItemDropWriter, NightreignMemoryWriter
from .overlay import NightreignOverlay

logger = logging.getLogger("NightreignClient")

# Tight enough to reliably catch the win pulse - see
# project notes on how narrow that window was observed to be.
POLL_INTERVAL = 0.25
RECONNECT_INTERVAL = 2
BUILD_MISMATCH_BACKOFF = 30

# The fly-in animation
EXPEDITION_ENTRY_SETTLE_SECONDS = 15

# Item received toast duration
TOAST_DURATION_SECONDS = 3.0


def _safe_filename_component(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_") or "unknown"


class NightreignCommandProcessor(ClientCommandProcessor):
    """ClientCommandProcessor for Nightreign

    Args:
        ClientCommandProcessor (_type_): _description_
    """
    ctx: "NightreignContext"

    def _cmd_status(self):
        """Show the memory reader's current live readings."""
        self.ctx.print_status()


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
    randomize_weapons: bool
    randomize_talismans: bool
    enable_everdark_checks: bool
    freed_nightlords: set
    freed_characters: set
    per_character_checks: bool
    goal: str
    goal_groups: list
    writer: Optional[NightreignMemoryWriter]
    overlay: Optional[NightreignOverlay]
    item_drop_writer: Optional[NightreignItemDropWriter]
    _worldchrman_slot: Optional[int]
    _hub_exit_time: Optional[float]

    _last_pulse: Optional[int]
    _synced_flags: set
    _last_overlay_state: Optional[tuple]
    _delivered_weapon_keys: set
    _delivered_talisman_keys: set
    _locked_boss_warned: bool
    _locked_character_warned: bool
    _locked_run_drop_withheld_warned: bool
    _toast_text: Optional[str]
    _toast_expiry: Optional[float]

    def __init__(self, server_address: Optional[str], password: Optional[str]):
        super().__init__(server_address, password)
        self.reader = NightreignMemoryReader()
        self.poll_task = None
        self.run_state_path = None
        self.checked_location_ids = set()
        self.slot_data = {}
        self.gate_boss_access = False
        self.gate_character_access = False
        self.randomize_weapons = False
        self.randomize_talismans = False
        self.enable_everdark_checks = False
        self.freed_nightlords = set()
        self.freed_characters = set()
        self.per_character_checks = False
        self.goal = "all_bosses"
        self.goal_groups = []
        self.writer = None
        self.overlay = None
        self.item_drop_writer = None
        self._worldchrman_slot = None
        self._hub_exit_time = None
        self._last_pulse = None
        self._synced_flags = set()
        self._last_overlay_state = None
        self._delivered_weapon_keys = set()
        self._delivered_talisman_keys = set()
        self._locked_boss_warned = False
        self._locked_character_warned = False
        self._locked_run_drop_withheld_warned = False
        self._toast_text = None
        self._toast_expiry = None

    def run_gui(self):

        # Allow deferred import for GUI
        from kvui import GameManager

        class NightreignManager(GameManager):
            logging_pairs = [("Client", "Archipelago")]
            base_title = "Archipelago Nightreign Client"

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
            # slot_data keys are "receive_weapons"/"receive_talismans" (see Options.py/__init__.py's
            # fill_slot_data), not "randomize_weapons"/"randomize_talismans" - using the wrong keys
            # previously fell back to False regardless of the player's actual YAML settings.
            self.randomize_weapons = bool(self.slot_data.get("receive_weapons", False))
            self.randomize_talismans = bool(self.slot_data.get("receive_talismans", False))
            self.enable_everdark_checks = bool(self.slot_data.get("enable_everdark_checks", False))
            self.freed_nightlords = set(
                starting_free_nightlords(self.slot_data.get("starting_boss", "Tricephalos"))
            )
            self.freed_characters = set(
                starting_free_characters(self.slot_data.get("starting_character", "Wylder"))
            )
            self.per_character_checks = (
                self.slot_data.get("bosses_with_characters", "boss") == "boss_and_character"
            )
            self.goal = self.slot_data.get("goal", "all_bosses")
            self.goal_groups = self.slot_data.get("goal_groups") or []
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

        if cmd == "ReceivedItems":
            if self.gate_boss_access or self.gate_character_access:
                asyncio.create_task(self._sync_event_flags())
            # No action needed for randomize_weapons/randomize_talismans - _pending_drop_keys()
            # recomputes from self.items_received on every poll_loop hub-exit edge, so a new
            # "Randomized Weapon"/"Talisman" is picked up on the next Expedition entry automatically.

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
        # freed_nightlords (from starting_boss) and freed_characters (from starting_character) are
        # stitched in as synthetic "X Access"/"X Character Access" entries so every downstream
        # consumer - flag-firing, overlay's locked/unlocked display - treats them exactly like an
        # already-received Access item, with no separate code path needed.
        owned = {lookup_id_to_name.get(i.item) for i in self.items_received}
        owned |= {f"{name} Access" for name in self.freed_nightlords}
        owned |= {f"{name} Character Access" for name in self.freed_characters}
        return owned

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
        """Builds the writer once either gate_boss_access/gate_character_access and the game
        connection are known, regardless of which arrived first this session - the game process
        attaching and the AP 'Connected' packet (which is what sets both options) race each other,
        and either can win. Called from both sides of that race: here and from poll_loop's
        connect-transition. A no-op once the writer already exists."""
        if (not (self.gate_boss_access or self.gate_character_access) or not self.reader.connected
                or self.writer is not None):
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

    def _warn_if_boss_locked(self, boss_name: str) -> None:
        """Logs (and records to run state) an Expedition started on a Nightlord whose Access item
        this slot hasn't received yet. gate_boss_access's flag write is all-or-nothing (see the
        module comment above _owned_item_names) - receiving any one Access item reveals all 6
        secondary bosses in the game's own menu, so nothing in-game stops the player from
        selecting one they don't actually have Access to. The overlay already shows this
        passively; this is the same check surfaced as a log line for the "basically wasting their
        run" case the player might not notice mid-run."""
        access_name = f"{boss_name} Access"
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
            if boss.status == "matched" and f"{boss.name} Access" not in owned_names:
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
            return
        self.writer = NightreignMemoryWriter(self.reader.pm, ptr_slot, base_a_addr)
        logger.info("Boss/character-gating writer resolved (ptr_slot=0x%X, base_a=0x%X).",
                    ptr_slot, base_a_addr)

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
        if (not (self.randomize_weapons or self.randomize_talismans) or not self.reader.connected
                or self._worldchrman_slot is not None):
            return
        try:
            self._worldchrman_slot = self.reader.resolve_current_animation_target()
        except PointerNotFoundError as e:
            logger.error("Flight-animation read path unavailable (%s) - disabling "
                         "randomize_weapons/randomize_talismans this session, the read-only "
                         "tracker is unaffected.", e)
            self.randomize_weapons = False
            self.randomize_talismans = False

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

    def _roll_weapon_drop(self, index: int, player: int) -> dict:
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
        """
        rng = random.Random(f"{self.seed_name}:{index}:{player}:weapon")
        item_id = rng.choice(list(WEAPON_TABLE))
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

    def _show_toast(self, text: str) -> None:
        """Arms the overlay's center-top toast for TOAST_DURATION_SECONDS. Timing lives here
        (asyncio side), not in overlay.py - poll_loop's per-tick overlay update re-passes this
        same text on every tick until the expiry it set has passed, then lets it go back to None,
        so the Tk thread just displays whatever it's handed rather than running its own clock."""
        self._toast_text = text
        self._toast_expiry = time.monotonic() + TOAST_DURATION_SECONDS

    async def _deliver_pending_drops(
        self, item_name: str, roll_fn, delivered_keys: set, event_type: str, log_label: str,
        toast_text: str,
    ) -> None:
        if self.item_drop_writer is None:
            return
        pending = self._pending_drop_keys(item_name, delivered_keys)
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
        await self._deliver_pending_drops(
            "Randomized Weapon", self._roll_weapon_drop, self._delivered_weapon_keys,
            "weapon_drop", "randomized weapon", "Weapon received"
        )

    async def _deliver_pending_talismans(self) -> None:
        await self._deliver_pending_drops(
            "Randomized Talisman", self._roll_talisman_drop, self._delivered_talisman_keys,
            "talisman_drop", "randomized talisman", "Talisman received"
        )

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
                self._delivered_weapon_keys = {
                    (int(index), int(player))
                    for index, player in data.get("delivered_weapon_keys", [])
                }
                self._delivered_talisman_keys = {
                    (int(index), int(player))
                    for index, player in data.get("delivered_talisman_keys", [])
                }
            except (json.JSONDecodeError, OSError, ValueError) as e:
                logger.warning(
                    "Could not read existing Nightreign run state at %s: %s", self.run_state_path, e
                )
                self.checked_location_ids = set()
                self._delivered_weapon_keys = set()
                self._delivered_talisman_keys = set()
        else:
            self.checked_location_ids = set()
            self._delivered_weapon_keys = set()
            self._delivered_talisman_keys = set()
            self._write_run_state(seed_name, slot_name, events=[])

        logger.info("Nightreign run state file: %s", self.run_state_path)

    def _write_run_state(self, seed_name: str, slot_name: str, events: list) -> None:
        data = {
            "seed_name": seed_name,
            "slot_name": slot_name,
            "checked_locations": sorted(self.checked_location_ids),
            "delivered_weapon_keys": sorted(list(key) for key in self._delivered_weapon_keys),
            "delivered_talisman_keys": sorted(list(key) for key in self._delivered_talisman_keys),
            "events": events,
        }
        with open(self.run_state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

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
                "checked_locations": [], "delivered_weapon_keys": [],
                "delivered_talisman_keys": [], "events": [],
            }
        data["checked_locations"] = sorted(self.checked_location_ids)
        data["delivered_weapon_keys"] = sorted(list(key) for key in self._delivered_weapon_keys)
        data["delivered_talisman_keys"] = sorted(
            list(key) for key in self._delivered_talisman_keys
        )
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
                    self._worldchrman_slot = None
                    self._hub_exit_time = None
                    self._locked_boss_warned = False
                    self._locked_character_warned = False
                    self._locked_run_drop_withheld_warned = False
                    try:
                        if self.reader.connect():
                            logger.info("Connected to nightreign.exe")
                            self._ensure_gating_ready()
                            self._ensure_overlay_ready()
                            if self.gate_boss_access or self.gate_character_access:
                                asyncio.create_task(self._sync_event_flags())
                            self._ensure_item_drop_ready()
                            self._ensure_animation_ready()
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

                pulse = self.reader.read_outcome_pulse()
                if pulse == 1 and self._last_pulse == 0:
                    await self._handle_win()
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
                            self._warn_if_boss_locked(boss.name)

                if self.gate_character_access:
                    if in_hub:
                        self._locked_character_warned = False
                    elif in_hub is False and not self._locked_character_warned:
                        character_name = self.reader.read_character_class_name()
                        if character_name is not None:
                            self._locked_character_warned = True
                            self._warn_if_character_locked(character_name)

                if self.randomize_weapons or self.randomize_talismans:
                    # Tracks how long in_hub has continuously been False, so the settle-time check
                    # below can tell "just exited the hub" from "been in the Expedition a while" -
                    # reset on True so each fresh Expedition gets its own settle window.
                    if in_hub:
                        self._hub_exit_time = None
                        self._locked_run_drop_withheld_warned = False
                    elif in_hub is False and self._hub_exit_time is None:
                        self._hub_exit_time = time.monotonic()

                if (
                    (self.randomize_weapons or self.randomize_talismans)
                    and in_hub is False
                    and self._hub_exit_time is not None
                    and time.monotonic() - self._hub_exit_time >= EXPEDITION_ENTRY_SETTLE_SECONDS
                ):
                    if self._current_run_is_locked():
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
                                "Withholding weapon/talisman drops this run - the current boss "
                                "and/or character isn't unlocked for this slot yet."
                            )
                    else:
                        # Level-triggered every tick, not edge-triggered on hub-exit: a pending drop
                        # needs both "in an Expedition" and "not mid-flight" (live-tested, see
                        # game_data.py) to land. Safe to retry: _delivered_weapon_keys/
                        # _delivered_talisman_keys dedupe.
                        animation = (
                            self.reader.read_current_animation(self._worldchrman_slot)
                            if self._worldchrman_slot is not None else None
                        )
                        if animation is not None and not is_flying_animation(animation):
                            if self.randomize_weapons:
                                await self._deliver_pending_weapons()
                            if self.randomize_talismans:
                                await self._deliver_pending_talismans()

                if self.overlay is not None:
                    locked_bosses = []
                    locked_characters = []
                    if self.gate_boss_access or self.gate_character_access:
                        owned_names = self._owned_item_names()
                        if self.gate_boss_access:
                            locked_bosses = [
                                name for name in ACCESS_NIGHTLORDS
                                if f"{name} Access" not in owned_names
                            ]
                        if self.gate_character_access:
                            locked_characters = [
                                name for name in ACCESS_CHARACTERS
                                if f"{name} Character Access" not in owned_names
                            ]

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
                        bool(in_hub), locked_bosses, locked_characters, self.reader.pm.process_id,
                        boss_raw, boss_desc, character, everdark, toast_text,
                    )

                    # Logged only on change, not every tick, so a log dump explains why the
                    # locked-boss panel was/wasn't visible without spamming 4x/second. The
                    # boss/character panel isn't included - those are expected to hold steady.
                    state_key = (bool(in_hub), tuple(locked_bosses), tuple(locked_characters))
                    if state_key != self._last_overlay_state:
                        self._last_overlay_state = state_key
                        logger.info(
                            "Overlay state changed: in_hub=%s locked_bosses=%s locked_characters=%s",
                            bool(in_hub), locked_bosses, locked_characters,
                        )
            except Exception:
                logger.exception("Error in Nightreign poll loop")
            await asyncio.sleep(POLL_INTERVAL)

    async def _handle_win(self) -> None:
        boss = self.reader.read_boss_id()
        character_name = self.reader.read_character_class_name()
        timestamp = datetime.now(timezone.utc).isoformat()

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

        if (self.gate_boss_access and f"{boss.name} Access" not in self._owned_item_names()):
            # Not just defense-in-depth: the 6 secondary bosses share EventFlag 110
            # (game_data.EVENT_FLAG_SECONDARY_BOSSES), so receiving any one of their Access items
            # makes the game's own UI select-able for all 6, including ones this slot hasn't
            # actually received yet (e.g. only "Augur Access" received unlocks Fissure in the Fog,
            # Sentient Pest, etc. too, in-game). This check is keyed on the specific Nightlord's own
            # Access item, not the shared flag, so a win against one of those still-unowned 5 is
            # correctly skipped here even though the game let the player queue into it.
            logger.info(
                "Win detected against %s, but this slot hasn't received %s's Access item yet - "
                "not sending.", boss.name, boss.name,
            )
            self._append_event({
                "timestamp": timestamp,
                "type": "locked_boss_win_skipped",
                "character": character_name,
                "boss": boss.name,
            })
            return

        everdark = bool(self.reader.read_everdark_flag())  # None (unreadable) treated as False

        if everdark and self.enable_everdark_checks and boss.name in EVERDARK_NIGHTLORDS:
            name = (location_name_everdark(character_name, boss.name) if self.per_character_checks
                    else location_name_everdark_boss_only(boss.name))
        elif everdark:
            # An Everdark win, but this slot either doesn't have enable_everdark_checks on, or
            # this Nightlord has no Everdark form (shouldn't happen - Night Aspect is the only
            # one, and it isn't fought via a normal win pulse the same way). Deliberately not
            # falling back to crediting the normal "Defeat X" location instead - that would
            # reward a harder fight with a check that doesn't reflect what actually happened.
            logger.info(
                "Win detected as Everdark %s, but Everdark checks aren't enabled for this slot "
                "(or this Nightlord has no Everdark form) - not sending.", boss.name,
            )
            return
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
            "run_state=%s",
            character, boss.raw, boss_desc, in_hub, pulse, self.run_state_path
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
    colorama.just_fix_windows_console()
    parser = get_base_parser(description="Archipelago Elden Ring Nightreign Client")
    parser.add_argument("--name", default=None, help="Slot Name to connect as.")
    args = parser.parse_args(launch_args)
    asyncio.run(main(args))
    colorama.deinit()
