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


# --- Item-drop write path (filler weapons) ---
#
# AOBs below are a Python port of the "Sly - ItemDrop" Cheat Engine script (community table
# `Nightreign_w_apvalues.CT`, contributor Volkov_ilya37) - see memory_writer.py's
# NightreignItemDropWriter for how these are actually dispatched. Same non-connect()-time
# resolution convention as EVENTFLAG_PTR_AOB/EVENTFLAG_BASE_A_AOB: only resolved when a caller
# actually wants write access, so a patch that breaks only these AOBs can't take down the
# read-only tracker.

# Pointer-slot style (like GAMEMAN_AOB/GAMEDATAMAN_AOB in memory_reader.py), but the actual
# `mov reg,[rip+disp32]` instruction isn't inside the matched bytes - it starts
# MAPITEMMAN_AOB_OFFSET bytes past the match, per the CT table's own registerBaseAddr() Lua
# resolver (offset applied before the same len=7/ripOffset=3 RIP-relative math
# _resolve_pointer_slot already does for the other two pointer slots).
MAPITEMMAN_AOB = "48 8B C8 E8 ?? ?? ?? ?? 0F 28 00 66 0F 7F 44 24 50"
MAPITEMMAN_AOB_OFFSET = 0x11

# Function-address style (like EVENTFLAG_BASE_A_AOB): the AOB scan lands near, not on, the real
# entry point - the caller applies ITEMDROP_CALL_FUNC_OFFSET after resolving.
ITEMDROP_CALL_AOB = "41 0F B6 E9 41 0F B6 F8 48 8B DA 48 8B F1 33 C0 48 89 44 24 30"
ITEMDROP_CALL_FUNC_OFFSET = -0x27  # real drop-function entry = match_addr + this

# Used directly (no offset) as the base for a further "+0xD" applied inline by the trampoline
# itself (see memory_writer.py) - the CT script reads a TLS index embedded as data at that fixed
# byte offset inside the game's own code, mirroring how the compiler itself would resolve a
# thread-local variable.
TLS_SLOT_FETCHER_ITEMDROP_AOB = "8D 41 0F 03 C2 83 E0 F0 41 89 00 8B 0D"

# The weapon-tier lookup helper ("Aboba" in the CT script's own Lua - an arbitrary name the CT
# table's author gave an otherwise-unnamed function; kept as ABOBA_* here so this stays
# traceable back to that source).
ABOBA_AOB = ("45 33 C0 33 D2 E8 ?? ?? ?? ?? 45 8B DF 48 85 C0 0F 84 ?? ?? ?? ?? "
             "48 8B 80 80 00 00 00 48 8B 90 80 00 00 00")
ABOBA_FUNC_OFFSET = -0x7A

# Fixed module-relative address the CT script points a faked TLS slot at, to make a raw
# CreateRemoteThread thread look like it's running in a valid game-thread context to the drop
# function - see memory_writer.py's module docstring for why this is needed at all.
TLS_FAKE_CONTEXT_RVA = 0x3C1F918

# Weapon affinity/"Gem" (Ash-of-War infusion) id families, grouped by the maximum upgrade tier
# they're allowed to carry - ported verbatim from the CT script's `capLevels` Lua table. An id
# not present here has no cap beyond the base game's own.
EFFECT_CAP_LEVELS = {
    0: [
        8883100,
        8370000, 8610600,
        8881200, 8650000, 8460200,
        8884000, 8885000, 8883000, 8884100,
        8884200, 8885100, 8885200, 8884300, 8520001,
        8330500, 8330700, 8460500, 8530000, 8530100, 8610500,
        8610000, 8610100, 8620010, 8610300, 8610400, 8350400, 8360000,
        8330900, 8610700, 8620100, 8652000, 8320400, 8450000, 8450100, 8460100,
        8410100, 8420100, 8420200, 8430000, 8440200, 8600300, 8620000, 8640000, 8640100,
        8460300, 8460400, 8460500, 8500000, 8530200, 8880200, 8880300, 8880400, 8881000, 8881100,
        8650100, 8652100, 8660200, 8880000, 8880100, 8882100, 8882200, 8882300, 8882300, 8882400,
        8882500, 8881300, 8881400, 8881500, 8881600, 8882000,
    ],
    1: [
        8000000, 8010000, 8010100, 8020000,
        8100000, 8100100, 8100200, 8100300, 8100400, 8330400,
        8200000, 8200100, 8200200, 8200300, 8200400, 8200500,
        8020100, 8020200, 8120000, 8230000,
    ],
    2: [
        8300000, 8350000, 8320300, 8320100, 8420000, 8670000, 8110000, 8110300, 8110600, 8111000,
        8310000, 8600100, 8600200, 8130000, 8330600, 8330000, 8330200, 8320000, 8660000, 8110900,
        8110800, 8330100, 8330300, 8340000, 8340100, 8510000, 8140000, 8110200, 8110700, 8660100,
        8670100, 8210000, 8210100, 8210200, 8210300, 8110500, 8210400, 8210500, 8210600, 8111000,
        8110100, 8110400,
    ],
}

