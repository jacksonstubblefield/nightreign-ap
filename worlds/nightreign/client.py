"""Archipelago client for Elden Ring Nightreign.

v1 is a read-only tracker (see the project plan's scope decision): polls the
running game via memory_reader.py and sends a location check on each
detected Nightlord win. Received items have no in-game effect yet - the base
CommonContext/CLI/GUI machinery already logs them, nothing extra needed here.
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

from .Locations import location_name, location_name_to_id
from .memory_reader import NightreignMemoryReader, PointerNotFoundError

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

    _last_pulse: Optional[int]

    def __init__(self, server_address: Optional[str], password: Optional[str]):
        super().__init__(server_address, password)
        self.reader = NightreignMemoryReader()
        self.poll_task = None
        self.run_state_path = None
        self.checked_location_ids = set()
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
            self._open_run_state()
            # Replay anything our local state already thinks is checked, in
            # case the server and our local record ever drifted (e.g. a
            # connection dropped mid-send). check_locations() only sends
            # what's still in ctx.missing_locations, so this is always safe.
            if self.checked_location_ids:
                asyncio.create_task(self.check_locations(self.checked_location_ids))

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
                    try:
                        if self.reader.connect():
                            logger.info("Connected to nightreign.exe")
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
