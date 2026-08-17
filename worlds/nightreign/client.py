"""Archipelago client for Elden Ring Nightreign.

Polls the running game via memory_reader.py and sends a location check on
each detected Nightlord win. When the gate_boss_access option is on for this
slot (learned from slot_data on connect), received Access items are synced
into the game via memory_writer.py's SetEventFlag port, gating which
Nightlords are actually selectable. With that option off, received items
have no in-game effect - the base CommonContext/CLI/GUI machinery just logs
them, same as before this was added.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

import colorama

import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, server_loop
from NetUtils import ClientStatus

from .game_data import ACCESS_ITEM_EVENT_FLAGS, ACCESS_NIGHTLORDS
from .Items import lookup_id_to_name
from .Locations import location_name, location_name_to_id
from .memory_reader import NightreignMemoryReader, PointerNotFoundError
from .memory_writer import NightreignMemoryWriter
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

    gate_boss_access: bool
    writer: Optional[NightreignMemoryWriter]
    overlay: Optional[NightreignOverlay]

    _last_pulse: Optional[int]

    def __init__(self, server_address: Optional[str], password: Optional[str]):
        super().__init__(server_address, password)
        self.reader = NightreignMemoryReader()
        self.poll_task = None
        self.run_state_path = None
        self.checked_location_ids = set()
        self.gate_boss_access = False
        self.writer = None
        self.overlay = None
        self._last_pulse = None

    def run_gui(self):
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

            self._open_run_state()
            # Replay anything our local state already thinks is checked, in
            # case the server and our local record ever drifted (e.g. a
            # connection dropped mid-send). check_locations() only sends
            # what's still in ctx.missing_locations, so this is always safe.
            if self.checked_location_ids:
                asyncio.create_task(self.check_locations(self.checked_location_ids))
            asyncio.create_task(self._maybe_declare_goal())
            # In case items were already waiting (e.g. a reconnect) and the
            # game is already attached from a prior connection.
            asyncio.create_task(self._sync_event_flags())

        if cmd == "ReceivedItems":
            if self.gate_boss_access:
                asyncio.create_task(self._sync_event_flags())

        if cmd == "RoomUpdate":
            # ctx.missing_locations is updated (by the base on_package
            # handling, before this hook runs) from the "checked_locations"
            # field on this same packet - this is the correct place to
            # notice "nothing left to check", not right after our own send,
            # since the server confirms via this packet rather than synchronously.
            asyncio.create_task(self._maybe_declare_goal())

    async def _maybe_declare_goal(self) -> None:
        # This tracker has no item/logic gating (topology_present = False,
        # every location is reachable from the start), so there's no
        # CollectionState-based completion_condition that could mean
        # anything here - "goal" can only be observed client-side, as
        # "no locations left to check for this slot's included
        # characters/Nightlords". See docs/adding games.md's "Hard
        # Requirements": a client must send a StatusUpdate on goal completion.
        if not self.finished_game and self.slot is not None and not self.missing_locations:
            self.finished_game = True
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            logger.info("All included locations checked - goal complete!")

    # --- Boss-access gating (write path) ---
    #
    # Off unless slot_data says gate_boss_access is on for this slot. Firing
    # SetEventFlag(110) for any one of the 6 secondary-boss Access items
    # necessarily reveals all 6 in the game's own menu (that flag is
    # all-or-nothing - see game_data.py) - overlay.py is what shows the
    # player which of those are actually AP-owned.

    def _owned_item_names(self) -> set:
        return {lookup_id_to_name.get(i.item) for i in self.items_received}

    async def _sync_event_flags(self) -> None:
        if not self.gate_boss_access or self.writer is None:
            return
        owned_names = self._owned_item_names()
        needed_flags = {flag for name, flag in ACCESS_ITEM_EVENT_FLAGS.items() if name in owned_names}
        if not needed_flags:
            return
        loop = asyncio.get_running_loop()
        for flag in needed_flags:
            ok = await loop.run_in_executor(None, self.writer.set_event_flag, flag, True)
            if not ok:
                logger.warning(f"SetEventFlag({flag}, 1) skipped - game not ready, will retry on next sync.")

    def _try_build_writer(self) -> None:
        try:
            ptr_slot, base_a_addr = self.reader.resolve_event_flag_targets()
        except PointerNotFoundError as e:
            logger.error(f"Boss-gating write path unavailable ({e}) - disabling gating this "
                         f"session, the read-only tracker is unaffected.")
            self.gate_boss_access = False
            return
        self.writer = NightreignMemoryWriter(self.reader.pm, ptr_slot, base_a_addr)

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
        filename = f"{_safe_filename_component(seed_name)}_{_safe_filename_component(slot_name)}.json"
        self.run_state_path = os.path.join(directory, filename)

        if os.path.exists(self.run_state_path):
            try:
                with open(self.run_state_path, "r") as f:
                    data = json.load(f)
                self.checked_location_ids = {int(x) for x in data.get("checked_locations", [])}
            except (json.JSONDecodeError, OSError, ValueError) as e:
                logger.warning(f"Could not read existing Nightreign run state at {self.run_state_path}: {e}")
                self.checked_location_ids = set()
        else:
            self.checked_location_ids = set()
            self._write_run_state(seed_name, slot_name, events=[])

        logger.info(f"Nightreign run state file: {self.run_state_path}")

    def _write_run_state(self, seed_name: str, slot_name: str, events: list) -> None:
        data = {
            "seed_name": seed_name,
            "slot_name": slot_name,
            "checked_locations": sorted(self.checked_location_ids),
            "events": events,
        }
        with open(self.run_state_path, "w") as f:
            json.dump(data, f, indent=2)

    def _append_event(self, event: dict) -> None:
        if not self.run_state_path:
            return
        seed_name, slot_name = self._run_state_key()
        try:
            with open(self.run_state_path, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            data = {"seed_name": seed_name, "slot_name": slot_name, "checked_locations": [], "events": []}
        data["checked_locations"] = sorted(self.checked_location_ids)
        data.setdefault("events", []).append(event)
        with open(self.run_state_path, "w") as f:
            json.dump(data, f, indent=2)

    # --- Memory polling ---

    async def poll_loop(self) -> None:
        while True:
            try:
                if not self.reader.connected:
                    # A stale writer holds addresses from a now-dead process handle - don't let
                    # the next _sync_event_flags() reuse it after a fresh connect rebuilds it.
                    self.writer = None
                    try:
                        if self.reader.connect():
                            logger.info("Connected to nightreign.exe")
                            if self.gate_boss_access:
                                self._try_build_writer()
                                asyncio.create_task(self._sync_event_flags())
                                if self.writer is not None and self.overlay is None:
                                    self.overlay = NightreignOverlay(self.reader.pm.process_id)
                                    self.overlay.start()
                        else:
                            await asyncio.sleep(RECONNECT_INTERVAL)
                            continue
                    except PointerNotFoundError as e:
                        logger.error(f"{e} - is the game up to date with this client? Retrying in "
                                    f"{BUILD_MISMATCH_BACKOFF}s.")
                        await asyncio.sleep(BUILD_MISMATCH_BACKOFF)
                        continue

                pulse = self.reader.read_outcome_pulse()
                if pulse == 1 and self._last_pulse == 0:
                    await self._handle_win()
                if pulse is not None:
                    self._last_pulse = pulse

                if self.gate_boss_access and self.overlay is not None:
                    owned_names = self._owned_item_names()
                    locked_names = [
                        name for name in ACCESS_NIGHTLORDS if f"{name} Access" not in owned_names
                    ]
                    self.overlay.state.update(bool(self.reader.read_hub_state()), locked_names)
            except Exception:
                logger.exception("Error in Nightreign poll loop")
            await asyncio.sleep(POLL_INTERVAL)

    async def _handle_win(self) -> None:
        boss = self.reader.read_boss_id()
        character_name = self.reader.read_character_class_name()
        timestamp = datetime.now(timezone.utc).isoformat()

        if character_name is None:
            logger.warning("Detected a win, but couldn't read the character class - skipping this check.")
            return

        if boss.status != "matched":
            message = boss.message or f"boss_id {boss.raw} could not be resolved (status={boss.status})"
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

        name = location_name(character_name, boss.name)
        location_id = location_name_to_id.get(name)
        if location_id is None:
            # Character not in this player's included_characters/included_nightlords - nothing to send.
            logger.info(f"Win detected ({name}) but that location isn't in this slot's options - not sending.")
            return

        logger.info(f"Win detected: {name} (boss_id={boss.raw})")
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
        if not self.reader.connected:
            logger.info("Nightreign: not connected to the game process.")
            return
        character = self.reader.read_character_class_name()
        boss = self.reader.read_boss_id()
        in_hub = self.reader.read_hub_state()
        pulse = self.reader.read_outcome_pulse()
        boss_desc = boss.name or boss.message or boss.status
        logger.info(
            f"Nightreign status: character={character}  boss_id={boss.raw} ({boss_desc})  "
            f"in_hub={in_hub}  outcome_pulse={pulse}  run_state={self.run_state_path}"
        )


async def main(args) -> None:
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
