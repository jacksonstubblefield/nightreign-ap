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
from worlds.nightreign.game_data import CHARACTERS, EVERDARK_NIGHTLORDS, NIGHTLORDS


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


# --- `enable_everdark_checks` option coverage ---
# Everdark locations get the same access_rule gating as normal ones (see create_regions()), so
# test_fill (via WorldTestBase's default auto_construct) already re-exercises the softlock
# invariant this file exists for, now with Everdark locations mixed in - including combined with
# gate_boss_access, the exact combination that produced the original bug.

class NightreignEverdarkBossTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"enable_everdark_checks": True}

    def test_adds_one_everdark_location_per_everdark_nightlord(self) -> None:
        locations = self.multiworld.get_locations(self.world.player)
        everdark_names = [loc.name for loc in locations if loc.name.startswith("Defeat Everdark ")]
        self.assertEqual(len(everdark_names), len(EVERDARK_NIGHTLORDS))
        self.assertNotIn("Defeat Everdark Night Aspect", everdark_names)


class NightreignEverdarkBossAndCharacterTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {"enable_everdark_checks": True, "bosses_with_characters": "boss_and_character"}

    def test_everdark_locations_mirror_bosses_with_characters(self) -> None:
        locations = self.multiworld.get_locations(self.world.player)
        everdark_names = [loc.name for loc in locations if loc.name.startswith("Defeat Everdark ")]
        self.assertEqual(len(everdark_names), len(CHARACTERS) * len(EVERDARK_NIGHTLORDS))


class NightreignEverdarkWithGateTest(WorldTestBase):
    game = "Elden Ring Nightreign"
    options = {
        "enable_everdark_checks": True,
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
        "enable_everdark_checks": True,
        "bosses_with_characters": "boss_and_character",
        "goal": "all_bosses",
    }

    def test_goal_groups_ignores_everdark_locations(self) -> None:
        # all_bosses' goal_groups is one singleton per active location - if Everdark locations
        # leaked in, this count would include them too, and some seeds could become unwinnable
        # since Everdark availability isn't guaranteed (see Options.py's disclaimer).
        self.assertEqual(len(self.world.goal_groups), len(CHARACTERS) * len(NIGHTLORDS))


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
