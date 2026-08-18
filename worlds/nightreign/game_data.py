"""Static game data for Nightreign
"""

# Character class ID
# Unlockable characters still need to be unlocked in-game traditionally
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

# Nightlord ID
# DLC not yet mapped because I don't understand unlock event flagging yet
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
# Checks Nightlord ID +/- 3 given variance seen in testing
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

# Nightlords that do not start unlocked (minus DLC)
ACCESS_NIGHTLORDS = list(NIGHTLORDS)

# Known event flags that unlock bosses
EVENT_FLAG_SECONDARY_BOSSES = 110
EVENT_FLAG_NIGHT_ASPECT = 115

# Event flags for ACCESS_NIGHTLORDS
ACCESS_ITEM_EVENT_FLAGS = {
    f"{name} Access": (EVENT_FLAG_NIGHT_ASPECT if name == "Night Aspect"
                       else EVENT_FLAG_SECONDARY_BOSSES)
    for name in ACCESS_NIGHTLORDS
    if name != "Tricephalos"
}


def starting_free_nightlords(starting_boss: str) -> list:
    """List of Nightlords that start unlocked for a given starting boss.
    """
    return [starting_boss]
