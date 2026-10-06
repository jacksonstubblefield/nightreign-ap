"""Tracker statuses for the client's Unlocks tab, kept free of client.py's pymem/Kivy imports so
it can be unit-tested directly.

Uses the usual tracker color scheme (minus "out of logic" yellow, which this world doesn't have):
LOCKED (red) - the Access item(s) needed aren't received yet; AVAILABLE (green) - accessible with
at least one check still unsent; DONE (gray) - every check it covers has been sent. A boss's checks
are its Defeat check plus kill bonuses and Night 1/Night 2 - a row stays green while any of those
is unsent, even if the boss itself has been beaten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .game_data import CHARACTERS, EVERDARK_NIGHTLORDS, NIGHTLORD_BONUS_INDICES, NIGHTLORDS
from .Locations import (location_name, location_name_boss_only, location_name_everdark,
                        location_name_everdark_boss_only, location_name_kill_bonus,
                        location_name_night1, location_name_night2, location_name_to_id,
                        location_name_win_count)

LOCKED = "locked"
AVAILABLE = "available"
DONE = "done"


@dataclass
class TrackerRow:
    name: str
    status: str
    children: list[TrackerRow] = field(default_factory=list)


def boss_location_names(nightlord: str, character: Optional[str], everdark: bool) -> list[str]:
    """Every location name a boss (or boss x character pair) can have - the slot may not include
    all of them, so callers filter against the slot's actual locations."""
    if everdark:
        defeat = (location_name_everdark(character, nightlord) if character is not None
                  else location_name_everdark_boss_only(nightlord))
    else:
        defeat = (location_name(character, nightlord) if character is not None
                  else location_name_boss_only(nightlord))
    return [
        defeat,
        *(location_name_kill_bonus(nightlord, i, character, everdark) for i in NIGHTLORD_BONUS_INDICES),
        location_name_night1(nightlord, character, everdark),
        location_name_night2(nightlord, character, everdark),
    ]


def _checks_status(names: list[str], slot_locations: set, sent: set) -> Optional[str]:
    """DONE/AVAILABLE for this set of location names, or None when the slot has none of them."""
    ids = [location_name_to_id[n] for n in names if location_name_to_id.get(n) in slot_locations]
    if not ids:
        return None
    return DONE if all(i in sent for i in ids) else AVAILABLE


def _rollup(children: list[TrackerRow]) -> str:
    """A boss inherits its characters' colors: green if any is green, else red if any is red,
    gray only once every character is gray."""
    statuses = {c.status for c in children}
    if AVAILABLE in statuses:
        return AVAILABLE
    if LOCKED in statuses:
        return LOCKED
    return DONE


def boss_rows(
    owned: set, slot_locations: set, sent: set, included_nightlords: list,
    everdark_nightlords: set, included_characters: list, per_character: bool,
    gate_boss_access: bool, gate_character_access: bool,
) -> list[TrackerRow]:
    """One row per included boss (base Nightlords first, then Everdark Sovereigns). In
    per_character mode each boss gets one child row per included character, and its own status
    rolls up from those. Gray (DONE) wins over red - checks that are all sent (e.g. via !collect)
    have nothing left to unlock."""
    subjects = [(name, False) for name in included_nightlords]
    subjects += [(name, True) for name in EVERDARK_NIGHTLORDS if name in everdark_nightlords]
    rows = []
    for nightlord, everdark in subjects:
        display = f"Everdark {nightlord}" if everdark else nightlord
        boss_locked = gate_boss_access and f"{display} Access" not in owned
        if not per_character:
            status = _checks_status(boss_location_names(nightlord, None, everdark), slot_locations, sent)
            if status is None:
                continue
            rows.append(TrackerRow(display, LOCKED if boss_locked and status != DONE else status))
            continue
        children = []
        for character in included_characters:
            status = _checks_status(
                boss_location_names(nightlord, character, everdark), slot_locations, sent
            )
            if status is None:
                continue
            character_locked = (gate_character_access
                                and f"{character} Character Access" not in owned)
            if status != DONE and (boss_locked or character_locked):
                status = LOCKED
            children.append(TrackerRow(character, status))
        if children:
            rows.append(TrackerRow(display, _rollup(children), children))
    return rows


