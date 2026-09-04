"""Regression coverage for the boss-access softlock bug: create_regions() used to attach no
access_rule to any location, so the fill algorithm had no idea "Defeat X" required owning X's
Access item first. That let it place the only route to a Nightlord behind an unreachable
location (see a real seed's spoiler log: starting_boss Fissure in the Fog -> Night Aspect Access
-> a filler Trophy, a dead end, while Tricephalos/Gaping Jaw/Augur/Sentient Pest/Equilibrious
Beast/Darkdrift Night sat in disconnected cycles never reachable from the start).

WorldTestBase.test_fill (test/bases.py) reruns the real distribute_items_restrictive fill and
asserts every location is reachable in some sphere - exactly the invariant that broke. One class
per starting_boss option exercises every "freed Nightlord" case since that's what the access rule
branches on.
"""

from Options import OptionError
from test.bases import WorldTestBase
from worlds.nightreign.game_data import (ALL_NIGHTLORD_ENTRIES, CHARACTERS, EVERDARK_NIGHTLORDS,
                                          NIGHTLORD_BONUS_INDICES, NIGHTLORDS,
                                          REWARD_CHECK_THRESHOLDS)
from worlds.nightreign.Locations import (location_name, location_name_boss_only,
                                          location_name_everdark, location_name_everdark_boss_only,
                                          location_name_kill_bonus, location_name_night1,
                                          location_name_night2, location_name_strong_reward,
                                          location_name_weak_reward)

# All base Nightlords plus every Everdark Sovereign entry (e.g. "Everdark Tricephalos") - used by
# tests exercising Everdark checks, since IncludedNightlords excludes Everdark entries by default
# (see Options.py's IncludedNightlords).
ALL_NIGHTLORDS_WITH_EVERDARK = list(ALL_NIGHTLORD_ENTRIES)


class NightreignGateOffTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"gate_boss_access": False}


class NightreignGateTricephalosTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"gate_boss_access": True, "starting_boss": "tricephalos"}


class NightreignGateGapingJawTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"gate_boss_access": True, "starting_boss": "gaping_jaw"}


class NightreignGateSentientPestTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"gate_boss_access": True, "starting_boss": "sentient_pest"}


class NightreignGateAugurTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"gate_boss_access": True, "starting_boss": "augur"}


class NightreignGateEquilibriousBeastTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"gate_boss_access": True, "starting_boss": "equilibrious_beast"}


class NightreignGateDarkdriftNightTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"gate_boss_access": True, "starting_boss": "darkdrift_night"}


class NightreignGateFissureInTheFogTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"gate_boss_access": True, "starting_boss": "fissure_in_the_fog"}


class NightreignGateNightAspectTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"gate_boss_access": True, "starting_boss": "night_aspect"}


class NightreignGateBossAndCharacterTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"gate_boss_access": True, "bosses_with_characters": "boss_and_character"}


# --- `gate_character_access` option coverage ---
# Same shape as the gate_boss_access classes above - one per starting_character, exercising the
# character access_rule branch in create_regions()'s _make_location. Always paired with
# bosses_with_characters=boss_and_character: that's the only mode where a location's access_rule
# depends on which character is playing at all (see create_regions()'s comment on why "boss" mode
# has no such dependency), so it's the only mode where a character-gating access_rule mistake could
# reintroduce the original boss self-loop softlock bug for characters instead of Nightlords.

class NightreignGateCharacterOffTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"gate_character_access": False, "bosses_with_characters": "boss_and_character"}


class NightreignGateCharacterWylderTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_character_access": True, "bosses_with_characters": "boss_and_character",
        "starting_character": "wylder",
    }


class NightreignGateCharacterGuardianTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_character_access": True, "bosses_with_characters": "boss_and_character",
        "starting_character": "guardian",
    }


class NightreignGateCharacterIroneyeTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_character_access": True, "bosses_with_characters": "boss_and_character",
        "starting_character": "ironeye",
    }


class NightreignGateCharacterDuchessTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_character_access": True, "bosses_with_characters": "boss_and_character",
        "starting_character": "duchess",
    }


class NightreignGateCharacterRaiderTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_character_access": True, "bosses_with_characters": "boss_and_character",
        "starting_character": "raider",
    }


class NightreignGateCharacterRevenantTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_character_access": True, "bosses_with_characters": "boss_and_character",
        "starting_character": "revenant",
    }


class NightreignGateCharacterRecluseTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_character_access": True, "bosses_with_characters": "boss_and_character",
        "starting_character": "recluse",
    }


class NightreignGateCharacterExecutorTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_character_access": True, "bosses_with_characters": "boss_and_character",
        "starting_character": "executor",
    }


class NightreignGateCharacterScholarTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_character_access": True, "bosses_with_characters": "boss_and_character",
        "starting_character": "scholar",
    }


class NightreignGateCharacterUndertakerTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_character_access": True, "bosses_with_characters": "boss_and_character",
        "starting_character": "undertaker",
    }


class NightreignGateBossAndCharacterAccessTogetherTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_boss_access": True,
        "gate_character_access": True,
        "bosses_with_characters": "boss_and_character",
        "starting_boss": "fissure_in_the_fog",  # the exact starting_boss the original softlock used
        "starting_character": "revenant",
    }
    # Both gates on at once, combined via _make_location's AND-rule - the real stress case. No
    # dedicated test method needed, same reasoning as NightreignEverdarkWithGateTest: WorldTestBase's
    # default test_fill already reruns real distribute_items_restrictive and asserts nothing is
    # unreachable.


class NightreignGateCharacterNotEnoughRoomTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    auto_construct = False
    options = {
        "gate_boss_access": False,
        "gate_character_access": True,
        "bosses_with_characters": "boss",  # locations aren't per-character in this mode
        "included_characters": CHARACTERS,  # all 10, minus 1 starting = 9 Character Access items
        "included_nightlords": ["Tricephalos"],  # only 1 location exists to hold them
    }

    def test_not_enough_locations_for_character_access_raises(self) -> None:
        # "boss" mode's location count depends only on included_nightlords, not
        # included_characters, so a slot can ask for more Character Access items than there are
        # locations to hold them - this should raise clearly rather than silently producing a
        # negative filler_count.
        with self.assertRaises(OptionError):
            self.world_setup()


# --- Everdark checks via IncludedNightlords' "Everdark X" entries ---
# Everdark locations get the same access_rule gating as normal ones (see create_regions()), so
# test_fill (via WorldTestBase's default auto_construct) already re-exercises the softlock
# invariant this file exists for, now with Everdark locations mixed in - including combined with
# gate_boss_access, the exact combination that produced the original bug.

class NightreignEverdarkBossTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"included_nightlords": ALL_NIGHTLORDS_WITH_EVERDARK}

    def test_adds_one_everdark_location_per_everdark_nightlord(self) -> None:
        # Exact-name match, not a prefix: nightlord_bonus_checks is universal now, so
        # "Defeat Everdark X (Bonus N)" locations also start with "Defeat Everdark " and would
        # inflate a prefix-based count 5x.
        locations = self.multiworld.get_locations(self.world.player)
        names = {loc.name for loc in locations}
        everdark_names = [
            location_name_everdark_boss_only(nightlord) for nightlord in EVERDARK_NIGHTLORDS
        ]
        for name in everdark_names:
            self.assertIn(name, names)
        self.assertNotIn("Defeat Everdark Night Aspect", names)


class NightreignEverdarkBossAndCharacterTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "included_nightlords": ALL_NIGHTLORDS_WITH_EVERDARK,
        "bosses_with_characters": "boss_and_character",
    }

    def test_everdark_locations_mirror_bosses_with_characters(self) -> None:
        # Exact-name match, not a prefix: nightlord_bonus_checks is universal now, so
        # "Defeat Everdark X as Y (Bonus N)" locations also start with "Defeat Everdark " and would
        # inflate a prefix-based count 5x.
        locations = self.multiworld.get_locations(self.world.player)
        names = {loc.name for loc in locations}
        expected = {
            location_name_everdark(character, nightlord)
            for character in CHARACTERS for nightlord in EVERDARK_NIGHTLORDS
        }
        self.assertTrue(expected.issubset(names))
        self.assertEqual(len(expected), len(CHARACTERS) * len(EVERDARK_NIGHTLORDS))


class NightreignEverdarkWithGateTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "included_nightlords": ALL_NIGHTLORDS_WITH_EVERDARK,
        "gate_boss_access": True,
        "bosses_with_characters": "boss_and_character",
        "starting_boss": "fissure_in_the_fog",  # the exact starting_boss the original softlock used
    }
    # No dedicated test method needed - WorldTestBase's default test_fill (run via auto_construct)
    # already reruns real distribute_items_restrictive and asserts nothing is unreachable, which is
    # exactly what would catch an Everdark access_rule mistake reintroducing the original softlock.


class NightreignEverdarkNotInGoalGroupsTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "included_nightlords": ALL_NIGHTLORDS_WITH_EVERDARK,
        "bosses_with_characters": "boss_and_character",
        "goal": "all_bosses",
    }

    def test_goal_groups_ignores_everdark_locations(self) -> None:
        # all_bosses' goal_groups is one singleton per active location - if Everdark locations
        # leaked in, this count would include them too, and some seeds could become unwinnable
        # since Everdark availability isn't guaranteed (see Options.py's disclaimer).
        self.assertEqual(len(self.world.goal_groups), len(CHARACTERS) * len(NIGHTLORDS))


class NightreignEverdarkAccessIsSeparateTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "included_nightlords": ALL_NIGHTLORDS_WITH_EVERDARK,
        "gate_boss_access": True,
        "starting_boss": "tricephalos",
    }

    def test_everdark_location_needs_its_own_access_item(self) -> None:
        # Tricephalos is the starting_boss (freed) - "Defeat Tricephalos" is reachable immediately.
        self.assertTrue(self.can_reach_location("Defeat Tricephalos"))
        # Everdark Tricephalos is a separate boss from base Tricephalos - it is NOT freed just
        # because the base form is, and needs its own "Everdark Tricephalos Access" item.
        self.assertFalse(self.can_reach_location("Defeat Everdark Tricephalos"))
        self.collect_by_name("Everdark Tricephalos Access")
        self.assertTrue(self.can_reach_location("Defeat Everdark Tricephalos"))

    def test_access_items_are_named_distinctly(self) -> None:
        item_names = {item.name for item in self.multiworld.itempool}
        self.assertIn("Everdark Tricephalos Access", item_names)
        # Tricephalos is the freed starting_boss, so its own (non-Everdark) Access item was never
        # added to the pool at all - the two access items are never conflated with each other.
        self.assertNotIn("Tricephalos Access", item_names)


class NightreignNoFillerSourceTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    auto_construct = False
    options = {"receive_weapons": False, "receive_talismans": False}

    def test_disabling_both_weapons_and_talismans_raises(self) -> None:
        # Trophy items (the old always-available flavor filler) were removed once Randomized
        # Weapon/Talisman gave real in-game drops, so with both of those off there is no filler
        # item left for get_filler_item_name() to choose from.
        with self.assertRaises(OptionError):
            self.world_setup()


# --- `goal` option coverage ---
# World.create_regions() builds self.goal_groups (see client.py's _goal_complete). These tests
# check that structure directly, not the fill/reachability invariant test_fill covers above.

class NightreignGoalRandomWrongGranularityTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    auto_construct = False
    options = {"goal": "random_subset", "bosses_with_characters": "boss"}

    def test_random_goal_requires_boss_and_character(self) -> None:
        with self.assertRaises(OptionError):
            self.world_setup()


class NightreignGoalNightAspectExcludedTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    auto_construct = False
    options = {"goal": "night_aspect", "included_nightlords": ["Tricephalos"]}

    def test_night_aspect_goal_requires_night_aspect_included(self) -> None:
        with self.assertRaises(OptionError):
            self.world_setup()


class NightreignGoalRandomMinTooHighTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    auto_construct = False
    options = {
        "goal": "random_subset",
        "bosses_with_characters": "boss_and_character",
        "included_characters": ["Wylder"],
        "included_nightlords": ["Tricephalos"],
        "goal_random_min": 2,  # only 1 combo (Wylder x Tricephalos) is available
    }

    def test_random_goal_min_above_available_combos(self) -> None:
        with self.assertRaises(OptionError):
            self.world_setup()


class NightreignGoalNightAspectTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"goal": "night_aspect", "bosses_with_characters": "boss_and_character"}

    def test_goal_groups_is_one_group_of_every_characters_night_aspect_win(self) -> None:
        self.assertEqual(len(self.world.goal_groups), 1)
        self.assertEqual(len(self.world.goal_groups[0]), len(CHARACTERS))


class NightreignGoalAllBossesAnyCharacterTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "goal": "all_bosses_any_character",
        "bosses_with_characters": "boss_and_character",
        "included_characters": ["Wylder", "Guardian"],
    }

    def test_goal_groups_is_one_group_per_nightlord(self) -> None:
        self.assertEqual(len(self.world.goal_groups), len(NIGHTLORDS))
        for group in self.world.goal_groups:
            self.assertEqual(len(group), 2)  # Wylder + Guardian


class NightreignGoalRandomTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "goal": "random_subset",
        "bosses_with_characters": "boss_and_character",
        "goal_random_min": 3,
        "goal_random_max": 5,
    }

    def test_goal_groups_is_singletons_bounded_by_min_and_max(self) -> None:
        self.assertGreaterEqual(len(self.world.goal_groups), 3)
        self.assertLessEqual(len(self.world.goal_groups), 5)
        for group in self.world.goal_groups:
            self.assertEqual(len(group), 1)
        all_ids = [location_id for group in self.world.goal_groups for location_id in group]
        self.assertEqual(len(all_ids), len(set(all_ids)))  # no duplicate objectives


class NightreignStartingBossEverdarkTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "starting_boss": "everdark_tricephalos",
        "included_nightlords": ALL_NIGHTLORDS_WITH_EVERDARK,
    }

    def test_starting_boss_resolves_to_base_nightlord_name(self) -> None:
        self.assertEqual(self.world.starting_boss, "Tricephalos")
        self.assertTrue(self.world.starting_boss_everdark)

    def test_everdark_starting_boss_frees_only_the_everdark_form(self) -> None:
        # The base Nightlord (Tricephalos) is a separate boss from Everdark Tricephalos and stays
        # gated - only "Everdark Tricephalos Access" is freed.
        self.assertEqual(self.world.freed_nightlords, set())
        self.assertEqual(self.world.freed_everdark_nightlords, {"Tricephalos"})


# --- `win_count_checks` option coverage ---
# Cumulative "Win N Expeditions" locations (see game_data.win_count_threshold_list), independent of
# any boss/character - never gated (create_regions() attaches no access_rule to them), so test_fill
# (via WorldTestBase's default auto_construct) exercising real distribute_items_restrictive already
# confirms they're all reachable.

class NightreignWinCountChecksOffTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"win_count_checks": False}

    def test_no_win_count_locations_added(self) -> None:
        locations = self.multiworld.get_locations(self.world.player)
        self.assertFalse(any(loc.name.startswith("Win ") for loc in locations))


class NightreignWinCountChecksOnTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"win_count_checks": True}  # win_count_up_to defaults to 25

    def test_adds_one_location_per_threshold(self) -> None:
        locations = self.multiworld.get_locations(self.world.player)
        win_count_names = {loc.name for loc in locations if loc.name.startswith("Win ")}
        # win_count_up_to=25 is already a multiple of 5, so no extra remainder entry beyond it.
        self.assertEqual(win_count_names, {
            "Win 1 Expedition", "Win 2 Expeditions", "Win 3 Expeditions", "Win 5 Expeditions",
            "Win 7 Expeditions", "Win 10 Expeditions", "Win 15 Expeditions", "Win 20 Expeditions",
            "Win 25 Expeditions",
        })

    def test_win_count_locations_never_gated(self) -> None:
        # No access_rule tied to any boss/character Access item - always reachable, same as every
        # other location here (topology_present = False).
        self.assertTrue(self.can_reach_location("Win 25 Expeditions"))

    def test_win_count_locations_excluded_from_goal_groups(self) -> None:
        # goal_groups is built from `locations` only (see create_regions()) - a win-count location
        # id should never show up there, same guarantee Everdark locations already have.
        all_goal_ids = {
            location_id for group in self.world.goal_groups for location_id in group
        }
        win_count_ids = {
            loc.address for loc in self.multiworld.get_locations(self.world.player)
            if loc.name.startswith("Win ")
        }
        self.assertTrue(win_count_ids.isdisjoint(all_goal_ids))


class NightreignWinCountUpToTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"win_count_checks": True, "win_count_up_to": 10}

    def test_thresholds_capped_at_up_to(self) -> None:
        locations = self.multiworld.get_locations(self.world.player)
        win_count_names = {loc.name for loc in locations if loc.name.startswith("Win ")}
        self.assertEqual(win_count_names, {
            "Win 1 Expedition", "Win 2 Expeditions", "Win 3 Expeditions",
            "Win 5 Expeditions", "Win 7 Expeditions", "Win 10 Expeditions",
        })
        self.assertNotIn("Win 15 Expeditions", win_count_names)
        self.assertNotIn("Win 20 Expeditions", win_count_names)
        self.assertNotIn("Win 25 Expeditions", win_count_names)


class NightreignWinCountUpToRemainderTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    # 21 isn't a multiple of 5 - it should land as its own final threshold on top of the last
    # multiple of 5 below it (20), not be dropped and not replace 20.
    options = {"win_count_checks": True, "win_count_up_to": 21}

    def test_up_to_value_not_a_multiple_of_5_is_its_own_final_threshold(self) -> None:
        locations = self.multiworld.get_locations(self.world.player)
        win_count_names = {loc.name for loc in locations if loc.name.startswith("Win ")}
        self.assertEqual(win_count_names, {
            "Win 1 Expedition", "Win 2 Expeditions", "Win 3 Expeditions", "Win 5 Expeditions",
            "Win 7 Expeditions", "Win 10 Expeditions", "Win 15 Expeditions", "Win 20 Expeditions",
            "Win 21 Expeditions",
        })


class NightreignStartingBossEverdarkWithoutChecksTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    auto_construct = False
    options = {
        "starting_boss": "everdark_tricephalos",
        # default included_nightlords has no "Everdark X" entries at all.
    }

    def test_everdark_starting_boss_requires_everdark_entry_in_included_nightlords(self) -> None:
        with self.assertRaises(OptionError):
            self.world_setup()


# --- Nightlord Bonus checks (universal, no toggle) ---
# Adds 4 bonus locations (see game_data.NIGHTLORD_BONUS_INDICES) alongside each existing "Defeat X"
# location (index 1, unchanged), built with the exact same access_rule as their base Nightlord's
# "Defeat X" location (see create_regions()'s _expand_thresholds/_make_location) - NOT a cumulative
# kill counter (client.py's _handle_win sends all 4 together on the first valid win; that
# all-at-once client-side behavior isn't exercised by generation-only tests like these, only the
# location/access_rule shape is). Always generated - no option disables this.

class NightreignBonusChecksAlwaysAddedTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"included_nightlords": frozenset({"Tricephalos"}), "goal": "all_bosses"}

    def test_adds_4_bonus_locations(self) -> None:
        locations = self.multiworld.get_locations(self.world.player)
        names = {loc.name for loc in locations}
        self.assertIn(location_name_boss_only("Tricephalos"), names)  # index 1, unchanged
        for index in NIGHTLORD_BONUS_INDICES:
            self.assertIn(location_name_kill_bonus("Tricephalos", index), names)

    def test_bonus_locations_excluded_from_goal_groups(self) -> None:
        all_goal_ids = {
            location_id for group in self.world.goal_groups for location_id in group
        }
        bonus_ids = {
            loc.address for loc in self.multiworld.get_locations(self.world.player)
            if loc.name != location_name_boss_only("Tricephalos") and loc.name.startswith("Defeat ")
        }
        self.assertTrue(bonus_ids)
        self.assertTrue(bonus_ids.isdisjoint(all_goal_ids))


class NightreignBonusChecksShareAccessRuleTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    # Gaping Jaw isn't the starting_boss (Tricephalos is), so it starts locked - if the bonus
    # locations didn't share the exact same access_rule as the base "Defeat Gaping Jaw" location,
    # this would either be reachable from the start (missing rule - the original softlock bug's
    # exact shape) or never reachable at all (a wrong/mismatched rule).
    options = {
        "gate_boss_access": True, "starting_boss": "tricephalos",
        "included_nightlords": frozenset({"Tricephalos", "Gaping Jaw"}),
        "goal": "all_bosses",
    }

    def test_locked_until_access_item_collected(self) -> None:
        location = location_name_kill_bonus("Gaping Jaw", 2)
        self.assertFalse(self.can_reach_location(location))
        self.collect_by_name("Gaping Jaw Access")
        self.assertTrue(self.can_reach_location(location))


# --- Night 1 / Night 2 Clear checks (universal, no toggle) ---
# Exactly one location each per Nightlord (or Nightlord x character), driven client-side by the
# day/night phase transition - not a cumulative counter, so there's no threshold/up_to dimension to
# test here at all, just that the single location exists, is reachable under the same rule as the
# base Nightlord, and stays out of goal_groups. Night 2 just confirms its own distinct location name
# is generated (catching a copy-paste mistake that reused Night 1's name function).

class NightreignNightClearChecksAlwaysAddedTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"included_nightlords": frozenset({"Tricephalos"}), "goal": "all_bosses"}

    def test_adds_exactly_one_night1_and_night2_location(self) -> None:
        locations = self.multiworld.get_locations(self.world.player)
        names = {loc.name for loc in locations}
        self.assertIn(location_name_night1("Tricephalos"), names)
        self.assertIn(location_name_night2("Tricephalos"), names)

    def test_night_clear_locations_never_gated_by_default(self) -> None:
        # gate_boss_access is off by default - every location, including these, stays reachable.
        self.assertTrue(self.can_reach_location(location_name_night1("Tricephalos")))
        self.assertTrue(self.can_reach_location(location_name_night2("Tricephalos")))

    def test_night_clear_locations_excluded_from_goal_groups(self) -> None:
        all_goal_ids = {
            location_id for group in self.world.goal_groups for location_id in group
        }
        night_clear_ids = {
            loc.address for loc in self.multiworld.get_locations(self.world.player)
            if loc.name.startswith("Clear Night ")
        }
        self.assertTrue(night_clear_ids)
        self.assertTrue(night_clear_ids.isdisjoint(all_goal_ids))


class NightreignNightClearChecksShareAccessRuleTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "gate_boss_access": True, "starting_boss": "tricephalos",
        "included_nightlords": frozenset({"Tricephalos", "Gaping Jaw"}),
        "goal": "all_bosses",
    }

    def test_locked_until_access_item_collected(self) -> None:
        night1_location = location_name_night1("Gaping Jaw")
        night2_location = location_name_night2("Gaping Jaw")
        self.assertFalse(self.can_reach_location(night1_location))
        self.assertFalse(self.can_reach_location(night2_location))
        self.collect_by_name("Gaping Jaw Access")
        self.assertTrue(self.can_reach_location(night1_location))
        self.assertTrue(self.can_reach_location(night2_location))


# --- `weak_reward_checks`/`strong_reward_checks` option coverage ---
# Both options are currently commented out in Options.py (the underlying memory counter fires on
# any weapon pickup, not just genuine reward-tier POI clears - see game_data.py's
# REWARD_CHECK_THRESHOLDS comment). There's no "on" state to test right now - only that the family
# stays fully absent regardless of what a stale options dict might still ask for (an unknown option
# key is silently ignored by the test harness, not an error, so this also guards against a
# leftover "weak_reward_checks": True somewhere quietly doing nothing instead of failing loudly).
# The commented-out On tests below are kept, not deleted, to restore quickly once the option
# itself is restored.

