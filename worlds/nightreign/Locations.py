from typing import NamedTuple, Optional

from BaseClasses import Location

from .game_data import (CHARACTERS, EVERDARK_NIGHTLORDS, NIGHTLORD_BONUS_INDICES, NIGHTLORDS,
                        REWARD_CHECK_THRESHOLDS, WIN_COUNT_THRESHOLDS)


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
    """Generates location names for an Everdark Sovereign included via IncludedNightlords, in
    BossWithCharacter mode.

    Args:
        character (str): Nightreign character name
        nightlord (str): Nightlord name (must have an Everdark form - see EVERDARK_NIGHTLORDS)

    Returns:
        str: The generated location name.
    """
    return f"Defeat Everdark {nightlord} as {character}"


def location_name_everdark_boss_only(nightlord: str) -> str:
    """Generates location names for an Everdark Sovereign included via IncludedNightlords, in
    Boss mode.

    Args:
        nightlord (str): Nightlord name (must have an Everdark form - see EVERDARK_NIGHTLORDS)

    Returns:
        str: The generated location name.
    """
    return f"Defeat Everdark {nightlord}"


def location_name_win_count(count: int) -> str:
    """Generates the location name for a cumulative "Win N Expeditions" threshold, independent of
    which boss/character was defeated - see game_data.WIN_COUNT_THRESHOLDS.

    Args:
        count (int): the win-count threshold (e.g. 5)

    Returns:
        str: The generated location name.
    """
    return f"Win {count} Expedition" if count == 1 else f"Win {count} Expeditions"


def location_name_kill_bonus(
    nightlord: str, index: int, character: Optional[str] = None, everdark: bool = False
) -> str:
    """Generates the location name for one of the 4 bonus checks (see game_data.
    NIGHTLORD_BONUS_INDICES) that fire together, alongside the existing "Defeat X" location, on a
    Nightlord's first valid defeat - NOT a cumulative kill counter (index has nothing to do with
    how many times the boss has been killed; it just distinguishes these 4 locations from each
    other and from the pre-existing "Defeat X"/index-1 location). Mirrors bosses_with_characters'
    per-character/boss-only shape and covers Everdark Sovereigns the same way location_name_everdark
    does.

    Args:
        nightlord (str): Nightlord name.
        index (int): which bonus check this is (2-5, per NIGHTLORD_BONUS_INDICES) - purely a
            distinguishing label, not a count of anything.
        character (str, optional): Nightreign character name, in BossWithCharacter mode.
        everdark (bool): whether this is the Nightlord's Everdark Sovereign form.

    Returns:
        str: The generated location name.
    """
    prefix = f"Defeat Everdark {nightlord}" if everdark else f"Defeat {nightlord}"
    if character is not None:
        return f"{prefix} as {character} (Bonus {index})"
    return f"{prefix} (Bonus {index})"


def location_name_night1(
    nightlord: str, character: Optional[str] = None, everdark: bool = False
) -> str:
    """Generates the location name for the (single, non-cumulative) Night 1 Clear check - fires on
    defeating the Nightlord's mid-run Night 1 boss, detected via the day/night phase transition
    (see memory_reader.DAY_NIGHT_PHASE_OFFSET), independent of whether the Nightlord itself is
    later defeated. Universal - exactly one per Nightlord (or Nightlord x character), no toggle.

    Args:
        nightlord (str): Nightlord name.
        character (str, optional): Nightreign character name, in BossWithCharacter mode.
        everdark (bool): whether this is the Nightlord's Everdark Sovereign form.

    Returns:
        str: The generated location name.
    """
    subject = f"Everdark {nightlord}" if everdark else nightlord
    if character is not None:
        return f"Clear Night 1 vs {subject} as {character}"
    return f"Clear Night 1 vs {subject}"


