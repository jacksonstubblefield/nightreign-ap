from typing import NamedTuple

from BaseClasses import Location

from .game_data import CHARACTERS, NIGHTLORDS


class NightreignLocation(Location):
    game: str = "Elden Ring Nightreign"


class LocationData(NamedTuple):
    id: int


base_id = 3940000  # separate range from Items.py's - item/location ids are independent namespaces


def location_name(character: str, nightlord: str) -> str:
    return f"Defeat {nightlord} as {character}"


# One location per (character x Nightlord) combination - the full matrix,
# regardless of a given player's included_characters/included_nightlords
# options. World.create_regions() filters this down per-player; this table
# just needs to cover every name/id any player could pick.
location_table = {
    location_name(character, nightlord): LocationData(base_id + i)
    for i, (character, nightlord) in enumerate(
        (character, nightlord) for character in CHARACTERS for nightlord in NIGHTLORDS
    )
}

location_name_to_id = {name: data.id for name, data in location_table.items()}
lookup_id_to_name = {data.id: name for name, data in location_table.items()}
