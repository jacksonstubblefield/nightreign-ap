"""Static game data for Nightreign
"""

from typing import Optional

# Character class ID
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
# DLC bosses (The Forsaken Hollows) live-verified 2026-08-29 by launching each expedition with the
# ACCESS_ALL_BOSSES_AOB menu patch active (see memory_reader.py) and reading boss_id once loaded
# in: Balancers=1080, Dreglord=1090. Unlike the base 8, no working EventFlag-based unlock was found
# for either despite testing several candidates (117, 6950-6952, and 110+117 together) - see
# ACCESS_ITEM_EVENT_FLAGS below for how that gap is handled.
#
# Keys are bases on multiples of 10; each boss matches its base +/- DRIFT_TOLERANCE, so the
# 9-wide windows never overlap. Raw ids actually sighted live in OBSERVED_BOSS_IDS below.
KNOWN_BOSS_IDS = {
    0: "Tricephalos",
    10: "Gaping Jaw",
    20: "Sentient Pest",
    30: "Augur",
    40: "Equilibrious Beast",
    50: "Darkdrift Knight",
    60: "Fissure in the Fog",
    70: "Night Aspect",
    1070: "Night Aspect",        # DLC map variant
    1080: "Balancers",
    1090: "Dreglord",
}
# Every raw boss_id actually read in a live run, kept even when it already falls inside a
# window - test_boss_ids.py checks each still resolves to the right boss.
OBSERVED_BOSS_IDS = {
    2: "Tricephalos",
    12: "Gaping Jaw",
    22: "Sentient Pest",
    23: "Sentient Pest",
    32: "Augur",
    43: "Equilibrious Beast",
    53: "Darkdrift Knight",
    61: "Fissure in the Fog",
    73: "Night Aspect",
    1074: "Night Aspect",        # user-reported 2026-10-02, DLC map
    1080: "Balancers",
    1084: "Balancers",           # user-reported 2026-10-02, Wylder, non-Everdark
    1090: "Dreglord",
}
# Each base covers base-4..base+4, leaving x5 as a gap between neighbours
DRIFT_TOLERANCE = 4

# +0xB50 reads this sentinel when no boss is selected (hub/menu). With DRIFT_TOLERANCE=4 this
# sits right inside Tricephalos's (base 0) match window, so it must be checked before
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

# Nightlords with an Everdark Sovereign variant - all of them except each campaign's finale boss
# (Night Aspect for the base game, Dreglord for the DLC), which has no Everdark form. Live-verified
# 2026-08-29 for Dreglord: its expedition entry has no Everdark option in the menu, while Balancers
# does (same boss_id, everdark=True - see memory_reader.py's read_everdark_flag()).
EVERDARK_NIGHTLORDS = [name for name in NIGHTLORDS if name not in ("Night Aspect", "Dreglord")]

# Everdark Sovereigns as their own separate, individually includable entries (e.g. "Everdark
# Tricephalos") - since they're entirely separate bosses from their base Nightlord (own checks, own
# Access item - see Items.py), they're selectable via Options.py's IncludedNightlords the same way
# base Nightlords are, rather than gated behind one all-or-nothing toggle. ALL_NIGHTLORD_ENTRIES is
# that option's full valid_keys set.
EVERDARK_NIGHTLORD_ENTRIES = [f"Everdark {name}" for name in EVERDARK_NIGHTLORDS]
ALL_NIGHTLORD_ENTRIES = NIGHTLORDS + EVERDARK_NIGHTLORD_ENTRIES

# Known event flags that unlock bosses
EVENT_FLAG_SECONDARY_BOSSES = 110
EVENT_FLAG_NIGHT_ASPECT = 115

# Event flags for ACCESS_NIGHTLORDS. Balancers/Dreglord are deliberately absent here - no working
# EventFlag was found for either (see KNOWN_BOSS_IDS's comment), so gate_boss_access has nothing to
# fire for their Access items and can't make them selectable in-game on its own. The
# unlock_all_bosses_in_game option (Options.py/client.py) is the real answer for these two - it
# patches the Expeditions menu's own selectability check directly (memory_reader.ACCESS_ALL_BOSSES_AOB
# / memory_writer's set_all_bosses_unlocked), independent of the EventFlag system entirely.
ACCESS_ITEM_EVENT_FLAGS = {
    f"{name} Access": (EVENT_FLAG_NIGHT_ASPECT if name == "Night Aspect"
                       else EVENT_FLAG_SECONDARY_BOSSES)
    for name in ACCESS_NIGHTLORDS
    if name not in ("Tricephalos", "Balancers", "Dreglord")
}


