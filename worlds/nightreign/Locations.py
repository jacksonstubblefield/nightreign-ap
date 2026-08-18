from typing import NamedTuple

from BaseClasses import Location

from .game_data import CHARACTERS, NIGHTLORDS


class NightreignLocation(Location):
    """NightreignLocation is a subclass of Location that represents a location in the Nightreign game.
    """
    game: str = "Elden Ring Nightreign"


class LocationData(NamedTuple):
    """A simple data structure to hold information about a location in the Nightreign game.
    """
    id: int


BASE_ID = 3940000  # separate range from Items.py's - item/location ids are independent namespaces


def location_name(character: str, nightlord: str) -> str:
    """Generates location names for BossWithCharacter mode

    Args:
        character (str): Nightreign character name
        nightlord (str): Nightlord name

    Returns:
        str: The generated location name.
    """
    return f"Defeat {nightlord} as {character}"


def location_name_boss_only(nightlord: str) -> str:
    """Generates location names for Boss mode

    Args:
        nightlord (str): Nightlord name

    Returns:
        str: The generated location name.
    """
    return f"Defeat {nightlord}"


# One location per (character x Nightlord) combination, plus one boss-only location per Nightlord -
# the full matrix for both bosses_with_characters modes, regardless of a given player's
# included_characters/included_nightlords/bosses_with_characters options. World.create_regions() filters
# this down per-player; this table just needs to cover every name/id any player could pick.
#
# The boss-only entries are appended after the per-character range (not interleaved) so existing
# per-character location ids never shift for seeds already generated before bosses_with_characters existed.
_per_character_table = {
    location_name(character, nightlord): LocationData(BASE_ID + i)
    for i, (character, nightlord) in enumerate(
        (character, nightlord) for character in CHARACTERS for nightlord in NIGHTLORDS
    )
}
_boss_only_table = {
    location_name_boss_only(nightlord): LocationData(BASE_ID + len(_per_character_table) + i)
    for i, nightlord in enumerate(NIGHTLORDS)
}
location_table = _per_character_table | _boss_only_table

location_name_to_id = {name: data.id for name, data in location_table.items()}
lookup_id_to_name = {data.id: name for name, data in location_table.items()}
