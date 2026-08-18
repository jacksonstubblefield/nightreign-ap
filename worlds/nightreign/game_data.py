"""Static game data for Elden Ring Nightreign: character and Nightlord
rosters. No AP or pymem imports - shared by `memory_reader.py` (which knows
how to detect these values from live game memory) and the world's
`Items.py`/`Locations.py` (which only need the names to build the location
matrix), so the roster only has to be edited in one place.
"""

# Class id (read from game memory) -> display name. Order matches the
# in-game class-select dropdown.
CHARACTER_CLASS_NAMES = {
    50000: "Wylder",
    50100: "Guardian",
    50200: "Ironeye",
    50300: "Duchess",
    50400: "Raider",
    50500: "Revenant",
    50600: "Recluse",
    50700: "Executor",
    50800: "Scholar",
    50900: "Undertaker",
}
CHARACTERS = list(CHARACTER_CLASS_NAMES.values())

# Candidate boss_id -> Nightlord name (see project memory for
# confidence/drift caveats per entry - Darkdrift Night and Night Aspect are
# single-sample as of Phase 0). DLC Nightlord(s) not yet sampled/reachable.
KNOWN_BOSS_IDS = {
    2: "Tricephalos",
    12: "Gaping Jaw",
    22: "Sentient Pest",
    23: "Sentient Pest",
    32: "Augur",
    43: "Equilibrious Beast",
    53: "Darkdrift Night",
    61: "Fissure in the Fog",
    73: "Night Aspect",
}
DRIFT_TOLERANCE = 3

# +0xB50 (like its neighbors +0xB48/+0xB4C) reads this sentinel when no boss
# is selected (hub/menu). With DRIFT_TOLERANCE=3 this sits right inside
# Tricephalos's (id=2) match window, so it must be checked before
# tolerance-matching rather than left to fall through - see memory_reader.py.
UNSET_SENTINEL = -1


def nightlord_roster() -> list:
    """Ordered, de-duplicated Nightlord names (ascending boss_id)."""
    seen = set()
    names = []
    for _boss_id, name in sorted(KNOWN_BOSS_IDS.items()):
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


NIGHTLORDS = nightlord_roster()

# Nightlords that need an AP "access" item before the player is considered to have earned them.
# This includes Tricephalos even though it's always visually selectable in a fresh save with no
# flag write needed (see ACCESS_ITEM_EVENT_FLAGS below) - that's a statement about what the
# vanilla game lets you click, not about what this player has actually earned in this multiworld.
# Without its own Access item, a player whose starting_boss was something else would see
# Tricephalos as "free" despite never receiving anything for it - exactly the AP-ownership-vs-
# in-game-visibility mismatch the overlay exists to surface for the other 6 (see overlay.py),
# so Tricephalos is tracked the same way rather than special-cased out of it.
ACCESS_NIGHTLORDS = list(NIGHTLORDS)

# EventFlag ids, confirmed live via Cheat Engine against the game's own
# EventFlagBaseA function: SetEventFlag(110, 1) reveals all 6 secondary
# Nightlords as one atomic batch (no finer per-boss flag exists), while
# SetEventFlag(115, 1) separately reveals Night Aspect. See memory_writer.py
# for how these get fired, and the project notes for how they were found.
EVENT_FLAG_SECONDARY_BOSSES = 110
EVENT_FLAG_NIGHT_ASPECT = 115

# Tricephalos has no entry here - there's no EventFlag gating it in the vanilla game (it's always
# selectable from a fresh save), so owning "Tricephalos Access" has no in-game write to perform.
# It still exists as an AP item (see ACCESS_NIGHTLORDS above) and still affects the overlay's
# locked/unlocked bookkeeping in client.py - it's just a no-op for _sync_event_flags specifically.
ACCESS_ITEM_EVENT_FLAGS = {
    f"{name} Access": (EVENT_FLAG_NIGHT_ASPECT if name == "Night Aspect" else EVENT_FLAG_SECONDARY_BOSSES)
    for name in ACCESS_NIGHTLORDS
    if name != "Tricephalos"
}


def starting_free_nightlords(starting_boss: str) -> list:
    """The Nightlord(s) that are free - AP-owned with no Access item needed -
    because of a `starting_boss` choice. Just that one boss. Returns a list
    (rather than the single name) so callers don't need a special case, and
    to leave room for this to grow in future.

    Deliberately NOT expanded to the rest of `starting_boss`'s
    EVENT_FLAG_SECONDARY_BOSSES group (when starting_boss is one of the 6):
    revealing it in-game unavoidably reveals its 5 siblings too (see
    EVENT_FLAG_SECONDARY_BOSSES above), but that's an in-game visibility side
    effect only, not AP ownership - those siblings still need their own
    Access item, same as if `starting_boss` hadn't been touched at all. The
    overlay is what shows the player which of the visually-unlocked-but-not-
    earned ones those are.
    """
    return [starting_boss]