EFFECT_CAP_MAP = {
    effect_id: cap
    for cap, effect_ids in EFFECT_CAP_LEVELS.items()
    for effect_id in effect_ids
}

# Upgrade-tier roll weighting for "Randomized Weapon" filler drops (see client.py's
# _roll_weapon_drop): a uniform 0-100 percentile roll lands in one of these bands. Matches the
# CT table's own Injector_WeaponTier naming (0=Default, 1=Blue, 2=Purple, 3=Orange) - the actual
# upgrade_level handed to a drop still gets clamped down further by that specific weapon's own
# max reinforcement tier (memory_writer.py's _clamp_upgrade_tier), same as every other drop.
UPGRADE_TIER_ROLL_BANDS = [
    (0, 45, 0),
    (46, 69, 1),
    (70, 89, 2),
    (90, 100, 3),
]

# effect_tier roll weighting for "Randomized Weapon" filler drops - same percentile-band idea as
# UPGRADE_TIER_ROLL_BANDS, just 3 bands (0/1/2) instead of 4, matching effect_tier's own range.
# The requested tier still gets clamped down further by the specific affinity/gem rolled (see
# EFFECT_CAP_MAP), same as every other drop - this only weights what gets *requested*.
EFFECT_TIER_ROLL_BANDS = [
    (0, 49, 0),
    (50, 84, 1),
    (85, 100, 2),
]


def _roll_from_bands(percentile: int, bands: list) -> int:
    for low, high, tier in bands:
        if low <= percentile <= high:
            return tier
    raise ValueError(f"percentile {percentile} out of range 0-100")


def roll_upgrade_tier(percentile: int) -> int:
    """Maps a 0-100 percentile roll to an upgrade_level (0-3) via UPGRADE_TIER_ROLL_BANDS."""
    return _roll_from_bands(percentile, UPGRADE_TIER_ROLL_BANDS)


def roll_effect_tier(percentile: int) -> int:
    """Maps a 0-100 percentile roll to an effect_tier (0-2) via EFFECT_TIER_ROLL_BANDS."""
    return _roll_from_bands(percentile, EFFECT_TIER_ROLL_BANDS)

