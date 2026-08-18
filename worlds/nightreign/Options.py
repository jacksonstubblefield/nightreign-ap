"""Nightreign Options
"""

# Native Imports
from dataclasses import dataclass

# Outside Imports
from Options import Choice, OptionSet, PerGameCommonOptions, Range, Toggle

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


class Goal(Choice):
    """What this slot needs to accomplish to complete its goal.

    "all_bosses" (default): every included character x Nightlord location (per
    bosses_with_characters) must be checked - the original behavior.

    "night_aspect": defeat Night Aspect - the vanilla game's own ending/credits boss. With
    bosses_with_characters set to boss_and_character, any one included character's Night
    Aspect win counts (matches how the vanilla game rolls credits on the first Night Aspect
    kill regardless of character). Night Aspect must be in included_nightlords, or this goal
    is unreachable.

    "all_bosses_any_character": defeat every included Nightlord at least once, with any
    included character - only differs from all_bosses when bosses_with_characters is
    boss_and_character (in "boss" mode they're identical, since there's already only one
    location per Nightlord). Every included character x Nightlord location still gets
    generated as a regular, non-required check - this only changes what's required to finish.

    "random_subset": bosses_with_characters must be boss_and_character. At generation time,
    a random number of specific "Defeat X as Y" locations (between goal_random_min and
    goal_random_max, drawn only from this slot's included_characters x included_nightlords,
    no duplicates) are selected as the required objective set. Every other included
    combination still exists as a regular, non-required check.
    """

    display_name = "Goal"
    option_all_bosses = 0
    option_night_aspect = 1
    option_all_bosses_any_character = 2
    option_random_subset = 3
    default = 0


class GoalRandomMin(Range):
    """Minimum number of specific "Defeat X as Y" objectives to require, when goal is random_subset.

    Ignored unless goal is set to random_subset.
    """

    display_name = "Random Goal Minimum Objectives"
    range_start = 1
    range_end = 80  # len(CHARACTERS) * len(NIGHTLORDS), the largest possible combo count.
    default = 3


class GoalRandomMax(Range):
    """Maximum number of specific "Defeat X as Y" objectives to require, when goal is random_subset.

    Ignored unless goal is set to random_subset. Silently clamped down to however many
    included_characters x included_nightlords combinations this slot actually has available,
    if set higher than that.
    """

    display_name = "Random Goal Maximum Objectives"
    range_start = 1
    range_end = 80
    default = 8


@dataclass
class NightreignOptions(PerGameCommonOptions):
    included_characters: IncludedCharacters
    included_nightlords: IncludedNightlords
    bosses_with_characters: BossesWithCharacters
    starting_boss: StartingBoss
    gate_boss_access: GateBossAccess
    goal: Goal
    goal_random_min: GoalRandomMin
    goal_random_max: GoalRandomMax