def starting_free_nightlords(starting_boss: str) -> list:
    """List of Nightlords that start unlocked for a given starting boss.
    """
    return [starting_boss]


def starting_free_everdark_nightlords(starting_boss: str) -> list:
    """List of Everdark Sovereigns that start unlocked for a given starting boss - only non-empty
    when starting_boss itself is an Everdark choice (see Options.py's StartingBoss/__init__.py's
    generate_early()). Everdark Sovereigns are separate bosses from their base Nightlord (own
    checks, own Access item - see EVERDARK_NIGHTLORDS/Items.py), so choosing e.g.
    "everdark_tricephalos" as starting_boss frees Everdark Tricephalos only, not base Tricephalos.
    """
    return [starting_boss]


# Event flags that unlock playable characters - individually addressable, unlike the batched
# secondary-boss flags above. Live-verified 2026-08-25 against a running offline save: fired each
# flag in turn and confirmed via the game's own character-select screen (Scholar's unlock even
# produced a native "New Character" popup). Directly confirmed: 6031->Duchess, 6037->Revenant,
# 6038->Scholar, 6039->Undertaker; the remaining 6 were already unlocked on the test save, so they
# follow the confirmed sequential pattern by inference rather than direct observation. That pattern
# matches the codename ordering (Tracker/Lady/Destroyer/Enforcer/Wise/Iron Eye/Guardian/Avenger)
# from https://soulsmodding.com/doku.php?id=nr-refmat:event-flag-list - this resolves the earlier
# disagreement with the CE table's partial/bundled reading (6037/6038/6039) in favor of the
# soulsmodding source's full 6030-6037 sequential range.
CHARACTER_EVENT_FLAGS = {
    "Wylder": 6030,
    "Duchess": 6031,
    "Raider": 6032,
    "Executor": 6033,
    "Recluse": 6034,
    "Ironeye": 6035,
    "Guardian": 6036,
    "Revenant": 6037,
    "Scholar": 6038,
    "Undertaker": 6039,
}

# Every character can be gated - unlike ACCESS_NIGHTLORDS, there's no Tricephalos-style "no flag"
# exception, since all 10 characters have a confirmed individually-addressable flag above.
ACCESS_CHARACTERS = list(CHARACTERS)

# Keyed the same shape as ACCESS_ITEM_EVENT_FLAGS (name -> flag, key already suffixed) so
# client.py's _sync_event_flags can treat both dicts identically.
CHARACTER_ACCESS_EVENT_FLAGS = {
    f"{name} Character Access": flag for name, flag in CHARACTER_EVENT_FLAGS.items()
}


def starting_free_characters(starting_character: str) -> list:
    """List of characters that start unlocked for a given starting character.
    """
    return [starting_character]


# --- Win-count checks ---
# Cumulative "Win N Expeditions" locations, tracked independently of which boss/character was
# defeated (see client.py's win-count handling) - one location per threshold, seed-scoped (the
# count lives in the per-seed run state file, resets for a new seed rather than persisting across
# them - see client.py's _open_run_state).
WIN_COUNT_UP_TO_MIN = 10
WIN_COUNT_UP_TO_MAX = 50

# The full, fixed universe of threshold values any win_count_up_to choice in [WIN_COUNT_UP_TO_MIN,
# WIN_COUNT_UP_TO_MAX] could ever produce via win_count_threshold_list() below - 1, 2, 3, 5, 7, then
# every integer from WIN_COUNT_UP_TO_MIN to WIN_COUNT_UP_TO_MAX (not just multiples of 5: any one of
# them could be the exact win_count_up_to a player picks, landing as that list's own final,
# not-a-multiple-of-5 entry). Locations.py builds its static id table from this - Options.py's
# WinCountUpTo choosing a value doesn't change which locations exist in the pool's namespace, only
# which of them create_regions() actually includes for that slot (same "full matrix, filtered
# per-player" pattern IncludedNightlords/IncludedCharacters already use), so ids never shift. Also
# reused, unchanged, as the full threshold universe for the Night 1/Night 2/weak/strong reward
# check families below - all five share the same curve/bounds by design (see nightreign-roadmap
# memory), so this constant and win_count_threshold_list() are intentionally generic despite the
# win_count-specific name.
WIN_COUNT_THRESHOLDS = (1, 2, 3, 5, 7) + tuple(range(WIN_COUNT_UP_TO_MIN, WIN_COUNT_UP_TO_MAX + 1))