# Weapon item id -> display name. Extracted mechanically (see the dev notes for this feature)
# from the same CT table's `WeaponIDList[]` C array - 385 unique ids after de-duplicating 5
# entries the CT table itself listed twice (a "Nightreign relic weapons" section at the top of
# its source duplicates a handful of vanilla weapons already covered further down; kept the
# properly-cased name on conflict). Two known typos survive from the source data unedited
# ("Wylder's Gretsword", "Guardian's Halbert") - flagged here rather than silently fixed, since
# there's no way to tell from this file alone whether that's a source typo or a real in-game
# string.
WEAPON_TABLE = {
    0x00F4240: "Dagger",
    0x00F6950: "Black Knife",
    0x00F9060: "Parrying Dagger",
    0x00FB770: "Miséricorde",
    0x00FDE80: "Reduvia",
    0x0100590: "Crystal Knife",
    0x0102CA0: "Celebrant's Sickle",
    0x01053B0: "Glintstone Kris",
    0x0107AC0: "Scorpion's Stinger",
    0x010A1D0: "Great Knife",
    0x010C8E0: "Wakizashi",
    0x010EFF0: "Cinquedea",
    0x0113E10: "Ivory Sickle",
    0x0116520: "Bloodstained Dagger",
    0x0118C30: "Erdsteel Dagger",
    0x011B340: "Blade of Calling",
    0x01E8480: "Longsword",
    0x01EAB90: "Short Sword",
    0x01ED2A0: "Broadsword",
    0x01F20C0: "Lordsworn's Straight Sword",
    0x01F47D0: "Weathered Straight Sword",
    0x01F6EE0: "Ornamental Straight Sword",
    0x01F95F0: "Golden Epitaph",
    0x01FBD00: "Nox Flowing Sword",
    0x01FE410: "Inseparable Sword",
    0x0203230: "Coded Sword",
    0x020A760: "Sword of Night and Flame",
    0x020CE70: "Crystal Sword",
    0x02143A0: "Carian Knight's Sword",
    0x0216AB0: "Sword of St. Trina",
    0x02191C0: "Miquellan Knight's Sword",
    0x021B8D0: "Cane Sword",
    0x021DFE0: "Regalia of Eochaid",
    0x02206F0: "Noble's Slender Sword",
    0x0222E00: "Warhawk's Talon",
    0x0225510: "Lazuli Glintstone Sword",
    0x0227C20: "Rotten Crystal Sword",
    0x02DC6C0: "Bastard Sword",
    0x02DEDD0: "Forked Greatsword",
    0x02E14E0: "Iron Greatsword",
    0x02E3BF0: "Lordsworn's Greatsword",
    0x02E6300: "Knight's Greatsword",
    0x02E8A10: "Flamberge",
    0x02EB120: "Ordovis's Greatsword",
    0x02ED830: "Alabaster Lord's Sword",
    0x02EFF40: "Banished Knight's Greatsword",
    0x02F2650: "Dark Moon Greatsword",
    0x02F4D60: "Sacred Relic Sword",
    0x02FC290: "Helphen's Steeple",
    0x02FE9A0: "Blasphemous Blade",
    0x03010B0: "Marais Executioner's Sword",
    0x03037C0: "Sword of Milos",
    0x0305ED0: "Golden Order Greatsword",
    0x03085E0: "Claymore",
    0x030ACF0: "Gargoyle's Greatsword",
    0x030D400: "Death's Poker",
    0x030FB10: "Gargoyle's Blackblade",
    0x0393870: "Wylder's Gretsword",
    0x03D0900: "Greatsword",
    0x03D3010: "Watchdog's Greatsword",
    0x03D5720: "Maliketh's Black Blade",
    0x03D7E30: "Troll's Golden Sword",
    0x03DA540: "Zweihander",
    0x03DCC50: "Starscourge Greatsword",
    0x03DF360: "Royal Greatsword",
    0x03E1A70: "Godslayer's Greatsword",
    0x03E4180: "Ruins Greatsword",
    0x03E8FA0: "Grafted Blade Greatsword",
    0x03EB6B0: "Troll Knight's Sword",
    0x04C4B40: "Estoc",
    0x04C7250: "Cleanrot Knight's Sword",
    0x04C9960: "Rapier",
    0x04CC070: "Rogier's Rapier",
    0x04CE780: "Antspur Rapier",
    0x04D0E90: "Frozen Needle",
    0x04D35A0: "Noble's Estoc",
    0x05B8D80: "Bloody Helice",
    0x05BB490: "Godskin Stitcher",
    0x05BDBA0: "Great Épée",
    0x05C29C0: "Dragon King's Cragblade",
    0x06ACFC0: "Falchion",
    0x06AF6D0: "Beastman's Curved Sword",
    0x06B1DE0: "Shotel",
    0x06B44F0: "Shamshir",
    0x06B6C00: "Bandit's Curved Sword",
    0x06B9310: "Magma Blade",
    0x06BBA20: "Flowing Curved Sword",
    0x06BE130: "Wing of Astel",
    0x06C0840: "Scavenger's Curved Sword",
    0x06C5660: "Eclipse Shotel",
    0x06C7D70: "Serpent-God's Curved Sword",
    0x06CA480: "Mantis Blade",
    0x06CF2A0: "Scimitar",
    0x06D19B0: "Grossmesser",
    0x07A3910: "Onyx Lord's Greatsword",
    0x07A6020: "Dismounter",
    0x07A8730: "Bloodhound's Fang",
    0x07AAE40: "Magma Wyrm's Scalesword",
    0x07AD550: "Zamor Curved Sword",
    0x07AFC60: "Omen Cleaver",
    0x07B2370: "Monk's Flameblade",
    0x07B4A80: "Beastman's Cleaver",
    0x07B98A0: "Morgott's Cursed Sword",
    0x0895440: "Uchigatana",
    0x0897B50: "Nagakiba",
    0x089A260: "Hand of Malenia",
    0x089C970: "Meteoric Ore Blade",
    0x089F080: "Rivers of Blood",
    0x08A3EA0: "Moonveil",
    0x08A65B0: "Dragonscale Blade",
    0x08A8CC0: "Serpentbone Blade",
    0x094C5F0: "Executor's Blade",
    0x0989680: "Twinblade",
    0x098BD90: "Godskin Peeler",
    0x0990BB0: "Twinned Knight Swords",
    0x09959D0: "Eleonora's Poleblade",
    0x099CF00: "Gargoyle's Twinblade",
    0x099F610: "Gargoyle's Black Blades",
    0x0A7D8C0: "Mace",
    0x0A7FFD0: "Club",
    0x0A84DF0: "Curved Club",
    0x0A87500: "Warpick",
    0x0A89C10: "Morning Star",
    0x0A8C320: "Varré's Bouquet",
    0x0A8EA30: "Spiked Club",
    0x0A91140: "Hammer",
    0x0A93850: "Monk's Flamemace",
    0x0A95F60: "Envoy's Horn",
    0x0A98670: "Scepter of the All-Knowing",
    0x0A9AD80: "Nox Flowing Hammer",
    0x0A9D490: "Ringed Finger",
    0x0A9FBA0: "Stone Club",
    0x0AA22B0: "Marika's Hammer",
    0x0B71B00: "Large Club",
    0x0B74210: "Greathorn Hammer",
    0x0B76920: "Battle Hammer",
    0x0B80560: "Great Mace",
    0x0B85380: "Curved Great Club",
    0x0B916D0: "Celebrant's Skull",
    0x0B93DE0: "Pickaxe",
    0x0B964F0: "Beastclaw Greathammer",
    0x0B98C00: "Envoy's Long Horn",
    0x0B9B310: "Cranial Vessel Candlestand",
    0x0B9DA20: "Great Stars",
    0x0BA0130: "Brick Hammer",
    0x0BA2840: "Devourer's Scepter",
    0x0BA4F50: "Rotten Battle Hammer",
    0x0C65D40: "Nightrider Flail",
    0x0C68450: "Flail",
    0x0C6AB60: "Family Heads",
    0x0C6D270: "Bastard's Stars",
    0x0C6F980: "Chainlink Flail",
    0x0D59F80: "Battle Axe",
    0x0D5C690: "Forked Hatchet",
    0x0D5EDA0: "Hand Axe",
    0x0D614B0: "Jawbone Axe",
    0x0D63BC0: "Iron Cleaver",
    0x0D662D0: "Ripple Blade",
    0x0D689E0: "Celebrant's Cleaver",
    0x0D6D800: "Icerind Hatchet",
    0x0D72620: "Highland Axe",
    0x0D74D30: "Sacrificial Axe",
    0x0D77440: "Rosus' Axe",
    0x0D7C260: "Stormhawk Axe",
    0x0E4E1C0: "Greataxe",
    0x0E508D0: "Warped Axe",
    0x0E52FE0: "Great Omenkiller Cleaver",
    0x0E556F0: "Crescent Moon Axe",
    0x0E57E00: "Axe of Godrick",
    0x0E5A510: "Longhaft Axe",
    0x0E5CC20: "Rusted Anchor",
    0x0E61A40: "Executioner's Greataxe",
    0x0E68F70: "Winged Greathorn",
    0x0E6B680: "Butchering Knife",
    0x0E6DD90: "Gargoyle's Great Axe",
    0x0E704A0: "Gargoyle's Black Axe",
    0x0F42400: "Short Spear",
    0x0F44B10: "Spear",
    0x0F47220: "Crystal Spear",
    0x0F49930: "Clayman's Harpoon",
    0x0F4C040: "Cleanrot Spear",
    0x0F4E750: "Partisan",
    0x0F50E60: "Celebrant's Rib-Rake",
    0x0F53570: "Pike",
    0x0F55C80: "Torchpole",
    0x0F58390: "Bolt of Gransax",
    0x0F5D1B0: "Cross-Naginata",
    0x0F5F8C0: "Death Ritual Spear",
    0x0F61FD0: "Inquisitor's Girandole",
    0x0F646E0: "Spiked Spear",
    0x0F66DF0: "Iron Spear",
    0x0F69500: "Rotten Crystal Spear",
    0x1038D50: "Mohgwyn's Sacred Spear",
    0x103B460: "Siluria's Tree",
    0x103DB70: "Serpent-Hunter",
    0x1042990: "Vyke's War Spear",
    0x10450A0: "Lance",
    0x10477B0: "Treespear",
    0x112A880: "Halberd",
    0x112CF90: "Pest's Glaive",
    0x112F6A0: "Lucerne",
    0x1131DB0: "Banished Knight's Halberd",
    0x11344C0: "Commander's Standard",
    0x1136BD0: "Nightrider Glaive",
    0x11392E0: "Ripple Crescent Halberd",
    0x113B9F0: "Vulgar Militia Saw",
    0x113E100: "Golden Halberd",
    0x1140810: "Glaive",
    0x1142F20: "Loretta's War Sickle",
    0x1145630: "Guardian's Swordspear",
    0x114A450: "Vulgar Militia Shotel",
    0x114CB60: "Dragon Halberd",
    0x114F270: "Gargoyle's Halberd",
    0x1151980: "Gargoyle's Black Halberd",
    0x11E1A30: "Guardian's Halbert",
    0x121EAC0: "Scythe",
    0x12211D0: "Grave Scythe",
    0x12238E0: "Halo Scythe",
    0x122D520: "Winged Scythe",
    0x1312D00: "Whip",
    0x1317B20: "Thorned Whip",
    0x131A230: "Magma Whip Candlestick",
    0x131F050: "Hoslow's Petal Whip",
    0x1321760: "Giant's Red Braid",
    0x1323E70: "Urumi",
    0x1406F40: "Caestus",
    0x1409650: "Spiked Caestus",
    0x14159A0: "Grafted Dragon",
    0x14180B0: "Iron Ball",
    0x141A7C0: "Star Fist",
    0x141F5E0: "Katar",
    0x1421CF0: "Clinging Bone",
    0x1424400: "Veteran's Prosthesis",
    0x1426B10: "Cipher Pata",
    0x14FB180: "Hookclaws",
    0x14FD890: "Venomous Fang",
    0x14FFFA0: "Bloodhound Claws",
    0x15026B0: "Raptor Talons",
    0x15EF3C0: "Prelate's Inferno Crozier",
    0x15F1AD0: "Watchdog's Staff",
    0x15F41E0: "Great Club",
    0x15F68F0: "Envoy's Greathorn",
    0x15F9000: "Duelist Greataxe",
    0x15FB710: "Axe of Godfrey",
    0x15FDE20: "Dragon Greatclaw",
    0x1600530: "Staff of the Avatar",
    0x1602C40: "Fallingstar Beast Jaw",
    0x1607A60: "Ghiza's Wheel",
    0x160A170: "Giant-Crusher",
    0x160C880: "Golem's Halberd",
    0x160EF90: "Troll's Hammer",
    0x16116A0: "Rotten Staff",
    0x1613DB0: "Rotten Greataxe",
    0x16A6570: "Raider's Greataxe",
    0x16E3600: "Torch",
    0x16E8420: "Steel-Wire Torch",
    0x16ED240: "St. Trina's Torch",
    0x16EF950: "Ghostflame Torch",
    0x16F2060: "Beast-Repellent Torch",
    0x16F4770: "Sentry's Torch",
    0x1C9C380: "Buckler",
    0x1C9EA90: "Perfumer's Shield",
    0x1CA11A0: "Man-Serpent's Shield",
    0x1CA38B0: "Rickety Shield",
    0x1CA5FC0: "Pillory Shield",
    0x1CAADE0: "Beastman's Jar-Shield",
    0x1CAD4F0: "Red Thorn Roundshield",
    0x1CAFC00: "Scripture Wooden Shield",
    0x1CB2310: "Riveted Wooden Shield",
    0x1CB4A20: "Blue-White Wooden Shield",
    0x1CB7130: "Rift Shield",
    0x1CB9840: "Iron Roundshield",
    0x1CBBF50: "Gilded Iron Shield",
    0x1CBE660: "Ice Crest Shield",
    0x1CC0D70: "Smoldering Shield",
    0x1CCA9B0: "Spiralhorn Shield",
    0x1CCD0C0: "Coil Shield",
    0x1D53530: "Wylder's Small Shield",
    0x1D905C0: "Kite Shield",
    0x1D92CD0: "Marred Leather Shield",
    0x1D953E0: "Marred Wooden Shield",
    0x1D97AF0: "Banished Knight's Shield",
    0x1D9A200: "Albinauric Shield",
    0x1D9C910: "Sun Realm Shield",
    0x1D9F020: "Silver Mirrorshield",
    0x1DA1730: "Round Shield",
    0x1DA3E40: "Scorpion Kite Shield",
    0x1DA6550: "Twinbird Kite Shield",
    0x1DA8C60: "Blue-Gold Kite Shield",
    0x1DB0190: "Brass Shield",
    0x1DB28A0: "Great Turtle Shell",
    0x1DB9DD0: "Shield of the Guilty",
    0x1DBEBF0: "Carian Knight's Shield",
    0x1DC8830: "Large Leather Shield",
    0x1DCAF40: "Horse Crest Wooden Shield",
    0x1DCD650: "Candletree Wooden Shield",
    0x1DCFD60: "Flame Crest Wooden Shield",
    0x1DD2470: "Hawk Crest Wooden Shield",
    0x1DD4B80: "Beast Crest Heater Shield",
    0x1DD7290: "Red Crest Heater Shield",
    0x1DD99A0: "Blue Crest Heater Shield",
    0x1DDC0B0: "Eclipse Crest Heater Shield",
    0x1DDE7C0: "Inverted Hawk Heater Shield",
    0x1DE0ED0: "Heater Shield",
    0x1DE35E0: "Black Leather Shield",
    0x1E84800: "Dragon Towershield",
    0x1E89620: "Distinguished Greatshield",
    0x1E8BD30: "Crucible Hornshield",
    0x1E8E440: "Dragonclaw Shield",
    0x1E90B50: "Briar Greatshield",
    0x1E98080: "Erdtree Greatshield",
    0x1E9A790: "Golden Beast Crest Shield",
    0x1EA1CC0: "Jellyfish Shield",
    0x1EA43D0: "Fingerprint Stone Shield",
    0x1EA6AE0: "Icon Shield",
    0x1EA91F0: "One-Eyed Shield",
    0x1EAB900: "Visage Shield",
    0x1EAE010: "Spiked Palisade Shield",
    0x1EB2E30: "Manor Towershield",
    0x1EB5540: "Crossed-Tree Towershield",
    0x1EB7C50: "Inverted Hawk Towershield",
    0x1EBA360: "Ant's Skull Plate",
    0x1EBCA70: "Redmane Greatshield",
    0x1EBF180: "Eclipse Crest Greatshield",
    0x1EC1890: "Cuckoo Greatshield",
    0x1EC3FA0: "Golden Greatshield",
    0x1EC66B0: "Gilded Greatshield",
    0x1EC8DC0: "Haligtree Crest Greatshield",
    0x1ECB4D0: "Wooden Greatshield",
    0x1ECDBE0: "Lordsworn's Shield",
    0x1F3B9B0: "Guardian's Greatshield",
    0x1F78A40: "Glintstone Staff",
    0x1F82680: "Crystal Staff",
    0x1F84D90: "Gelmir Glintstone Staff",
    0x1F874A0: "Demi-Human Queen's Staff",
    0x1F8E9D0: "Carian Regal Scepter",
    0x1F95F00: "Digger's Staff",
    0x1F98610: "Astrologer's Staff",
    0x1FA2250: "Carian Glintblade Staff",
    0x1FA4960: "Prince of Death's Staff",
    0x1FA7070: "Albinauric Staff",
    0x1FA9780: "Academy Glintstone Staff",
    0x1FABE90: "Carian Glintstone Staff",
    0x1FB0CB0: "Azur's Glintstone Staff",
    0x1FB33C0: "Lusat's Glintstone Staff",
    0x1FB5AD0: "Meteorite Staff",
    0x1FB81E0: "Staff of the Guilty",
    0x1FBA8F0: "Rotten Crystal Staff",
    0x1FBD000: "Staff of Loss",
    0x202FBF0: "Recluse's Staff",
    0x206CC80: "Finger Seal",
    0x206F390: "Godslayer's Seal",
    0x2071AA0: "Giant's Seal",
    0x20741B0: "Gravel Stone Seal",
    0x20768C0: "Clawmark Seal",
    0x207B6E0: "Golden Order Seal",
    0x207DDF0: "Erdtree Seal",
    0x2080500: "Dragon Communion Seal",
    0x2082C10: "Frenzied Flame Seal",
    0x2625A00: "Shortbow",
    0x2628110: "Misbegotten Shortbow",
    0x262A820: "Red Branch Shortbow",
    0x262CF30: "Harp Bow",
    0x2631D50: "Composite Bow",
    0x2719C40: "Longbow",
    0x271C350: "Albinauric Bow",
    0x271EA60: "Horn Bow",
    0x2721170: "Erdtree Bow",
    0x2723880: "Serpent Bow",
    0x27286A0: "Pulley Bow",
    0x272ADB0: "Black Bow",
    0x27D0DF0: "Ironeye's Bow",
    0x280DE80: "Lion Greatbow",
    0x2810590: "Golem Greatbow",
    0x28153B0: "Erdtree Greatbow",
    0x2817AC0: "Greatbow",
    0x29020C0: "Soldier's Crossbow",
    0x2906EE0: "Light Crossbow",
    0x29095F0: "Heavy Crossbow",
    0x290E410: "Pulley Crossbow",
    0x2910B20: "Full Moon Crossbow",
    0x2915940: "Arbalest",
    0x291CE70: "Crepus's Black-Key Crossbow",
    0x29F6300: "Hand Ballista",
    0x29F8A10: "Jar Cannon",
}

