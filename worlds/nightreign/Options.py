from dataclasses import dataclass

from Options import DeathLink, OptionSet, PerGameCommonOptions, Toggle

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


class GateBossAccess(Toggle):
    """If enabled, Nightlords beyond Tricephalos require receiving that
    Nightlord's Access item before you can select them in-game.

    This writes to the running game process (not just reads) and needs
    Borderless Windowed mode so the client can show an overlay of which
    bosses you actually own - the underlying game flag reveals the 6
    secondary Nightlords in one all-or-nothing batch, so some not-yet-owned
    ones will still be visible/selectable in-game; the overlay exists to
    show you which is which.

    Off by default - this is new, and both the write path and the overlay
    are less tested than the read-only tracker.
    """

    display_name = "Gate Boss Access Behind Items"


@dataclass
class NightreignOptions(PerGameCommonOptions):
    included_characters: IncludedCharacters
    included_nightlords: IncludedNightlords
    gate_boss_access: GateBossAccess
    death_link: DeathLink