def win_count_threshold_list(up_to: int) -> list:
    """The actual thresholds to generate checks for, given an up_to value: 1, 2, 3, 5, 7, 10, then
    every multiple of 5 up to `up_to`, plus `up_to` itself if it isn't already a multiple of 5 -
    e.g. up_to=21 -> [1, 2, 3, 5, 7, 10, 15, 20, 21]; up_to=24 -> [..., 15, 20, 24]; up_to=25 ->
    [..., 15, 20, 25] (25 is already a multiple of 5, so no extra entry). Despite the name, this is
    shared by Win Count, Night 1 Clear, Night 2 Clear, Weak Reward, and Strong Reward checks - all
    five use the same curve/bounds by design.
    """
    thresholds = [1, 2, 3, 5, 7, 10]
    step = 15
    while step <= up_to:
        thresholds.append(step)
        step += 5
    if up_to % 5 != 0:
        thresholds.append(up_to)
    return thresholds


# --- Nightlord bonus checks ---
# A flat 5 checks per Nightlord (or per Nightlord x character, mirroring bosses_with_characters),
# all sent together on the FIRST valid defeat - NOT a cumulative kill counter (repeat kills of the
# same Nightlord/character/Everdark combo award nothing further here, same as the existing
# "Defeat X" location already doesn't re-fire). Index 1 is just that existing "Defeat X" location,
# unchanged; indices 2-5 are new locations (see Locations.py's location_name_kill_bonus) sent
# alongside it in the same check_locations call. Universal - always on, no option gates this (see
# nightreign-roadmap memory for why: this and Night 1/Night 2 Clear below are meant to be baseline
# check density for every seed, not opt-in extras).
NIGHTLORD_BONUS_INDICES = (2, 3, 4, 5)


# --- Day/night phase tracking (Night 1 / Night 2 clear checks) ---
# GameDataMan+0x00de (see memory_reader.py's DAY_NIGHT_PHASE_OFFSET) cycles through an expedition:
# Day 1 -> Night 1 (mid-run boss) -> Day 2 -> Night 2 (second night boss) -> Day 3 (the Nightlord
# arena), then 5 back in the lobby; resets to Day 1 at the start of each new expedition. Night 1
# Clear fires on the Night 1 boss kill (the 1->2 transition); Night 2 Clear fires on the Night 2
# boss kill (the 3->4 transition, ~20-60s after the kill) - NOT on merely reaching the Night 2
# arena (2->3). DAY_PHASE_DAY_3 live-confirmed 2026-10-04 across a Night Aspect and an Augur run:
# 3->4 right after the Night 2 boss died, held at 4 through the whole Nightlord fight.
# Each Nightlord (or Nightlord x character, mirroring bosses_with_characters) gets exactly ONE
# Night 1 Clear location and ONE Night 2 Clear location - not a cumulative counter, and not
# optional, same "universal baseline" posture as the bonus checks above.
DAY_PHASE_DAY_1 = 0
DAY_PHASE_NIGHT_1 = 1
DAY_PHASE_DAY_2 = 2
DAY_PHASE_NIGHT_2 = 3
DAY_PHASE_DAY_3 = 4


def is_nightlord_kill_tick(
    last_buff_picks: Optional[int], buff_picks: Optional[int], day_phase: Optional[int]
) -> bool:
    """True when memory_reader's buff-pick counter (BUFF_PICK_COUNTER_OFFSET) just rose while in the
    Day 3 Nightlord arena - the game ticks that counter once on the Nightlord kill itself.

    This is the primary win signal, with the outcome pulse (OUTCOME_PULSE_OFFSET) as a fallback,
    because the pulse never fires for Night Aspect: its ending/credits path skips the normal result
    flow. Live-confirmed 2026-10-04: Augur's kill ticked this ~7s before the pulse; Night Aspect's
    kill ticked it with no pulse at all, and its phase-1 end did not tick it. The Day 3 arena holds
    only the Nightlord, so no other buff pick should land in this phase. last_buff_picks is None
    on the first in-run read (a baseline, never an edge), so connecting mid-fight can't misfire."""
    return (
        day_phase == DAY_PHASE_DAY_3
        and last_buff_picks is not None
        and buff_picks is not None
        and buff_picks > last_buff_picks
    )


