"""Archipelago client for Elden Ring Nightreign.

Polls the running game via memory_reader.py and sends a location check on
each detected Nightlord win. When the gate_boss_access option is on for this
slot (learned from slot_data on connect), received Access items are synced
into the game via memory_writer.py's SetEventFlag port, gating which
Nightlords are actually selectable. When randomize_weapons and/or
randomize_talismans is on, received "Randomized Weapon"/"Randomized Talisman"
filler items are rolled into a real weapon/talisman client-side (see
_roll_weapon_drop/_roll_talisman_drop) and dropped on the ground via
memory_writer.py's NightreignItemDropWriter (shared by both - it's item-type
agnostic) the next time an Expedition is entered. With all three options off,
received items have no in-game effect - the base CommonContext/CLI/GUI
machinery just logs them, same as before any was added.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import random
import re
from datetime import datetime, timezone
from typing import Optional

import colorama

import Utils
from CommonClient import (ClientCommandProcessor, CommonContext, get_base_parser,
                          gui_enabled, server_loop)
from NetUtils import ClientStatus

from .game_data import (ACCESS_ITEM_EVENT_FLAGS, ACCESS_NIGHTLORDS, EFFECT_CAP_MAP,
                        TALISMAN_TABLE, WEAPON_ART_TABLE, WEAPON_TABLE, roll_effect_tier,
                        roll_upgrade_tier, starting_free_nightlords)
from .Items import lookup_id_to_name
from .Locations import location_name, location_name_boss_only, location_name_to_id
from .memory_reader import NightreignMemoryReader, PointerNotFoundError
from .memory_writer import NightreignItemDropWriter, NightreignMemoryWriter
from .overlay import NightreignOverlay

logger = logging.getLogger("NightreignClient")

# Tight enough to reliably catch the transient +0xAF1 win pulse - see
# project notes on how narrow that window was observed to be.
POLL_INTERVAL = 0.25
RECONNECT_INTERVAL = 2
BUILD_MISMATCH_BACKOFF = 30


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
    game = "Elden Ring Nightreign"
    command_processor = NightreignCommandProcessor
    items_handling = 0b111
    reader: NightreignMemoryReader
    poll_task: Optional[asyncio.Task]
    run_state_path: Optional[str]
    checked_location_ids: set
    slot_data: dict
    gate_boss_access: bool
    randomize_weapons: bool
    randomize_talismans: bool
    freed_nightlords: set
    per_character_checks: bool
    goal: str
    goal_groups: list
    writer: Optional[NightreignMemoryWriter]
    overlay: Optional[NightreignOverlay]
    item_drop_writer: Optional[NightreignItemDropWriter]

    _last_pulse: Optional[int]
    _synced_flags: set
    _last_overlay_state: Optional[tuple]
    _last_hub_state: Optional[bool]
    _delivered_weapon_keys: set
    _delivered_talisman_keys: set

    def __init__(self, server_address: Optional[str], password: Optional[str]):
        super().__init__(server_address, password)
        self.reader = NightreignMemoryReader()
        self.poll_task = None
        self.run_state_path = None
        self.checked_location_ids = set()
        self.slot_data = {}
        self.gate_boss_access = False
        self.randomize_weapons = False
        self.randomize_talismans = False
        self.freed_nightlords = set()
        self.per_character_checks = False
        self.goal = "all_bosses"
        self.goal_groups = []
        self.writer = None
        self.overlay = None
        self.item_drop_writer = None
        self._last_pulse = None
        self._synced_flags = set()
        self._last_overlay_state = None
        self._last_hub_state = None
        self._delivered_weapon_keys = set()
        self._delivered_talisman_keys = set()

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
            self.randomize_weapons = bool(self.slot_data.get("randomize_weapons", False))
            self.randomize_talismans = bool(self.slot_data.get("randomize_talismans", False))
            self.freed_nightlords = set(
                starting_free_nightlords(self.slot_data.get("starting_boss", "Tricephalos"))
            )
            self.per_character_checks = (
                self.slot_data.get("bosses_with_characters", "boss") == "boss_and_character"
            )
            self.goal = self.slot_data.get("goal", "all_bosses")
            self.goal_groups = self.slot_data.get("goal_groups") or []
            logger.info("gate_boss_access=%s for this slot.", self.gate_boss_access)

            # A flag write only ever confirms that the remote thread was dispatched, not that the
            # in-game effect actually landed (see memory_writer.py's set_event_flag docstring) - so
            # treating a past dispatch as permanently done would mean a write that silently had no
            # visible effect (e.g. fired too early in the hub-load sequence) could never be retried
            # for the rest of the process's life. Clearing this on every fresh AP connection - not
            # just on a game-process reconnect (see poll_loop) - turns "disconnect/reconnect the AP
            # client" into an actual retry path instead of a no-op.
            self._synced_flags.clear()

            self._open_run_state()
            # Replay anything our local state already thinks is checked, in
            # case the server and our local record ever drifted (e.g. a
            # connection dropped mid-send). check_locations() only sends
            # what's still in ctx.missing_locations, so this is always safe.
            if self.checked_location_ids:
                asyncio.create_task(self.check_locations(self.checked_location_ids))
            asyncio.create_task(self._maybe_declare_goal())
            # gate_boss_access is only known once this packet arrives, but the game
            # process may already be attached from before this connect (its own
            # connect-transition in poll_loop already ran with gate_boss_access still
            # False at the time) - build the writer/overlay here too, or that ordering
            # would leave them permanently unbuilt for the rest of the session.
            self._ensure_gating_ready()
            asyncio.create_task(self._sync_event_flags())
            # Same race as gating above: the game process may already be attached from before
            # this connect, so build the item-drop writer here too, not just in poll_loop.
            self._ensure_item_drop_ready()

        if cmd == "ReceivedItems":
            if self.gate_boss_access:
                asyncio.create_task(self._sync_event_flags())
            # No action needed here for randomize_weapons/randomize_talismans -
            # _pending_drop_keys() recomputes from self.items_received fresh every time
            # poll_loop's hub-exit edge fires, so a newly received "Randomized Weapon"/
            # "Randomized Talisman" is picked up automatically on the next Expedition entry
            # without any bookkeeping needed at receive time.

        if cmd == "RoomUpdate":
            # ctx.missing_locations is updated (by the base on_package
            # handling, before this hook runs) from the "checked_locations"
            # field on this same packet - this is the correct place to
            # notice "nothing left to check", not right after our own send,
            # since the server confirms via this packet rather than synchronously.
            asyncio.create_task(self._maybe_declare_goal())

    def _goal_complete(self) -> bool:
        # goal_groups (from slot_data, see World.create_regions()) is a list of groups, where
        # each group is satisfied by ANY one of its location ids being checked - the overall
        # goal needs EVERY group satisfied. Falls back to the pre-`goal`-option behavior ("no
        # locations left to check at all") if slot_data has no goal_groups, e.g. stale slot_data
        # from a seed generated before this existed.
        if not self.goal_groups:
            return not self.missing_locations
        return all(
            any(location_id not in self.missing_locations for location_id in group)
            for group in self.goal_groups
        )

    async def _maybe_declare_goal(self) -> None:
        # This tracker has no item/logic gating (topology_present = False,
        # every location is reachable from the start), so there's no
        # CollectionState-based completion_condition that could mean
        # anything here - "goal" can only be observed client-side, via
        # _goal_complete(). See docs/adding games.md's "Hard Requirements":
        # a client must send a StatusUpdate on goal completion.
        if not self.finished_game and self.slot is not None and self._goal_complete():
            self.finished_game = True
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            logger.info("Goal '%s' complete!", self.goal)

    # --- Boss-access gating (write path) ---
    #
    # Off unless slot_data says gate_boss_access is on for this slot. Firing
    # SetEventFlag(110) for any one of the 6 secondary-boss Access items
    # necessarily reveals all 6 in the game's own menu (that flag is
    # all-or-nothing - see game_data.py) - overlay.py is what shows the
    # player which of those are actually AP-owned.

    def _owned_item_names(self) -> set:
        # freed_nightlords (from the starting_boss option) are stitched in as
        # synthetic "X Access" entries so every downstream consumer of this
        # set - flag-firing and the overlay's locked/unlocked display - treats
        # them exactly like an already-received Access item, with no separate
        # code path needed.
        owned = {lookup_id_to_name.get(i.item) for i in self.items_received}
        owned |= {f"{name} Access" for name in self.freed_nightlords}
        return owned

    async def _sync_event_flags(self) -> None:
        if not self.gate_boss_access or self.writer is None:
            return
        owned_names = self._owned_item_names()
        needed_flags = {
            flag for name, flag in ACCESS_ITEM_EVENT_FLAGS.items() if name in owned_names
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
        """Builds the writer/overlay once both gate_boss_access and the game connection are
        known, regardless of which arrived first this session - the game process attaching
        and the AP 'Connected' packet (which is what sets gate_boss_access) race each other,
        and either can win. Called from both sides of that race: here and from poll_loop's
        connect-transition. A no-op once the writer already exists."""
        if not self.gate_boss_access or not self.reader.connected or self.writer is not None:
            return
        self._try_build_writer()
        if self.writer is not None and self.overlay is None:
            self.overlay = NightreignOverlay(self.reader.pm.process_id)
            self.overlay.start()
            logger.info("Boss-gating overlay started (pid=%s).", self.reader.pm.process_id)

    def _try_build_writer(self) -> None:
        try:
            ptr_slot, base_a_addr = self.reader.resolve_event_flag_targets()
        except PointerNotFoundError as e:
            logger.error("Boss-gating write path unavailable (%s) - disabling gating this "
                         "session, the read-only tracker is unaffected.", e)
            self.gate_boss_access = False
            return
        self.writer = NightreignMemoryWriter(self.reader.pm, ptr_slot, base_a_addr)
        logger.info("Boss-gating writer resolved (ptr_slot=0x%X, base_a=0x%X).",
                    ptr_slot, base_a_addr)

    # --- Randomized item-drop write path (weapons and talismans) ---
    #
    # Off unless slot_data says randomize_weapons and/or randomize_talismans is on for this slot.
    # A received "Randomized Weapon"/"Randomized Talisman" filler item is deterministically
    # rolled into a real item (see _roll_weapon_drop/_roll_talisman_drop) and dropped on the
    # ground the next time the hub->active-run edge fires in poll_loop (i.e. the next Expedition
    # entry) - not immediately on receipt, since there's no safe way to drop an item while in the
    # hub/menu. One item_drop_writer is shared by both - memory_writer.py's drop_item() is
    # item-type agnostic (category comes from the item id itself), so there's no need for a
    # second write path.

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

    def _pending_drop_keys(self, item_name: str, delivered_keys: set) -> set:
        """(location, player) keys for every received `item_name` filler item not yet delivered -
        recomputed fresh from self.items_received each call rather than tracked incrementally,
        the same "diff against what's already done" shape as _sync_event_flags."""
        received = {
            (i.location, i.player) for i in self.items_received
            if lookup_id_to_name.get(i.item) == item_name
        }
        return received - delivered_keys

    def _roll_weapon_drop(self, location: int, player: int) -> dict:
        """Deterministic roll for one "Randomized Weapon" filler instance, seeded off which
        check sent it (seed_name + location + player) rather than delivery order or timing - so
        a reconnect, a retried drop, or a delayed Expedition entry always reproduces the exact
        same weapon instead of re-rolling. Every axis is independently randomized per the
        project's design discussion: weapon id (uniform over game_data.WEAPON_TABLE),
        upgrade_level (weighted via game_data.roll_upgrade_tier - see its own comment for the
        band shape), weapon_art and wep_effect (uniform, including a "None" outcome so not every
        drop is maximally loaded - left unweighted deliberately, so "None" is roughly 1-in-131),
        and effect_tier (weighted via game_data.roll_effect_tier, same band-percentile idea as
        upgrade_level - memory_writer.py's drop_item already discards this whenever wep_effect is
        None or the rolled effect's own cap is lower, so no extra logic is needed here to keep it
        valid). magic_skill_1/2 are left at "None" - narrower in scope (only staff/seal weapons
        use them) and out of scope for this pass; ask if you want those randomized too.
        """
        rng = random.Random(f"{self.seed_name}:{location}:{player}:weapon")
        return {
            "item_id": rng.choice(list(WEAPON_TABLE)),
            "upgrade_level": roll_upgrade_tier(rng.randint(0, 100)),
            "weapon_art": rng.choice([-1] + list(WEAPON_ART_TABLE)),
            "wep_effect": rng.choice([-1] + list(EFFECT_CAP_MAP)),
            "effect_tier": roll_effect_tier(rng.randint(0, 100)),
        }

    def _roll_talisman_drop(self, location: int, player: int) -> dict:
        """Deterministic roll for one "Randomized Talisman" filler instance, same seeding idea as
        _roll_weapon_drop (seed_name + location + player, so retries/reconnects reproduce the
        same talisman rather than re-rolling) but much simpler: talismans have no upgrade tier,
        Ash of War, or affinity to roll - just a uniform pick over game_data.TALISMAN_TABLE.
        Every other drop_item() argument is left at its default ("none"/no-op for a weapon-only
        field), which memory_writer.py's drop_item/the source CT script's dropItem() both already
        skip entirely for a non-Weapon item type.
        """
        rng = random.Random(f"{self.seed_name}:{location}:{player}:talisman")
        return {"item_id": rng.choice(list(TALISMAN_TABLE))}

    async def _deliver_pending_drops(
        self, item_name: str, roll_fn, delivered_keys: set, event_type: str, log_label: str
    ) -> None:
        if self.item_drop_writer is None:
            return
        pending = self._pending_drop_keys(item_name, delivered_keys)
        if not pending:
            return
        loop = asyncio.get_running_loop()
        for location, player in pending:
            roll = roll_fn(location, player)
            ok = await loop.run_in_executor(
                None, functools.partial(self.item_drop_writer.drop_item, **roll)
            )
            if ok:
                delivered_keys.add((location, player))
                self._append_event({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": event_type,
                    "location": location,
                    "player": player,
                    **roll,
                })
                logger.info("Dropped %s 0x%X for location=%s player=%s.",
                            log_label, roll["item_id"], location, player)
            else:
                # Not removed from the pending set - _pending_drop_keys() will offer it again on
                # the next Expedition entry, matching _sync_event_flags's retry shape.
                logger.warning("%s drop skipped for location=%s player=%s - game not ready, "
                                "will retry on next Expedition entry.", log_label, location, player)

    async def _deliver_pending_weapons(self) -> None:
        await self._deliver_pending_drops(
            "Randomized Weapon", self._roll_weapon_drop, self._delivered_weapon_keys,
            "weapon_drop", "randomized weapon"
        )

    async def _deliver_pending_talismans(self) -> None:
        await self._deliver_pending_drops(
            "Randomized Talisman", self._roll_talisman_drop, self._delivered_talisman_keys,
            "talisman_drop", "randomized talisman"
        )

    # --- Per-run local state file ---
    #
    # One file per distinct AP world/slot (keyed by seed name + slot name),
    # under Utils.user_path("nightreign"). Keeping this separate per seed
    # means switching between different multiworld games never mixes up
    # which locations have already been sent. Beyond that resume/dedupe
    # role, it also keeps a timestamped event log of every win and every
    # unresolved boss_id detection - a self-contained artifact a tester can
    # hand to the mod owner alongside the "please report this" message from
    # the Phase 0/1 design decision.

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
                    (int(location), int(player))
                    for location, player in data.get("delivered_weapon_keys", [])
                }
                self._delivered_talisman_keys = {
                    (int(location), int(player))
                    for location, player in data.get("delivered_talisman_keys", [])
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
                    # the next _sync_event_flags() reuse it after a fresh connect rebuilds it.
                    # Drop synced-flag bookkeeping too, so a fresh connect re-verifies rather than
                    # trusting state from a writer that no longer exists.
                    self.writer = None
                    self._synced_flags.clear()
                    self.item_drop_writer = None
                    self._last_hub_state = None
                    try:
                        if self.reader.connect():
                            logger.info("Connected to nightreign.exe")
                            self._ensure_gating_ready()
                            if self.gate_boss_access:
                                asyncio.create_task(self._sync_event_flags())
                            self._ensure_item_drop_ready()
                        else:
                            await asyncio.sleep(RECONNECT_INTERVAL)
                            continue
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

                if self.gate_boss_access and self.writer is not None:
                    # Retried every tick, not just on Connected/ReceivedItems: freed_nightlords
                    # (from the starting_boss option) never arrives as a ReceivedItems packet, so
                    # this is the only thing that retries a flag write that failed because the
                    # EventFlag pointer was transiently unreadable (e.g. still mid-tutorial
                    # transition) right when the writer was first built. A no-op once synced.
                    await self._sync_event_flags()

                # Read once per tick and shared below - True in hub/menu/loading, False in an
                # active run, None if transiently unreadable (e.g. a scene transition).
                in_hub = self.reader.read_hub_state()

                if (self.randomize_weapons or self.randomize_talismans) and in_hub is not None:
                    # Only a *confirmed* True->False read counts as "just entered an Expedition" -
                    # deliberately not coercing a transient None to False here (unlike the
                    # overlay's bool(in_hub) below), since that could misfire a real remote-thread
                    # dispatch off a momentarily-unreadable read instead of a genuine transition.
                    if self._last_hub_state is True and in_hub is False:
                        if self.randomize_weapons:
                            await self._deliver_pending_weapons()
                        if self.randomize_talismans:
                            await self._deliver_pending_talismans()
                    self._last_hub_state = in_hub

                if self.gate_boss_access and self.overlay is not None:
                    owned_names = self._owned_item_names()
                    locked_names = [
                        name for name in ACCESS_NIGHTLORDS if f"{name} Access" not in owned_names
                    ]
                    # pid is refreshed here too, not just at overlay construction - the game
                    # process can restart mid-session and reconnect under a new pid, but this
                    # already-running overlay is never torn down/rebuilt for that (see the
                    # `self.overlay is None` guard above), so without this it would keep hunting
                    # for a dead process's window and stay invisible forever.
                    self.overlay.state.update(bool(in_hub), locked_names, self.reader.pm.process_id)

                    # Logged only on change, not every tick - lets a log dump explain exactly
                    # why the overlay panel was/wasn't visible at any point (it only draws
                    # while in_hub and locked_names is non-empty - see overlay.py's _tick),
                    # without spamming a line 4x/second.
                    state_key = (bool(in_hub), tuple(locked_names))
                    if state_key != self._last_overlay_state:
                        self._last_overlay_state = state_key
                        logger.info("Overlay state changed: in_hub=%s locked=%s", bool(in_hub),
                                    locked_names)
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