# Ash of War id -> display name, same source/extraction as WEAPON_TABLE. Per the research pass
# that pulled this out of the CT file: this covers every generic, weapon-swappable Ash of War,
# but not the unique arts innately bound to specific legendary weapons (e.g. Moonveil's,
# Rivers of Blood's) - those apply automatically with the weapon itself and were never meant to
# be independently selectable, so their absence here is expected, not a gap.
# Talisman item id -> display name. Extracted from the same CT table's "Injector_Talismans"
# DropDownList (a curated CE-UI dropdown, unlike WEAPON_TABLE's raw WeaponIDList[] C array) -
# 67 entries, with the list's own "FFFFFFFF:None" sentinel entry dropped since it isn't a real
# item. Base talisman ids only (a handful of talismans also have separate +1/+2 upgrade-variant
# ids elsewhere in the CT file, e.g. Dragoncrest Shield Talisman - deliberately left out here,
# same "no upgrade tier" scope as this whole feature, unlike randomized weapons).
TALISMAN_TABLE = {
    0x200003E8: "Crimson Amber Medallion",
    0x200003F2: "Cerulean Amber Medallion",
    0x200003FC: "Viridian Amber Medallion",
    0x20000410: "Erdtree's Favor",
    0x2000044C: "Silver Scarab",
    0x20000456: "Gold Scarab",
    0x2000047E: "Green Turtle Talisman",
    0x20000488: "Stalwart Horn Charm",
    0x20000492: "Immunizing Horn Charm",
    0x2000049C: "Clarifying Horn Charm",
    0x200004A6: "Prince of Death's Pustule",
    0x200004B0: "Mottled Necklace",
    0x200004BA: "Bull-Goat's Talisman",
    0x200004E2: "Millicent's Prosthesis",
    0x200007D0: "Magic Scorpion Charm",
    0x200007DA: "Lightning Scorpion Charm",
    0x200007E4: "Fire Scorpion Charm",
    0x200007EE: "Sacred Scorpion Charm",
    0x200007F8: "Red-Feathered Branchsword",
    0x20000802: "Ritual Sword Talisman",
    0x2000080C: "Spear Talisman",
    0x20000816: "Hammer Talisman",
    0x20000820: "Winged Sword Insignia",
    0x20000821: "Rotten Winged Sword Insignia",
    0x2000082A: "Dagger Talisman",
    0x20000834: "Arrow's Reach Talisman",
    0x2000083E: "Blue Dancer Charm",
    0x20000848: "Twinblade Talisman",
    0x20000852: "Axe Talisman",
    0x2000085C: "Lance Talisman",
    0x20000866: "Arrow's Sting Talisman",
    0x20000870: "Lord of Blood's Exultation",
    0x2000087A: "Kindred of Rot's Exultation",
    0x20000884: "Claw Talisman",
    0x2000088E: "Roar Medallion",
    0x20000898: "Curved Sword Talisman",
    0x200008A2: "Companion Jar",
    0x200008AC: "Perfumer's Talisman",
    0x20000BB8: "Graven-School Talisman",
    0x20000BB9: "Graven-Mass Talisman",
    0x20000BE0: "Faithful's Canvas Talisman",
    0x20000BEA: "Flock's Canvas Talisman",
    0x20000BF4: "Old Lord's Talisman",
    0x20000BFE: "Radagon Icon",
    0x20000C08: "Primal Glintstone Blade",
    0x20000C12: "Godfrey Icon",
    0x20000FA0: "Dragoncrest Shield Talisman",
    0x20000FA3: "Dragoncrest Greatshield Talisman",
    0x20000FAA: "Spelldrake Talisman",
    0x20000FB4: "Flamedrake Talisman",
    0x20000FBE: "Boltdrake Talisman",
    0x20000FC8: "Haligdrake Talisman",
    0x20000FD2: "Pearldrake Talisman",
    0x20000FF0: "Blue-Feathered Branchsword",
    0x20000FFA: "Ritual Shield Talisman",
    0x20001004: "Greatshield Talisman",
    0x2000100E: "Crucible Knot Talisman",
    0x20001388: "Crimson Seed Talisman",
    0x20001392: "Cerulean Seed Talisman",
    0x2000139C: "Blessed Dew Talisman",
    0x200013A6: "Taker's Cameo",
    0x200013B0: "Godskin Swaddling Cloth",
    0x200013BA: "Assassin's Crimson Dagger",
    0x200013C4: "Assassin's Cerulean Dagger",
    0x20001784: "Carian Filigreed Crest",
    0x200017B6: "Sacrificial Twig",
    0x200017DE: "Ancestral Spirit's Horn",
}