# --- Reward-tier checks (weak/strong) ---
# Fixed 1-5 cumulative counter per Nightlord (or per Nightlord x character, mirroring
# bosses_with_characters) for the game's own "Weak"/"Strong" reward-tier POI pickups (see
# memory_reader.py's WEAPON_PICKUP_COUNTER_OFFSET/BUFF_PICK_COUNTER_OFFSET) collected during an
# Expedition against that Nightlord. Unlike the two families above, these stay opt-in
# (Options.py's WeakRewardChecks/StrongRewardChecks) since several can be earned in a single
# Expedition and not everyone wants that much added density. Fixed at 5, not configurable.
#
# KNOWN ISSUE, live-confirmed: neither counter is a POI-tier signal. A narrated live run
# (2026-10-04) showed "weak" counts every weapon acquired from any source (orb, chest, ground, any
# rarity) and "strong" counts boss-reward buff picks plus the Nightlord kill - see memory_reader.py's
# comment on those offsets. The original RE session (nightreign-roadmap memory, 2026-08-30) only
# corroborated them against real POI clears, which usually drop a weapon or buff as their reward.
# Both options default to off for that reason.
REWARD_CHECK_THRESHOLDS = (1, 2, 3, 4, 5)


# --- Item-drop write path (filler weapons) ---
# AOBs below are a Python port of the "Sly - ItemDrop" Cheat Engine script - see
# memory_writer.py's NightreignItemDropWriter. Resolved lazily, not in connect().

# Pointer-slot style (like GAMEMAN_AOB/GAMEDATAMAN_AOB), but the `mov reg,[rip+disp32]` instruction
# isn't inside the matched bytes - it starts MAPITEMMAN_AOB_OFFSET bytes past the match, per the
# CT table's own registerBaseAddr() Lua resolver, before _resolve_pointer_slot's usual RIP math.
MAPITEMMAN_AOB = "48 8B C8 E8 ?? ?? ?? ?? 0F 28 00 66 0F 7F 44 24 50"
MAPITEMMAN_AOB_OFFSET = 0x11

# Function-address style (like EVENTFLAG_BASE_A_AOB): the AOB scan lands near, not on, the real
# entry point - the caller applies ITEMDROP_CALL_FUNC_OFFSET after resolving.
ITEMDROP_CALL_AOB = "41 0F B6 E9 41 0F B6 F8 48 8B DA 48 8B F1 33 C0 48 89 44 24 30"
ITEMDROP_CALL_FUNC_OFFSET = -0x27  # real drop-function entry = match_addr + this

# Used directly (no offset) as the base for a further "+0xD" applied inline by the trampoline
# (see memory_writer.py) - the CT script reads a TLS index embedded as data at that fixed byte
# offset, mirroring how the compiler itself would resolve a thread-local variable.
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

# --- Currency grant write path (Murk/Runes/Sovereign Sigil filler) ---
# Ported from the CT table's "Give Murk"/"Give Runes [Expedition]"/"Give Sovereign Sigil" scripts
# (contributor Volkov_ilya37) - each is a plain `executeCodeEx(fn, [GameDataMan]+8, amount)`, i.e.
# fn(PlayerGameData*, amount), the same 2-argument shape memory_writer.py's EventFlag trampoline
# already handles. Every AOB lands directly on the function entry (no offset). Resolved lazily and
# independently of each other, not in connect() - see memory_reader.py's resolve_currency_target().
# NOT yet live-tested from Python, only via the source CT scripts.
MURK_GRANT_AOB = "44 8B 81 D0 00 00 00 4C 8B D1 B9 FF C9 9A 3B 41 8D 04 10 3B C1 0F 4F C1"
SOVEREIGN_SIGIL_GRANT_AOB = "44 8B 41 5C 4C 8B D1 B9 FF C9 9A 3B 41 8D 04 10 3B C1 0F 4F C1"
RUNES_GRANT_AOB = "48 89 5C 24 08 57 48 83 EC 20 8B 79 6C 48 8B D9"