def location_name_night2(
    nightlord: str, character: Optional[str] = None, everdark: bool = False
) -> str:
    """Generates the location name for the (single, non-cumulative) Night 2 Clear check - fires on
    a successful transition out of the Nightlord's Night 2 fight (see game_data.DAY_PHASE_DAY_3),
    independent of the Nightlord Bonus checks above (a different detection mechanism for a related
    event). Universal - exactly one per Nightlord (or Nightlord x character), no toggle.

    Args:
        nightlord (str): Nightlord name.
        character (str, optional): Nightreign character name, in BossWithCharacter mode.
        everdark (bool): whether this is the Nightlord's Everdark Sovereign form.

    Returns:
        str: The generated location name.
    """
    subject = f"Everdark {nightlord}" if everdark else nightlord
    if character is not None:
        return f"Clear Night 2 vs {subject} as {character}"
    return f"Clear Night 2 vs {subject}"


def location_name_weak_reward(
    nightlord: str, count: int, character: Optional[str] = None, everdark: bool = False
) -> str:
    """Generates the location name for a cumulative "Weak Reward vs X N times" threshold (see
    game_data.REWARD_CHECK_THRESHOLDS, fixed at 1-5) - fires on collecting a Weak-tier
    reward-tier POI pickup (see memory_reader.WEAK_REWARD_COUNTER_OFFSET) while on an expedition
    against this Nightlord. "Weak"/"Strong" is the game's own naming for this reward tier.

    Args:
        nightlord (str): Nightlord name.
        count (int): the cumulative-pickup threshold (1-5).
        character (str, optional): Nightreign character name, in BossWithCharacter mode.
        everdark (bool): whether this is the Nightlord's Everdark Sovereign form.

    Returns:
        str: The generated location name.
    """
    subject = f"Everdark {nightlord}" if everdark else nightlord
    if character is not None:
        return f"Weak Reward vs {subject} as {character} x{count}"
    return f"Weak Reward vs {subject} x{count}"


def location_name_strong_reward(
    nightlord: str, count: int, character: Optional[str] = None, everdark: bool = False
) -> str:
    """Generates the location name for a cumulative "Strong Reward vs X N times" threshold (see
    game_data.REWARD_CHECK_THRESHOLDS, fixed at 1-5) - fires on collecting a Strong-tier
    reward-tier POI pickup (see memory_reader.STRONG_REWARD_COUNTER_OFFSET) while on an expedition
    against this Nightlord.

    Args:
        nightlord (str): Nightlord name.
        count (int): the cumulative-pickup threshold (1-5).
        character (str, optional): Nightreign character name, in BossWithCharacter mode.
        everdark (bool): whether this is the Nightlord's Everdark Sovereign form.

    Returns:
        str: The generated location name.
    """
    subject = f"Everdark {nightlord}" if everdark else nightlord
    if character is not None:
        return f"Strong Reward vs {subject} as {character} x{count}"
    return f"Strong Reward vs {subject} x{count}"


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
_win_count_table = {
    location_name_win_count(count): LocationData(
        BASE_ID + len(_per_character_table) + len(_boss_only_table)
        + len(_everdark_per_character_table) + len(_everdark_boss_only_table) + i
    )
    for i, count in enumerate(WIN_COUNT_THRESHOLDS)
}

# Extra check-density families (kill-bonus, Night 1/Night 2 clear, weak/strong reward) - each gets
# the same 4 shapes as the tables above (per-character/boss-only x base/Everdark), built via two
# small shared helpers (_append_family for the threshold/index-list families - kill-bonus, weak/
# strong reward; _append_single for Night 1/Night 2 Clear, which have no such dimension) instead of
# 20 near-duplicate comprehensions. `_extra_tables` tracks every table built so far (seeded with the
# 5 above) purely so each new table's id range starts right after the last one - strict append
# order, so ids never shift for older seeds regardless of which families a given slot actually uses.
_extra_tables: list[dict] = [
    _per_character_table, _boss_only_table, _everdark_per_character_table,
    _everdark_boss_only_table, _win_count_table,
]


def _append_family(name_fn, characters: tuple, nightlords: list, thresholds, everdark: bool = False) -> dict:
    start = BASE_ID + sum(len(table) for table in _extra_tables)
    table = {
        name_fn(nightlord, count, character, everdark): LocationData(start + i)
        for i, (character, nightlord, count) in enumerate(
            (character, nightlord, count)
            for character in characters
            for nightlord in nightlords
            for count in thresholds
        )
    }
    _extra_tables.append(table)
    return table


