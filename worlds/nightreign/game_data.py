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
