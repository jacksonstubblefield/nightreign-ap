from dataclasses import dataclass

from Options import Choice, DeathLink, OptionSet, PerGameCommonOptions, Toggle

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


class CheckGranularity(Choice):
    """How location checks are generated.

    "boss" (default): one check per Nightlord - "Defeat X" - any character's win counts, and
    included_characters has no effect on what locations exist.

    "boss_and_character": one check per included character x included Nightlord combination -
    "Defeat X as Y" - the original, more granular mode.
    """

    display_name = "Check Granularity"
    option_boss = 0
    option_boss_and_character = 1
    default = 0


class StartingBoss(Choice):
    """Which Nightlord starts unlocked, before receiving any Access items - or "random" to have
    the generator pick one for this slot.

    This doesn't take Tricephalos away: it's always available in a fresh save with no flag write
    needed (see game_data.py), regardless of this option. Picking Tricephalos here (the default)
    matches that baseline exactly. Picking anything else additionally frees that Nightlord - and,
    for the 6 secondary Nightlords, its whole group, since the game only exposes one shared flag
    for all 6 and there's no way to unlock just one - without needing its Access item.
    """

    display_name = "Starting Boss"
    option_tricephalos = 0
    option_gaping_jaw = 1
    option_sentient_pest = 2
    option_augur = 3
    option_equilibrious_beast = 4
    option_darkdrift_night = 5
    option_fissure_in_the_fog = 6
    option_night_aspect = 7
    default = 0


# option_* values above are positionally mapped to game_data.NIGHTLORDS order (world code resolves
# a chosen value via NIGHTLORDS[value]) - this catches drift if the roster is ever reordered/edited.
assert [StartingBoss.name_lookup[i] for i in range(len(NIGHTLORDS))] == [
    name.lower().replace(" ", "_") for name in NIGHTLORDS
], "StartingBoss option values must stay in sync with game_data.NIGHTLORDS order."


class GateBossAccess(Toggle):
    """If enabled, Nightlords not already unlocked (by being Tricephalos or the chosen
    starting_boss) require receiving that Nightlord's Access item before you can select them
    in-game.

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
    check_granularity: CheckGranularity
    starting_boss: StartingBoss
    gate_boss_access: GateBossAccess
    death_link: DeathLink
