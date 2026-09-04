from BaseClasses import Region, Tutorial
from Options import OptionError
from worlds.AutoWorld import World, WebWorld
from worlds.LauncherComponents import Component, Type, components, icon_paths, launch_subprocess

from .game_data import (ACCESS_CHARACTERS, ACCESS_NIGHTLORDS, CHARACTERS, EVERDARK_NIGHTLORDS,
                        NIGHTLORD_BONUS_INDICES, NIGHTLORDS, starting_free_characters,
                        starting_free_everdark_nightlords, starting_free_nightlords,
                        win_count_threshold_list)
from .Items import FILLER_ITEM_NAMES, NightreignItem, item_name_to_id, item_table
from .Locations import (NightreignLocation, location_name, location_name_boss_only,
                        location_name_everdark, location_name_everdark_boss_only,
                        location_name_kill_bonus, location_name_night1, location_name_night2,
                        location_name_strong_reward, location_name_to_id, location_name_weak_reward,
                        location_name_win_count)
from .Options import NightreignOptions, option_groups


def launch_client():
    # Lazy import so `pymem` isn't imported at world-load time - Generate.py and the webhost
    # load every world's __init__.py unconditionally, but only need the client when a user
    # launches it from the Archipelago Launcher.
    from .client import launch

    launch_subprocess(launch, name="NightreignClient")


components.append(Component("Nightreign Client", func=launch_client, component_type=Type.CLIENT, icon="nightreign"))
icon_paths["nightreign"] = f"ap:{__name__}/data/image.png"


class NightreignWeb(WebWorld):
    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up the Archipelago Elden Ring Nightreign tracker.",
        "English",
        "setup_en.md",
        "setup/en",
        ["jrstubb"],
    )

    tutorials = [setup_en]
    option_groups = option_groups