def character_rows(owned: set, included_characters: list) -> list[TrackerRow]:
    """Plain received (green) / not received (red) list - no check tracking."""
    return [
        TrackerRow(name, AVAILABLE if f"{name} Character Access" in owned else LOCKED)
        for name in included_characters
    ]


def win_count_rows(slot_locations: set, sent: set, thresholds: list) -> list[TrackerRow]:
    """Always reachable, so only green (unsent) or gray (sent)."""
    rows = []
    for count in thresholds:
        location_id = location_name_to_id.get(location_name_win_count(count))
        if location_id in slot_locations:
            rows.append(TrackerRow(location_name_win_count(count),
                                   DONE if location_id in sent else AVAILABLE))
    return rows


# Location id -> (nightlord, character or None) for every base Defeat check - the only locations
# goal_groups can contain (see __init__.py's create_regions()).
_DEFEAT_SUBJECTS = {
    **{location_name_to_id[location_name_boss_only(n)]: (n, None) for n in NIGHTLORDS},
    **{location_name_to_id[location_name(c, n)]: (n, c) for n in NIGHTLORDS for c in CHARACTERS},
}


def goal_rows(
    goal_groups: list, owned: set, sent: set, gate_boss_access: bool, gate_character_access: bool,
) -> list[TrackerRow]:
    """One row per Nightlord the goal involves, in roster order. goal_groups (from slot_data) is a
    list of any-of groups that must ALL be satisfied:
    - a multi-id group ("beat X with any character") becomes "X (any character)", gray once ANY
      of its character children is gray;
    - single-id groups for the same Nightlord ("beat X as A", "beat X as B") collect under one
      "X" row, gray only once EVERY child is gray;
    - a single boss-only id is a plain "X" row.
    A pending objective is red when its Access item(s) aren't received, else green."""

    def status(location_id: int, nightlord: str, character: Optional[str]) -> str:
        if location_id in sent:
            return DONE
        if gate_boss_access and f"{nightlord} Access" not in owned:
            return LOCKED
        if (gate_character_access and character is not None
                and f"{character} Character Access" not in owned):
            return LOCKED
        return AVAILABLE

    def child(location_id: int) -> tuple[int, TrackerRow]:
        nightlord, character = _DEFEAT_SUBJECTS[location_id]
        return CHARACTERS.index(character), TrackerRow(character, status(location_id, nightlord, character))

    any_of: dict[str, list] = {}
    all_of: dict[str, list] = {}
    boss_only: dict[str, str] = {}
    for group in goal_groups:
        ids = [i for i in group if i in _DEFEAT_SUBJECTS]
        if not ids:
            continue
        nightlord, character = _DEFEAT_SUBJECTS[ids[0]]
        if len(ids) > 1:
            any_of[nightlord] = [row for _, row in sorted((child(i) for i in ids),
                                                          key=lambda pair: pair[0])]
        elif character is None:
            boss_only[nightlord] = status(ids[0], nightlord, None)
        else:
            all_of.setdefault(nightlord, []).append(child(ids[0]))

    rows = []
    for nightlord in NIGHTLORDS:
        if nightlord in any_of:
            children = any_of[nightlord]
            statuses = {c.status for c in children}
            rollup = (DONE if DONE in statuses else AVAILABLE if AVAILABLE in statuses else LOCKED)
            rows.append(TrackerRow(f"{nightlord} (any character)", rollup, children))
        if nightlord in all_of:
            children = [row for _, row in sorted(all_of[nightlord], key=lambda pair: pair[0])]
            rows.append(TrackerRow(nightlord, _rollup(children), children))
        if nightlord in boss_only:
            rows.append(TrackerRow(nightlord, boss_only[nightlord]))
    return rows


def goal_progress(goal_groups: list, sent: set) -> tuple[int, int]:
    """(groups satisfied, total groups) - the same test as client.py's _goal_complete."""
    done = sum(1 for group in goal_groups if any(i in sent for i in group))
    return done, len(goal_groups)