# PlayerGameData-relative (i.e. [GameDataMan+0x8]+offset) counters each grant function above reads
# as its first instruction - read back before/after a grant for logging only, never as a
# success/retry signal (see client.py's _deliver_pending_currency for why).
MURK_COUNTER_OFFSET = 0xD0
SOVEREIGN_SIGIL_COUNTER_OFFSET = 0x5C
RUNES_COUNTER_OFFSET = 0x6C

# Both grant functions clamp the running total at 999,999,999 themselves (the `B9 FF C9 9A 3B`
# in their AOBs) - this just keeps one batched request inside a signed 32-bit int.
CURRENCY_GRANT_MAX = 999_999_999

# --- Current Animation read path (flight gating for the item-drop write path) ---
# WorldChrMan pointer-slot AOB, same shape as GAMEMAN_AOB/GAMEDATAMAN_AOB. Unlike those, its live
# object address changes across scenes, so callers must re-walk the chain on every read.
WORLDCHRMAN_AOB = "48 8B 05 ?? ?? ?? ?? 0F 28 F1 48 85 C0"

# [[[WorldChrMan+0x174E8]+0x1B8]+0x80]+0x98 is the local player's live "Current Animation" int -
# live-tested into four magnitude bands: ~2,000,000s (grounded), ~20,000s (hub/cutscene),
# ~60,000s (flying), 8-9 digits (attacks). Gates the item-drop write path (see client.py).
WORLDCHRMAN_ANIM_OFFSETS = (0x174E8, 0x1B8, 0x80)
WORLDCHRMAN_ANIM_FINAL_OFFSET = 0x98

# Live-tested flying band was 61020-69410 - kept as a round 60000-69999 range with headroom on
# both ends rather than the exact observed min/max, since those two sessions can't have sampled
# every possible flying sub-animation id.
FLYING_ANIMATION_RANGE = range(60000, 70000)


def is_flying_animation(current_animation: int) -> bool:
    """True if `current_animation` (see WORLDCHRMAN_ANIM_OFFSETS above) falls in the live-tested
    flying band - used to gate the randomized item-drop write path on the player being grounded."""
    return current_animation in FLYING_ANIMATION_RANGE


# Each grantable currency's counter offset, keyed by currency name - the same keys
# memory_reader.py's resolve_currency_target() uses to pick each currency's grant AOB.
CURRENCY_COUNTER_OFFSETS = {
    "Murk": MURK_COUNTER_OFFSET,
    "Runes": RUNES_COUNTER_OFFSET,
    "Sovereign Sigil": SOVEREIGN_SIGIL_COUNTER_OFFSET,
}

# Currency filler items, keyed by item name (see Items.py): (currency, amount granted, weight).
# Weight is relative within the same currency only - once __init__.py's get_filler_item_name()
# picks a currency, it picks which bundle by these weights, so a currency with several bundles
# isn't any more common overall than one with a single item.
# Runes: 5,000 is about one early level (level 2 costs 3,698); a Heroic Rune Bundle takes a fresh
# character to roughly level 7 (89,633 total, level 8 is 121,770). Murk weights are placeholders
# pending real play-calibration; Sovereign Sigils are a single fixed bundle of 6.
CURRENCY_BUNDLES = {
    "Rune Bundle": ("Runes", 5000, 95),
    "Heroic Rune Bundle": ("Runes", 100000, 5),
    "Murk Bundle": ("Murk", 500, 60),
    "Large Murk Bundle": ("Murk", 1000, 30),
    "Titanic Murk Bundle": ("Murk", 5000, 10),
    "Sovereign Sigil Bundle": ("Sovereign Sigil", 6, 1),
}


def currency_bundle_names(currency: str) -> list:
    """Every CURRENCY_BUNDLES item name that grants `currency`, in table order."""
    return [name for name, (bundle_currency, _amount, _weight) in CURRENCY_BUNDLES.items()
            if bundle_currency == currency]


def bundles_for_amount(currency: str, amount: int) -> list:
    """Fewest bundle items of `currency` adding up to `amount`, largest first - e.g. Murk 12,000 ->
    2 Titanic + 2 Large. Any remainder smaller than the smallest bundle is dropped, so the result
    can total slightly less than `amount` (Murk always comes out exact for multiples of 500)."""
    bundles = sorted(currency_bundle_names(currency), key=lambda name: -CURRENCY_BUNDLES[name][1])
    result = []
    for name in bundles:
        size = CURRENCY_BUNDLES[name][1]
        count, amount = divmod(amount, size)
        result += [name] * count
    return result
