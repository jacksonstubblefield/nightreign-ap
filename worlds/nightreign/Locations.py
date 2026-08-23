from typing import NamedTuple

from BaseClasses import Location

from .game_data import CHARACTERS, EVERDARK_NIGHTLORDS, NIGHTLORDS


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


def location_name_everdark(character: str, nightlord: str) -> str:
    """Generates location names for the enable_everdark_checks option in BossWithCharacter mode.

    Args:
        character (str): Nightreign character name
        nightlord (str): Nightlord name (must have an Everdark form - see EVERDARK_NIGHTLORDS)

    Returns:
        str: The generated location name.
    """
    return f"Defeat Everdark {nightlord} as {character}"


def location_name_everdark_boss_only(nightlord: str) -> str:
    """Generates location names for the enable_everdark_checks option in Boss mode.

    Args:
        nightlord (str): Nightlord name (must have an Everdark form - see EVERDARK_NIGHTLORDS)

    Returns:
        str: The generated location name.
    """
    return f"Defeat Everdark {nightlord}"


# One location per (character x Nightlord), plus one boss-only location per Nightlord, plus the
# same two shapes again for Everdark (over EVERDARK_NIGHTLORDS, which excludes Night Aspect) - the
# full matrix regardless of a player's options (World.create_regions() filters it per-player).
# Each table is appended after the last, never interleaved, so ids never shift for older seeds.
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
_everdark_per_character_table = {
    location_name_everdark(character, nightlord): LocationData(
        BASE_ID + len(_per_character_table) + len(_boss_only_table) + i
    )
    for i, (character, nightlord) in enumerate(
        (character, nightlord) for character in CHARACTERS for nightlord in EVERDARK_NIGHTLORDS
    )
}
_everdark_boss_only_table = {
    location_name_everdark_boss_only(nightlord): LocationData(
        BASE_ID + len(_per_character_table) + len(_boss_only_table)
        + len(_everdark_per_character_table) + i
    )
    for i, nightlord in enumerate(EVERDARK_NIGHTLORDS)
}
location_table = (
    _per_character_table | _boss_only_table
    | _everdark_per_character_table | _everdark_boss_only_table
)

location_name_to_id = {name: data.id for name, data in location_table.items()}
lookup_id_to_name = {data.id: name for name, data in location_table.items()}
