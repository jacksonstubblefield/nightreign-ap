from BaseClasses import Region, Tutorial
from worlds.AutoWorld import World, WebWorld
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from .game_data import ACCESS_NIGHTLORDS, CHARACTERS, NIGHTLORDS, starting_free_nightlords
from .Items import FILLER_ITEM_NAMES, NightreignItem, item_name_to_id, item_table
from .Locations import NightreignLocation, location_name, location_name_boss_only, location_name_to_id
from .Options import NightreignOptions


def launch_client():
    # Lazy import so `pymem` (required by client.py's memory_reader use)
    # isn't imported at world-load time - Generate.py and the webhost load
    # every world's __init__.py unconditionally, but only actually need the
    # client when a user launches it from the Archipelago Launcher.
    from .client import launch

    launch_subprocess(launch, name="NightreignClient")


components.append(Component("Nightreign Client", func=launch_client, component_type=Type.CLIENT))


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
    Location checks are "defeat Nightlord X" (or, with check_granularity set
    to boss_and_character, "defeat Nightlord X as character Y"), detected via
    read-only game memory polling. With the gate_boss_access option enabled,
    every Nightlord other than the chosen starting_boss is gated behind
    receiving that Nightlord's Access item - written into the running game
    process where the game supports it (all but Tricephalos, which has no
    gating flag and is tracked overlay-side only); otherwise received items
    are flavorful and have no in-game effect.
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

    def generate_early(self) -> None:
        # This tracker has no item/location gating at all (topology_present
        # = False, every location reachable from the start), so there's no
        # CollectionState-derived condition that could reflect real
        # progress - the actual goal ("every included character x Nightlord
        # combination checked") can only be observed live, by the client,
        # via ctx.missing_locations (see client.py's _maybe_declare_goal).
        # Set explicitly (rather than relying on the silent BaseClasses
        # default of the same value) so that choice is visible in code, per
        # docs/adding games.md's "a set completion condition" requirement.
        self.multiworld.completion_condition[self.player] = lambda state: True

        self.starting_boss = NIGHTLORDS[self.options.starting_boss.value]
        self.freed_nightlords = set(starting_free_nightlords(self.starting_boss))

    def create_regions(self) -> None:
        included_nightlords = self.options.included_nightlords.value

        # Iterate CHARACTERS/NIGHTLORDS (fixed order) rather than the option
        # sets directly, so location creation order - and therefore id
        # assignment order for anything downstream that relies on it - stays
        # deterministic regardless of set iteration order. Each location is
        # paired with the Nightlord it defeats so the access rule below can
        # gate it without re-parsing "Defeat X" / "Defeat X as Y" apart.
        if self.options.bosses_with_characters == "boss_and_character":
            included_characters = self.options.included_characters.value
            locations = [
                (location_name(character, nightlord), nightlord)
                for character in CHARACTERS
                if character in included_characters
                for nightlord in NIGHTLORDS
                if nightlord in included_nightlords
            ]
        else:
            locations = [
                (location_name_boss_only(nightlord), nightlord)
                for nightlord in NIGHTLORDS
                if nightlord in included_nightlords
            ]
        self.active_locations = [name for name, _nightlord in locations]

        menu = Region("Menu", self.player, self.multiworld)
        for name, nightlord in locations:
            location = NightreignLocation(self.player, name, self.location_name_to_id[name], menu)
            # Without this, every location is unconditionally reachable and the fill
            # algorithm has no idea that defeating a Nightlord requires having earned
            # it first - it can (and did) place the only route to a Nightlord behind a
            # location that's itself unreachable from starting_boss, softlocking the
            # run. gate_boss_access off means no Access items exist at all, so no rule
            # is needed there either.
            if self.options.gate_boss_access and nightlord not in self.freed_nightlords:
                location.access_rule = lambda state, nightlord=nightlord: state.has(
                    f"{nightlord} Access", self.player
                )
            menu.locations.append(location)
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

        self.multiworld.itempool += [self.create_item(name) for name in access_names]

        # access_names is always <= active_locations: location count is
        # |included_characters| * |included_nightlords|, which is at least
        # |included_nightlords| (and therefore at least len(access_names))
        # whenever active_locations is non-empty, i.e. at least one
        # character is included.
        filler_count = len(self.active_locations) - len(access_names)
        self.multiworld.itempool += [self.create_filler() for _ in range(filler_count)]

    def create_item(self, name: str) -> NightreignItem:
        data = item_table[name]
        return NightreignItem(name, data.classification, data.code, self.player)

    def get_filler_item_name(self) -> str:
        return self.random.choice(FILLER_ITEM_NAMES)

    def fill_slot_data(self) -> dict:
        return {
            "gate_boss_access": bool(self.options.gate_boss_access),
            "starting_boss": self.starting_boss,
            "bosses_with_characters": self.options.bosses_with_characters.current_key,
        }
