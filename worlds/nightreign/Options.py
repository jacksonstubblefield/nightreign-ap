"""Nightreign Options
"""

# Native Imports
from dataclasses import dataclass

# Outside Imports
from Options import Choice, OptionSet, PerGameCommonOptions, Range, Toggle

# Local Imports
from .game_data import ALL_NIGHTLORD_ENTRIES, CHARACTERS, EVERDARK_NIGHTLORDS, NIGHTLORDS


class IncludedCharacters(OptionSet):
    """Which characters to generate location checks for.
    """

    display_name = "Included Characters"
    valid_keys = frozenset(CHARACTERS)
    default = frozenset(CHARACTERS)


class IncludedNightlords(OptionSet):
    """Which Nightlords to generate location checks for. Each Everdark Sovereign is its own
    separate entry (e.g. "Everdark Tricephalos") - Everdark Sovereigns are entirely separate
    bosses from their base Nightlord (own check, own Access item), so add one explicitly to
    include its check; it is NOT implied by including the base Nightlord. Excluded by default,
    since reaching a specific Everdark Sovereign depends on an external weekly rotation this world
    can't unlock or guarantee - the actual availability is on you, the player.
    """

    display_name = "Included Nightlords"
    valid_keys = frozenset(ALL_NIGHTLORD_ENTRIES)
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
    option_balancers = 8
    option_dreglord = 9
    option_everdark_tricephalos = 10
    option_everdark_gaping_jaw = 11
    option_everdark_sentient_pest = 12
    option_everdark_augur = 13
    option_everdark_equilibrious_beast = 14
    option_everdark_darkdrift_night = 15
    option_everdark_fissure_in_the_fog = 16
    option_everdark_balancers = 17
    default = 0


# option_* values above are positionally mapped to game_data.NIGHTLORDS order (world code resolves
# a chosen value via NIGHTLORDS[value]) - this catches drift if the roster is ever reordered/edited.
assert [StartingBoss.name_lookup[i] for i in range(len(NIGHTLORDS))] == [
    name.lower().replace(" ", "_") for name in NIGHTLORDS
], "StartingBoss option values must stay in sync with game_data.NIGHTLORDS order."

# The everdark_* block right after continues positionally over EVERDARK_NIGHTLORDS (world code
# resolves a value >= len(NIGHTLORDS) via EVERDARK_NIGHTLORDS[value - len(NIGHTLORDS)]).
assert [
    StartingBoss.name_lookup[len(NIGHTLORDS) + i] for i in range(len(EVERDARK_NIGHTLORDS))
] == [
    "everdark_" + name.lower().replace(" ", "_") for name in EVERDARK_NIGHTLORDS
], "StartingBoss's everdark_* option values must stay in sync with game_data.EVERDARK_NIGHTLORDS order."


class GateBossAccess(Toggle):
    """If enabled, every Nightlord other than your chosen starting boss requires receiving that
    Nightlord's Access item before it counts as yours.
    """

    display_name = "Gate Boss Access Behind Items"
    default = 1


class UnlockAllBossesInGame(Toggle):
    """For new files: this ensures that bosses are unlocked in-game, bypassing the natural
    progression that Fromsoft intended for the player to follow.

    This permanently alters files - highly recommended you not use this option for a file you 
    intend to play online.
    """

    display_name = "Unlock for me"
    default = 0

    
class GateCharacterAccess(Toggle):
    """If enabled, receive access to characters from the multiworld.
    If disabled, all characters are available from the start.
    """

    display_name = "Gate Character Access Behind Items"
    default = 0


class StartingCharacter(Choice):
    """If character access is gated, this is the character you start with.
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


class GoalRandomMin(Range):
    """Minimum number of specific "Defeat X as Y" objectives to require, when goal is random_subset.
    """

    display_name = "Random Goal Minimum Objectives"
    range_start = 1
    range_end = len(CHARACTERS) * len(NIGHTLORDS)  # the largest possible combo count.
    default = 3


class GoalRandomMax(Range):
    """Maximum number of specific "Defeat X as Y" objectives to require, when goal is random_subset.
    """

    display_name = "Random Goal Maximum Objectives"
    range_start = 1
    range_end = len(CHARACTERS) * len(NIGHTLORDS)
    default = 8


@dataclass
class NightreignOptions(PerGameCommonOptions):
    included_characters: IncludedCharacters
    included_nightlords: IncludedNightlords
    bosses_with_characters: BossesWithCharacters
    starting_boss: StartingBoss
    gate_boss_access: GateBossAccess
    unlock_all_bosses_in_game: UnlockAllBossesInGame
    starting_character: StartingCharacter
    gate_character_access: GateCharacterAccess
    receive_weapons: ReceiveWeapons
    receive_talismans: ReceiveTalismans
    goal: Goal
    goal_random_min: GoalRandomMin
    goal_random_max: GoalRandomMax
