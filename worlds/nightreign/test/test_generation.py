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

from test.bases import WorldTestBase


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
