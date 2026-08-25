from BaseClasses import LocationProgressType, Region, Tutorial
from Options import OptionError
from worlds.AutoWorld import World, WebWorld
from worlds.LauncherComponents import Component, Type, components, icon_paths, launch_subprocess

from .game_data import (ACCESS_CHARACTERS, ACCESS_NIGHTLORDS, CHARACTERS, EVERDARK_NIGHTLORDS,
                        NIGHTLORDS, starting_free_characters, starting_free_nightlords)
from .Items import FILLER_ITEM_NAMES, NightreignItem, item_name_to_id, item_table
from .Locations import (NightreignLocation, location_name, location_name_boss_only,
                        location_name_everdark, location_name_everdark_boss_only,
                        location_name_to_id)
from .Options import NightreignOptions


def launch_client():
    # Lazy import so `pymem` isn't imported at world-load time - Generate.py and the webhost
    # load every world's __init__.py unconditionally, but only need the client when a user
    # launches it from the Archipelago Launcher.
    from .client import launch

    launch_subprocess(launch, name="NightreignClient")


components.append(Component("Nightreign Client", func=launch_client, component_type=Type.CLIENT, icon="nightreign"))
icon_paths["nightreign"] = f"ap:{__name__}/data/image.png"


class NightreignWeb(WebWorld):
    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up the Archipelago Elden Ring Nightreign tracker.",
        "English",
        "setup_en.md",
        "setup/en",
        ["jrstubb"],
    )

    tutorials = [setup_en]


