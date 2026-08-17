from BaseClasses import Region, Tutorial
from worlds.AutoWorld import World, WebWorld
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from .game_data import ACCESS_NIGHTLORDS, CHARACTERS, NIGHTLORDS
from .Items import FILLER_ITEM_NAMES, NightreignItem, item_name_to_id, item_table
from .Locations import NightreignLocation, location_name, location_name_to_id
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
    Location checks are "defeat Nightlord X as character Y", detected via
    read-only game memory polling. With the gate_boss_access option enabled,
    Nightlords beyond Tricephalos are also gated behind receiving their
    Access item, written into the running game process; otherwise received
    items are flavorful and have no in-game effect.
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

    def create_regions(self) -> None:
        included_characters = self.options.included_characters.value
        included_nightlords = self.options.included_nightlords.value

        # Iterate CHARACTERS/NIGHTLORDS (fixed order) rather than the option
        # sets directly, so location creation order - and therefore id
        # assignment order for anything downstream that relies on it - stays
        # deterministic regardless of set iteration order.
        self.active_locations = [
            location_name(character, nightlord)
            for character in CHARACTERS
            if character in included_characters
            for nightlord in NIGHTLORDS
            if nightlord in included_nightlords
        ]

        menu = Region("Menu", self.player, self.multiworld)
        menu.locations += [
            NightreignLocation(self.player, name, self.location_name_to_id[name], menu)
            for name in self.active_locations
        ]
        self.multiworld.regions.append(menu)

    def create_items(self) -> None:
        if not self.active_locations:
            return

        access_names = []
        if self.options.gate_boss_access:
            included_nightlords = self.options.included_nightlords.value
            access_names = [
                f"{name} Access" for name in ACCESS_NIGHTLORDS if name in included_nightlords
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
        return {"gate_boss_access": bool(self.options.gate_boss_access)}
