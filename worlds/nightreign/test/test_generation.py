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
from worlds.nightreign.game_data import CHARACTERS, NIGHTLORDS


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


# --- `goal` option coverage ---
#
# World.create_regions() builds self.goal_groups (a list of groups, each satisfied by ANY one
# of its location ids being checked, with the overall goal requiring EVERY group satisfied -
# see client.py's _goal_complete for the client-side half of this). These tests check that
# structure directly rather than the fill/reachability invariant test_fill covers above.

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
