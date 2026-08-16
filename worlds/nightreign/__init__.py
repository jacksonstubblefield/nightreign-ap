from BaseClasses import Region, Tutorial
from worlds.AutoWorld import World, WebWorld
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from .game_data import CHARACTERS, NIGHTLORDS
from .Items import NightreignItem, item_name_to_id, item_table
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
    This is a tracker-only integration for v1: location checks are "defeat
    Nightlord X as character Y", detected via read-only game memory polling.
    The game itself is not modified or gated - received items are flavorful
    and have no in-game effect.
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
        self.multiworld.itempool += [self.create_filler() for _ in range(len(self.active_locations))]

    def create_item(self, name: str) -> NightreignItem:
        data = item_table[name]
        return NightreignItem(name, data.classification, data.code, self.player)

    def get_filler_item_name(self) -> str:
        return self.random.choice(list(item_table.keys()))