WEAPON_ART_TABLE = {
    100: "Lion's Claw",
    101: "Impaling Thrust",
    102: "Piercing Fang",
    103: "Spinning Slash",
    105: "Charge Forth",
    106: "Stamp (Upward Cut)",
    107: "Stamp (Sweep)",
    108: "Blood Tax",
    109: "Repeating Thrust",
    110: "Wild Strikes",
    111: "Spinning Strikes",
    112: "Double Slash",
    113: "Prelate's Charge",
    114: "Unsheathe",
    115: "Square Off",
    116: "Giant Hunt",
    118: "Loretta's Slash",
    119: "Poison Moth Flight",
    120: "Spinning Weapon",
    122: "Storm Assault",
    123: "Stormcaller",
    124: "Sword Dance",
    200: "Glintblade Phalanx",
    201: "Sacred Blade",
    202: "Ice Spear",
    203: "Glintstone Pebble",
    204: "Bloody Slash",
    205: "Lifesteal Fist",
    207: "Eruption",
    208: "Prayerful Strike",
    209: "Gravitas",
    210: "Storm Blade",
    212: "Earthshaker",
    213: "Golden Land",
    214: "Flaming Strike",
    216: "Thunderbolt",
    217: "Lightning Slash",
    218: "Carian Grandeur",
    219: "Carian Greatsword",
    220: "Vacuum Slice",
    221: "Black Flame Tornado",
    222: "Sacred Ring of Light",
    224: "Blood Blade",
    225: "Phantom Slash",
    226: "Spectral Lance",
    227: "Chilling Mist",
    228: "Poisonous Mist",
    300: "Shield Bash",
    301: "Barricade Shield",
    302: "Parry",
    305: "Carian Retaliation",
    306: "Storm Wall",
    307: "Golden Parry",
    308: "Shield Crash",
    309: "Thops's Barrier",
    400: "Through and Through",
    401: "Barrage",
    402: "Mighty Shot",
    404: "Enchanted Shot",
    405: "Sky Shot",
    406: "Rain of Arrows",
    501: "Hoarfrost Stomp",
    502: "Storm Stomp",
    503: "Kick",
    504: "Lightning Ram",
    505: "Flame of the Redmanes",
    506: "Ground Slam",
    507: "Golden Slam",
    508: "Waves of Darkness",
    509: "Hoarah Loux's Earthshaker",
    600: "Determination",
    601: "Royal Knight's Resolve",
    602: "Assassin's Gambit",
    603: "Golden Vow",
    604: "Sacred Order",
    605: "Shared Order",
    606: "Seppuku",
    607: "Cragblade",
    650: "Barbaric Roar",
    651: "War Cry",
    652: "Beast's Roar",
    653: "Troll's Roar",
    654: "Braggart's Roar",
    700: "Endure",
    701: "Vow of the Indomitable",
    702: "Holy Ground",
    800: "Quickstep",
    801: "Bloodhound's Step",
    802: "Raptor of the Mists",
    850: "White Shadow's Lure",
}