def _append_single(name_fn, characters: tuple, nightlords: list, everdark: bool = False) -> dict:
    """Like _append_family, but for a family with exactly one location per (nightlord, character)
    pair - no threshold/index dimension at all (Night 1/Night 2 Clear)."""
    start = BASE_ID + sum(len(table) for table in _extra_tables)
    table = {
        name_fn(nightlord, character, everdark): LocationData(start + i)
        for i, (character, nightlord) in enumerate(
            (character, nightlord) for character in characters for nightlord in nightlords
        )
    }
    _extra_tables.append(table)
    return table


_kill_bonus_per_character_table = _append_family(
    location_name_kill_bonus, tuple(CHARACTERS), NIGHTLORDS, NIGHTLORD_BONUS_INDICES
)
_kill_bonus_boss_only_table = _append_family(
    location_name_kill_bonus, (None,), NIGHTLORDS, NIGHTLORD_BONUS_INDICES
)
_kill_bonus_everdark_per_character_table = _append_family(
    location_name_kill_bonus, tuple(CHARACTERS), EVERDARK_NIGHTLORDS, NIGHTLORD_BONUS_INDICES,
    everdark=True,
)
_kill_bonus_everdark_boss_only_table = _append_family(
    location_name_kill_bonus, (None,), EVERDARK_NIGHTLORDS, NIGHTLORD_BONUS_INDICES, everdark=True
)

_night1_per_character_table = _append_single(location_name_night1, tuple(CHARACTERS), NIGHTLORDS)
_night1_boss_only_table = _append_single(location_name_night1, (None,), NIGHTLORDS)
_night1_everdark_per_character_table = _append_single(
    location_name_night1, tuple(CHARACTERS), EVERDARK_NIGHTLORDS, everdark=True
)
_night1_everdark_boss_only_table = _append_single(
    location_name_night1, (None,), EVERDARK_NIGHTLORDS, everdark=True
)

_night2_per_character_table = _append_single(location_name_night2, tuple(CHARACTERS), NIGHTLORDS)
_night2_boss_only_table = _append_single(location_name_night2, (None,), NIGHTLORDS)
_night2_everdark_per_character_table = _append_single(
    location_name_night2, tuple(CHARACTERS), EVERDARK_NIGHTLORDS, everdark=True
)
_night2_everdark_boss_only_table = _append_single(
    location_name_night2, (None,), EVERDARK_NIGHTLORDS, everdark=True
)

_weak_reward_per_character_table = _append_family(
    location_name_weak_reward, tuple(CHARACTERS), NIGHTLORDS, REWARD_CHECK_THRESHOLDS
)
_weak_reward_boss_only_table = _append_family(
    location_name_weak_reward, (None,), NIGHTLORDS, REWARD_CHECK_THRESHOLDS
)
_weak_reward_everdark_per_character_table = _append_family(
    location_name_weak_reward, tuple(CHARACTERS), EVERDARK_NIGHTLORDS, REWARD_CHECK_THRESHOLDS,
    everdark=True,
)
_weak_reward_everdark_boss_only_table = _append_family(
    location_name_weak_reward, (None,), EVERDARK_NIGHTLORDS, REWARD_CHECK_THRESHOLDS, everdark=True
)

_strong_reward_per_character_table = _append_family(
    location_name_strong_reward, tuple(CHARACTERS), NIGHTLORDS, REWARD_CHECK_THRESHOLDS
)
_strong_reward_boss_only_table = _append_family(
    location_name_strong_reward, (None,), NIGHTLORDS, REWARD_CHECK_THRESHOLDS
)
_strong_reward_everdark_per_character_table = _append_family(
    location_name_strong_reward, tuple(CHARACTERS), EVERDARK_NIGHTLORDS, REWARD_CHECK_THRESHOLDS,
    everdark=True,
)
_strong_reward_everdark_boss_only_table = _append_family(
    location_name_strong_reward, (None,), EVERDARK_NIGHTLORDS, REWARD_CHECK_THRESHOLDS, everdark=True
)

location_table = {}
for _table in _extra_tables:
    location_table.update(_table)

location_name_to_id = {name: data.id for name, data in location_table.items()}
lookup_id_to_name = {data.id: name for name, data in location_table.items()}