class NightreignWorld(World):
    """
    Elden Ring Nightreign is a co-op roguelike action game from FromSoftware.
    Location checks are "defeat Nightlord X" (or, with bosses_with_characters set
    to boss_and_character, "defeat Nightlord X as character Y"), detected via
    read-only game memory polling. With the gate_boss_access option enabled,
    every Nightlord other than the chosen starting_boss is gated behind
    receiving that Nightlord's Access item - written into the running game
    process where the game supports it (all but Tricephalos, which has no
    gating flag and is tracked overlay-side only); otherwise received items
    are flavorful and have no in-game effect. The gate_character_access option works the same way
    for playable characters instead of Nightlords - every character other than the chosen
    starting_character is gated behind receiving that character's Character Access item, and with
    bosses_with_characters set to boss_and_character, a win as a not-yet-unlocked character also
    doesn't send its check. With enable_everdark_checks on, defeating a
    Nightlord's Everdark Sovereign variant is a separate, optional location - never required for
    the goal, since Everdark availability depends on an external weekly rotation this world can't
    unlock or guarantee (see Options.py's disclaimer).
    """

    game = "Elden Ring Nightreign"
    web = NightreignWeb()

    options_dataclass = NightreignOptions
    options: NightreignOptions

    topology_present = False

    base_id = 3939000
    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id

    active_locations: list[str]
    starting_boss: str
    freed_nightlords: set
    starting_character: str
    freed_characters: set
    goal_groups: list[list[int]]
    goal_random_count: int

    def generate_early(self) -> None:
        # No item/location gating here (topology_present = False), so there's no CollectionState
        # condition that reflects real progress - the goal is only observed live by the client
        # (see client.py's _maybe_declare_goal). Set explicitly, per docs/adding games.md.
        self.multiworld.completion_condition[self.player] = lambda state: True

        if not self.options.receive_weapons and not self.options.receive_talismans:
            # There is no other flavorful filler item left (Trophy items were removed once
            # Randomized Weapon/Talisman gave real in-game drops) - with both options off,
            # get_filler_item_name() would have an empty pool to choose from.
            raise OptionError(
                f"{self.player_name}: at least one of receive_weapons/receive_talismans must be "
                "enabled, since filler items are drawn from those two pools."
            )

        self.starting_boss = NIGHTLORDS[self.options.starting_boss.value]
        self.freed_nightlords = set(starting_free_nightlords(self.starting_boss))
        self.starting_character = CHARACTERS[self.options.starting_character.value]
        self.freed_characters = set(starting_free_characters(self.starting_character))

        included_characters = self.options.included_characters.value
        included_nightlords = self.options.included_nightlords.value
        per_character = self.options.bosses_with_characters == "boss_and_character"

        if self.options.goal == "random_subset" and not per_character:
            raise OptionError(
                f"{self.player_name}: goal 'random_subset' requires bosses_with_characters to "
                "be 'boss_and_character'."
            )
        if self.options.goal == "night_aspect" and "Night Aspect" not in included_nightlords:
            raise OptionError(
                f"{self.player_name}: goal 'night_aspect' requires Night Aspect to be in "
                "included_nightlords, or the goal can never be completed."
            )

        self.goal_random_count = 0
        if self.options.goal == "random_subset":
            available = len(included_characters) * len(included_nightlords)
            goal_min = self.options.goal_random_min.value
            goal_max = self.options.goal_random_max.value
            if goal_min > available:
                raise OptionError(
                    f"{self.player_name}: goal_random_min ({goal_min}) is higher than the "
                    f"number of included_characters x included_nightlords combinations "
                    f"available ({available})."
                )
            if goal_min > goal_max:
                raise OptionError(
                    f"{self.player_name}: goal_random_min ({goal_min}) is higher than "
                    f"goal_random_max ({goal_max})."
                )
            self.goal_random_count = self.random.randint(goal_min, min(goal_max, available))

    def create_regions(self) -> None:
        included_nightlords = self.options.included_nightlords.value

        # Iterate CHARACTERS/NIGHTLORDS (fixed order) rather than the option sets directly, so
        # location creation order stays deterministic. Each location is paired with the Nightlord
        # it defeats (and, in boss_and_character mode, the character - None in "boss" mode, since
        # locations aren't tied to a specific character there) so the access rule below can gate
        # it without re-parsing the location name.
        if self.options.bosses_with_characters == "boss_and_character":
            included_characters = self.options.included_characters.value
            locations = [
                (location_name(character, nightlord), nightlord, character)
                for character in CHARACTERS
                if character in included_characters
                for nightlord in NIGHTLORDS
                if nightlord in included_nightlords
            ]
        else:
            locations = [
                (location_name_boss_only(nightlord), nightlord, None)
                for nightlord in NIGHTLORDS
                if nightlord in included_nightlords
            ]

        # enable_everdark_checks locations mirror bosses_with_characters exactly like the normal
        # locations above, but over EVERDARK_NIGHTLORDS (excludes Night Aspect, which has no
        # Everdark form) and are gated behind the option entirely - empty list when it's off.
        # Deliberately kept out of goal_groups below (see Options.py's disclaimer): Everdark
        # Sovereign availability depends on an external weekly rotation this world can't unlock or
        # guarantee, so requiring one for the goal could make a seed impossible to finish.
        everdark_locations = []
        if self.options.enable_everdark_checks:
            everdark_nightlords = [nl for nl in included_nightlords if nl in EVERDARK_NIGHTLORDS]
            if self.options.bosses_with_characters == "boss_and_character":
                included_characters = self.options.included_characters.value
                everdark_locations = [
                    (location_name_everdark(character, nightlord), nightlord, character)
                    for character in CHARACTERS
                    if character in included_characters
                    for nightlord in EVERDARK_NIGHTLORDS
                    if nightlord in everdark_nightlords
                ]
            else:
                everdark_locations = [
                    (location_name_everdark_boss_only(nightlord), nightlord, None)
                    for nightlord in EVERDARK_NIGHTLORDS
                    if nightlord in everdark_nightlords
                ]

        self.active_locations = [
            name for name, _nightlord, _character in locations + everdark_locations
        ]

        # goal_groups: a list of groups, each satisfied by ANY one of its location ids being
        # checked; the goal is complete once EVERY group is satisfied (see client.py's
        # _goal_complete). This varies by `goal` option; the location set above never changes.
        # Built from `locations` only - everdark_locations is never goal-eligible, see above.
        goal = self.options.goal.current_key
        ids_by_name = self.location_name_to_id
        if goal == "night_aspect":
            self.goal_groups = [[
                ids_by_name[name] for name, nightlord, _character in locations
                if nightlord == "Night Aspect"
            ]]
        elif goal == "all_bosses_any_character":
            self.goal_groups = [
                [ids_by_name[name] for name, nl, _character in locations if nl == nightlord]
                for nightlord in NIGHTLORDS
                if nightlord in included_nightlords
            ]
        elif goal == "random_subset":
            chosen = self.random.sample(locations, self.goal_random_count)
            self.goal_groups = [[ids_by_name[name]] for name, _nightlord, _character in chosen]
        else:
            self.goal_groups = [[ids_by_name[name]] for name, _nightlord, _character in locations]

        menu = Region("Menu", self.player, self.multiworld)

        def _make_location(
            name: str, nightlord: str, everdark: bool, character: str | None
        ) -> NightreignLocation:
            location = NightreignLocation(self.player, name, self.location_name_to_id[name], menu)
            # Without this, the fill algorithm has no idea defeating a Nightlord requires
            # earning it first - it can (and did) place the only route to a Nightlord behind an
            # unreachable location, softlocking the run. gate_boss_access off needs no rule.
            # Everdark locations reuse the same base Nightlord's Access item - there's no separate
            # "Everdark X Access" item, since Everdark is a variant fight against the same
            # Nightlord, not a distinct one. character is only set in boss_and_character mode - in
            # "boss" mode no location is tied to a specific character, so gate_character_access
            # there only controls in-game unlocking, never location reachability. Combined via a
            # small AND-rule when both the Nightlord and the character are gated, the same way AP's
            # access_rule mechanism is meant to be composed.
            rules = []
            if self.options.gate_boss_access and nightlord not in self.freed_nightlords:
                rules.append(lambda state, nightlord=nightlord: state.has(
                    f"{nightlord} Access", self.player
                ))
            if (character is not None and self.options.gate_character_access
                    and character not in self.freed_characters):
                rules.append(lambda state, character=character: state.has(
                    f"{character} Character Access", self.player
                ))
            if len(rules) == 1:
                location.access_rule = rules[0]
            elif rules:
                location.access_rule = lambda state, rules=rules: all(rule(state) for rule in rules)
            if everdark:
                # EXCLUDED stops the fill algorithm from ever placing a progression/useful item
                # here (see BaseClasses.Location.can_fill) - keeping Everdark locations out of
                # goal_groups isn't enough on its own, since AP can still place an Access item
                # *other* locations depend on into one. A real generated seed did exactly that
                # (starting_boss=Tricephalos: "Defeat Everdark Tricephalos" held the only copy of
                # "Sentient Pest Access", the sole route out of the starting Nightlord) - since
                # Everdark availability is an external, uncertain weekly rotation (see Options.py's
                # disclaimer), nothing else in the graph may ever depend on reaching one.
                location.progress_type = LocationProgressType.EXCLUDED
            return location

        for name, nightlord, character in locations:
            menu.locations.append(
                _make_location(name, nightlord, everdark=False, character=character)
            )
        for name, nightlord, character in everdark_locations:
            menu.locations.append(
                _make_location(name, nightlord, everdark=True, character=character)
            )
        self.multiworld.regions.append(menu)

    def create_items(self) -> None:
        if not self.active_locations:
            return

        access_names = []
        if self.options.gate_boss_access:
            included_nightlords = self.options.included_nightlords.value
            access_names = [
                f"{name} Access" for name in ACCESS_NIGHTLORDS
                if name in included_nightlords and name not in self.freed_nightlords
            ]

        character_access_names = []
        if self.options.gate_character_access:
            included_characters = self.options.included_characters.value
            character_access_names = [
                f"{name} Character Access" for name in ACCESS_CHARACTERS
                if name in included_characters and name not in self.freed_characters
            ]

        self.multiworld.itempool += [self.create_item(name) for name in access_names]
        self.multiworld.itempool += [self.create_item(name) for name in character_access_names]

        # access_names is always <= active_locations: location count is
        # |included_characters| * |included_nightlords|, at least |included_nightlords|
        # (and therefore at least len(access_names)) whenever it's non-empty. character_access_names
        # has no equivalent guarantee - in "boss" mode active_locations is bounded only by
        # |included_nightlords|, independent of |included_characters|, so a slot could ask for more
        # Character Access items than there are locations to hold them (e.g. many included
        # characters but a single included Nightlord). Guard explicitly rather than let
        # itempool/location counts silently desync.
        total_progression = len(access_names) + len(character_access_names)
        if total_progression > len(self.active_locations):
            raise OptionError(
                f"{self.player_name}: gate_boss_access/gate_character_access together need "
                f"{total_progression} progression item slots, but only "
                f"{len(self.active_locations)} locations are generated with the current "
                "bosses_with_characters/included_characters/included_nightlords settings - not "
                "enough room to place them. Include more characters/Nightlords, switch "
                "bosses_with_characters to boss_and_character, or disable one of the gating "
                "options."
            )

        filler_count = len(self.active_locations) - total_progression
        self.multiworld.itempool += [self.create_filler() for _ in range(filler_count)]

    def create_item(self, name: str) -> NightreignItem:
        data = item_table[name]
        return NightreignItem(name, data.classification, data.code, self.player)

    def get_filler_item_name(self) -> str:
        names = FILLER_ITEM_NAMES
        if self.options.receive_weapons:
            names = names + ["Randomized Weapon"]
        if self.options.receive_talismans:
            names = names + ["Randomized Talisman"]
        return self.random.choice(names)

    def fill_slot_data(self) -> dict:
        return {
            "gate_boss_access": bool(self.options.gate_boss_access),
            "gate_character_access": bool(self.options.gate_character_access),
            "receive_weapons": bool(self.options.receive_weapons),
            "receive_talismans": bool(self.options.receive_talismans),
            "enable_everdark_checks": bool(self.options.enable_everdark_checks),
            "starting_boss": self.starting_boss,
            "starting_character": self.starting_character,
            "bosses_with_characters": self.options.bosses_with_characters.current_key,
            "goal": self.options.goal.current_key,
            "goal_groups": self.goal_groups,
        }
