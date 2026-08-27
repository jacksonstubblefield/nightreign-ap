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
    """

    display_name = "Included Characters"
    valid_keys = frozenset(CHARACTERS)
    default = frozenset(CHARACTERS)


class IncludedNightlords(OptionSet):
    """Which Nightlords to generate location checks for.
    """

    display_name = "Included Nightlords"
    valid_keys = frozenset(NIGHTLORDS)
    default = frozenset(NIGHTLORDS)


class BossesWithCharacters(Choice):
    """Enable this if you want to generate checks for defeating each boss with each character, 
    rather than just one check per boss.
    """

    display_name = "Bosses With Characters"
    option_boss = 0
    option_boss_and_character = 1
    default = 0


class StartingBoss(Choice):
    """Which Nightlord starts unlocked, before receiving any Access items - or "random" to have
    the generator pick one for this slot.
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
    """

    display_name = "Gate Boss Access Behind Items"
    default = 1


class StartingCharacter(Choice):
    """Which character starts unlocked, before receiving any Character Access items - or "random"
    to have the generator pick one for this slot.
    """

    display_name = "Starting Character"
    option_wylder = 0
    option_guardian = 1
    option_ironeye = 2
    option_duchess = 3
    option_raider = 4
    option_revenant = 5
    option_recluse = 6
    option_executor = 7
    option_scholar = 8
    option_undertaker = 9
    default = 0


# option_* values above are positionally mapped to game_data.CHARACTERS order (world code resolves
# a chosen value via CHARACTERS[value]) - this catches drift if the roster is ever reordered/edited.
assert [StartingCharacter.name_lookup[i] for i in range(len(CHARACTERS))] == [
    name.lower().replace(" ", "_") for name in CHARACTERS
], "StartingCharacter option values must stay in sync with game_data.CHARACTERS order."


class GateCharacterAccess(Toggle):
    """If enabled, receive access to characters from the multiworld.
    If disabled, all characters are available from the start.
    """

    display_name = "Gate Character Access Behind Items"
    default = 0


class ReceiveWeapons(Toggle):
    """If enabled, includes randomized weapons as filler items.
    """

    display_name = "Receive Weapons"
    default = 1


class ReceiveTalismans(Toggle):
    """If enabled, includes randomized talismans as filler items.
    """

    display_name = "Receive Talismans"
    default = 1


class Goal(Choice):
    """What this slot needs to accomplish to complete its goal.

    "Night Aspect" (default): defeat Night Aspect - the vanilla game's own ending/credits boss.

    "All Bosses": defeat every boss with every included character. A titanic goal.

    "All Bosses Any Character": defeat every included Nightlord at least once.

    "Random": creates a random subset of defeating nightlords as random characters. 
    """

    display_name = "Goal"
    option_night_aspect = 0
    option_all_bosses = 1
    option_all_bosses_any_character = 2
    option_random_subset = 3
    default = 0


class EnableEverdarkChecks(Toggle):
    """If enabled, adds checks for defeating Everdark Soverigns.

    Note: The Nightreign client cannot unlock access to Everdark Sovereigns, you'll have to find
    an alternative source for selecting them in the expedition menu. 
    """

    display_name = "Enable Everdark Checks"
    default = 0


class GoalRandomMin(Range):
    """Minimum number of specific "Defeat X as Y" objectives to require, when goal is random_subset.
    """

    display_name = "Random Goal Minimum Objectives"
    range_start = 1
    range_end = 80  # len(CHARACTERS) * len(NIGHTLORDS), the largest possible combo count.
    default = 3


class GoalRandomMax(Range):
    """Maximum number of specific "Defeat X as Y" objectives to require, when goal is random_subset.
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
    starting_character: StartingCharacter
    gate_character_access: GateCharacterAccess
    receive_weapons: ReceiveWeapons
    receive_talismans: ReceiveTalismans
    enable_everdark_checks: EnableEverdarkChecks
    goal: Goal
    goal_random_min: GoalRandomMin
    goal_random_max: GoalRandomMax
