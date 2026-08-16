from dataclasses import dataclass

from Options import DeathLink, OptionSet, PerGameCommonOptions

from .game_data import CHARACTERS, NIGHTLORDS


class IncludedCharacters(OptionSet):
    """Which characters to generate location checks for.

    One location is generated per included character x included Nightlord
    combination. Defaults to all characters.
    """

    display_name = "Included Characters"
    valid_keys = frozenset(CHARACTERS)
    default = frozenset(CHARACTERS)


class IncludedNightlords(OptionSet):
    """Which Nightlords to generate location checks for.

    One location is generated per included character x included Nightlord
    combination. Defaults to all currently-supported Nightlords - DLC
    Nightlord(s) aren't supported yet, see the game page for status.
    """

    display_name = "Included Nightlords"
    valid_keys = frozenset(NIGHTLORDS)
    default = frozenset(NIGHTLORDS)


@dataclass
class NightreignOptions(PerGameCommonOptions):
    included_characters: IncludedCharacters
    included_nightlords: IncludedNightlords
    death_link: DeathLink
