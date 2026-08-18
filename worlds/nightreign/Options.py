"""Nightreign Options
"""

# Native Imports
from dataclasses import dataclass

# Outside Imports
from Options import Choice, OptionSet, PerGameCommonOptions, Toggle

# Local Imports
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


class BossesWithCharacters(Choice):
    """If location checks are generated as just defeating the boss or defeating 
    the boss as a specific character.

    "boss" (default): one check per Nightlord - "Defeat X" - any character's win counts, and
    included_characters has no effect on what locations exist.

    "boss_and_character": one check per included character x included Nightlord combination -
    "Defeat X as Y" - the original, more granular mode.
    """

    display_name = "Bosses With Characters"
    option_boss = 0
    option_boss_and_character = 1
    default = 0


class StartingBoss(Choice):
    """Which Nightlord starts unlocked, before receiving any Access items - or "random" to have
    the generator pick one for this slot.

    Picking Tricephalos here (the default) frees it from an AP perspective, matching how it's
    already always selectable in-game on a fresh save with no flag write needed (see game_data.py)
    - so no Access item for it needs to be found. Picking anything else means Tricephalos is
    NOT free: like any other Nightlord that isn't your starting_boss, you'll need to receive its
    Access item before it counts as yours, even though the vanilla game still lets you select it
    (the overlay is what shows you that mismatch - see GateBossAccess). Picking one of the 6
    secondary Nightlords additionally frees just that one from an AP perspective, without needing
    its Access item - though the game's own all-or-nothing flag will also reveal its 5 siblings
    in-game as an unavoidable side effect; those still need their own Access item to actually be
    yours.
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
    """If enabled, every Nightlord other than your chosen starting_boss requires receiving that
    Nightlord's Access item before it counts as yours.

    This writes to the running game process (not just reads) and needs Borderless Windowed mode
    so the client can show an overlay of which bosses you actually own. The underlying game only
    supports gating in two ways - Tricephalos is always selectable with no flag at all, and the
    other 6 secondary Nightlords reveal as one all-or-nothing batch - so plenty of not-yet-owned
    Nightlords (Tricephalos included) can still be visible/selectable in-game; the overlay exists
    to show you which ones those are.

    On by default.
    """

    display_name = "Gate Boss Access Behind Items"
    default = 1


@dataclass
class NightreignOptions(PerGameCommonOptions):
    included_characters: IncludedCharacters
    included_nightlords: IncludedNightlords
    bosses_with_characters: BossesWithCharacters
    starting_boss: StartingBoss
    gate_boss_access: GateBossAccess