class NightreignWorld(World):
    """
    Elden Ring Nightreign is a co-op roguelike action game from FromSoftware.
    Location checks are "defeat Nightlord X" (or, with bosses_with_characters set
    to boss_and_character, "defeat Nightlord X as character Y"), detected via
    read-only game memory polling. With the gate_boss_access option enabled,
    every Nightlord other than the chosen starting_boss is gated behind
    receiving that Nightlord's Access item - written into the running game
    process where the game supports it (all but Tricephalos, which has no
    gating flag and is tracked overlay-side only); otherwise received items
    are flavorful and have no in-game effect. The gate_character_access option works the same way
    for playable characters instead of Nightlords - every character other than the chosen
    starting_character is gated behind receiving that character's Character Access item, and with
    bosses_with_characters set to boss_and_character, a win as a not-yet-unlocked character also
    doesn't send its check. Each Everdark Sovereign is its own separate entry in
    included_nightlords (e.g. "Everdark Tricephalos", excluded by default) - defeating one is a
    separate, optional location, never required for the goal, since Everdark availability depends
    on an external weekly rotation this world can't unlock or guarantee (see Options.py's
    IncludedNightlords disclaimer). Everdark Sovereigns are treated as entirely separate bosses
    from their base Nightlord: with gate_boss_access on, an Everdark location is gated behind its
    own "Everdark X Access" item, independent of whether the base Nightlord's own Access item has
    been received. With win_count_checks enabled, extra locations are added for winning a
    cumulative number of Expeditions this seed (see game_data.win_count_threshold_list and
    win_count_up_to) - independent of which boss/character was defeated, never gated, and never
    required for the goal. Two more check families add density within and across a Nightlord's own
    Expeditions specifically (unlike win_count_checks, which is global), never gated, never
    required for the goal, and universal - always generated, no option to disable "for now": a
    Nightlord's first valid defeat always sends 4 extra bonus checks alongside the existing
    "Defeat X" check (5 total, all at once - not a cumulative kill counter, repeat defeats award
    nothing further here), and each Nightlord always has exactly one Night 1 Clear and one Night 2
    Clear location, detected via the day/night phase transition rather than the win itself (Night 1
    on defeating the mid-run boss, Night 2 on a successful transition out of the Nightlord fight
    itself). A third family, weak_reward_checks/strong_reward_checks (cumulative counters, fixed at
    1-5, for the game's own "Weak"/"Strong" reward-tier POI pickups) exists in Locations.py/
    client.py but its Options.py toggles are currently commented out - live-confirmed to also fire
    on any weapon pickup at all, including this world's own randomized weapon drops, so there's no
    way to enable it right now (see Options.py for the known-issue writeup, still there next to the
    commented-out classes). The two universal families mirror bosses_with_characters and cover
    Everdark Sovereigns the same way the base locations do.
    """

    game = "Elden Ring Nightreign"
    web = NightreignWeb()

    options_dataclass = NightreignOptions
    options: NightreignOptions

    topology_present = False

    base_id = 3939000
    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id

    active_locations: list[str]
    everdark_nightlords: list[str]
    starting_boss: str
    starting_boss_everdark: bool
    freed_nightlords: set
    freed_everdark_nightlords: set
    starting_character: str
    freed_characters: set
    goal_groups: list[list[int]]
    goal_random_count: int
    win_count_thresholds: list[int]
    weak_reward_thresholds: list[int]
    strong_reward_thresholds: list[int]

    def generate_early(self) -> None:
        # No item/location gating here (topology_present = False), so there's no CollectionState
        # condition that reflects real progress - the goal is only observed live by the client
        # (see client.py's _maybe_declare_goal). Set explicitly, per docs/adding games.md.
        self.multiworld.completion_condition[self.player] = lambda state: True

        if not self.options.receive_weapons and not self.options.receive_talismans:
            # There is no other flavorful filler item left (Trophy items were removed once
            # Randomized Weapon/Talisman gave real in-game drops) - with both options off,
            # get_filler_item_name() would have an empty pool to choose from.
            raise OptionError(
                f"{self.player_name}: at least one of receive_weapons/receive_talismans must be "
                "enabled, since filler items are drawn from those two pools."
            )

        # A starting_boss value >= len(NIGHTLORDS) is one of the everdark_* choices, positionally
        # mapped over EVERDARK_NIGHTLORDS instead (see Options.py's StartingBoss asserts).
        # self.starting_boss stays the base Nightlord name either way (used to name the freed
        # entry), but Everdark Sovereigns are separate bosses from their base Nightlord - own
        # checks, own Access item (see EVERDARK_NIGHTLORDS/Items.py) - so which set gets freed
        # below depends on starting_boss_everdark: picking "everdark_tricephalos" frees Everdark
        # Tricephalos only, leaving base Tricephalos just as gated as any other Nightlord.
        starting_boss_value = self.options.starting_boss.value
        self.starting_boss_everdark = starting_boss_value >= len(NIGHTLORDS)
        self.starting_boss = (
            EVERDARK_NIGHTLORDS[starting_boss_value - len(NIGHTLORDS)] if self.starting_boss_everdark
            else NIGHTLORDS[starting_boss_value]
        )
        if (self.starting_boss_everdark
                and f"Everdark {self.starting_boss}" not in self.options.included_nightlords.value):
            raise OptionError(
                f"{self.player_name}: starting_boss is an Everdark Sovereign "
                f"({self.starting_boss}), but \"Everdark {self.starting_boss}\" isn't in "
                "included_nightlords - there'd be no Everdark check for it to grant free access to."
            )
        if self.starting_boss_everdark:
            self.freed_nightlords = set()
            self.freed_everdark_nightlords = set(
                starting_free_everdark_nightlords(self.starting_boss)
            )
        else:
            self.freed_nightlords = set(starting_free_nightlords(self.starting_boss))
            self.freed_everdark_nightlords = set()
        self.starting_character = CHARACTERS[self.options.starting_character.value]
        self.freed_characters = set(starting_free_characters(self.starting_character))

        included_characters = self.options.included_characters.value
        # included_nightlords.value may also contain "Everdark X" entries (see
        # game_data.EVERDARK_NIGHTLORD_ENTRIES/Options.py's IncludedNightlords) - filtered out here
        # since goal_random_count/the night_aspect check below are both about base Nightlords only
        # (random_subset samples from create_regions()'s `locations`, never `everdark_locations`).
        included_nightlords = [
            nl for nl in self.options.included_nightlords.value if nl in NIGHTLORDS
        ]
        per_character = self.options.bosses_with_characters == "boss_and_character"

        if self.options.goal == "random_subset" and not per_character:
            raise OptionError(
                f"{self.player_name}: goal 'random_subset' requires bosses_with_characters to "
                "be 'boss_and_character'."
            )
        if self.options.goal == "night_aspect" and "Night Aspect" not in included_nightlords:
            raise OptionError(
                f"{self.player_name}: goal 'night_aspect' requires Night Aspect to be in "
                "included_nightlords, or the goal can never be completed."
            )

        self.goal_random_count = 0
        if self.options.goal == "random_subset":
            available = len(included_characters) * len(included_nightlords)
            goal_min = self.options.goal_random_min.value
            goal_max = self.options.goal_random_max.value
            if goal_min > available:
                raise OptionError(
                    f"{self.player_name}: goal_random_min ({goal_min}) is higher than the "
                    f"number of included_characters x included_nightlords combinations "
                    f"available ({available})."
                )
            if goal_min > goal_max:
                raise OptionError(
                    f"{self.player_name}: goal_random_min ({goal_min}) is higher than "
                    f"goal_random_max ({goal_max})."
                )
            self.goal_random_count = self.random.randint(goal_min, min(goal_max, available))

        # win_count_thresholds: the "Win N Expeditions" checks this slot actually generates (see
        # Locations.py's location_name_win_count and game_data.win_count_threshold_list) - empty
        # whenever win_count_checks is off. Passed to the client via fill_slot_data() rather than
        # letting it recompute from win_count_up_to itself, so the two can never drift apart.
        self.win_count_thresholds = []
        if self.options.win_count_checks:
            self.win_count_thresholds = win_count_threshold_list(self.options.win_count_up_to.value)

        # weak_reward_thresholds/strong_reward_thresholds: always empty for now - WeakRewardChecks/
        # StrongRewardChecks are commented out in Options.py (the underlying memory counter fires on
        # any weapon pickup, not just genuine reward-tier POI clears - see game_data.py's
        # REWARD_CHECK_THRESHOLDS comment). Left as real attributes (rather than deleted) so
        # create_regions()/fill_slot_data() below don't need their own special-casing, and so
        # restoring the option later is just restoring these two lines. Night 1/Night 2 Clear and
        # the Nightlord Bonus checks have no threshold list at all - they're universal, not opt-in.
        self.weak_reward_thresholds = []
        self.strong_reward_thresholds = []

    def create_regions(self) -> None:
        included_nightlords = self.options.included_nightlords.value

        # Iterate CHARACTERS/NIGHTLORDS (fixed order) rather than the option sets directly, so
        # location creation order stays deterministic. Each location is paired with the Nightlord
        # it defeats (and, in boss_and_character mode, the character - None in "boss" mode, since
        # locations aren't tied to a specific character there) so the access rule below can gate
        # it without re-parsing the location name.
        if self.options.bosses_with_characters == "boss_and_character":
            included_characters = self.options.included_characters.value
            locations = [
                (location_name(character, nightlord), nightlord, character)
                for character in CHARACTERS
                if character in included_characters
                for nightlord in NIGHTLORDS
                if nightlord in included_nightlords
            ]
        else:
            locations = [
                (location_name_boss_only(nightlord), nightlord, None)
                for nightlord in NIGHTLORDS
                if nightlord in included_nightlords
            ]

        # Everdark locations mirror bosses_with_characters exactly like the normal locations
        # above, but over whichever EVERDARK_NIGHTLORDS entries have their own "Everdark X" entry
        # in included_nightlords (see game_data.EVERDARK_NIGHTLORD_ENTRIES/Options.py's
        # IncludedNightlords) - each Everdark Sovereign is included independently of its base
        # Nightlord, empty list when none are selected. Deliberately kept out of goal_groups below
        # (see Options.py's disclaimer): Everdark Sovereign availability depends on an external
        # weekly rotation this world can't unlock or guarantee, so requiring one for the goal could
        # make a seed impossible to finish.
        self.everdark_nightlords = [
            nightlord for nightlord in EVERDARK_NIGHTLORDS
            if f"Everdark {nightlord}" in included_nightlords
        ]
        everdark_locations = []
        if self.options.bosses_with_characters == "boss_and_character":
            included_characters = self.options.included_characters.value
            everdark_locations = [
                (location_name_everdark(character, nightlord), nightlord, character)
                for character in CHARACTERS
                if character in included_characters
                for nightlord in EVERDARK_NIGHTLORDS
                if nightlord in self.everdark_nightlords
            ]
        else:
            everdark_locations = [
                (location_name_everdark_boss_only(nightlord), nightlord, None)
                for nightlord in EVERDARK_NIGHTLORDS
                if nightlord in self.everdark_nightlords
            ]

        # Extra check-density families - each expands `locations`/`everdark_locations` (already
        # filtered per-player above), reusing the exact same nightlord/character/everdark
        # association those pairs already carry so the access_rule built below stays identical to
        # the base "Defeat X" location's. Nightlord Bonus (4 extra locations alongside "Defeat X")
        # and Night 1/Night 2 Clear (exactly one location each) are universal - always generated,
        # no option gates them. Weak/Strong Reward stay opt-in, capped at a fixed 1-5
        # (self.weak_reward_thresholds/strong_reward_thresholds are [] when their toggle is off -
        # see generate_early()).
        def _expand_thresholds(base_list, name_fn, thresholds, everdark) -> list:
            return [
                (name_fn(nightlord, count, character, everdark), nightlord, character)
                for _name, nightlord, character in base_list
                for count in thresholds
            ]

        def _expand_single(base_list, name_fn, everdark) -> list:
            return [
                (name_fn(nightlord, character, everdark), nightlord, character)
                for _name, nightlord, character in base_list
            ]

        kill_bonus_locations = _expand_thresholds(
            locations, location_name_kill_bonus, NIGHTLORD_BONUS_INDICES, False
        )
        kill_bonus_everdark_locations = _expand_thresholds(
            everdark_locations, location_name_kill_bonus, NIGHTLORD_BONUS_INDICES, True
        )
        night1_locations = _expand_single(locations, location_name_night1, False)
        night1_everdark_locations = _expand_single(everdark_locations, location_name_night1, True)
        night2_locations = _expand_single(locations, location_name_night2, False)
        night2_everdark_locations = _expand_single(everdark_locations, location_name_night2, True)
        weak_reward_locations = _expand_thresholds(
            locations, location_name_weak_reward, self.weak_reward_thresholds, False
        )
        weak_reward_everdark_locations = _expand_thresholds(
            everdark_locations, location_name_weak_reward, self.weak_reward_thresholds, True
        )
        strong_reward_locations = _expand_thresholds(
            locations, location_name_strong_reward, self.strong_reward_thresholds, False
        )
        strong_reward_everdark_locations = _expand_thresholds(
            everdark_locations, location_name_strong_reward, self.strong_reward_thresholds, True
        )
        extra_check_locations = (
            kill_bonus_locations + kill_bonus_everdark_locations
            + night1_locations + night1_everdark_locations
            + night2_locations + night2_everdark_locations
            + weak_reward_locations + weak_reward_everdark_locations
            + strong_reward_locations + strong_reward_everdark_locations
        )

        # Cumulative "Win N Expeditions" locations - independent of boss/character, seed-scoped
        # (see self.win_count_thresholds, computed in generate_early()), never gated and never part
        # of goal_groups below. Empty whenever win_count_checks is off.
        win_count_names = [
            location_name_win_count(count) for count in self.win_count_thresholds
        ]

        self.active_locations = [
            name for name, _nightlord, _character in locations + everdark_locations + extra_check_locations
        ] + win_count_names

        # goal_groups: a list of groups, each satisfied by ANY one of its location ids being
        # checked; the goal is complete once EVERY group is satisfied (see client.py's
        # _goal_complete). This varies by `goal` option; the location set above never changes.
        # Built from `locations` only - everdark_locations is never goal-eligible, see above.
        goal = self.options.goal.current_key
        ids_by_name = self.location_name_to_id
        if goal == "night_aspect":
            self.goal_groups = [[
                ids_by_name[name] for name, nightlord, _character in locations
                if nightlord == "Night Aspect"
            ]]
        elif goal == "all_bosses_any_character":
            self.goal_groups = [
                [ids_by_name[name] for name, nl, _character in locations if nl == nightlord]
                for nightlord in NIGHTLORDS
                if nightlord in included_nightlords
            ]
        elif goal == "random_subset":
            chosen = self.random.sample(locations, self.goal_random_count)
            self.goal_groups = [[ids_by_name[name]] for name, _nightlord, _character in chosen]
        else:
            self.goal_groups = [[ids_by_name[name]] for name, _nightlord, _character in locations]

        menu = Region("Menu", self.player, self.multiworld)

        def _make_location(
            name: str, nightlord: str, everdark: bool, character: str | None
        ) -> NightreignLocation:
            location = NightreignLocation(self.player, name, self.location_name_to_id[name], menu)
            # Without this, the fill algorithm has no idea defeating a Nightlord requires
            # earning it first - it can (and did) place the only route to a Nightlord behind an
            # unreachable location, softlocking the run. gate_boss_access off needs no rule.
            # Everdark Sovereigns are treated as entirely separate bosses from their base Nightlord
            # - own checks, own "Everdark X Access" item, own freed_everdark_nightlords set, keyed
            # off the same nightlord name but never sharing the base Nightlord's Access item or
            # freed_nightlords entry. character is only set in boss_and_character mode - in "boss"
            # mode no location is tied to a specific character, so gate_character_access there only
            # controls in-game unlocking, never location reachability. Combined via a small
            # AND-rule when both the Nightlord and the character are gated, the same way AP's
            # access_rule mechanism is meant to be composed.
            rules = []
            if everdark:
                if self.options.gate_boss_access and nightlord not in self.freed_everdark_nightlords:
                    rules.append(lambda state, nightlord=nightlord: state.has(
                        f"Everdark {nightlord} Access", self.player
                    ))
            elif self.options.gate_boss_access and nightlord not in self.freed_nightlords:
                rules.append(lambda state, nightlord=nightlord: state.has(
                    f"{nightlord} Access", self.player
                ))
            if (character is not None and self.options.gate_character_access
                    and character not in self.freed_characters):
                rules.append(lambda state, character=character: state.has(
                    f"{character} Character Access", self.player
                ))
            if len(rules) == 1:
                location.access_rule = rules[0]
            elif rules:
                location.access_rule = lambda state, rules=rules: all(rule(state) for rule in rules)
            # Everdark locations are NOT excluded from progression (unlike an earlier revision of
            # this feature): now that Everdark Sovereigns are entirely separate bosses with their
            # own Access item, an Everdark location is just as legitimate a place for AP's fill
            # algorithm to route progression through as any other - the "might not be reachable
            # this week" risk is accepted as part of the same onus-on-the-player disclaimer that
            # already covers Everdark availability in general (see Options.py's
            # IncludedNightlords). goal_groups still excludes Everdark locations (see below) so
            # the goal itself is never required to depend on one, but that's a separate concern
            # from whether one may hold a progression item.
            return location

        def _add_menu_locations(location_list: list, everdark: bool) -> None:
            for name, nightlord, character in location_list:
                menu.locations.append(
                    _make_location(name, nightlord, everdark=everdark, character=character)
                )

        _add_menu_locations(locations, everdark=False)
        _add_menu_locations(everdark_locations, everdark=True)
        _add_menu_locations(kill_bonus_locations, everdark=False)
        _add_menu_locations(kill_bonus_everdark_locations, everdark=True)
        _add_menu_locations(night1_locations, everdark=False)
        _add_menu_locations(night1_everdark_locations, everdark=True)
        _add_menu_locations(night2_locations, everdark=False)
        _add_menu_locations(night2_everdark_locations, everdark=True)
        _add_menu_locations(weak_reward_locations, everdark=False)
        _add_menu_locations(weak_reward_everdark_locations, everdark=True)
        _add_menu_locations(strong_reward_locations, everdark=False)
        _add_menu_locations(strong_reward_everdark_locations, everdark=True)
        # No access_rule: win-count locations aren't tied to any specific boss/character Access
        # item, so - like everything else here (topology_present = False) - they're reachable from
        # the start.
        for name in win_count_names:
            menu.locations.append(
                NightreignLocation(self.player, name, self.location_name_to_id[name], menu)
            )
        self.multiworld.regions.append(menu)

    def create_items(self) -> None:
        if not self.active_locations:
            return

        access_names = []
        if self.options.gate_boss_access:
            included_nightlords = self.options.included_nightlords.value
            access_names = [
                f"{name} Access" for name in ACCESS_NIGHTLORDS
                if name in included_nightlords and name not in self.freed_nightlords
            ]

        character_access_names = []
        if self.options.gate_character_access:
            included_characters = self.options.included_characters.value
            character_access_names = [
                f"{name} Character Access" for name in ACCESS_CHARACTERS
                if name in included_characters and name not in self.freed_characters
            ]

        # Everdark Sovereigns are separate bosses from their base Nightlord (own checks, own
        # Access item), so gate_boss_access needs its own Everdark Access items too - one per
        # self.everdark_nightlords entry (computed in create_regions() from included_nightlords'
        # "Everdark X" entries), empty when none are included.
        everdark_access_names = []
        if self.options.gate_boss_access:
            everdark_access_names = [
                f"Everdark {name} Access" for name in self.everdark_nightlords
                if name not in self.freed_everdark_nightlords
            ]

        self.multiworld.itempool += [self.create_item(name) for name in access_names]
        self.multiworld.itempool += [self.create_item(name) for name in character_access_names]
        self.multiworld.itempool += [self.create_item(name) for name in everdark_access_names]

        # character_access_names (and, now, everdark_access_names) have no guarantee of fitting
        # active_locations the way access_names does: "boss" mode's location count tracks
        # included_nightlords only, not included_characters, so this can genuinely run out of
        # room. Structural limit, not a bug.
        total_progression = len(access_names) + len(character_access_names) + len(everdark_access_names)
        if total_progression > len(self.active_locations):
            raise OptionError(
                f"{self.player_name}: needs {total_progression} progression items "
                f"({len(access_names)} boss + {len(character_access_names)} character + "
                f"{len(everdark_access_names)} Everdark) but only "
                f"{len(self.active_locations)} locations exist with these settings. "
                "bosses_with_characters=boss only makes one location per Nightlord, not per "
                "character - switch to boss_and_character, reduce included_characters/"
                "included_nightlords, or disable gate_boss_access/gate_character_access."
            )

        filler_count = len(self.active_locations) - total_progression
        self.multiworld.itempool += [self.create_filler() for _ in range(filler_count)]

    def create_item(self, name: str) -> NightreignItem:
        data = item_table[name]
        return NightreignItem(name, data.classification, data.code, self.player)

    def get_filler_item_name(self) -> str:
        names = FILLER_ITEM_NAMES
        if self.options.receive_weapons:
            names = names + ["Randomized Weapon"]
        if self.options.receive_talismans:
            names = names + ["Randomized Talisman"]
        return self.random.choice(names)

    def fill_slot_data(self) -> dict:
        return {
            "gate_boss_access": bool(self.options.gate_boss_access),
            "gate_character_access": bool(self.options.gate_character_access),
            "unlock_all_bosses_in_game": bool(self.options.unlock_all_bosses_in_game),
            "receive_weapons": bool(self.options.receive_weapons),
            "receive_talismans": bool(self.options.receive_talismans),
            "win_count_checks": bool(self.options.win_count_checks),
            "win_count_thresholds": self.win_count_thresholds,
            # weak_reward_checks/strong_reward_checks: hardcoded False - the options are commented
            # out in Options.py (see generate_early()'s comment above). weak/strong_reward_thresholds
            # stay real keys (always []) so client.py's slot_data schema doesn't need touching.
            "weak_reward_checks": False,
            "weak_reward_thresholds": self.weak_reward_thresholds,
            "strong_reward_checks": False,
            "strong_reward_thresholds": self.strong_reward_thresholds,
            "everdark_nightlords": self.everdark_nightlords,
            "starting_boss": self.starting_boss,
            "starting_boss_everdark": self.starting_boss_everdark,
            "starting_character": self.starting_character,
            "bosses_with_characters": self.options.bosses_with_characters.current_key,
            "goal": self.options.goal.current_key,
            "goal_groups": self.goal_groups,
        }
