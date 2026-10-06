import unittest

from worlds.nightreign import tracker
from worlds.nightreign.Locations import location_name_to_id, location_name_win_count
from worlds.nightreign.tracker import AVAILABLE, DONE, LOCKED, boss_location_names


def _ids(nightlord, character=None, everdark=False) -> set:
    return {location_name_to_id[n] for n in boss_location_names(nightlord, character, everdark)}


class TestBossOnlyRows(unittest.TestCase):
    def _rows(self, owned, sent, gate=True):
        slot = _ids("Tricephalos") | _ids("Gaping Jaw")
        return {
            r.name: r.status for r in tracker.boss_rows(
                owned, slot, sent, ["Tricephalos", "Gaping Jaw"], set(), [], False, gate, False,
            )
        }

    def test_locked_available_done(self) -> None:
        rows = self._rows({"Tricephalos Access"}, set())
        self.assertEqual(rows, {"Tricephalos": AVAILABLE, "Gaping Jaw": LOCKED})
        rows = self._rows({"Tricephalos Access"}, _ids("Tricephalos"))
        self.assertEqual(rows["Tricephalos"], DONE)

    def test_unsent_night_check_keeps_boss_green(self) -> None:
        night2 = location_name_to_id["Clear Night 2 vs Tricephalos"]
        rows = self._rows({"Tricephalos Access"}, _ids("Tricephalos") - {night2})
        self.assertEqual(rows["Tricephalos"], AVAILABLE)

    def test_all_sent_is_gray_even_without_access(self) -> None:
        self.assertEqual(self._rows(set(), _ids("Gaping Jaw"))["Gaping Jaw"], DONE)

    def test_ungated_bosses_are_available(self) -> None:
        self.assertEqual(set(self._rows(set(), set(), gate=False).values()), {AVAILABLE})

    def test_bosses_without_slot_locations_are_skipped(self) -> None:
        rows = tracker.boss_rows(set(), _ids("Tricephalos"), set(), ["Tricephalos", "Gaping Jaw"],
                                 set(), [], False, True, False)
        self.assertEqual([r.name for r in rows], ["Tricephalos"])


class TestPerCharacterRows(unittest.TestCase):
    characters = ["Wylder", "Guardian"]

    def _boss(self, owned, sent, everdark=False):
        slot = set()
        for c in self.characters:
            slot |= _ids("Gaping Jaw", c, everdark)
        rows = tracker.boss_rows(
            owned, slot, sent, [] if everdark else ["Gaping Jaw"],
            {"Gaping Jaw"} if everdark else set(), self.characters, True, True, True,
        )
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_boss_green_if_any_character_green(self) -> None:
        boss = self._boss({"Gaping Jaw Access", "Wylder Character Access"}, set())
        self.assertEqual(boss.status, AVAILABLE)
        self.assertEqual({c.name: c.status for c in boss.children},
                         {"Wylder": AVAILABLE, "Guardian": LOCKED})

    def test_boss_red_when_only_red_remains(self) -> None:
        owned = {"Gaping Jaw Access", "Wylder Character Access"}
        boss = self._boss(owned, _ids("Gaping Jaw", "Wylder"))
        self.assertEqual(boss.status, LOCKED)
        self.assertEqual({c.name: c.status for c in boss.children},
                         {"Wylder": DONE, "Guardian": LOCKED})

    def test_missing_boss_access_locks_every_character(self) -> None:
        boss = self._boss({"Wylder Character Access", "Guardian Character Access"}, set())
        self.assertEqual({c.status for c in boss.children}, {LOCKED})
        self.assertEqual(boss.status, LOCKED)

    def test_boss_gray_once_every_character_cleared(self) -> None:
        sent = _ids("Gaping Jaw", "Wylder") | _ids("Gaping Jaw", "Guardian")
        self.assertEqual(self._boss(set(), sent).status, DONE)

    def test_everdark_uses_its_own_access_item(self) -> None:
        owned = {"Gaping Jaw Access", "Wylder Character Access", "Guardian Character Access"}
        self.assertEqual(self._boss(owned, set(), everdark=True).status, LOCKED)
        boss = self._boss(owned | {"Everdark Gaping Jaw Access"}, set(), everdark=True)
        self.assertEqual((boss.name, boss.status), ("Everdark Gaping Jaw", AVAILABLE))


class TestOtherRows(unittest.TestCase):
    def test_character_rows(self) -> None:
        rows = tracker.character_rows({"Wylder Character Access"}, ["Wylder", "Guardian"])
        self.assertEqual([(r.name, r.status) for r in rows],
                         [("Wylder", AVAILABLE), ("Guardian", LOCKED)])

    def test_win_count_rows_only_green_or_gray(self) -> None:
        one, five = (location_name_to_id[location_name_win_count(n)] for n in (1, 5))
        rows = tracker.win_count_rows({one, five}, {one}, [1, 5, 10])
        self.assertEqual([(r.name, r.status) for r in rows],
                         [("Win 1 Expedition", DONE), ("Win 5 Expeditions", AVAILABLE)])


class TestGoalRows(unittest.TestCase):
    @staticmethod
    def _id(nightlord, character=None) -> int:
        name = (f"Defeat {nightlord} as {character}" if character is not None
                else f"Defeat {nightlord}")
        return location_name_to_id[name]

    def _shape(self, rows) -> list:
        return [(r.name, r.status, [(c.name, c.status) for c in r.children]) for r in rows]

    def test_any_character_group_is_gray_once_any_child_is(self) -> None:
        group = [self._id("Night Aspect", c) for c in ("Wylder", "Guardian")]
        rows = tracker.goal_rows([group], set(), set(), False, False)
        self.assertEqual(self._shape(rows), [("Night Aspect (any character)", AVAILABLE,
                                              [("Wylder", AVAILABLE), ("Guardian", AVAILABLE)])])
        rows = tracker.goal_rows([group], set(), {group[1]}, False, False)
        self.assertEqual(rows[0].status, DONE)

    def test_singletons_collect_under_their_nightlord_in_roster_order(self) -> None:
        groups = [[self._id("Gaping Jaw", "Guardian")], [self._id("Tricephalos", "Guardian")],
                  [self._id("Tricephalos", "Wylder")]]
        sent = {self._id("Tricephalos", "Wylder")}
        rows = tracker.goal_rows(groups, set(), sent, False, False)
        self.assertEqual(self._shape(rows), [
            ("Tricephalos", AVAILABLE, [("Wylder", DONE), ("Guardian", AVAILABLE)]),
            ("Gaping Jaw", AVAILABLE, [("Guardian", AVAILABLE)]),
        ])

    def test_gating_marks_pending_objectives_red(self) -> None:
        groups = [[self._id("Tricephalos", "Wylder")], [self._id("Tricephalos", "Guardian")]]
        owned = {"Tricephalos Access", "Wylder Character Access"}
        rows = tracker.goal_rows(groups, owned, set(), True, True)
        self.assertEqual(self._shape(rows), [
            ("Tricephalos", AVAILABLE, [("Wylder", AVAILABLE), ("Guardian", LOCKED)]),
        ])

    def test_boss_only_rows_and_progress(self) -> None:
        groups = [[self._id("Tricephalos")], [self._id("Gaping Jaw")]]
        sent = {self._id("Gaping Jaw")}
        rows = tracker.goal_rows(groups, set(), sent, True, False)
        self.assertEqual(self._shape(rows), [("Tricephalos", LOCKED, []), ("Gaping Jaw", DONE, [])])
        self.assertEqual(tracker.goal_progress(groups, sent), (1, 2))