class NightreignWeakRewardChecksAlwaysOffTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "weak_reward_checks": True, "strong_reward_checks": True,  # ignored - see comment above
        "included_nightlords": frozenset({"Tricephalos"}), "goal": "all_bosses",
    }

    def test_no_weak_or_strong_reward_locations_added(self) -> None:
        locations = self.multiworld.get_locations(self.world.player)
        self.assertFalse(any(loc.name.startswith("Weak Reward ") for loc in locations))
        self.assertFalse(any(loc.name.startswith("Strong Reward ") for loc in locations))


# class NightreignWeakRewardChecksOnTest(WorldTestBase):
#     game = "Elden Ring Nightreign"
#     options = {
#         "weak_reward_checks": True, "included_nightlords": frozenset({"Tricephalos"}),
#         "goal": "all_bosses",
#     }
#
#     def test_adds_one_location_per_threshold(self) -> None:
#         locations = self.multiworld.get_locations(self.world.player)
#         names = {loc.name for loc in locations if loc.name.startswith("Weak Reward ")}
#         expected = {
#             location_name_weak_reward("Tricephalos", count) for count in REWARD_CHECK_THRESHOLDS
#         }
#         self.assertEqual(names, expected)
#
#     def test_weak_reward_locations_excluded_from_goal_groups(self) -> None:
#         all_goal_ids = {
#             location_id for group in self.world.goal_groups for location_id in group
#         }
#         weak_reward_ids = {
#             loc.address for loc in self.multiworld.get_locations(self.world.player)
#             if loc.name.startswith("Weak Reward ")
#         }
#         self.assertTrue(weak_reward_ids)
#         self.assertTrue(weak_reward_ids.isdisjoint(all_goal_ids))
#
#
# class NightreignStrongRewardChecksOnTest(WorldTestBase):
#     game = "Elden Ring Nightreign"
#     options = {
#         "strong_reward_checks": True, "included_nightlords": frozenset({"Tricephalos"}),
#         "goal": "all_bosses",
#     }
#
#     def test_adds_one_location_per_threshold(self) -> None:
#         locations = self.multiworld.get_locations(self.world.player)
#         names = {loc.name for loc in locations if loc.name.startswith("Strong Reward ")}
#         expected = {
#             location_name_strong_reward("Tricephalos", count) for count in REWARD_CHECK_THRESHOLDS
#         }
#         self.assertEqual(names, expected)


class NightreignAllExtraCheckFamiliesTogetherTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    # boss_and_character plus an Everdark entry, to exercise create_regions()'s full cross product
    # (the shape most likely to break silently) for the always-on bonus/Night 1/Night 2 families.
    # weak_reward_checks/strong_reward_checks dropped from here - no "on" state exists right now.
    options = {
        "bosses_with_characters": "boss_and_character",
        "included_nightlords": frozenset({"Tricephalos", "Everdark Tricephalos"}),
        "included_characters": frozenset({"Wylder"}), "goal": "all_bosses",
    }

    def test_everdark_bonus_location_generated(self) -> None:
        locations = self.multiworld.get_locations(self.world.player)
        names = {loc.name for loc in locations}
        self.assertIn(
            location_name_kill_bonus("Tricephalos", 2, "Wylder", everdark=True), names
        )

    def test_no_extra_check_family_location_in_goal_groups(self) -> None:
        # In boss_and_character mode, the only location goal_groups (goal=all_bosses default)
        # should ever contain is the base per-character "Defeat Tricephalos as Wylder" - everything
        # else this slot generated (bonus checks, Night 1/2, weak/strong, Everdark) must be
        # disjoint. Exact-name exclusion, not a prefix match: a prefix match on "Defeat Tricephalos
        # as" would also swallow "Defeat Tricephalos as Wylder x2" and silently weaken this test.
        all_goal_ids = {
            location_id for group in self.world.goal_groups for location_id in group
        }
        base_defeat_name = location_name("Wylder", "Tricephalos")
        extra_ids = {
            loc.address for loc in self.multiworld.get_locations(self.world.player)
            if loc.name != base_defeat_name
        }
        self.assertTrue(extra_ids)
        self.assertTrue(extra_ids.isdisjoint(all_goal_ids))
